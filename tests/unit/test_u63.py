# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U63

"""U63 (spec 1.2.1 section 6.2): a launch of round 2 or later resumes the immediately previous launch's session when
that launch has a session id, a result, a transcript, the same model, effort and profile and the same instructions
manifest; it records `resumed_from` or `fresh: <reason>`, counts only its own tool uses, and a resumed launch ending
with no result and no commit of its own is a failed resume, relaunched fresh, never decision point 3."""

import json
import shutil
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from test_builders import seed, launches_of, UNIT, no_graphify, which  # noqa: F401  the autouse fixtures
from test_u37 import blob_sha

OK = {"type": "result", "subtype": "success", "is_error": False, "result": "done", "session_id": "s"}
RULES = ".superegm/rules.md"


def jsonl(path, items):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")


def agent(tid):
  return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "Agent", "input": {"prompt": "p"}}]}}


def profile_of(world):
  return json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]["profile_dir"]


def write_launches(s, launches):
  s.path("launches", f"{UNIT}.json").write_text(json.dumps({"launches": launches}), encoding="utf-8")


def ended(entry, result=OK, transcript=True, code=0):
  """The launch `entry` as an exit leaves it: `exited <code>`, its exit file, its result file (`None`: none) and,
  when `transcript`, its session's transcript under its `profile_dir`."""
  entry["status"] = f"exited {code}"
  Path(entry["result_file"] + ".exit").write_text(f"{code}\n", encoding="utf-8")
  if result is not None:
    Path(entry["result_file"]).write_text(json.dumps(result), encoding="utf-8")
  if transcript:
    jsonl(Path(entry["profile_dir"]) / "projects/-wt" / f"{entry['session_id']}.jsonl", [agent("a1")])
  return entry


def instructed(world, s, card, text):
  """The handoff's approval freezing `RULES` with `text` for the builder, `card`'s stored render dropped (a new card's)."""
  from superegm import approve_spec
  sha12 = blob_sha(text.encode())
  spec = json.loads(s.path("state").read_text(encoding="utf-8"))["design"]["path"]
  path = s.path("approvals", superegm.spec_slug(spec))
  record = json.loads(path.read_text(encoding="utf-8"))
  record["instructions"] = [{"file": RULES, "to": ["builder"], "sha": sha12}]
  path.write_text(json.dumps(record), encoding="utf-8")
  approve_spec.write_copy(s, {"file": RULES, "sha": sha12, "text": text})
  path = s.path("runcards", card)
  data = json.loads(path.read_text(encoding="utf-8"))
  if data.pop("instructions", None) is not None:
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def started(world, monkeypatch):
  """`seed`, `launch` and round 1's `launch-builder` (the spawn faked); returns `(s, card, launch_builder)`."""
  from superegm import launch_builder
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: 4242)
  assert world.run("launch", "--runcard", card)[0] == 0
  return s, card, launch_builder


def launch_round(world, card, rnd):
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", rnd, "--runcard", card)
  assert code == 0, out


@pytest.mark.parametrize("previous, recorded", [
  ("none", {"fresh": "first round"}),
  ("ok", {"resumed_from": "s-1"}),
  ("result file is_error true", {"fresh": "no result"}),
  ("no session_id", {"fresh": "no result"}),
  ("previous no result, older launch ok", {"fresh": "no result"}),
  ("no transcript under its profile_dir", {"fresh": "no transcript"}),
  ("no profile_dir (pre-U63 entry)", {"fresh": "no transcript"}),
  ("effort differs, transcript missing too", {"fresh": "no transcript"}),
  ("tier changed: model differs", {"fresh": "model changed"}),
  ("profile differs", {"fresh": "model changed"}),
  ("re-approval changed a reference document", {"fresh": "instructions changed"}),
  ("previous recorded no instructions[]", {"fresh": "instructions changed"}),
])
def test_resume_or_fresh(world, started, tmp_path, previous, recorded):
  # §6.2: only the immediately previous launch; checks in order result, transcript, model, instructions
  s, card, _ = started
  profile = profile_of(world)
  if previous == "re-approval changed a reference document":
    instructed(world, s, card, "Run the suite.\n")
  launch_round(world, card, 1)
  if previous != "none":
    first = launches_of(s)[0]
    first["profile_dir"] = profile  # as U63 records it; a pre-U63 entry has none
    first["session_id"] = "s-1"
    launches = [ended(first)]
    if previous == "result file is_error true":
      ended(first, result=dict(OK, is_error=True))
    elif previous == "no session_id":
      first.pop("session_id")
    elif previous == "previous no result, older launch ok":
      second = dict(first, round=2, session_id="s-2", result_file=first["result_file"].replace("_r1_", "_r2_"))
      launches.append(ended(second, result=None))
    elif previous == "no transcript under its profile_dir":
      shutil.rmtree(Path(profile) / "projects")
    elif previous == "no profile_dir (pre-U63 entry)":
      first.pop("profile_dir")
    elif previous == "effort differs, transcript missing too":
      first["effort"] = "low"
      shutil.rmtree(Path(profile) / "projects")
    elif previous == "tier changed: model differs":
      first["model"] = "claude-sonnet-5-5"
    elif previous == "profile differs":
      other = tmp_path / "other-profile"
      first["profile_dir"] = str(other)
      ended(first)  # its transcript under its own profile
    elif previous == "re-approval changed a reference document":
      instructed(world, s, card, "Run the whole suite.\n")
    elif previous == "previous recorded no instructions[]":
      first.pop("instructions")
    write_launches(s, launches)
    launch_round(world, card, len(launches) + 1)
  entry = launches_of(s)[-1]
  assert {k: entry.get(k) for k in recorded} == recorded and entry["profile_dir"] == profile
  assert ("resumed_from" in entry) != ("fresh" in entry)


def resumable(world, s, card):
  """Round 1 launched and ended with a result and a transcript, as a resume needs; returns its entry."""
  launch_round(world, card, 1)
  first = launches_of(s)[0]
  first["profile_dir"], first["session_id"] = profile_of(world), "s-1"
  write_launches(s, [ended(first)])
  return first


def test_resumed_command_and_prompt(world, started, monkeypatch):
  # §6.2: flags through U60's builder_flags, run from the new round's worktree; one stale-paths line first
  s, card, launch_builder = started
  config = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))
  _, args = launch_builder.builder_flags(config, ["Read"], [], Path("mcp.json"), ("claude-opus-5-5", "medium"), resume_from="s-1")
  assert args[args.index("--resume"):args.index("--resume") + 3] == ["--resume", "s-1", "--fork-session"]
  resumable(world, s, card)
  made = []
  real = launch_builder.prompt_text
  monkeypatch.setattr(launch_builder, "prompt_text", lambda *a, **k: made.append(real(*a, **k)) or made[-1])
  launch_round(world, card, 2)
  entry = launches_of(s)[-1]
  assert entry["resumed_from"] == "s-1"
  command, worktree_r2 = entry["command"], entry["worktree"]
  prompt_text_output = made[-1]
  prompt = Path(s.path("launches", f"{UNIT}_r2_prompt.md")).read_text(encoding="utf-8")
  assert "--resume 's-1' --fork-session" in command or "--resume s-1 --fork-session" in command
  assert "--session-id" in command and command.startswith(f"SUPEREGM_EXIT=") and f"cd '{worktree_r2}'" in command
  assert prompt.split("\n", 1)[1] == prompt_text_output and worktree_r2 in prompt.split("\n", 1)[0] and "stale" in prompt.split("\n", 1)[0]


@pytest.mark.parametrize("status", ["exited 0", "interrupted"])
def test_resumed_launch_counts_own_calls(tmp_path, status):
  # §6.2: the forked transcript repeats round 1's two Agent calls; tool-use ids already there are not counted
  from superegm import traces
  profile_dir = tmp_path / "profile"
  jsonl(profile_dir / "projects/-wt-r1/s-1.jsonl", [agent("a1"), agent("a2")])
  jsonl(profile_dir / "projects/-wt-r2/s-2.jsonl", [agent("a1"), agent("a2"), agent("a3")])
  assert traces.launch_subagent_calls(profile_dir, {"session_id": "s-2", "resumed_from": "s-1", "status": status})["count"] == 1
  assert traces.launch_subagent_calls(profile_dir, {"session_id": "s-1", "status": status})["count"] == 2


@pytest.mark.parametrize("result, commit, failed", [
  (None, None, True), ("is_error", None, True), ("ok", None, False), (None, "2026-11-14T10:00:00Z", False),
])
def test_failed_resume(world, started, monkeypatch, capsys, result, commit, failed):
  # §6.2: a resumed launch with no result and no commit of its own; the status stays exited, never point 3
  from superegm import decision, launch, record_launch
  from superegm.report import pending_decisions
  s, card, _ = started
  resumable(world, s, card)
  launch_round(world, card, 2)
  second = launches_of(s)[-1]
  assert second["resumed_from"] == "s-1"
  Path(second["result_file"] + ".exit").write_text("1\n", encoding="utf-8")
  if result is not None:
    Path(second["result_file"]).write_text(json.dumps(dict(OK, is_error=result == "is_error")), encoding="utf-8")
  monkeypatch.setattr(record_launch, "own_commit_of", lambda entry: superegm.epoch(commit) if commit else None)
  capsys.readouterr()
  code, finish_out = world.run("record-launch", "--unit", UNIT, "--exit", 1, "--runcard", card)
  assert code == 0, finish_out
  entry = launches_of(s)[-1]
  assert entry["status"] == "exited 1" and entry.get("failed_resume", False) == failed
  assert launch.terminal(entry)  # the report and every terminal reader read it as today
  assert ("failed resume" in finish_out) == failed
  assert decision.no_commit(entry) == (commit is None and not failed)
  if failed:
    launch_round(world, card, 3)
    next_entry = launches_of(s)[-1]
    open_decisions = pending_decisions(superegm.load_foreman(s, UNIT))
  assert (failed and next_entry["fresh"] == "no result" and open_decisions == []) or not failed
