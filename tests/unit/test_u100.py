# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U100's tests: the watchdog's 60-minute default and the foreman's background and `collect`'s foreground wording (1.3 design section 3.3).

"""U100 (spec section 3.3): `builder.stall_minutes` defaults to 60; the foreman runs in the background beside
`status --wait`, `collect` in the foreground."""

import json
import shutil
import subprocess
import time
from pathlib import Path

from conftest import REPO, set_config
import superegm
from superegm import atomic_write, DEFAULT_CONFIG
from test_builders import github
from test_events import seed as events_seed, WAIT

NOW = 1_700_000_000.0
iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def test_stall_minutes_defaults_to_60(world, monkeypatch, tmp_path):
  # the watchdog's default is 60 minutes (L3), for a .superegm/config.json whose builder lacks the key
  from superegm import status as status_mod
  gh, st, card = events_seed(world, monkeypatch)
  bare = tmp_path / "origin.git"  # origin is a local bare clone, as test_builders.seed makes it: doctor's origin check fetches, never from github.com
  subprocess.run(["git", "clone", "-q", "--bare", str(world.repo), str(bare)], check=True, capture_output=True)
  subprocess.run(["git", "-C", str(world.repo), "remote", "set-url", "origin", str(bare)], check=True, capture_output=True)
  world.ns["find_remote"] = lambda root, repo: "origin"
  builder = {k: v for k, v in DEFAULT_CONFIG["builder"].items() if k != "stall_minutes"}
  set_config(world, repo=REPO, builder=builder)
  assert superegm.load_config(world.repo)["builder"]["stall_minutes"] == 60
  monkeypatch.setenv("HOME", str(tmp_path))
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins"))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: None)
  saved = dict(world.gh.comments)
  github(world)
  world.gh.comments = saved
  _, doctor_out = world.run("doctor")
  assert "stall: 60 min" in doctor_out.splitlines(), doctor_out
  # wait_31: `superegm status --wait 1` over U01's launch running 31 minutes with no commit of its own
  atomic_write(st.path("launches", "U01"), {"launches": [{"round": 1, "status": "running", "started_at": iso(NOW - 31 * 60),
                                                           "worktree": str(tmp_path), "result_file": str(tmp_path / "r1.json")}]})
  monkeypatch.setattr(status_mod, "head_time", lambda worktree: None)
  _, wait_31 = world.run(*WAIT, card)
  assert not any(line.startswith("U01 stalled (") for line in wait_31.splitlines()), wait_31


def test_foreman_background_collect_foreground():
  # the foreman runs in the background beside `status --wait`, `collect` in the foreground (L6, L14); no second foreman for a
  # unit whose foreman is out; brief_opening: foreman_brief.md above `## Brief`; brief_block: the fenced text under it
  root = Path(__file__).resolve().parents[2] / "skills/wave"
  wave_skill = (root / "SKILL.md").read_text(encoding="utf-8")
  brief = (root / "references/foreman_brief.md").read_text(encoding="utf-8")
  brief_opening, brief_block = brief.split("\n## Brief\n", 1)
  for text in (brief_opening, wave_skill):
    assert "beside `status --wait`" in text
  for text in (brief_block, wave_skill):
    assert "never with `run_in_background`" in text
  assert "except a unit whose foreman has not returned (no call, no dispatch)" in wave_skill
  assert "A returned word is applied at the next batch's step 5, after steps 1-4 and before its dispatch" in wave_skill
  assert "Rule a unit after its foreman's `collect` ends." in wave_skill  # section 9: a ruling typed during `collect` can be lost
  assert "The end is reached only with no foreman out." in wave_skill
  assert "no 5b line in step 2 → The end" in wave_skill and "no 5b line of a non-idle unit → The end" in wave_skill
  assert "`foreman-<unit-id>-<dispatch-id>`, in the foreground" not in brief_opening
  assert "named `foreman-<U>-<dispatch-id>`, in the foreground" not in wave_skill
  assert "It alone evaluates §11's predicate" not in wave_skill
  assert "It alone evaluates §11's predicate (CI concluded, latest launch terminal, no round posted since it" in brief_opening
  assert len(wave_skill.encode("utf-8")) < 15_000
