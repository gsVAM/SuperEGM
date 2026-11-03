# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_record_launch` as the record-launch module; it records a builder launch in `launches/<unit>.json` and, with --exit, the exit its exit file proves.

"""superegm record-launch: record a builder launch as `running`, later its exit as `exited <code>`."""

from pathlib import Path

import superegm as core
from superegm.launch import load_launches

WRITES = frozenset(["launches"])  # the store kinds this subcommand writes
SKILLS = frozenset(["wave"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "record-launch", "record a builder launch, or with --exit the exit its exit file holds")
  p.add_argument("--unit", required=True)
  p.add_argument("--exit", type=int, help="the code the launched command's exit file holds")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  try:
    return record(args)
  except core.HandoffError as error:
    raise core.HandoffError(f"record-launch: {error}") from None


def record(args):
  """The elephant runs this the moment it has started the command, and again when the exit
  file exists: between the two, the launch is `running` and nothing is inferred from silence."""
  st = core.store(core.git_toplevel(Path.cwd()))
  unit = args.unit
  launches = load_launches(st, unit)
  latest = launches[-1] if launches else {}
  if args.exit is None:
    if latest.get("status") == "running":
      raise core.HandoffError(f"{unit} launch {latest['round']} is already recorded (running)")
    n = len(launches) + 1
    prompt = st.path("launches", f"{unit}_r{n}_prompt.md")
    if not prompt.is_file():
      raise core.HandoffError(f"{unit} launch {n} has no prompt file: run launch-builder first")
    launches.append({"round": n, "worktree": str(st.path("worktrees", unit, f"r{n}")),
                     "branch": f"{core.BRANCH_PREFIX}/{st.handoff_id}/{unit}", "started_at": core.now_iso(),
                     "status": "running", "result_file": str(st.path("launches", f"{unit}_r{n}_result.json")),
                     "prompt_sha256": core.sha256_file(prompt)})
    line = f"{unit} launch {n} running"
  else:
    if latest.get("status") != "running":
      raise core.HandoffError(f"{unit} has no running launch")
    exit_file = Path(latest["result_file"] + ".exit")
    if not exit_file.is_file():
      raise core.HandoffError(f"{unit} launch {latest['round']} has no exit file")
    held = core.read_text(exit_file).strip()
    if held != str(args.exit):
      raise core.HandoffError(f"the exit file of {unit} launch {latest['round']} says {held}, not {args.exit}")
    latest["status"] = f"exited {args.exit}"
    line = f"{unit} launch {latest['round']} exited {args.exit}"
  core.atomic_write(st.path("launches", unit), {"launches": launches})
  core.journal(st, line)
  print(line)
  return 0
