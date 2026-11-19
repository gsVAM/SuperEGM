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
from superegm.judges import decision_question
from test_foreman import UNIT, c, prepared
from test_wave import REPO, fake_gh, foreman_of, question, wave_store

SPEC_LINE = "**Deviation (spec):** docs/specs/x.md:12 says 3; `pytest -k t` fails"
SPEC_COMMENT = SPEC_LINE + "\n- (a) keep the spec\n- (b) follow the code\n**Builder status:** BLOCKED"


@pytest.mark.parametrize("ruled, blockers", [(False, 1), (True, 0)])
def test_spec_deviation_blocks_until_ruled(world, tmp_path, monkeypatch, ruled, blockers):
  # a `spec` deviation is a blocker as `interface`, `dod` and `test` are (collect.py:600-605)
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
  # the judges' question for the blocked comment, and a plan-time decision's, list every option but respec
  code, out = world.run("judges", "question", "--unit", "U02", "--blocked", "101", "--runcard", card)
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
  second = open_decision(world, card, SPEC_COMMENT.replace("x.md:12", "x.md:40"), cid=102)
  assert rule_on(world, card, second, "respec")[0] == 0
  second_open_file = s.path("file", "respec", "R2.open.json")
  assert second_open_file.name == "R2.open.json" and json.loads(second_open_file.read_text(encoding="utf-8"))["comment_id"] == 102
  assert state_file.read_bytes() == before and "file" in decision.WRITES


@pytest.mark.parametrize("body, refusal", [
    ("**Deviation (spec):** the retry count is wrong; `pytest -k retry` fails", "decision: respec needs the frozen spec's path:line"),
    ("**Deviation (spec):** docs/specs/x.md:12 says 3 retries", "decision: respec needs the evidence")])
def test_spec_deviation_needs_the_line_and_the_evidence(world, body, refusal):
  # a spec deviation quotes the frozen spec's path:line AND the evidence (a command and output, or a base path:line)
  text = body + "\n- (a) keep the spec\n- (b) follow the code\n**Builder status:** BLOCKED"
  card, s = spec_world(world, text=text)
  qid = open_decision(world, card, text)
  rule_respec_rc, err = rule_on(world, card, qid, "respec")
  assert rule_respec_rc != 0 and refusal in err
  assert not s.path("file", "respec", "R1.open.json").exists() and not any(world.gh.comments.values())  # refused before anything is posted
