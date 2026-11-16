# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0

"""U94: a recorded proceed comment is consumed (spec section 4.2): no later `status` reads it as a ruling event."""

import json

import pytest

import test_foreman as tf
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


def test_edited_proceed_waives_no_collect_check(world, tmp_path, monkeypatch):
  allowances = ["**Ruling:** test-delta tests/unit/test_q.py allowed — by design", "**Ruling:** dod-2 allowed — needs a service"]
  comments = {2: [tf.c(501 + i,"owner", body) | {"updated_at": "2026-11-02T14:00:00Z"} for i, body in enumerate(allowances)]}
  monkeypatch.setattr(tf, "BODY", tf.BODY.replace("2. Run `true` — passes\n", f"2. Run `{tf.RED}` — passes\n"))
  pr_body = f"U01\n\n### DoD 2\n```\n$ {tf.RED}\nok\n```\n\nCloses #2\n"
  gut = [("chore: gut", tf.Q, tf.T("def test_a():", "  pass"))]
  w = tf.prepared(world, tmp_path, monkeypatch, commits=tf.S1 + gut, base_files={tf.Q: tf.THREE}, pr_body=pr_body, comments=comments)
  data = json.loads(w.st.path("foreman", tf.UNIT).read_text())
  data["proceeds"] = [proceed_entry(f"comment {501 + i}", by="owner", posted_at="2026-11-02T13:00:00Z") for i in range(2)]
  w.st.path("foreman", tf.UNIT).write_text(json.dumps(data))
  tf.record(world, w.st, w.rid, 1, w.head, w.child, {"change-review": ""})
  code, out = world.run("collect", "--unit", tf.UNIT, "--dispatch", w.did, "--runcard", w.child)
  found = (w.dir / "r1/foreman.findings").read_text()
  assert code == 0 and "test-delta" in found and "dod" in found, (out, found)
