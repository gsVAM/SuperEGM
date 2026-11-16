# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U89's tests: the repository reviewer's adapter and persona.

"""U89: the repository reviewer's adapter."""

import json
from conftest import ROOT
from test_skeleton import frontmatter, FINDINGS_LINE, IDS

ADAPTER = ROOT / ".claude-plugin/agents/repo-reviewer.md"
PERSONA = ROOT / "agents/repo-reviewer.md"


def test_repo_reviewer_adapter():
  # the one adapter repository reviewers and overridden built-ins dispatch through
  meta = frontmatter(ADAPTER)
  manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
  assert {k: meta[k] for k in ("name", "model", "omitClaudeMd")} == {"name": "repo-reviewer", "model": "inherit", "omitClaudeMd": True}
  assert sorted(meta["tools"]) == ["Glob", "Grep", "Read"] and "memory" not in meta
  assert "./.claude-plugin/agents/repo-reviewer.md" in manifest["agents"] and "repo-reviewer" in IDS


def test_repo_reviewer_persona():
  # the persona says only that the brief's `# Reviewer persona` is the persona and that it writes findings lines
  meta = frontmatter(PERSONA)
  body = PERSONA.read_text(encoding="utf-8")
  assert "`# Reviewer persona`" in body and FINDINGS_LINE in body and meta["name"] == "repo-reviewer"
