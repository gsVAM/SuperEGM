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


def write_skill(root: Path, name: str, frontmatter: str) -> None:
  path = root / "skills" / name / "SKILL.md"
  path.parent.mkdir(parents=True)
  path.write_text(frontmatter + "\n# Skill\n", encoding="utf-8")


@pytest.mark.parametrize("name,frontmatter,reason", [
    ("clean", "---\nname: clean\nlicense: Apache-2.0\ndisable-model-invocation: true\n"
     "description: x\n---", "effects missing"),
    ("clean", "---\nname: clean\nlicense: Apache-2.0\neffects: writes\n"
     "disable-model-invocation: true\ndescription: x\n---", "unknown effects writes"),
    ("clean", "---\nname: clean\nlicense: Apache-2.0\neffects: external\n"
     "disable-model-invocation: true\ndescription: x\n---", "effect_kinds missing"),
    ("clean", "---\nname: clean\nlicense: Apache-2.0\neffects: external\n"
     "effect_kinds: [publish, state-store]\ndisable-model-invocation: true\n"
     "description: x\n---", "unknown effect kind publish"),
    ("clean", "---\nname: clean\nlicense: Apache-2.0\neffects: external\n"
     "effect_kinds: [destructive-local, state-store]\ndescription: x\n---",
     "external but not disable-model-invocation: true"),
    ("draft", "---\nname: draft\nlicense: Apache-2.0\neffects: working-tree\n"
     "description: x\n---", "typed but not disable-model-invocation: true"),
])
def test_check_effects_refuses(tmp_path: Path, name: str, frontmatter: str, reason: str) -> None:
  write_skill(tmp_path, name, frontmatter)
  with pytest.raises(ValueError) as error:
    PACKER["check_effects"](tmp_path)
  assert str(error.value) == f"Effects: {name}: {reason}"


def test_check_effects_accepts_the_tree_and_pins_the_typed_set() -> None:
  PACKER["check_effects"](ROOT)
  assert PACKER["TYPED_SKILLS"] == frozenset(TYPED)
  assert PACKER["EFFECT_KINDS"] == ("github-write", "remote-branch", "start-session",
                                   "state-store", "destructive-local")
