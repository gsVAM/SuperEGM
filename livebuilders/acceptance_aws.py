"""Opt-in acceptance against real S3 and AgentCore; creates and deletes one session."""
import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

from lb import Laptop
from protocol import prefixes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    directory = Path(__file__).resolve().parent
    state = args.evidence / 'state'
    laptop = Laptop(json.loads(args.config.read_text()), state)
    run_id = None
    checks = []

    def passed(name):
        checks.append(name)
        print('PASS: ' + name, flush=True)

    def observer(*extra):
        return subprocess.run([sys.executable, str(directory / 'lb.py'), '--config', str(args.config), '--state-dir', str(state), 'watch', run_id, *extra], capture_output=True, text=True, timeout=90, check=True).stdout

    try:
        launched = laptop.run(directory / 'demo', directory / 'demo/task.md', ['python3', '-u', 'job.py'], 180)
        run_id = launched['run_id']
        (args.evidence / 'run.json').write_text(json.dumps({'run_id': run_id, 'owner': laptop.owner}, indent=2))
        passed('source and brief uploaded; remote worker accepted')
        duplicate = laptop.resume(run_id)
        assert duplicate['duplicate']
        passed('duplicate launch reuses the same job')
        inp, out = prefixes(laptop.owner, run_id)
        deadline = time.monotonic() + 45
        while True:
            event = laptop.store.optional(out + 'events/00000002.json')
            if event and 'READY' in event.get('text', ''):
                break
            assert time.monotonic() < deadline, 'Remote job did not become ready'
            time.sleep(1)
        try:
            laptop.fetch(run_id, args.evidence / 'premature')
            raise AssertionError('Incomplete run was fetched')
        except ValueError:
            passed('fetch refuses an incomplete run')
        first = observer('--once')
        (args.evidence / 'observer-first.jsonl').write_text(first)
        assert 'READY' in first
        passed('separate laptop observer sees output before completion and exits')
        request_id = str(uuid.uuid4())
        text = 'Use the greeting: Hello from the laptop'
        laptop.control(run_id, text, request_id)
        assert laptop.control(run_id, text, request_id)['duplicate']
        mailbox, _ = laptop.store.json(inp + 'control.json')
        assert len(mailbox['messages']) == 1
        passed('follow-up input persisted once despite a repeated request')
        # No observer process is alive during this interval. This simulates a
        # disconnected observer, not a physical laptop/network power-off.
        time.sleep(25)
        second = observer()
        (args.evidence / 'observer-reconnected.jsonl').write_text(second)
        assert 'FOLLOW_UP_APPLIED' in second and '"status": "passed"' in second
        assert 'READY: waiting' not in second
        passed('fresh observer reconnects at its saved cursor and recovers completion')
        fetched = laptop.fetch(run_id, args.evidence / 'fetched')
        assert fetched['status'] == 'passed' and fetched['verified_files'] == 4
        proof = json.loads((args.evidence / 'fetched/artifacts/proof.json').read_text())
        assert proof['passed'] and proof['request_id'] == request_id
        passed('all output files match the manifest checksums')
        checkout = args.evidence / 'patch-check'
        checkout.mkdir()
        (checkout / 'greeting.txt').write_bytes((directory / 'demo/greeting.txt').read_bytes())
        subprocess.run(['git', 'apply', '--check', str(args.evidence.resolve() / 'fetched/artifacts/patch.diff')], cwd=checkout, check=True)
        subprocess.run(['git', 'apply', str(args.evidence.resolve() / 'fetched/artifacts/patch.diff')], cwd=checkout, check=True)
        assert (checkout / 'greeting.txt').read_text() == 'Hello from the laptop\n'
        passed('downloaded patch applies cleanly and produces the expected file')
        original, _ = laptop.store.get(out + 'out/job.log')
        try:
            laptop.store.put(out + 'out/job.log', b'intentionally-corrupted-test-output')
            try:
                laptop.fetch(run_id, args.evidence / 'corrupted-fetch')
                raise AssertionError('Corrupted artifact was accepted')
            except ValueError:
                assert not (args.evidence / 'corrupted-fetch').exists()
                passed('real S3 corruption is rejected without publishing partial output')
        finally:
            laptop.store.put(out + 'out/job.log', original)
    finally:
        run_id = run_id or getattr(laptop, 'last_run_id', None)
        try:
            cleanup = laptop.cleanup(run_id, force=True) if run_id else None
        except Exception as error:
            cleanup = {'error_type': type(error).__name__, 'run_id': run_id}
        evidence = {'run_id': run_id, 'checks': checks, 'passed': len(checks) == 9 and cleanup is not None and 'error_type' not in cleanup, 'cleanup': cleanup}
        (args.evidence / 'acceptance.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps(evidence), flush=True)
    assert evidence['passed'], 'Acceptance or cleanup failed; inspect acceptance.json'


if __name__ == '__main__':
    main()
