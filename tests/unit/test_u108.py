# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U108's tests: the `superegm-push` script, the allow-list, the orders' section, the per-form author rules, owner notes, the edited rule, the managed hooks, doctor's `managed:` line and the wave skill's probe (1.3 design section 3.7).

"""U108 (spec section 3.7): builder launch, orders and what reaches the prompt."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from superegm import launch_builder
from test_builders import ISSUE, UNIT, git, launches_of, seed, spawn_fake, no_graphify, which  # noqa: F401  the fixtures a launch runs under


def launch(world, monkeypatch, comments=(), rnd=1, card=None, seeded=None):
  """U07 seeded and marked (once), its issue comments `comments`, then `launch-builder` round `rnd`: (store, card, hid)."""
  if seeded is None:
    s, card, hid, _ = seed(world)
    monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
    assert world.run("launch", "--runcard", card)[0] == 0
  else:
    s, card, hid = seeded
  world.gh.comments[ISSUE] = list(comments)
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", rnd, "--runcard", card)
  assert code == 0, out
  return s, card, hid


def refs(bare: Path) -> dict:
  out = git(["for-each-ref", "--format=%(refname) %(objectname)"], bare)
  return dict(line.split(" ", 1) for line in out.splitlines())


def test_push_script_pushes_head_to_the_launch_branch(world, monkeypatch, spawn_fake):
  s, card, hid = launch(world, monkeypatch)
  bin_dir, wt, bare = s.path("launches", f"{UNIT}_r1_bin"), s.path("worktrees", UNIT, "r1"), world.repo.parent / "origin.git"
  git(["config", "push.followTags", "true"], world.repo)  # the flag the script must override
  main_before = refs(bare)["refs/heads/main"]
  (wt / "w.txt").write_text("w\n", encoding="utf-8")
  git(["add", "-A"], wt); git(["commit", "-qm", "feat(S1): w"], wt)
  git(["tag", "-a", "v-annotated", "-m", "annotated"], wt)
  worktree_head = git(["rev-parse", "HEAD"], wt).strip()
  done = subprocess.run([str(bin_dir / "superegm-push"), "origin", "HEAD:main", "--tags"], cwd=str(wt), capture_output=True, text=True)
  assert done.returncode == 0, done.stderr
  origin_refs, config_text = refs(bare), (world.repo / ".git/config").read_text(encoding="utf-8")
  assert os.access(bin_dir / "superegm-push", os.X_OK)
  assert origin_refs[f"refs/heads/superegm/{hid}/U07"] == worktree_head
  assert origin_refs["refs/heads/main"] == main_before
  assert "refs/tags/v-annotated" not in origin_refs
  assert f'[branch "superegm/{hid}/U07"]' not in config_text
