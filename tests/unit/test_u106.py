# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U106 (1.3 design section 3.8): the wave ends on a unit waiting on an open respec, the respec files' refusal, the replan hold on launch-builder and the replan gate's order.

"""U106 (1.3 design section 3.8, Respec): `report` leaves a `waiting respec` unit out of its merge rounds and names each open
respec the loop waits on; `respec.load_json` refuses an unreadable or non-object file with its path; `launch-builder` refuses
a unit a `replan:` mark holds; `gate` reads every unfiled unit's replan mark before any body-hash refusal."""

import json

import pytest

import superegm as core
from test_wave import wave_store, CLEAN as WAVE_CLEAN, open_wave_card
from test_u62 import HEAD, with_rounds, put
from test_u85 import open_respec


@pytest.mark.parametrize("raised, loop_starts, names", [
  ({"R1": "U02"}, "loop: ended", ["waiting respec: U02", "; waiting: respec R1"]),
  ({"R1": "U02", "R2": "U03"}, "loop: ended", ["waiting respec: U02, U03", "; waiting: respec R1; waiting: respec R2"]),
  ({}, "loop: continuing (merge round: U02)", []),
])
def test_waiting_respec_takes_no_merge_round(world, raised, loop_starts, names):
  # approval with rounds; U01 landed; U02 (and U03) clean, U02's PR CONFLICTING; each open respec raised by its unit
  clean = {"pr": 71, "head": HEAD, "ci": "green", **WAVE_CLEAN}
  s = wave_store(world, U01={"pr": 70, "head": "b" * 40, "ci": "green", "landed": True, **WAVE_CLEAN}, U02=clean,
                 U03={**clean, "pr": 72})
  with_rounds(s, world)
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"]["U02"] |= {"status": "conflict", "conflict": True}
  put(s.path("state"), json.dumps(state))
  for rid, unit in raised.items():
    open_respec(s, rid, unit)
  code, out = world.run("report", "--runcard", open_wave_card(world))
  loop = next(line for line in out.splitlines() if line.startswith("loop: "))
  assert code == 0 and loop.startswith(loop_starts), out
  assert all(name in loop for name in names), loop
  assert ("merge round" in loop) is (not raised), loop
