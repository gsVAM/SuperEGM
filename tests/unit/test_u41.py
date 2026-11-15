# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U41's tests: the triage goldfish (spec section 5.2): its adapter, its persona and the foreman brief's Step 3b.

"""U41: the triage goldfish."""

import json
import pytest
from conftest import ROOT
from test_skeleton import frontmatter


def text_of(path):
  return (ROOT / path).read_text(encoding="utf-8")


def test_triage_adapter_is_zero_context_and_read_only():
  # a goldfish: no project context, read-only tools, the persona by plugin path, the docs/specs/ ban
  meta = frontmatter(ROOT / ".claude-plugin/agents/triage.md")
  adapter = text_of(".claude-plugin/agents/triage.md")
  manifest = json.loads(text_of(".claude-plugin/plugin.json"))
  assert (meta["name"], set(meta["tools"]), meta["omitClaudeMd"]) == ("triage", {"Read", "Grep", "Glob"}, True)
  assert "${CLAUDE_PLUGIN_ROOT}/agents/triage.md" in adapter and "docs/specs/" in adapter
  assert "./.claude-plugin/agents/triage.md" in manifest["agents"]
