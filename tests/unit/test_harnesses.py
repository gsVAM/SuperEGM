# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0
# Modified by the elephant-goldfish-model Astra fork (gsVAM), 2026: the marketplace name.
# Modified by SuperEGM (gsVAM), 2026: one host; section 14 reviewer ids; superpowers skills carry no harness line yet.

"""Offline packaging and isolation contracts for shared and host manifests."""

import json
from pathlib import Path
import re
import runpy
from xml.etree import ElementTree

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
NAME_RE = r"(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?"
COMPATIBILITY_MANIFESTS = (".claude-plugin/plugin.json",)
MARKETPLACES = (".claude-plugin/marketplace.json",)
SUPERPOWERS_SKILLS = ("brainstorming", "finishing-a-development-branch", "test-driven-development",
                      "systematic-debugging", "verification-before-completion", "writing-skills",
                      "using-superegm")
REVIEWERS = (
    "design", "zoom-out", "comprehension", "codebase-details", "readiness",
    "structural", "style", "change-review", "judge",
)




def read_json(path: str) -> dict:
  return json.loads((ROOT / path).read_text(encoding="utf-8"))


def frontmatter(path: Path) -> dict:
  return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def test_portable_manifest_schema() -> None:
  # The $schema key is deliberately omitted: omp (Oh My Pi) routes manifests
  # that declare the agent-plugins 1.0.0 schema to its strict validator, which
  # rejects the skills' disable-model-invocation frontmatter field.
  manifest = read_json("plugin.json")
  assert re.fullmatch(NAME_RE, manifest["name"])
  assert re.fullmatch(r"\d+\.\d+\.\d+(-pre\.[1-9]\d*)?", manifest["version"])




@pytest.mark.parametrize("path", COMPATIBILITY_MANIFESTS)
def test_compatibility_metadata_matches_root(path: str) -> None:
  canonical = read_json("plugin.json")
  manifest = read_json(path)
  for field in ("name", "version", "description"):
    assert manifest[field] == canonical[field], f"{path}: {field} drift"
  for field in ("author", "homepage", "repository", "license"):
    if field in manifest:
      assert manifest[field] == canonical[field], f"{path}: {field} drift"
  if "interface" in manifest:
    assert manifest["interface"]["developerName"] == canonical["author"]["name"]


@pytest.mark.parametrize("path", MARKETPLACES)
def test_marketplace_resolves_shared_package(path: str) -> None:
  canonical = read_json("plugin.json")
  marketplace = read_json(path)
  assert marketplace["name"] == "superegm"
  assert len(marketplace["plugins"]) == 1
  entry = marketplace["plugins"][0]
  assert entry["name"] == canonical["name"]
  assert (ROOT / entry["source"]).resolve() == ROOT
  if "description" in entry:
    assert entry["description"] == canonical["description"]


@pytest.mark.parametrize("name", REVIEWERS)
def test_claude_reviewers_are_read_only_with_fresh_context(name: str) -> None:
  adapter = ROOT / ".claude-plugin/agents" / f"{name}.md"
  config = frontmatter(adapter)
  assert isinstance(config["tools"], list)
  assert set(config["tools"]) == {"Read", "Grep", "Glob"}
  assert config["model"] == "inherit"
  assert config["omitClaudeMd"] is True
  assert "memory" not in config
  assert f"${{CLAUDE_PLUGIN_ROOT}}/agents/{name}.md" in adapter.read_text()
  canonical = frontmatter(ROOT / "agents" / f"{name}.md")
  assert canonical["name"] == config["name"]
  assert "tools" not in canonical
  assert "omitClaudeMd" not in canonical






def test_claude_permissions_remain_under_user_control() -> None:
  """Bundled resources must not carry an automatic permission override."""
  manifest = read_json(".claude-plugin/plugin.json")
  assert "hooks" not in manifest
  assert not (ROOT / ".claude-plugin/hooks/allow_plugin_reads.sh").exists()


def test_claude_manifest_agents_and_shared_personas_resolve() -> None:
  paths = read_json(".claude-plugin/plugin.json")["agents"]
  assert all((ROOT / path).is_file() for path in paths)
  personas = [frontmatter(p)["name"] for p in (ROOT / "agents").glob("*.md")]
  assert len(personas) == len(set(personas)), "Ambiguous persona name"


def test_bundled_prompt_dependencies_and_harness_guides() -> None:
  assert (ROOT / "docs/claude.md").is_file()
  skills = list((ROOT / "skills").glob("*/SKILL.md"))
  for skill in skills:
    if skill.parent.name in SUPERPOWERS_SKILLS:
      continue
    text = skill.read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}/docs/claude.md" in text

  prompts = skills + list((ROOT / "agents").glob("*.md"))
  for prompt in prompts:
    for target in re.findall(
        r"`((?:agents|resources|references)/[^`\s]+\.md)`",
        prompt.read_text(encoding="utf-8"),
    ):
      if any(char in target for char in "{}[]<>"):
        continue
      base = prompt.parent if target.startswith("references/") else ROOT
      assert (base / target).is_file(), f"{prompt}: missing {target}"


def test_artifact_directory_override_is_documented_for_each_harness() -> None:
  # The models match this exact line in the user's prompt or instruction file.
  marker = "EGM artifact directory: "
  for guide in ("docs/claude.md",):
    text = " ".join((ROOT / guide).read_text(encoding="utf-8").split())
    assert marker in text, f"{guide} does not document `{marker}<path>`"
