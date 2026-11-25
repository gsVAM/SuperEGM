# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U110's tests, 1.3 design section 3.10 (Post-mortem and retro): copies counted once, not-run rounds, the redesign stop, unapproved respec cycles, the Reply label and the empty answer.

"""U110: the post-mortem's copies, `--not-run` rounds, `redesign` cap rulings, unapproved respec cycles and `**Reply <fid>:**`, and `next answer --answer ''`."""

import pytest
from test_u43 import registry  # noqa: F401  (the autouse fixture: no test reads the owner's registry)
from test_u78 import jwrite, reviewed, table, two_units


def found(fid, claim="a defect", severity="high", **more):
  return {"id": fid, "severity": severity, "claim": claim, "location": "a.py:1", "regression": "no", "disposition": None, **more}


def head_rounds(c, rounds, rulings=(), uid="U01"):
  """One head cycle of `uid`: `rounds[n - 1]` is round n's `{reviewer: [findings]}`; each round is posted; `rulings` are the foreman's ruling texts."""
  jwrite(c.hs.path("foreman", uid), {
      "dispatch_id": None, "decisions": [], "rounds": [{"round": n, "phase": "posted", "outcome": "posted"} for n in range(1, len(rounds) + 1)],
      "rulings": [{"ruling": text, "by": "owner"} for text in rulings]})
  names = sorted({name for rnd in rounds for name in rnd})
  records = [{name: {"findings": findings} for name, findings in rnd.items()} for rnd in rounds]
  reviewed(c, f"head-{uid}-c1", "head", uid, names, records[0])
  for n, record in enumerate(records[1:], 2):
    jwrite(c.hs.path("reviews", f"head-{uid}-c1", f"round-{n}.json"), {"round": n, "runcard": "rc", "reviewers": record})


def report_of(world, c):
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  return c.hs.path("file", "postmortem.md").read_text(encoding="utf-8")


def keyed(report, section, width):
  """A section's rows, each keyed by its first `width` cells: `{(cell, ...): {column: cell}}`."""
  body = report.split(f"## {section}\n", 1)[1].split("\n## ", 1)[0]
  rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in body.splitlines() if line.startswith("|")]
  return {tuple(row[:width]): dict(zip(rows[0], row)) for row in rows[2:]}


EXTERNAL = found("ext-1")
UNREPLIED = "unreplied ext-1: a defect"
CONTESTED = "contested change-review-1-1: out of Scope"


@pytest.mark.parametrize("rounds, rulings, table_name, row, column, value", [
    # r1 external:octo ext-1 high; r2 foreman `unreplied ext-1: <claim>` copy settled fixed
    ([{"external:octo": [EXTERNAL]}, {"foreman": [found("foreman-2-1", UNREPLIED, disposition="fixed")]}], (),
     "Reviewers", ("external:octo", "head"), "fixed", "1"),
    # ... the copy ruled `<copy fid> finding overruled`
    ([{"external:octo": [EXTERNAL]}, {"foreman": [found("foreman-2-1", UNREPLIED)]}], ("foreman-2-1 finding overruled — not a defect",),
     "Reviewers", ("external:octo", "head"), "overruled", "1"),
    # ... the copy unsettled: the foreman raised nothing
    ([{"external:octo": [EXTERNAL]}, {"foreman": [found("foreman-2-1", UNREPLIED)]}], (),
     "Reviewers", ("foreman", "head"), "high", "0"),
    # r1 change-review-1-1 high; r2 foreman `contested change-review-1-1: <reason>` copy
    ([{"change-review": [found("change-review-1-1")]}, {"foreman": [found("foreman-2-1", CONTESTED)]}], (),
     "Reviewers", ("foreman", "head"), "high", "0"),
    ([{"change-review": [found("change-review-1-1")]}, {"foreman": [found("foreman-2-1", CONTESTED)]}], (),
     "Units", ("U01",), "high", "1"),
    # r1 foreman-1-1 high; r2 the foreman's only finding its carried copy
    ([{"foreman": [found("foreman-1-1")]}, {"foreman": [found("foreman-1-1", carried_from=1)]}], (),
     "Reviewers", ("foreman", "head"), "quiet rounds", "1"),
    # r1 external:octo ext-1 high, the foreman's entry empty; r2 the foreman's only finding the `unreplied` copy
    ([{"external:octo": [EXTERNAL], "foreman": []}, {"foreman": [found("foreman-2-1", UNREPLIED)]}], (),
     "Reviewers", ("foreman", "head"), "quiet rounds", "2"),
])
def test_copies_count_once_in_the_reviewers_and_units_tables(world, rounds, rulings, table_name, row, column, value):
  c, _, _ = two_units(world)
  head_rounds(c, rounds, rulings)
  tables = keyed(report_of(world, c), table_name, len(row))
  assert tables[row][column] == value


def test_a_settled_copy_settles_no_unrelated_finding_of_the_same_id(world):
  # ids repeat across a unit's head cycles: cycle 2's own `ext-1` (another claim) is not the finding cycle 1's copy settled
  c, _, _ = two_units(world)
  head_rounds(c, [{"external:octo": [EXTERNAL]}, {"foreman": [found("foreman-2-1", UNREPLIED, disposition="fixed")]}])
  reviewed(c, "head-U01-c2", "head", "U01", ["external:octo"], {"external:octo": {"findings": [found("ext-1", "another defect")]}})
  row = keyed(report_of(world, c), "Reviewers", 2)[("external:octo", "head")]
  assert (row["high"], row["fixed"]) == ("2", "1")


def test_a_ruled_copy_rules_no_unrelated_finding_of_the_same_id(world):
  # cycle 1's copy of ext-1 is ruled overruled; cycle 2's own `ext-1` (another claim) is not the finding that ruling reached
  c, _, _ = two_units(world)
  head_rounds(c, [{"external:octo": [EXTERNAL]}, {"foreman": [found("foreman-2-1", UNREPLIED)]}], ("foreman-2-1 finding overruled — not a defect",))
  reviewed(c, "head-U01-c2", "head", "U01", ["external:octo"], {"external:octo": {"findings": [found("ext-1", "another defect")]}})
  row = keyed(report_of(world, c), "Reviewers", 2)[("external:octo", "head")]
  assert (row["high"], row["overruled"]) == ("2", "1")


def test_a_claim_that_reads_like_a_copy_is_a_finding_unless_a_foreman_copy_of_a_known_finding(world):
  # a reviewer's own finding whose claim begins `contested state:` copies nothing: no finding `state` exists, and it is no foreman's
  c, _, _ = two_units(world)
  head_rounds(c, [{"change-review": [found("change-review-1-1", "contested state: retries never terminate")]}])
  report = report_of(world, c)
  row = keyed(report, "Reviewers", 2)[("change-review", "head")]
  assert (row["high"], row["quiet rounds"]) == ("1", "0")
  assert keyed(report, "Units", 1)[("U01",)]["high"] == "1"


def test_a_foreman_claim_naming_no_known_finding_is_a_finding(world):
  # the foreman's own `contested ghost-9-9: …` finding names a finding no round holds: counted as its own
  c, _, _ = two_units(world)
  head_rounds(c, [{"foreman": [found("foreman-1-1", "contested ghost-9-9: out of Scope")]}])
  assert keyed(report_of(world, c), "Reviewers", 2)[("foreman", "head")]["high"] == "1"


def test_a_carried_finding_of_a_later_cycle_takes_no_settlement_from_an_earlier_one(world):
  # head cycle 1: foreman-1-1 and its `contested` copy settled fixed; cycle 2 raises its own foreman-1-1 and carries it: still open
  c, _, _ = two_units(world)
  copy = found("foreman-2-1", "contested foreman-1-1: out of Scope", disposition="fixed")
  head_rounds(c, [{"foreman": [found("foreman-1-1")]}, {"foreman": [copy]}])
  reviewed(c, "head-U01-c2", "head", "U01", ["foreman"], {"foreman": {"findings": [found("foreman-1-1", "another defect")]}})
  jwrite(c.hs.path("reviews", "head-U01-c2", "round-2.json"), {"round": 2, "runcard": "rc", "reviewers": {
      "foreman": {"findings": [found("foreman-1-1", "another defect", carried_from=1)]}}})
  row = keyed(report_of(world, c), "Reviewers", 2)[("foreman", "head")]
  assert (row["high"], row["fixed"]) == ("2", "1")


def test_a_copy_of_a_later_cycle_follows_no_link_of_an_earlier_one(world):
  # cycle 1's `foreman-2-1` was an `unreplied` copy of external ext-1; cycle 2's own `foreman-2-1` is a finding, and its `contested` copy settled fixed
  c, _, _ = two_units(world)
  head_rounds(c, [{"external:octo": [EXTERNAL]}, {"foreman": [found("foreman-2-1", UNREPLIED)]}])
  reviewed(c, "head-U01-c2", "head", "U01", ["foreman"], {"foreman": {"findings": [found("foreman-2-1", "a real defect")]}})
  jwrite(c.hs.path("reviews", "head-U01-c2", "round-2.json"), {"round": 2, "runcard": "rc", "reviewers": {
      "foreman": {"findings": [found("foreman-3-1", "contested foreman-2-1: out of Scope", disposition="fixed")]}}})
  rows = keyed(report_of(world, c), "Reviewers", 2)
  assert (rows[("foreman", "head")]["fixed"], rows[("external:octo", "head")]["fixed"]) == ("1", "0")


def test_not_run_round_is_no_head_round(world):
  # U01's head round 1 ran; round 2's foreman entry is `prepared` and its reviewers hold only `review record --not-run` records
  c, _, _ = two_units(world)
  jwrite(c.hs.path("foreman", "U01"), {"dispatch_id": None, "decisions": [], "rulings": [], "rounds": [
      {"round": 1, "phase": "posted", "outcome": "posted"}, {"round": 2, "phase": "prepared"}]})
  reviewed(c, "head-U01-c1", "head", "U01", ["design", "zoom-out"], {"design": {"findings": []}, "zoom-out": {"findings": []}})
  jwrite(c.hs.path("reviews", "head-U01-c1", "round-2.json"), {"round": 2, "runcard": "rc", "reviewers": {
      "design": {"findings": [], "not_run": True}, "zoom-out": {"findings": [], "not_run": True}}})
  report = report_of(world, c)
  assert table(report, "Units")["U01"]["head rounds"] == "1"
  assert table(report, "Plan against actual")["U01"]["head rounds"] == "1"


def lesson_rows(world, c):
  """The Lessons table's rows, each as its cells, in order."""
  body = report_of(world, c).split("## Lessons\n", 1)[1].split("\n## ", 1)[0]
  return [[cell.strip() for cell in line.strip().strip("|").split(" | ")] for line in body.splitlines() if line.startswith("|")][2:]


@pytest.mark.parametrize("ruling", ["stop — over budget", "redesign — the seam is wrong"])
def test_cap_ruling_stop_or_redesign_is_a_lesson(world, ruling):
  # U01's foreman decision q1 with source `review head-U01-c1 cap`, ruled `ruling`
  c, _, _ = two_units(world)
  jwrite(c.hs.path("foreman", "U01"), {
      "dispatch_id": None, "rounds": [], "stopped": None, "rulings": [{"decision": "q1", "ruling": ruling, "by": "owner"}],
      "decisions": [{"id": "q1", "point": 2, "source": "review head-U01-c1 cap", "asked_at": "2026-11-16T00:00:00Z"}]})
  lessons = lesson_rows(world, c)
  assert [r[:3] for r in lessons if r[0] == "unit stopped at the cap"] == [["unit stopped at the cap", "U01", "foreman/U01.json q1"]]


def open_spec_cycle(c, n, extra, disposition="fix-design"):
  """Spec cycle `n` of the handoff's spec, its `review.json` holding `extra`, its round 1 holding one finding settled `disposition`."""
  from test_review import SLUG
  rid = f"spec-{SLUG}-c{n}"
  jwrite(c.hs.path("reviews", rid, "review.json"), {"kind": "spec", "artifact": str(c.spec), "cycle": n, "reviewers": ["design"],
                                                    "runcard": "rc", "converged": "no", "rulings": [], **extra})
  jwrite(c.hs.path("reviews", rid, "round-1.json"), {"round": 1, "runcard": "rc", "reviewers": {
      "design": {"findings": [found("design-1-1", "the range is wrong", disposition=disposition)]}}})


@pytest.mark.parametrize("review_json, rows", [
    ({"respec": "R1", "handoff_id": "<this handoff>"}, 1),     # this handoff's respec cycle, never approved
    ({"respec": "R1", "handoff_id": "<another handoff>"}, 0),
    ({}, 0),                                                    # a plain spec cycle opened after the last entry
])
def test_unapproved_respec_cycle_findings_are_kept(world, review_json, rows):
  # spec cycle c3 opened after the handoff's last approval entry (c2) and in no entry
  from test_review import SLUG
  from test_u43 import jread
  c, _, _ = two_units(world)
  path = c.root / "approvals" / f"{SLUG}.json"
  record = jread(path)
  jwrite(path, {**record, "entries": [{**record["entries"][-1], "review": f"spec-{SLUG}-c2"}]})
  open_spec_cycle(c, 3, {k: c.hid if v == "<this handoff>" else v for k, v in review_json.items()})
  lessons = lesson_rows(world, c)
  assert len([r for r in lessons if r[0] == "fix-design finding"]) == rows


@pytest.mark.parametrize("reply", ["**Reply foreman-2-1:** fixed", "**Reply change-review-1-3:** contested — out of Scope"])
def test_reply_fid_ends_the_respec_evidence(world, reply):
  # the deviation comment's body, read for the respec's Lessons row
  import json
  from test_u87 import respec_world
  body = f"**Deviation (spec):** docs/specs/x.md:12 says 3\n\n`pytest -k retry` fails\n\n{reply}\n"
  c = respec_world(world, lambda args: (0, json.dumps({"id": 901, "body": body}), ""))
  lessons = lesson_rows(world, c)
  fact = " | ".join(next(r for r in lessons if r[0] == "respec"))
  assert "says 3 `pytest -k retry` fails" in fact and reply not in fact


def test_next_answer_refuses_an_empty_answer(world):
  # chain/<handoff>.json holds an unanswered wait; the owner runs `superegm next answer --handoff <id> --answer ''`
  from test_u43 import jread
  from test_u78 import chain_world, wait
  c = chain_world(world)
  c.plan("U01")
  wait(world, c, "plan", "split U01?")
  waits_dir = c.hs.path("file", "waits")
  code, out = world.run("next", "answer", "--handoff", c.hid, "--answer", "")
  chain_after = jread(c.root / "chain" / f"{c.hid}.json")
  assert code == 1, out
  assert out.strip().startswith("superegm: next answer: ") and len(out.strip().splitlines()) == 1, out  # the helper's error prefix, then one line
  assert "answer" not in chain_after and not list(waits_dir.glob("*.answer.*"))
