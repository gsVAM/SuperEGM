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


@pytest.mark.parametrize("phrase", [
    "before you run doctor or the probe again",               # a fix after a failed probe is committed too
    "`private_key_env`", "`builder.gh_token_env`", "`builder.mcp`",  # area 7 lists every credential name
    "`.mcp.json`",                                           # area 5 offers the owner's server names
    "the builder check",                                     # the step follows the builder check's edits
    "skip the walk",                                         # Cowork's skip is stated before the walk
])
def test_workflow_step_review_round_1(phrase):
  # round 1 review: wording the section must carry beyond the Step's phrases
  t = Path("skills/brainstorming/SKILL.md").read_text()
  assert phrase in t[t.index("## Design the SDLC Workflow"):t.index("## The Gate")]


def test_workflow_step_commits_and_gate():
  # round 1 review: the area-6 fix commit and the area-7 chain commit are each instructed; the gate and the size table name the step
  t = Path("skills/brainstorming/SKILL.md").read_text()
  s, g = t.index("## Design the SDLC Workflow"), t.index("## The Gate")
  six, seven = t.index("6. `superegm doctor`", s), t.index("7. The chain", s)
  assert "commit each fix by path" in t[six:seven] and "commit it" in t[seven:g]
  assert "In Cowork" in t[s:six].split("1. Reviewers")[0]
  assert "SDLC workflow" in t[g:t.index("## Red Flags")]
  assert "SDLC workflow" in t[t.index("| A project with a written design"):t.index("If it grows mid-task")]


def test_using_superegm_line_follows_the_rule():
  # round 1 review: the line comes after "Then announce", names the chain, and does not end the step at doctor
  t = Path("skills/using-superegm/SKILL.md").read_text()
  line = next(l for l in t.splitlines() if "SDLC workflow" in l)
  assert t.index("Then announce") < t.index(line) and "chain" in line and "ending at" not in line
