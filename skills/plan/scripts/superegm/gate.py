# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: `gate --pass` on converged plan reviews at the body hash over the store's plan copy; the unfiled write list; the reviewed pair, accept and readiness forms removed; an adopted unit's two trailing fields (U13); a review with a round after the converged one is not converged (U56); a review the owner's proceed converged, at the ruling's sha256 (U57); a `replan: R<n>` unit refused, an unfiled body hashed as it renders now (U90).

"""superegm gate: pass the gate when every unfiled unit's plan review converged at its body hash."""

import json
from pathlib import Path

import superegm as core
from superegm import graph, respec, review

WRITES = frozenset(["state"])  # the store kinds this subcommand writes
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
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


def require_latest(handoff, name: str) -> None:
  """An older handoff is frozen (spec section 7): the filing's `name` refuses before anything else."""
  try:
    core.require_latest_handoff(handoff.store)
  except core.HandoffError as error:
    raise core.HandoffError(f"{name}: {error}") from None


def handoff_marks(store: core.Store, root: Path | None = None) -> dict:
  """U85's `respec.marks` of the store's handoff, read once per call by `run`, `require_gate` (so `dry-run` and a
  resumed `apply`) and `next` (U90); none, and no git run, while the handoff has no applied respec (its entries are
  read by the spec's file name alone). The recorded spec is rebased onto `root` inside `respec.marks`, so a spec
  approved in a worktree since removed is read under the repository root before git runs."""
  hid = store.handoff_id
  if not hid:
    return {}
  if not any(e.get("kind") == "respec" for e in respec.entries_of(store, hid, respec.spec_of(store, hid))):
    return {}
  return respec.marks(store, hid, root)


def require_replanned(uid: str, marks: dict) -> None:
  """A unit carrying `replan: R<n>` (U90) has no reviewed body: refused `gate: <U> needs a re-plan after respec R<n>`."""
  mark = marks.get(uid) or ""
  if mark.startswith("replan: "):
    raise core.HandoffError(f"gate: {uid} needs a re-plan after respec {mark.removeprefix('replan: ')}")


def converged_review(store: core.Store, uid: str, marks: dict | None = None):
  """(converged, the converged round's artifact_sha256) of the unit's latest plan review in the handoff's
  `reviews/`, found by kind and artifact, never by id; U04 writes `converged` as `yes | no | by ruling R<n>`, U57 `by proceed R<n>` (the ruling's
  `sha256`, ahead of the converged-round test). A `replan: R<n>` unit (U90) is refused by `require_replanned`
  over `marks`, the caller's one read of `respec.marks`: `run` passes its own; `apply` passes none, its
  `require_gate` having refused the unit already; `phase.plan_review_due` passes none, `planning_line` having
  returned `plan` for any unfiled unit carrying a `replan:` mark before it asks (no `require_gate` guards it)."""
  if marks is not None:
    require_replanned(uid, marks)
  latest = None
  for path in store.path("reviews").glob("*/review.json"):
    record = json.loads(core.read_text(path))
    if record.get("kind") == "plan" and record.get("artifact") == uid \
        and (latest is None or record["cycle"] > latest[0]["cycle"]):
      latest = (record, path.parent)
  if latest is not None and str(latest[0].get("converged") or "").startswith("by proceed "):  # the owner's (U57)
    return True, next(r["sha256"] for r in reversed(latest[0]["rulings"]) if r["ruling"] == "proceed")
  if latest is None or latest[0].get("converged", "no") == "no" or not latest[0].get("converged_round"):
    return False, None
  converged_round = int(latest[0]["converged_round"])
  if max(review.round_numbers(store, latest[1].name), default=0) > converged_round:
    return False, None  # a round recorded after the converged one: the review is due again (`review_plan.due_rows`)
  rnd = json.loads(core.read_text(latest[1] / f"round-{converged_round}.json"))
  return True, rnd["artifact_sha256"]


def require_gate(handoff) -> None:
  """The gate passed on the current plan and bodies. An unfiled `replan: R<n>` unit is refused first (U90): a
  respec changes every body's spec hash, so the hash test alone would hide the re-plan from a resumed `apply`."""
  marks = handoff_marks(handoff.store, handoff.repo_root)
  for uid in handoff.graph.order:
    if handoff.filed(uid) is None:
      require_replanned(uid, marks)
  state = handoff.state
  if not state.get("gate_plan_sha256") or not state.get("gate_bodies_sha256"):
    raise core.HandoffError("the gate has not passed: run gate --pass first")
  if core.gate_hashes(handoff) != (state["gate_plan_sha256"], state["gate_bodies_sha256"]):
    raise core.HandoffError("the plan or the bodies changed after the gate: run gate --pass again")


def body_hashes(handoff) -> dict:
  """Each unit's body as it renders now, the bytes the filing posts, which its plan review must have converged on:
  a respec that moves an unfiled unit's Design range or the spec's hash invalidates the review (U90), where the
  stored `handoff_units.json` hash would keep the body rendered before it. A filed unit keeps its stored hash."""
  stored = json.loads(core.read_text(handoff.store.path("units")))["units"]
  return {uid: core.sha256_text(handoff.render_unit(uid)) if handoff.filed(uid) is None else unit["body_sha256"]
          for uid, unit in stored.items()}


def pending_writes(handoff, units=None, adopted=None) -> list:
  """EGM's canonical write list with every issue and link of a filed unit removed: filed is a
  number in `state.units` when `units` is None, else not in `units` (a resumed `apply` keeps the
  dry run's set). `repo`, `gate`, every label and the tracking issue always stay. An adopted
  unit (`adopted[uid] = (number, old body sha256)`) keeps the five fixed `issue` fields and
  carries those two after them (spec section 10)."""
  import superegm.apply as apply  # at call time: apply imports this module
  state = handoff.state
  pending = [uid for uid in handoff.graph.order
             if (uid in units if units is not None else handoff.filed(uid) is None)]
  items = [["repo", handoff.config["repo"]],
           ["gate", state.get("gate_plan_sha256"), state.get("gate_bodies_sha256")]]
  items += [["label", name] for name in apply.derived_labels(handoff)]
  items.append(["issue", "tracking", handoff.tracking_title(), apply.tracking_labels(handoff), handoff.render_tracking()])
  items += [["issue", uid, handoff.unit_title(uid), apply.unit_labels(handoff, uid), handoff.render_unit(uid),
             *(adopted or {}).get(uid, ())]
            for uid in pending]
  items += [["sub_issue", uid] for uid in pending]
  items += [["blocked_by", uid, b] for uid in pending for b in sorted(handoff.plan.units[uid].blockers)]
  return items


def run(args):
  core.require_runcard(args, SKILLS)
  handoff = open_handoff(Path(args.design))
  require_latest(handoff, "gate")
  state = handoff.state
  unfiled =[uid for uid in handoff.graph.order if handoff.filed(uid) is None]
  if not unfiled:
    raise core.HandoffError("gate: nothing to file (every unit is filed)")
  hashes = body_hashes(handoff)
  marks = handoff_marks(handoff.store, handoff.repo_root)
  for uid in unfiled:
    converged, sha = converged_review(handoff.store, uid, marks)
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
