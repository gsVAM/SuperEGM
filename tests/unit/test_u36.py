# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U36's tests: the review round cap (`review.rounds`, the cycle's stored `cap`, the `Rounds:` line frozen at approval), the narrowed panel and the hand-written approval.

"""U36: the review round cap and a narrowed panel."""

import json
import pytest
from conftest import REPO, ROOT, set_config
from test_review import (SPEC, SLUG, PANEL_OF, opened, converged_spec, approve, hstore, rjson, rpath,
                         head_round, record, status, F, A, card, spec_file, seed_handoff, HID)
from superegm import approve_spec, atomic_write, handoff_store

BANNED = ["(?i)secret-codename"]


def live_rounds(world, value):
  """The repository's config with `review.rounds` set to `value` (a bad value stays as written)."""
  set_config(world, repo=REPO, banned_terms=BANNED, review={"rounds": value})


def edit_entry(world, **changes):
  """Rewrite the latest approval entry by hand: a key set, or dropped with `None`."""
  path = hstore(world).path("approvals", SLUG)
  data = json.loads(path.read_text(encoding="utf-8"))
  for key, value in changes.items():
    data["entries"][-1].pop(key, None)
    if value is not None:
      data["entries"][-1][key] = value
  atomic_write(path, data)


def fill_round(world, kind, rid, n, cid):
  """Round `n` with one high finding by the panel's first reviewer, the others empty."""
  if kind == "head":
    head_round(world, n, "posted", cid, "revise")
  for i, reviewer in enumerate(PANEL_OF[kind].split(",")):
    lines = [F(reviewer, n, 1)] if i == 0 else []
    got = record(world, rid, n, reviewer, lines, cid, sha=A if kind == "head" else None)
    assert got[0] == 0, got


def rounds_until_cap(world, kind, rid, cid, limit=12):
  """How many rounds record before `review status` says cap (exit 2)."""
  for n in range(1, limit + 1):
    fill_round(world, kind, rid, n, cid)
    if status(world, rid, cid)[0] == 2:
      return n
  return None


@pytest.mark.parametrize("kind, source, cap", [
  ("spec", "live review.rounds 3", 3),
  ("spec", "live review.rounds 7", 7),
  ("plan", "latest approval entry rounds 4", 4),
  ("head", "latest approval entry rounds 4", 4),
  ("integrate", "latest approval entry rounds 4", 4),
  ("plan", "1.2.0 entry without rounds", 5),
  ("plan", "legacy flat store, no approval entry", 5),
  ("spec", "record opened under 1.2.0 without cap", 5),
])
def test_cap_stored_at_open(world, kind, source, cap):
  """A cycle stores its cap at open and keeps it through a later config edit; no cap reads 5."""
  if source.startswith("live"):
    live_rounds(world, cap)
    spec, cid, rid = opened(world)
  elif source.startswith("latest approval"):
    spec, cid, rid = converged_spec(world)
    assert approve(world, spec, cid, "--yes")[0] == 0
    edit_entry(world, rounds=cap)
    spec, cid, rid = opened(world, kind)
  elif source.startswith("1.2.0 entry"):
    spec, cid, rid = converged_spec(world)
    assert approve(world, spec, cid, "--yes")[0] == 0
    edit_entry(world, rounds=None)
    spec, cid, rid = opened(world, kind)
  elif source.startswith("legacy"):
    spec, cid, rid = opened(world, kind)
  else:
    live_rounds(world, 3)
    spec, cid, rid = opened(world)
    review = rjson(world, rid)
    review.pop("cap")
    atomic_write(rpath(world, rid, "review.json"), review)
  live_rounds(world, 9)                                    # a later config edit does not move the stored cap
  assert rounds_until_cap(world, kind, rid, cid) == cap
  other = spec.with_name("other-design.md")
  other.write_text(SPEC, encoding="utf-8")
  other_card = card(world, other)
  for bad in (0, 11):
    live_rounds(world, bad)
    code, out = world.run("review", "open", "--kind", "spec", "--artifact", str(other), "--reviewers",
                          PANEL_OF["spec"], "--runcard", other_card)
    assert code == 1 and "review.rounds" in out, out


def with_rounds_line(extra):
  """SPEC with `extra` before its first H2, or (an `(after the first H2)` line) inside its first section."""
  if extra.startswith("(after"):
    return SPEC.replace("Text.\n", "Text.\n" + extra.split(") ", 1)[1], 1)
  return SPEC.replace("## 1. Intent", extra + "\n## 1. Intent", 1)


@pytest.mark.parametrize("before_first_h2, live, frozen, refused_with", [
  ("Rounds: 4\n", 3, 4, None),
  ("", 3, 3, None),
  ("(after the first H2) Rounds: 9\n", 3, 3, None),
  ("Rounds: 0\n", 3, None, "Rounds: 0"),
  ("Rounds: 11\n", 3, None, "Rounds: 11"),
  ("Rounds: two\n", 3, None, "Rounds: two"),
  ("Rounds: 4\nRounds: 5\n", 3, None, "Rounds: 5"),
  ("", 11, None, "review.rounds"),
])
def test_rounds_frozen_at_approval(world, before_first_h2, live, frozen, refused_with):
  """approve-spec freezes the one `Rounds:` line before the first H2, else the live value; `--amend-units` copies
  the frozen fields the extended entry has."""
  spec, cid, rid = converged_spec(world, text=with_rounds_line(before_first_h2))
  live_rounds(world, live)
  code, out = approve(world, spec, cid, "--yes")
  if refused_with:
    assert code == 1 and refused_with in out, out
    assert not hstore(world).path("approvals", SLUG).exists()
    return
  assert code == 0, out
  entry = json.loads(hstore(world).path("approvals", SLUG).read_text(encoding="utf-8"))["entries"][-1]
  assert entry["rounds"] == frozen
  assert "rounds" in approve_spec.FROZEN_FIELDS
  icid = card(world, spec, "integrate")
  spec.write_text(spec.read_text(encoding="utf-8") + "| U02 | more | U01 | S |\n", encoding="utf-8")
  assert approve(world, spec, icid, "--amend-units")[0] == 0
  entries = json.loads(hstore(world).path("approvals", SLUG).read_text(encoding="utf-8"))["entries"]
  assert entries[-1]["kind"] == "amend-units" and entries[-1]["rounds"] == frozen
  edit_entry(world, rounds=None)                           # a 1.2.0 entry: its amendment stays without the field
  spec.write_text(spec.read_text(encoding="utf-8") + "| U03 | again | U01 | S |\n", encoding="utf-8")
  assert approve(world, spec, icid, "--amend-units")[0] == 0
  entries = json.loads(hstore(world).path("approvals", SLUG).read_text(encoding="utf-8"))["entries"]
  assert len(entries) == 3 and "rounds" not in entries[-1]


def test_approve_after_hand_written_approval(world):
  """A latest approval whose review has no numeric `-c<n>` suffix counts as since = 0."""
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  edit_entry(world, review="owner: approved in session")
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  entries = json.loads(hstore(world).path("approvals", SLUG).read_text(encoding="utf-8"))["entries"]
  assert entries[-1]["review"] == rid and len(entries) == 2


def resume(world, spec, cid, given, kind="spec", artifact=None):
  """`review open` again with `given` as the panel: (code, output)."""
  return world.run("review", "open", "--kind", kind, "--artifact", artifact or str(spec), "--reviewers", given, "--runcard", cid)


@pytest.mark.parametrize("panels_before, recorded, given, panels_after, line2", [
  (None, [1, 2], "design,style", [{"from_round": 3, "reviewers": ["design", "style", "astra"]}], "panel design,style,astra from round 3"),
  (None, [1, 2, "3 partly"], "design,style", [{"from_round": 4, "reviewers": ["design", "style", "astra"]}], "panel design,style,astra from round 4"),
  (None, [1], "design,zoom-out,style", None, "panel design,zoom-out,style,astra from round 2"),
  (None, [1], "design,zoom-out,style,comprehension", None, "panel design,zoom-out,style,astra from round 2 (unchanged: "),
  (None, [1], "design,comprehension", None, "panel design,zoom-out,style,astra from round 2 (unchanged: "),
  ([{"from_round": 3, "reviewers": ["design", "style", "astra"]}], [1, 2, 3], "design",
   [{"from_round": 3, "reviewers": ["design", "style", "astra"]}, {"from_round": 4, "reviewers": ["design", "astra"]}], "panel design,astra from round 4"),
])
def test_resume_narrows_the_panel(world, panels_before, recorded, given, panels_after, line2):
  """A resume with a proper subset of the panel, `design` first, narrows it from the next unrecorded round (the Astra
  lane kept); a wider, overlapping or equal panel changes nothing; a spec resume prints the panel line, no other kind."""
  spec, cid, rid = opened(world, reviewers="design,zoom-out,style", astra="on")
  assert rjson(world, rid)["reviewers"] == ["design", "zoom-out", "style", "astra"]
  for item in recorded:
    n = item if isinstance(item, int) else int(item.split()[0])
    for reviewer in ("design", "zoom-out", "style")[:1 if isinstance(item, str) else 3]:
      assert record(world, rid, n, reviewer, [F("design", n, 1)] if reviewer == "design" else [], cid)[0] == 0
  if panels_before:
    review = rjson(world, rid)
    review["panels"] = panels_before
    atomic_write(rpath(world, rid, "review.json"), review)
  code, out = resume(world, spec, cid, given)
  assert code == 0, out
  assert rjson(world, rid).get("panels") == panels_after
  lines = out.splitlines()
  assert lines[0] == rid and len(lines) == 2
  assert lines[1].startswith(line2) if "(unchanged" in line2 else lines[1] == line2
  assert "review open: first reviewer must be design" in resume(world, spec, cid, "zoom-out,design")[1]
  _, pcid, prid = opened(world, "plan")
  for panel in (PANEL_OF["plan"], "readiness"):
    code, out = resume(world, spec, pcid, panel, "plan", "U07")
    assert code == 0 and out.splitlines() == [prid], out
  assert "panels" not in rjson(world, prid)


def test_round_reads_its_panel(world):
  """Narrowed to design,style from round 3: zoom-out is off round 3's panel and round 3 completes without it."""
  spec, cid, rid = opened(world, reviewers="design,zoom-out,style")
  for reviewer in ("design", "zoom-out", "style"):
    assert record(world, rid, 1, reviewer, [F("design", 1, 1)] if reviewer == "design" else [], cid)[0] == 0
  for reviewer in ("design", "style"):
    assert record(world, rid, 2, reviewer, [F("design", 2, 1)] if reviewer == "design" else [], cid)[0] == 0
  assert rjson(world, rid, "round-2.json")["what_ran"].startswith("not run (zoom-out")
  code, out = resume(world, spec, cid, "design,style")
  assert code == 0 and out.splitlines()[1] == "panel design,style from round 3", out
  code, out = record(world, rid, 3, "zoom-out", [], cid)
  assert code == 1 and "review record: zoom-out is not on the panel" in out
  for reviewer in ("design", "style"):
    assert record(world, rid, 3, reviewer, [F("design", 3, 1)] if reviewer == "design" else [], cid)[0] == 0
  assert rjson(world, rid, "round-3.json")["what_ran"] == "completed"
  assert record(world, rid, 2, "zoom-out", [], cid)[0] == 0
  assert rjson(world, rid, "round-2.json")["what_ran"] == "completed"


def test_review_loop_dispatches_the_printed_panel():
  """The loop dispatches the panel `review open` printed; the cap is `review.rounds`."""
  loop = (ROOT / "skills/review-spec/references/review_loop.md").read_text(encoding="utf-8")
  spec_skill = (ROOT / "skills/review-spec/SKILL.md").read_text(encoding="utf-8")
  assert "The panel cannot change after this" not in loop and "review.rounds" in loop
  assert "panel <a,b,astra> from round <n>" in loop and "panel <a,b,astra> from round <n>" in spec_skill


def test_a_handoff_without_its_own_entry_reads_rounds_5(world):
  """A legacy flat handoff sharing its spec with a newer approved handoff (frozen at rounds 4) has no entry of its
  own: its plan review stores cap 5."""
  spec = spec_file(world)
  seed_handoff(world, spec)                                # the flat store's handoff, HID
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  edit_entry(world, rounds=4)
  entry = json.loads(hstore(world).path("approvals", SLUG).read_text(encoding="utf-8"))["entries"][-1]
  assert entry["handoff_id"] != HID and entry["rounds"] == 4
  pcid = card(world, spec, "review-plan", handoff=HID)
  code, out = world.run("review", "open", "--kind", "plan", "--artifact", "U07", "--reviewers", PANEL_OF["plan"],
                        "--runcard", pcid)
  assert code == 0, out
  legacy = handoff_store(hstore(world), HID)
  assert json.loads(legacy.path("reviews", out.strip(), "review.json").read_text(encoding="utf-8"))["cap"] == 5


@pytest.mark.parametrize("review, since", [
  ("spec-x-c3", 3),
  ("spec-x-c12", 12),
  ("owner: approved in session", 0),
  ("123", 0),
  ("c7", 0),
  ("spec-x-c", 0),
  ("", 0),
])
def test_since_reads_the_cycle_suffix_alone(review, since):
  """Only a trailing `-c<n>` is a cycle number: a hand-written review reference, digits or not, counts as 0."""
  assert approve_spec.cycle_of(review) == since


def test_resume_journals_the_narrowing(world):
  """The narrowing is one journal line naming the panel and its first round; a resume that narrows nothing writes none."""
  spec, cid, rid = opened(world, reviewers="design,zoom-out,style")
  journal = hstore(world).path("journal")
  assert resume(world, spec, cid, "design,style")[0] == 0
  assert f"review open {rid} panel design,style from round 1 under {cid}" in journal.read_text(encoding="utf-8")
  assert resume(world, spec, cid, "design,style")[0] == 0
  assert journal.read_text(encoding="utf-8").count("panel design,style from round") == 1


def test_narrowing_twice_before_a_round_keeps_the_later(world):
  """Two narrowings before the same round leave one `panels` entry from that round: the later."""
  spec, cid, rid = opened(world, reviewers="design,zoom-out,style")
  assert resume(world, spec, cid, "design,zoom-out")[0] == 0
  code, out = resume(world, spec, cid, "design")
  assert code == 0 and out.splitlines()[1] == "panel design from round 1", out
  assert rjson(world, rid)["panels"] == [{"from_round": 1, "reviewers": ["design"]}]


def test_a_repeated_reviewer_in_the_given_panel_counts_once(world):
  """`design,zoom-out,zoom-out` narrows to `design,zoom-out`: a reviewer is dispatched once."""
  spec, cid, rid = opened(world, reviewers="design,zoom-out,style")
  code, out = resume(world, spec, cid, "design,zoom-out,zoom-out")
  assert code == 0 and out.splitlines()[1] == "panel design,zoom-out from round 1", out
  assert rjson(world, rid)["panels"] == [{"from_round": 1, "reviewers": ["design", "zoom-out"]}]
