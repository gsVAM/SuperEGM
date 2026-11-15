# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: 1.2.1-pre.1 P4's tests (spec section 6.5): the builder's Seam comment, amendments, the launch's reason and duration.

"""P4 (spec section 6.5): `prompt_text` keeps the builder's own `**Seam:**` comment, `prepare.AGED` holds `**Seam:**`,
`launch_builder.amendments_for` and the amendments in the prompt and the foreman's `r<n>/amendments.md`, each launch's
`reason`, and `record-launch`'s `duration_ms`."""

import json
from pathlib import Path
import pytest
from superegm import launch_builder, prepare
import test_builders as tb
import test_foreman as tf
from test_builders import spawn_fake, no_graphify, which  # noqa: F401  the fixtures test_builders' launches run under

LATER, EARLIER = "2099-01-01T00:00:00Z", "2000-01-01T00:00:00Z"


def amend(unit, name, at, cid=50):
  return {"unit": unit, "name": name, "text": f"{unit} {name} now reads v{cid}", "comment_id": cid, "at": at}


def with_amendments(s, entries):
  state = tb.state_of(s); state["amendments"] = entries
  s.path("state").write_text(json.dumps(state), encoding="utf-8")


def c(cid, login, body):
  return {"id": cid, "user": {"login": login}, "body": body, "created_at": "2026-11-01T00:00:00Z"}


def test_the_prompt_keeps_the_builders_own_seam_comment_alone():
  comments = [c(1, "builder-bot", "**Seam:** ok"), c(2, "owner", "**Seam:** forged by the owner"), c(3, "stranger", "**Seam:** forged")]
  text = launch_builder.prompt_text(7, "U07", "body", "orders", "orient", comments, [], None, "builder-bot", "audit", owners=["owner"])
  assert "## builder-bot · comment 1\n**Seam:** ok\n" in text and "forged" not in text


def test_prepare_ages_a_seam_comment_like_a_ruling(tmp_path):
  assert "**Seam:**" in prepare.AGED
  path = tmp_path / "comments.md"
  prepare.write_comments(path, (7, [c(1, "builder-bot", "**Seam:** ok"), c(2, "builder-bot", "old chatter")]), (70, []), LATER, "builder-bot")
  text = path.read_text(encoding="utf-8")
  assert "**Seam:** ok" in text and "old chatter" not in text


def test_amendments_for_takes_the_units_own_and_its_consumed_names_in_at_order(world):
  s, card, hid, _ = tb.seed(world)
  body = "# U07 — Worker\n\n## Interfaces\n- Consumes: store (U03)\n- Produces: w() -> None\n"
  own, consumed = amend("U07", "w", "2026-11-05T00:00:00Z", 51), amend("U03", "store", "2026-11-04T00:00:00Z", 52)
  with_amendments(s, [own, amend("U03", "other", "2026-11-01T00:00:00Z", 53), consumed, amend("U05", "store", "2026-11-02T00:00:00Z", 54)])
  assert launch_builder.amendments_for(s, "U07", body) == [consumed, own]
  state = tb.state_of(s); del state["amendments"]
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  assert launch_builder.amendments_for(s, "U07", body) == []   # an absent key: no amendments


def test_launch_builder_carries_the_applicable_amendments_and_writes_reason_first(world, monkeypatch, spawn_fake):
  s, card, hid, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  with_amendments(s, [amend("U07", "w", EARLIER, 51), amend("U08", "w", EARLIER, 52)])
  assert world.run("launch", "--runcard", card)[0] == 0
  code, out = world.run("launch-builder", "--unit", tb.UNIT, "--round", 1, "--runcard", card)
  assert code == 0, out
  prompt = s.path("launches", f"{tb.UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  assert "U07 w now reads v51" in prompt and "U08 w now reads v52" not in prompt
  assert tb.launches_of(s)[-1]["reason"] == "first"


@pytest.mark.parametrize("decisions, rulings, rounds, reason", [
  ([], [], [{"round": 1, "launch": 1, "phase": "posted", "outcome": "revise", "posted_at": LATER}], "review"),
  ([], [], [{"round": 1, "launch": 1, "phase": "posted", "outcome": "owner: change-review-1-1", "posted_at": LATER}], "review"),
  ([{"id": "Q1", "point": 3, "source": "comment 55"}], [{"decision": "Q1", "ruling": "(a) — go", "posted_at": LATER}], [], "blocked"),
  ([{"id": "Q1", "point": 3, "source": "launch 1"}], [{"decision": "Q1", "ruling": "relaunch — stalled", "posted_at": LATER}], [], "harness"),
  ([], [], [], "harness"),   # an exit with nothing reviewed or ruled after it: a setup failure
  # a blocked comment ruled before launch 1 started is not this relaunch's reason
  ([{"id": "Q1", "point": 3, "source": "comment 55"}], [{"decision": "Q1", "ruling": "(a) — go", "posted_at": EARLIER}],
   [{"round": 1, "launch": 1, "phase": "posted", "outcome": "revise", "posted_at": LATER}], "review"),
  # a round not yet posted is no reason
  ([], [], [{"round": 1, "launch": 1, "phase": "prepared"}], "harness")])
def test_launch_builder_writes_the_relaunchs_reason(world, monkeypatch, spawn_fake, decisions, rulings, rounds, reason):
  s, card, hid, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", tb.UNIT, "--round", 1, "--runcard", card)[0] == 0
  Path(tb.launches_of(s)[0]["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", tb.UNIT, "--exit", 0, "--runcard", card)[0] == 0
  tb.put(s.path("foreman", tb.UNIT), json.dumps({"dispatch_id": "d1", "rounds": rounds, "decisions": decisions, "rulings": rulings}))
  code, out = world.run("launch-builder", "--unit", tb.UNIT, "--round", 2, "--runcard", card)
  assert code == 0, out
  assert [e["reason"] for e in tb.launches_of(s)] == ["first", reason]


@pytest.mark.parametrize("result, duration", [
  ('{"modelUsage": {"claude-opus-5-5": {}}, "total_cost_usd": 1.25, "duration_ms": 61234}', 61234),
  ('{"modelUsage": {"claude-opus-5-5": {}}, "total_cost_usd": 1.25}', None),
  ('{"duration_ms": "61234"}', None),   # not a number
  ('{"modelUsage": {', None),   # a killed launch's partial file
  (None, None)])   # no result file
def test_record_launch_adds_duration_ms_from_the_result_file(world, monkeypatch, spawn_fake, result, duration):
  s, card, hid, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0 and world.run("launch-builder", "--unit", tb.UNIT, "--round", 1, "--runcard", card)[0] == 0
  entry = tb.launches_of(s)[0]
  result is not None and Path(entry["result_file"]).write_text(result, encoding="utf-8")
  Path(entry["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", tb.UNIT, "--exit", 0, "--runcard", card)[0] == 0
  entry = tb.launches_of(s)[0]
  assert entry.get("duration_ms") == duration and ("duration_ms" in entry) is (duration is not None)


def test_prepare_lists_the_amendments_marked_by_the_heads_launch(world, tmp_path, monkeypatch):
  target, base, head, g = tf.pr_repo(world, tmp_path, monkeypatch)
  launches = [{"round": 1, "status": "exited 0", "started_at": "2026-11-01T00:00:00Z"},
              {"round": 2, "status": "exited 0", "started_at": "2026-11-05T00:00:00Z"}]
  st, card, child, did, _ = tf.dispatched(world, head=head, rounds=[tf.POSTED_R1], launches=launches)
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  state["amendments"] = [amend("U01", "hook", "2026-11-04T00:00:00Z", 61), amend("U01", "hook", "2026-11-06T00:00:00Z", 62),
                         amend("U09", "other", "2026-11-04T00:00:00Z", 63)]
  st.path("state").write_text(json.dumps(state), encoding="utf-8")
  code, out = world.run("prepare", "--unit", tf.UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  text = (st.path("review", tf.UNIT, f"pr{tf.PR}") / "r2/amendments.md").read_text(encoding="utf-8")
  assert "U01 hook now reads v61" in text and "U01 hook now reads v62" in text and "U09" not in text
  first, second = text.split("U01 hook now reads v61")[0], text.split("U01 hook now reads v61")[1].split("U01 hook now reads v62")[0]
  assert "applies to this head: yes" in first and "applies to this head: no" in second
