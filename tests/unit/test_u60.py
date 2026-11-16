"""U60: the builder probe, `superegm doctor --probe` (spec 1.2.1 section 3.3)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import superegm
from superegm import DEFAULT_CONFIG
from conftest import set_config


WRAPPER_BEFORE_REFACTOR = (
    "SUPEREGM_EXIT='/result.json.exit'; trap 'echo stalled > \"$SUPEREGM_EXIT\"; exit' TERM; "
    "cd '/wt' && env -u GIT_ASKPASS -u SSH_ASKPASS -u GITHUB_TOKEN -u CLAUDE_CODE_EFFORT_LEVEL CLAUDE_CONFIG_DIR='/p' "
    "ENABLE_CLAUDEAI_MCP_SERVERS=false GH_TOKEN=\"$SUPEREGM_BUILDER_TOKEN\" "
    "SUPEREGM_ROLE=builder SUPEREGM_RUNCARD='wave-0001' {pairs} "
    "claude -p \"$(cat '/prompt.md')\" --session-id 's1' --model 'claude-opus-5-5' --effort 'medium' --permission-mode 'acceptEdits' "
    "--setting-sources user --plugin-dir '/c/a/1' --plugin-dir '/c/b/2' --mcp-config '/m.json' --strict-mcp-config "
    "--allowedTools 'Read,Bash(pytest:*)' --output-format json > '/result.json'; echo $? > '/result.json.exit'")


def probe_world(world, monkeypatch, tmp_path, events=(), exit_code=0, mcp=None):
  """A repository whose config names a builder profile under `tmp_path`, doctor's own checks stubbed to nothing, and a
  fake `claude` on PATH that records its argv, its cwd and its prompt, then prints `events` as stream-json lines."""
  from superegm import doctor
  profile = tmp_path / "profile"
  profile.mkdir()
  current = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))
  set_config(world, repo=current["repo"], builder={"profile_dir": str(profile), "mcp": mcp or {}})
  monkeypatch.setattr(doctor, "checks", lambda config, repo_root, token: [])
  fake = tmp_path / "fakebin"
  fake.mkdir()
  record = tmp_path / "claude-calls.jsonl"
  events_file = tmp_path / "claude-events.json"
  events_file.write_text(json.dumps(list(events)), encoding="utf-8")
  script = fake / "claude"
  script.write_text(
      f"#!{sys.executable}\n"
      "import json, os, sys\n"
      f"with open({str(record)!r}, 'a') as f:\n"
      "  f.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}) + '\\n')\n"
      f"for event in json.load(open({str(events_file)!r})):\n"
      "  print(json.dumps(event))\n"
      f"sys.exit({exit_code})\n", encoding="utf-8")
  script.chmod(0o755)
  monkeypatch.setenv("PATH", f"{fake}:{os.environ['PATH']}")
  spawned = []
  real_run = subprocess.run

  def spy(argv, *args, **kwargs):
    if isinstance(argv, list) and "claude" in argv:
      spawned.append({"argv": list(argv), "cwd": kwargs.get("cwd")})
    return real_run(argv, *args, **kwargs)
  monkeypatch.setattr(subprocess, "run", spy)
  return profile, record, spawned


def calls(record: Path) -> list:
  return [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()] if record.is_file() else []


def test_probe_uses_the_launch_flags(world, monkeypatch, tmp_path):
  # §3.3: one function builds the launch's flags; the probe adds only its own tail, no token, issue or worktree
  from superegm.launch_builder import builder_flags, command_line, launched_pairs
  cfg = {"builder": {**DEFAULT_CONFIG["builder"], "profile_dir": "/p"}}
  pair = superegm.tier_pair(cfg, "doable")
  launch_args = (cfg, "/wt", "/prompt.md", "/result.json", "wave-0001", ["Read", "Bash(pytest:*)"], "/usr/local/bin/gh", "b", "b@x",
                 ["/c/a/1", "/c/b/2"], Path("/m.json"), pair)
  pairs = " ".join(f"{k}='{v}'" for k, v in launched_pairs("/usr/local/bin/gh", "b", "b@x"))
  wrapper_before_refactor = WRAPPER_BEFORE_REFACTOR.format(pairs=pairs)
  assert command_line(*launch_args, session_id="s1") == wrapper_before_refactor
  env_words, claude_args = builder_flags(cfg, ["Read", "Bash(pytest:*)"], ["/c/a/1", "/c/b/2"], Path("/m.json"), pair)
  assert claude_args == ["--model", "claude-opus-5-5", "--effort", "medium", "--permission-mode", "acceptEdits", "--setting-sources", "user",
                         "--plugin-dir", "/c/a/1", "--plugin-dir", "/c/b/2", "--mcp-config", "/m.json", "--strict-mcp-config",
                         "--allowedTools", "Read,Bash(pytest:*)"]

  profile, record, spawned = probe_world(world, monkeypatch, tmp_path)
  code, out = world.run("doctor", "--probe")
  assert len(spawned) == 1, out
  argv = spawned[0]["argv"]
  assert argv[0] == "env"
  at = argv.index("claude")
  probe_env, probe_argv = argv[1:at], argv[at:]
  config = superegm.load_config(world.repo)
  from superegm.launch_builder import allowed_tools
  import shutil
  tools = [t for t in allowed_tools(config["builder"]["allowed_tools"], "superegm/probe", "", shutil.which("gh") or "gh")
           if not t.startswith("Bash(git push ")]
  mcp_file = Path(spawned[0]["cwd"]) / "probe-mcp.json"
  env_words, claude_args = builder_flags(config, tools, [], mcp_file, (config["builder"]["model"], config["builder"]["effort"]))
  assert probe_argv[:2] == ["claude", "-p"]
  assert probe_argv[-5:] == ["--output-format", "stream-json", "--verbose", "--max-turns", "5"]
  assert probe_argv[3:-5] == claude_args and probe_env == env_words
  assert "GH_TOKEN" not in " ".join(probe_env) and "SUPEREGM_RUNCARD" not in " ".join(probe_env)
  assert "ENABLE_CLAUDEAI_MCP_SERVERS=false" in probe_env and "--strict-mcp-config" in probe_argv
  assert f"CLAUDE_CONFIG_DIR={profile}" in probe_env
  assert out.rstrip().endswith("probe: session ok") and code == 0, out
  assert not os.path.exists(spawned[0]["cwd"])


READ_CALL = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "x"}}]}}
CLEAN_RESULT = {"type": "result", "subtype": "success", "is_error": False, "permission_denials": []}


def store_files(world) -> list:
  root = Path(superegm.load_config(world.repo)["artifacts_dir"])
  return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.is_dir() else []


@pytest.mark.parametrize("event, line, code", [
    ({"type": "system", "subtype": "init", "mcp_servers": [{"name": "linear", "status": "connected"}]}, "probe: mcp linear connected", 0),
    ({"type": "system", "subtype": "init", "mcp_servers": [{"name": "linear", "status": "needs-auth"}]}, "probe: mcp linear needs-auth", 1),
    ({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "boom\nmore"}]}}, "probe: tool Read error: boom", 1),
    ({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": False, "content": "x"}]}}, "probe: tool Read ok", 0),
    ({"type": "result", "subtype": "success", "is_error": False, "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": "curl -s x"}}]}, "probe: denied Bash curl -s x (--allow curl)", 1),
])
def test_probe_lines(world, monkeypatch, tmp_path, event, line, code):
  # §3.3: a fake `claude` prints the event (tool t1 is a Read) and a clean result; any failing line fails doctor
  events = [READ_CALL, event] + ([] if event["type"] == "result" else [CLEAN_RESULT])
  mcp = {"linear": {"type": "http", "url": "https://mcp.example.invalid/mcp"}}
  store_files_before = store_files(world)
  profile_path, record, spawned = probe_world(world, monkeypatch, tmp_path, events=events, mcp=mcp)
  profile = str(profile_path)
  exit_code, out = world.run("doctor", "--probe")
  probe_temp_dir = spawned[0]["cwd"]
  store_files_after = store_files(world)
  assert line in out and out.rstrip().endswith("probe: session ok") and exit_code == code, out
  assert ("CLAUDE_CONFIG_DIR=" + profile + " claude --mcp-config " + profile + "/probe-mcp.json --strict-mcp-config" in out) == ("needs-auth" in line)
  assert os.path.exists(profile + "/probe-mcp.json") == ("needs-auth" in line)
  assert not os.path.exists(probe_temp_dir) and store_files_after == store_files_before
  if "needs-auth" in line:
    assert "/mcp" in out and "Authenticate" in out, out
    assert json.loads(Path(profile, "probe-mcp.json").read_text(encoding="utf-8")) == {"mcpServers": mcp}
