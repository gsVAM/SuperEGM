# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the interrupt subcommand (spec section 11).

"""superegm interrupt: the owner's typed interrupt of a launch (`interrupted`) or of a prepared
round (`collected`, `not run (interrupted: owner)`); an owner's decision, never a guess."""

from pathlib import Path

import superegm as core
from superegm.launch import load_launches, terminal

WRITES = frozenset(["launches", "foreman"])  # the store kinds this subcommand writes
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SKILLS = frozenset(["interrupt"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "interrupt", "record the owner's interrupt of a launch or a prepared round")
  p.add_argument("--unit", required=True)
  which = p.add_mutually_exclusive_group(required=True)
  which.add_argument("--launch", type=int, help="the launch count")
  which.add_argument("--round", type=int, help="the review round")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  try:
    return interrupt(args)
  except core.HandoffError as error:
    raise core.HandoffError(f"interrupt: {error}") from None


def interrupt(args):
  st = core.store(core.git_toplevel(Path.cwd()))
  unit = args.unit
  if args.launch is not None:
    launches = load_launches(st, unit)
    if not 1 <= args.launch <= len(launches):
      raise core.HandoffError(f"{unit} has no launch {args.launch}")
    entry = launches[args.launch - 1]
    if terminal(entry):
      raise core.HandoffError(f"{unit} launch {args.launch} is already terminal ({entry['status']})")
    entry["status"] = "interrupted"
    core.atomic_write(st.path("launches", unit), {"launches": launches})
    line = f"{unit} launch {args.launch} interrupted"
  else:
    data = core.load_foreman(st, unit)
    entry = next((r for r in data["rounds"] if r.get("round") == args.round), None)
    if entry is None:
      raise core.HandoffError(f"{unit} has no round {args.round}")
    if entry.get("phase") not in ("fetched", "prepared"):
      raise core.HandoffError(f"{unit} round {args.round} is not a prepared round ({entry.get('phase')})")
    entry.update({"phase": "collected", "outcome": "not run (interrupted: owner)"})
    core.save_foreman(st, unit, data)
    line = f"{unit} round {args.round} interrupted: owner"
  core.journal(st, line)
  print(line)
  return 0
