# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U25, the foreman verifies: the DoD re-run and the test delta (spec §11.1).

"""U25: the `foreman` config key, `kill_group`, `dod_runs`, `test_delta`, the forced removal and the hook-free checkouts."""

import re
import signal
import subprocess
import time

import pytest

import superegm
from conftest import REPO, set_config
from superegm import init, kill_group
from superegm.collect import KILL_WAIT, dod_runs, run_env, test_delta
from superegm.launch_builder import SENTINEL, allowed_tools


@pytest.mark.parametrize("given, expect", [(None, 8), ({"run_timeout_minutes": 0.02}, 0.02), ({"run_timeout_minutes": 10}, None)])
def test_foreman_config_key_and_the_init_sentence(world, given, expect):
  assert superegm.DEFAULT_CONFIG["foreman"] == {"run_timeout_minutes": 8} and "foreman.run_timeout_minutes" in init.STEPS
  set_config(world, repo=REPO, **({"foreman": given} if given else {}))
  if expect is None:
    with pytest.raises(superegm.HandoffError, match=re.escape("foreman.run_timeout_minutes must be a number above 0 and at most 9")):
      superegm.load_config(world.repo)
  else:
    assert superegm.load_config(world.repo)["foreman"] == {"run_timeout_minutes": expect}


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


test_delta.__test__ = False  # the helper's name starts `test_`: pytest must not collect it here
F, T = "tests/unit/test_a.py", lambda *lines: "\n".join(lines) + "\n"
BASE = T("import pytest", "@pytest.mark.parametrize('x', [", "  (1,),", "  (2,),", "])", "def test_a(x):", "  assert x == x", "  assert 1 in [1]", "  with pytest.raises(ValueError):", "    int('a')")
E = lambda line, base_line, kind="removed": {"file": F, "line": line, "base_line": base_line, "kind": kind, "base_commit": "b"}


@pytest.mark.parametrize("head, named, expect", [
  (BASE.replace("assert x == x", "assert x == 1"), set(), []), (BASE.replace("  assert 1 in [1]\n", ""), set(), [E(8, 8)]), (BASE.replace("  assert 1 in [1]\n", ""), {F}, []),
  (BASE.replace("assert x == x", "assert x"), set(), [E(7, 7, "weakened")]), (BASE.replace("pytest.raises", "contextlib.suppress"), set(), [E(9, 9, "weakened")]),
  (BASE.replace("  (2,),\n", ""), set(), [E(4, 4)]), (BASE.replace("  (1,),\n  (2,),\n", "  (2,),\n  (1,),\n"), set(), []),
  (BASE.replace("def test_a", "@pytest.mark.skip\ndef test_a"), set(), [E(6, 6, "weakened")]), (None, set(), [E(n, n) for n in (3, 4, 6, 7, 8, 9)])])
def test_test_delta_pairs_assertions_as_git_does(head, named, expect):
  assert test_delta({F: ("b", BASE)}, {F: head} if head is not None else {}, named) == expect
