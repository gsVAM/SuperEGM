# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U35

"""U35: accept below the cap (`review rule --ruling accept --owner` on an acceptable round, its refusals)."""

import json
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


def test_a_settled_regression_still_bars_the_accept_below_the_cap(world):
  """PR #105 round 1 (astra-1-4, change-review-1-1): `regressions_of` counts a blocking `regression: yes` whatever
  its disposition, so one settled `declined` keeps the round unacceptable."""
  from test_review import settle
  spec, cid, rid = opened(world, "plan")
  recorded(world, rid, cid, [F("readiness", 1, 1, "medium", "yes"), F("readiness", 1, 2, "medium")])
  assert settle(world, rid, "readiness-1-1", "declined", cid, "--owner")[0] == 0
  assert "acceptable:" not in world.run("review", "status", "--review", rid, "--runcard", cid)[1]
  code, out = rule(world, rid, "accept", cid)
  assert code == 1 and "review rule: accept refused: regression readiness-1-1" in out and rjson(world, rid)["rulings"] == []


def test_an_accept_below_the_cap_lapses_on_a_later_round(world):
  """PR #105 round 1 (astra-1-7): an early accept holds its round alone: a later completed round (a set finding
  recorded into a converged unit's next round) puts the review back to open."""
  spec, cid, rid = opened(world, "plan")
  recorded(world, rid, cid, [F("readiness", 1, 1, "medium")])
  assert rule(world, rid, "accept", cid)[0] == 0 and status(world, rid, cid)[0] == 0
  recorded(world, rid, cid, [F("readiness", 2, 1, "medium")], n=2)
  assert status(world, rid, cid)[0] == 3


def test_a_head_accept_lapses_on_an_ingested_external_high(world):
  """PR #105 round 1 (astra-1-2): an external high recorded into the accepted round after the accept bars it: the
  head review is open again, so `review ingest` rewrites the round's `clean`."""
  from test_wave import fifth_point_open
  s, card, rid = fifth_point_open(world)
  assert rule_fifth(world, card)[0] == 0 and status(world, rid, card)[0] == 0
  code, out = record(world, rid, 1, "external:devin[bot]", [F("external:devin[bot]", 1, 1, "high")], card, sha="a" * 40)
  assert code == 0, out
  assert status(world, rid, card)[0] == 3


def test_a_point_one_decision_stays_open_until_each_contested_finding_is_ruled(world, monkeypatch):
  """PR #105 round 1 (astra-1-5): point 1 takes one ruling per contested finding, so its decision blocks the accept
  until the last one is ruled."""
  from superegm import review
  findings = [{"id": f"foreman-1-{i}", "disposition": None} for i in (1, 2)]
  rnd = {"reviewers": {"foreman": {"findings": findings}}, "builder_contested": [{"fid": "foreman-1-1"}, {"fid": "foreman-1-2"}]}
  monkeypatch.setattr(review, "load_round", lambda st, rid, n: rnd)
  d = {"id": "q1", "point": 1, "source": "review head-U01-c1 round 1"}
  one = {"decisions": [d], "rulings": [{"decision": "q1", "ruling": "foreman-1-1 finding upheld"}]}
  both = {"decisions": [d], "rulings": one["rulings"] + [{"decision": "q1", "ruling": "foreman-1-2 finding overruled"}]}
  assert review.point_one_open(None, one, d) and not review.point_one_open(None, both, d)


def head_rulings(s, rid):
  import json
  return json.loads(s.path("reviews", rid, "review.json").read_text(encoding="utf-8"))["rulings"]


def rule_fifth(world, card):
  return world.run("decision", "rule", "--unit", "U01", "--decision", "q1", "--ruling", "accept — fine", "--by", "owner", "--runcard", card)


def test_a_head_accept_is_refused_once_the_pull_request_moved(world):
  """PR #105 round 1 (astra-1-1, change-review-1-5): the point-5 accept binds the head its round reviewed."""
  import json
  from test_wave import fifth_point_open, foreman_of
  s, card, rid = fifth_point_open(world)
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"]["U01"]["head"] = "b" * 40
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  code, out = rule_fifth(world, card)
  assert code == 1 and "review rule: the reviewed head moved: revise" in out
  assert foreman_of(s, "U01")["rulings"] == [] and head_rulings(s, rid) == []


def test_a_head_accept_whose_post_failed_reruns(world, monkeypatch):
  """PR #105 round 1 (astra-1-3, change-review-1-2, codebase-details-1-1): the accept is applied before the post;
  a failed post leaves the decision pending and the same call completes it, the accept given once."""
  import superegm
  from test_wave import fifth_point_open, foreman_of
  s, card, rid = fifth_point_open(world)
  real = superegm.gh

  def failing(args, *a, **kw):
    if args[:2] == ["issue", "comment"]:
      raise superegm.GhError(args, 1, "", "HTTP 502")
    return real(args, *a, **kw)
  monkeypatch.setattr(superegm, "gh", failing)
  with pytest.raises(superegm.GhError):
    rule_fifth(world, card)
  assert foreman_of(s, "U01")["rulings"] == []
  monkeypatch.setattr(superegm, "gh", real)
  assert rule_fifth(world, card)[0] == 0
  f = foreman_of(s, "U01")
  assert [r["decision"] for r in f["rulings"]] == ["q1"] and f["rounds"][-1]["outcome"] == "clean"
  assert [r["ruling"] for r in head_rulings(s, rid)] == ["accept"]
  assert s.path("journal").read_text(encoding="utf-8").count("U01 awaiting merge") == 1


def test_a_lapsed_accept_stays_lapsed_at_the_cap(world):
  """PR #105 round 2 (astra-2-1, change-review-2-1, codebase-details-2-1): an early accept a later round lapsed never
  comes back: at the cap the landed point-2 question stands, `continue` is ruled, and the lapse is journaled."""
  spec, cid, rid = opened(world, "plan")
  recorded(world, rid, cid, [F("readiness", 1, 1, "medium")])
  assert rule(world, rid, "accept", cid)[0] == 0
  for n in range(2, 6):
    recorded(world, rid, cid, [F("readiness", n, 1, "high")], n)
  assert status(world, rid, cid)[0] == 2
  assert rule(world, rid, "continue", cid)[0] == 0
  assert "R1 accept lapsed" in hstore(world).path("journal").read_text(encoding="utf-8")


def test_a_lapsed_accept_is_not_the_verdict_of_a_later_clean_round(world):
  """PR #105 round 2 (codebase-details-2-2): a later clean round converges by itself, never by the lapsed accept."""
  spec, cid, rid = opened(world, "plan")
  recorded(world, rid, cid, [F("readiness", 1, 1, "medium")])
  assert rule(world, rid, "accept", cid)[0] == 0
  recorded(world, rid, cid, [], n=2)
  assert status(world, rid, cid)[0] == 0
  assert "converged yes" in world.run("review", "status", "--review", rid, "--runcard", cid)[1]
  assert (rjson(world, rid)["converged"], rjson(world, rid)["converged_round"]) == ("yes", 2)


def moved_snapshot(s, head):
  import json
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"]["U01"]["head"] = head
  s.path("state").write_text(json.dumps(state), encoding="utf-8")


def test_review_status_prints_no_acceptable_line_on_a_moved_head(world):
  """PR #105 round 2 (astra-2-4, codebase-details-2-4): the line is printed at the reviewed head alone."""
  from test_wave import fifth_point_open
  s, card, rid = fifth_point_open(world)
  assert "acceptable: yes (1 medium, 0 low)" in world.run("review", "status", "--review", rid, "--runcard", card)[1]
  moved_snapshot(s, "b" * 40)
  assert "acceptable:" not in world.run("review", "status", "--review", rid, "--runcard", card)[1]


def test_a_head_accept_reads_the_pull_requests_head_afresh(world):
  """PR #105 round 2 (astra-2-2): the saved snapshot still says the reviewed head, the pull request has moved."""
  from conftest import make_pr
  from test_wave import fifth_point_open, foreman_of
  s, card, rid = fifth_point_open(world)
  make_pr(world.gh, 70, "b" * 40)
  code, out = rule_fifth(world, card)
  assert code == 1 and "review rule: the reviewed head moved: revise" in out
  assert foreman_of(s, "U01")["rulings"] == [] and head_rulings(s, rid) == []


def failed_accept(world, monkeypatch, card):
  import superegm
  real = superegm.gh

  def failing(args, *a, **kw):
    if args[:2] == ["issue", "comment"]:
      raise superegm.GhError(args, 1, "", "HTTP 502")
    return real(args, *a, **kw)
  monkeypatch.setattr(superegm, "gh", failing)
  with pytest.raises(superegm.GhError):
    rule_fifth(world, card)
  monkeypatch.setattr(superegm, "gh", real)


def test_a_rerun_accept_is_refused_once_the_pull_request_moved(world, monkeypatch):
  """PR #105 round 2 (astra-2-3): the accept a failed post left given is checked against the head again on the rerun."""
  from conftest import make_pr
  from test_wave import fifth_point_open, foreman_of
  s, card, rid = fifth_point_open(world)
  failed_accept(world, monkeypatch, card)
  make_pr(world.gh, 70, "b" * 40)
  code, out = rule_fifth(world, card)
  assert code == 1 and "review rule: the reviewed head moved: revise" in out and foreman_of(s, "U01")["rulings"] == []


def test_a_revise_after_a_failed_accept_withdraws_the_accept(world, monkeypatch):
  """PR #105 round 2 (change-review-2-2): the owner's rerun with `revise` lapses the accept the failed call gave."""
  from test_wave import fifth_point_open, foreman_of
  s, card, rid = fifth_point_open(world)
  failed_accept(world, monkeypatch, card)
  code, out = world.run("decision", "rule", "--unit", "U01", "--decision", "q1", "--ruling", "revise — once more",
                        "--by", "owner", "--runcard", card)
  assert code == 0, out
  f = foreman_of(s, "U01")
  assert [r["decision"] for r in f["rulings"]] == ["q1"] and f["rounds"][-1]["outcome"] == "revise"
  assert status(world, rid, card)[0] == 3
  assert json.loads(s.path("reviews", rid, "review.json").read_text(encoding="utf-8"))["converged"] == "no"
  assert "R1 accept lapsed" in s.path("journal").read_text(encoding="utf-8")


def test_a_fix_design_settle_lapses_an_accept_below_the_cap(world):
  """PR #105 round 3 (astra-3-1): a `fix-design` on the accepted round stores the open verdict, so the gate never
  reads the accept as a converged review; the lapse is journaled."""
  spec, cid, rid = opened(world, "plan")
  recorded(world, rid, cid, [F("readiness", 1, 1, "medium")])
  assert rule(world, rid, "accept", cid)[0] == 0
  code, out = world.run("review", "settle", "--review", rid, "--finding", "readiness-1-1", "--disposition", "fix-design", "--runcard", cid)
  assert code == 0, out
  assert status(world, rid, cid)[0] == 4
  assert (rjson(world, rid)["converged"], rjson(world, rid)["converged_round"]) == ("no", None)
  assert "R1 accept lapsed" in hstore(world).path("journal").read_text(encoding="utf-8")


def test_a_rerun_accept_refused_on_a_moved_head_withdraws_the_accept(world, monkeypatch):
  """PR #105 round 3 (astra-3-2): the accept a failed post left given is withdrawn when the rerun is refused: the
  review is open again, the round's word is `revise`, and no merge is advertised."""
  from conftest import make_pr
  from test_wave import fifth_point_open, foreman_of
  s, card, rid = fifth_point_open(world)
  failed_accept(world, monkeypatch, card)
  make_pr(world.gh, 70, "b" * 40)
  assert rule_fifth(world, card)[0] == 1
  f = foreman_of(s, "U01")
  assert f["rulings"] == [] and f["rounds"][-1]["outcome"] == "revise"
  assert status(world, rid, card)[0] == 3
  assert json.loads(s.path("reviews", rid, "review.json").read_text(encoding="utf-8"))["converged"] == "no"
  assert "R1 accept lapsed" in s.path("journal").read_text(encoding="utf-8")


def test_a_posted_head_round_journals_the_lapse_of_an_accept(world):
  """PR #105 round 3 (codebase-details-3-1): a later head round posted after a point-5 accept stores its verdict, so
  the accept's lapse is journaled and the review converges by the later round."""
  from superegm import review
  from superegm import atomic_write
  from test_wave import fifth_point_open, foreman_of
  s, card, rid = fifth_point_open(world)
  assert rule_fifth(world, card)[0] == 0
  f = foreman_of(s, "U01")
  f["rounds"].append({"round": 2, "phase": "launched", "launch": 2, "head": "a" * 40, "outcome": None})
  atomic_write(s.path("foreman", "U01"), f)
  assert record(world, rid, 2, "change-review", [], card, sha="a" * 40)[0] == 0
  entry = dict(foreman_of(s, "U01")["rounds"][-1])
  assert review.count_posted(s, "U01", entry, "2026-11-09T00:00:00Z", rid, card) == "clean"
  stored = json.loads(s.path("reviews", rid, "review.json").read_text(encoding="utf-8"))
  assert (stored["converged"], stored["converged_round"]) == ("yes", 2)
  assert "R1 accept lapsed" in s.path("journal").read_text(encoding="utf-8")
