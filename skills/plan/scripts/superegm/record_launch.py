# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_record_launch` as the record-launch module; it records a builder launch in `launches/<unit>.json` and, with --exit, the exit its exit file proves; the flagless form refused, launch-builder recording the launch (U24).

"""superegm record-launch: record a builder launch's exit as `exited <code>`; `launch-builder` records it `running`."""

from pathlib import Path

import superegm as core
from superegm.launch import load_launches

WRITES = frozenset(["launches"])  # the store kinds this subcommand writes
SKILLS = frozenset(["wave"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "record-launch", "record a builder launch's exit, the code its exit file holds (launch-builder records the launch)")
  p.add_argument("--unit", required=True)
  p.add_argument("--exit", type=int, help="the code the launched command's exit file holds; required")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  if args.exit is None:  # amendment 10: launch-builder records the launch it starts
    raise core.HandoffError("record-launch: --exit is required: launch-builder records the launch")
  try:
    return record(args)
  except core.HandoffError as error:
    raise core.HandoffError(f"record-launch: {error}") from None


def record(args):
  """The elephant runs this when the exit file of the launch `launch-builder` started and recorded exists."""
  st = core.store(core.git_toplevel(Path.cwd()))
  unit = args.unit
  launches = load_launches(st, unit)
  latest = launches[-1] if launches else {}
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
