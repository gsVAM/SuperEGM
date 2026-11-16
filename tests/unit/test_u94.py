# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0

"""U94: a recorded proceed comment is consumed (spec section 4.2): no later `status` reads it as a ruling event."""

import json

from conftest import REPO, set_config
from superegm import decision
from test_events import WAIT, comment, put, seed

T0 = "2026-11-03T10:00:00Z"
SHA = "a" * 40


def proceed_entry(posted, by="gsvam", reason="ship it", posted_at=T0):
  return {"ruling": "R1", "review": "r1", "posted": posted, "posted_at": posted_at, "issue": 2, "head": SHA,
          "launch": 1, "by": by, "reason": reason}


def test_consumed_comments_lists_posted_proceeds(world, monkeypatch):
  set_config(world, repo=REPO, owners=["gsvam"])
  gh, st, card = seed(world, monkeypatch)
  foreman = {"dispatch_id": None, "rounds": [], "decisions": [{"id": "q1", "point": 3, "source": "comment 300"}],
             "rulings": [{"decision": "q1", "ruling": "(b)", "by": "gsvam", "reason": "fine", "posted": "comment 400",
                          "posted_at": T0}],
             "proceeds": [proceed_entry("comment 501"), proceed_entry(None, by="owner", posted_at=None)]}
  put(st.path("foreman", "U01"), json.dumps(foreman))
  comment(gh, "**Ruling:** proceed — ship it", login="gsvam", cid=501, at=T0)
  assert decision.consumed_comments(foreman) == {501, 400}
  code, out = world.run(*WAIT, card)
  assert code == 0 and "U01 ruling" not in out, out
