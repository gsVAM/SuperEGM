# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_decide` as the decide module.

"""superegm decide: record the user's answer to a decide-before-build item."""

import superegm as core

WRITES = frozenset(['file', 'state', 'unit'])  # the store kinds this subcommand writes
SKILLS = frozenset(['plan'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "decide", "record the user's answer to a decide-before-build item")
  p.add_argument("--published", help="mark the recorded answer as posted, with the comment url")
  p.add_argument("--unit", required=True)
  p.add_argument("--decision", required=True)
  p.add_argument("--answer")
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
  if args.published:
    record = handoff.state.setdefault("decisions", {}).get(key)
    if not record:
      raise core.HandoffError(f"{key} has no recorded answer to mark published")
    if record.get("fingerprint") not in (None, fingerprint):
      raise core.HandoffError(
          f"{key} was answered for a different question than the plan now asks: "
          f"the answer was invalidated. Ask the user again with `decide --answer`.")
    record["published"] = {"comment": args.published, "at": core.now_iso()}
    core.save_state(handoff.artifact_dir, handoff.state)
    print(f"{key} published as {args.published}")
    return 0
  if args.answer is None:
    raise core.HandoffError("decide needs --answer, or --published <comment url>")
  handoff.state.setdefault("decisions", {})[key] = {"answer": args.answer,
                                                    "decided_at": core.now_iso(),
                                                    "fingerprint": fingerprint,
                                                    "published": None}
  core.save_state(handoff.artifact_dir, handoff.state)
  core.atomic_write(handoff.unit_file(args.unit), handoff.unit_file_text(args.unit))
  comment = handoff.artifact_dir / f"decision_comment_{args.unit}_{args.decision}.md"
  core.atomic_write(comment, f"**Decision {args.decision}** ({decision['question']}): {args.answer}\n")
  print(f"recorded {key}; re-rendered {handoff.unit_file(args.unit).name}; comment in {comment.name}")
  print(f"NOT YET PUBLISHED: post {comment.name} on the issue, then run "
        f"`decide --state '{core.state_path(handoff.artifact_dir)}' --unit {args.unit} "
        f"--decision {args.decision} --published <comment url>`. "
        f"{args.unit} stays blocked until then.")
  return 0
