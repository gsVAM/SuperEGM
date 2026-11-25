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
