# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03).

"""EGM's tests of the subcommands U09 (builders) changes, moved from test_helper.py by U03;
that unit rewrites the ones whose form it changes."""

import json

import pytest

from conftest import applied, state_of, foreman_path, round_of


def test_record_launch_persists_the_run_folder_before_the_wait(world):
  """R18: nothing persisted between `prepared` and `collected` on the no-teams
  path, so a session ending in between redid the round."""
  applied(world)
  assert world.run("record-launch", "--plan", world.plan, "--unit", "U01",
                   "--round", 2, "--run-folder", "/tmp/egm-astra/claudex-abc")[0] == 0
  data = json.loads(foreman_path(world, "U01").read_text(encoding="utf-8"))
  assert round_of(data, 2)["phase"] == "launched"
  assert round_of(data, 2)["run_folder"].endswith("claudex-abc")
  assert round_of(data, 2)["status"] == "running"
  assert world.run("record-launch", "--plan", world.plan, "--unit", "U01",
                   "--round", 3, "--not-run", "denied")[0] == 0
  data = json.loads(foreman_path(world, "U01").read_text(encoding="utf-8"))
  assert round_of(data, 3)["status"] == "not run (denied)"
  assert round_of(data, 2)["run_folder"], "an earlier round must survive"


def test_launch_refuses_a_unit_that_is_not_ready(world):
  """R3-09: launch validated only that the unit id parsed."""
  applied(world)
  code, out = world.run("launch", "--plan", world.plan, "--wave", 1, "--units", "U03")
  assert code == 1 and "nothing was launched" in out
  assert "U03" in out and ("not ready" in out or "blocking decision" in out)
  assert not (state_of(world)["units"].get("U03") or {}).get("launched")


def test_record_launch_not_run_cannot_erase_a_recorded_launch(world, tmp_path):
  """R10-01: nulling the run folder hid a live runner from every cleanup guard."""
  applied(world)
  folder = tmp_path / "run"; folder.mkdir()
  assert world.run("record-launch", "--plan", world.plan, "--unit", "U01",
                   "--round", 1, "--run-folder", str(folder))[0] == 0
  code, out = world.run("record-launch", "--plan", world.plan, "--unit", "U01",
                        "--round", 1, "--not-run", "skipped")
  assert code == 1 and "already recorded a launch" in out, out
  data = json.loads(foreman_path(world, "U01").read_text(encoding="utf-8"))
  assert round_of(data, 1)["run_folder"].endswith("run"), "the folder must survive"
  assert round_of(data, 1)["run_status"] == "running"
  # a round that never launched may still be recorded not run
  assert world.run("record-launch", "--plan", world.plan, "--unit", "U01",
                   "--round", 2, "--not-run", "lane off")[0] == 0


def test_record_launch_is_immutable_per_round(world, tmp_path):
  """R11-02: re-pointing a live round at another folder let an old result be
  collected in its place."""
  applied(world)
  a, b = tmp_path / "a", tmp_path / "b"; a.mkdir(); b.mkdir()
  assert world.run("record-launch", "--plan", world.plan, "--unit", "U01",
                   "--round", 1, "--run-folder", str(a))[0] == 0
  code, out = world.run("record-launch", "--plan", world.plan, "--unit", "U01",
                        "--round", 1, "--run-folder", str(a))
  assert code == 0 and "already recorded" in out
  code, out = world.run("record-launch", "--plan", world.plan, "--unit", "U01",
                        "--round", 1, "--run-folder", str(b))
  assert code == 1 and "a new round" in out, out
  data = json.loads(foreman_path(world, "U01").read_text(encoding="utf-8"))
  assert round_of(data, 1)["run_folder"] == str(a)
