# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U27

"""U27 (spec section 11.1): the builder's plugins and MCP servers passed per launch, the amendment-7
profile refusals, the prose, and the `Agent` rule with the subagent calls read from the transcript."""

import json, re, uuid
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import init
from conftest import ROOT, REPO, set_config

PONY, MCP = "ponytail@ponytail", {"context7": {"type": "http", "url": "https://mcp.context7.com/mcp"}}


@pytest.mark.parametrize("key, value, message", [
  ("plugins", [PONY, "context7@claude-plugins-official"], None), ("plugins", ["ponytail"], "builder.plugins must be a list of <name>@<marketplace> ids"),
  ("mcp", MCP, None), ("mcp", [], "builder.mcp must be an object in mcpServers form"), ("allowed_tools", "Read", "builder.allowed_tools must be a list of strings"),
  ("max_subagent_calls", 0, "config: builder.max_subagent_calls: a positive integer")])
def test_builder_plugins_and_mcp_keys(world, key, value, message):
  assert superegm.DEFAULT_CONFIG["builder"]["plugins"] == [] and superegm.DEFAULT_CONFIG["builder"]["mcp"] == {}
  assert {"Bash(gh pr view:*)", "Bash(pytest:*)"} <= set(superegm.DEFAULT_CONFIG["builder"]["allowed_tools"])
  assert '"disableClaudeAiConnectors": true' in init.STEPS and "builder.plugins" in init.STEPS and "builder.mcp" in init.STEPS
  builder = {k: v for k, v in superegm.DEFAULT_CONFIG["builder"].items() if k not in ("plugins", "mcp", "max_subagent_calls")}
  set_config(world, repo=REPO, builder={**builder, key: value})
  if message:
    with pytest.raises(superegm.HandoffError, match=re.escape(message)):
      superegm.load_config(world.repo)
    return
  loaded, expect = superegm.load_config(world.repo)["builder"], {"plugins": [], "mcp": {}, "max_subagent_calls": 12, key: value}
  assert {k: loaded[k] for k in expect} == expect


from test_builders import no_graphify, which  # noqa: F401
