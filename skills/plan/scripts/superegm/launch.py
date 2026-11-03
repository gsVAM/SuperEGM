# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_launch` as the launch module.

"""superegm launch: record the units launched in a wave."""

import superegm as core

WRITES = frozenset(['state'])  # the store kinds this subcommand writes
SKILLS = frozenset(['wave'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "launch", "record the units launched in a wave")
  p.add_argument("--wave", type=int, required=True)
  p.add_argument("--units", nargs="+", required=True)
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  core.require_frozen_units(handoff)
  state = handoff.state
  core.require_receipt(state)
  core.require_repo(handoff)
  for uid in args.units:
    if uid not in handoff.plan.units:
      raise core.HandoffError(f"unknown unit {uid}")
  # Readiness is the rule a wave exists to respect; checking only that the id
  # parses lets a stale wave list launch a blocked unit.
  summary, open_blocking = core.status_pass(handoff)
  problems = []
  for uid in args.units:
    if uid in summary["landed"]:
      problems.append(f"{uid} has already landed")
    elif (state.get("units", {}).get(uid) or {}).get("launched"):
      problems.append(f"{uid} is already launched")
    elif uid in open_blocking:
      ids = ", ".join(d["id"] for d in open_blocking[uid])
      problems.append(f"{uid} has an unanswered or unpublished blocking decision ({ids})")
    elif uid not in summary["ready"]:
      waiting = sorted(handoff.graph.preds[uid] - set(summary["landed"]))
      problems.append(f"{uid} is not ready: waiting on {', '.join(waiting) or 'its predecessors'}")
  if problems:
    raise core.HandoffError("nothing was launched:\n  " + "\n  ".join(problems))
  for uid in args.units:
    state.setdefault("units", {}).setdefault(uid, {})["launched"] = {"wave": args.wave, "at": core.now_iso()}
  core.save_state(handoff.artifact_dir, state)
  print(f"launched in wave {args.wave}: {', '.join(args.units)}")
  return 0
