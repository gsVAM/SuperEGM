"""U60: the builder probe, `superegm doctor --probe` (spec 1.2.1 section 3.3)."""

import json
import os
import shlex
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


def probe_world(world, monkeypatch, tmp_path, events=(), exit_code=0, mcp=None, stderr="", allowed=None):
  """A repository whose config names a builder profile under `tmp_path`, doctor's own checks stubbed to nothing, and a
  fake `claude` on PATH that records its argv, its cwd and its prompt, then prints `events` as stream-json lines."""
  from superegm import doctor
  profile = tmp_path / "profile"
  profile.mkdir()
  current = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))
  builder = {"profile_dir": str(profile), "mcp": mcp or {}}
  if allowed is not None:
    builder["allowed_tools"] = allowed
  set_config(world, repo=current["repo"], builder=builder)
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
      "  f.write(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd(), 'gh_token': os.environ.get('GH_TOKEN')}) + '\\n')\n"
      f"for event in json.load(open({str(events_file)!r})):\n"
      "  print(json.dumps(event))\n"
      f"sys.stderr.write({stderr!r})\n"
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
  tools = [t for t in allowed_tools(config["builder"]["allowed_tools"], "superegm/probe", "", "gh")
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


@pytest.mark.parametrize("addressed, prompt", [
    (True, "Always run make lint first.\n\nDo only what these instructions ask at the start of a session, then reply ok."),
    (False, "Reply ok."),
])
def test_probe_prompt(world, monkeypatch, tmp_path, addressed, prompt):
  # §3.3: HEAD's builder-addressed text from U37's renderer; plain doctor never calls claude
  from superegm import instructions
  rendered = []

  def render(st, role, handoff_id=None, root=None, **kwargs):
    rendered.append((role, handoff_id, Path(root).resolve() if root else None))
    return ([{"path": "AGENTS.md"}], "Always run make lint first.\n") if addressed else ([], "")
  monkeypatch.setattr(instructions, "render", render)
  profile, record, spawned = probe_world(world, monkeypatch, tmp_path, events=[CLEAN_RESULT])
  code, out = world.run("doctor")
  claude_calls_without_probe = len(calls(record)) + len(spawned)
  assert "probe:" not in out and rendered == [], out
  code, out = world.run("doctor", "--probe")
  argv = calls(record)[0]["argv"]
  prompt_seen_by_fake_claude = argv[argv.index("-p") + 1]
  assert prompt_seen_by_fake_claude.strip() == prompt
  assert claude_calls_without_probe == 0
  assert rendered == [("builder", None, world.repo.resolve())] and code == 0, out


def test_probe_session_has_no_token(world, monkeypatch, tmp_path):
  # review change-review-1-1: the session's GH_TOKEN is the launch's no-token sentinel, never the owner's
  from superegm.launch_builder import SENTINEL
  monkeypatch.setenv("GH_TOKEN", "owner-secret")
  profile, record, spawned = probe_world(world, monkeypatch, tmp_path, events=[CLEAN_RESULT])
  code, out = world.run("doctor", "--probe")
  assert [c["gh_token"] for c in calls(record)] == [SENTINEL] and code == 0, out


def test_probe_refused_allow_list_closes_the_session(world, monkeypatch, tmp_path):
  # review change-review-1-2: an allow-list `allowed_tools` refuses prints the closing session line and starts no session
  profile, record, spawned = probe_world(world, monkeypatch, tmp_path, allowed=["Read", "Bash"])
  code, out = world.run("doctor", "--probe")
  assert spawned == [] and code == 1, out
  assert out.rstrip().splitlines()[-1].startswith("probe: session ") and "allowed_tools carries Bash" in out, out


@pytest.mark.parametrize("command, allow", [
    ("curl -s x", "--allow curl"),
    ("git checkout -b x", "--allow 'git checkout'"),
    ("/usr/local/bin/gh api repos/o/r", "--allow 'gh api repos/o/r'"),
    ("gh pr merge 1", "--allow 'gh pr merge'"),
    ("pytest -q | tail -5", "--allow pytest --allow tail"),
    ("make test || npm test", "--allow make --allow npm"),
    ("git -C x status", "--allow 'git -C x status'"),
])
def test_probe_denial_names_a_narrow_allow(command, allow):
  # review codebase-details-1-2 and 1-3: as narrow as the allow-list's own git and gh entries, every pipeline segment named
  from superegm.doctor import probe_lines
  event = {"type": "result", "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": command}}]}
  assert probe_lines(json.dumps(event), "/p") == [(f"denied Bash {command} ({allow})", False)]


def test_probe_session_exit_names_the_reason(world, monkeypatch, tmp_path):
  # review codebase-details-1-4: a failed session's closing line carries stderr's first line, else the result text's
  profile, record, spawned = probe_world(world, monkeypatch, tmp_path, exit_code=1, stderr="Invalid API key\nmore\n")
  code, out = world.run("doctor", "--probe")
  assert out.rstrip().endswith("probe: session exit 1: Invalid API key") and code == 1, out
  result = {"type": "result", "subtype": "success", "is_error": True, "result": "Not logged in · Please run /login"}
  (tmp_path / "again").mkdir()
  profile, record, spawned = probe_world(world, monkeypatch, tmp_path / "again", events=[result], exit_code=1)
  code, out = world.run("doctor", "--probe")
  assert out.rstrip().endswith("probe: session exit 1: Not logged in · Please run /login") and code == 1, out


def test_probe_admits_bare_gh_as_the_launch_admits_its_gh(world, monkeypatch, tmp_path):
  # review codebase-details-2-1 and change-review-2-2: the probe prompt carries no gh path, so its rules name bare gh;
  # a `gh <group> <command>` hint is then the entry that admits the call, rewritten to the launch's gh at launch
  profile, record, spawned = probe_world(world, monkeypatch, tmp_path, events=[CLEAN_RESULT], allowed=["Read", "Bash(gh pr view:*)"])
  code, out = world.run("doctor", "--probe")
  argv = spawned[0]["argv"]
  assert argv[argv.index("--allowedTools") + 1] == "Read,Bash(gh pr view:*)" and code == 0, out


PUSH = "git push: a launch admits only its own branch, no --allow"


@pytest.mark.parametrize("command, shown, hint", [
    ("git push origin main", "git push origin main", PUSH),
    ("git status && git push --force origin main", "git status && git push --force origin main", "--allow 'git status'; " + PUSH),
    ("git status\ngh pr merge 1", "git status\\ngh pr merge 1", "--allow 'git status' --allow 'gh pr merge'"),
])
def test_probe_denial_never_widens_push_and_names_every_line(command, shown, hint):
  # review change-review-2-1, codebase-details-2-2 and 2-3: no hint admits a push; every line of a command is a segment
  from superegm.doctor import probe_lines
  event = {"type": "result", "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": command}}]}
  assert probe_lines(json.dumps(event), "/p") == [(f"denied Bash {shown} ({hint})", False)]


@pytest.mark.parametrize("command, shown, hint", [
    ("git -C x push origin main", "git -C x push origin main", PUSH),
    ("git -c k=v push origin main", "git -c k=v push origin main", PUSH),
    ("git --no-pager push --force", "git --no-pager push --force", PUSH),
    ("git status  # check\ngh pr merge 1", "git status  # check\\ngh pr merge 1", "--allow 'git status' --allow 'gh pr merge'"),
    ("git status # x\ngit push origin main", "git status # x\\ngit push origin main", "--allow 'git status'; " + PUSH),
    ("gh api repos/o/r/pulls/1 --jq '.state'", "gh api repos/o/r/pulls/1 --jq '.state'",
     "--allow " + shlex.quote("gh api repos/o/r/pulls/1 --jq '.state'")),
    ("pytest -q 2>&1 | tail -5", "pytest -q 2>&1 | tail -5", "--allow pytest --allow tail"),
])
def test_probe_denial_after_a_git_option_a_comment_or_a_quote(command, shown, hint):
  # review change-review-3-1, codebase-details-3-1, 3-2 and 3-3: a push after a git option gives no hint, a comment never
  # joins two lines, and a whole-call hint is the command's own text, so it is a prefix of what was denied
  from superegm.doctor import probe_lines
  event = {"type": "result", "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": command}}]}
  assert probe_lines(json.dumps(event), "/p") == [(f"denied Bash {shown} ({hint})", False)]
