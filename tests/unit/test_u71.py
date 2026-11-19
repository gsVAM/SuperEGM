# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U71

"""U71 (spec 1.2.1 section 7.4): `driver kick` ticks one store at once (registered, installed, chain on) with the
env file applied, under a `tick/lock` shared with `tick`; `driver env` writes the env file; both wrappers end with
the `env -i` kick; `register --root` names the base worktree; the SDLC step and review-spec's approval name the
chain's setup. Every path is under `tmp_path` (`HOME` patched); no test reaches launchd, systemd or `claude`."""

import fcntl
import json
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


def chain_store(world, monkeypatch, tmp_path):
  """A registered, installed, chain-on store (`s1`); returns its artifacts dir."""
  registered(world, monkeypatch, tmp_path)
  edit_config(world.repo, driver={"chain": True})
  install_marker(tmp_path)
  return world.artifacts


@pytest.mark.parametrize("case, ticked, again_left", [
  ("kick while held", ["s1", "s1"], False), ("kick while held, holder still running", ["s1"], True),
  ("tick over a held store", ["s2"], True)])
def test_lock_never_loses_or_doubles_a_kick(world, monkeypatch, tmp_path, case, ticked, again_left):
  # tick/again is written before the non-blocking flock on tick/lock is tried
  store = chain_store(world, monkeypatch, tmp_path)
  other = tmp_path / "artifacts2"
  names = {os.path.realpath(store): "s1", os.path.realpath(other): "s2"}
  calls, seen = [], {}

  def fake(entry):
    calls.append(names[os.path.realpath(entry["artifacts_dir"])])
    if case != "tick over a held store" and len(calls) == 1:
      assert driver.kick(world.repo) == 0  # a second kick while this one holds the lock
      seen["calls"], seen["again"] = list(calls), (store / "tick" / "again").exists()
  monkeypatch.setattr(driver, "tick_store", fake)
  if case == "tick over a held store":
    registry = superegm.registry_path()
    entries = json.loads(registry.read_text(encoding="utf-8"))
    entries.append({"repo": entries[0]["repo"], "root": str(tmp_path / "root2"), "artifacts_dir": str(other)})
    put(registry, json.dumps(entries))
    put(store / "tick" / "lock", "")
    with open(store / "tick" / "lock", "r") as held:
      fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
      assert world.run("driver", "tick", card=None)[0] == 0
  else:
    assert world.run("driver", "kick", "--root", world.repo, card=None)[0] == 0
  if case == "kick while held, holder still running":
    calls, again = seen["calls"], seen["again"]
  else:
    again = (store / "tick" / "again").exists()
  assert (calls, again) == (ticked, again_left)


def set_builder(repo, **keys):
  """The repository config's `builder` with `keys` set, its other keys kept."""
  path = repo / ".superegm" / "config.json"
  config = json.loads(path.read_text(encoding="utf-8"))
  config["builder"] = {**config.get("builder", {}), **keys}
  path.write_text(json.dumps(config), encoding="utf-8")


def profile_with_hook_plugin(profile, subagent_hook):
  """A Claude Code profile enabling `hook-plugin@market`, whose `hooks/hooks.json` has a `SubagentStart` hook; its
  own `settings.json` names a `SubagentStart` hook only when `subagent_hook`."""
  plugin = profile / "plugins" / "cache" / "hook-plugin"
  put(plugin / "hooks" / "hooks.json", json.dumps({"hooks": {"SubagentStart": [{"hooks": [{"type": "command", "command": "true"}]}]}}))
  put(profile / "plugins" / "installed_plugins.json",
      json.dumps({"version": 2, "plugins": {"hook-plugin@market": [{"scope": "user", "installPath": str(plugin)}]}}))
  settings = {"enabledPlugins": {"hook-plugin@market": True}}
  if subagent_hook:
    settings["hooks"] = {"SubagentStart": [{"hooks": [{"type": "command", "command": "true"}]}]}
  put(profile / "settings.json", json.dumps(settings))


@pytest.mark.parametrize("case, keys, code, out_part", [
  ("token and mcp", {"PATH", "CLAUDE_CONFIG_DIR", "GH_X", "API_Y"}, 0, None), ("API_Y unset", None, 1, "env: API_Y unset"),
  ("app key KEY_Z, token unset", {"PATH", "CLAUDE_CONFIG_DIR", "KEY_Z", "API_Y"}, 0, None), ("existing file, no --replace", {"OLD"}, 0, None),
  ("SubagentStart hook", None, 1, "SubagentStart")])
def test_driver_env_writes_the_configured_names(world, monkeypatch, tmp_path, case, keys, code, out_part):
  # values never printed; doctor names a configured name the file lacks and an enabled plugin's SubagentStart hook
  from superegm import doctor
  registered(world, monkeypatch, tmp_path)
  env_file = tmp_path / ".superegm" / "env"
  env_file.unlink()
  if case == "existing file, no --replace":
    put(env_file, "OLD=1\n"); env_file.chmod(0o600)
  profile = tmp_path / "driver-profile"
  profile_with_hook_plugin(profile, case == "SubagentStart hook")
  monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(profile))
  for name in ("GH_X", "API_Y", "KEY_Z"):
    monkeypatch.setenv(name, "secret-value")
  mcp = {"api": {"type": "http", "url": "https://example.invalid/mcp", "headers": {"Authorization": "Bearer ${API_Y}"}}}
  set_builder(world.repo, gh_token_env="GH_X", mcp=mcp)
  if case == "API_Y unset":
    monkeypatch.delenv("API_Y")
  if case.startswith("app key"):
    monkeypatch.delenv("GH_X")
    set_builder(world.repo, app={"app_id": 7, "slug": "the-app", "private_key_env": "KEY_Z"})
  card = world.open_card("driver", world.spec)
  result_code, out = world.run("driver", "env", "--runcard", card)
  assert result_code == code and (out_part is None or out_part in out)
  env_file_exists = env_file.is_file()
  env_keys = {line.split("=", 1)[0] for line in env_file.read_text(encoding="utf-8").splitlines()} if env_file_exists else set()
  assert (env_keys if keys else env_file_exists) == (keys if keys else (case == "existing file, no --replace"))
  assert not keys or oct(env_file.stat().st_mode & 0o777) == "0o600"
  if keys and "GH_X" in keys:
    assert "GH_X=secret-value" in env_file.read_text(encoding="utf-8")
  if not env_file_exists:  # doctor reads the driver's profile from the env file: one naming it, no credential
    put(env_file, f"PATH=/usr/bin\nCLAUDE_CONFIG_DIR={profile}\n"); env_file.chmod(0o600)
  set_builder(world.repo, gh_token_env="GH_Q", app=None)
  lines = [text for name, text in doctor.driver_lines(superegm.load_config(world.repo)) if name == "driver"]
  doctor_out = "\n".join(lines)
  doctor_lacks_line = next((t for t in lines if "lacks" in t), "")
  doctor_hook_line = next((t for t in lines if "SubagentStart" in t), "")
  assert "secret-value" not in out + doctor_out and "GH_Q" in doctor_lacks_line and "hook-plugin" in doctor_hook_line
