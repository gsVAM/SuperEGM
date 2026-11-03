# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
"""U08: the judge panel (judges open|record|diff|verdict, the grammars, the adapter, persona and skill)."""
import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from superegm import judges

ROOT = Path(__file__).resolve().parents[2]

QUESTIONS = """## Q1 Is finding design-2-1 upheld?
- (a) finding upheld
- (b) finding overruled: the reason, copied verbatim

## Q2 The review is at its cap: what next?
- (a) continue one bounded round
- (b) accept the remainder
- (c) stop
"""
ONE = "## Q1 Is finding design-2-1 upheld?\n- (a) finding upheld\n- (b) finding overruled: reason\n"


def open_card(world, skill, artifact, parent=None):
  argv = ["runcard", "open", "--skill", skill, "--artifact", artifact]
  if parent:
    argv += ["--parent", parent]
  code, out = world.run(*argv)
  assert code == 0, out
  return out.strip()


def open_panel(world, text=QUESTIONS, name="q-test", parent=None):
  question = world.repo.parent / f"{name}.md"
  question.write_text(text, encoding="utf-8")
  card = parent or open_card(world, "judges", question)
  code, out = world.run("judges", "open", "--question", question, "--parent" if parent else "--runcard", card)
  assert code == 0, out
  return out.strip(), card, question


def panel_json(world, pid):
  return json.loads((world.artifacts / "judges" / pid / "panel.json").read_text(encoding="utf-8"))


def journal(world):
  return (world.artifacts / "journal.md").read_text(encoding="utf-8")


def record(world, pid, card, rnd, judge, answers=None, not_run=None, isolation="clean", extra=()):
  argv = ["judges", "record", "--panel", pid, "--round", rnd, "--judge", judge, "--runcard", card, *extra]
  if not_run:
    argv += ["--not-run", not_run]
  else:
    verdict = world.repo.parent / f"{pid}-r{rnd}-{judge}.md"
    verdict.write_text("".join(f"{q}: ({o})\n" for q, o in answers.items()), encoding="utf-8")
    argv += ["--verdict", verdict]
    if isolation:
      argv += ["--isolation", isolation]
  return world.run(*argv)


@pytest.mark.parametrize("text, reason", [
    ("Is it upheld?\n- (a) yes\n- (b) no\n", "line 1: expected `## Q<n> <question>` or `- (<id>) <option>`"),
    ("## Q1 Upheld?\n- (a) yes\n", "Q1: fewer than two options"),
    ("## Q1 Upheld?\n- (a) yes\n- (a) no\n", "Q1: duplicate option (a)"),
    ("## Q1 Upheld?\n- (a) yes\n- (b) no\n## Q1 Again?\n- (a) yes\n- (b) no\n", "duplicate question Q1"),
    ("- (a) yes\n## Q1 Upheld?\n- (a) yes\n- (b) no\n", "line 1: option before any question"),
    ("", "no questions"),
])
def test_question_grammar_refusals(text, reason):
  with pytest.raises(ValueError, match=re.escape(reason)):
    judges.parse_questions(text)


def test_parse_questions_several():
  parsed = judges.parse_questions(QUESTIONS)
  assert [q["id"] for q in parsed] == ["Q1", "Q2"]
  assert parsed[0]["text"] == "Is finding design-2-1 upheld?"
  assert parsed[1]["options"] == {"a": "continue one bounded round", "b": "accept the remainder", "c": "stop"}
