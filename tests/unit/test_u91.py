# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U91

"""U91: a respec opened from a plan or integrate review's `fix-design` finding (spec section 7.6): `respec open`,
the wait of `file`, `integrate` and `next`, the source cycle its approval closes and the fresh plan cycle after."""

import json
import pytest

from superegm import atomic_write
from test_file import planned, open_card, hp, converge, dry_run, SLUG
from test_u43 import registry  # noqa: F401 -- autouse: HOME under tmp_path, so `next` never reads the owner's registry
from test_builders import spawn_fake, no_graphify, which  # noqa: F401  the fixtures test_builders' launches run under


def F(reviewer, n, i, sev="high"):
  return f"{reviewer}-{n}-{i} | {sev} | §1 | regression: no | claim {i}"


def record(world, rid, n, reviewer, lines, card):
  path = world.repo.parent / f"{rid}-{n}-{reviewer}.txt"
  path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
  code, out = world.run("review", "record", "--review", rid, "--round", str(n), "--reviewer", reviewer,
                        "--findings", str(path), "--isolation", "clean", "--model", "inherit:opus",
                        "--effort", "inherit:high", "--runcard", card)
  assert code == 0, out


def opened_review(world, spec, kind, uid="U02"):
  """A cycle of `kind` opened under its skill's card, its first reviewer's round 1 one high finding: (card, rid, fid)."""
  skill, artifact, first = {"plan": ("review-plan", uid, "readiness"),
                            "integrate": ("integrate", str(spec), "design")}[kind]
  card = open_card(world, skill, str(spec))
  code, out = world.run("review", "open", "--kind", kind, "--artifact", artifact, "--reviewers", first, "--runcard", card)
  assert code == 0, out
  rid = out.splitlines()[0]
  record(world, rid, 1, first, [F(first, 1, 1)], card)
  return card, rid, f"{first}-1-1"


def settle(world, rid, fid, disposition, card):
  code, out = world.run("review", "settle", "--review", rid, "--finding", fid, "--disposition", disposition,
                        "--owner", "--runcard", card)
  assert code == 0, out


def head_review(world, uid="U01"):
  """A head review written as `review open` leaves one, its round 1 finding settled fix-design (a head's settle refuses
  that disposition, so the files are written by hand): its id and finding id."""
  st = hp(world, "state").parent
  hid = json.loads((st / "state.json").read_text(encoding="utf-8"))["handoff_id"]
  rid = f"{hid[-6:]}-head-{uid}-c1"
  atomic_write(st / "reviews" / rid / "review.json",
               {"id": rid, "kind": "head", "artifact": uid, "cycle": 1, "handoff_id": hid, "reviewers": ["change-review"],
                "rulings": [], "converged": "no"})
  finding = {"id": "change-review-1-1", "severity": "high", "location": "§1", "regression": "no", "claim": "claim 1",
             "disposition": "fix-design", "ruling": "owner"}
  atomic_write(st / "reviews" / rid / "round-1.json",
               {"round": 1, "artifact_sha256": "a" * 64, "reviewers": {"change-review": {"findings": [finding]}}})
  return rid, finding["id"]


def respec_files(world):
  folder = hp(world, "file", "respec")
  return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


# ---------------------------------------------------------------- S1: respec open


@pytest.mark.parametrize("role, mode, finding, refused", [
  (None, "normal", "integrate fix-design", None),
  ("driver", "normal", "integrate fix-design", "respec open: owner only"),
  (None, "leavemealone", "integrate fix-design", "respec open: owner only"),
  (None, "normal", "plan fix-blocking", "fix-design"),
  (None, "normal", "head", "head"),
])
def test_respec_open_writes_or_refuses(world, monkeypatch, role, mode, finding, refused):
  spec, _, _ = planned(world)
  if finding == "head":
    rid, fid = head_review(world)
    skill = "review-plan"
  else:
    kind = finding.split()[0]
    card, rid, fid = opened_review(world, spec, kind)
    settle(world, rid, fid, "fix-design" if finding.endswith("fix-design") else "escalated", card)
    skill = {"plan": "review-plan", "integrate": "integrate"}[kind]
  card = open_card(world, skill, str(spec), mode if mode != "normal" else None)
  monkeypatch.delenv("SUPEREGM_ROLE", raising=False)  # a builder session runs the suite under its own role
  if role:
    monkeypatch.setenv("SUPEREGM_ROLE", role)
  code, out = world.run("respec", "open", "--review", rid, "--finding", fid, "--runcard", card)
  assert (refused is None) == (code == 0), out
  assert refused is None or refused in out
  if refused is None:
    assert respec_files(world) == ["R1.open.json"]
    record_ = json.loads(hp(world, "file", "respec", "R1.open.json").read_text(encoding="utf-8"))
    assert {k: record_[k] for k in ("id", "unit", "review", "finding")} == {"id": "R1", "unit": None, "review": rid, "finding": fid}
    assert "comment_id" not in record_
  else:
    assert respec_files(world) == []


@pytest.mark.parametrize("held", ["open", "applied"])
def test_respec_open_rerun_keeps_its_file(world, monkeypatch, held):
  """A rerun on the same review and finding prints the R<n> it wrote and writes no R2; once an approval names R1, the
  rerun is refused, never printed as open."""
  monkeypatch.delenv("SUPEREGM_ROLE", raising=False)
  spec, _, _ = planned(world)
  card, rid, fid = opened_review(world, spec, "integrate")
  settle(world, rid, fid, "fix-design", card)
  code, out = world.run("respec", "open", "--review", rid, "--finding", fid, "--runcard", card)
  assert code == 0, out
  if held == "applied":
    add_entry(world, respec="R1", review=f"spec-{SLUG}-c2", kind="respec", source_review=rid)
  code, out = world.run("respec", "open", "--review", rid, "--finding", fid, "--runcard", card)
  if held == "open":
    assert code == 0 and "respec R1 open" in out, out
  else:
    assert code == 1 and "respec open: R1" in out and "applied" in out and "respec R1 open" not in out, out
  assert respec_files(world) == ["R1.open.json"]


def test_respec_open_names_itself_on_an_unknown_finding(world, monkeypatch):
  monkeypatch.delenv("SUPEREGM_ROLE", raising=False)
  spec, _, _ = planned(world)
  card, rid, _ = opened_review(world, spec, "integrate")
  code, out = world.run("respec", "open", "--review", rid, "--finding", "design-9-9", "--runcard", card)
  assert code == 1 and "respec open: no finding design-9-9" in out and "review settle" not in out, out
  assert respec_files(world) == []


# ---------------------------------------------------------------- S2: file waits


def put_review_respec(world, rid="R1", review="abc123-plan-U02-c1", finding="readiness-1-1"):
  """`respec/R<n>.open.json` as `respec open` writes it from a plan review's fix-design finding (`unit: null`)."""
  atomic_write(hp(world, "file", "respec", f"{rid}.open.json"),
               {"id": rid, "unit": None, "review": review, "finding": finding, "at": "2026-11-04T00:00:00Z"})


def approvals_path(world):
  return world.artifacts / "approvals" / f"{SLUG}.json"


def add_entry(world, **fields):
  """One more approval entry, the latest one's fields with `fields` over them."""
  data = json.loads(approvals_path(world).read_text(encoding="utf-8"))
  data["entries"].append(data["entries"][-1] | {"approved_at": "2026-11-05T00:00:00Z"} | fields)
  approvals_path(world).write_text(json.dumps(data), encoding="utf-8")


def respec_state(world, state, handoff_id):
  put_review_respec(world)
  if state == "applied":
    add_entry(world, respec="R1", review="spec-r1-c2", kind="respec-review")
  elif state == "withdrawn":  # a later approval opened another handoff
    add_entry(world, handoff_id=f"{SLUG}-ffffff", kind="opening", review=f"spec-{SLUG}-c2")


@pytest.mark.parametrize("state, command, refused", [
  ("open", "gate --pass", True), ("open", "apply --yes", True),
  ("applied", "gate --pass", False), ("withdrawn", "gate --pass", False),
])
def test_file_waits_on_an_open_respec(world, state, command, refused):
  if command == "apply --yes":  # the gate passed and the dry run confirmed before the respec opened: a resumed apply
    spec, _, handoff_id, card = dry_run(world)
  else:
    spec, _, handoff_id = planned(world)
    for uid in ("U01", "U02"):
      converge(world, uid)
    card = open_card(world, "file", str(spec))
  respec_state(world, state, handoff_id)
  argv = ["apply", "--spec", spec, "--yes"] if command == "apply --yes" else ["gate", "--pass", "--spec", spec]
  argv += ["--handoff", handoff_id] if state == "withdrawn" else []
  code, out = world.run(*argv, "--runcard", card)
  assert ("file: respec R1 open" in out) is refused, out
  if refused:
    assert code == 1 and not world.gh.issues, out  # nothing filed
  if state == "applied":
    assert code == 0, out



@pytest.mark.parametrize("filing", ["gate passed, dry run confirmed", "every unit filed"])
def test_dry_run_and_apply_wait_on_an_open_respec(world, filing):
  """`require_gate` refuses while the respec is open: a dry run never overwrites the confirmed receipt, and an apply
  with no unit left to file never skips the check."""
  from test_file import applied
  spec, _, _, card = (dry_run if filing.startswith("gate") else applied)(world)
  put_review_respec(world)
  before = json.loads(hp(world, "state").read_text(encoding="utf-8"))
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 1 and "file: respec R1 open" in out, out
  after = json.loads(hp(world, "state").read_text(encoding="utf-8"))
  assert (after.get("confirmed"), after.get("confirmed_sha256")) == (before.get("confirmed"), before.get("confirmed_sha256"))
  issues = json.dumps(world.gh.issues, sort_keys=True)
  code, out = world.run("apply", "--spec", spec, "--yes", "--runcard", card)
  assert code == 1 and "file: respec R1 open" in out, out
  assert json.dumps(world.gh.issues, sort_keys=True) == issues


# ---------------------------------------------------------------- S3: next waits


@pytest.mark.parametrize("origin, units, printed", [
  ("plan", "U07 unfiled", "waiting respec R1"),
  ("integrate", "every unit filed and landed", "waiting respec R1"),
  ("plan", "U05 filed with a running launch whose exit file exists, U07 unfiled", "wave"),
])
def test_next_waits_on_a_review_respec(world, registry, origin, units, printed):
  """Test_u43's chain of U01-U03: U01 and U02 stand for the filed units, U03 for the unfiled one."""
  from test_u43 import Chain, jwrite
  c = Chain(world)
  if units == "every unit filed and landed":
    c.all_filed()
  else:  # U03 unfiled with no plan review: `review-plan` would match
    c.plan("U01", "U02", "U03")
    running = units.startswith("U05")
    for n, uid in enumerate(("U01", "U02"), 1):
      c.review(uid)
      c.filed(uid, n, pr={"number": 10 + n}, ci="success", landed=not (running and uid == "U01"))
    if running:
      result = world.repo.parent / "U01-r1.result"
      jwrite(c.hs.path("launches", "U01"), {"launches": [{"round": 1, "status": "running", "result_file": str(result)}]})
      result.with_name(result.name + ".exit").write_text("0\n", encoding="utf-8")
  c.save()
  source = f"{c.hid[-6:]}-plan-U03-c1" if origin == "plan" else f"spec-{SLUG}-integrate-c1"
  jwrite(c.hs.path("file", "respec", "R1.open.json"),
         {"id": "R1", "unit": None, "review": source, "finding": "readiness-1-1", "at": "2026-11-15T00:00:00Z"})
  code, out, before, after = c.next()
  assert (code, out) == (0, printed)
  assert before == after  # next writes nothing


def test_chained_inbox_shows_one_review_respec_wait(world, registry, monkeypatch):
  """A chained handoff (the chain on, a frozen mode) whose `next` prints `waiting respec R1`: `chain_items` drops
  that line, so the inbox lists the respec's one item."""
  import superegm as core
  from superegm import inbox, phase, store
  from test_u43 import Chain, jwrite
  monkeypatch.setattr(core, "frozen_mode", lambda hs: "normal")
  monkeypatch.setattr(core, "chain_on", lambda config: True)
  c = Chain(world)
  c.plan("U01", "U02", "U03")
  for n, uid in enumerate(("U01", "U02"), 1):
    c.review(uid)
    c.filed(uid, n, pr={"number": 10 + n}, ci="success", landed=True)
  c.save()
  jwrite(c.hs.path("file", "respec", "R1.open.json"),
         {"id": "R1", "unit": None, "review": f"{c.hid[-6:]}-plan-U03-c1", "finding": "readiness-1-1",
          "at": "2026-11-15T00:00:00Z"})
  st = store(world.repo)
  assert phase.next_line(st, c.hid) == "waiting respec R1"
  lines = [inbox.line_of(i) for i in inbox.inbox_items(st, [c.hid])]
  assert sum("waiting respec R1" in line for line in lines) == 1, lines


# ---------------------------------------------------------------- S4: the approval closes the source cycle


def source_cycle(st, kind, artifact, handoff_id):
  """Cycle 1 of a plan or integrate review in `st`'s handoff directory, its one round holding a `fix-design` finding
  (exit 4): the review `respec open` read. Its id."""
  import superegm as core
  from superegm import review
  rid = review.review_id(st, kind, artifact, 1)
  core.atomic_write(st.path("reviews", rid, "review.json"), {
    "kind": kind, "artifact": artifact, "cycle": 1, "handoff_id": handoff_id, "reviewers": ["readiness"], "cap": 3,
    "runcard": "rc", "converged": "no", "converged_round": None, "rulings": []})
  finding = {"id": "readiness-1-1", "severity": "high", "location": "§1", "regression": "no", "claim": "claim 1",
             "disposition": "fix-design", "reason": None}
  core.atomic_write(st.path("reviews", rid, "round-1.json"), {
    "round": 1, "runcard": "rc", "artifact_sha256": "0" * 64, "what_ran": "completed",
    "reviewers": {"readiness": {"findings": [finding]}}})
  return rid


def review_status(st, rid):
  """`review status`'s exit code for `rid` in `st`'s handoff: the verdict `evaluate` returns."""
  from superegm import review
  return review.evaluate(st, review.load_review(st, rid), None).code


@pytest.mark.parametrize("kind", ["plan", "integrate"])
def test_respec_approval_closes_the_source_cycle(world, kind):
  import superegm as core
  from superegm import review
  from test_u85 import respec_world, respec_cycle, R1_TEXT, BASE, HID
  spec, st = respec_world(world, [(BASE, None)])
  artifact = "U2" if kind == "plan" else str(spec)
  source_id = source_cycle(st, kind, artifact, HID)
  other = core.handoff_store(st, "x-other")  # a second handoff holding a cycle of the source's id
  assert source_cycle(other, kind, artifact, "x-other") == source_id
  core.atomic_write(other.path("unit", "U2"), st.path("unit", "U2").read_text(encoding="utf-8"))
  core.atomic_write(st.path("file", "respec", "R1.open.json"),
                    {"id": "R1", "unit": None, "review": source_id, "finding": "readiness-1-1", "at": "2026-11-13T00:00:00Z"})
  assert review_status(st, source_id) == 4
  spec.write_text("".join(R1_TEXT), encoding="utf-8")
  spec_cycle_id = "spec-x-c2"
  assert spec_cycle_id != source_id
  respec_cycle(world, spec, st, rid=spec_cycle_id)
  code, out = world.run("approve-spec", "--spec", spec, "--respec", "R1", "--yes")
  assert code == 0, out
  entry = json.loads(st.path("approvals", core.spec_slug(spec)).read_text(encoding="utf-8"))["entries"][-1]
  assert entry["source_review"] == source_id and entry["review"] == spec_cycle_id
  assert review_status(st, source_id) != 4
  assert review.latest_cycle(st, kind, artifact)[1] is True
  spec_review, _ = review.latest_cycle(st, "spec", str(spec))
  assert spec_review["cycle"] == 2 and core.load_approval(st, spec)["review"] == spec_cycle_id
  assert review_status(other, source_id) == 4
  if kind == "plan":  # an integrate cycle of a handoff that is not the store's current one is closed by D1 (a) anyway
    assert review.latest_cycle(other, kind, artifact)[1] is False


# ---------------------------------------------------------------- S5: due_rows opens a fresh cycle


@pytest.mark.parametrize("case", ["respec closed the cycle at the old cap", "proceeded cycle, body changed by a replan"])
def test_due_rows_opens_a_fresh_cycle(world, case):
  """test_file's planned U01 and U02: U01 converged by an accept ruling beside U02, the unit under the case."""
  from superegm import review, review_plan, store
  spec, _, hid = planned(world, ("U01", "U02"))
  card = open_card(world, "review-plan", str(spec))
  code, out = world.run("review", "open", "--kind", "plan", "--artifact", "U01", "--reviewers", "readiness", "--runcard", card)
  assert code == 0, out
  accepted = out.splitlines()[0]
  st = store(world.repo)
  path = st.path("reviews", accepted, "review.json")
  atomic_write(path, json.loads(path.read_text(encoding="utf-8")) | {"cap": 1})
  record(world, accepted, 1, "readiness", [F("readiness", 1, 1)], card)  # U01 at its cap of one unclean round
  code, out = world.run("review", "rule", "--review", accepted, "--ruling", "accept", "--owner", "--runcard", card)
  assert code == 0, out  # U01 converged by the owner's accept
  assert review.load_review(st, accepted)["converged"].startswith("by ruling ")
  sha = json.loads(hp(world, "units").read_text(encoding="utf-8"))["units"]["U02"]["body_sha256"]
  if case.startswith("respec"):
    rid = source_cycle(st, "plan", "U02", hid)  # cycle 1: a fix-design finding at the cap
    old = json.loads(st.path("reviews", rid, "review.json").read_text(encoding="utf-8"))
    atomic_write(st.path("reviews", rid, "review.json"), old | {"cap": 1})
    assert [r[1] for r in review_plan.due_rows(st, card) if r[0] == "U02"] == ["fix-design"]
    put_review_respec(world, review=rid)
    add_entry(world, respec="R1", review=f"spec-{SLUG}-c2", kind="respec", source_review=rid)
  else:
    code, out = world.run("review", "open", "--kind", "plan", "--artifact", "U02", "--reviewers", "readiness",
                          "--runcard", card)
    assert code == 0, out
    rid = out.splitlines()[0]
    code, out = world.run("review", "rule", "--review", rid, "--ruling", "proceed", "--owner", "--reason", "planned enough",
                          "--runcard", card)
    assert code == 0, out
    assert [r[1] for r in review_plan.due_rows(st, card) if r[0] == "U02"] == ["converged"]
    body = st.path("unit", "U02")
    body.write_text(body.read_text(encoding="utf-8") + "\nReplanned.\n", encoding="utf-8")
    units = json.loads(hp(world, "units").read_text(encoding="utf-8"))
    sha = units["units"]["U02"]["body_sha256"] = review.current_sha.__globals__["core"].sha256_file(body)
    atomic_write(hp(world, "units"), units)
  old_review = review.load_review(st, rid)
  rows = review_plan.due_rows(st, card)
  assert [r for r in rows if r[0] == "U02"] == [("U02", "due", "-", "1", sha)]  # `due - 1`: the skill runs `review open`
  assert [r[1] for r in rows if r[0] == "U01"] == ["converged"]  # the accepted cycle beside it stays converged
  code, out = world.run("review", "open", "--kind", "plan", "--artifact", "U02", "--reviewers", "readiness", "--runcard", card)
  assert code == 0, out
  new_review = review.load_review(st, out.splitlines()[0])
  assert new_review["cycle"] == old_review["cycle"] + 1


# ---------------------------------------------------------------- S6: the skills offer the respec


@pytest.mark.parametrize("path", ["skills/review-plan/SKILL.md", "skills/integrate/SKILL.md"])
def test_skills_offer_respec_beside_void(path):
  """Interactive only: the leavemealone panel never offers it."""
  from conftest import ROOT
  text = (ROOT / path).read_text(encoding="utf-8")
  assert "superegm respec open --review" in text
  assert "--void" in text
  offer = next(p for p in text.split("\n\n") if "superegm respec open --review" in p)
  assert "--void" in offer and "leavemealone" in offer  # beside the void, and never under a leavemealone card


# ---------------------------------------------------------------- S7: a plan-origin respec skips unfiled units


def plan_respec_world(world):
  """test_builders' seed of U05 and U07 with U07 unfiled and a plan-origin respec R1 open on U07's plan review:
  (store, card, handoff id)."""
  import test_builders as tb
  s, card, hid, _ = tb.seed(world, units=("U05", "U07"))
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  del state["units"]["U07"]  # unfiled: its plan review raised the design finding
  atomic_write(s.path("state"), state)
  rid = f"{hid[-6:]}plan-U07-c1"
  atomic_write(s.path("reviews", rid, "review.json"),
               {"id": rid, "kind": "plan", "artifact": "U07", "cycle": 1, "handoff_id": hid, "rulings": []})
  atomic_write(s.path("file", "respec", "R1.open.json"),
               {"id": "R1", "unit": None, "review": rid, "finding": "readiness-1-1", "at": "2026-11-04T00:00:00Z"})
  return s, card, hid


def test_plan_respec_skips_unfiled_units(world, monkeypatch):
  """A plan-origin respec R1 waits; U05 filed, U07 unfiled: status, readiness and launch skip U07 only."""
  from superegm import inbox, store as store_of
  s, card, hid = plan_respec_world(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")

  code, out = world.run("status", "--runcard", card)
  assert code == 0, out
  rows = out.splitlines()
  units = [line.split()[0] for line in rows if line[:1] == "U"]
  ready = next(line for line in rows if line.startswith("ready: "))
  assert "U07" not in units and "U05" in units and "U07" not in ready
  code, out = world.run("launch", "--runcard", card)
  assert code == 0, out
  marked = next((line for line in out.splitlines() if line.startswith("marked:")), "")
  assert "U05" in marked and "U07" not in marked  # readiness and launch skip it
  assert "launched" not in json.loads(s.path("state").read_text(encoding="utf-8"))["units"].get("U07", {})
  lines = [inbox.line_of(i) for i in inbox.inbox_items(store_of(world.repo), [hid])]
  assert any("waiting respec R1" in line for line in lines), lines


def test_wave_trigger_skips_unfiled_units(world):
  """The driver's `wave_trigger` reaches `tick_trigger` on a fresh handoff: U07, unfiled under the plan-origin
  respec, is never read from GitHub (no `issues/None`), and the tick still reads the filed unit."""
  from superegm import driver
  s, _, _ = plan_respec_world(world)
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  trigger = driver.wave_trigger(s, {"root": str(world.repo)}, state)
  assert not any("issues/None" in " ".join(map(str, call)) for call in world.gh.calls), world.gh.calls
  assert trigger is None or "U07" not in trigger, trigger

