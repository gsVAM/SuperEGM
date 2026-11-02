#!/usr/bin/env python3
"""Laptop CLI for the livebuilders S3 transport. No model credentials required."""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import unicodedata
import uuid
from pathlib import Path

from protocol import Store, bundle, checked, digest, encoded, output_entries, prefixes, scan


def session(profile):
    try:
        import boto3
        return boto3.Session(profile_name=profile)
    except ImportError:
        # Homebrew AWS CLI bundles a current SDK, including browser-login support.
        import awscli.botocore.session
        return awscli.botocore.session.Session(profile=profile)


def client(sdk, service, region):
    try:
        from botocore.config import Config
    except ImportError:
        from awscli.botocore.config import Config
    factory = getattr(sdk, 'client', None) or sdk.create_client
    return factory(service, region_name=region, config=Config(connect_timeout=10, read_timeout=180 if service == 'bedrock-agentcore' else 30, retries={'max_attempts': 2}))


class Laptop:
    def __init__(self, config, state_dir):
        self.config = config
        self.sdk = session(config['profile'])
        identity = client(self.sdk, 'sts', config['region']).get_caller_identity()
        if identity['Account'] != config['account_id'] or config['runtime_arn'].split(':')[4] != identity['Account']:
            raise ValueError('AWS account does not match the builders configuration')
        # IAM user ARN is stable. Role-session ARNs are deliberately unsupported
        # until owner identity mapping and multi-user authorization are designed.
        if ':user/' not in identity['Arn']:
            raise ValueError('Prototype requires a dedicated IAM user profile')
        self.principal = identity['Arn']
        self.owner = hashlib.sha256(self.principal.encode()).hexdigest()[:24]
        self.store = Store(client(self.sdk, 's3', config['region']), config['bucket'])
        self.agent = client(self.sdk, 'bedrock-agentcore', config['region'])
        self.state = Path(state_dir).expanduser() / self.owner
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)

    def request(self, run_id):
        inp, out = prefixes(self.owner, run_id)
        raw, _ = self.store.get(inp + 'request.json', 1024 * 1024)
        request = json.loads(raw)
        if request['owner'] != self.owner or request['run_id'] != run_id or request['principal'] != self.principal:
            raise ValueError('Run ownership mismatch')
        return request, digest(raw), inp, out

    def run(self, source, brief, command, timeout):
        if not command or not 1 <= timeout <= 2400:
            raise ValueError('Command and a timeout between 1 and 2400 seconds are required')
        archive = bundle(source)
        text = Path(brief).read_bytes()
        if len(text) > 65536:
            raise ValueError('Brief exceeds 64 KiB')
        scan(text)
        scan(encoded(command))
        run_id = str(uuid.uuid4())
        self.last_run_id = run_id
        inp, _ = prefixes(self.owner, run_id)
        request = {'schema': 1, 'owner': self.owner, 'principal': self.principal, 'run_id': run_id,
                   'command': command, 'timeout_seconds': timeout,
                   'source': {'size': len(archive), 'sha256': digest(archive)},
                   'brief': text.decode(), 'runtime_arn': self.config['runtime_arn']}
        print(json.dumps({'run_id': run_id, 'inputs_uploaded': False}), flush=True)
        self.store.put(inp + 'source.tar.gz', archive, IfNoneMatch='*')
        self.store.put_json(inp + 'control.json', {'schema': 1, 'stop': False, 'messages': []}, IfNoneMatch='*')
        self.store.put_json(inp + 'request.json', request, IfNoneMatch='*')
        # Print before a potentially ambiguous network failure. resume uses this
        # same durable request and session ID, never a newly generated job.
        print(json.dumps({'run_id': run_id, 'inputs_uploaded': True}), flush=True)
        return self.resume(run_id)

    def resume(self, run_id):
        request, sha, _, out = self.request(run_id)
        final = self.store.optional(out + 'manifest.json')
        if final:
            return self.validate_manifest(final, request, sha, out)
        if request['runtime_arn'] != self.config['runtime_arn']:
            raise ValueError('Run belongs to another runtime')
        response = self.agent.invoke_agent_runtime(agentRuntimeArn=self.config['runtime_arn'], runtimeSessionId=run_id,
                                                   contentType='application/json', accept='application/json',
                                                   payload=encoded({'action': 'start', 'owner': self.owner, 'run_id': run_id, 'request_sha256': sha}))
        try:
            result = json.loads(response['response'].read())
        finally:
            response['response'].close()
        if not result.get('accepted') or result.get('run_id') != run_id:
            raise ValueError('Runtime did not accept the run')
        return result

    def control(self, run_id, text=None, request_id=None, stop=False):
        _, _, inp, out = self.request(run_id)
        if self.store.optional(out + 'manifest.json'):
            raise ValueError('Run already finished')
        if text is not None:
            scan(text.encode())
            if len(text.encode()) > 4096:
                raise ValueError('Message exceeds 4 KiB')
        request_id = str(uuid.UUID(request_id)) if request_id else str(uuid.uuid4())
        for _ in range(10):
            control, etag = self.store.json(inp + 'control.json')
            for message in control['messages']:
                if message['request_id'] == request_id:
                    if message['text'] != text:
                        raise ValueError('Request ID reused with different input')
                    return {'request_id': request_id, 'duplicate': True}
            if stop:
                control['stop'] = True
            else:
                if control['stop'] or len(control['messages']) >= 128:
                    raise ValueError('Mailbox stopped or full')
                control['messages'].append({'request_id': request_id, 'text': text})
            data = encoded(control)
            if len(data) > 65536:
                raise ValueError('Mailbox exceeds 64 KiB')
            try:
                self.store.put(inp + 'control.json', data, IfMatch=etag)
                return {'request_id': request_id, 'queued': not stop, 'stop_requested': stop}
            except Exception as error:
                if getattr(error, 'response', {}).get('Error', {}).get('Code') not in ('PreconditionFailed', 'ConditionalRequestConflict', '412', '409'):
                    raise
                time.sleep(0.2)
        raise RuntimeError('Mailbox changed repeatedly; retry with the same request ID')

    def validate_manifest(self, manifest, request, sha, out):
        if manifest['owner'] != self.owner or manifest['run_id'] != request['run_id'] or manifest['request_sha256'] != sha:
            raise ValueError('Manifest identity mismatch')
        output_entries(manifest, out)
        return manifest

    def status(self, run_id):
        request, sha, _, out = self.request(run_id)
        manifest = self.store.optional(out + 'manifest.json')
        return self.validate_manifest(manifest, request, sha, out) if manifest else {'run_id': run_id, 'status': 'incomplete', 'detail': 'No final manifest yet; this does not prove the worker is alive'}

    def watch(self, run_id, once=False, replay=False):
        request, sha, _, out = self.request(run_id)
        cursor = self.state / (run_id + '.cursor')
        after = 0 if replay or not cursor.exists() else int(cursor.read_text())
        while True:
            while True:
                event = self.store.optional(out + f'events/{after + 1:08d}.json')
                if event is None:
                    break
                if event['run_id'] != run_id or event['sequence'] != after + 1:
                    raise ValueError('Event sequence mismatch')
                print(json.dumps(event), flush=True)
                after += 1
                temporary = cursor.with_suffix('.tmp')
                temporary.write_text(str(after))
                temporary.replace(cursor)
            manifest = self.store.optional(out + 'manifest.json')
            if manifest:
                self.validate_manifest(manifest, request, sha, out)
                if after >= manifest['last_event']:
                    return {'run_id': run_id, 'status': manifest['status'], 'last_event': after}
            if once:
                return {'run_id': run_id, 'last_event': after, 'status': 'incomplete'}
            time.sleep(1)

    def fetch(self, run_id, destination):
        request, sha, _, out = self.request(run_id)
        manifest = self.store.optional(out + 'manifest.json')
        if manifest is None:
            raise ValueError('Run has no final manifest; output is incomplete')
        self.validate_manifest(manifest, request, sha, out)
        entries = output_entries(manifest, out)
        names = {'manifest.json'}
        for item in entries:
            portable = unicodedata.normalize('NFC', item['name']).casefold()
            if portable in names:
                raise ValueError('Artifact names collide on a case-insensitive filesystem')
            names.add(portable)
        destination = Path(destination).absolute()
        if destination.exists() or destination.is_symlink():
            raise ValueError('Fetch destination must not already exist')
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix='.lb-fetch-', dir=destination.parent))
        try:
            for item in entries:
                data, _ = self.store.get(item['key'], item['size'])
                checked(data, item)
                scan(data)
                file = temporary / item['name']
                file.parent.mkdir(parents=True, exist_ok=True)
                with file.open('xb') as stream:
                    stream.write(data)
            with (temporary / 'manifest.json').open('xb') as stream:
                stream.write(encoded(manifest))
            temporary.rename(destination)
        except BaseException:
            shutil.rmtree(temporary)
            raise
        return {'run_id': run_id, 'status': manifest['status'], 'verified_files': len(manifest['files']), 'directory': str(destination)}

    def cleanup(self, run_id, force=False):
        self.request(run_id)  # Still verify ownership when forcing cleanup.
        if not force and self.status(run_id)['status'] == 'incomplete':
            raise ValueError('No final manifest; stop and collect first, or explicitly use --force')
        response = self.agent.delete_capacity_provider_session(capacityProviderId=self.config['capacity_provider_id'], sessionId=run_id)
        return {'run_id': run_id, 'status': response['status']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--state-dir', type=Path, default=Path.home() / '.cache/livebuilders')
    commands = parser.add_subparsers(dest='action', required=True)
    launch = commands.add_parser('run')
    launch.add_argument('--source', required=True)
    launch.add_argument('--brief', required=True)
    launch.add_argument('--timeout', type=int, default=300)
    launch.add_argument('command', nargs=argparse.REMAINDER)
    for name in ('resume', 'status', 'watch', 'fetch', 'send', 'stop', 'cleanup'):
        p = commands.add_parser(name)
        p.add_argument('run_id')
        if name == 'watch':
            p.add_argument('--once', action='store_true')
            p.add_argument('--replay', action='store_true')
        if name == 'fetch':
            p.add_argument('--destination', required=True)
        if name == 'send':
            p.add_argument('text')
            p.add_argument('--request-id')
        if name == 'cleanup':
            p.add_argument('--force', action='store_true')
    args = parser.parse_args()
    laptop = Laptop(json.loads(args.config.read_text()), args.state_dir)
    if args.action == 'run':
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        result = laptop.run(args.source, args.brief, command, args.timeout)
    elif args.action == 'send':
        result = laptop.control(args.run_id, args.text, args.request_id)
    elif args.action == 'stop':
        result = laptop.control(args.run_id, stop=True)
    elif args.action == 'watch':
        result = laptop.watch(args.run_id, args.once, args.replay)
    elif args.action == 'fetch':
        result = laptop.fetch(args.run_id, args.destination)
    elif args.action == 'cleanup':
        result = laptop.cleanup(args.run_id, args.force)
    else:
        result = getattr(laptop, args.action)(args.run_id)
    print(json.dumps(result), flush=True)
    return 1 if result.get('status') in ('failed', 'cancelled', 'timed_out') else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('Detached. The remote job continues; use watch/fetch with its run ID.', file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        # SDK errors may include request URLs. Keep logs free of credential-bearing URLs.
        print(str(error) if isinstance(error, ValueError) else type(error).__name__, file=sys.stderr)
        sys.exit(2)
