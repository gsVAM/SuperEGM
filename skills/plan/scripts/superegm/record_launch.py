# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_record_launch` as the record-launch module; it records a builder launch in `launches/<unit>.json` and, with --exit, the exit its exit file proves; the flagless form refused, launch-builder recording the launch (U24); `subagent_calls` read from the session's transcript at the exit (U27); the effective model and `total_cost_usd` read from the result file at the exit (U28).

"""superegm record-launch: record a builder launch's exit as `exited <code>`; `launch-builder` records it `running`."""

import json
from pathlib import Path

import superegm as core
from superegm.launch import load_launches
from superegm.traces import subagent_calls

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
  # U27: the platform's default subagents the session spawned, from its transcript under the builder profile;
  # a pre-U27 entry, without `session_id`, records the no-file value; the profile from the config the store
  # loaded (`load_config` expands it), so a plan or spec edited during the launch cannot stop the exit's record
  profile = Path(st.config["builder"]["profile_dir"])
  latest["subagent_calls"] = subagent_calls(profile, latest["session_id"]) if latest.get("session_id") else {"count": 0, "calls": []}
  latest["effective_model"], latest["total_cost_usd"] = result_usage(Path(latest["result_file"]))
  line = f"{unit} launch {latest['round']} exited {args.exit}"
  core.atomic_write(st.path("launches", unit), {"launches": launches})
  core.journal(st, line)
  print(line)
  return 0


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
