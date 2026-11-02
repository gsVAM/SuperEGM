# Laptop ↔ AWS builder transport

This prototype uploads a selected source directory and task brief to S3, runs an
argv command in an AgentCore Instances session, accepts follow-up input, and fetches
checksummed output. The job runs independently of the laptop observer. It does not
deploy the application or open/merge PRs.

## Run from a laptop

Use Python 3.11+ with a current boto3 installation and an authenticated, restricted
AWS CLI profile. The Python bundled with Homebrew AWS CLI also works via its
bundled SDK. Copy `config.example.json` outside the repository and fill in your
builders account, bucket, runtime and capacity provider. The CLI checks the caller's
account before accessing the builder. This prototype accepts IAM user profiles;
Identity Center/assumed-role owner mapping is not implemented.

```sh
python3 tools/livebuilders/lb.py --config /path/to/builders.json run \
  --source tools/livebuilders/demo --brief tools/livebuilders/demo/task.md \
  --timeout 180 -- python3 -u job.py

python3 tools/livebuilders/lb.py --config /path/to/builders.json watch RUN_ID
python3 tools/livebuilders/lb.py --config /path/to/builders.json send RUN_ID \
  'Use the greeting: Hello from the laptop' --request-id A_UUID
python3 tools/livebuilders/lb.py --config /path/to/builders.json fetch RUN_ID \
  --destination /path/to/new-output-directory
python3 tools/livebuilders/lb.py --config /path/to/builders.json cleanup RUN_ID
```

`run` returns after starting the remote worker. It prints the run ID before its first S3 upload, so an ambiguous connection failure can be retried with `resume RUN_ID`.
`resume` reuses the immutable request and session ID. Preflight download/validation failures remain retryable; `resume` can launch a new
worker after the failed preflight exits. A process lock prevents concurrent preflight
workers, and a durable marker written after staging and before command launch
prevents executing the same command twice. After a worker crash, the marker prevents
automatic replay: inspect the run and start a new run explicitly if appropriate.

`watch` polls saved S3 events about once per second; it is near-live, not a terminal
or WebSocket. Ctrl-C detaches the observer. Another invocation resumes from the
saved cursor; `--replay` starts from event one. Printing and cursor persistence are
not a distributed transaction: a crash between them can repeat the last displayed
event. Use one observer per local cursor directory, or separate `--state-dir` values.

`send` updates the S3 mailbox with an ETag compare-and-swap. Retrying with the same
request ID and text does not enqueue the message again. The worker passes one JSON
line per message to the job's stdin: `{"request_id":"...","text":"..."}`.
`input_queued` confirms queueing, not that the job understood or acted on the message.
The job must emit its own acknowledgment. This is a command-process protocol;
adapting it to a continuing Claude conversation is separate work. No Claude token
is needed for the transport or its demo, and no model request is made.

`stop` sets a durable cancellation flag. The worker polls it and kills the job's
process group, saves partial output, and publishes a cancelled manifest. `cleanup`
deletes the AgentCore capacity-provider session and its persistent volume; it
requires a final manifest unless `--force` is explicitly supplied. It does not
delete S3 evidence. The bucket's configured lifecycle controls evidence retention.

## Objects and completion

The owner component is a hash of the authenticated IAM user ARN. It organizes data;
**it is not an IAM isolation boundary**. The single-user runtime requires `LB_OWNER`
to equal this hash and rejects other owner namespaces. This pin is not caller
authentication: only the dedicated user may have invoke permission. The current sandbox role can access more
than one run. Do not onboard coworkers until their session and object permissions
are enforced separately.

```text
inputs/livebuilders/<owner>/<run>/
  request.json                 immutable command, brief and source hash
  source.tar.gz                immutable selected source snapshot
  control.json                 ETag-protected follow-ups and cancellation
runs/livebuilders/<owner>/<run>/
  events/00000001.json ...      ordered durable progress
  out/job.log
  out/result.json
  out/artifacts/...             files written by the job
  manifest.json                published last, after successful output uploads
```

The worker gets `LB_INPUT_DIR`, `LB_BRIEF_PATH`, and `LB_OUTPUT_DIR`. The working
directory is the extracted snapshot. Put deliverables in `LB_OUTPUT_DIR`; the
working tree, dependencies and database are not automatically downloaded.

Inputs and output files are limited to 512 MiB total and 20,000 files. Final
manifest JSON is limited to 32 MiB on both publication and read. The mailbox
is limited to 128 messages/64 KiB, each message to 4 KiB. Source packaging excludes
credential directories, `.env*`, private-key files, dependencies and build outputs;
it skips excluded symlinks without following or archiving them, and rejects other
symlinks and recognizable credential patterns. This scan is best
effort, not proof that arbitrary files contain no secrets. Select inputs carefully.
Extraction rejects traversal, duplicate paths, symlinks and special files.

`fetch` binds the manifest to the run/request, verifies every size and SHA-256, and
publishes the destination only after all files pass. It never applies or executes a
patch. Hashes detect corruption; they do not make agent-produced content trusted.
If a worker or artifact upload fails before the manifest, status remains
`incomplete`. It does not falsely report success or assume the worker is alive.
Progress events omit command arguments. Logs truncate overlong lines at 64 KiB
and stop recording after 16 MiB while continuing to drain stdout.
The job deadline is at most 2,400 seconds; configure the AgentCore maximum lifetime
above that. AWS request delays can extend cancellation/deadline handling. Instance
lifetime still bounds the session. Jobs must not daemonize/escape their process
group; session deletion is the final cleanup boundary.

## Runtime and permissions

`runtime.py` provides AgentCore's `/ping` and `/invocations` endpoints. It reports
`HealthyBusy` while workers are active. Build `Dockerfile` using a pinned workspace
image that already has Python/boto3 and the job's tools. Set `LB_BUCKET`, `AWS_REGION`, and `LB_OWNER` (the first 24 hex characters of
SHA-256 of the dedicated IAM user ARN) in the runtime configuration. Bind the intended runtime version before
launching work; do not update an active runtime during a job.

The laptop needs S3 Get/Put under `inputs/livebuilders/*`, Get under
`runs/livebuilders/*`, bucket List (so missing objects return 404), STS identity,
AgentCore invoke, and delete-capacity-provider-session permissions. The real-AWS
acceptance test additionally writes its own output object to test corruption,
then restores it. The worker needs Get under `inputs/livebuilders/*` and Put under
`runs/livebuilders/*`. Production credentials, GitHub tokens, and model credentials
are not part of this protocol. Existing account-wide sandbox permissions are not
tightened by this change.

## Verify

Offline protocol tests use real temporary files and subprocesses, not live AWS:

```sh
python3 -W error::ResourceWarning -m unittest discover \
  -s tools/livebuilders -p 'test_*.py' -v
```

Opt-in acceptance uses real S3 and one real AgentCore session, incurs compute/S3
charges, and requests session deletion afterward:

```sh
python3 tools/livebuilders/acceptance_aws.py \
  --config /path/to/builders.json --evidence /path/to/new-evidence-directory
```

It checks duplicate launch, incomplete fetch rejection, progress before completion,
idempotent follow-up, observer exit/reconnect, checksummed retrieval, patch application,
and rejection of a deliberately corrupted S3 object. The observer test exits a
local process; it does not physically power off the laptop. No CI steps are added.
