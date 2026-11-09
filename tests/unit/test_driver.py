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


# ---------------------------------------------------------------- round 2: the review findings of round 1

CASES["stale-refusal"] = {"tick": {"exit": 0, "refused": {"at": "2026-11-03T00:00:00Z", "reason": "two launches failed before the loop ran"}},
                          "wave": "closed", "status_at": "2026-11-03T02:00:00Z"}


def test_reset_lifts_a_refusal_of_two_exited_failures(world, monkeypatch, tmp_path, spawn_fake):
  s, hid, _ = arranged(world, monkeypatch, tmp_path, "twice-failed"); assert world.run("driver", "tick")[0] == 0 and not SPAWNED
  out = world.run("driver", "reset", "--runcard", world.open_card("driver", world.spec))[1]
  assert out.strip() == f"reset {hid}: refusal cleared; failures 1-2 set aside" and f"driver: {hid} failures 1-2 set aside by reset" in s.path("journal").read_text()
  assert world.run("driver", "tick")[0] == 0 and tick_launches(s, hid)[-1]["status"] == "running" and len(SPAWNED) == 1


def test_the_proofs_run_for_a_handoff_with_nothing_left_to_build(world, monkeypatch, tmp_path, spawn_fake):
  s, hid = registered(world, monkeypatch, tmp_path); other = "other-abcdef"
  put(s.path("handoffs", other), json.dumps({"id": other, "spec": str(world.spec), "opened_at": "2026-11-03T00:00:00Z", "closed_at": None}))
  tick_launch(s, other, boot="boot-0")
  assert world.run("driver", "tick")[0] == 0 and tick_launches(s, other)[0]["status"] == "interrupted (reboot)" and tick_launches(s, hid)[-1]["status"] == "running"


def test_a_skip_still_sends_a_new_typed_wave_card(world, monkeypatch, tmp_path, spawn_fake):
  s, hid, _ = arranged(world, monkeypatch, tmp_path, "first"); live = world.open_card("wave", str(world.spec))
  assert world.run("driver", "tick")[0] == 0 and not SPAWNED and live in json.loads(driver_file(s, hid).read_text())["notified"]


def test_a_refusal_the_tick_no_longer_makes_is_cleared(world, monkeypatch, tmp_path, spawn_fake):
  s, hid, _ = arranged(world, monkeypatch, tmp_path, "stale-refusal")
  assert world.run("driver", "tick")[0] == 0 and not SPAWNED and json.loads(driver_file(s, hid).read_text())["refused"] is None
  assert f"tick: {hid} refusal cleared (two launches failed before the loop ran)" in s.path("journal").read_text()


def test_one_stores_error_never_stops_the_tick_for_the_next(world, monkeypatch, tmp_path, spawn_fake):
  s, hid = registered(world, monkeypatch, tmp_path); registry = tmp_path / ".superegm/registry.json"; bad = tmp_path / "bad"
  put(bad / "handoffs" / "x.json", "{")
  put(registry, json.dumps([{"repo": REPO, "root": str(tmp_path / "x"), "artifacts_dir": str(bad)}, *json.loads(registry.read_text())]))
  code, out = world.run("driver", "tick")
  assert code == 1 and f"driver: {bad}:" in out and tick_launches(s, hid)[-1]["status"] == "running"


def test_a_phase_card_written_after_the_read_backs_the_tick_off(world, monkeypatch, tmp_path, spawn_fake):
  s, hid, _ = arranged(world, monkeypatch, tmp_path, "first"); real = driver.tick_command
  def racing(*a):
    put(s.root / hid / "runcards" / "plan-abc-0099.json", json.dumps({"id": "plan-abc-0099", "skill": "plan", "artifact": str(world.spec.resolve()), "handoff": hid, "opened_at": superegm.now_iso()})); return real(*a)
  monkeypatch.setattr(driver, "tick_command", racing)
  assert world.run("driver", "tick")[0] == 0 and not SPAWNED and tick_launches(s, hid)[-1]["status"] == "interrupted"
  assert "driver: tick backed off: plan card plan-abc-0099 open" in s.path("journal").read_text()


def test_install_refuses_an_interval_of_zero(world, monkeypatch, tmp_path):
  s, hid = registered(world, monkeypatch, tmp_path); monkeypatch.setattr(driver, "RUN", lambda argv, **k: subprocess.CompletedProcess(argv, 0))
  code, out = world.run("driver", "install", "--interval", 0, "--runcard", world.open_card("driver", world.spec))
  assert code == 1 and "driver: --interval must be at least 1 minute" in out


def test_a_tick_runs_the_spec_of_the_registered_root(world, monkeypatch, tmp_path, spawn_fake):
  s, hid = registered(world, monkeypatch, tmp_path); wt2 = tmp_path / "wt2"
  subprocess.run(["git", "worktree", "add", "-q", str(wt2), "-b", "wt2"], cwd=world.repo, check=True); monkeypatch.chdir(wt2)
  assert world.run("register", "--runcard", world.open_card("driver", world.spec))[0] == 0 and world.run("driver", "tick")[0] == 0
  rel = world.spec.resolve().relative_to(world.repo.resolve())
  assert f"cd '{wt2.resolve()}' && claude -p '/superegm:wave {wt2.resolve() / rel} --handoff {hid}" in SPAWNED[-1][0][2]


def trigger(s):
  state = state_of(s); return status.tick_trigger(superegm.Handoff(Path(state["plan"]), s, state))


def test_tick_trigger_reads_the_builders_status_alone(world, monkeypatch, tmp_path):
  s, hid, _ = arranged(world, monkeypatch, tmp_path, "nothing"); real, login = superegm.status_pass, ["mallory"]
  def stranger(handoff, save=True):
    summary, rest = real(handoff, save=save); summary["units"][UNIT]["builder_status"] = [9, "DONE", login[0]]; return summary, rest
  monkeypatch.setattr(superegm, "status_pass", stranger); assert trigger(s) is None
  card = sorted((s.root / hid / "runcards").glob("wave-*.json"))[0].stem; superegm.card_add(s, card, "builder", {"login": "builder-bot"})
  login[0] = "builder-bot"; assert trigger(s) == f"{UNIT} status word=DONE comment=9 by=builder-bot"


def test_tick_trigger_skips_a_stopped_units_threads(world, monkeypatch, tmp_path):
  s, hid, _ = arranged(world, monkeypatch, tmp_path, "thread"); assert trigger(s) == f"{UNIT} threads 1 un-ingested"
  data = json.loads(s.path("foreman", UNIT).read_text()); data["stopped"] = {"at": superegm.now_iso()}; put(s.path("foreman", UNIT), json.dumps(data))
  assert trigger(s) is None


def test_tick_trigger_counts_a_unit_ready_since_the_fingerprint(world, monkeypatch, tmp_path):
  s, hid, _ = arranged(world, monkeypatch, tmp_path, "nothing"); assert trigger(s) is None
  state = state_of(s); state["status"]["ready"] = []; put(s.path("state"), json.dumps(state))
  assert trigger(s) == f"{UNIT} ready"
