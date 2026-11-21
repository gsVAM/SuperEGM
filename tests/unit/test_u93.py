# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the tests of U93, cleanup is automatic.

"""U93 (spec section 7.1): `clean` removes only registered review worktrees, kills a worktree's leftover
`node` and `python*` processes first, keeps round records, and `clean --auto` cleans every landed, merged or
stopped unit at the end of each wave and integrate invocation."""

import json, subprocess
from pathlib import Path
import pytest
from test_builders import seed, put, launched, spawn_fake, no_graphify, which  # noqa: F401  the fixtures a seeded store runs under

ROOT = Path(__file__).resolve().parents[2]
UNIT = "U01"


def git(*args, cwd):
  return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


def journal_text(s):
  return s.path("journal").read_text(encoding="utf-8") if s.path("journal").is_file() else ""


def clean_card(world, skill="clean", artifact=UNIT):
  return world.open_card(skill, artifact)


def read(path):
  return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("layout, removed, printed", [
  ("review/U01/pr7/worktree registered, dirty", "review/U01/pr7/worktree", None),
  ("review/U01/pr7 registered (legacy)", "review/U01/pr7", None),
  ("review/U01/pr7 not registered", None, "kept {store}/review/U01/pr7: not a worktree"),
])
def test_clean_removes_the_registered_review_worktree(world, layout, removed, printed):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  pr = s.path("review", UNIT, "pr7")
  repo = world.repo
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=repo)
  git("update-ref", "refs/superegm/pr-base/7", "HEAD", cwd=repo)
  if layout.startswith("review/U01/pr7/worktree"):
    git("worktree", "add", "-q", "--detach", str(pr / "worktree"), "HEAD", cwd=repo)
    (pr / "worktree" / "scratch.txt").write_text("unsaved\n", encoding="utf-8")
  elif layout.endswith("(legacy)"):
    pr.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "--detach", str(pr), "HEAD", cwd=repo)
  for record in ("r1", "r2"):
    if not layout.endswith("(legacy)"):
      (pr / record).mkdir(parents=True, exist_ok=True)
      (pr / record / "round.json").write_text("{}\n", encoding="utf-8")
  result = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  code, out = result
  assert code == 0, out
  base = pr.parent.parent.parent  # the handoff's store directory, the parent of `review/`
  assert removed is None or not (base / removed).exists()
  assert layout.endswith("(legacy)") or (pr / "r1").is_dir() and (pr / "r2").is_dir()
  if printed:
    assert printed.format(store=base) in out
  assert git("for-each-ref", "refs/superegm/pr/7", "refs/superegm/pr-base/7", cwd=repo) == "" or printed
  assert "/review/" not in git("worktree", "list", "--porcelain", cwd=repo) or printed  # no review worktree stays registered
