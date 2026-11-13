# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: 1.2.1-pre.1 P5, the owner's `amend` ruling and `amendments[]` (spec §6.5 "`amend`").

"""P5: `**Ruling:** (<comment-id>) amend — <Interfaces line>` on an interface deviation, offered, refused and recorded,
and the `amendments[]` entries `decision rule` writes to the handoff's state.json."""

import json
import re
from pathlib import Path

import pytest

from conftest import set_config
from superegm.decision import check_ruling, offered, options_for, ruling_of
from superegm.review import Refusal
from test_wave import REPO, fake_gh, foreman_of, open_wave_card, question, wave_store

IFACE = "**Deviation (interface):** U01 dequeue: returns null, not undefined\n"
DOD = "**Deviation (dod):** item 2 needs a service\n"
OPTS = "**Builder status:** BLOCKED\nWhich?\n- (a) keep undefined\n- (b) return null\n"
LINE = "dequeue() -> Job | null"
NONE = "decision: ruling is none of the options: (a) keep undefined; (b) return null; stop the unit\n"
ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def amend_of(body, cid=4, login="owner"):
  return ruling_of({"id": cid, "user": {"login": login}, "body": body}, ["owner"])


@pytest.mark.parametrize("deviation, ok", [(IFACE, True), (DOD, False), (IFACE + DOD, False)])
def test_offered_accepts_amend_on_an_interface_deviation(deviation, ok):
  comments = [{"id": 3, "user": {"login": "builder-bot"}, "body": deviation + OPTS}]
  r = amend_of(f"**Ruling:** (3) amend — {LINE}")
  assert (r.kind, r.subject, r.option, r.reason) == ("option", "3", "amend", LINE)
  assert offered(r, comments, []) is ok
  options = options_for(3, "comment 3", deviation + OPTS, {}, "a" * 40)
  assert ("amend" in options) is ok and options[-1] == "stop the unit"
  assert offered(r, comments, [{"id": "q1", "point": 3, "source": "comment 3", "options": options}]) is ok


def test_check_ruling_refuses_amend_from_the_judges():
  options = ["(a) keep undefined", "(b) return null", "amend", "stop the unit"]
  assert check_ruling(3, options, "amend", "owner") == "amend"
  with pytest.raises(Refusal, match="owner's alone"):
    check_ruling(3, options, "amend", "judges:p-1")


def world_on(world, routes=None):
  card = open_wave_card(world)
  s = wave_store(world, U02={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world, routes)
  return card, s


def opened(world, card, text, source="comment 77", point=3):
  return world.run("decision", "open", "--unit", "U02", "--point", point, "--question", question(world, text),
                   "--source", source, "--runcard", card)[1].splitlines()[0]


def amendments(s):
  return json.loads(s.path("state").read_text(encoding="utf-8")).get("amendments")


def rule(world, card, qid, ruling, by="owner", *extra):
  return world.run("decision", "rule", "--unit", "U02", "--decision", qid, "--ruling", ruling, "--by", by, "--runcard", card, *extra)


def test_an_amend_ruling_is_recorded_with_its_amendment(world):
  card, s = world_on(world)
  qid = opened(world, card, IFACE + OPTS)
  assert rule(world, card, qid, f"amend — {LINE}", "judges:p-1") == (1, "decision: amend is the owner's alone\n")
  code, out = rule(world, card, qid, f"amend — {LINE}")
  assert code == 0, out
  assert world.gh.comments[3][-1]["body"].startswith(f"**Ruling:** (77) amend — {LINE}\n")
  assert foreman_of(s, "U02")["rulings"][-1]["ruling"] == f"amend — {LINE}"
  [entry] = amendments(s)
  assert {k: v for k, v in entry.items() if k != "at"} == {"unit": "U01", "name": "dequeue", "text": LINE, "comment_id": 1}
  assert ISO.match(entry["at"])


@pytest.mark.parametrize("text, refusal", [
  ("**Deviation (interface):** U01 peek: missing\n" + OPTS, "decision: amend names U01 peek, not in U01's Interfaces lines\n"),
  (IFACE + DOD + OPTS, NONE),  # not offered off one interface heading alone
  (IFACE + "**Deviation (interface):** U02 deliver: a bool\n" + OPTS, NONE),
  ("**Deviation (interface):** dequeue returns null\n" + OPTS, "decision: amend needs a comment with one interface deviation and no other\n"),
])
def test_amend_is_refused_off_one_named_interface_deviation(world, text, refusal):
  card, s = world_on(world)
  qid = opened(world, card, text)
  assert rule(world, card, qid, f"amend — {LINE}") == (1, refusal)
  assert not foreman_of(s, "U02")["rulings"] and amendments(s) is None and 3 not in world.gh.comments


def test_amend_needs_the_interfaces_line(world):
  card, s = world_on(world)
  qid = opened(world, card, IFACE + OPTS)
  assert rule(world, card, qid, "amend") == (1, "decision: amend needs — <the Interfaces line as it now reads>\n")
  assert amendments(s) is None


def test_amend_is_not_offered_on_a_dod_deviation(world):
  card, s = world_on(world)
  qid = opened(world, card, DOD + OPTS)
  code, out = rule(world, card, qid, f"amend — {LINE}")
  assert code == 1 and out.startswith("decision: ruling is none of the options:") and amendments(s) is None


def test_an_option_ruling_on_several_headings_settles_them_all_and_amends_the_interface(world):
  card, s = world_on(world)
  text = IFACE + DOD + "**Deviation (interface):** U01 enqueue: takes a list\n" + OPTS
  qid = opened(world, card, text)
  assert rule(world, card, qid, "(b) — null reads better") == (0, f"https://github.com/{REPO}/issues/3#issuecomment-1\n")
  got = [{k: v for k, v in e.items() if k != "at"} for e in amendments(s)]
  assert got == [{"unit": "U01", "name": "dequeue", "text": "return null", "comment_id": 1},
                 {"unit": "U01", "name": "enqueue", "text": "return null", "comment_id": 1}]


@pytest.mark.parametrize("point, source, ruling", [
  (3, "comment 77", "stop the unit"), (3, "launch 1", "relaunch"), (2, "review head-U02-c1 cap", "one more round")])
def test_a_ruling_that_keeps_the_contract_records_no_amendment(world, point, source, ruling):
  card, s = world_on(world)
  qid = opened(world, card, IFACE + OPTS, source, point)
  code, out = rule(world, card, qid, ruling)
  assert code == 0, out
  assert amendments(s) is None


def test_an_option_ruling_on_a_dod_deviation_records_no_amendment(world):
  card, s = world_on(world)
  qid = opened(world, card, DOD + OPTS)
  assert rule(world, card, qid, "(b) — fine")[0] == 0
  assert amendments(s) is None


def test_a_by_hand_amend_records_its_comment_id(world):
  routes = {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": login}, "body": body}
            for cid, login, body in ((88, "owner", f"**Ruling:** (77) amend — {LINE}\n"),)}
  card, s = world_on(world, routes)
  qid = opened(world, card, IFACE + OPTS)
  assert rule(world, card, qid, "amend", "owner", "--posted", "88") == (0, "recorded (comment 88)\n")
  [entry] = amendments(s)
  assert (entry["unit"], entry["name"], entry["text"], entry["comment_id"]) == ("U01", "dequeue", LINE, 88)
  assert 3 not in world.gh.comments


def test_the_judges_question_leaves_amend_out(world):
  routes = {f"repos/{REPO}/issues/comments/77": {"id": 77, "user": {"login": "builder-bot"}, "body": IFACE + OPTS}}
  card, s = world_on(world, routes)
  opened(world, card, IFACE + OPTS)
  code, out = world.run("judges", "question", "--unit", "U02", "--blocked", "77", "--runcard", card)
  assert code == 0, out
  text = Path(out.splitlines()[0]).read_text(encoding="utf-8")
  assert "amend" not in text and text.endswith("- (a) keep undefined\n- (b) return null\n- (c) stop the unit\n")


def test_the_judges_decision_question_leaves_amend_out(world):
  from superegm.judges import decision_question
  card, s = world_on(world)
  qid = opened(world, card, IFACE + OPTS)
  decision = foreman_of(s, "U02")["decisions"][-1]
  assert "amend" in decision["options"]
  s.path("units").write_text(json.dumps({"units": {"U02": {"decisions": [decision]}}}), encoding="utf-8")
  text = decision_question(s, "U02", qid)
  assert "- amend\n" not in text and text.endswith("- (a) keep undefined\n- (b) return null\n- stop the unit\n")
