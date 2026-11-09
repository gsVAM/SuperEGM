# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U31

"""U31 (spec section 11.1): the watchdog's key `builder.stall_minutes` and the `kill_failed` lines."""

import json
import os
import re
import subprocess

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, set_config, state_of
from superegm import atomic_write
from test_wave import open_wave_card, wave_store


@pytest.mark.parametrize("value, loaded", [(30, 30), (45, 45), ("absent", 30), (0, None), ("30", None), (True, None)])
def test_stall_minutes_is_30_and_a_positive_integer(world, value, loaded):
  assert superegm.DEFAULT_CONFIG["builder"]["stall_minutes"] == 30
  builder = {**superegm.DEFAULT_CONFIG["builder"], "stall_minutes": value}
  value == "absent" and builder.pop("stall_minutes")
  set_config(world, repo=REPO, builder=builder)
  if loaded:
    assert superegm.load_config(world.repo)["builder"]["stall_minutes"] == loaded
    return
  with pytest.raises(superegm.HandoffError, match=re.escape("builder.stall_minutes must be a positive integer")):
    superegm.load_config(world.repo)


def test_a_kill_failed_launch_is_idle_and_in_the_inbox(world):
  from superegm.inbox import inbox_items
  card = open_wave_card(world)
  s = wave_store(world, U01={"launches": [{"round": 1, "status": "running", "started_at": "t", "result_file": "/w/r1.json", "pid": 4242, "kill_failed": "no exit file"}]})
  code, out = world.run("report", "--runcard", card)
  assert code == 0 and "idle: U01" in out, out
  assert "## Idle\n- U01: kill_failed (no exit file): /superegm:interrupt --unit U01 --launch 1\n" in s.path("wave_report", 1).read_text(encoding="utf-8")
  items = [i for i in inbox_items(s, [state_of(world)["handoff_id"]]) if i["kind"].startswith("kill_failed")]
  assert [(i["subject"], i["kind"], i["action"], i["fingerprint"]) for i in items] == [
    ("U01", "kill_failed (no exit file, pid 4242)", "/superegm:interrupt --unit U01 --launch 1, then /superegm:wave", "U01 launch 1 kill_failed")]


@pytest.mark.parametrize("mark", ["pid reused", "no process"])
def test_a_kill_failed_mark_reads_on_the_board_and_in_the_inbox_for_a_stopped_unit_too(world, mark):
  """The board's next action for a `kill_failed` unit is the interrupt; the inbox kind names a mark other than
  `no exit file` with no pid, and a stopped unit's `kill_failed` launch stays in the inbox (the kill is what is left)."""
  from superegm.inbox import inbox_items
  card = open_wave_card(world)
  s = wave_store(world, U01={"launches": [{"round": 1, "status": "running", "started_at": "t", "result_file": "/w/r1.json", "pid": 4242, "kill_failed": mark}]})
  code, out = world.run("report", "--runcard", card)
  assert code == 0, out
  row = next(line for line in out.splitlines() if line.startswith("| U01 "))
  assert row.split(" | ")[1] == "idle" and row.split(" | ")[7] == f"kill_failed ({mark}): /superegm:interrupt --unit U01 --launch 1", row
  for stopped in (None, {"reason": "stop the unit"}):
    stopped and atomic_write(s.path("foreman", "U01"), {**json.loads(s.path("foreman", "U01").read_text(encoding="utf-8")), "stopped": stopped})
    items = [i for i in inbox_items(s, [state_of(world)["handoff_id"]]) if i["kind"].startswith("kill_failed")]
    assert [(i["subject"], i["kind"], i["action"]) for i in items] == [
      ("U01", f"kill_failed ({mark})", "/superegm:interrupt --unit U01 --launch 1, then /superegm:wave")], stopped


@pytest.mark.parametrize("extra, read", [({"status": "exited 0"}, False), ({"kill_failed": "no exit file"}, False),
                                         ({"started_at": "t"}, True), ({}, True)])
def test_the_pass_reads_git_only_for_a_launch_the_predicate_can_hold_of(world, monkeypatch, tmp_path, extra, read):
  """A `status` pass reads the worktree head only for a running, unmarked launch (U31); a `started_at` that does not
  parse is no stall and fails no pass."""
  from test_events import seed as events_seed, WAIT
  from superegm import status as status_mod
  gh, st, card = events_seed(world, monkeypatch)
  atomic_write(st.path("launches", "U01"), {"launches": [{"round": 1, "status": "running", "started_at": "2026-11-03T10:00:00Z",
                                                          "worktree": str(tmp_path), "result_file": str(tmp_path / "r1.json"), **extra}]})
  calls = []
  monkeypatch.setattr(status_mod, "head_time", lambda worktree: calls.append(worktree))
  code, out = world.run(*WAIT, card)
  assert code == 0 and "Traceback" not in out and bool(calls) == read, out


def test_head_time_reads_the_worktree_head_or_none(tmp_path):
  """`head_time` (U31) reads the committer time of the worktree's `HEAD` through git; None for a folder with no
  commit, a folder that is not a repository, and a worktree that is gone."""
  from superegm.status import head_time
  repo = tmp_path / "w"
  repo.mkdir()
  git = lambda *args, **env: subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env={**os.environ, **env})
  git("init", "-q")
  assert head_time(repo) is None
  git("-c", "user.name=b", "-c", "user.email=b@x", "commit", "-q", "--allow-empty", "-m", "c", GIT_COMMITTER_DATE="@1700000000 +0000")
  assert head_time(repo) == 1_700_000_000.0 and head_time(str(repo)) == 1_700_000_000.0
  assert head_time(tmp_path / "gone") is None and head_time(None) is None
