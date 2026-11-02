"""Real remote transport acceptance job; no model, database, or external API."""
import difflib
import json
import os
import sys
import time
from pathlib import Path

output = Path(os.environ['LB_OUTPUT_DIR'])
source = Path('greeting.txt')
before = source.read_text()
print('READY: waiting for a follow-up message', flush=True)
message = json.loads(sys.stdin.readline())
assert message['text'] == 'Use the greeting: Hello from the laptop'
after = 'Hello from the laptop\n'
source.write_text(after)
print('FOLLOW_UP_APPLIED: ' + message['request_id'], flush=True)
for step in range(4):
    print(f'WORKING: step {step + 1}/4', flush=True)
    time.sleep(5)
assert source.read_text() == after
patch = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/greeting.txt', tofile='b/greeting.txt'))
(output / 'patch.diff').write_text(patch)
(output / 'proof.json').write_text(json.dumps({'passed': True, 'request_id': message['request_id'], 'before': before, 'after': after}))
print('PASS: patch and proof created', flush=True)
