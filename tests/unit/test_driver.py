# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U24's tests of the driver's tick and its four actions.

"""U24 (spec section 11.2): `driver tick`'s predicate, table by table, and `install`, `uninstall`, `status` and
`reset`. Every path is under `tmp_path` (`HOME` patched); no test reaches launchd, systemd or `claude`."""

import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import driver, status
from superegm.launch_builder import HELPER
from conftest import REPO, make_pr
from test_builders import seed, put, spawn_fake, SPAWNED, UNIT  # noqa: F401  (spawn_fake: a fixture)
from test_u24 import tick_launch, wave_of, card_of, tick_launches, driver_file

A = "a" * 40


def registered(world, monkeypatch, tmp_path):
  """The base: `HOME` and `boot_id` `boot-1` patched, `seed` with its `wave` card closed, `~/.superegm/env` (0600),
  `<tmp>/bin/git` recording the `PATH` it ran under, `~/.superegm/notify` exiting 0, the store registered under a
  closed `driver` card. Returns `(s, hid)`."""
  monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setattr(superegm, "boot_id", lambda: "boot-1")
  s, card, hid, _ = seed(world)
  assert world.run("runcard", "close", card)[0] == 0
  env = tmp_path / ".superegm/env"
  put(env, f"PATH={tmp_path}/bin\nCLAUDE_CONFIG_DIR={tmp_path}/profile\nSUPEREGM_BUILDER_TOKEN=ghp_builder\n"); env.chmod(0o600)
  gitbin = tmp_path / "bin/git"
  put(gitbin, f"#!/bin/sh\necho \"$PATH\" > '{tmp_path}/git-path'\nexec '{shutil.which('git')}' \"$@\"\n"); gitbin.chmod(0o755)
  hook = tmp_path / ".superegm/notify"
  put(hook, "#!/bin/sh\nexit 0"); hook.chmod(0o755)
  dcard = world.open_card("driver", world.spec)
  assert world.run("register", "--runcard", dcard)[0] == 0 and world.run("runcard", "close", dcard)[0] == 0
  return s, hid


def state_of(s):
  return json.loads(s.path("state").read_text(encoding="utf-8"))


def save_status(world, s, at):
  """`state.status` as a `status --wait` saves it now, its `at` the given time."""
  state = state_of(s)
  handoff = superegm.Handoff(Path(state["plan"]), s, state)
  summary, _ = superegm.status_pass(handoff, save=False)
  state["status"] = {**summary, "at": at, "units": {u: status.fingerprint(v) for u, v in summary["units"].items()}}
  put(s.path("state"), json.dumps(state))


def notified(s, hid, *ids):
  path = driver_file(s, hid)
  data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"launches": [], "notified": [], "refused": None}
  data["notified"] = sorted(set(data["notified"]) | set(ids))
  put(path, json.dumps(data))


def arranged(world, monkeypatch, tmp_path, case):
  """`registered`, then `CASES[case]` applied in key order. Returns `(s, hid, the case's live card or None)`."""
  s, hid = registered(world, monkeypatch, tmp_path)
  spec, live, boot, seed_card = str(world.spec), None, "boot-1", sorted((s.root / hid / "runcards").glob("wave-*.json"))[0].stem
  monkeypatch.delenv("SUPEREGM_ROLE", raising=False); monkeypatch.delenv("SUPEREGM_RUNCARD", raising=False)
  for key, value in CASES[case].items():
    if key == "tick":
      for kw in value if isinstance(value, list) else [value]:
        kw = {"card": f"driver-abc-000{kw.get('n', 1)}", **kw}; boot = kw.get("boot", "boot-1"); tick_launch(s, hid, **kw)
    elif key == "wave":
      live = wave_of(world, monkeypatch, tick_launches(s, hid)[-1]["card"], boot)
      if value == "open": notified(s, hid, live)
      else: assert world.run("runcard", "close", live)[0] == 0
    elif key == "typed":
      world.advance(60); live = world.open_card("wave", spec)
      if value == "open": notified(s, hid, live)
      else: world.advance(60); assert world.run("runcard", "close", live)[0] == 0
    elif key == "child":
      code, out = world.run("runcard", "open", "--skill", "wave", "--artifact", spec, "--parent", seed_card, card=None); assert code == 0, out; live = out.strip()
    elif key == "card":
      world.open_card(value, spec)
    elif key == "pr":
      make_pr(world.gh, value, A, branch=f"superegm/{hid}/{UNIT}", closes=[(REPO, 7)])
      state = state_of(s); state["units"][UNIT]["pr"] = {"number": value, "head": A, "base_ref": "main"}; put(s.path("state"), json.dumps(state))
    elif key == "status_at":
      save_status(world, s, superegm.now_iso() if value in ("head", "after") else value)
    elif key == "posted":
      put(s.path("foreman", UNIT), json.dumps({"dispatch_id": "d1", "decisions": [], "rulings": [], "ingested": [], "rounds": [
          {"round": value, "runcard": seed_card, "launch": 1, "head": A, "phase": "posted", "dispatch_id": "d1", "outcome": "revise", "posted_at": superegm.now_iso()}]}))
    elif key == "thread":
      severity, role = value
      thread = {"id": "t1", "login": "alice", "bot": False, "body": "fix this", "path": "a.py", "line": 1, "commit_id": A, "review_body": "", "created_at": superegm.now_iso()}
      monkeypatch.setattr(status, "read_threads", lambda repo, number, skip: [thread])
      monkeypatch.setattr(status, "thread_severity", lambda t, config, r: severity)
      monkeypatch.setattr(status, "collaborator_role", lambda repo, login: role)
    elif key == "reset":
      assert world.run("driver", "reset", "--runcard", world.open_card("driver", spec))[0] == 0
    elif key == "root":
      registry = tmp_path / ".superegm/registry.json"
      put(registry, json.dumps([{**e, "root": str(tmp_path / value)} for e in json.loads(registry.read_text(encoding="utf-8"))]))
  return s, hid, live


CASES = {"first": {}, "live": {"tick": {"boot": "boot-1"}, "wave": "open"}, "reboot": {"tick": {"boot": "boot-0"}, "wave": "open"}, "typed-wave": {"typed": "open"}, "child-card": {"child": "open"},
         "phase-card": {"card": "plan"}, "nothing": {"tick": {"exit": 0}, "wave": "closed", "status_at": "2026-11-03T02:00:00Z"}, "exited-open-card": {"tick": {"exit": 0}, "wave": "open", "status_at": "2026-11-03T02:00:00Z", "pr": 70},
         "thread": {"pr": 70, "status_at": "head", "posted": 1, "thread": ("medium", "write")}, "twice-failed": {"tick": [{"exit": 1}, {"exit": 1, "n": 2}]}, "reset": {"tick": [{"exit": 1}, {"n": 2}], "reset": True},
         "typed-success": {"tick": [{"exit": 1}, {"exit": 1, "n": 2}], "typed": "closed", "status_at": "after", "pr": 70}, "bad-root": {"root": "x"}}
@pytest.mark.parametrize("case, expect", [("first", "launch"), ("live", "skip"), ("reboot", "launch"), ("typed-wave", "skip"), ("child-card", "launch"), ("exited-open-card", "launch"), ("phase-card", "skip"),
                                          ("nothing", "nothing"), ("thread", "launch"), ("twice-failed", "refuse"), ("reset", "launch"), ("typed-success", "launch"), ("bad-root", "refuse")])
def test_tick_predicate(world, monkeypatch, tmp_path, spawn_fake, case, expect):
  s, hid, live = arranged(world, monkeypatch, tmp_path, case); before = sorted(str(p) for p in s.root.rglob("*"))
  code, out = world.run("driver", "tick"); launches, journal = tick_launches(s, hid), s.path("journal").read_text(); assert code == 0
  if expect == "launch":
    last, (command, log, env) = launches[-1], SPAWNED[-1]; reason = {"thread": "U07 threads 1 un-ingested", "reboot": "reboot 1", "exited-open-card": f"exit-file {live}"}.get(case, "first launch" if case in ("first", "reset", "child-card") else f"U07 head pr=70 sha={A} ci=pending")
    assert (last["status"], last["pid"], last["boot_id"], last["reason"], last["command"]) == ("running", 4242, "boot-1", reason, command[2]) and command[:2] == ["/bin/sh", "-c"]
    assert command[2] == f"cd '{world.repo.resolve()}' && claude -p '/superegm:wave {world.spec.resolve()} --handoff {hid} --leavemealone' --permission-mode bypassPermissions --output-format json > '{last['result_file']}'; echo $? > '{last['exit_file']}'"
    assert (env["SUPEREGM_ROLE"], env["SUPEREGM_RUNCARD"], env["PATH"]) == ("driver", last["card"], f"{tmp_path}/bin") and (tmp_path / "git-path").read_text().strip() == env["PATH"] and card_of(s, last["card"])["closed_at"] and f"tick: {hid} launch {last['round']} running (pid 4242)" in journal
    assert f"launch:{hid}:{last['round']}" in json.loads((s.root / hid / "driver" / f"{hid}.json").read_text())["notified"] and (case != "child-card" or not card_of(s, live)["interrupted_at"])
    assert case not in ("reboot", "exited-open-card") or (card_of(s, live)["interrupted_at"] and launches[0]["status"] == ("interrupted (reboot)" if case == "reboot" else "running")); return
  assert not SPAWNED and (expect == "refuse" or (out == "" and sorted(str(p) for p in s.root.rglob("*")) == before))
  if expect == "refuse":
    reason = f"root {tmp_path / 'x'} is not a worktree of {REPO}" if case == "bad-root" else "two launches failed before the loop ran"; data = json.loads((s.root / hid / "driver" / f"{hid}.json").read_text())
    assert f"tick: refused ({hid}: {reason})" in journal and data["refused"]["reason"] == reason and f"refused:{hid}" in data["notified"]


@pytest.mark.parametrize("platform, interval", [("darwin", None), ("darwin", 5), ("linux", None)])
def test_driver_install_status_and_reset(world, monkeypatch, tmp_path, platform, interval):
  s, hid = registered(world, monkeypatch, tmp_path); dcard, uid, minutes, calls = world.open_card("driver", world.spec), os.getuid(), interval or 15, []
  monkeypatch.setattr(driver, "RUN", lambda argv, **k: (calls.append(argv), subprocess.CompletedProcess(argv, 0))[1]); monkeypatch.setattr(driver, "PLATFORM", platform)
  code, out = world.run("driver", "install", *(["--interval", interval] if interval else []), "--runcard", dcard); plist = tmp_path / "Library/LaunchAgents/com.superegm.driver.plist"
  if platform == "darwin":
    assert code == 0 and out.strip() == f"installed ({minutes} min): {plist}" and calls == [["launchctl", "bootout", f"gui/{uid}", str(plist)], ["launchctl", "bootstrap", f"gui/{uid}", str(plist)]]
    assert plistlib.loads(plist.read_bytes()).items() >= {"Label": "com.superegm.driver", "ProgramArguments": [sys.executable, str(HELPER), "driver", "tick"], "StartInterval": minutes * 60, "AbandonProcessGroup": True}.items()
    assert world.run("driver", "uninstall", "--runcard", dcard)[0] == 0 and not plist.exists()
  else:
    unit = (tmp_path / ".config/systemd/user/superegm-driver.service").read_text(); timer = (tmp_path / ".config/systemd/user/superegm-driver.timer").read_text()
    assert code == 0 and f"ExecStart={sys.executable} {HELPER} driver tick\n" in unit and "KillMode=process\n" in unit and f"OnUnitActiveSec={minutes}min\n" in timer
  entry = tick_launch(s, hid, card=dcard, refused={"at": superegm.now_iso(), "reason": "two launches failed before the loop ran"}); live = wave_of(world, monkeypatch, dcard, "boot-1"); world.advance(600)
  assert world.run("driver", "status")[1] == f"{hid}: launch 1 started {entry['started_at']} pid 4242 exit file no; wave card {live} open 10 min; refused: two launches failed before the loop ran\n"
  assert world.run("driver", "reset", "--runcard", dcard)[1].strip() == f"reset {hid}: launch 1 interrupted; card {live} interrupted" and tick_launches(s, hid)[0]["status"] == "interrupted"
  assert card_of(s, live)["interrupted_at"] and f"driver: {hid} has no live tick launch or open wave card" in world.run("driver", "reset", "--runcard", dcard)[1]
