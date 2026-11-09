# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_record_launch` as the record-launch module; it records a builder launch in `launches/<unit>.json` and, with --exit, the exit its exit file proves; the flagless form refused, launch-builder recording the launch (U24); `subagent_calls` read from the session's transcript at the exit (U27); the effective model and `total_cost_usd` read from the result file at the exit (U28); `--exit stalled`, the group check, the signal, `kill_failed` and `last_commit_at` (U31).

"""superegm record-launch: record a builder launch's exit as `exited <code>`, or a stalled launch's as `exited (stalled)`
after signalling its group (or `kill_failed`); `launch-builder` records it `running`."""

import json
import subprocess
import time
from pathlib import Path

import superegm as core
from superegm.launch import load_launches
from superegm.status import epoch, head_time, own_commit
from superegm.traces import subagent_calls

WRITES = frozenset(["launches"])  # the store kinds this subcommand writes
SKILLS = frozenset(["wave"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "record-launch", "record a builder launch's exit, the code its exit file holds (launch-builder records the launch)")
  p.add_argument("--unit", required=True)
  p.add_argument("--exit", help="the code the launched command's exit file holds, or `stalled` (U31); required")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  if args.exit is None:  # amendment 10: launch-builder records the launch it starts
    raise core.HandoffError("record-launch: --exit is required: launch-builder records the launch")
  word = str(args.exit).strip()
  if word != "stalled":
    try:
      word = str(int(word))
    except ValueError:
      raise core.HandoffError(f"record-launch: --exit {args.exit}: a code or stalled") from None
  args.exit = word
  try:
    return record(args)
  except core.HandoffError as error:
    raise core.HandoffError(f"record-launch: {error}") from None


def record(args):
  """The elephant runs this when the exit file of the launch `launch-builder` started and recorded exists, or, with
  `--exit stalled`, when a `status` pass reported the launch stalled (spec section 11.1, U31)."""
  st = core.store(core.git_toplevel(Path.cwd()))
  unit = args.unit
  launches = load_launches(st, unit)
  latest = launches[-1] if launches else {}
  if latest.get("status") != "running":
    raise core.HandoffError(f"{unit} has no running launch")
  exit_file = Path(latest["result_file"] + ".exit")
  last = own_commit_of(latest)
  if args.exit == "stalled":
    return record_stalled(st, unit, launches, latest, exit_file, last)
  if not exit_file.is_file():
    raise core.HandoffError(f"{unit} launch {latest['round']} has no exit file")
  held = core.read_text(exit_file).strip()
  if held != args.exit:
    raise core.HandoffError(f"the exit file of {unit} launch {latest['round']} says {held}, not {args.exit}")
  return finish(st, unit, launches, latest, f"exited {args.exit}", last, f"{unit} launch {latest['round']} exited {args.exit}")


def own_commit_of(entry):
  """The launch's own newest commit time (U31), read from its worktree `HEAD`; None when it has none."""
  try:
    return own_commit(entry, head_time(entry.get("worktree")))
  except (ValueError, TypeError):
    return None


def record_stalled(st, unit, launches, entry, exit_file, last):
  """U31: re-read the entry, never the predicate; a file already present is read with no group check and no signal,
  else the group the recorded `pid` names is signalled once when it is the launch's own (or leaderless) and its
  exit file `stalled` awaited 30 s, the one proof; `kill_failed` with the reason otherwise."""
  rnd = entry["round"]
  try:
    waited = int((core.NOW() - (last or epoch(entry["started_at"]))) // 60)
  except (KeyError, ValueError, TypeError):
    waited = 0
  line = f"{unit} launch {rnd} stalled ({waited} min; last commit {iso(last) or 'none'})"
  if not exit_file.is_file():
    if entry.get("kill_failed"):
      raise core.HandoffError(f"{unit} launch {rnd} kill_failed ({entry['kill_failed']})")
    owner = group_owner(entry["pid"], entry["result_file"]) if entry.get("pid") else "no process"
    if owner in ("own", "no leader"):
      core.kill_group(entry["pid"])
      start = core.NOW()
      while not exit_file.is_file() and core.NOW() - start < 30:
        core.SLEEP(1)
      owner = "no exit file"
    if not exit_file.is_file():
      entry["kill_failed"] = owner
      failed = f"{unit} launch {rnd} kill_failed ({owner})"
      core.atomic_write(st.path("launches", unit), {"launches": launches})
      core.journal(st, failed)
      print(failed)
      return 0
  held = core.read_text(exit_file).strip()
  if held != "stalled":
    raise core.HandoffError(f"the exit file of {unit} launch {rnd} says {held}, not stalled")
  return finish(st, unit, launches, entry, "exited (stalled)", last, line)


def finish(st, unit, launches, latest, status, last, line):
  """Record an exit: the status, the `kill_failed` mark cleared, `last_commit_at` (U31), the subagent calls and the usage."""
  latest["status"] = status
  latest.pop("kill_failed", None)
  latest["last_commit_at"] = iso(last)
  # U27: the platform's default subagents the session spawned, from its transcript under the builder profile;
  # a pre-U27 entry, without `session_id`, records the no-file value; the profile from the config the store
  # loaded (`load_config` expands it), so a plan or spec edited during the launch cannot stop the exit's record
  profile = Path(st.config["builder"]["profile_dir"])
  latest["subagent_calls"] = subagent_calls(profile, latest["session_id"]) if latest.get("session_id") else {"count": 0, "calls": []}
  latest["effective_model"], latest["total_cost_usd"] = result_usage(Path(latest["result_file"]))
  core.atomic_write(st.path("launches", unit), {"launches": launches})
  core.journal(st, line)
  print(line)
  return 0


def iso(seconds):
  """A `%Y-%m-%dT%H:%M:%SZ` stamp of these seconds, or None."""
  return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds)) if seconds is not None else None


def PS(args):
  """`ps` with these arguments, its stdout; empty when it fails."""
  try:
    return subprocess.run(["ps", *args], capture_output=True, text=True, check=False).stdout
  except OSError:
    return ""


def group_owner(pid: int, result_file: str) -> str:
  """U31: whose group the recorded `pid` names: `own` when its leader's args name the launch's result file,
  `pid reused` when the leader is another's, `no leader` when members of the group live without it (the
  wrapper died, its `claude -p` lives on), `no process` when none does."""
  leader = PS(["-ww", "-o", "args=", "-p", str(pid)]).strip()
  if leader:
    return "own" if result_file in leader else "pid reused"
  for row in PS(["-axo", "pid=,pgid="]).splitlines():
    parts = row.split()
    if len(parts) == 2 and parts[1] == str(pid):
      return "no leader"
  return "no process"


def result_usage(result_file: Path):
  """U28: the effective model and the cost from the launch's `--output-format json` result file: every key of
  `modelUsage`, joined `, `, else `requested only`; `total_cost_usd` as the file holds it, `unrecorded` for a file
  that does not parse (a killed launch's partial file), else `None` (no file, or no number in it)."""
  if not result_file.is_file():
    return "requested only", None
  try:
    data = json.loads(core.read_text(result_file))
  except ValueError:
    return "requested only", "unrecorded"
  if not isinstance(data, dict):
    return "requested only", None
  usage, cost = data.get("modelUsage"), data.get("total_cost_usd")
  effective = ", ".join(usage) if isinstance(usage, dict) and usage else "requested only"
  return effective, cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
