# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the file skill under the chain, a started filing resumed, a converged review with a later round refused (U56).

"""U56: `gate.converged_review` refuses a review with a round after the converged one; the file skill resumes a
started filing through `apply --yes` and `verify` before the gate, takes the frozen mode, and waits under the driver."""

import json
import re
from pathlib import Path

import pytest

from superegm import gate, store
from test_file import (ROOT, ROWS, applied, close_card, dry_run, gated, hp, open_card, state_of, planned, converge)


def reviews_of(world, uid):
  """The folder of the unit's plan review in the handoff's `reviews/`."""
  return next(p.parent for p in hp(world, "reviews").glob("*/review.json")
              if json.loads(p.read_text(encoding="utf-8"))["artifact"] == uid)


def test_converged_review_refuses_a_later_round(world):
  spec, plan, handoff_id, card = dry_run(world)
  folder = reviews_of(world, "U01")
  # U01's plan review converged at round 2 on the current body
  round_one = json.loads((folder / "round-1.json").read_text(encoding="utf-8"))
  (folder / "round-2.json").write_text(json.dumps(round_one), encoding="utf-8")
  meta = json.loads((folder / "review.json").read_text(encoding="utf-8"))
  meta["converged_round"] = 2
  (folder / "review.json").write_text(json.dumps(meta), encoding="utf-8")
  hp(world, "state")  # resolves the handoff of the spec for `store`
  handoff_store = store(world.repo)
  assert gate.converged_review(handoff_store, "U01") == (True, round_one["artifact_sha256"])
  # a round-3 file then written
  (folder / "round-3.json").write_text(json.dumps(round_one), encoding="utf-8")
  assert gate.converged_review(handoff_store, "U01") == (False, None)
  code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", card)
  assert code == 1 and "gate: U01 plan review not converged" in out, out
  # a resumed apply keeps the hashes of the earlier pass and refuses on its own check
  code, out = world.run("apply", "--yes", "--spec", spec, "--runcard", card)
  assert code == 1 and "apply: U01 body differs from its converged round" in out, out
  # without the round-3 file
  (folder / "round-3.json").unlink()
  assert gate.converged_review(handoff_store, "U01") == (True, round_one["artifact_sha256"])


@pytest.mark.parametrize("case, apply_code, verify_line", [
    ("complete with problems, repaired by hand", 0, "verify: complete, <k> of <k> checked, 0 problem(s)"),
    ("issue body mismatch left", 1, "MISMATCH"),     # a typed run reports it; the fresh receipt replaces the stored one
    ("--amend-units changed the plan", 1, None)])    # falls through: gate --pass, dry-run; len(filings) unchanged
def test_started_filing_resumes(world, case, apply_code, verify_line):
  spec, plan, handoff_id, card = applied(world)
  state = state_of(world)
  filed = state["units"]["U01"]["number"]
  clean = world.gh.issues[filed]["body"]
  # a filing applied (filings[-1].sha256 == confirmed.sha256), verify recorded a failing receipt
  world.gh.issues[filed]["body"] = clean + "\nedited by hand\n"
  code, out = world.run("verify", "--spec", spec, "--runcard", card)
  assert code == 1 and "MISMATCH" in out, out
  state = state_of(world)
  assert state["filings"][-1]["sha256"] == state["confirmed"]["sha256"] and state["verify"]["problems"]
  state["verify"]["stale"] = True  # the stored receipt the fresh one must replace
  (hp(world, "state")).write_text(json.dumps(state), encoding="utf-8")
  filings = len(state["filings"])
  if case.startswith("complete"):
    world.gh.issues[filed]["body"] = clean  # repaired by hand on GitHub
  if case.startswith("--amend"):
    plan_text = plan.read_text(encoding="utf-8")
    from test_file import unit_section, approve, graphed
    import hashlib
    approve(world, ROWS, amended=(hashlib.sha256(spec.read_bytes()).hexdigest(),))
    plan.write_text(plan_text.replace("## Global constraints", unit_section(*ROWS[2]) + "\n## Global constraints"), encoding="utf-8")
    graphed(world, spec, plan)
    converge(world, "U03")
  # the resume order of the skill: `apply --yes` then `verify`, no `gate --pass` between
  code, out = world.run("apply", "--yes", "--spec", spec, "--runcard", card)
  assert code == apply_code, out
  if case.startswith("--amend"):
    assert "changed after the gate" in out or "write list changed" in out, out
    after = state_of(world)
    assert len(after["filings"]) == filings and after["verify"].get("stale")  # the earlier entry and receipt stay
    code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", card)
    assert code == 0 and "gate passed" in out, out
    code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
    assert code == 0, out
    assert len(state_of(world)["filings"]) == filings
    return
  code, out = world.run("verify", "--spec", spec, "--runcard", card)
  after = state_of(world)
  assert "stale" not in after["verify"] and after["verify"]["sha256"] == after["confirmed_sha256"]
  if case.startswith("complete"):
    assert code == 0 and re.search(r"verify: complete, (\d+) of \1 checked, 0 problem\(s\)", out), out
    assert after["verify"]["complete"] and not after["verify"]["problems"]
  else:
    assert code == 1 and verify_line in out, out
    assert after["verify"]["problems"] and all(p.startswith("MISMATCH") for p in after["verify"]["problems"])


def test_file_skill_under_the_chain():
  body = (ROOT / "skills/file/SKILL.md").read_text(encoding="utf-8").split("---", 2)[2]
  assert len(body.encode("utf-8")) <= 24_000
  # the resume names `filings[]` and `confirmed_sha256`; its `apply --yes` and `verify` come before `gate --pass`
  resume = body.index("Resume a started filing")
  assert "filings[]" in body[resume:] and "confirmed_sha256" in body[resume:]
  gate_at = body.index("gate --pass")
  assert resume < body.index("apply --yes", resume) < body.index("verify", resume) < gate_at
  # the config-mode clause of Step 1 is gone: the frozen default, `config.mode` the fallback
  assert "the config's `mode` is `leavemealone`" not in body
  step_one = body[body.index("## Step 1"):resume]
  assert "--mode leavemealone" in step_one and "only when the invocation said `--leavemealone`" in step_one
  assert "frozen" in step_one and "`config.mode`" in step_one
  # under the driver: `next wait` at Create and on MISMATCH lines other than `MISMATCH read failed`
  assert "<HELPER>' next wait" in body and "--phase file" in body and "SUPEREGM_ROLE=driver" in body
  create = body[body.index("In leavemealone-mode there is no question"):body.index("## Step 5")]
  assert "next wait" in create and "handoff_dryrun.md" in create
  readback = body[body.index("## Step 6"):body.index("## Step 7")]
  assert "next wait" in readback and "MISMATCH read failed" in readback
  # on a wait record: `runcard open --mode normal`, the record's question asked directly, then `next clear`
  assert "runcard open --mode normal" in body and "the record's question" in body
  assert "<HELPER>' next clear" in body
  # the gate's "nothing to file" no longer ends the skill after a resumed verify with problems
  gate_text = body[gate_at:body.index("## Step 4")]
  assert "nothing to file" in gate_text and "never after a resumed verify with problems" in gate_text
