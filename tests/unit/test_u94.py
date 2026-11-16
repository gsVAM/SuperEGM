# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0

"""U94: a recorded proceed comment is consumed (spec section 4.2): no later `status` reads it as a ruling event."""

import json

import pytest

from conftest import REPO, set_config
from superegm import decision
from superegm.launch_builder import prompt_text
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


@pytest.mark.parametrize("comment", ["**Ruling:** stop", None])
def test_edited_or_deleted_proceed_shows_the_record(world, comment):
  foreman = {"decisions": [], "rulings": [], "proceeds": [proceed_entry("comment 501", by="owner1", posted_at="t2")]}
  comments = [{"id": 501, "user": {"login": "owner1"}, "body": comment, "created_at": "t1", "updated_at": "t3"}] if comment else []
  assert decision.binding_rulings(comments, ["owner1"], [], consumed={501}) == []
  text = prompt_text(2, "U01", "body", "orders", "orient", comments, [], None, "builder-bot", "audit", owners=["owner1"], foreman=foreman)
  shown = text.split("# Comments on issue #2\n\n", 1)[1]
  assert "## owner1 · comment 501\n**Ruling:** proceed — ship it\n(as recorded by owner1; " in shown
  assert "stop" not in shown
