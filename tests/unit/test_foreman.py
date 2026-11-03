# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03).

"""EGM's tests of the subcommands U10 (foreman) changes, moved from test_helper.py by U03;
that unit rewrites the ones whose form it changes."""

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from conftest import REPO, Harness, make_repo, make_plan, make_pr, applied, result_for, foreman_path, round_of, git


def launched(world, unit, rnd, folder):
  """A round as EGM's `record-launch --run-folder` left it: `launched` with its run folder (U09
  removed that form; `collect` and `prepare` still read the phase until U10 rewrites them)."""
  import superegm
  st = superegm.store(world.repo)
  data = superegm.load_foreman(st, unit)
  superegm.round_entry(data, rnd).update({"runcard": world.card("wave"), "phase": "launched", "run_folder": str(folder),
                                          "status": "running", "run_status": "running", "at": superegm.now_iso()})
  superegm.save_foreman(st, unit, data)


def test_prepare_fetches_from_the_recorded_remote_into_private_refs(tmp_path, capsys, monkeypatch):
  target = make_repo(tmp_path / "target", config={"repo": REPO})
  (target / "src").mkdir()
  (target / "src/a.txt").write_text("base\n", encoding="utf-8")
  git(["add", "-A"], target)
  git(["commit", "-qm", "base"], target)
  base_sha = git(["rev-parse", "HEAD"], target).strip()
  git(["checkout", "-qb", "feature"], target)
  (target / "src/a.txt").write_text("base\nchanged\n", encoding="utf-8")
  git(["commit", "-qam", "change"], target)
  head = git(["rev-parse", "HEAD"], target).strip()
  git(["update-ref", "refs/pull/7/head", head], target)
  git(["checkout", "-q", "main"], target)
  elsewhere = tmp_path / "elsewhere"
  git(["clone", "-q", str(target), str(elsewhere)], tmp_path)
  checkout = tmp_path / "checkout"
  git(["clone", "-q", "-o", "origin", str(elsewhere), str(checkout)], tmp_path)
  git(["remote", "set-url", "origin", "https://github.com/fork-user/webhooks.git"], checkout)
  git(["remote", "add", "upstream", str(target)], checkout)
  git(["config", "user.email", "egm@example.invalid"], checkout)
  git(["config", "user.name", "EGM"], checkout)
  plan = make_plan(tmp_path / "plans", checkout)
  artifacts = tmp_path / "artifacts"
  monkeypatch.chdir(checkout)
  harness = Harness(capsys)
  harness.spec = checkout / "docs/designs/sample.md"
  harness.ns["find_remote"] = lambda root, repo: "upstream"
  assert harness.run("graph", "--plan", plan)[0] == 0
  state = json.loads((artifacts / "state.json").read_text(encoding="utf-8"))
  hexd = state["handoff_id"][-6:]
  state.update({"remote": "upstream", "confirmed_sha256": "x", "verify": {"complete": True, "sha256": "x", "problems": []},
                "units": {"U01": {"number": 2, "pr": {"number": 7, "head": head, "base_ref": "main", "base_sha": base_sha}}}})
  (artifacts / "state.json").write_text(json.dumps(state), encoding="utf-8")
  harness.ns["parse_remote_url"] = lambda url: REPO if url.strip() == str(target) else None
  harness.gh.check_runs[head] = [{"name": "tests", "status": "completed", "conclusion": "success"}]
  harness.gh.combined[head] = {"state": "success", "statuses": []}
  fetch_head = checkout / ".git/FETCH_HEAD"
  before = fetch_head.read_bytes() if fetch_head.exists() else None
  code, out = harness.run("prepare", "--plan", plan, "--unit", "U01", "--round", 1,
                          "--runner", "/tmp/runner.py", "--model", "gpt-6-astra", "--effort", "xhigh")
  assert code == 0, out
  assert git(["rev-parse", "refs/egm/pr/7"], checkout).strip() == head
  assert git(["rev-parse", "refs/egm/base/7"], checkout).strip() == base_sha
  assert (fetch_head.read_bytes() if fetch_head.exists() else None) == before
  tree = Path(re.search(r"worktree (\S+) at", out).group(1))
  assert tree.is_dir() and "egm-wave" in str(tree)
  diff = (artifacts / "pr_7_r1.diff").read_bytes()
  expected = subprocess.run(["git", "-C", str(tree), "diff", "--no-ext-diff", "--no-textconv", "--binary",
                             base_sha, "--"], capture_output=True, check=True).stdout
  assert diff == expected and b"+changed" in diff
  ci = json.loads((artifacts / "ci_7_r1.json").read_text(encoding="utf-8"))
  assert ci["verdict"] == "ci green"
  launch = (artifacts / "foreman_U01_r1_launch.md").read_text(encoding="utf-8")
  line = [l for l in launch.splitlines() if "inspect" in l][0]
  assert f"--base '{base_sha}'" in line and "--resume" not in line and not re.search(r"\$EGM_|&&|\||;|\s>", line)
  foreman = json.loads((artifacts / hexd / "foreman/U01.json").read_text(encoding="utf-8"))
  assert round_of(foreman, 1)["phase"] == "prepared" and round_of(foreman, 1)["merge_base"] == base_sha
  # A leftover clean worktree is removed on the next call; a dirty one is refused.
  code, out = harness.run("prepare", "--plan", plan, "--unit", "U01", "--round", 2)
  assert code == 0, out
  (tree / "src/a.txt").write_text("dirty\n", encoding="utf-8")
  code, out = harness.run("prepare", "--plan", plan, "--unit", "U01", "--round", 3)
  assert code == 1 and "has changes: remove it by hand" in out
  (tree / "src/a.txt").write_text("base\nchanged\n", encoding="utf-8")
  code, out = harness.run("prepare", "--plan", plan, "--unit", "U01", "--round", 3)
  assert code == 0 and tree.exists(), out  # the worktree lives until the unit lands
  # A moved head stops the round.
  state["units"]["U01"]["pr"]["head"] = "0" * 40
  (artifacts / "state.json").write_text(json.dumps(state), encoding="utf-8")
  code, out = harness.run("prepare", "--plan", plan, "--unit", "U01", "--round", 4)
  assert code == 3 and "head-moved" in out
  # A remote that no longer names the repository is refused.
  harness.ns["parse_remote_url"] = lambda url: None
  code, out = harness.run("prepare", "--plan", plan, "--unit", "U01", "--round", 4)
  assert code == 1 and "no longer names" in out
  harness.ns["parse_remote_url"] = lambda url: REPO if url.strip() == str(target) else None
  code, out = harness.run("prepare", "--plan", plan, "--unit", "U01", "--clean")
  assert code == 0, out
  assert subprocess.run(["git", "-C", str(checkout), "rev-parse", "refs/egm/pr/7"], capture_output=True).returncode != 0


def test_prepare_refuses_a_selection_its_observation_contradicts(world):
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  assert world.run("status", "--plan", world.plan, "--watch", "U01=70")[0] == 0
  path = world.artifacts / "state.json"
  state = json.loads(path.read_text(encoding="utf-8"))
  state["units"]["U01"]["watch"]["number"] = 71
  path.write_text(json.dumps(state), encoding="utf-8")
  code, out = world.run("prepare", "--plan", world.plan, "--unit", "U01")
  assert code == 1 and "watches PR #71" in out and "describes #70" in out


def test_collect_records_a_round_and_guards_cleanup(world, tmp_path):
  """R4-04: nothing recorded `collected`, so the cleanup guard saw a round that
  was still `launched` for ever."""
  applied(world)
  folder = tmp_path / "run"; folder.mkdir()
  launched(world, "U01", 1, folder)
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "does not exist" in out
  (folder / "result.json").write_text(json.dumps({"status": "running"}), encoding="utf-8")
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "not `completed`" in out
  (folder / "result.json").write_text(json.dumps(result_for(world, "U01", 1)), encoding="utf-8")
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01",
                        "--round", 1, "--verdict", "clean")
  assert code == 0 and "collected" in out, out
  data = json.loads(foreman_path(world, "U01").read_text(encoding="utf-8"))
  assert round_of(data, 1)["phase"] == "collected"
  assert round_of(data, 1)["run_status"] == "completed"


def test_collect_accepts_a_round_whose_lane_never_launched(world):
  """R6-05: with the lane off, nothing records a launch, so the round stays
  `prepared` and the documented collect-before-remove sequence could not run."""
  applied(world)
  data = {"dispatch_id": None, "decisions": [], "rulings": [],
          "rounds": [{"round": 1, "phase": "prepared", "pr": 70, "worktree": "/tmp/egm-wave/x"}]}
  foreman_path(world, "U01").parent.mkdir(parents=True)
  foreman_path(world, "U01").write_text(json.dumps(data), encoding="utf-8")
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "--not-run" in out, out
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01",
                        "--round", 1, "--not-run", "lane off")
  assert code == 0, out
  saved = json.loads(foreman_path(world, "U01").read_text(encoding="utf-8"))
  assert round_of(saved, 1)["phase"] == "collected"
  assert "not run (lane off)" in round_of(saved, 1)["run_status"]


def test_there_is_no_mid_round_worktree_removal(world):
  """Rounds 9, 10 and 11 each found a door to "cleanup removes a worktree a
  runner still reads". The capability is gone: a review worktree lives until
  the unit lands, and `--remove` is not a flag."""
  with pytest.raises(SystemExit) as caught:
    world.run("prepare", "--plan", world.plan, "--unit", "U01", "--round", 1, "--remove")
  assert caught.value.code == 2  # argparse: unrecognized arguments: --remove


def test_collect_refuses_a_result_from_a_different_review(world, tmp_path):
  """R11-02: a completed result is accepted only if it reviewed this round's
  unit file against this round's merge base."""
  applied(world)
  folder = tmp_path / "run"; folder.mkdir()
  launched(world, "U01", 1, folder)
  bad = dict(result_for(world, "U01", 1), plan="/elsewhere/unit_U09.md")
  (folder / "result.json").write_text(json.dumps(bad), encoding="utf-8")
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "different review" in out, out
  # R12-02: identity is required, and an older run is refused
  (folder / "result.json").write_text(json.dumps({"status": "completed"}), encoding="utf-8")
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "lacks" in out, out
  stale = dict(result_for(world, "U01", 1), started_at=1_600_000_000.0)
  (folder / "result.json").write_text(json.dumps(stale), encoding="utf-8")
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "older run" in out, out


def test_a_launched_round_is_never_re_prepared(world, tmp_path):
  """R12-03: re-preparing kept the old run folder, so the replacement launch
  was refused and left unrecorded."""
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  assert world.run("status", "--plan", world.plan, "--watch", "U01=70")[0] == 0
  folder = tmp_path / "run"; folder.mkdir()
  launched(world, "U01", 1, folder)
  code, out = world.run("prepare", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "prepare round 2" in out, out


def test_collect_without_not_run_still_requires_a_completed_result(world, tmp_path):
  applied(world)
  folder = tmp_path / "run"; folder.mkdir()
  launched(world, "U01", 1, folder)
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "does not exist" in out, out
  (folder / "result.json").write_text(json.dumps({"status": "running"}), encoding="utf-8")
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1)
  assert code == 1 and "not `completed`" in out, out


def test_an_interrupted_round_is_collected_but_its_worktree_is_never_removed(world, tmp_path):
  """R12-01 (panel, Q2): the non-destructive decision - stop waiting - may be
  taken on a non-terminal result; the destructive one - remove the worktree -
  needs a terminal result or a human. File inactivity is never evidence, so
  there is no backdating trick that makes this pass."""
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  assert world.run("status", "--plan", world.plan, "--watch", "U01=70")[0] == 0
  folder = tmp_path / "run"; folder.mkdir()
  tree = tmp_path / "wt-u01"; tree.mkdir()
  launched(world, "U01", 1, folder)
  path = foreman_path(world, "U01")
  data = json.loads(path.read_text(encoding="utf-8"))
  round_of(data, 1).update({"pr": 70, "worktree": str(tree)})
  path.write_text(json.dumps(data), encoding="utf-8")
  (folder / "result.json").write_text(json.dumps({"status": "running"}), encoding="utf-8")
  # stop waiting: accepted, folder kept, nothing invented
  code, out = world.run("collect", "--plan", world.plan, "--unit", "U01", "--round", 1,
                        "--not-run", "runner killed")
  assert code == 0 and "not run (interrupted: runner killed)" in out, out
  data = json.loads(path.read_text(encoding="utf-8"))
  assert round_of(data, 1)["run_folder"] == str(folder) and round_of(data, 1)["phase"] == "collected"
  # removal: NOT performed, even though the round is administratively
  # "collected" and even though the files are old - inactivity is never
  # evidence. Landing still completes (exit 0) and says what it kept.
  old = time.time() - 7200
  for p in (folder, folder / "result.json"):
    os.utime(p, (old, old))
  code, out = world.run("prepare", "--plan", world.plan, "--unit", "U01", "--round", 1, "--clean")
  assert code == 0 and "kept" in out and "cannot know its runner has stopped reading" in out, out
  assert "if you know the runner is dead" not in out
  assert tree.exists()
  # a terminal result is the only evidence that unlocks it
  (folder / "result.json").write_text(json.dumps({"status": "failed"}), encoding="utf-8")
  code, out = world.run("prepare", "--plan", world.plan, "--unit", "U01", "--round", 1, "--clean")
  assert code == 0 and "cleaned" in out, out
