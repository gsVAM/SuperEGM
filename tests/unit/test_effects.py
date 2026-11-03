# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
"""The hook, the effects frontmatter and the section 14 skill edits (U02)."""
import hashlib
import json
import os
import re
import runpy
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKER = runpy.run_path(str(ROOT / "scripts/pack_plugin.py"))
SKILLS = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))
EXTERNAL = {
    "review-spec": ("state-store", "start-session"),
    "plan": ("state-store", "start-session", "github-write"),
    "review-plan": ("state-store", "start-session"),
    "file": ("github-write", "state-store"),
    "wave": ("start-session", "github-write", "remote-branch", "state-store"),
    "interrupt": ("state-store",),
    "clean": ("destructive-local", "state-store"),
    "finishing-a-development-branch": ("github-write", "remote-branch", "state-store"),
    "integrate": ("state-store", "start-session"),
    "judges": ("start-session", "state-store", "github-write"),
}
WORKING_TREE = {"brainstorming", "draft", "drift-report", "test-driven-development",
                "systematic-debugging", "verification-before-completion", "writing-skills"}
TYPED = set(EXTERNAL) | {"draft", "drift-report"}
FROM_SUPERPOWERS = {"brainstorming", "finishing-a-development-branch", "using-superegm",
                    "test-driven-development", "systematic-debugging",
                    "verification-before-completion", "writing-skills"}
HARNESS_LINE = "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first."
PHASE_SENTENCE = ("Only for a filed unit on its branch or for an owner-requested fix on a "
                  "branch; never during brainstorm, spec or plan.")


def skill_text(skill: str) -> str:
  return (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")


def test_skill_set_is_section_14() -> None:
  assert set(SKILLS) == set(EXTERNAL) | WORKING_TREE | {"using-superegm"}


@pytest.mark.parametrize("skill", SKILLS)
def test_frontmatter_order_and_opening_line(skill: str) -> None:
  text = skill_text(skill)
  assert text.startswith("---\n"), f"{skill}: the frontmatter must open the file"
  fm = PACKER["read_frontmatter"](ROOT / "skills" / skill / "SKILL.md")
  effects = ("external" if skill in EXTERNAL
             else "none" if skill == "using-superegm" else "working-tree")
  expected = ["name", "license", "effects"]
  if effects == "external":
    expected.append("effect_kinds")
  if skill in TYPED:
    expected.append("disable-model-invocation")
  expected.append("description")
  assert list(fm) == expected, f"{skill}: keys {list(fm)}"
  assert fm["name"] == skill
  assert fm["license"] == ("MIT" if skill in FROM_SUPERPOWERS else "Apache-2.0")
  assert fm["effects"] == effects
  if effects == "external":
    assert fm["effect_kinds"] == "[" + ", ".join(EXTERNAL[skill]) + "]"
    assert "state-store" in EXTERNAL[skill]
  if skill in TYPED:
    assert fm["disable-model-invocation"] == "true"
  assert fm["description"].strip()
  assert text.count(HARNESS_LINE) == 1, f"{skill}: harness line must appear once"
