# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U55

"""U55 (spec section 7.1): a merged unit holds no slot. A view with `pr` set and `ci` null reads `landed`, is never
relaunched and frees its `max_in_flight` slot; `launch-builder` refuses a direct revision of a merged pull request."""

import pytest

from conftest import REPO
from superegm.report import unit_state
from test_wave import open_wave_card, wave_store

NOW = 1_700_000_000.0
HEAD = "a" * 40
REVISE = {"round": 1, "phase": "posted", "outcome": "revise", "launch": 1}


@pytest.mark.parametrize("pr, ci, state", [(7, None, "landed"), (7, "pending", "active"), (None, None, "active")])
def test_merged_view_reads_landed(world, pr, ci, state):
  # the latest round posted `revise`; the card saw the head just now, well inside `ci_wait_minutes`
  view = {"pr": pr, "head": HEAD, "ci": ci, "landed": False, "launched": True}
  card = {"opened_at": NOW, "idle": [], "heads": [{"unit": "U01", "head": HEAD, "seen_at": NOW}]}
  foreman = {"rounds": [REVISE]}
  assert unit_state("U01", view, foreman, [{"round": 1, "status": "exited 0"}], card, {"ci_wait_minutes": 30}, NOW) == state
  if state != "landed":
    return
  # the saved snapshot shows U1 merged, no other unit ready or launched: the loop ends at once
  card_id = open_wave_card(world)
  wave_store(world, U01={"pr": pr, "head": HEAD, "ci": None, "rounds": [REVISE], "launches": [{"round": 1, "status": "exited 0"}]})
  code, out = world.run("report", "--runcard", card_id)
  assert code == 0 and "loop: ended (" in out, out
