# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U67

"""U67 (spec section 6.3): `superegm precheck` runs the foreman's worktree checks in the builder's worktree,
through the one function `collect` calls too, before every push. Fixtures: conftest's `world` and
test_foreman's `seed`, `pr_repo` and `open_head_review`."""

import json
import os
import re
import sys
from pathlib import Path

import pytest

from test_foreman import POSTED_R1, PR_BODY, TWO_LAUNCHES, open_head_review, pr_repo, seed
# test_builders' launch fixtures, by name (its two autouse fixtures are not imported: the S4 test applies them itself)
from test_builders import UNIT, app_seed, launches_of, seed as builders_seed, spawn_fake  # noqa: F401
from test_builder_token import OPENSSL, key  # noqa: F401  the App key fixture
from superegm.launch_builder import HELPER

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


def test_collect_and_precheck_share_the_worktree_checks(world, tmp_path, monkeypatch):
  # one worktree, no rulings: the shared function yields the same lines to both callers
  from superegm import collect as collect_mod
  calls, shared = [], collect_mod.worktree_checks  # each caller goes through the one function
  monkeypatch.setattr(collect_mod, "worktree_checks", lambda *a, **kw: calls.append(a) or shared(*a, **kw))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  st, _, _ = builder_worktree(world, tmp_path, monkeypatch, pr_body="U01\n\nCloses #2\n")
  code, out = precheck(world, st, tmp_path, "U01\n\nCloses #2\n")
  precheck_lines = out.splitlines()
  monkeypatch.chdir(world.repo)
  card = world.open_card("wave", str(world.spec.resolve()))
  code, out = world.run("foreman", "dispatch", "--unit", "U01", "--runcard", card)
  assert code == 0, out
  did, child = out.split()
  assert world.run("prepare", "--unit", "U01", "--dispatch", did, "--runcard", child)[0] == 0
  code, out = world.run("collect", "--unit", "U01", "--dispatch", did, "--runcard", child)
  assert code == 0, out
  collect_lines = (st.path("review", "U01", "pr70") / "r1" / "foreman.findings").read_text(encoding="utf-8").splitlines()
  assert len(calls) == 2
  assert collect_lines == precheck_lines and "Run item 2: no fenced output" in " ".join(precheck_lines)


TWO_RUNS = ("2. Run `pytest tests/unit/test_u07.py -q` — passes\n3. Run `pytest tests/unit -q` — the suite passes\n"
            "4. Exists `src/hooks.py`\n5. CI green on the head\n")
TWO_PASTED = ("U01\n\n### DoD 2\n```\n$ pytest tests/unit/test_u07.py -q\n1 passed\n```\n\n"
              "### DoD 3\n```\n$ pytest tests/unit -q\n9 passed\n```\n\nCloses #2\n")


def snapshot(root):
  return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_precheck_runs_every_item_without_a_draft_and_writes_nothing(world, tmp_path, monkeypatch):
  # no pull request yet: --pr-body alone drives the Run items
  from superegm import collect as collect_mod
  st, worktree, g = builder_worktree(world, tmp_path, monkeypatch)
  unit = st.path("unit", "U01")
  unit.write_text(unit.read_text(encoding="utf-8").replace("2. Run `true` — passes\n3. Exists `src/hooks.py`\n4. CI green on the head\n",
                                                           TWO_RUNS), encoding="utf-8")
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  del state["units"]["U01"]["pr"]  # round 1, no draft pull request
  st.path("state").write_text(json.dumps(state), encoding="utf-8")
  ran, dirs, real = [], [], collect_mod.dod_runs

  def fake(items, cwd, env, deadline, out_dir):  # each command's output stands in for the run: a count line, no pytest
    ran.extend(cmd for _, cmd, _ in items)
    dirs.append(Path(out_dir))
    return real([(n, f"echo '{paste}'", paste) for n, _, paste in items], cwd, env, deadline, out_dir)
  monkeypatch.setattr(collect_mod, "dod_runs", fake)
  store_bytes_before = snapshot(st.root)
  git_status_before = g("status", "--porcelain", "--ignored", cwd=worktree)
  code, out = precheck(world, st, tmp_path, TWO_PASTED)
  store_bytes_after = snapshot(st.root)
  git_status_after = g("status", "--porcelain", "--ignored", cwd=worktree)
  assert ran == ["pytest tests/unit/test_u07.py -q", "pytest tests/unit -q"]
  assert (store_bytes_after, git_status_after) == (store_bytes_before, git_status_before)
  assert (code, out) == (0, "")
  assert not dirs[0].exists() and not dirs[0].is_relative_to(st.root) and not dirs[0].is_relative_to(worktree)


@pytest.mark.parametrize("app", [True, False])
def test_every_launch_writes_and_allows_the_precheck_script(app, world, monkeypatch, key, tmp_path, spawn_fake):
  # the App and machine-account paths alike
  import shutil
  import superegm
  from superegm import orient
  from superegm.launch_builder import CONFIG_DEFAULTS
  monkeypatch.setattr(orient, "GRAPHIFY", "superegm-no-such-tool")  # test_builders' autouse fixtures, applied here alone
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"gh": "/usr/local/bin/gh", "openssl": OPENSSL}.get(cmd))
  if app:
    s, card, _, _, _ = app_seed(world, monkeypatch, key, tmp_path)
  else:
    s, card, _, _ = builders_seed(world)
    monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  real = superegm.Handoff

  class Spaced(real):  # the config as read with `artifacts_dir` holding a space; the store stays where it is
    def __init__(self, *a, **k):
      super().__init__(*a, **k)
      self.config = {**self.config, "artifacts_dir": "/tmp/a b"}
  monkeypatch.setattr(superegm, "Handoff", Spaced)
  whitespace_code, whitespace_out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  monkeypatch.setattr(superegm, "Handoff", real)
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  assert code == 0, out
  script = s.path("launches", f"{UNIT}_r1_bin", "superegm-precheck")
  tools = launches_of(s)[-1]["command"].split("--allowedTools '")[1].split("'")[0].split(",")
  prompt = s.path("launches", f"{UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  assert (script.name, script.parent.name, os.access(script, os.X_OK)) == ("superegm-precheck", "U07_r1_bin", True)
  assert f"Bash({script.parent}/superegm-precheck:*)" in tools and "Bash(git reset --hard:*)" in tools
  assert str(script) in prompt and "{{precheck}}" not in prompt
  assert CONFIG_DEFAULTS["builder"]["precheck_attempts"] == 3
  assert whitespace_code == 1 and "artifacts_dir /tmp/a b holds whitespace" in whitespace_out
  assert f"'{sys.executable}' '{HELPER}' precheck --handoff '{s.handoff_id}' --unit '{UNIT}' \"$@\"" in script.read_text(encoding="utf-8")


@pytest.mark.parametrize("phrase", [
  "{{precheck}}", "600000", "before every push", "merge round", "`builder.precheck_attempts`",
  "git reset --hard", "never one older than the pull request's tip", "**Precheck reply <n>:** contested", "**Precheck:**"])
def test_orders_carry_the_precheck_step(phrase):
  # precheck, then a self-review against the DoD and Scope paths, before each push, with no subagent
  assert phrase in Path("skills/wave/references/builder_orders.md").read_text()
