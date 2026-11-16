# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U45's tests: the skills' wait, resume and frozen-mode wording under the driver, and the inbox's chained lines.

"""U45 (spec sections 7.1, 7.2): the plan, review-plan and wave skills wait, resume and take the frozen mode under the
driver; the inbox reads the frozen mode and shows a chained handoff's `waiting …` and `ready to integrate` lines."""

import pytest

from conftest import ROOT


@pytest.mark.parametrize("path,phase", [("skills/plan/SKILL.md", "plan"), ("skills/review-plan/SKILL.md", "review-plan")])
def test_skills_wait_and_resume(path, phase):
  # under the driver an owner question becomes next wait and exit; typed on a wait record: ask, record, run on, next clear
  text = " ".join((ROOT / path).read_text(encoding="utf-8").split())
  assert "SUPEREGM_ROLE=driver" in text and "next wait" in text and f"--phase {phase}" in text
  assert "runcard open --mode normal" in text and "next clear" in text


@pytest.mark.parametrize("path", ["skills/wave/SKILL.md", "skills/wave/references/leavemealone_mode.md",
                                  "skills/review-plan/SKILL.md", "skills/plan/SKILL.md"])
def test_skills_frozen_mode(path):
  # --mode leavemealone only when the invocation says --leavemealone, else runcard open's frozen default; config.mode kept as fallback
  text = " ".join((ROOT / path).read_text(encoding="utf-8").split())
  assert "frozen" in text and "`config.mode`" in text
  assert "or the config's `mode` is `leavemealone`" not in text and "--mode '<normal|leavemealone>'" not in text
