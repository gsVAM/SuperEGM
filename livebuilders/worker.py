"""One detached job. S3 is the mailbox and durable output, never a shared checkout."""
import argparse
import fcntl
import shutil
import json
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path

from protocol import MAX_BYTES, MAX_FILES, Store, checked, digest, encoded, prefixes, redacted, safe_name, scan, unpack


OUTPUT_REASONS = {
    'Path is not valid UTF-8': 'path_encoding',
    'Path exceeds 512 serialized bytes': 'path_too_long',
    'Unsafe artifact path': 'unsafe_path',
    'Artifact directory must not be a symlink': 'non_regular',
    'Only regular output files may be uploaded': 'non_regular',
    'Too many output artifacts': 'too_many',
    'Output exceeds limit': 'too_large',
    'Output grew beyond limit': 'too_large',
    'Credential pattern detected; object was not published': 'credential_pattern',
}


def kill_group(process):
    if process is not None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run(store, owner, run_id, request_hash, root):
    inp, out = prefixes(owner, run_id)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # A process lock admits one preflight at a time and is released on a crash.
    with (root / 'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if (root / 'started').exists():
            return  # Never replay a command that may have had side effects.
        for name in ('workspace', 'artifacts'):
            shutil.rmtree(root / name, ignore_errors=True)
        return execute(store, owner, run_id, request_hash, root)


def execute(store, owner, run_id, request_hash, root):
    inp, out = prefixes(owner, run_id)
    admitted = False
    sequence = 0
    process = None
    selector = None
    started = time.monotonic()
    status, exit_code = 'failed', None
    log = []
    log_bytes = 0
    delivered = 0

    def event(kind, **fields):
        nonlocal sequence
        next_sequence = sequence + 1
        payload = {'schema': 1, 'run_id': run_id, 'sequence': next_sequence, 'type': kind, **fields}
        store.put_json(out + f'events/{next_sequence:08d}.json', payload)
        sequence = next_sequence

    try:
        raw, _ = store.get(inp + 'request.json', 1024 * 1024)
        if digest(raw) != request_hash:
            raise ValueError('Request digest mismatch')
        request = json.loads(raw)
        if request['run_id'] != run_id or request['owner'] != owner:
            raise ValueError('Request identity mismatch')
        command = request['command']
        if not isinstance(command, list) or not command or not all(isinstance(s, str) and '\x00' not in s for s in command):
            raise ValueError('Command must be an argv array')
        timeout = request['timeout_seconds']
        if type(timeout) is not int or not 1 <= timeout <= 2400:
            raise ValueError('Job timeout must be between 1 and 2400 seconds')
        source, _ = store.get(inp + 'source.tar.gz')
        unpack(checked(source, request['source']), root / 'workspace')
        work = root / 'workspace'
        (root / 'brief.md').write_text(request.get('brief', ''))
        artifacts = root / 'artifacts'
        artifacts.mkdir(mode=0o700)
        # Preflight is complete. Persist admission before any command side effects.
        marker = os.open(root / 'started', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(marker)
        admitted = True
        event('started')
        env = dict(os.environ, LB_INPUT_DIR=str(work), LB_OUTPUT_DIR=str(artifacts), LB_BRIEF_PATH=str(root / 'brief.md'), PYTHONUNBUFFERED='1')
        process = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stdin.fileno(), False)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        pending = b''
        truncated = False
        stdin_pending = b''
        next_poll = 0.0
        while process.poll() is None or selector.get_map():
            if time.monotonic() - started > timeout:
                status = 'timed_out'
                kill_group(process)
                break
            if time.monotonic() >= next_poll and process.poll() is None:
                control, _ = store.json(inp + 'control.json')
                if control['stop']:
                    status = 'cancelled'
                    kill_group(process)
                    break
                messages = control['messages']
                for message in messages[delivered:]:
                    stdin_pending += encoded(message) + b'\n'
                    event('input_queued', request_id=message['request_id'])
                    delivered += 1
                next_poll = time.monotonic() + 1
            if stdin_pending and process.poll() is None:
                try:
                    count = os.write(process.stdin.fileno(), stdin_pending)
                    stdin_pending = stdin_pending[count:]
                except BlockingIOError:
                    pass
                except BrokenPipeError:
                    event('input_closed', detail='Job closed stdin; queued messages were not delivered')
                    stdin_pending = b''
            for key, _ in selector.select(timeout=0.2):
                chunk = os.read(key.fd, 16384)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                lines = []
                parts = chunk.split(b'\n')
                for index, part in enumerate(parts):
                    available = 65536 - len(pending)
                    pending += part[:available]
                    truncated = truncated or len(part) > available
                    if index < len(parts) - 1:
                        text = '[oversized line omitted]' if truncated else redacted(pending.decode(errors='replace'))
                        remaining = 16 * 1024 * 1024 - log_bytes
                        if remaining > 0:
                            data = (text + '\n').encode()[:remaining]
                            log_bytes += len(data)
                            text = data.decode(errors='ignore')
                            log.append(text)
                            lines.append(text.rstrip('\n'))
                        pending, truncated = b'', False
                if lines:
                    event('output', text='\n'.join(lines))
            if process.poll() is not None and not selector.get_map():
                break
        if pending and log_bytes < 16 * 1024 * 1024:
            text = '[oversized line omitted]' if truncated else redacted(pending.decode(errors='replace'))
            text = text.encode()[:16 * 1024 * 1024 - log_bytes].decode(errors='ignore')
            log.append(text)
            event('output', text=text)
        exit_code = process.wait()
        if status not in ('cancelled', 'timed_out'):
            status = 'passed' if exit_code == 0 else 'failed'
    except Exception as error:
        if not admitted and not isinstance(error, (ValueError, KeyError, TypeError)):
            # No command ran. A later resume may safely repeat preflight.
            (root / 'preflight-error.txt').write_text(type(error).__name__)
            return
        # Do not publish SDK exception bodies, presigned URLs, or command secrets.
        event('error', error_type=type(error).__name__)
        status = 'failed'
    finally:
        kill_group(process)  # Also kill children left behind by an exited parent.
        if selector is not None:
            selector.close()
        if process is not None:
            process.stdin.close()
            process.stdout.close()

    result = {'schema': 1, 'owner': owner, 'run_id': run_id, 'status': status, 'job_status': status, 'exit_code': exit_code, 'elapsed_seconds': round(time.monotonic() - started, 2)}
    try:
        artifacts = root / 'artifacts'
        if artifacts.is_symlink():
            raise ValueError('Artifact directory must not be a symlink')
        artifacts.mkdir(exist_ok=True)
        collected = [('job.log', ''.join(log).encode()), ('result.json', encoded(result))]
        total = sum(len(data) for _, data in collected)
        for _, data in collected:
            scan(data)
        for file in sorted(artifacts.rglob('*')):
            if file.is_dir() and not file.is_symlink():
                continue
            if len(collected) >= MAX_FILES:
                raise ValueError('Too many output artifacts')
            name = safe_name('artifacts/' + file.relative_to(artifacts).as_posix())
            if file.is_symlink() or not file.is_file():
                raise ValueError('Only regular output files may be uploaded')
            if total + file.stat().st_size > MAX_BYTES:
                raise ValueError('Output exceeds limit')
            with file.open('rb') as stream:
                data = stream.read(MAX_BYTES - total + 1)
            total += len(data)
            if total > MAX_BYTES:
                raise ValueError('Output grew beyond limit')
            scan(data)
            collected.append((name, data))
    except (ValueError, OSError) as error:
        # Validation finishes before any artifact upload. Publish a small safe
        # failure result, not partial/secret-bearing outputs or an endless wait.
        status = 'failed'
        reason = 'filesystem_error' if isinstance(error, OSError) else OUTPUT_REASONS.get(str(error), 'validation_failed')
        result.update(status=status, output_error_type=type(error).__name__, output_error_reason=reason)
        event('error', stage='outputs', error_type=type(error).__name__, reason=reason)
        collected = [('job.log', b'Output validation failed; job log and artifacts omitted.\n'), ('result.json', encoded(result))]
    entries = []
    for name, data in collected:
        key = out + 'out/' + name
        store.put(key, data)
        entries.append({'name': name, 'key': key, 'size': len(data), 'sha256': digest(data)})
    event('finished', status=status, exit_code=exit_code)
    manifest = {**result, 'request_sha256': request_hash, 'last_event': sequence, 'files': entries}
    # Completion is published only after all output uploads succeed.
    store.put_json(out + 'manifest.json', manifest)
    (root / 'manifest.json').write_bytes(encoded(manifest))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('bucket', 'region', 'owner', 'run-id', 'request-sha256', 'root'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    import boto3
    run(Store(boto3.client('s3', region_name=args.region), args.bucket), args.owner, args.run_id, args.request_sha256, args.root)
