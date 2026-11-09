# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U25, the foreman verifies: the DoD re-run and the test delta (spec §11.1).

"""U25: the `foreman` config key, `kill_group`, `dod_runs`, `test_delta`, the forced removal and the hook-free checkouts."""

import re
import signal
import subprocess
import time
from pathlib import Path

import pytest

import superegm
from conftest import REPO, set_config
from superegm import init, kill_group
from superegm.collect import KILL_WAIT, dod_runs, run_env, test_delta
from superegm.launch_builder import SENTINEL, add_worktree, allowed_tools
from test_foreman import PR, UNIT, builder_token, prepared  # noqa: F401  builder_token: the autouse token `prepare` reads


@pytest.mark.parametrize("given, expect", [(None, 8), ({"run_timeout_minutes": 0.02}, 0.02), ({"run_timeout_minutes": 10}, None)])
def test_foreman_config_key_and_the_init_sentence(world, given, expect):
  assert superegm.DEFAULT_CONFIG["foreman"] == {"run_timeout_minutes": 8} and "foreman.run_timeout_minutes" in init.STEPS
  set_config(world, repo=REPO, **({"foreman": given} if given else {}))
  if expect is None:
    with pytest.raises(superegm.HandoffError, match=re.escape("foreman.run_timeout_minutes must be a number above 0 and at most 9")):
      superegm.load_config(world.repo)
  else:
    assert superegm.load_config(world.repo)["foreman"] == {"run_timeout_minutes": expect}


@pytest.mark.parametrize("given, message", [({"run_timeout_minutes": 5, "extra": 1}, "foreman: unknown keys ['extra']"), ("8", "foreman must be an object")])
def test_the_foreman_key_names_its_own_fault(world, given, message):
  """Round 2 (PR #103 review): an extra key or a non-object is refused under its own name, not the bound's."""
  set_config(world, repo=REPO, foreman=given)
  with pytest.raises(superegm.HandoffError, match=re.escape(message)):
    superegm.load_config(world.repo)


def test_dod_runs_kills_each_items_group_on_return_and_at_the_bound(tmp_path, monkeypatch):
  p = subprocess.Popen(["/bin/sh", "-c", "sleep 30"], start_new_session=True)
  kill_group(p.pid)
  assert p.wait(timeout=5) == -signal.SIGTERM and kill_group(p.pid) is None
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "x")
  env = run_env("/usr/local/bin/gh", tmp_path)
  assert "SUPEREGM_BUILDER_TOKEN" not in env and (env["GH_TOKEN"], env["PIP_REQUIRE_VIRTUALENV"], env["npm_config_prefix"], env["GIT_CONFIG_GLOBAL"]) == (SENTINEL, "1", str(tmp_path), "/dev/null")
  assert "Bash(.v/bin/pytest:*)" in allowed_tools([], "b", "## Definition of done\n2. Run `python3 -m venv .v && .v/bin/pytest -q` — passes\n", "/usr/local/bin/gh")
  start = time.time()
  runs = dod_runs([(3, "printf 'x\\n== 1 passed in 0.01s ==\\n'", "1 passed"), (4, "echo boom; exit 1", None), (5, "sleep 30 &", None), (6, "sleep 30", None), (7, "true", "ok")], tmp_path, env, start + 1, tmp_path / "dod")
  assert time.time() - start < 1 + KILL_WAIT
  assert runs == {"3": {"exit": 0, "summary": "== 1 passed in 0.01s ==", "paste_summary": "1 passed", "timed_out": False},
                  "4": {"exit": 1, "summary": "boom", "paste_summary": None, "timed_out": False}, "5": {"exit": 0, "summary": "", "paste_summary": None, "timed_out": False},
                  "6": {"exit": None, "summary": "", "paste_summary": None, "timed_out": True}, "7": {"exit": None, "summary": None, "paste_summary": "ok", "timed_out": True}}
  assert sorted(p.name for p in (tmp_path / "dod").iterdir()) == ["3.out", "4.out", "5.out", "6.out"] and (tmp_path / "dod/4.out").read_text() == "boom\n"
  gone = dod_runs([(2, f"echo x; rm -f '{tmp_path / 'gone/2.out'}'", None)], tmp_path, env, time.time() + 5, tmp_path / "gone")
  assert gone == {"2": {"exit": 0, "summary": "", "paste_summary": None, "timed_out": False}}  # a run that unlinks its output


test_delta.__test__ = False  # the helper's name starts `test_`: pytest must not collect it here
F, T = "tests/unit/test_a.py", lambda *lines: "\n".join(lines) + "\n"
BASE = T("import pytest", "@pytest.mark.parametrize('x', [", "  (1,),", "  (2,),", "])", "def test_a(x):", "  assert x == x", "  assert 1 in [1]", "  with pytest.raises(ValueError):", "    int('a')")
E = lambda line, base_line, kind="removed": {"file": F, "line": line, "base_line": base_line, "kind": kind, "base_commit": "b"}


@pytest.mark.parametrize("head, named, expect", [
  (BASE.replace("assert x == x", "assert x == 1"), set(), []), (BASE.replace("  assert 1 in [1]\n", ""), set(), [E(8, 8)]), (BASE.replace("  assert 1 in [1]\n", ""), {F}, []),
  (BASE.replace("assert x == x", "assert x"), set(), [E(7, 7, "weakened")]), (BASE.replace("pytest.raises", "contextlib.suppress"), set(), [E(9, 9, "weakened")]),
  (BASE.replace("  (2,),\n", ""), set(), [E(4, 4)]), (BASE.replace("  (1,),\n  (2,),\n", "  (2,),\n  (1,),\n"), set(), []),
  (BASE.replace("def test_a", "@pytest.mark.skip\ndef test_a"), set(), [E(6, 6, "weakened")]), (None, set(), [E(n, n) for n in (3, 4, 6, 7, 8, 9)]),
  (BASE.replace("def test_a", "@pytest.mark.skipif(True, reason='x')\ndef test_a"), set(), [E(6, 6, "weakened")]),
  (BASE.replace("@pytest.mark.parametrize", "@pytest.mark.skip\n@pytest.mark.parametrize"), set(), [E(2, 6, "weakened")])])
def test_test_delta_pairs_assertions_as_git_does(head, named, expect):
  assert test_delta({F: ("b", BASE)}, {F: head} if head is not None else {}, named) == expect


ONE = T("import pytest", "@pytest.mark.parametrize('x', [1, 2])", "# a note", "def test_b(x):", "  assert x")


@pytest.mark.parametrize("head, expect", [(ONE.replace("# a note\n", ""), []),
  (ONE.replace("# a note", "@pytest.mark.skip"), [E(3, 4, "weakened")]), (ONE.replace("# a note", "@pytest.mark.slow"), []),
  (ONE.replace("# a note\ndef test_b(x):", "@pytest.mark.skip\ndef test_b(x, tmp_path):"), [E(3, 4, "weakened")])])
def test_a_one_line_parametrize_opens_no_rows_and_a_marker_written_over_a_line_is_weakened(head, expect):
  assert test_delta({F: ("b", ONE)}, {F: head}, set()) == expect


def test_allowed_tools_splits_segments_as_the_shell_does():
  text = "## Definition of done\n2. Run `python3 -c \"print('a'); print('b')\" && .v/bin/pytest -q` — passes\n"
  assert [t for t in allowed_tools([], "b", text, "/g") if t.startswith("Bash(") and "git push" not in t] == ["Bash(python3:*)", "Bash(.v/bin/pytest:*)"]
  text = "## Definition of done\n2. Run `printf '%s\\n' ';' \"&&\" \"can't\" && pytest -q;make` — passes\n"
  assert [t for t in allowed_tools([], "b", text, "/g") if t.startswith("Bash(") and "git push" not in t] == ["Bash(printf:*)", "Bash(pytest:*)", "Bash(make:*)"]


def test_prepare_removes_the_review_worktree_by_force_and_checks_out_without_hooks(world, tmp_path, monkeypatch):
  hooks = tmp_path / "hooks"; hooks.mkdir()
  (hooks / "post-checkout").write_text(f"#!/bin/sh\ntouch '{tmp_path / 'ran'}'\n"); (hooks / "post-checkout").chmod(0o755)
  subprocess.run(["git", "config", "core.hooksPath", str(hooks)], cwd=world.repo, check=True)
  w = prepared(world, tmp_path, monkeypatch)
  (w.dir / "worktree/scratch.txt").write_text("left by a Run item\n")
  seen, real = [], subprocess.run
  def spy(argv, *a, **kw):
    if argv[0] == "git":
      d = Path(argv[2].removeprefix("core.hooksPath="))
      assert argv[1] == "-c" and argv[3:5] == ["-c", "core.fsmonitor=false"] and d.name.startswith("superegm-no-hooks-"), argv
      assert d.is_dir() and not any(d.iterdir()) and d.stat().st_mode & 0o777 == 0o700
      seen.append(d)
    return real(argv, *a, **kw)
  monkeypatch.setattr(subprocess, "run", spy)
  assert world.run("prepare", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)[0] == 0
  assert not (w.dir / "worktree/scratch.txt").exists() and (w.dir / "worktree").is_dir()
  assert add_worktree(world.repo, w.st, UNIT, 2, f"superegm/{w.st.handoff_id}/{UNIT}", PR).is_dir()
  assert seen and not (tmp_path / "ran").exists() and not any(d.exists() for d in seen)
