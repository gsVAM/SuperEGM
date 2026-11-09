# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U35

"""U35: accept below the cap (`review rule --ruling accept --owner` on an acceptable round, its refusals)."""

import pytest

from test_review import opened, record, head_round, F, A, rule, status, rjson, hstore, move
from test_wave import question


def recorded(world, rid, cid, lines, n=1):
  """Round `n`: every reviewer of the review and every other id prefix among `lines` records its own lines;
  a head's after its posted `rounds[]` entry and with the sha."""
  head = rjson(world, rid)["kind"] == "head"
  prefix = lambda line: line.split(" | ")[0].rsplit("-", 2)[0]
  ids = list(rjson(world, rid)["reviewers"])
  ids += [p for p in dict.fromkeys(prefix(line) for line in lines) if p not in ids]
  if head:
    head_round(world, n, "posted", cid)
  for reviewer in ids:
    code, out = record(world, rid, n, reviewer, [line for line in lines if prefix(line) == reviewer], cid,
                       sha=A if head else None)
    assert code == 0, out


def pending(world, cid, unit, rid):
  """A point-1 decision open on the head's unit, its source this review's round 1."""
  code, out = world.run("decision", "open", "--unit", unit, "--point", "1", "--question", question(world),
                        "--source", f"review {rid} round 1", "--runcard", cid)
  assert code == 0, out


def test_accept_below_the_cap_converges_by_ruling(world):
  spec, cid, rid = opened(world, "plan")
  recorded(world, rid, cid, [F("readiness", 1, 1, "medium"), F("readiness", 1, 2, "medium"), F("proportion", 1, 1, "low")])
  assert status(world, rid, cid)[0] == 3
  code, out = rule(world, rid, "accept", cid)
  assert (code, out.strip()) == (0, "ruling R1 accept")
  review = rjson(world, rid)
  assert (review["converged"], review["converged_round"], review["rulings"][0]["by"]) == ("by ruling R1", 1, "owner")
  assert all(f["disposition"] is None for f in rjson(world, rid, "round-1.json")["reviewers"]["readiness"]["findings"])
  assert "accepted before the cap by the owner (2 medium, 1 low)" in hstore(world).path("journal").read_text(encoding="utf-8")
  assert status(world, rid, cid)[0] == 0


@pytest.mark.parametrize("kind, findings, extra, expect", [
  ("plan", [F("readiness", 1, 1, "high"), F("readiness", 1, 2, "medium")], (), "review rule: accept refused: high readiness-1-1"),
  ("plan", [F("readiness", 1, 1, "medium", "yes"), F("readiness", 1, 2, "medium")], (), "review rule: accept refused: regression readiness-1-1"),
  ("head", [F("external:devin[bot]", 1, 1, "medium")], (), "review rule: accept refused: external external:devin[bot]-1-1"),
  ("head", [F("change-review", 1, 1, "medium")], ("decision",), "review rule: accept refused: decision q1"),
  ("head", [F("change-review", 1, 1, "medium")], (), "review rule: accept on a head needs --decision"),
  ("integrate", [F("design", 1, 1, "medium")], (), "review rule: accept refused: kind integrate"),
  ("plan", [F("readiness", 1, 1, "medium")], ("judges",), "review rule: accept refused: judges"),
  ("plan", [F("readiness", 1, 1, "medium")], ("moved",), "review rule: the reviewed bytes moved: continue or stop"),
  ("plan", [F("readiness", 1, 1, "low")], (), "review rule: not at the cap"),
  ("plan", [F("readiness", 1, 1, "low")], ("moved",), "review rule: accept refused: no medium to accept"),
  ("head", [F("change-review", 1, 1, "medium")], ("cap",), "review rule: accept is refused on a head")])
def test_accept_below_the_cap_is_refused_with_its_blockers(world, kind, findings, extra, expect):
  spec, cid, rid = opened(world, kind)
  for n in range(1, 6 if "cap" in extra else 2):
    recorded(world, rid, cid, [F("change-review", n, 1)] if "cap" in extra else findings, n)
  "decision" in extra and pending(world, cid, "U07", rid)
  "moved" in extra and move(world, kind, spec)
  code, out = rule(world, rid, "accept", cid, by=("--judges", "j1") if "judges" in extra else ("--owner",))
  assert code == 1 and expect in out and rjson(world, rid)["rulings"] == []
