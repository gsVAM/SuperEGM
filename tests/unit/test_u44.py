# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U44's tests: the phase-aware tick behind `driver.chain`.

"""U44 (spec section 7.1): the tick fetches the base into `refs/superegm/tick-base`, asks `superegm next` and launches,
proves, counts and reports the session of the chain phase that comes next; with `driver.chain` absent or false it is
1.2's tick. Every path is under `tmp_path` (`HOME` patched); the fetch is faked; no test reaches launchd or `claude`."""

import json
import subprocess
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import driver, phase
from conftest import ROOT, make_repo, Harness
from test_builders import put, spawn_fake, SPAWNED  # noqa: F401  (spawn_fake: a fixture)
from test_driver import registered
from test_u24 import tick_launches


def edit_config(repo, **keys):
  """The repository's config with `keys` set (None removes one), every other key kept."""
  path = repo / ".superegm" / "config.json"
  config = json.loads(path.read_text(encoding="utf-8"))
  for key, value in keys.items():
    if value is None:
      config.pop(key, None)
    else:
      config[key] = value
  path.write_text(json.dumps(config), encoding="utf-8")


def watch(monkeypatch):
  """The fetches and the `next` calls a tick makes, recorded: the fetch faked (no network), `next` passed through."""
  calls = {"fetch": [], "next": []}

  def fetch(root, remote, base):
    calls["fetch"].append((str(root), remote, base))
    return True, ""
  real = phase.next_line
  monkeypatch.setattr(driver, "fetch_base", fetch, raising=False)
  monkeypatch.setattr(phase, "next_line", lambda st, hid, read_wait=True: (calls["next"].append(hid), real(st, hid, read_wait))[1])
  return calls


@pytest.mark.parametrize("chain", [None, False])
def test_chain_off_is_1_2(world, monkeypatch, tmp_path, spawn_fake, chain, capsys):
  """Absent or false: the tick neither fetches nor asks next, writes no tick/fetch.json, types the 1.2 prompt; the
  driver skill names the chain's tick; `init` writes no `driver` key."""
  s, hid = registered(world, monkeypatch, tmp_path)
  edit_config(world.repo, driver=None if chain is None else {"chain": chain})
  calls = watch(monkeypatch)
  code, out = world.run("driver", "tick")
  assert code == 0, out
  assert calls == {"fetch": [], "next": []}
  assert subprocess.run(["git", "-C", str(world.repo), "rev-parse", "-q", "--verify", "refs/superegm/tick-base"],
                        capture_output=True).returncode != 0
  assert not (world.artifacts / "tick" / "fetch.json").exists()
  last = tick_launches(s, hid)[-1]
  assert f"claude -p '/superegm:wave {world.spec.resolve()} --handoff {hid} --leavemealone' " in last["command"]
  assert driver.tick_prompt(world.spec, hid) == f"/superegm:wave {world.spec} --handoff {hid} --leavemealone"
  text = (ROOT / "skills" / "driver" / "SKILL.md").read_text(encoding="utf-8")
  assert "driver.chain" in text and "superegm next" in text
  fresh = make_repo(tmp_path / "fresh")
  monkeypatch.chdir(fresh)
  harness = Harness(capsys)
  harness.gh.extend("api", lambda args, cwd, token=None: (0, "octocat\n", "") if args[1:] == ["user", "-q", ".login"] else (1, "", "x"))
  code, out = harness.run("init", "--artifacts-dir", str(tmp_path / "store"))
  assert code == 0, out
  assert "driver" not in json.loads((fresh / ".superegm" / "config.json").read_text(encoding="utf-8"))
