# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_gate` as the gate module.

"""superegm gate: record the reviewed pair, pass or accept the gate, record readiness."""

import difflib

import superegm as core

WRITES = frozenset(['bodies', 'file', 'plan', 'state', 'unit', 'units'])  # the store kinds this subcommand writes
SKILLS = frozenset(['file'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "gate", "record the reviewed pair, pass or accept the gate, record readiness")
  p.add_argument("--reviewed", action="store_true")
  p.add_argument("--round", type=int, default=0)
  p.add_argument("--pass", dest="pass_gate", action="store_true")
  p.add_argument("--accept", action="store_true")
  p.add_argument("--readiness")
  p.add_argument("--what-ran", action="append")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  handoff.write_graph_files()
  state = handoff.state
  plan_sha, bodies_sha = core.gate_hashes(handoff)
  gate = state.setdefault("gate", {})
  if args.what_ran:
    gate["what_ran"] = list(args.what_ran)
  if args.readiness:
    state["readiness"] = {"summary": args.readiness, "recorded_at": core.now_iso()}
    core.save_state(handoff.artifact_dir, state)
    print("readiness recorded")
    return 0
  if args.reviewed:
    core.atomic_write(handoff.artifact_dir / "gate_reviewed_plan.md", core.read_text(handoff.plan_path))
    core.atomic_write(handoff.artifact_dir / "gate_reviewed_bodies.md", handoff.bodies_text())
    gate["reviewed"] = {"round": args.round, "plan_sha256": plan_sha, "bodies_sha256": bodies_sha}
    core.save_state(handoff.artifact_dir, state)
    print(f"round {args.round}: reviewed pair recorded ({plan_sha[:12]}, {bodies_sha[:12]})")
    return 0
  reviewed = gate.get("reviewed")
  if not reviewed:
    raise core.HandoffError("no reviewed pair: run `gate --reviewed --round <n>` before the round's reviewers")
  changed = (reviewed["plan_sha256"], reviewed["bodies_sha256"]) != (plan_sha, bodies_sha)
  if args.pass_gate:
    if changed:
      raise core.HandoffError(f"the plan or the bodies changed after round {reviewed['round']} was "
                         "reviewed: run one more Stage 10 round (or decline the remaining fixes)")
    state["gate_plan_sha256"], state["gate_bodies_sha256"] = plan_sha, bodies_sha
    gate.update({"passed": "converged", "round": reviewed["round"], "passed_at": core.now_iso()})
    state.pop("gate_unreviewed_diff", None)
    core.save_state(handoff.artifact_dir, state)
    print(f"gate passed at round {reviewed['round']}: gate_plan_sha256 {plan_sha[:12]}, "
          f"gate_bodies_sha256 {bodies_sha[:12]}")
    return 0
  if args.accept:
    state["gate_plan_sha256"], state["gate_bodies_sha256"] = plan_sha, bodies_sha
    gate.update({"passed": "accepted at cap", "round": reviewed["round"], "passed_at": core.now_iso()})
    if changed:
      diff = []
      for name, current in (("handoff_plan.md", core.read_text(handoff.plan_path)),
                            ("handoff_bodies.md", handoff.bodies_text())):
        old = core.read_text(handoff.artifact_dir / f"gate_reviewed_{name.split('_')[1]}")
        diff += difflib.unified_diff(old.splitlines(True), current.splitlines(True),
                                     f"reviewed/{name}", f"current/{name}")
      core.atomic_write(handoff.artifact_dir / "gate_unreviewed.diff", "".join(diff))
      state["gate_unreviewed_diff"] = "gate_unreviewed.diff"
    core.save_state(handoff.artifact_dir, state)
    print("gate accepted at the cap" + (": unreviewed changes in gate_unreviewed.diff" if changed else ""))
    return 0
  raise core.HandoffError("gate needs one of --reviewed, --pass, --accept or --readiness")
