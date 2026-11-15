# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U44's tests: the phase-aware tick behind `driver.chain`.

"""U44 (spec section 7.1): the tick fetches the base into `refs/superegm/tick-base`, asks `superegm next` and launches,
proves, counts and reports the session of the chain phase that comes next; with `driver.chain` absent or false it is
1.2's tick. Every path is under `tmp_path` (`HOME` patched); the fetch is faked; no test reaches launchd or `claude`."""

import json
import re
import subprocess
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import driver, phase
from conftest import ROOT, make_repo, Harness
from test_builders import put, spawn_fake, SPAWNED  # noqa: F401  (spawn_fake: a fixture)
from test_driver import registered
from test_u24 import tick_launches, tick_launch, card_of, driver_file
from test_u43 import Chain, UNITS


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
  assert "phase" not in last  # a chain-off launch entry is 1.2's (change-review-1-3)
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


def git(world, *args):
  return subprocess.run(["git", "-C", str(world.repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def chained(world, monkeypatch, tmp_path, chain=True):
  """U43's `Chain` (an approved three-unit handoff, its root clean on main at `refs/superegm/tick-base`) in a
  registered store whose committed config sets `driver.chain`; HOME under `tmp_path`, the boot id fixed."""
  monkeypatch.setenv("HOME", str(tmp_path / "home"))
  monkeypatch.setattr(superegm, "boot_id", lambda: "boot-1")
  edit_config(world.repo, driver={"chain": chain})
  git(world, "commit", "-qam", "chain")
  c = Chain(world)
  registry = tmp_path / "home" / ".superegm" / "registry.json"
  put(registry, json.dumps([{"repo": superegm.load_config(world.repo)["repo"], "root": str(world.repo),
                             "artifacts_dir": str(world.artifacts)}]))
  return c


def fake_fetch(world, monkeypatch, ok, stderr="", ref="HEAD"):
  """`driver.fetch_base` faked: its calls recorded; a good fetch moves `refs/superegm/tick-base` to `ref` (HEAD: a
  remote at the root's commit)."""
  calls = []

  def fetch(root, remote, base):
    calls.append((Path(root).resolve(), remote, base))
    if ok:
      git(world, "update-ref", "refs/superegm/tick-base", ref)
    return ok, stderr
  monkeypatch.setattr(driver, "fetch_base", fetch, raising=False)
  return calls


def journal_lines(world, needle):
  return [line.split(" ", 1)[1] for path in sorted(world.artifacts.rglob("journal.md"))
          for line in path.read_text(encoding="utf-8").splitlines() if needle in line]


@pytest.mark.parametrize("ok,journal,line", [
  (True, [], "plan"),
  (False, ["driver: fetch origin failed: fatal: unable to access"], "waiting fetch: origin: fatal: unable to access")])
def test_tick_fetch(world, monkeypatch, tmp_path, spawn_fake, ok, journal, line):
  """One fetch of +refs/heads/<base>:refs/superegm/tick-base from config.remote per store per tick, before next;
  its record `tick/fetch.json`; a failed fetch's journal line once per distinct stderr line."""
  c = chained(world, monkeypatch, tmp_path)
  calls = fake_fetch(world, monkeypatch, ok, "" if ok else "fatal: unable to access\nmore detail")
  asked = []
  real = phase.next_line
  monkeypatch.setattr(phase, "next_line", lambda st, hid, read_wait=True: (asked.append(len(calls)), real(st, hid, read_wait))[1])
  for _ in range(2):
    code, out = world.run("driver", "tick")
    assert code == 0, out
  assert calls == [(world.repo.resolve(), "origin", "main")] * 2
  assert asked and all(n >= 1 for n in asked)  # the fetch came before next
  record = json.loads((world.artifacts / "tick" / "fetch.json").read_text(encoding="utf-8"))
  assert set(record) == {"at", "ok", "stderr"} and record["ok"] is ok
  assert record["stderr"] == ("" if ok else "fatal: unable to access")
  assert journal_lines(world, "driver: fetch") == journal
  code, out = world.run("next", "--handoff", c.hid)
  assert (code, out.strip()) == (0, line)


def test_tick_removes_a_superseded_wait_record(world, monkeypatch, tmp_path, spawn_fake):
  """After a good fetch, a superseded handoff's wait record goes with one journal line; a failed fetch keeps it."""
  c = chained(world, monkeypatch, tmp_path)
  c.plan(*UNITS); c.wait(phase="file", question="q"); c.supersede()
  record = world.artifacts / "chain" / f"{c.hid}.json"
  fake_fetch(world, monkeypatch, False, "fatal: x")
  world.run("driver", "tick")
  assert record.exists()
  fake_fetch(world, monkeypatch, True)
  for _ in range(2):
    code, out = world.run("driver", "tick")
    assert code == 0, out
  assert not record.exists()
  assert journal_lines(world, "superseded: wait record") == [f"driver: {c.hid} superseded: wait record removed"]


def set_mode(c, mode):
  """The handoff's approval entry with `mode` frozen as given; None removes it (a 1.2.0 entry)."""
  path = next((c.root / "approvals").glob("*.json"))
  record = json.loads(path.read_text(encoding="utf-8"))
  entry = record["entries"][-1]
  entry.pop("mode", None)
  if mode is not None:
    entry["mode"] = mode
  path.write_text(json.dumps(record), encoding="utf-8")


def arrange_line(world, monkeypatch, c, line):
  """The store for the line `next` should print, its fake fetch good; a `wave` row's trigger fires."""
  ref = "HEAD"
  if line == "review-plan":
    c.plan(*UNITS)
  elif line == "file":
    c.plan(*UNITS); [c.review(u) for u in UNITS]
  elif line == "file (answered wait record)":
    c.plan(*UNITS); [c.review(u) for u in UNITS]
    c.wait(phase="file", question="create 3 issues?", answer="yes", by="owner", at="2026-11-15T01:00:00Z")
  elif line == "wave":
    c.all_filed("U02"); c.save()
  elif line == "none":
    c.void()
  elif line == "waiting push":
    c.other_spec_at_tick_base(); ref = "side"
  elif line == "integrate":
    c.all_filed(); c.save()
  fake_fetch(world, monkeypatch, True, ref=ref)
  monkeypatch.setattr(driver, "wave_trigger", lambda hs, entry, state: "U02 first launch", raising=False)


def launched_prompt(s, hid):
  """The prompt of the handoff's last launch, or None with none."""
  launches = tick_launches(s, hid)
  if not launches:
    return None
  return re.search(r"claude -p '([^']*)' ", launches[-1]["command"]).group(1)


@pytest.mark.parametrize("line,mode,prompt", [
  ("plan", "leavemealone", "/superegm:plan {spec} --handoff H1 --leavemealone"),
  ("review-plan", "normal", "/superegm:review-plan {spec} --handoff H1"),
  ("file", "leavemealone", "/superegm:file {spec} --handoff H1 --leavemealone"),
  ("file (answered wait record)", "leavemealone", "/superegm:file {spec} --handoff H1"),
  ("wave", "normal", "/superegm:wave {spec} --handoff H1"), ("none", "leavemealone", None),
  ("waiting push", "leavemealone", None), ("integrate", "leavemealone", None),
  ("plan", None, None), ("wave", None, "/superegm:wave {spec} --handoff H1 --leavemealone")])
def test_tick_launches_by_phase(world, monkeypatch, tmp_path, spawn_fake, line, mode, prompt):
  """tick_store asks next first; the spec comes from handoffs/<id>.json rebased onto the root; mode None is a 1.2.0
  entry, which runs only its `wave` row, with `--leavemealone`."""
  c = chained(world, monkeypatch, tmp_path)
  set_mode(c, mode)
  arrange_line(world, monkeypatch, c, line)
  code, out = world.run("next", "--handoff", c.hid)
  assert out.strip() == line.split()[0] or (line == "waiting push" and out.strip() == "waiting push"), out
  code, out = world.run("driver", "tick")
  assert code == 0, out
  got = launched_prompt(c.hs, c.hid)
  if prompt is None:
    assert got is None
    return
  spec = got.split()[1]
  assert Path(spec).resolve() == c.spec.resolve()  # the handoff record's spec, there being no state.json before plan
  assert got == prompt.format(spec=spec).replace("H1", c.hid)
  assert tick_launches(c.hs, c.hid)[-1]["phase"] == line.split()[0]
  assert driver.tick_prompt(spec, "H1", line.split()[0], prompt.endswith("--leavemealone")) == prompt.format(spec=spec)


def driven_card(world, monkeypatch, c, skill, dcard="driver-abc-0001", boot="boot-1"):
  """A top-level `skill` card on the handoff's spec opened by a tick's session: `SUPEREGM_ROLE=driver`,
  `SUPEREGM_RUNCARD=dcard`, the boot id `boot`. Returns (code, output)."""
  with monkeypatch.context() as m:
    m.setenv("SUPEREGM_ROLE", "driver"); m.setenv("SUPEREGM_RUNCARD", dcard); m.setattr(superegm, "boot_id", lambda: boot)
    return world.run("runcard", "open", "--skill", skill, "--artifact", str(c.spec), "--handoff", c.hid, card=None)


@pytest.mark.parametrize("phase", ["plan", "review-plan", "file"])
def test_driven_card_of_any_phase(world, monkeypatch, tmp_path, phase):
  """A driven top-level card of any phase gets driver_card and boot_id, passes the second-live-card refusal, and is
  reboot-proved; handoff_spec for a handoff with no state.json reads handoffs/<id>.json spec."""
  c = chained(world, monkeypatch, tmp_path)
  s = superegm.Store(world.artifacts)
  tick_launch(s, c.hid, card="driver-abc-0001", boot="boot-1")  # the tick's launch, live
  code, out = driven_card(world, monkeypatch, c, phase)
  assert code == 0, out  # exempt from the refusal of a second live card
  cid = out.strip()
  card = card_of(c.hs, cid)
  assert card["driver_card"] == "driver-abc-0001" and card["boot_id"] == "boot-1"
  superegm.reboot_proof(c.hs, "boot-2")
  assert card_of(c.hs, cid).get("interrupted_at")  # core.reboot_proof finds that card after the boot id changes
  with monkeypatch.context() as m:  # a typed card of that phase still meets the refusal while the launch is live
    m.delenv("SUPEREGM_ROLE", raising=False)
    tick_launch(s, c.hid, card="driver-abc-0002", boot="boot-1", n=2)
    code, out = world.run("runcard", "open", "--skill", phase, "--artifact", str(c.spec), "--handoff", c.hid, card=None)
    assert code == 1, out
  import argparse
  assert not c.hs.path("state").exists()
  assert superegm.handoff_spec(argparse.Namespace(plan=None), c.hs) == str(c.spec)


def set_entry(s, hid, n, **keys):
  """Launch `n` of the handoff's `driver/<hid>.json` with `keys` set."""
  path = driver_file(s, hid)
  data = json.loads(path.read_text(encoding="utf-8"))
  data["launches"][n - 1].update(keys)
  path.write_text(json.dumps(data), encoding="utf-8")


def tick(world):
  code, out = world.run("driver", "tick")
  assert code == 0, out
  return out


@pytest.mark.parametrize("closed,code,line_changed,wait_record,outcome", [
  (True, 0, True, False, "succeeded"), (True, 0, False, True, "succeeded"), (True, 0, False, False, "failed"),
  (False, 0, True, False, "failed"), (True, 1, True, False, "failed")])
def test_phase_outcome_and_failures(world, monkeypatch, tmp_path, spawn_fake, closed, code, line_changed, wait_record, outcome):
  """A non-wave launch succeeds on card closed, exit 0 and a new next line or a wait record; failures count across
  phases; review.stall_cards and driver status read a review-plan top-level card."""
  c = chained(world, monkeypatch, tmp_path)
  set_mode(c, "leavemealone")
  fake_fetch(world, monkeypatch, True)
  s = superegm.Store(world.artifacts)
  first = tick_launch(s, c.hid, card="driver-abc-0001")
  set_entry(s, c.hid, 1, phase="plan")
  rc, out = driven_card(world, monkeypatch, c, "plan", dcard="driver-abc-0001")
  assert rc == 0, out
  if closed:
    rc, out = world.run("runcard", "close", out.strip(), card=None)
    assert rc == 0, out
  if line_changed:
    c.plan(*UNITS)  # the session planned: next prints review-plan
  if wait_record:
    c.wait(phase="plan", question="which units?", since=superegm.now_iso())  # written by the session
  put(Path(first["exit_file"]), f"{code}\n")
  tick(world)
  assert tick_launches(s, c.hid)[0]["outcome"] == outcome  # the plan launch entry after its session ends
  if closed or code:
    return
  # a failed plan then a failed file refuses as twice-failed; a typed file card after it restarts; driver reset clears
  for entry in tick_launches(s, c.hid):  # the launch that tick started ended too, failing
    if not Path(entry["exit_file"]).is_file():
      put(Path(entry["exit_file"]), "1\n")
  n = len(tick_launches(s, c.hid)) + 1
  second = tick_launch(s, c.hid, card="driver-abc-0009", n=n)
  set_entry(s, c.hid, n, phase="file")
  put(Path(second["exit_file"]), "1\n")
  tick(world)
  data = json.loads(driver_file(s, c.hid).read_text(encoding="utf-8"))
  assert data["launches"][n - 1]["outcome"] == "failed"
  assert (data["refused"] or {}).get("reason") == driver.TWICE
  typed = world.open_card("file", str(c.spec))  # the owner types file: the count restarts
  world.run("runcard", "close", typed, card=None)
  world.advance(60)  # the next launch starts after the typed card
  tick(world)
  assert journal_lines(world, f"tick: {c.hid} refusal cleared") and len(tick_launches(s, c.hid)) == n + 1
  put(Path(tick_launches(s, c.hid)[-1]["exit_file"]), "1\n")
  third = tick_launch(s, c.hid, card="driver-abc-0011", n=n + 2)
  set_entry(s, c.hid, n + 2, phase="review-plan", started_at=superegm.now_iso())  # after the typed card
  put(Path(third["exit_file"]), "1\n")
  tick(world)
  assert driver.twice_failed(c.hs, superegm.load_driver(c.hs), {})
  rc, out = world.run("driver", "reset", "--runcard", world.open_card("driver", str(c.spec)))
  assert rc == 0 and "set aside" in out, out
  assert not driver.twice_failed(c.hs, superegm.load_driver(c.hs), {})
  # review.stall_cards and driver status read a review-plan top-level card
  from superegm import review
  earlier = world.open_card("review-plan", str(c.spec))
  world.run("runcard", "close", earlier, card=None)
  rc, out = driven_card(world, monkeypatch, c, "review-plan", dcard="driver-abc-0012")
  assert rc == 0, out
  mine = out.strip()
  hs = superegm.handoff_store(superegm.Store(world.artifacts, config=superegm.load_config(world.repo)), c.hid)
  assert {earlier, mine} <= review.stall_cards(hs, {"kind": "plan", "artifact": "U01"}, mine)
  rc, out = world.run("driver", "status", card=None)
  assert rc == 0 and f"review-plan card {mine} open" in out, out


@pytest.mark.parametrize("chain,trigger", [(True, "U01 merged pr=7"), (False, None)])
def test_merged_trigger_then_integrate(world, monkeypatch, tmp_path, chain, trigger):
  """Last PR merged, issue open: tick_trigger fires with the chain on; after the wave session saves the snapshot,
  next prints integrate; tick_trigger's reboot and exit-file proofs read a plan top-level card."""
  from types import SimpleNamespace
  from superegm import status
  c = chained(world, monkeypatch, tmp_path, chain=chain)
  c.all_filed(open_unit="U01")
  for n, u in enumerate(UNITS, 1):  # the snapshot's `pr` as `status.unit_view` saves it: the number
    c.state["status"]["units"][u]["pr"] = 10 + n
  c.filed("U01", 1)  # the saved snapshot: no PR yet
  c.save()
  fresh = {u: {**status.EMPTY, "pr": 10 + n, "ci": "success", "landed": True} for n, u in enumerate(UNITS, 1)}
  fresh["U01"] = {**status.EMPTY, "pr": 7}  # the fresh pass: merged (pr set, ci null), the issue left open
  monkeypatch.setattr(superegm, "status_pass", lambda handoff, save=True: ({"units": fresh, "ready": []}, None))
  handoff = SimpleNamespace(store=c.hs, state=json.loads(c.hs.path("state").read_text(encoding="utf-8")),
                            graph=SimpleNamespace(order=list(UNITS)), config=superegm.load_config(world.repo))
  assert status.tick_trigger(handoff) == trigger
  c.filed("U01", 1, pr=7)  # the wave session saved the snapshot
  c.save()
  handoff.state = json.loads(c.hs.path("state").read_text(encoding="utf-8"))
  assert status.tick_trigger(handoff) is None  # the saved snapshot already shows it so
  code, out, _, _ = c.next()
  assert not chain or (code == 0 and out == "integrate"), out
  # tick_trigger's reboot and exit-file proofs read a plan top-level card
  s = superegm.Store(world.artifacts)
  entry = tick_launch(s, c.hid, card="driver-abc-0001", exit=0)
  rc, out = driven_card(world, monkeypatch, c, "plan", dcard="driver-abc-0001")
  assert rc == 0, out
  cid = out.strip()
  driver.exit_file_proof(c.hs, tick_launches(s, c.hid))
  assert card_of(c.hs, cid)["interrupted_at"] and status.tick_trigger(handoff) == f"exit-file {cid}"
  set_entry(s, c.hid, 1, status="interrupted (reboot)")
  assert status.tick_trigger(handoff) == "reboot 1"


@pytest.mark.parametrize("chain", [True, False])
def test_reset_status_and_stall_read_phase_cards_only_with_the_chain(world, monkeypatch, tmp_path, chain):
  """With the chain off, `driver reset`, `driver status` and `review.stall_cards` read 1.2's `wave` cards alone: an
  owner's open typed plan card is neither listed nor interrupted, and a typed review-plan card is no stall card; with
  it on they read the top-level card of every chain phase (change-review-1-1, codebase-details-1-2)."""
  from superegm import review
  c = chained(world, monkeypatch, tmp_path, chain=chain)
  rc, out = world.run("runcard", "open", "--skill", "plan", "--artifact", str(c.spec), "--handoff", c.hid, card=None)
  assert rc == 0, out
  typed = out.strip()
  rc, out = world.run("driver", "status", card=None)
  assert rc == 0 and (f"plan card {typed} open" in out) is chain, out
  rc, out = world.run("driver", "reset", "--runcard", world.open_card("driver", str(c.spec)))
  if chain:
    assert rc == 0 and f"card {typed} interrupted" in out, out
    assert card_of(c.hs, typed)["interrupted_at"]
  else:
    assert rc == 1 and f"driver: {c.hid} has no live tick launch or open wave card" in out, out
    assert not card_of(c.hs, typed)["interrupted_at"]
  earlier = world.open_card("review-plan", str(c.spec))
  world.run("runcard", "close", earlier, card=None)
  rc, out = driven_card(world, monkeypatch, c, "wave", dcard="driver-abc-0007")
  assert rc == 0, out
  mine = out.strip()
  hs = superegm.handoff_store(superegm.Store(world.artifacts, config=superegm.load_config(world.repo)), c.hid)
  assert (earlier in review.stall_cards(hs, {"kind": "plan", "artifact": "U01"}, mine)) is chain


def test_an_outcome_waits_out_a_masking_line(world, monkeypatch, tmp_path, spawn_fake):
  """A plan session that closed its card with exit 0 is not settled while `next` prints `waiting fetch` (a row above
  the phase rows); once the fetch is good and `next` still prints `plan`, it is `failed` (change-review-1-2,
  codebase-details-1-4)."""
  c = chained(world, monkeypatch, tmp_path)
  set_mode(c, "leavemealone")
  s = superegm.Store(world.artifacts)
  first = tick_launch(s, c.hid, card="driver-abc-0001")
  set_entry(s, c.hid, 1, phase="plan")
  rc, out = driven_card(world, monkeypatch, c, "plan", dcard="driver-abc-0001")
  assert rc == 0, out
  assert world.run("runcard", "close", out.strip(), card=None)[0] == 0
  put(Path(first["exit_file"]), "0\n")
  fake_fetch(world, monkeypatch, False, "fatal: unable to access")
  tick(world)
  entry = tick_launches(s, c.hid)[0]
  assert "outcome" not in entry
  assert not driver.counted_failures(c.hs, [entry, {**entry, "round": 2}], {})  # undecided: no failure
  fake_fetch(world, monkeypatch, True)
  tick(world)
  assert tick_launches(s, c.hid)[0]["outcome"] == "failed"


@pytest.mark.parametrize("since,outcome", [("2000-01-01T00:00:00Z", "failed"), (None, "succeeded")])
def test_only_the_sessions_own_wait_record_is_success(world, monkeypatch, tmp_path, spawn_fake, since, outcome):
  """The answered wait record that started a `file` launch is no success of that launch; a record the session wrote
  (its `since` at or after the launch's start) is (codebase-details-1-3)."""
  c = chained(world, monkeypatch, tmp_path)
  set_mode(c, "leavemealone")
  c.plan(*UNITS); [c.review(u) for u in UNITS]
  c.wait(phase="file", question="create 3 issues?", answer="yes", by="owner", at="2026-11-15T01:00:00Z",
         since="2000-01-01T00:00:00Z")
  fake_fetch(world, monkeypatch, True)
  s = superegm.Store(world.artifacts)
  world.advance(60)
  first = tick_launch(s, c.hid, card="driver-abc-0001")
  set_entry(s, c.hid, 1, phase="file")
  rc, out = driven_card(world, monkeypatch, c, "file", dcard="driver-abc-0001")
  assert rc == 0, out
  assert world.run("runcard", "close", out.strip(), card=None)[0] == 0
  if since is None:  # the session asked again: its own record
    c.wait(phase="file", question="create 3 issues?", since=superegm.now_iso())
  put(Path(first["exit_file"]), "0\n")
  code, out = world.run("next", "--handoff", c.hid)
  assert out.strip() == ("file" if since else "waiting file: create 3 issues?"), out
  tick(world)
  assert tick_launches(s, c.hid)[0]["outcome"] == outcome


@pytest.mark.parametrize("value,message", [
  ({"chian": True}, "driver: unknown keys ['chian']"), ({"chain": "true"}, "driver.chain must be true or false"),
  ("on", "driver must be an object")])
def test_the_driver_key_is_validated(world, value, message):
  """`driver` is an object whose one key `chain` is a bool (codebase-details-1-9)."""
  edit_config(world.repo, driver=value)
  with pytest.raises(superegm.HandoffError, match=re.escape(message)):
    superegm.load_config(world.repo)


def test_the_tick_fetch_is_hook_free(monkeypatch, tmp_path):
  """The tick's fetch runs with the hook-free `-c` pairs and writes no FETCH_HEAD (codebase-details-1-5)."""
  seen = []

  def run(argv, **kw):
    seen.append(argv)
    return subprocess.CompletedProcess(argv, 1, "", "fatal: x\n")
  monkeypatch.setattr(driver.subprocess, "run", run)
  assert driver.fetch_base(tmp_path, "origin", "main") == (False, "fatal: x\n")
  argv = seen[0]
  assert argv[0] == "git" and "--no-write-fetch-head" in argv and any(a.startswith("core.hooksPath=") for a in argv)
  assert argv[-1] == "+refs/heads/main:refs/superegm/tick-base"
