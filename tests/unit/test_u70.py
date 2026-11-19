import re
from pathlib import Path

import pytest


@pytest.mark.parametrize("skill, phrase", [(s, p) for s in ("plan", "review-plan", "file") for p in (
  "runcard open --mode normal", "as the owner's", "`by` and `at`", "superegm next clear", "next wait", "cannot be mapped", "by hand still counts")]
  + [("review-plan", "stops, write a wait record")])
def test_driven_skills_act_on_an_answered_record(skill, phrase):
  # a driven run on an answered chain record is the owner's answer; an unmappable one is asked again
  assert phrase in Path(f"skills/{skill}/SKILL.md").read_text()


@pytest.mark.parametrize("phrase", [
  "next wait --phase file", "Create these <n> issues and <m> links", "handoff_dryrun.md", "sha256", "redo the dry run", "ask again"])
def test_file_creates_only_on_a_matching_sha256(phrase):
  # the sha256 is of handoff_dryrun.md's bytes, carried in the question
  assert phrase in Path("skills/file/SKILL.md").read_text()


@pytest.mark.parametrize("path", ["skills/wave/SKILL.md", "skills/integrate/SKILL.md", "skills/using-superegm/SKILL.md"])
def test_merge_lines_point_to_the_inbox(path):
  # the merge happens in the inbox; the admin-bypass literal stays
  line = next(l for l in Path(path).read_text().splitlines() if "gh pr merge --admin" in l)
  assert "inbox" in line


@pytest.mark.parametrize("path", [
  "skills/plan/SKILL.md", "skills/review-plan/SKILL.md", "skills/file/SKILL.md", "skills/wave/SKILL.md",
  "skills/integrate/SKILL.md", "skills/wave/references/decision_points.md"])
def test_no_skill_asks_for_a_paste(path):
  # the owner answers in the inbox, never by a pasted command or a posted comment
  assert not re.search(r"(?i)\b(paste|the owner posts|owner types)\b", Path(path).read_text())


def test_inbox_is_typed_and_the_rule_is_one_line():
  # inbox joins the typed list; one line says no skill asks the owner to paste
  text = Path("skills/using-superegm/SKILL.md").read_text()
  typed, auto = text.split("## Typed only")[1].split("## May be auto-invoked")
  assert "/superegm:inbox" in typed and "/superegm:inbox" not in auto.split("## Four rules")[0]
  assert sum("paste" in l and "inbox" in l for l in text.splitlines()) == 1
