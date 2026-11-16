# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U55

"""U55 (spec section 7.1): a merged unit holds no slot. A view with `pr` set and `ci` null reads `landed`, is never
relaunched and frees its `max_in_flight` slot; `launch-builder` refuses a direct revision of a merged pull request."""

import json
from pathlib import Path

import pytest

from conftest import REPO, make_pr
from superegm.report import unit_state
from test_builders import spawn_fake, no_graphify, which  # noqa: F401  the fixtures `launch-builder` and `launch` need
from test_builders import seed, launched, foreman, git, launches_of, state_of
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


def snapshot_of(world, s):
  """What a refused launch must leave alone: the launch records, the worktrees and the git refs."""
  def names(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*")) if folder.is_dir() else []
  return (names(s.path("launches", "U07.json").parent), names(s.path("worktrees", "U07", "r1").parent.parent),
          git(["for-each-ref"], world.repo))


@pytest.mark.parametrize("recorded, merged_at, refused", [
  (7, "2026-11-14T10:00:00Z", "pull request #7 is merged: U07 is not relaunched"),
  (7, None, None),       # an open pull request: the launch goes on
  (None, None, None),    # Decision point 3's round-2 relaunch with no recorded pull request
])
def test_merged_pr_refuses_a_direct_revision(world, monkeypatch, spawn_fake, recorded, merged_at, refused):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", "U07", "--round", 1, "--runcard", card)[0] == 0
  Path(launches_of(s, "U07")[0]["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", "U07", "--exit", 0, "--runcard", card)[0] == 0
  head = git(["rev-parse", "refs/superegm/base"], world.repo).strip()
  if recorded:  # the snapshot was saved while the pull request was open; it merged afterwards
    git(["update-ref", f"refs/pull/{recorded}/head", head], world.repo.parent / "origin.git")
    state = state_of(s)
    state["units"]["U07"]["pr"] = {"number": recorded, "head": head, "base_ref": "main"}
    s.path("state").write_text(json.dumps(state), encoding="utf-8")
    make_pr(world.gh, recorded, head, merged=merged_at, closes=[(REPO, 7)])
  before = snapshot_of(world, s)
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  if refused:
    assert code == 1 and refused in out, out
    assert snapshot_of(world, s) == before
  else:
    assert code == 0, out
