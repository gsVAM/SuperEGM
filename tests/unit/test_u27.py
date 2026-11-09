# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U27

"""U27 (spec section 11.1): the builder's plugins and MCP servers passed per launch, the amendment-7
profile refusals, the prose, and the `Agent` rule with the subagent calls read from the transcript."""

import json, re, uuid
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import init
from superegm.launch_builder import plugin_dirs, elephant_profile
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


def elephant(tmp_path, monkeypatch, scopes, hooks=None, manifest=False):
  """The elephant's profile under `tmp_path` (`CLAUDE_CONFIG_DIR`): PONY installed at `scopes`, disabled, its hook files
  `rel: events` under its directory, named by its manifest when `manifest`. Returns `(home, dir)`."""
  home = tmp_path / "elephant"
  monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
  d = home / "plugins/cache/ponytail/ponytail/5.3.3"
  d.mkdir(parents=True, exist_ok=True)
  (home / "plugins/installed_plugins.json").write_text(json.dumps(
    {"version": 2, "plugins": {PONY: [{"scope": s, "version": "5.3.3", "installPath": str(d)} for s in scopes]}}), encoding="utf-8")
  (home / "settings.json").write_text(json.dumps({"enabledPlugins": {PONY: False}}), encoding="utf-8")
  for rel, events in (hooks or {}).items():
    (d / rel).parent.mkdir(parents=True, exist_ok=True)
    (d / rel).write_text(json.dumps({"hooks": {event: [] for event in events}}), encoding="utf-8")
  if manifest:
    (d / ".claude-plugin").mkdir(exist_ok=True)
    (d / ".claude-plugin/plugin.json").write_text(json.dumps({"hooks": [f"./{rel}" for rel in hooks or {}]}), encoding="utf-8")
  return home, d


THREE = ["SessionStart", "SubagentStart", "UserPromptSubmit"]


@pytest.mark.parametrize("scopes, hooks, manifest, expect", [
  (["user", "project"], {"hooks/hooks.json": THREE}, False, THREE),
  (["user"], {"hooks/claude-codex-hooks.json": THREE, "hooks/claude-band.json": []}, True, THREE), (["user"], {}, False, []),
  (["project"], {}, False, "plugin ponytail@ponytail not installed"), ([], {}, False, "plugin ponytail@ponytail not installed")])
def test_plugin_dirs_resolves_the_user_entry_and_hook_events(tmp_path, monkeypatch, scopes, hooks, manifest, expect):
  home, d = elephant(tmp_path, monkeypatch, scopes, hooks, manifest)
  assert elephant_profile() == home
  if isinstance(expect, str):
    with pytest.raises(superegm.HandoffError, match=re.escape(expect)):
      plugin_dirs([PONY], home)
    return
  assert plugin_dirs([PONY], home) == [{"id": PONY, "version": "5.3.3", "dir": str(d), "hooks": expect}]
  monkeypatch.delenv("CLAUDE_CONFIG_DIR"); monkeypatch.setenv("HOME", str(tmp_path))
  assert elephant_profile() == tmp_path / ".claude"


from test_builders import no_graphify, which  # noqa: F401
