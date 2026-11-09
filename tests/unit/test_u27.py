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
PROSE += [("skills/using-superegm/references/claude-code-tools.md", n) for n in ("`Agent` in a builder's allow-list admits the platform's default subagents, each inheriting the session's allow-list, profile and worktree",
          "`--session-id <uuid>` names the session, its transcript `projects/<slug>/<uuid>.jsonl` under the profile")] + [("docs/getting_started.md", "`builder.max_subagent_calls` (12)")] + [
         ("skills/wave/references/builder_orders.md", n) for n in ("{{subagents}}", "<!-- subagents: You have no subagents: a builder never spawns. -->",
          "<!-- subagents Agent: You may delegate through the Agent tool, at most {{cap}} calls in this launch: a budget, not a gate; past it you finish your Steps yourself. Delegate a long test run, a wide read or a second opinion on a Step, after the Step's first commit, and keep each call under your config's `builder.stall_minutes`: the watchdog's clock runs on while a subagent works. You, never a subagent, commit and post. -->")] + [
         (p, "from superegm.traces import trace_directory, assert_child_probe") for p in ("tests/integration/test_claude.py", "tests/unit/test_claude_traces.py")]


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


def jsonl(path, items):
  """`items` as a `.jsonl` file at `path`, a dict as its JSON line, a string written as is."""
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("".join((json.dumps(i, ensure_ascii=False) if isinstance(i, dict) else i) + "\n" for i in items), encoding="utf-8")


def agent(tid, **given):
  return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "Agent", "input": {"prompt": "p", **given}}]}}


def test_subagent_calls_pairs_by_id_with_the_defaults_and_skips_bad_lines(tmp_path):
  """Round 2 (astra-1-3, astra-1-4, change-review-1-1, change-review-1-3): a call takes the child its result's
  `agentId` or its own id names, wherever that child sorts; an unlinked call takes a spare child, else none;
  a prompt holding U+2028 stays one record; a naive timestamp reads as UTC; a non-object message is skipped."""
  from superegm import traces
  sid, folder = str(uuid.uuid4()), tmp_path / "p/projects/-wt"
  jsonl(folder / f"{sid}.jsonl", [
    agent("b1", prompt="one two\u0085three"), "not json", {"type": "assistant", "message": "text"},
    agent("b2", subagent_type="Explore", description="d", model="haiku"),
    {"type": "user", "toolUseResult": {"agentId": "x2"}, "message": {"content": [{"type": "tool_result", "tool_use_id": "b2"}]}},
    agent("b3")])
  jsonl(folder / sid / "subagents/agent-b1.jsonl", [{"timestamp": "2026-11-06T10:00:01Z"}, {"timestamp": "2026-11-06T10:00:03"},
                                                   {"timestamp": "2026-11-06T10:00:05Z", "message": {"model": "claude-sonnet-4-5"}}])
  jsonl(folder / sid / "subagents/agent-x2.jsonl", [{"timestamp": "2026-11-06T09:59:58Z"}, {"timestamp": "2026-11-06T10:00:00Z"}])
  assert traces.subagent_calls(tmp_path / "p", sid) == {"count": 3, "calls": [
    {"role": "general-purpose", "description": "", "model": "claude-sonnet-4-5", "duration_s": 4.0},
    {"role": "Explore", "description": "d", "model": "haiku", "duration_s": 2.0},
    {"role": "general-purpose", "description": "", "model": None, "duration_s": 0.0}]}
  other = str(uuid.uuid4())
  jsonl(folder / f"{other}.jsonl", [agent("q1")])
  jsonl(folder / other / "subagents/agent-zz.jsonl", [{"timestamp": "2026-11-06T10:00:00Z"}, {"timestamp": "2026-11-06T10:00:01.25Z"}])
  assert traces.subagent_calls(tmp_path / "p", other)["calls"] == [{"role": "general-purpose", "description": "", "model": None, "duration_s": 1.2}]


def test_record_launch_records_no_calls_for_an_entry_without_a_session_id(world, monkeypatch):
  """Round 2 (change-review-1-2): a launch entry written before U27 carries no `session_id`: the no-file value."""
  from superegm import launch_builder
  from test_builders import seed, launches_of, UNIT
  s, card, _, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder"); monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: 4242)
  assert world.run("launch", "--runcard", card)[0] == 0 and world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)[0] == 0
  entries = launches_of(s)
  del entries[0]["session_id"]
  s.path("launches", UNIT).write_text(json.dumps({"launches": entries}), encoding="utf-8")
  Path(entries[0]["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", UNIT, "--exit", 0, "--runcard", card)[0] == 0
  assert launches_of(s)[0]["subagent_calls"] == NONE and launches_of(s)[0]["status"] == "exited 0"


@pytest.mark.parametrize("named, expect", [
  ("./hooks/extra.json", ["PreToolUse", "SessionStart"]), ({"hooks": {"Stop": []}}, ["SessionStart", "Stop"]), ([], ["SessionStart"])])
def test_hook_events_reads_hooks_json_and_the_manifest_s_string_or_inline_object(tmp_path, monkeypatch, named, expect):
  """Round 2 (change-review-1-4, codebase-details-1-5): `hooks/hooks.json` always, the manifest's files besides."""
  home, d = elephant(tmp_path, monkeypatch, ["user"], {"hooks/hooks.json": ["SessionStart"], "hooks/extra.json": ["PreToolUse"]})
  (d / ".claude-plugin").mkdir()
  (d / ".claude-plugin/plugin.json").write_text(json.dumps({"hooks": named}), encoding="utf-8")
  assert plugin_dirs([PONY], home)[0]["hooks"] == expect


@pytest.mark.parametrize("mcp", [{"mcpServers": MCP}, {"context7": "https://mcp.context7.com/mcp"}])
def test_builder_mcp_is_the_server_map_alone(world, mcp):
  """Round 2 (codebase-details-1-6): a whole `.mcp.json` or a non-object server is refused."""
  builder = {k: v for k, v in superegm.DEFAULT_CONFIG["builder"].items() if k not in ("plugins", "mcp", "max_subagent_calls")}
  set_config(world, repo=REPO, builder={**builder, "mcp": mcp})
  with pytest.raises(superegm.HandoffError, match=re.escape("builder.mcp must be an object in mcpServers form")):
    superegm.load_config(world.repo)


def test_launch_builder_refuses_a_quoted_plugin_dir_before_any_write(world, monkeypatch, tmp_path):
  """Round 2 (change-review-1-5): a plugin directory holding a quote is refused before the worktree and the files."""
  from superegm import launch_builder
  from test_builders import seed, configure, UNIT
  s, card, _, _ = seed(world)
  home, _ = elephant(tmp_path, monkeypatch, ["user"])
  quoted = tmp_path / "it's"; quoted.mkdir()
  (home / "plugins/installed_plugins.json").write_text(json.dumps(
    {"version": 2, "plugins": {PONY: [{"scope": "user", "version": "5.3.3", "installPath": str(quoted)}]}}), encoding="utf-8")
  cfg = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]
  configure(world, builder={**cfg, "plugins": [PONY]})
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder"); monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: 4242)
  assert world.run("launch", "--runcard", card)[0] == 0
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  assert code == 1 and "holds a quote" in out and not s.path("worktrees", UNIT).exists(), out
  assert not s.path("launches", f"{UNIT}_r1_mcp.json").exists() and not s.path("launches", f"{UNIT}_r1_plugins.json").exists()


@pytest.mark.parametrize("tools, present, absent", [
  (["Read"], ["Your skills, named by your allow-list: none. You have no subagents: a builder never spawns."], ["Agent tool", "{{"]),
  (["Read", "Agent"], ["at most 12 calls in this launch: a budget, not a gate"], ["You have no subagents", "{{"])])
def test_the_agent_rule_and_the_delegation_paragraph(tools, present, absent):
  from superegm.launch_builder import orders_text
  text = orders_text(tools, "/usr/local/bin/gh", 12)
  assert all(n in text for n in present) and not any(n in text for n in absent), text


from test_builders import no_graphify, which  # noqa: F401
