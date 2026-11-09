# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U31

"""U31 (spec section 11.1): the watchdog's key `builder.stall_minutes` and the `kill_failed` lines."""

import re

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, set_config, state_of
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
