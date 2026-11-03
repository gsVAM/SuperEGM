# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
"""U01: the file set, names, personas, manifests, workflow, README and notices."""
import json
from pathlib import Path
import re
from xml.etree import ElementTree

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
IDS = ("design", "zoom-out", "comprehension", "codebase-details", "readiness", "structural",
       "style", "change-review", "judge", "foreman")
SKILLS = ("brainstorming", "draft", "review-spec", "plan", "review-plan", "file", "wave", "interrupt",
          "clean", "finishing-a-development-branch", "integrate", "judges", "test-driven-development",
          "systematic-debugging", "verification-before-completion", "writing-skills",
          "using-superegm", "drift-report")


def frontmatter(path: Path) -> dict:
  return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


EGM_KEPT = (
    "LICENSE", "pyproject.toml", ".gitignore", ".claude-plugin/icon.png", "tests/conftest.py",
    "skills/draft/references/design_doc.md",
    "skills/review-spec/references/review_loop.md", "skills/review-spec/references/resolve.md",
    "skills/plan/scripts/superegm.py", "skills/plan/references/handoff_plan.md",
    "skills/plan/references/issue_template.md", "skills/plan/references/handoff_config.md",
    "skills/wave/references/foreman_brief.md",
    "resources/README.md", "resources/astra_lane.md", "resources/review_panels.md",
    "resources/execution_instructions.md",
    "tests/unit/test_helper.py", "tests/unit/test_astra_fork.py", "tests/unit/test_harnesses.py",
    "tests/unit/test_frontmatter.py", "tests/unit/test_link_integrity.py",
    "tests/unit/test_markdown_tables.py", "tests/unit/test_scenario_coverage.py",
    "tests/unit/test_skill_load_limits.py", "tests/unit/test_claude_traces.py",
    "tests/integration/test_claude.py",
) + tuple(f"skills/{s}/{f}" for s in ("draft", "drift-report", "review-spec", "plan", "wave")
          for f in ("SKILL.md", "assets/icon.svg", "test_scenarios.yaml")
) + tuple(f"docs/{n}.md" for n in ("index", "getting_started", "claude", "faq", "privacy", "releases")
) + tuple(f"resources/document_standards/{n}-standard.md" for n in (
    "feature-spec", "heilmeier", "implementation-readiness", "re-implementation", "zoom-out", "handoff")
) + tuple(f"{d}/{i}.md" for d in ("agents", ".claude-plugin/agents") for i in IDS[:8])
NOT_KEPT = (
    "distributions", ".codex-plugin", ".agents", "site", "assets", "vendor", "docs/designs",
    "docs/codex.md", "docs/harnesses.md", "docs/directory.md", "docs/assets", "TESTING.md",
    "CONTRIBUTING.md", "AI_POLICY.md", "AGENTS.md", "requirements-dev.txt",
    "agents/synthesizer.md", "agents/bootstrap_orchestrator.md",
    ".claude-plugin/agents/synthesizer.md", ".claude-plugin/agents/bootstrap_orchestrator.md",
    "tests/unit/test_egm_handoff.py", "tests/unit/test_codex_traces.py",
    "tests/integration/test_codex.py",
)


@pytest.mark.parametrize("path", EGM_KEPT)
def test_egm_file_is_kept_under_its_section_14_name(path: str) -> None:
  assert (ROOT / path).is_file(), path


def test_nothing_not_kept_and_no_source_tree_is_in_the_repository() -> None:
  present = [p for p in NOT_KEPT if (ROOT / p).exists()]
  present += [str(p.relative_to(ROOT)) for pattern in
              ("skills/egm-*", "skills/*/agents/openai.yaml", "skills/*/TEST.md")
              for p in ROOT.glob(pattern)]
  assert present == []
  for doc in ("docs/index.md", "docs/getting_started.md"):
    text = (ROOT / doc).read_text(encoding="utf-8")
    assert "codex.md" not in text and "harnesses.md" not in text, doc
  for skill in ROOT.glob("skills/*/SKILL.md"):
    assert "[Codex integration]" not in skill.read_text(encoding="utf-8"), skill


SP_KEPT = (
    "LICENSE-MIT", "skills/brainstorming/SKILL.md", "skills/finishing-a-development-branch/SKILL.md",
    "skills/test-driven-development/SKILL.md", "skills/test-driven-development/writing-good-tests.md",
    "skills/systematic-debugging/SKILL.md", "skills/systematic-debugging/root-cause-tracing.md",
    "skills/systematic-debugging/find-polluter.sh", "skills/verification-before-completion/SKILL.md",
    "skills/writing-skills/SKILL.md", "skills/writing-skills/anthropic-best-practices.md",
    "skills/writing-skills/testing-skills-with-subagents.md", "skills/writing-skills/render-graphs.js",
    "skills/writing-skills/references/skill_discovery_optimization.md",
    "skills/using-superegm/SKILL.md", "skills/using-superegm/references/claude-code-tools.md",
    "skills/plan/references/writing_plans.md", "skills/wave/references/builder_orders.md",
)
SP_NOT_KEPT = (
    "skills/brainstorming/scripts", "skills/brainstorming/visual-companion.md",
    "skills/brainstorming/builder-check-prompt.md", "skills/using-superpowers", "skills/writing-plans",
    "skills/executing-plans", "skills/subagent-driven-development", "skills/requesting-code-review",
    "skills/receiving-code-review", "skills/dispatching-parallel-agents", "skills/using-git-worktrees",
    "skills/diagnosing-superpowers",
) + tuple(f"skills/using-superegm/references/{h}-tools.md"
          for h in ("codex", "gemini", "pi", "antigravity", "hermes", "muse"))


def test_superpowers_files_are_kept_under_the_section_14_names() -> None:
  missing = [p for p in SP_KEPT if not (ROOT / p).is_file()]
  present = [p for p in SP_NOT_KEPT if (ROOT / p).exists()]
  assert (missing, present) == ([], [])
  licence = (ROOT / "LICENSE-MIT").read_text(encoding="utf-8")
  assert licence.startswith("MIT License") and "Copyright (c) 2025 Jesse Vincent" in licence
  using = (ROOT / "skills/using-superegm/SKILL.md").read_text(encoding="utf-8")
  assert using.count("-tools.md") == 1 and "references/claude-code-tools.md" in using
  writing = (ROOT / "skills/writing-skills/SKILL.md").read_text(encoding="utf-8")
  assert "codex-tools.md" not in writing and "gemini-tools.md" not in writing
  assert "## Skill Discovery Optimization (SDO)" not in writing
  assert "references/skill_discovery_optimization.md" in writing
  assert len(writing.split("---", 2)[2].strip().encode("utf-8")) <= 24_000


STUBS = {  # §14 effects of the new typed skills
    "review-plan": ["state-store", "start-session"], "file": ["github-write", "state-store"],
    "interrupt": ["state-store"], "clean": ["destructive-local", "state-store"],
    "integrate": ["state-store", "start-session"],
    "judges": ["start-session", "state-store", "github-write"],
}
HARNESS = "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first."


@pytest.mark.parametrize("skill", SKILLS)
def test_every_section_14_skill_folder_is_complete(skill: str) -> None:
  folder = ROOT / "skills" / skill
  assert (folder / "SKILL.md").is_file() and (folder / "test_scenarios.yaml").is_file()
  svg = ElementTree.parse(folder / "assets/icon.svg").getroot()
  assert svg.get("viewBox") == "0 0 24 24" and svg.findtext("{http://www.w3.org/2000/svg}title")
  if skill in STUBS:
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    meta = frontmatter(folder / "SKILL.md")
    assert text.startswith("---\n") and HARNESS in text
    assert list(meta) == ["name", "license", "effects", "effect_kinds",
                          "disable-model-invocation", "description"]
    assert meta["name"] == skill and meta["license"] == "Apache-2.0"
    assert meta["effects"] == "external" and meta["effect_kinds"] == STUBS[skill]
    assert meta["disable-model-invocation"] is True and meta["description"].strip()


@pytest.mark.parametrize("skill", SKILLS)
def test_skill_name_is_its_folder_name(skill: str) -> None:
  assert frontmatter(ROOT / "skills" / skill / "SKILL.md")["name"] == skill


@pytest.mark.parametrize("id_", IDS)
def test_adapter_and_persona_carry_the_section_14_id(id_: str) -> None:
  adapter = ROOT / ".claude-plugin/agents" / f"{id_}.md"
  meta = frontmatter(adapter)
  assert meta["name"] == id_ == frontmatter(ROOT / "agents" / f"{id_}.md")["name"]
  assert meta["omitClaudeMd"] is True and meta["model"] == "inherit" and "memory" not in meta
  expected = ["Agent", "Bash", "Read", "Grep", "Glob"] if id_ == "foreman" else ["Read", "Grep", "Glob"]
  assert sorted(meta["tools"]) == sorted(expected)
  assert f"${{CLAUDE_PLUGIN_ROOT}}/agents/{id_}.md" in adapter.read_text(encoding="utf-8")
  assert sorted(p.stem for p in ROOT.glob(".claude-plugin/agents/*.md")) == sorted(IDS)


FINDINGS_LINE = "<reviewer>-<round>-<n> | high|medium|low | <location> | regression: yes|no | <claim>"


@pytest.mark.parametrize("id_", IDS[:8])
def test_persona_output_section_is_the_findings_line(id_: str) -> None:
  text = (ROOT / "agents" / f"{id_}.md").read_text(encoding="utf-8")
  assert FINDINGS_LINE in text.split("# Output Format", 1)[1]
  assert not re.search(r"Blocker|Major|Nit|🔴|🟡|🟢", text), id_


def read_json(path: str) -> dict:
  return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_manifests_name_superegm_1_0_0() -> None:
  portable, manifest = read_json("plugin.json"), read_json(".claude-plugin/plugin.json")
  assert (portable["name"], portable["version"], portable["license"]) == ("superegm", "1.0.0", "Apache-2.0")
  assert "extensions" not in portable and "hooks" not in manifest
  for key in ("name", "version", "description", "author", "homepage", "repository", "license"):
    assert manifest[key] == portable[key], key
  assert portable["repository"] == "https://github.com/gsVAM/superegm"
  assert manifest["icon"] == "./.claude-plugin/icon.png"
  assert sorted(manifest["agents"]) == sorted(f"./.claude-plugin/agents/{i}.md" for i in IDS)
  market = read_json(".claude-plugin/marketplace.json")
  assert market["name"] == "superegm" and [p["name"] for p in market["plugins"]] == ["superegm"]
  assert market["plugins"][0]["source"] == "./"
  for path in ("plugin.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
    text = (ROOT / path).read_text(encoding="utf-8").lower()
    assert not any(w in text for w in ("bootstrap", "synthesizer", "openai", "codex")), path
