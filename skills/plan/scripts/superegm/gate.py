# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: `gate --pass` on converged plan reviews at the body hash over the store's plan copy; the unfiled write list; the reviewed pair, accept and readiness forms removed.

"""superegm gate: pass the gate when every unfiled unit's plan review converged at its body hash."""

import json
from pathlib import Path

import superegm as core
from superegm import graph

WRITES = frozenset(["state"])  # the store kinds this subcommand writes
SKILLS = frozenset(["file"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "gate", "pass the gate: every unfiled unit's plan review converged at its body hash")
  p.add_argument("--pass", dest="pass_gate", action="store_true", required=True)
  p.add_argument("--spec", dest="design", required=True, help="the approved spec the filing is for")
  p.set_defaults(run=run, writes=WRITES)


def open_handoff(spec: Path) -> graph.Handoff:
  """The handoff over the store's plan copy (U05's `handoff_plan.md`): the filing never reads the outside plan."""
  st = core.store(core.git_toplevel(Path(spec).expanduser().resolve()))
  return graph.load(st, st.path("plan"))


def converged_review(artifact_dir: Path, uid: str):
  """(converged, the converged round's artifact_sha256) of the unit's latest plan review, found by
  kind and artifact, never by id; U04 writes `converged` as `yes | no | by ruling R<n>`."""
  latest = None
  for path in (Path(artifact_dir) / "reviews").glob("*/review.json"):
    review = json.loads(core.read_text(path))
    if review.get("kind") == "plan" and review.get("artifact") == uid \
        and (latest is None or review["cycle"] > latest[0]["cycle"]):
      latest = (review, path.parent)
  if latest is None or latest[0].get("converged", "no") == "no" or not latest[0].get("converged_round"):
    return False, None
  rnd = json.loads(core.read_text(latest[1] / f"round-{latest[0]['converged_round']}.json"))
  return True, rnd["artifact_sha256"]


def require_gate(handoff) -> None:
  state = handoff.state
  if not state.get("gate_plan_sha256") or not state.get("gate_bodies_sha256"):
    raise core.HandoffError("the gate has not passed: run gate --pass first")
  if core.gate_hashes(handoff) != (state["gate_plan_sha256"], state["gate_bodies_sha256"]):
    raise core.HandoffError("the plan or the bodies changed after the gate: run gate --pass again")


def body_hashes(handoff) -> dict:
  """`handoff_units.json` units[<id>].body_sha256, what the plan review converged on."""
  return {uid: unit["body_sha256"]
          for uid, unit in json.loads(core.read_text(handoff.store.path("units")))["units"].items()}


def pending_writes(handoff, units=None) -> list:
  """EGM's canonical write list with every issue and link of a filed unit removed: filed is a
  number in `state.units` when `units` is None, else not in `units` (a resumed `apply` keeps the
  dry run's set). `repo`, `gate`, every label and the tracking issue always stay."""
  import superegm.apply as apply  # at call time: apply imports this module
  state = handoff.state
  pending = [uid for uid in handoff.graph.order
             if (uid in units if units is not None else handoff.filed(uid) is None)]
  items = [["repo", handoff.config["repo"]],
           ["gate", state.get("gate_plan_sha256"), state.get("gate_bodies_sha256")]]
  items += [["label", name] for name in apply.derived_labels(handoff)]
  items.append(["issue", "tracking", handoff.tracking_title(), apply.tracking_labels(handoff), handoff.render_tracking()])
  items += [["issue", uid, handoff.unit_title(uid), apply.unit_labels(handoff, uid), handoff.render_unit(uid)]
            for uid in pending]
  items += [["sub_issue", uid] for uid in pending]
  items += [["blocked_by", uid, b] for uid in pending for b in sorted(handoff.plan.units[uid].blockers)]
  return items


def run(args):
  core.require_runcard(args, SKILLS)
  handoff = open_handoff(Path(args.design))
  state = handoff.state
  unfiled = [uid for uid in handoff.graph.order if handoff.filed(uid) is None]
  if not unfiled:
    raise core.HandoffError("gate: nothing to file (every unit is filed)")
  hashes = body_hashes(handoff)
  for uid in unfiled:
    converged, sha = converged_review(handoff.artifact_dir, uid)
    if not converged:
      raise core.HandoffError(f"gate: {uid} plan review not converged")
    if sha != hashes[uid]:
      raise core.HandoffError(f"gate: {uid} body differs from its converged round")
  plan_sha, bodies_sha = core.gate_hashes(handoff)
  state["gate_plan_sha256"], state["gate_bodies_sha256"] = plan_sha, bodies_sha
  state["gate"] = {"passed": "converged", "passed_at": core.now_iso(), "units": unfiled}
  core.save_state(handoff.artifact_dir, state)
  print(f"gate passed: {len(unfiled)} unfiled units converged; gate_plan_sha256 {plan_sha[:12]}, "
        f"gate_bodies_sha256 {bodies_sha[:12]}")
  return 0
