# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U64's tests: the brainstorm's step that designs the SDLC workflow (spec section 3.4).

"""U64: the brainstorming skill designs the review and build workflow after the spec (spec section 3.4)."""

from pathlib import Path

import pytest


def test_workflow_step_order():
  # §3.4: after the written spec, before review-spec; areas, then commit, then doctor, probe, chain
  t = Path("skills/brainstorming/SKILL.md").read_text()
  s = t.index("## Design the SDLC Workflow")
  assert t.index("## The Written Design") < s < t.rindex("`/superegm:review-spec`")
  order = ["`reviewers.spec`", "`reviewers.integrate`", "`instructions`", "`review.rounds`", "`mode`", "`superegm builder-setup`", "commit", "`superegm doctor`", "`doctor --probe`", "`driver.chain`"]
  assert [t.index(p, s) for p in order] == sorted(t.index(p, s) for p in order)
