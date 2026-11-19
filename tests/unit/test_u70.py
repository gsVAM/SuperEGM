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
