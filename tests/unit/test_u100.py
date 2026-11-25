# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U100's tests: the watchdog's 60-minute default and the foreman's background and `collect`'s foreground wording.

"""U100 (spec section 3.3): `builder.stall_minutes` defaults to 60; the foreman runs in the background beside
`status --wait`, `collect` in the foreground."""

import json
import shutil

from conftest import REPO, set_config
import superegm
from superegm import atomic_write, DEFAULT_CONFIG
from test_builders import seed
from test_events import seed as events_seed, WAIT

NOW = 1_700_000_000.0
iso = lambda t: __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime(t))


def test_stall_minutes_defaults_to_60(world, monkeypatch, tmp_path):
  # the watchdog's default is 60 minutes (L3), for a .superegm/config.json whose builder lacks the key
  from superegm import status as status_mod
  builder = {k: v for k, v in DEFAULT_CONFIG["builder"].items() if k != "stall_minutes"}
  set_config(world, repo=REPO, builder=builder)
  assert superegm.load_config(world.repo)["builder"]["stall_minutes"] == 60
  # doctor_out
  monkeypatch.setenv("HOME", str(tmp_path))
  seed(world)
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins"))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: "/usr/local/bin/gh" if cmd == "gh" else None)
  path = world.repo / ".superegm/config.json"
  cfg = json.loads(path.read_text(encoding="utf-8"))
  cfg["builder"].pop("stall_minutes", None)
  path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
  _, doctor_out = world.run("doctor")
  assert "stall: 60 min" in doctor_out.splitlines(), doctor_out
  # wait_31: `superegm status --wait 1` over U01's launch running 31 minutes with no commit of its own
  gh, st, card = events_seed(world, monkeypatch)
  set_config(world, repo=REPO, builder=builder)
  atomic_write(st.path("launches", "U01"), {"launches": [{"round": 1, "status": "running", "started_at": iso(NOW - 31 * 60),
                                                           "worktree": str(tmp_path), "result_file": str(tmp_path / "r1.json")}]})
  monkeypatch.setattr(status_mod, "head_time", lambda worktree: None)
  _, wait_31 = world.run(*WAIT, card)
  assert not any(line.startswith("U01 stalled (") for line in wait_31.splitlines()), wait_31
