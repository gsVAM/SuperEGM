# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U71

"""U71 (spec 1.2.1 section 7.4): `driver kick` ticks one store at once (registered, installed, chain on) with the
env file applied, under a `tick/lock` shared with `tick`; `driver env` writes the env file; both wrappers end with
the `env -i` kick; `register --root` names the base worktree; the SDLC step and review-spec's approval name the
chain's setup. Every path is under `tmp_path` (`HOME` patched); no test reaches launchd, systemd or `claude`."""

import os

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import driver
from test_builders import put
from test_driver import registered
from test_u44 import edit_config


def install_marker(tmp_path):
  """The installed driver as the kick reads it: the launchd plist file under the patched `HOME`."""
  put(driver.plist_path(), "<plist/>")


def fake_tick_store(monkeypatch):
  """`tick_store` recorded: each call's store and the environment it ran under."""
  calls = []
  monkeypatch.setattr(driver, "tick_store", lambda entry: calls.append((entry["artifacts_dir"], dict(os.environ))))
  return calls


@pytest.mark.parametrize("registered_, installed, chain, ticks", [
  (True, True, True, 1), (False, True, True, 0), (True, False, True, 0), (True, True, None, 0), (True, True, False, 0)])
def test_kick_ticks_one_store_or_nothing(world, monkeypatch, tmp_path, registered_, installed, chain, ticks):
  # no run card in any case; the env file's keys reach the tick and are restored after it
  registered(world, monkeypatch, tmp_path)
  env = tmp_path / ".superegm/env"
  put(env, env.read_text(encoding="utf-8") + "GH_X=from-env-file\n"); env.chmod(0o600)
  monkeypatch.delenv("GH_X", raising=False)
  edit_config(world.repo, driver=None if chain is None else {"chain": chain})
  if installed:
    install_marker(tmp_path)
  ticked = fake_tick_store(monkeypatch)
  root = world.repo if registered_ else tmp_path / "elsewhere"
  root.mkdir(exist_ok=True)
  code, out = world.run("driver", "kick", "--root", root, card=None)
  assert (code, len(ticked)) == (0, ticks)
  tick_env = ticked[0][1] if ticked else {}
  assert tick_env.get("GH_X") == ("from-env-file" if ticks else None) and "GH_X" not in os.environ
  assert out == ""
  if ticks:
    assert ticked[0][0] == str(world.artifacts) or os.path.samefile(ticked[0][0], world.artifacts)
