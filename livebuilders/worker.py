"""One detached job. S3 is the mailbox and durable output, never a shared checkout."""
import argparse
import json
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path

from protocol import MAX_BYTES, MAX_FILES, Store, checked, digest, encoded, prefixes, redacted, safe_name, scan, unpack


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
    # The volume survives a compute restart. An old marker deliberately prevents
    # replaying arbitrary side effects, even if the first worker died mid-command.
    try:
        marker = os.open(root / 'started', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return
    os.close(marker)
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
        sequence += 1
        payload = {'schema': 1, 'run_id': run_id, 'sequence': sequence, 'type': kind, **fields}
        store.put_json(out + f'events/{sequence:08d}.json', payload)

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
        event('started', command=command)
        env = dict(os.environ, LB_INPUT_DIR=str(work), LB_OUTPUT_DIR=str(artifacts), LB_BRIEF_PATH=str(root / 'brief.md'), PYTHONUNBUFFERED='1')
        process = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        os.set_blocking(process.stdout.fileno(), False)
        os.set_blocking(process.stdin.fileno(), False)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        pending = b''
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
                pending += chunk
                lines = []
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    if log_bytes < 16 * 1024 * 1024:
                        text = redacted(line.decode(errors='replace'))[:65536]
                        log_bytes += len(text.encode())
                        log.append(text + '\n')
                        lines.append(text)
                if lines:
                    event('output', text='\n'.join(lines))
                if len(pending) > 65536:
                    raise ValueError('Job emitted an oversized output line')
            if process.poll() is not None and not selector.get_map():
                break
        if pending:
            text = redacted(pending.decode(errors='replace'))
            log.append(text)
            event('output', text=text)
        exit_code = process.wait()
        if status not in ('cancelled', 'timed_out'):
            status = 'passed' if exit_code == 0 else 'failed'
    except Exception as error:
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

    artifacts = root / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    result = {'schema': 1, 'owner': owner, 'run_id': run_id, 'status': status, 'exit_code': exit_code, 'elapsed_seconds': round(time.monotonic() - started, 2)}
    (root / 'job.log').write_text(''.join(log))
    (root / 'result.json').write_bytes(encoded(result))
    files = [('job.log', root / 'job.log'), ('result.json', root / 'result.json')]
    files += [('artifacts/' + p.relative_to(artifacts).as_posix(), p) for p in sorted(artifacts.rglob('*')) if not p.is_dir() or p.is_symlink()]
    if len(files) > MAX_FILES:
        raise ValueError('Too many output artifacts')
    entries = []
    total = 0
    for name, file in files:
        safe_name(name)
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
