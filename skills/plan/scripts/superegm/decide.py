# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_decide` as the decide module.

"""superegm decide: record the user's answer to a decide-before-build item."""

import superegm as core

WRITES = frozenset(['file', 'state', 'unit'])  # the store kinds this subcommand writes
SKILLS = frozenset(['plan'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "decide", "record the user's answer to a decide-before-build item")
  p.add_argument("--unit", required=True)
  p.add_argument("--decision", required=True)
  p.add_argument("--answer", required=True)
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  unit = handoff.plan.units.get(args.unit)
  if not unit:
    raise core.HandoffError(f"unknown unit {args.unit}")
  decision = next((d for d in unit.decisions if d["id"] == args.decision), None)
  if not decision:
    raise core.HandoffError(f"{args.unit} has no decision {args.decision}")
  key = f"{args.unit}/{args.decision}"
  fingerprint = core.sha256_text(core.canonical([decision["question"], decision["owner"],
                                       decision["default"], decision["blocking"]]))[:16]
  handoff.state.setdefault("decisions", {})[key] = {"answer": args.answer,
                                                    "decided_at": core.now_iso(),
                                                    "fingerprint": fingerprint}
  core.save_state(handoff.artifact_dir, handoff.state)
  core.atomic_write(handoff.unit_file(args.unit), handoff.unit_file_text(args.unit))
  comment = handoff.artifact_dir / f"decision_comment_{args.unit}_{args.decision}.md"
  core.atomic_write(comment, f"**Decision {args.decision}** ({decision['question']}): {args.answer}\n")
  print(f"recorded {key}; re-rendered {handoff.unit_file(args.unit).name}; comment in {comment.name}")
  return 0
