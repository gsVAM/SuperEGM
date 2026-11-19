# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U71

"""U71 (spec 1.2.1 section 7.4): `driver kick` ticks one store at once (registered, installed, chain on) with the
env file applied, under a `tick/lock` shared with `tick`; `driver env` writes the env file; both wrappers end with
the `env -i` kick; `register --root` names the base worktree; the SDLC step and review-spec's approval name the
chain's setup. Every path is under `tmp_path` (`HOME` patched); no test reaches launchd, systemd or `claude`."""

import fcntl
import json
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import git
import superegm  # the harness reloads the package per test: read its names at call time
from superegm import driver
from test_builders import put, seed, spawn_fake, UNIT  # noqa: F401 (spawn_fake is a fixture)
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


@pytest.mark.parametrize("wrapper", ["builder", "phase"])
def test_wrappers_end_with_the_env_i_kick(world, monkeypatch, tmp_path, spawn_fake, wrapper):
  # after .exit or the session's end; failure ignored and logged, interpreter and helper quoted
  from superegm.launch_builder import HELPER
  s, _ = registered(world, monkeypatch, tmp_path)  # the registry entry: root world.repo, the store world.artifacts
  root = Path(json.loads(superegm.registry_path().read_text(encoding="utf-8"))[0]["root"])
  if wrapper == "builder":
    card = world.open_card("wave", world.spec)
    monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
    assert world.run("launch", "--runcard", card)[0] == 0
    code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
    assert code == 0, out
    command = spawn_fake[-1][0][2]
    head = command.rstrip().splitlines()[0]
    assert head.endswith(".exit'")  # the kick comes after the exit file is written
  else:
    command = driver.tick_command(root, "/superegm:wave spec", tmp_path / "r.json", tmp_path / "r.exit")
  tail = command.rstrip().splitlines()[-1]
  assert tail.startswith('env -i HOME="$HOME" PATH="$PATH" ') and f"driver kick --root {shlex.quote(str(root))}" in tail
  assert f"{shlex.quote(sys.executable)} {shlex.quote(str(HELPER))} driver kick" in tail
  assert "||" in tail  # a failed kick is logged, never fails the wrapper
  monkeypatch.setattr(driver, "RUN", lambda argv, **k: subprocess.CompletedProcess(argv, 0)); monkeypatch.setattr(driver, "PLATFORM", "darwin")
  dcard = world.open_card("driver", world.spec)
  assert world.run("driver", "install", "--runcard", dcard)[0] == 0
  install_interval_default = plistlib.loads(driver.plist_path().read_bytes())["StartInterval"] // 60
  assert install_interval_default == 5


@pytest.mark.parametrize("base_config, on_base, code", [(None, True, 0), ("older store", True, 0), (None, False, 1)])
def test_register_root_names_the_base_worktree(world, monkeypatch, tmp_path, base_config, on_base, code):
  # run from a spec worktree; the store and card resolve from the current checkout
  monkeypatch.setenv("HOME", str(tmp_path / "home"))
  seed(world)  # an approved handoff: the card's spec is the handoff's
  base_wt, current_store = world.repo, world.artifacts
  spec_wt, other_wt = tmp_path / "spec-wt", tmp_path / "other-wt"
  git(["worktree", "add", "-q", "-b", "spec/x", str(spec_wt)], base_wt)
  git(["worktree", "add", "-q", "-b", "feature", str(other_wt)], base_wt)
  config = base_wt / ".superegm" / "config.json"
  if base_config == "older store":
    data = json.loads(config.read_text(encoding="utf-8")); data["artifacts_dir"] = str(tmp_path / "older-artifacts")
    config.write_text(json.dumps(data), encoding="utf-8")
  else:
    config.unlink()
  monkeypatch.chdir(spec_wt)
  card = world.open_card("driver", spec_wt / "docs/designs/sample.md")
  root = base_wt if on_base else other_wt
  result_code, out = world.run("register", "--root", root, "--runcard", card)
  assert result_code == code, out
  entries = json.loads(superegm.registry_path().read_text(encoding="utf-8")) if superegm.registry_path().is_file() else []
  found = next((e for e in entries if os.path.realpath(e["artifacts_dir"]) == os.path.realpath(current_store)), None)
  entry = found and {"root": found["root"], "store": found["artifacts_dir"]}
  if code == 0:
    assert (entry["root"], entry["store"]) == (str(base_wt), str(current_store))
  else:
    assert entry is None and f"register: {other_wt}: not a checkout on main" in out


@pytest.mark.parametrize("skill, phrase", [
  ("brainstorming", "after doctor passes"), ("brainstorming", "`driver.chain`"), ("brainstorming", "commit"),
  ("brainstorming", "nothing outside the repository"), ("brainstorming", "effects: working-tree"),
  ("review-spec", "after `approve-spec` exits 0"), ("review-spec", "driver env"), ("review-spec", "driver install"),
  ("review-spec", "skip `register` for a registered store"), ("review-spec", "git worktree list"),
  ("review-spec", "register --root"), ("review-spec", "/superegm:driver register"), ("review-spec", "the approval stands")])
def test_skills_name_the_chain_setup(skill, phrase):
  # the owner's word turns the chain on; review-spec's approval sets the driver up only when chain is true and not current
  assert phrase in (superegm_root() / f"skills/{skill}/SKILL.md").read_text(encoding="utf-8")


def superegm_root():
  """The repository root: the skills read from the checkout under test, whatever the working directory."""
  return Path(__file__).resolve().parents[2]


def test_a_builder_wrapper_without_a_registry_entry_has_no_kick(world, monkeypatch, tmp_path, spawn_fake):
  """No registry entry names the launch's store: the wrapper is the one line it was."""
  monkeypatch.setenv("HOME", str(tmp_path))
  _, card, _, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)[0] == 0
  command = spawn_fake[-1][0][2]
  assert "driver kick" not in command and len(command.rstrip().splitlines()) == 1
