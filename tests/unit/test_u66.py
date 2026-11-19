# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U66

"""U66 (spec sections 6.1 and 4.2): the foreman round of a launch with `merge: "alone"` carries `merge: true` and is
left out of the review round cap's count, and after a proceed the merge launch's head is refused dispatch so the
owner proceeds again. Fixtures: conftest's `world` and test_foreman's `seed`."""

import json

import pytest

from test_foreman import UNIT, dispatched


@pytest.mark.parametrize("launch_merge, has_key", [("alone", True), ("with-fix", False), (None, False)])
def test_round_carries_merge(world, launch_merge, has_key):
  # the dispatched rounds[] entry is marked only when its launch merged alone
  launch = {"round": 1, "status": "exited 0"} | ({"merge": launch_merge} if launch_merge else {})
  st, card, child, did, _ = dispatched(world, launches=[launch])
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  entry = data["rounds"][-1]
  assert entry["dispatch_id"] == did and entry["launch"] == 1
  assert ("merge" in entry, entry.get("merge")) == (has_key, True if has_key else None)


# ---------------------------------------------------------------- S2: the cap counts the rounds that are not merge rounds

from superegm import atomic_write  # noqa: E402
from superegm import review as review_mod  # noqa: E402
from test_foreman import head_rid, record, seed  # noqa: E402

HEAD = "a" * 40
FINDING = "change-review-{n}-1 | high | tests/unit/test_hooks.py:1 | regression: no | the hook never fires\n"


@pytest.mark.parametrize("cap, rounds, status_exit, outcome", [
  (3, [("revise", None), ("clean", None), ("high", "alone")], 3, "revise"),
  (3, [("revise", None), ("clean", None), ("high", "with-fix")], 2, "cap-reached"),
  (3, [("revise", None), ("revise", None), ("clean", None), ("clean", "alone")], 0, "clean")])
def test_merge_round_and_the_cap(world, cap, rounds, status_exit, outcome):
  # rounds as (result, launch merge); a merge: true round is left out of the completed-round count
  entries = [{"round": n, "runcard": "w", "launch": n, "head": HEAD, "phase": "posted", "dispatch_id": f"d{n}",
              "outcome": "clean" if result == "clean" else "revise", "posted_at": "2026-11-02T12:00:00Z"}
             | ({"merge": True} if merge == "alone" else {}) for n, (result, merge) in enumerate(rounds, 1)]
  launches = [{"round": n, "status": "exited 0"} | ({"merge": merge} if merge else {}) for n, (_, merge) in enumerate(rounds, 1)]
  st, card, _ = seed(world, head=HEAD, rounds=entries, launches=launches)
  assert world.run("review", "open", "--kind", "head", "--artifact", UNIT, "--reviewers", "change-review", "--runcard", card)[0] == 0
  rid = head_rid(st)
  path = st.path("reviews", rid, "review.json")
  atomic_write(path, json.loads(path.read_text(encoding="utf-8")) | {"cap": cap})
  for n, (result, _) in enumerate(rounds, 1):
    record(world, st, rid, n, HEAD, card, {"change-review": "" if result == "clean" else FINDING.format(n=n)})
  code, out = world.run("review", "status", "--review", rid, "--runcard", card)
  assert (code, review_mod.outcome_word(code, [])) == (status_exit, outcome), out


@pytest.mark.parametrize("round2_merge, lapsed", [(True, True), (False, False)])
def test_an_early_accept_next_to_a_merge_round(round2_merge, lapsed):
  # cap 3, accepted on round 3: a merge round 2 is left out of the count, so the accept is below the cap and a later
  # completed round lapses it; with round 2 counted the accept is the cap's and stands
  rounds = [{"round": n, "what_ran": "completed", "reviewers": {}} | ({"merge": True} if n == 2 and round2_merge else {})
            for n in range(1, 5)]
  review = {"converged": "by ruling R1", "converged_round": 3, "cap": 3}
  assert review_mod.early_accept_lapsed(review, {"id": "R1"}, rounds, ["accept"]) is lapsed


# ---------------------------------------------------------------- S3: a proceeded head's merge launch is not reviewed

MERGE_HEAD = "c" * 40


def test_proceeded_merge_head_is_not_reviewed(world):
  # a proceed is final for its head: the merge launch's head waits for a second proceed, not a review
  from superegm import inbox
  from test_foreman import PR
  round1 = {"round": 1, "runcard": "w", "launch": 1, "head": HEAD, "phase": "posted", "dispatch_id": "d1",
            "outcome": "revise", "posted_at": "2026-11-02T12:00:00Z"}
  st, card, _ = seed(world, head=HEAD, rounds=[round1])
  assert world.run("review", "open", "--kind", "head", "--artifact", UNIT, "--reviewers", "change-review", "--runcard", card)[0] == 0
  rid = head_rid(st)
  record(world, st, rid, 1, HEAD, card, {"change-review": FINDING.format(n=1)})
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  state["status"] = {"units": {UNIT: {"pr": PR, "head": HEAD, "ci": "green", "landed": False}}, "ready": [], "landed": []}
  state["units"][UNIT]["launched"] = True
  atomic_write(st.path("state"), state)
  code, out = world.run("review", "rule", "--review", rid, "--ruling", "proceed", "--owner", "--reason", "accepted risk",
                        "--runcard", card)
  assert code == 0, out
  # the conflict: the unit's merge launch 2 ran and moved the head
  atomic_write(st.path("launches", UNIT), {"launches": [{"round": 1, "status": "exited 0"},
                                                        {"round": 2, "status": "exited 0", "merge": "alone"}]})
  world.gh.prs[PR]["headRefOid"] = MERGE_HEAD
  world.gh.check_runs[MERGE_HEAD] = [{"name": "tests", "status": "completed", "conclusion": "success"}]
  world.gh.combined[MERGE_HEAD] = {"state": "success", "statuses": []}
  state["status"]["units"][UNIT]["head"] = MERGE_HEAD
  atomic_write(st.path("state"), state)
  code, out = world.run("foreman", "dispatch", "--unit", UNIT, "--runcard", card)
  assert (code, out) == (1, f"dispatch refused: review {rid} proceeded\n")
  foreman = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  assert [r["round"] for r in foreman["rounds"]] == [1]  # the refusal opened no round
  items = [inbox.line_of(i) for i in inbox.inbox_items(st, [st.handoff_id]) if i["subject"] == UNIT]
  assert any(i["kind"] == "proceed" and i["action"] == "answer in the inbox" and i["fingerprint"].endswith(f"/{MERGE_HEAD}")
             for i in inbox.inbox_items(st, [st.handoff_id]) if i["subject"] == UNIT), items
  assert not any("gh pr merge" in line for line in items), items
  assert unit_state(st, card, foreman) == "waiting proceed"
  # the second proceed names launch 2: the merge is offered on the merge head
  code, out = world.run("review", "rule", "--review", rid, "--ruling", "proceed", "--owner", "--reason", "merge round fine",
                        "--runcard", card)
  assert code == 0, out
  items = [inbox.line_of(i) for i in inbox.inbox_items(st, [st.handoff_id]) if i["subject"] == UNIT]
  assert any(f"gh pr merge {PR} --match-head-commit {MERGE_HEAD}" in line for line in items), items
  # a proceed is final for the head: the second proceed authorizes the merge, not a review of the merge head
  code, out = world.run("foreman", "dispatch", "--unit", UNIT, "--runcard", card)
  assert (code, out) == (1, f"dispatch refused: review {rid} proceeded\n")
  foreman = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  assert [r["round"] for r in foreman["rounds"]] == [1]


def unit_state(st, card, foreman):
  """`report.unit_state` of UNIT as the readers see it: its saved view, launches and the wave card."""
  import time
  from superegm import launch, report
  view = report.unit_view(json.loads(st.path("state").read_text(encoding="utf-8")), UNIT)
  card_json = json.loads(st.path("runcards", card).read_text(encoding="utf-8"))
  return report.unit_state(UNIT, view, foreman, launch.load_launches(st, UNIT), card_json, {}, time.time())
