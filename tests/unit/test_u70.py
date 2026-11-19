import re
from pathlib import Path

import pytest


@pytest.mark.parametrize("skill, phrase", [(s, p) for s in ("plan", "review-plan", "file") for p in (
  "runcard open --mode normal", "as the owner's", "`by` and `at`", "superegm next clear", "next wait", "cannot be mapped", "by hand still counts")]
  + [("review-plan", "stops, write a wait record")])
def test_driven_skills_act_on_an_answered_record(skill, phrase):
  # a driven run on an answered chain record is the owner's answer; an unmappable one is asked again
  assert phrase in Path(f"skills/{skill}/SKILL.md").read_text()
