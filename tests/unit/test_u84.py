# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U84's tests, spec §7.6 "The deviation" and "The ruling": the `spec` deviation kind and the owner's `respec`.

"""U84: a `**Deviation (spec):**` comment blocks until ruled, its decision offers `respec` (the owner's alone,
never in the judges' question), `decision rule ... respec` writes `respec/R<n>.open.json` and never `state.json`,
and the builder orders and the foreman brief define the kind."""

import json
from pathlib import Path

import pytest

import superegm as core
from conftest import set_config
from superegm import decision
from superegm.collect import DEVIATION_RE
from superegm.decision import comment_options
from superegm.judges import decision_question, stored_options_text
from test_foreman import UNIT, c, prepared
from test_wave import REPO, fake_gh, foreman_of, question, wave_store

SPEC_LINE = "**Deviation (spec):** docs/designs/sample.md:12 says 3; `pytest -k t` fails"  # the test world's frozen spec path
SPEC_COMMENT = SPEC_LINE + "\n- (a) keep the spec\n- (b) follow the code\n**Builder status:** BLOCKED"


@pytest.mark.parametrize("ruled, blockers", [(False, 1), (True, 0)])
def test_spec_deviation_blocks_until_ruled(world, tmp_path, monkeypatch, ruled, blockers):
  # a `spec` deviation is a blocker as `interface`, `dod` and `test` are (collect.py:550-554)
  assert DEVIATION_RE.match(SPEC_LINE).group(1) == "spec"
  comments = [c(12, "builder-bot", SPEC_COMMENT)] + ([c(13, "owner", "**Ruling:** (12) (a) — the spec stands")] if ruled else [])
  w = prepared(world, tmp_path, monkeypatch, comments={2: comments})
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"collected: {blockers} foreman findings"), out
  lines = (w.dir / "r1/foreman.findings").read_text(encoding="utf-8").splitlines()
  assert lines == (["foreman-1-1 | high | issue #2 comment 12 | regression: no | deviation (spec) unruled"] if blockers else [])


def spec_world(world, mode="normal", text=SPEC_COMMENT, cid=101):
  """A wave card in `mode`, U02 with a pull request, the owner `owner`, the builder's comment `cid` on the issue."""
  extra = ["--mode", "leavemealone"] if mode == "leavemealone" else []
  card = world.run("runcard", "open", "--skill", "wave", "--artifact", world.spec, *extra, card=None)[1].strip()
  s = wave_store(world, U02={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "builder-bot"}, "body": text}})
  return card, s


def open_decision(world, card, text, cid=101):
  return world.run("decision", "open", "--unit", "U02", "--point", 3, "--question", question(world, text),
                   "--source", f"comment {cid}", "--runcard", card)[1].splitlines()[0]


def rule_on(world, card, qid, ruling, by="owner"):
  return world.run("decision", "rule", "--unit", "U02", "--decision", qid, "--ruling", ruling, "--by", by, "--runcard", card)


@pytest.mark.parametrize("mode", ["normal", "leavemealone"])
def test_respec_is_the_owners_alone(world, mode):
  # respec, like amend, is offered on a spec deviation but refused to the judges and absent from their question
  assert comment_options(SPEC_COMMENT)[-2:] == ["respec", "stop the unit"]
  assert "respec" not in comment_options(SPEC_COMMENT.replace("(spec)", "(interface)"))
  card, s = spec_world(world, mode)
  qid = open_decision(world, card, SPEC_COMMENT)
  stored = foreman_of(s, "U02")["decisions"][-1]["options"]
  assert stored == ["(a) keep the spec", "(b) follow the code", "respec", "stop the unit"]
  code, err = rule_on(world, card, qid, "respec", "judges:p-1")
  assert code != 0 and "decision: respec is the owner's alone" in err
  assert not (s.base() / "respec").exists()
  # the judges' question for the blocked comment lists every option but respec; in leavemealone it waits for the owner (§7.6)
  code, out = world.run("judges", "question", "--unit", "U02", "--blocked", "101", "--runcard", card)
  if mode == "leavemealone":
    assert code != 0 and "waits for the owner" in out and not (s.base() / "questions").exists()
  else:
    assert code == 0, out
    blocked = Path(out.splitlines()[0]).read_text(encoding="utf-8")
    assert "respec" not in blocked and blocked.endswith("- (a) keep the spec\n- (b) follow the code\n- (d) stop the unit\n")
  s.path("units").write_text(json.dumps({"units": {"U01": {"decisions": [{"id": "d1", "question": "Which?", "options": stored}]}}}), encoding="utf-8")
  asked = decision_question(s, "U01", "d1")
  assert "- respec\n" not in asked and "- stop the unit\n" in asked and "- (a) keep the spec\n" in asked


def test_respec_ruling_writes_the_open_file_only(world):
  # the owner's respec writes respec/R<n>.open.json (store kind `file`), never state.json, under write enforcement
  card, s = spec_world(world)
  state_file, AT = s.path("state"), core.now_iso()
  qid = open_decision(world, card, SPEC_COMMENT)
  before = state_file.read_bytes()
  rule_rc, out = rule_on(world, card, qid, "respec")
  assert rule_rc == 0 and state_file.read_bytes() == before, out
  open_file = s.path("file", "respec", "R1.open.json")
  assert json.loads(open_file.read_text(encoding="utf-8")) == {"id": "R1", "unit": "U02", "comment_id": 101, "at": AT}
  assert foreman_of(s, "U02")["rulings"][-1]["ruling"] == "respec"
  assert sorted(p.name for p in (s.base() / "respec").iterdir()) == ["R1.open.json"]
  second = open_decision(world, card, SPEC_COMMENT.replace("sample.md:12", "sample.md:40"), cid=102)
  assert rule_on(world, card, second, "respec")[0] == 0
  second_open_file = s.path("file", "respec", "R2.open.json")
  assert second_open_file.name == "R2.open.json" and json.loads(second_open_file.read_text(encoding="utf-8"))["comment_id"] == 102
  assert state_file.read_bytes() == before and "file" in decision.WRITES


@pytest.mark.parametrize("body, refusal", [
    ("**Deviation (spec):** the retry count is wrong; `pytest -k retry` fails", "decision: respec needs the frozen spec's path:line"),
    ("**Deviation (spec):** docs/designs/sample.md:12 says 3 retries", "decision: respec needs the evidence"),
    ("**Deviation (spec):** docs/designs/sample.md:12 says 3; docs/designs/sample.md:40 says 4", "decision: respec needs the evidence"),
    ("**Deviation (spec):** src/retry.py:12 says 3; `pytest -k retry` fails", "decision: respec needs the frozen spec's path:line"),
    ("**Deviation (spec):** src/a.py:1 says 3; src/b.py:2 sets 5", "decision: respec needs the frozen spec's path:line")])
def test_spec_deviation_needs_the_line_and_the_evidence(world, body, refusal):
  # a spec deviation quotes the frozen spec's path:line AND the evidence (a command and output, or a base path:line)
  text = body + "\n- (a) keep the spec\n- (b) follow the code\n**Builder status:** BLOCKED"
  card, s = spec_world(world, text=text)
  qid = open_decision(world, card, text)
  rule_respec_rc, err = rule_on(world, card, qid, "respec")
  assert rule_respec_rc != 0 and refusal in err
  assert not s.path("file", "respec", "R1.open.json").exists() and not any(world.gh.comments.values())  # refused before anything is posted


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("path", ["skills/wave/references/builder_orders.md", "skills/wave/references/foreman_brief.md"])
def test_builder_orders_and_foreman_brief_define_spec(path):
  # both docs define the `spec` kind with its two parts; the foreman raises it as a finding of kind `spec`
  text = (ROOT / path).read_text(encoding="utf-8")
  assert all(p in text for p in ("**Deviation (spec):**", "`path:line`", "evidence", "stays `interface`"))
  assert "which the foreman never posts" not in text
  if path.endswith("foreman_brief.md"):  # the foreman raises it by posting the deviation comment, so the blocker and the respec decision apply
    assert "posting a `**Deviation (spec):**` comment" in text


@pytest.mark.parametrize("text, spec, refusal", [
    (SPEC_LINE, "/r/docs/designs/sample.md", None),
    ("**Deviation (spec):** docs/designs/sample.md:12 says 3; src/retry.py:9 sets 5", "/r/docs/designs/sample.md", None),
    ("**Deviation (spec):** ./docs/designs/sample.md:12 says 3; `pytest` fails", "/r/docs/designs/sample.md", None),
    ("**Deviation (spec):** src/retry.py:12 says 3; `pytest` fails", "/r/docs/designs/sample.md", "frozen spec's path:line"),
    ("**Deviation (spec):** other/sample.md:12 says 3; `pytest` fails", "/r/docs/designs/sample.md", "frozen spec's path:line"),
    ("**Deviation (spec):** src/retry.py:12 says 3; `pytest` fails", "", None)])  # no spec known: nothing to compare with
def test_check_respec_compares_the_cited_path_with_the_frozen_spec(text, spec, refusal):
  if refusal is None:
    decision.check_respec(text, spec)
  else:
    with pytest.raises(decision.Refusal, match=refusal):
      decision.check_respec(text, spec)


def test_judges_cannot_reach_respec_by_a_lettered_option(world):
  # a comment whose own option line reads `- (a) respec` stores `(a) respec`: the judges' letter still resolves to the owner's alone
  text = SPEC_LINE + "\n- (a) respec\n- (b) follow the code\n**Builder status:** BLOCKED"
  card, s = spec_world(world, text=text)
  qid = open_decision(world, card, text)
  code, err = rule_on(world, card, qid, "(a)", "judges:p-1")
  assert code != 0 and "decision: respec is the owner's alone" in err and not (s.base() / "respec").exists()
  assert stored_options_text(["(a) respec", "(b) follow the code", "respec", "stop the unit"]) == "- (b) follow the code\n- (d) stop the unit\n"
  s.path("units").write_text(json.dumps({"units": {"U01": {"decisions": [{"id": "d1", "question": "Which?", "options": ["(a) respec", "(b) x"]}]}}}), encoding="utf-8")
  assert "respec" not in decision_question(s, "U01", "d1")


@pytest.mark.parametrize("body", [SPEC_COMMENT, SPEC_COMMENT.replace(" says 3; `pytest -k t` fails", ""), SPEC_LINE])
def test_an_unrecorded_respec_ruling_binds_nothing(body):
  # only `decision rule` records a respec, after writing the open file: a ruling comment alone clears no blocker, on a
  # comment with or without option lines, on a decision, or on a comment id this issue lacks
  ruling = decision.Ruling("option", "12", "respec", "the spec is wrong", "owner", 20)
  assert decision.offered(ruling, [{"id": 12, "body": body}], []) is False
  assert decision.offered(ruling, [], [{"point": 3, "source": "comment 12", "question": body, "options": decision.comment_options(body)}]) is False
  assert decision.offered(ruling, [], []) is False
  assert decision.offered(decision.Ruling("option", "12", "(a)", "the spec stands", "owner", 20), [{"id": 12, "body": SPEC_COMMENT}], []) is True


def test_an_unrecorded_respec_comment_keeps_the_spec_blocker(world, tmp_path, monkeypatch):
  comments = [c(12, "builder-bot", SPEC_COMMENT), c(13, "owner", "**Ruling:** (12) respec — the spec is wrong")]
  w = prepared(world, tmp_path, monkeypatch, comments={2: comments})
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, "collected: 1 foreman findings"), out


def test_a_third_comment_decision_still_offers_respec(world):
  # the relaunch/stop carve-out for a third comment on one head keeps `respec` on a spec deviation (§7.6: every spec deviation's decision)
  card, s = spec_world(world)
  for cid in (101, 102):
    qid = open_decision(world, card, "**Deviation (other):** x\n- (a) go on\n**Builder status:** BLOCKED", cid=cid)
    assert rule_on(world, card, qid, "(a)")[0] == 0
  fake_gh(world, {f"repos/{REPO}/issues/comments/103": {"id": 103, "user": {"login": "builder-bot"}, "body": SPEC_COMMENT}})
  third = open_decision(world, card, SPEC_COMMENT, cid=103)
  assert foreman_of(s, "U02")["decisions"][-1]["options"] == ["relaunch", "respec", "stop the unit"]
  assert rule_on(world, card, third, "respec")[0] == 0 and s.path("file", "respec", "R1.open.json").exists()


def test_the_judges_blocked_question_without_a_decision_leaves_out_respec(world):
  # no decision opened on the comment: the options are read off its lines, a lettered `respec` and `amend` still left out
  text = SPEC_LINE + "\n- (a) respec\n- (b) follow the code\n**Builder status:** BLOCKED"
  card, s = spec_world(world, text=text)
  code, out = world.run("judges", "question", "--unit", "U02", "--blocked", "101", "--runcard", card)
  assert code == 0, out
  assert Path(out.splitlines()[0]).read_text(encoding="utf-8").endswith("- (b) follow the code\n- (c) stop the unit\n")


def test_judges_cannot_reach_amend_by_a_lettered_option(world):
  # amend, like respec, is the owner's alone: a stored `(a) amend` resolved by the judges' letter is refused too
  text = "**Deviation (interface):** U02 load: takes two\n- (a) amend\n- (b) keep\n**Builder status:** BLOCKED"
  card, s = spec_world(world, text=text)
  qid = open_decision(world, card, text)
  code, err = rule_on(world, card, qid, "(a)", "judges:p-1")
  assert code != 0 and "amend" in err and "owner" in err


def test_a_rerun_keeps_the_open_file_of_the_same_deviation(world):
  # open_respec after a crash finds the file of the same unit and comment; another comment takes the next number
  card, s = spec_world(world)
  assert [decision.open_respec(s, "U02", cid, core.now_iso()) for cid in (101, 101, 102, 101)] == ["R1", "R1", "R2", "R1"]
  assert sorted(p.name for p in (s.base() / "respec").iterdir()) == ["R1.open.json", "R2.open.json"]
