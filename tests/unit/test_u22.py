# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U22, rulings by GitHub comment (spec §13.2).

"""U22: the one ruling grammar `decision.ruling_of`, its renderer `ruling_form` and the builder prompt's keep rule."""

import re

import pytest

from superegm.decision import recorded_rulings, ruling_form, ruling_of
from superegm.launch_builder import prompt_text

FORMS = [
  ("**Ruling:** f-2-1 finding upheld", ("upheld", "f-2-1", None, None)),
  ("**Ruling:** f-2-1 finding upheld (fix it)\n\n> the finding", ("upheld", "f-2-1", None, None)),
  ("**Ruling:** f-2-1 finding overruled — the test covers it", ("overruled", "f-2-1", None, "the test covers it")),
  ("**Ruling:** one more round", ("round", "", None, None)), ("**Ruling:** f-2-1 finding overruled — done.", ("overruled", "f-2-1", None, "done.")),
  ("**Ruling:** stop", ("stop", "", None, None)),
  ("**Ruling:** (77) (b) use Redis — already a dependency", ("option", "77", "(b) use Redis", "already a dependency")),
  ("**Ruling:** dod-3 allowed — a service the worktree lacks", ("allowed", "dod-3", None, "a service the worktree lacks")),
  ("**Ruling:** test-delta tests/unit/test_x.py allowed — by design", ("allowed-file", "tests/unit/test_x.py", None, "by design")),
  ("**Ruling:** redesign — the queue is the wrong shape", ("redesign", "", None, "the queue is the wrong shape")),
  ("**Ruling:** f-2-1 finding upheld now", None), ("**Ruling:** f-2-1 finding overruled", None), ("**Ruling:** (77) use Redis", None),
  ("**Ruling:** (cap) stop", None), ("**Ruling:** (77) use Redis — fine\n(judges p-1, leavemealone)\n\n> q", None)]


@pytest.mark.parametrize("body, expect", FORMS)
def test_ruling_of_is_the_one_grammar(body, expect):
  comment = {"id": 501, "user": {"login": "gsvam"}, "body": body}
  ruling = ruling_of(comment, ["gsvam", "other"])
  assert (ruling and (ruling.kind, ruling.subject, ruling.option, ruling.reason)) == expect
  assert ruling_of(comment, ["other"]) is None and (not expect or (ruling.login, ruling.comment_id) == ("gsvam", 501))


RENDER = [((1, "f-2-1", "finding upheld"), "**Ruling:** f-2-1 finding upheld"), ((1, "f-2-1", "finding overruled"), "**Ruling:** f-2-1 finding overruled — <reason>"),
          ((1, "test-delta tests/unit/test_x.py", "allowed"), "**Ruling:** test-delta tests/unit/test_x.py allowed — <reason>"),
          ((1, "redesign", None), "**Ruling:** redesign — <reason>"), ((2, "one more round", None), "**Ruling:** one more round"),
          ((3, "77", "(b) use Redis"), "**Ruling:** (77) (b) use Redis — <reason>"), ((3, "q3", "relaunch"), "**Ruling:** (q3) relaunch — <reason>")]


@pytest.mark.parametrize("args, text", RENDER)
def test_ruling_form_renders_what_ruling_of_reads(args, text):
  assert ruling_form(*args) == text
  ruling = ruling_of({"id": 1, "user": {"login": "o"}, "body": text}, ["o"])
  assert ruling and (ruling.reason or "<reason>") == "<reason>"
  assert ruling.subject == ("" if ruling.kind in ("round", "stop", "redesign") else args[1].removeprefix("test-delta "))


COMMENTS = [(1, "owner", "**Decision D1:** (a) five"), (3, "builder-bot", "**Deviation (other):** renamed a fixture"),
            (4, "owner", "**Ruling:** (3) (a) proceed — fine"), (5, "passer-by", "**Ruling:** (3) (b) stop — now"), (6, "passer-by", "**Decision D2:** (b) ten"),
            (7, "owner", "**Ruling:** (3) (b) stop"), (8, "owner", "**Ruling:** (3) (a) proceed — fine\n(judges p-1, leavemealone)\n\n> q"),
            (9, "passer-by", "**Ruling:** (3) (b) stop — now\n(judges p-1, leavemealone)")]


def test_the_prompt_keeps_rulings_and_decisions_from_owners_alone():
  comments = [{"id": i, "user": {"login": who}, "body": body} for i, who, body in COMMENTS]
  text = prompt_text(2, "U01", "body", "orders", "orient", comments, [], None, "builder-bot", "audit", owners=["owner"])
  assert re.findall(r"^## \S+ · comment (\d+)$", text.split("# Comments on issue #2\n\n", 1)[1], re.M) == ["1", "3", "4", "8"]


# Round 2 (PR #96 review): option text that ends like a bare form still carries its reason; a point-3 option
# beginning with `redesign` is an option; the record wins over an edit of its comment and a later comment on its subject.


def test_a_point_3_option_ending_finding_upheld_keeps_its_reason():
  text = ruling_form(3, "77", "(a) mark finding upheld")
  assert text == "**Ruling:** (77) (a) mark finding upheld — <reason>"
  assert ruling_of({"id": 1, "user": {"login": "o"}, "body": text}, ["o"]).kind == "option"


def test_a_recorded_point_3_option_naming_redesign_is_an_option():
  foreman = {"decisions": [{"id": "q1", "point": 3, "source": "comment 12"}],
             "rulings": [{"decision": "q1", "ruling": "redesign the queue", "by": "judges:p-1", "reason": None, "posted": "comment 13"}]}
  assert [(r.kind, r.subject, r.option) for r in recorded_rulings(foreman)] == [("option", "12", "redesign")]


def test_the_prompt_drops_a_ruling_the_record_overrides():
  comments = [{"id": 4, "user": {"login": "owner"}, "body": "**Ruling:** f-1-1 finding overruled — changed", "created_at": "t1", "updated_at": "t3"},
              {"id": 5, "user": {"login": "owner"}, "body": "**Ruling:** f-1-1 finding overruled — again", "created_at": "t2", "updated_at": "t2"},
              {"id": 6, "user": {"login": "owner"}, "body": "**Ruling:** f-1-2 finding upheld (fix it)", "created_at": "t1", "updated_at": "t1"}]
  foreman = {"decisions": [{"id": "q1", "point": 1, "source": "review r round 1"}],
             "rulings": [{"decision": "q1", "ruling": "f-1-1 finding upheld", "by": "owner", "posted": "comment 4", "posted_at": "t1"},
                         {"decision": "q1", "ruling": "f-1-2 finding upheld", "by": "owner", "posted": "comment 6", "posted_at": "t1"}]}
  text = prompt_text(2, "U01", "body", "orders", "orient", comments, [], None, "builder-bot", "audit", owners=["owner"], foreman=foreman)
  shown = text.split("# Comments on issue #2\n\n", 1)[1]
  assert re.findall(r"^## \S+ · comment (\d+)$", shown, re.M) == ["4", "6"]  # comment 4 edited after its record: shown as the record
  assert "## owner · comment 4\n**Ruling:** f-1-1 finding upheld\n(as recorded by owner; the comment was edited after its record)\n" in shown
  assert "changed" not in shown and "again" not in shown


# Round 3 (PR #96 review): an edit before the record is the recorded text; an option the decision does not offer binds nothing.


def test_an_edit_before_the_record_keeps_the_ruling_in_the_prompt():
  comments = [{"id": 4, "user": {"login": "owner"}, "body": "**Ruling:** (3) (a) proceed — fixed the typo", "created_at": "t1", "updated_at": "t2"}]
  foreman = {"decisions": [{"id": "q1", "point": 3, "source": "comment 3", "options": ["(a) proceed", "stop the unit"]}],
             "rulings": [{"decision": "q1", "ruling": "(a)", "by": "owner", "reason": "fixed the typo", "posted": "comment 4", "posted_at": "t2"}]}
  text = prompt_text(2, "U01", "body", "orders", "orient", comments, [], None, "builder-bot", "audit", owners=["owner"], foreman=foreman)
  assert "## owner · comment 4\n**Ruling:** (3) (a) proceed — fixed the typo\n" in text


def test_an_option_the_comment_does_not_offer_binds_nothing():
  blocked = "**Deviation (dod):** item 3\nWhich?\n- (a) drop it\n- (b) keep it\n**Builder status:** BLOCKED"
  comments = [{"id": 3, "user": {"login": "builder-bot"}, "body": blocked},
              {"id": 4, "user": {"login": "owner"}, "body": "**Ruling:** (3) (c) proceed — fine"},
              {"id": 5, "user": {"login": "owner"}, "body": "**Ruling:** (3) (b) keep it — fine"}]
  text = prompt_text(2, "U01", "body", "orders", "orient", comments, [], None, "builder-bot", "audit", owners=["owner"], foreman={})
  assert re.findall(r"^## \S+ · comment (\d+)$", text.split("# Comments on issue #2\n\n", 1)[1], re.M) == ["3", "5"]
