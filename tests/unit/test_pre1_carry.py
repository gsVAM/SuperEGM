# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: P6 (1.2.1-pre.1), the foreman's carry and contests (spec section 6.5, "The foreman").

"""P6: a finding waiting on a ruling is posted once. `collect` carries a builder contest with no ruling on a finding
it does not derive, and every derived finding whose check still fails with the same claim and location, from the
previous posted round only, under the same id with `carried_from`; `review post` leaves carried findings out; a
`contested` reply counts by membership in the previous posted round's record; `review settle --finding` settles the
newest round holding the id. Fixtures: test_foreman's `seed`, `prepared`, `open_head_review`, `record`."""
import json

import pytest

from superegm import atomic_write
from superegm import review as review_mod
from test_foreman import POSTED_R1, PR, R2, UNIT, builder_token, c, open_head_review, prepared, record, seed  # noqa: F401  builder_token: autouse

CI = "foreman-1-1 | high | ci | regression: no | CI not green on this head: ci red (tests)\n"
SCOPE = "foreman-1-2 | high | src/other.py | regression: no | changed path outside Scope paths\n"
CR = "change-review-1-1 | high | src/hooks.py:1 | regression: no | no hook\n"
OTHER = [("test(S1): hook", "tests/unit/test_hooks.py"), ("feat(S1): hook", "src/hooks.py"), ("feat(S1): more", "src/other.py")]
SCOPE_F = {"id": "foreman-1-2", "severity": "high", "location": "src/other.py", "regression": "no",
           "claim": "changed path outside Scope paths", "disposition": None, "ruling": None}


def patch_round(st, rid, n, change):
  path = st.path("reviews", rid, f"round-{n}.json")
  data = json.loads(path.read_text(encoding="utf-8"))
  change(data)
  atomic_write(path, data)


def build(world, tmp_path, monkeypatch, records, patches=(), comments=None, commits=None):
  """Rounds 1..len(records) posted (each a reviewer → findings text), `patches` applied to their round files, then
  the next round prepared and its change-review record written: `(w, n)`."""
  n = len(records) + 1
  rounds = [POSTED_R1] + [{**R2, "round": i, "launch": i, "dispatch_id": f"d{i}"} for i in range(2, n)]
  kw = dict(rounds=rounds, launches=[{"round": i, "status": "exited 0"} for i in range(1, n + 1)], comments=comments or {})
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, records[0])
  for i, findings in enumerate(records[1:], 2):
    record(world, st0, rid, i, "0" * 40, card0, findings)
  for i, change in patches:
    patch_round(st0, rid, i, change)
  w = prepared(world, tmp_path, monkeypatch, **({"commits": commits} if commits else {}), **kw)
  record(world, w.st, w.rid, n, w.head, w.child, {"change-review": ""})
  return w, n


def collected(world, w, n, count):
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"collected: {count} foreman findings"), out
  lines = (w.dir / f"r{n}/foreman.findings").read_text(encoding="utf-8").splitlines()
  return lines, json.loads(w.st.path("reviews", w.rid, f"round-{n}.json").read_text(encoding="utf-8"))


def foreman_of(rnd):
  return rnd["reviewers"]["foreman"]["findings"]


CONTEST = "foreman-2-1 | high | pr #70 comment 14 | regression: no | contested change-review-1-1: the test covers it\n"
BC = [{"fid": "foreman-2-1", "reason": "the test covers it"}]


@pytest.mark.parametrize("case", ["unruled", "ruled-on-the-contest", "ruled-on-the-finding"])
def test_an_unruled_builder_contest_is_carried_under_its_id_and_not_posted_again(world, tmp_path, monkeypatch, case):
  rulings = {"unruled": {}, "ruled-on-the-contest": {2: [c(15, "owner", "**Ruling:** foreman-2-1 finding overruled — fine")]},
             "ruled-on-the-finding": {2: [c(15, "owner", "**Ruling:** change-review-1-1 finding overruled — fine")]}}[case]
  w, n = build(world, tmp_path, monkeypatch, [{"change-review": CR, "foreman": ""}, {"change-review": "", "foreman": CONTEST}],
               patches=[(2, lambda r: r.update(builder_contested=BC))], comments=rulings)
  lines, rnd = collected(world, w, n, 0)
  assert lines == []
  if case != "unruled":  # a ruling exists: not carried again
    assert foreman_of(rnd) == [] and rnd["builder_contested"] == []
    return
  copy = foreman_of(rnd)
  assert [(f["id"], f["claim"], f["carried_from"], f["disposition"]) for f in copy] == [
      ("foreman-2-1", "contested change-review-1-1: the test covers it", 2, None)]
  assert rnd["builder_contested"] == BC
  assert "foreman-2-1" not in review_mod.render_comment(rnd, w.head, "ci green", None)
  entry = dict(json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][-1])
  # counts against convergence like any other, and the word reads the copied entry
  assert review_mod.count_posted(w.st, UNIT, entry, "2026-11-03T00:00:00Z", w.rid, w.child) == "contested: foreman-2-1"


def test_a_contest_of_a_derived_finding_is_not_carried_as_a_contest(world, tmp_path, monkeypatch):
  """The derived finding itself is carried while its check fails; the contest of it is not."""
  contest = "foreman-2-1 | high | pr #70 comment 14 | regression: no | contested foreman-1-2: it is needed\n"
  def round_2(r):
    r.update(builder_contested=[{"fid": "foreman-2-1", "reason": "it is needed"}])
    r["reviewers"]["foreman"]["findings"].append({**SCOPE_F, "carried_from": 1})
  w, n = build(world, tmp_path, monkeypatch, [{"change-review": "", "foreman": CI + SCOPE}, {"change-review": "", "foreman": contest}],
               patches=[(2, round_2)], commits=OTHER)
  lines, rnd = collected(world, w, n, 0)
  assert lines == [] and foreman_of(rnd) == [{**SCOPE_F, "carried_from": 2}] and rnd["builder_contested"] == []


def test_two_alike_derived_findings_keep_their_two_ids(world, tmp_path, monkeypatch):
  twice = {70: [c(14, "builder-bot", "**Deviation (interface):** a\n**Deviation (interface):** b")]}
  alike = "".join(f"foreman-1-{k} | high | pr #70 comment 14 | regression: no | deviation (interface) unruled\n" for k in (1, 2))
  w, n = build(world, tmp_path, monkeypatch, [{"change-review": "", "foreman": alike}], comments=twice)
  lines, rnd = collected(world, w, n, 0)
  assert [(f["id"], f["carried_from"]) for f in foreman_of(rnd)] == [("foreman-1-1", 1), ("foreman-1-2", 1)]


EXT = "external:alice-1-1 | high | src/hooks.py:3 at 0000000 | regression: no | the hook never fires\n"
COPY = "foreman-2-1 | high | src/hooks.py:3 at 0000000 | regression: no | unreplied external:alice-1-1: the hook never fires\n"


@pytest.mark.parametrize("at, carried", [("2026-11-02T13:00:00Z", True), ("2026-11-02T16:00:00Z", False)])
def test_a_reply_in_this_window_to_a_carried_copy_counts_after_its_first_post(world, tmp_path, monkeypatch, at, carried):
  """Round 2 (posted 15:00) holds foreman-2-1; round 3's own comments hold `**Reply foreman-2-1:** fixed`: after the
  post it ends the carry, before it answers nothing and foreman-2-1 is carried under its id."""
  r2 = {**R2, "posted_at": "2026-11-02T15:00:00Z"}
  kw = dict(rounds=[POSTED_R1, r2], launches=[{"round": i, "status": "exited 0"} for i in (1, 2, 3)],
            comments={70: [c(14, "builder-bot", "**Reply foreman-2-1:** fixed", at=at)]})
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", "external:alice": EXT})
  record(world, st0, rid, 2, "0" * 40, card0, {"change-review": "", "foreman": COPY})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  record(world, w.st, w.rid, 3, w.head, w.child, {"change-review": ""})
  lines, rnd = collected(world, w, 3, 0)
  assert [(f["id"], f["carried_from"]) for f in foreman_of(rnd)] == ([("foreman-2-1", 2)] if carried else [])


@pytest.mark.parametrize("case", ["still-fails", "reverted", "moved"])
def test_a_derived_finding_reuses_its_id_only_while_its_check_still_fails(world, tmp_path, monkeypatch, case):
  scope = SCOPE.replace("src/other.py", "src/else.py") if case == "moved" else SCOPE
  w, n = build(world, tmp_path, monkeypatch, [{"change-review": CR, "foreman": CI + scope}],
               commits=None if case == "reverted" else OTHER)
  if case == "moved":  # another location: a new finding, posted
    lines, rnd = collected(world, w, n, 1)
    assert lines == ["foreman-2-1 | high | src/other.py | regression: no | changed path outside Scope paths"]
    assert "carried_from" not in foreman_of(rnd)[0]
    return
  lines, rnd = collected(world, w, n, 0)
  assert lines == []  # neither the CI finding (green now) nor a panel finding is carried
  assert foreman_of(rnd) == ([{**SCOPE_F, "carried_from": 1}] if case == "still-fails" else [])
  assert "change-review-1-1" not in json.dumps(rnd)
  assert "foreman-1-2" not in review_mod.render_comment(rnd, w.head, "ci green", None)


def test_carries_come_from_the_previous_round_only(world, tmp_path, monkeypatch):
  w, n = build(world, tmp_path, monkeypatch, [{"change-review": "", "foreman": CI + SCOPE}, {"change-review": "", "foreman": ""}],
               commits=OTHER)
  lines, _ = collected(world, w, n, 1)
  assert lines == ["foreman-3-1 | high | src/other.py | regression: no | changed path outside Scope paths"]


def test_a_contested_reply_counts_by_membership_in_the_previous_posted_record(world, tmp_path, monkeypatch):
  """foreman-1-2 carried into round 2 is open there, so its contest counts in round 3 whatever round its id names;
  change-review-2-9 names round 2 but no record holds it, so it contests nothing."""
  replies = {70: [c(14, "builder-bot", "**Reply foreman-1-2:** contested — needed for the hook"),
                  c(15, "builder-bot", "**Reply change-review-2-9:** contested — no such finding")]}
  w, n = build(world, tmp_path, monkeypatch, [{"change-review": "", "foreman": CI + SCOPE}, {"change-review": "", "foreman": ""}],
               patches=[(2, lambda r: r["reviewers"]["foreman"]["findings"].append({**SCOPE_F, "carried_from": 1}))],
               comments=replies)
  lines, rnd = collected(world, w, n, 1)
  assert lines == ["foreman-3-1 | high | pr #70 comment 14 | regression: no | contested foreman-1-2: needed for the hook"]
  assert rnd["builder_contested"] == [{"fid": "foreman-3-1", "reason": "needed for the hook"}]


def test_settle_finding_settles_the_newest_round_holding_it(world):
  st, card, _ = seed(world, rounds=[POSTED_R1, R2], launches=[{"round": i, "status": "exited 0"} for i in (1, 2)])
  rid = open_head_review(world, st, card, "0" * 40, {"change-review": "", "foreman": CI + SCOPE})
  record(world, st, rid, 2, "0" * 40, card, {"change-review": "", "foreman": ""})
  patch_round(st, rid, 2, lambda r: r["reviewers"]["foreman"]["findings"].append({**SCOPE_F, "carried_from": 1}))
  assert review_mod.locate_finding(st, rid, "foreman-1-2")[0] == 2
  assert world.run("review", "settle", "--review", rid, "--finding", "foreman-1-2", "--disposition", "fixed", "--runcard", card)[0] == 0
  held = lambda m: next(f for f in foreman_of(review_mod.load_round(st, rid, m)) if f["id"] == "foreman-1-2")["disposition"]
  assert (held(1), held(2)) == (None, "fixed")


def test_the_outcome_word_counts_carried_copies():
  delta = {"id": "foreman-1-3", "severity": "high", "location": "tests/a.py:3", "regression": "no",
           "claim": "test-delta: tests/a.py:3 removed", "disposition": None, "ruling": None, "carried_from": 1}
  rnd = {"round": 2, "reviewers": {"foreman": {"findings": [delta]}}, "builder_contested": []}
  assert review_mod.owner_only_fids(rnd) == ["foreman-1-3"]
  assert review_mod.outcome_word(3, review_mod.contested_fids(rnd), review_mod.owner_only_fids(rnd)) == "owner: foreman-1-3"
  assert "foreman-1-3" not in review_mod.render_comment(rnd, "a" * 40, "ci green", None)
