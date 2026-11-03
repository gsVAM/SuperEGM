# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the answer is one of the item's options, written into the plan line of an unfiled unit; a filed unit gets the comment file only.

"""superegm decide: answer a decide-before-build item in place."""

import re
from pathlib import Path

import superegm as core
from superegm import graph

WRITES = frozenset(['bodies', 'file', 'plan', 'state', 'unit', 'units'])  # the store kinds this subcommand writes
SKILLS = frozenset(['plan', 'wave'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "decide", "answer a decide-before-build item in place")
  p.add_argument("--unit", required=True)
  p.add_argument("--decision", required=True)
  which = p.add_mutually_exclusive_group(required=True)
  which.add_argument("--answer", help='the option id, as "(b)"')
  which.add_argument("--default", action="store_true", help="the item's default option")
  p.add_argument("--judges", help="the judges panel id whose verdict this answer is")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  st = core.store(core.git_toplevel(Path.cwd()))
  handoff = graph.load(st, args.plan)
  core.require_runcard(args, SKILLS)
  uid, did = args.unit, args.decision
  unit = handoff.plan.units.get(uid)
  if not unit:
    raise core.HandoffError(f"decide: unknown unit {uid}")
  decision = next((d for d in unit.decisions if d["id"] == did), None)
  if not decision:
    raise core.HandoffError(f"decide: {uid} has no decision {did}")
  answer = decision["default"] if args.default else args.answer
  by = f"judges:{args.judges}" if args.judges else "owner"
  lines = core.read_text(handoff.plan_path).split("\n")
  index = decision["line"] - 1
  lines[index] = re.sub(r"; answer: \(\w\)$", "", lines[index]) + f"; answer: {answer}"
  core.atomic_write(handoff.plan_path, "\n".join(lines))
  handoff = graph.load(st, handoff.plan_path)
  handoff.state.setdefault("decisions", {})[f"{uid}/{did}"] = {"answer": answer, "by": by, "decided_at": core.now_iso()}
  handoff.write_graph_files()
  core.journal(st, f"decide {uid}/{did} {answer} by {by}")
  print(f"recorded {uid}/{did} {answer}; re-rendered unit_{uid}.md")
  return 0
