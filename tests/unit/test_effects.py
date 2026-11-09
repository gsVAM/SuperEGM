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
    "review-spec": ("state-store", "start-session", "github-write", "remote-branch"),
    "plan": ("state-store", "start-session", "github-write"),
    "review-plan": ("state-store", "start-session"),
    "file": ("github-write", "state-store"),
    "wave": ("start-session", "github-write", "remote-branch", "state-store"),
    "interrupt": ("state-store",),
    "clean": ("destructive-local", "state-store"),
    "finishing-a-development-branch": ("github-write", "remote-branch", "state-store"),
    "integrate": ("state-store", "start-session"),
    "judges": ("start-session", "state-store", "github-write"),
    "orient": ("state-store",),
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
  assert set(SKILLS) == set(EXTERNAL) | WORKING_TREE | {"using-superegm", "inbox"}


@pytest.mark.parametrize("skill", SKILLS)
def test_frontmatter_order_and_opening_line(skill: str) -> None:
  text = skill_text(skill)
  assert text.startswith("---\n"), f"{skill}: the frontmatter must open the file"
  fm = PACKER["read_frontmatter"](ROOT / "skills" / skill / "SKILL.md")
  effects = ("external" if skill in EXTERNAL
             else "none" if skill in ("using-superegm", "inbox") else "working-tree")
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


@pytest.mark.parametrize("skill", ["test-driven-development", "systematic-debugging",
                                   "verification-before-completion"])
def test_phase_sentence_verbatim(skill: str) -> None:
  fm = PACKER["read_frontmatter"](ROOT / "skills" / skill / "SKILL.md")
  assert PHASE_SENTENCE in fm["description"], skill
  assert "disable-model-invocation" not in fm
  assert fm["effects"] == "working-tree"


def test_verification_never_updates_snapshots_or_fixtures() -> None:
  text = skill_text("verification-before-completion")
  assert "never updates snapshots or fixtures" in text


HOOK_COMMAND = '"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd" session-start'


def run_hook(**env: str) -> subprocess.CompletedProcess:
  return subprocess.run(
      ["bash", str(ROOT / "hooks/run-hook.cmd"), "session-start"],
      env={"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/"), **env},
      capture_output=True, timeout=30)


def test_hooks_json_declares_one_session_start_command() -> None:
  hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
  assert list(hooks) == ["hooks"] and list(hooks["hooks"]) == ["SessionStart"]
  [entry] = hooks["hooks"]["SessionStart"]
  assert entry["matcher"] == "startup|clear|compact"
  [hook] = entry["hooks"]
  assert hook == {"type": "command", "command": HOOK_COMMAND, "shell": "bash", "async": False}
  for script in ("run-hook.cmd", "session-start"):
    assert os.access(ROOT / "hooks" / script, os.X_OK), script


def test_session_start_injects_using_superegm() -> None:
  result = run_hook()
  assert result.returncode == 0, result.stderr
  assert result.stderr == b""
  output = json.loads(result.stdout)
  assert list(output) == ["hookSpecificOutput"]
  inner = output["hookSpecificOutput"]
  assert list(inner) == ["hookEventName", "additionalContext"]
  assert inner["hookEventName"] == "SessionStart"
  context = inner["additionalContext"]
  assert skill_text("using-superegm").rstrip("\n") in context
  assert "'superegm:using-superegm' skill" in context
  assert "superpowers" not in context.replace("From superpowers 7.0.0 (MIT)", "")


@pytest.mark.parametrize("role", ["goldfish", "builder"])
def test_session_start_silent_under_role(role: str) -> None:
  result = run_hook(SUPEREGM_ROLE=role)
  assert (result.returncode, result.stdout, result.stderr) == (0, b"", b"")


def test_manifest_hook_hash_matches_script() -> None:
  manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
  digest = hashlib.sha256((ROOT / "hooks/session-start").read_bytes()).hexdigest()
  assert manifest["superegm"] == {"hook_sha256": digest}
  assert "hooks" not in manifest


def test_hooks_directory_is_exactly_three_files() -> None:
  names = sorted(p.name for p in (ROOT / "hooks").iterdir())
  assert names == ["hooks.json", "run-hook.cmd", "session-start"]


def test_using_superegm_dispatcher_text() -> None:
  folder = ROOT / "skills/using-superegm"
  text = skill_text("using-superegm")
  for needle in (
      "If you think there is even a 1% chance a skill might apply to what you are doing, "
      "you ABSOLUTELY MUST invoke the skill.",
      "Invoke relevant or requested skills BEFORE any response or action",
      "superegm:brainstorming first", "superegm:systematic-debugging first",
      PHASE_SENTENCE, "## Typed only", "## May be auto-invoked",
      "`references/claude-code-tools.md`"):
    assert needle in text, needle
  for skill in TYPED:
    assert f"/superegm:{skill}" in text, skill
  for skill in set(SKILLS) - TYPED:
    assert f"superegm:{skill}" in text, skill
  for banned in ("superpowers:", "You have superpowers", "SUBAGENT-STOP", "codex-tools",
                 "pi-tools", "antigravity", "hermes", "muse-tools", "Codex"):
    assert banned not in text, banned
  assert sorted(p.name for p in (folder / "references").iterdir()) == ["claude-code-tools.md"]
  reference = (folder / "references/claude-code-tools.md").read_text(encoding="utf-8")
  assert "subagent-driven-development" not in reference
  assert "SessionStart hooks run for sessions, not for Agent-tool subagents" in reference


def test_brainstorming_path_gate_and_removals() -> None:
  folder = ROOT / "skills/brainstorming"
  text = skill_text("brainstorming")
  for needle in ("`docs/specs/YYYY-MM-DD-<topic>-design.md`", "`## Units`",
                 "/superegm:review-spec", "the last H2"):
    assert needle in text, needle
  for banned in ("docs/superpowers", "Builder check", "builder-check-prompt", "Visual Companion",
                 "visual-companion", "visual companion", "writing-plans", "subagent",
                 "browser tab", "throwaway prototypes"):
    assert banned not in text, banned
  for name in ("builder-check-prompt.md", "visual-companion.md", "scripts"):
    assert not (folder / name).exists(), name


MENU = """Implementation complete. What would you like to do?

1. Push and open a pull request as the owner, for a colleague's review
2. Keep the branch as-is (I'll handle it later)

Which option?"""


def test_finishing_offers_no_merge() -> None:
  text = skill_text("finishing-a-development-branch")
  assert MENU in text
  for needle in ("Type 'discard' to confirm.", "A forced push is never offered.",
                 "superegm runcard open --skill finishing-a-development-branch --artifact",
                 "superegm runcard close", "only the owner updates <base-branch>"):
    assert needle in text, needle
  for banned in ("Merge back", "Merge Locally", "merge locally", "Merge locally", "git merge",
                 "git pull", "| Merge |", "force-push only", "Reduced 2 options",
                 "Standard 3 options"):
    assert banned not in text, banned
  assert text.count("Which option?") == 2


def test_draft_and_drift_report_edits() -> None:
  draft = ROOT / "skills/draft"
  fm = PACKER["read_frontmatter"](draft / "SKILL.md")
  assert "draft a spec from a brief when brainstorming was skipped" in fm["description"]
  text = skill_text("draft")
  for needle in ("/superegm:review-spec", "docs/specs/", "`## Units`", "/superegm:brainstorming"):
    assert needle in text, needle
  for banned in ("egm-brainstorm", "`egm-review`", "docs/designs/", "Codex", "ChatGPT"):
    assert banned not in text, banned
  template = (draft / "references/design_doc.md").read_text(encoding="utf-8")
  assert re.findall(r"^## (.+)$", template, re.MULTILINE)[-1] == "Units"
  drift = skill_text("drift-report")
  assert "{YYYY-MM-DD}_DRIFT_REPORT.md" in drift
  assert "after `/superegm:integrate`" in drift
  assert "Codex" not in drift


SWEEP = {
    "skills/test-driven-development/SKILL.md": ("superpowers:",),
    "skills/systematic-debugging/SKILL.md": ("superpowers:",),
    "skills/verification-before-completion/SKILL.md": ("superpowers:",),
    "skills/writing-skills/SKILL.md": ("superpowers:", "codex-tools", "gemini-tools", "Codex",
                                       "Copilot", "Gemini", "~/.agents/skills/"),
    "skills/using-superegm/SKILL.md": ("superpowers:", "distributions/claude"),
    "skills/brainstorming/SKILL.md": ("superpowers:",),
    "skills/finishing-a-development-branch/SKILL.md": ("superpowers:", "Superpowers created"),
    "skills/draft/SKILL.md": ("[Codex integration]", "egm-"),
    "skills/drift-report/SKILL.md": ("[Codex integration]", "egm-"),
    "hooks/session-start": ("CURSOR_PLUGIN_ROOT", "COPILOT_CLI", "MUSE_PLUGIN_ROOT",
                            "additional_context", "using-superpowers"),
}
NOTICE_MIT = "From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: "
NOTICE_APACHE = "Modified by SuperEGM (gsVAM), 2026: "


@pytest.mark.parametrize("path,banned", sorted(SWEEP.items()))
def test_no_removed_mechanism_named(path: str, banned: tuple) -> None:
  text = (ROOT / path).read_text(encoding="utf-8")
  for term in banned:
    assert term not in text.replace("superegm-", ""), f"{path}: {term}"


@pytest.mark.parametrize("path", [
    "hooks/session-start", "skills/using-superegm/SKILL.md",
    "skills/using-superegm/references/claude-code-tools.md", "skills/brainstorming/SKILL.md",
    "skills/finishing-a-development-branch/SKILL.md", "skills/test-driven-development/SKILL.md",
    "skills/systematic-debugging/SKILL.md", "skills/verification-before-completion/SKILL.md",
    "skills/writing-skills/SKILL.md",
])
def test_changed_superpowers_files_carry_notice(path: str) -> None:
  text = (ROOT / path).read_text(encoding="utf-8")
  assert NOTICE_MIT in text, path
  if path.endswith(".md"):
    assert "<!-- " + NOTICE_MIT in text and text.startswith("---\n")


@pytest.mark.parametrize("path", [
    "scripts/pack_plugin.py", "skills/draft/SKILL.md", "skills/draft/references/design_doc.md",
    "skills/drift-report/SKILL.md", "tests/unit/test_packaging.py", "tests/unit/test_harnesses.py",
])
def test_changed_apache_files_carry_notice(path: str) -> None:
  assert NOTICE_APACHE in (ROOT / path).read_text(encoding="utf-8"), path
