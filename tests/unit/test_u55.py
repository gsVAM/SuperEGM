# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U55

"""U55 (spec section 7.1): a merged unit holds no slot. A view with `pr` set and `ci` null reads `landed`, is never
relaunched and frees its `max_in_flight` slot; `launch-builder` refuses a direct revision of a merged pull request."""

import pytest

from conftest import REPO, make_pr
from superegm.report import unit_state
from test_builders import spawn_fake, no_graphify, which  # noqa: F401  the fixtures `launch-builder` and `launch` need
from test_builders import seed, launched, foreman
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


CLEAN = {"round": 1, "runcard": "c", "launch": 1, "head": HEAD, "phase": "posted", "dispatch_id": "d1", "outcome": "clean", "posted_at": "2026-11-03T01:00:00Z"}


@pytest.mark.parametrize("case", ["clean rewritten to revise by an ingest", "latest round revise", "launch recorded after its clean round"])
def test_merged_unit_holds_no_slot(world, monkeypatch, case):
  s, card, hid, _ = seed(world, units=("U07", "U08"), max_in_flight=1)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07" in world.run("launch", "--runcard", card)[1]
  # U07's pull request merged, its issue left open: the fresh status pass reads `pr` set and `ci` null
  make_pr(world.gh, 71, "b" * 40, merged="2026-11-03T02:00:00Z", closes=[(REPO, 7)])
  world.gh.graphql[7] = [{**world.gh.prs[71], "repository": {"nameWithOwner": REPO}}]
  if case == "launch recorded after its clean round":
    launched(s, "U07", "running", rnd=2)
    foreman(s, "U07", [{**CLEAN, "runcard": card}])
  else:
    launched(s, "U07", "exited 0")
    rewritten = {"outcome": "revise", "rewritten_from": "clean"} if case.startswith("clean") else {"outcome": "revise"}
    foreman(s, "U07", [{**CLEAN, "runcard": card, **rewritten}])
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and "in flight: none" in out and "marked: U08" in out, out
  assert "U07" not in out.split("marked:")[1]
