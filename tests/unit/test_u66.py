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
