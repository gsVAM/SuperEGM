"""Offline protocol tests using real files/processes; AWS acceptance is separate."""
import contextlib
import io
import json
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import runtime
import uuid
from pathlib import Path

from lb import Laptop
from protocol import Store, bundle, digest, encoded, output_entries, prefixes, safe_name, unpack
from worker import run


class FileObjects:
    """Local object storage for protocol unit tests (does not simulate AWS IAM)."""
    def __init__(self, root):
        self.root = root

    def put(self, key, data, **conditions):
        file = self.root / key
        file.parent.mkdir(parents=True, exist_ok=True)
        temporary = file.with_name(file.name + '.' + uuid.uuid4().hex)
        temporary.write_bytes(data)
        temporary.replace(file)

    def put_json(self, key, value, **conditions):
        self.put(key, encoded(value))

    def get(self, key, limit=None):
        data = (self.root / key).read_bytes()
        if limit is not None and len(data) > limit:
            raise ValueError('Object exceeds limit')
        return data, digest(data)

    def json(self, key):
        data, etag = self.get(key)
        return json.loads(data), etag

    def optional(self, key):
        try:
            return self.json(key)[0]
        except FileNotFoundError:
            return None


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = FileObjects(self.root / 'objects')
        self.owner, self.run_id = 'a' * 24, str(uuid.uuid4())
        self.inp, self.out = prefixes(self.owner, self.run_id)
        self.source = self.root / 'source'
        self.source.mkdir()

    def prepare(self, code, timeout=10):
        (self.source / 'job.py').write_text(code)
        archive = bundle(self.source)
        self.request = {'schema': 1, 'owner': self.owner, 'run_id': self.run_id, 'principal': 'test-owner',
                        'command': [sys.executable, '-u', 'job.py'], 'timeout_seconds': timeout,
                        'source': {'size': len(archive), 'sha256': digest(archive)}}
        self.store.put(self.inp + 'source.tar.gz', archive)
        self.store.put_json(self.inp + 'control.json', {'messages': [], 'stop': False})
        self.store.put_json(self.inp + 'request.json', self.request)
        self.sha = digest(encoded(self.request))

    def execute(self):
        run(self.store, self.owner, self.run_id, self.sha, self.root / 'worker')

    def laptop(self):
        laptop = Laptop.__new__(Laptop)
        laptop.owner, laptop.principal, laptop.store = self.owner, 'test-owner', self.store
        laptop.state = self.root / 'state'
        laptop.state.mkdir(exist_ok=True)
        return laptop

    def test_runtime_owner_pin_and_preflight_retry_admission(self):
        self.prepare("print('ok')\n")
        class Process:
            code = None
            def poll(inner):
                return inner.code
        process = Process()
        class Request:
            path = '/invocations'
            value = {'action': 'start', 'owner': self.owner, 'run_id': self.run_id, 'request_sha256': self.sha}
            def read_body(inner):
                return encoded(inner.value)
            def respond(inner, code, value):
                inner.response = code, value
        request = Request()
        original_path = Path
        def local_path(value):
            return self.root / 'runtime' if value == '/mnt/workspace/livebuilders' else original_path(value)
        with patch.dict(runtime.os.environ, {'LB_OWNER': self.owner, 'LB_BUCKET': 'test', 'AWS_REGION': 'test'}), patch.object(runtime, 'WORKERS', {}), patch.object(runtime, 'Path', local_path), patch.object(runtime.subprocess, 'Popen', return_value=process) as launch:
            request.value = dict(request.value, owner='b' * 24)
            runtime.Handler.do_POST(request)
            self.assertEqual(request.response[0], 400)
            launch.assert_not_called()
            request.value['owner'] = self.owner
            runtime.Handler.do_POST(request)
            self.assertEqual(request.response[0], 202)
            runtime.Handler.do_POST(request)
            self.assertTrue(request.response[1]['duplicate'])
            self.assertEqual(launch.call_count, 1)
            process.code = 0
            runtime.Handler.do_POST(request)
            self.assertEqual(launch.call_count, 2)
            (self.root / 'runtime' / self.owner / self.run_id / 'started').touch()
            runtime.Handler.do_POST(request)
            self.assertTrue(request.response[1]['duplicate'])
            self.assertEqual(launch.call_count, 2)

    def test_started_event_omits_opaque_command_argument(self):
        self.prepare("print('done')\n")
        self.request['command'].append('opaque-credential-example')
        self.store.put_json(self.inp + 'request.json', self.request)
        self.sha = digest(encoded(self.request))
        self.execute()
        self.assertNotIn(b'opaque-credential-example', self.store.get(self.out + 'events/00000001.json')[0])

    def test_large_manifest_status_fetch_and_forced_cleanup(self):
        self.prepare("print('done')\n")
        self.execute()
        final = self.store.optional(self.out + 'manifest.json')
        for index in range(5000):
            name = 'artifacts/' + str(index) + '-' + 'x' * 100
            key = self.out + 'out/' + name
            self.store.put(key, b'x')
            final['files'].append({'name': name, 'key': key, 'size': 1, 'sha256': digest(b'x')})
        self.store.put_json(self.out + 'manifest.json', final)
        self.assertGreater(len(encoded(final)), 1024 * 1024)
        # Exercise the production JSON read limit over local object bytes.
        self.store.json = lambda key: Store.json(self.store, key)
        laptop = self.laptop()
        self.assertEqual(laptop.status(self.run_id)['status'], 'passed')
        self.assertEqual(laptop.fetch(self.run_id, self.root / 'large')['verified_files'], 5002)
        class Agent:
            def delete_capacity_provider_session(inner, **kwargs):
                return {'status': 'Deprovisioning'}
        laptop.agent, laptop.config = Agent(), {'capacity_provider_id': 'test'}
        self.assertEqual(laptop.cleanup(self.run_id)['status'], 'Deprovisioning')
        self.store.put(self.out + 'manifest.json', b'not-json')
        self.assertEqual(laptop.cleanup(self.run_id, force=True)['status'], 'Deprovisioning')

    def test_ambiguous_upload_prints_id_before_first_write(self):
        (self.source / 'job.py').write_text('pass')
        brief = self.root / 'brief.txt'
        brief.write_text('test')
        laptop = self.laptop()
        laptop.config = {'runtime_arn': 'runtime'}
        output = io.StringIO()
        def failed_put(key, data, **kwargs):
            self.assertIn(laptop.last_run_id, output.getvalue())
            self.assertIn('false', output.getvalue())
            raise OSError('lost response')
        self.store.put = failed_put
        with contextlib.redirect_stdout(output), self.assertRaises(OSError):
            laptop.run(self.source, brief, ['python3', 'job.py'], 10)

    def test_preflight_failure_is_retryable_without_replaying_execution(self):
        self.prepare("print('executed once')\n")
        original = self.store.get
        def transient(key, limit=None):
            if key.endswith('source.tar.gz'):
                raise OSError('temporary source failure')
            return original(key, limit)
        self.store.get = transient
        self.execute()
        self.assertFalse((self.root / 'worker/started').exists())
        self.assertIsNone(self.store.optional(self.out + 'manifest.json'))
        self.store.get = original
        self.execute()
        self.assertEqual(self.laptop().status(self.run_id)['status'], 'passed')
        manifest = self.store.get(self.out + 'manifest.json')[0]
        self.execute()
        self.assertEqual(self.store.get(self.out + 'manifest.json')[0], manifest)

    def test_long_lines_do_not_fail_job_or_expose_command_arguments(self):
        self.prepare("import time\nprint('x'*100000,flush=True)\ntime.sleep(.2)\nprint('completed')\n")
        self.request['command'].append('opaque-credential-example')
        self.store.put_json(self.inp + 'request.json', self.request)
        self.sha = digest(encoded(self.request))
        self.execute()
        self.assertEqual(self.laptop().status(self.run_id)['status'], 'passed')
        self.assertIn(b'completed', self.store.get(self.out + 'out/job.log')[0])
        for file in (self.store.root / self.out / 'events').iterdir():
            self.assertNotIn(b'opaque-credential-example', file.read_bytes())

    def test_excluded_symlinks_are_not_followed_or_archived(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'secret').write_text('sk-ant-' + 'x' * 25)
        (self.source / 'node_modules').symlink_to(outside, target_is_directory=True)
        (self.source / '.env').symlink_to(outside / 'secret')
        (self.source / 'ok').write_text('included')
        unpack(bundle(self.source), self.root / 'excluded')
        self.assertEqual([p.name for p in (self.root / 'excluded').iterdir()], ['ok'])

    def test_followup_reconnect_fetch_and_duplicate_start(self):
        self.prepare("import os,json,sys,time\nfrom pathlib import Path\nprint('ready',flush=True)\nm=json.loads(sys.stdin.readline())\nprint(m['text'],flush=True)\ntime.sleep(.2)\nPath(os.environ['LB_OUTPUT_DIR'],'answer.txt').write_text(m['text'])\n")
        thread = threading.Thread(target=self.execute)
        thread.start()
        deadline = time.monotonic() + 5
        while not self.store.optional(self.out + 'events/00000002.json'):
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.05)
        laptop = self.laptop()
        with contextlib.redirect_stdout(io.StringIO()) as first:
            snapshot = laptop.watch(self.run_id, once=True)
        self.assertEqual(snapshot['status'], 'incomplete')
        self.assertIn('ready', first.getvalue())
        self.store.put_json(self.inp + 'control.json', {'stop': False, 'messages': [{'request_id': str(uuid.uuid4()), 'text': 'followup'}]})
        thread.join(5)
        self.assertFalse(thread.is_alive())
        with contextlib.redirect_stdout(io.StringIO()) as second:
            result = self.laptop().watch(self.run_id)
        self.assertEqual(result['status'], 'passed')
        self.assertNotIn('"text": "ready"', second.getvalue())
        self.assertIn('followup', second.getvalue())
        manifest = self.store.get(self.out + 'manifest.json')[0]
        self.execute()
        self.assertEqual(self.store.get(self.out + 'manifest.json')[0], manifest)
        destination = self.root / 'fetched'
        laptop.fetch(self.run_id, destination)
        self.assertEqual((destination / 'artifacts/answer.txt').read_text(), 'followup')

    def test_timeout_stops_process_and_publishes_partial_log(self):
        self.prepare("import time\nprint('before timeout',flush=True)\ntime.sleep(60)\n", timeout=1)
        start = time.monotonic()
        self.execute()
        self.assertLess(time.monotonic() - start, 5)
        final = self.store.optional(self.out + 'manifest.json')
        self.assertEqual(final['status'], 'timed_out')
        self.assertIn(b'before timeout', self.store.get(self.out + 'out/job.log')[0])

    def test_mailbox_cancellation_saves_a_cancelled_manifest(self):
        self.prepare("import time\ntime.sleep(60)\n")
        self.store.put_json(self.inp + 'control.json', {'stop': True, 'messages': []})
        self.execute()
        self.assertEqual(self.store.optional(self.out + 'manifest.json')['status'], 'cancelled')

    def test_nonzero_exit_keeps_failure_and_downloadable_evidence(self):
        self.prepare("import sys\nprint('expected failure')\nsys.exit(7)\n")
        self.execute()
        final = self.store.optional(self.out + 'manifest.json')
        self.assertEqual((final['status'], final['exit_code']), ('failed', 7))
        result = self.laptop().fetch(self.run_id, self.root / 'failed-output')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('expected failure', (self.root / 'failed-output/job.log').read_text())

    def test_source_tamper_never_executes(self):
        self.prepare("raise RuntimeError('must not execute')\n")
        self.store.put(self.inp + 'source.tar.gz', b'tampered')
        self.execute()
        self.assertIsNone(self.store.optional(self.out + 'manifest.json'))
        self.assertFalse((self.root / 'worker/started').exists())
        self.assertFalse((self.root / 'worker/workspace').exists())

    def test_fetch_rejects_tamper_and_does_not_publish_partial_directory(self):
        self.prepare("print('done')\n")
        self.execute()
        self.store.put(self.out + 'out/job.log', b'fake')
        target = self.root / 'fetched'
        with self.assertRaises(ValueError):
            self.laptop().fetch(self.run_id, target)
        self.assertFalse(target.exists())
        self.assertFalse(list(self.root.glob('.lb-fetch-*')))

    def test_unfinished_fetch_and_cross_run_manifest_rejected(self):
        self.prepare("print('done')\n")
        with self.assertRaises(ValueError):
            self.laptop().fetch(self.run_id, self.root / 'missing')
        self.execute()
        final = self.store.optional(self.out + 'manifest.json')
        final['files'][0]['key'] = 'runs/another-owner/out/job.log'
        self.store.put_json(self.out + 'manifest.json', final)
        with self.assertRaises(ValueError):
            self.laptop().fetch(self.run_id, self.root / 'cross-run')

    def test_fetch_rejects_names_that_collide_on_case_insensitive_laptops(self):
        self.prepare("print('done')\n")
        self.execute()
        final = self.store.optional(self.out + 'manifest.json')
        alias = dict(final['files'][0], name='JOB.LOG', key=self.out + 'out/JOB.LOG')
        self.store.put(alias['key'], self.store.get(final['files'][0]['key'])[0])
        final['files'].append(alias)
        self.store.put_json(self.out + 'manifest.json', final)
        with self.assertRaises(ValueError):
            self.laptop().fetch(self.run_id, self.root / 'case-alias')
        self.assertFalse((self.root / 'case-alias').exists())

    def test_bundle_excludes_credentials_and_rejects_symlinks_and_tokens(self):
        (self.source / '.env').write_text('PRIVATE=do-not-upload')
        (self.source / 'ok.txt').write_text('hello')
        data = bundle(self.source)
        unpack(data, self.root / 'expanded')
        self.assertFalse((self.root / 'expanded/.env').exists())
        (self.source / 'link').symlink_to(self.source / 'ok.txt')
        with self.assertRaises(ValueError):
            bundle(self.source)
        (self.source / 'link').unlink()
        (self.source / 'ok.txt').write_text('sk-ant-' + 'x' * 25)
        with self.assertRaises(ValueError):
            bundle(self.source)

    def test_archive_escape_links_and_duplicate_members_rejected(self):
        for name, member_type, repeat in [('../escape', tarfile.REGTYPE, False), ('link', tarfile.SYMTYPE, False), ('same', tarfile.REGTYPE, True)]:
            with self.subTest(name=name):
                stream = io.BytesIO()
                with tarfile.open(fileobj=stream, mode='w:gz') as archive:
                    info = tarfile.TarInfo(name)
                    info.type = member_type
                    archive.addfile(info, io.BytesIO())
                    if repeat:
                        archive.addfile(info, io.BytesIO())
                with self.assertRaises(ValueError):
                    unpack(stream.getvalue(), self.root / uuid.uuid4().hex)
        self.assertFalse((self.root / 'escape').exists())

    def test_manifest_aliases_negative_sizes_and_duplicate_names_rejected(self):
        self.prepare("print('done')\n")
        self.execute()
        original = self.store.optional(self.out + 'manifest.json')
        for name in ('../escape', '/absolute', 'a//b', 'a/./b', 'a\\b', 'C:/escape', 'a/.. /escape', 'NUL.txt', 'a/CON'):
            with self.assertRaises(ValueError):
                safe_name(name)
        bad = json.loads(json.dumps(original))
        bad['files'][0]['size'] = -1
        with self.assertRaises(ValueError):
            output_entries(bad, self.out)
        original['files'].append(original['files'][0])
        with self.assertRaises(ValueError):
            output_entries(original, self.out)


if __name__ == '__main__':
    unittest.main()
