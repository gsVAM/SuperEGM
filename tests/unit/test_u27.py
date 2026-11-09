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
from superegm.launch_builder import profile_problem
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


@pytest.mark.parametrize("layout, plugins, problem", [
  ("ok", [], None), ("ok", [PONY], None), ("skills", [], "holds skills/"), ("commands", [], "holds commands/"),
  ("no-settings", [], "lacks disableClaudeAiConnectors"), ("connectors-false", [], "lacks disableClaudeAiConnectors"),
  ("managed", [PONY], "plugin ponytail@ponytail managed in the builder profile")])
def test_profile_problem_refuses_the_amendment_7_layouts(tmp_path, monkeypatch, layout, plugins, problem):
  home, _ = elephant(tmp_path, monkeypatch, ["user"])
  profile = tmp_path / "profile"; profile.mkdir()
  layout != "no-settings" and (profile / "settings.json").write_text(json.dumps({"disableClaudeAiConnectors": layout != "connectors-false"}), encoding="utf-8")
  layout in ("skills", "commands") and (profile / layout).mkdir()
  if layout == "managed":
    (profile / "plugins").mkdir(); (profile / "plugins/installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {PONY: [{"scope": "managed"}]}}), encoding="utf-8")
  expect = f"builder profile {profile} {problem}" if problem and problem.startswith(("holds", "lacks")) else problem
  assert profile_problem(profile, plugins, home) == expect and (layout != "ok" or profile_problem(profile) is None)


PROSE = [("skills/wave/references/builder_orders.md", n) for n in ("Your skills, named by your allow-list: {{skills}}.", "invokes no skill its allow-list does not name",
          "refresh the PR body (`{{gh}} pr edit <n> --body-file <file>`) before every push")] + [
         ("skills/using-superegm/references/claude-code-tools.md", n) for n in ("`Skill(<name>)` and `Skill(<name> *)`", "`mcp__<server>__<tool>` or `mcp__<server>__*`",
          "`--plugin-dir <dir>` loads a plugin for the session", "`--mcp-config <file> --strict-mcp-config` loads that file's servers")] + [
         ("docs/getting_started.md", n) for n in ('"disableClaudeAiConnectors": true', "no `skills/` or `commands/` directory", "`builder.plugins`", "`builder.mcp`")]
ABSENT = [("skills/wave/references/builder_orders.md", n) for n in ("You have no skills", "and update the existing pull request's body")]


@pytest.mark.parametrize("path, needle, present", [(p, n, True) for p, n in PROSE] + [(p, n, False) for p, n in ABSENT])
def test_the_amendment_7_prose(path, needle, present):
  assert (needle in (ROOT / path).read_text(encoding="utf-8")) is present, (path, needle)


CALL = {"type": "assistant", "timestamp": "2026-11-06T10:00:00.000Z", "message": {"content": [{"type": "tool_use", "id": "a1", "name": "Agent",
        "input": {"subagent_type": "Explore", "description": "a wide read", "model": "haiku", "prompt": "list the callers"}}]}}
READ = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/x"}}]}}
NONE = {"count": 0, "calls": []}


def transcript(profile, sid, case):
  """A builder session's transcript under `profile`: none for `missing`; else `projects/-wt/<sid>.jsonl` holding one
  `Agent` call (`one`) or one `Read` (`none`), and for `one` the paired child's two events 12.5 s apart."""
  if case == "missing":
    return
  folder = Path(profile) / "projects/-wt"
  folder.mkdir(parents=True, exist_ok=True)
  (folder / f"{sid}.jsonl").write_text(json.dumps(CALL if case == "one" else READ) + "\n", encoding="utf-8")
  if case == "one":
    child = folder / sid / "subagents/agent-a1.jsonl"
    child.parent.mkdir(parents=True)
    events = [{"type": "user", "timestamp": "2026-11-06T10:00:01.000Z", "message": {"role": "user", "content": "list the callers"}},
              {"type": "assistant", "timestamp": "2026-11-06T10:00:13.500Z", "message": {"model": "claude-haiku-4-5", "content": []}}]
    child.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


@pytest.mark.parametrize("case, expect", [("one", {"count": 1, "calls": [{"role": "Explore", "description": "a wide read", "model": "haiku", "duration_s": 12.5}]}), ("none", NONE), ("missing", NONE)])
def test_record_launch_reads_the_subagent_calls_from_the_transcript(world, monkeypatch, tmp_path, case, expect):
  from superegm import launch_builder, traces
  from test_builders import seed, launches_of, UNIT
  sid = str(uuid.uuid4()); transcript(tmp_path / "p", sid, case)
  assert traces.subagent_calls(tmp_path / "p", sid) == expect
  s, card, _, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder"); monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: 4242)
  assert world.run("launch", "--runcard", card)[0] == 0 and world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)[0] == 0
  entry = launches_of(s)[0]
  assert uuid.UUID(entry["session_id"]).version == 4 and "subagent_calls" not in entry
  transcript(Path(json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]["profile_dir"]), entry["session_id"], case)
  Path(entry["result_file"]).write_text("{}\n", encoding="utf-8"); Path(entry["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", UNIT, "--exit", 0, "--runcard", card)[0] == 0
  assert launches_of(s)[0]["subagent_calls"] == expect and Path(entry["result_file"]).read_text(encoding="utf-8") == "{}\n"


from test_builders import no_graphify, which  # noqa: F401
