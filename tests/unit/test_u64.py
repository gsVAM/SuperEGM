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


@pytest.mark.parametrize("phrase", [
    "suggestion drawn from the spec",                        # each question led by its suggestion
    "changes only what the owner agrees to",
    "quick, clear task",                                     # skips the step
    "In Cowork",
    "`plan` and `wave` need `superegm doctor` to pass",
    "`--mcp`", "`--allow`",
    "model call", "only when the owner agrees",              # the probe offered, never run unasked
    "records nothing", "refuse until doctor passes",         # a skipped area
    "`~/.superegm/env`", "`0600`",                           # the driver setup offer
])
def test_workflow_step_phrases(phrase):
  # §3.4: the step's branches and promises, each a required phrase in the section
  t = Path("skills/brainstorming/SKILL.md").read_text()
  assert phrase in t[t.index("## Design the SDLC Workflow"):]


def test_using_superegm_names_the_step():
  # §3.4: one line saying the brainstorm designs the review and build workflow after the spec
  lines = [l for l in Path("skills/using-superegm/SKILL.md").read_text().splitlines() if "SDLC workflow" in l]
  assert len(lines) == 1 and "brainstorming" in lines[0] and "superegm doctor" in lines[0]
