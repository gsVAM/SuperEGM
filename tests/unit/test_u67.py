# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U67

"""U67 (spec section 6.3): `superegm precheck` runs the foreman's worktree checks in the builder's worktree,
through the one function `collect` calls too, before every push. Fixtures: conftest's `world` and
test_foreman's `seed`, `pr_repo` and `open_head_review`."""

import re

import pytest

from test_foreman import POSTED_R1, PR_BODY, TWO_LAUNCHES, open_head_review, pr_repo, seed

BRANCH = "superegm/sample-42aff4/U01"
GOOD = (("test(S1): hook", "tests/unit/test_hooks.py"), ("feat(S1): hook", "src/hooks.py"))
CASES = {
    "out_of_scope": dict(commits=GOOD + (("feat(S1): more", "src/other.py"),)),
    "missing_dod": dict(pr_body="U01\n\nCloses #2\n"),
    "tdd_order": dict(commits=(("feat(S1): hook", "src/hooks.py"), ("test(S1): hook", "tests/unit/test_hooks.py"))),
    "clean": {},
    "round_2_overruled_scope": dict(commits=GOOD + (("feat(S1): more", "src/other.py"),), round_2=True),
}
RULING = ("builder: builder-bot\n### issue #2 comment 13 by owner at 2026-11-02T13:00:00Z\n"
          "**Ruling:** foreman-1-2 finding overruled — Scope widened to src/other.py\n")


def builder_worktree(world, tmp_path, monkeypatch, commits=GOOD, round_2=False, **kw):
  """The builder's worktree on its branch, `refs/superegm/base` at the base as `launch` fetches it, the
  working directory inside it; on round 2 a posted round whose out-of-Scope finding the owner overruled."""
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch, commits=commits)
  if round_2:
    kw.update(rounds=[POSTED_R1], launches=TWO_LAUNCHES)
  st, card, _ = seed(world, head=head, **kw)
  if round_2:
    open_head_review(world, st, card, "0" * 40, {
        "change-review": "",
        "foreman": "foreman-1-1 | high | ci | regression: no | CI not green on this head: ci red (tests)\n"
                   "foreman-1-2 | high | src/other.py | regression: no | changed path outside Scope paths\n"})
    seen = st.path("review", "U01", "pr70") / "r1" / "comments.md"
    seen.parent.mkdir(parents=True, exist_ok=True)
    seen.write_text(RULING, encoding="utf-8")
  g("fetch", "-q", "--no-write-fetch-head", "origin", "+refs/heads/main:refs/superegm/base",
    f"+refs/pull/70/head:refs/heads/{BRANCH}", cwd=world.repo)
  worktree = tmp_path / "wt"
  g("worktree", "add", "-q", str(worktree), BRANCH, cwd=world.repo)
  monkeypatch.chdir(worktree)
  return st, worktree, g


def precheck(world, st, tmp_path, pr_body=PR_BODY):
  body = tmp_path / "pr_body.md"
  body.write_text(pr_body, encoding="utf-8")
  return world.run("precheck", "--handoff", st.handoff_id, "--unit", "U01", "--pr-body", body)


@pytest.mark.parametrize("case, claim_part", [
    ("out_of_scope", "outside Scope"), ("missing_dod", "Run item 2: no fenced output"),
    ("tdd_order", "tdd-order"), ("clean", None), ("round_2_overruled_scope", None)])
def test_precheck_prints_each_worktree_finding(world, tmp_path, monkeypatch, case, claim_part):
  # each break prints one foreman-grammar line; a clean or overruled worktree prints nothing
  setup = dict(CASES[case])
  pr_body = setup.pop("pr_body", PR_BODY)
  st, _, _ = builder_worktree(world, tmp_path, monkeypatch, **setup)
  code, out = precheck(world, st, tmp_path, pr_body)
  lines = out.splitlines()
  if claim_part is None:
    assert (code, out) == (0, "")
  else:
    assert code == 1 and len(lines) == 1 and claim_part in lines[0], out
    assert re.fullmatch(r"foreman-1-\d+ \| (high|medium|low) \| .+ \| regression: no \| .+", lines[0])
