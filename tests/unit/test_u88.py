# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U88's tests: the judges rule a builder's contest first (design section 7.8).

"""U88: a builder's contest of a head finding goes to the judges' panel first in normal mode as in leavemealone."""

import json
from pathlib import Path

import pytest

import superegm as core
from test_leavemealone_finish import head_review, seed
from test_review import A, F, head_round, hstore, opened, rjson, settle
from test_review import record as record_findings
from test_wave import REPO, fake_gh, foreman_of, wave_store
from test_wave import question as write_question

COMMENTS_TEXT = "change-review-1-1 | high | src/x.py:3 | the retry loop never backs off\n"
DIFF_TEXT = "--- a/src/x.py\n+++ b/src/x.py\n@@ -3 +3 @@\n-retry()\n+retry(backoff=1)\n"
BODY_TEXT = "### U07: Retry\n\n## Objective\nDeliver with a bounded retry.\n"
SPEC_RANGE_TEXT = "### 4.2 Retries\nA retry waits before it tries again.\n"
AMENDMENTS_TEXT = "amendment 1: the wait is one second.\n"


def evidence(world):
  """The five evidence files of a head contest, written beside the repo: `comments.md`, the diff, the body, `r1/spec_range.md`, `r1/amendments.md`."""
  folder = world.repo.parent / "evidence"
  files = {"comments.md": COMMENTS_TEXT, "diff": DIFF_TEXT, "body": BODY_TEXT,
           "r1/spec_range.md": SPEC_RANGE_TEXT, "r1/amendments.md": AMENDMENTS_TEXT}
  for name, text in files.items():
    (folder / name).parent.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
  return [str(folder / name) for name in files]


def contest(world, tmp_path):
  """A normal-mode head review of U07 with a high finding the builder contested; its opened panel and question text."""
  seed(world)
  runcard = world.card("wave")
  review = head_review(world, runcard, tmp_path)
  code, out = world.run("judges", "question", "--review", review, "--round", "1",
                        "--reason", "change-review-1-1=the test covers it", "--runcard", runcard)
  assert code == 0, out
  path = Path(out.splitlines()[0])
  flags = [part for item in evidence(world) for part in ("--evidence", item)]
  code, out = world.run("judges", "open", "--question", str(path), *flags, "--parent", runcard)
  assert code == 0, out
  return out.strip(), path.read_text(encoding="utf-8")


def test_head_contest_goes_to_the_panel(world, tmp_path):
  """A normal-mode head contest renders the panel question with the five evidence files, inlined for Astra."""
  pid, question = contest(world, tmp_path)
  assert all(f") {o}" in question for o in ("finding upheld", "finding overruled — ", "redesign — "))
  astra_brief = (world.artifacts / "judges" / pid / "round-1" / "brief-astra.md").read_text(encoding="utf-8")
  assert all(name in astra_brief for name in ("comments.md", "diff", "body", "r1/spec_range.md", "r1/amendments.md"))
  assert AMENDMENTS_TEXT in astra_brief and SPEC_RANGE_TEXT in astra_brief and COMMENTS_TEXT in astra_brief


def journal_of(st):
  return st.path("journal").read_text(encoding="utf-8")


@pytest.mark.parametrize("kind, rc, out", [
    ("head", 0, "Ruling (judges p1, contest): U07 change-review-1-1 declined"),
    ("spec", 1, "review settle: design-1-1 is high: --owner required in normal mode"),
    ("plan", 1, "review settle: set-1-1 is high: --owner required in normal mode")])
def test_settle_judges_by_card_kind(world, kind, rc, out):
  """`--judges` settles a contested head finding on a normal-mode card; every other review keeps `--owner`."""
  reviewer = {"head": "change-review", "spec": "design", "plan": "set"}[kind]
  spec, cid, rid = opened(world, kind)
  if kind == "head":
    head_round(world, 1, "posted", cid, "revise")
  loc = "src/x.py" if kind == "head" else "§1"
  assert record_findings(world, rid, 1, reviewer, [F(reviewer, 1, 1, "high", loc=loc)], cid, sha=A if kind == "head" else None)[0] == 0
  code, text = settle(world, rid, f"{reviewer}-1-1", "declined", cid, "--judges", "p1")
  finding = rjson(world, rid, "round-1.json")["reviewers"][reviewer]["findings"][0]
  journal = journal_of(hstore(world)) if rc == 0 else ""
  assert code == rc and out in (journal if rc == 0 else text), text
  assert (finding["disposition"], finding["ruling"]) == (("declined", "judges:p1") if rc == 0 else (None, None))
  if rc == 0:  # the contest line stands in place of the `review settle … by …` line
    assert f"review settle {rid} change-review-1-1" not in journal


@pytest.mark.parametrize("mode, word", [("normal", "contest"), ("leavemealone", "leavemealone")])
def test_the_judges_ruling_word_is_the_cards_mode(world, mode, word):
  """`decision rule --by judges:<panel>` journals and posts `contest` on a normal-mode card, `leavemealone` on a leavemealone one;
  `<fid> allowed` stays the owner's alone in normal mode."""
  from test_u84 import SPEC_COMMENT, open_decision, rule_on, spec_world
  card, s = spec_world(world, mode)
  qid = open_decision(world, card, SPEC_COMMENT)
  code, text = rule_on(world, card, qid, "(a)", "judges:p1")
  assert code == 0, text
  assert f"Ruling (judges p1, {word}): U02 {qid} " in journal_of(s)
  assert f"\n(judges p1, {word})\n" in [c for posted in world.gh.comments.values() for c in posted][-1]["body"]
  data = foreman_of(s, "U02")  # the owner-only decision: a test-delta finding the foreman raised, which the judges never settle
  core.atomic_write(s.path("foreman", "U02"), data | {"rounds": [{"round": 1, "phase": "posted", "outcome": "owner: foreman-1-1"}]})
  td = "foreman-1-1 | high | tests/unit/test_q.py:3 | regression: no | test-delta: tests/unit/test_q.py:3 removed\n"
  owner_qid = world.run("decision", "open", "--unit", "U02", "--point", 1, "--question", write_question(world, td),
                        "--source", "review head-U02-c1 round 1", "--runcard", card)[1].splitlines()[0]
  code, text = world.run("decision", "rule", "--unit", "U02", "--decision", owner_qid, "--ruling", "foreman-1-1 allowed",
                         "--by", "judges:p1", "--runcard", card)
  assert code != 0 and "decision: foreman-1-1 allowed is the owner's alone" in text, text
