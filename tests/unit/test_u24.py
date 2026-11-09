# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U24's tests of the registry, the refusals, the detached start, the stall read and the prose.

"""U24 (spec section 11.2): `register` and the registry, `runcard open`'s refusal while a tick's launch may be
live, `start_detached`, the stall read across a tick's `wave` cards and the driver skill's prose.
`HOME` is `tmp_path` in every test here."""

import json
import os
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import launch_builder
from conftest import REPO
from test_builders import seed, put, git, launched, launches_of, UNIT  # noqa: F401
from test_review import opened, head_round, hstore


def test_a_strangers_builder_status_comment_is_no_builders(world, monkeypatch):
  s, card, hid, _ = seed(world); monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0; launched(s, UNIT, "exited 0"); from superegm import status
  say = lambda cid, login, word: {"id": cid, "body": f"**Builder status:** {word}", "created_at": "2026-11-03T01:00:00Z", "user": {"login": login}}
  assert status.builder_facts(s, UNIT, [say(1, "builder-bot", "DONE"), say(2, "stranger", "BLOCKED")])[1] == [1, "DONE", "builder-bot"]

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def home(monkeypatch, tmp_path):
  monkeypatch.setenv("HOME", str(tmp_path))


def test_register_keeps_one_entry_per_store(world, monkeypatch, tmp_path):
  s, card, hid, _ = seed(world); dcard, root, wt2 = world.open_card("driver", world.spec), str(world.repo.resolve()), tmp_path / "wt2"
  assert world.run("register", "--runcard", dcard)[0] == 0 and superegm.load_registry() == [{"repo": REPO, "root": root, "artifacts_dir": str(s.root)}]
  git(["worktree", "add", "-q", str(wt2), "-b", "wt2"], world.repo); monkeypatch.chdir(wt2); assert world.run("register", "--runcard", dcard)[0] == 0
  assert [e["root"] for e in superegm.load_registry()] == [str(wt2.resolve())] and f"registry: {s.root} root {root} → {wt2.resolve()}" in s.path("journal").read_text()
  assert world.run("register", "--remove", "--runcard", dcard)[0] == 0 and superegm.load_registry() == [] and s.kind_of(s.path("driver", hid)) == "driver" and superegm.boot_id() == superegm.boot_id() != ""
  put(tmp_path / ".superegm/registry.json", '[{"mode": "x"}]'); assert "register: registry: unknown key mode" in world.run("register", "--runcard", dcard)[1]


def driver_file(s, hid):
  return s.root / hid / "driver" / f"{hid}.json"


def tick_launch(s, hid, card="driver-abc-0001", boot="boot-1", exit=None, n=1, refused=None):
  """A tick's launch `n` of handoff `hid` in `driver/<hid>.json` as `driver tick` records it: `pid` 4242, its exit
  file when `exit` is given, `notified` seeded with `launch:<hid>:<n>`, `refused` when given. Returns the entry."""
  path, base = driver_file(s, hid), s.root / hid / "driver"
  data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"launches": [], "notified": [], "refused": None}
  entry = {"round": n, "card": card, "started_at": superegm.now_iso(), "boot_id": boot, "status": "running", "pid": 4242,
           "reason": "first launch", "command": "true", "result_file": str(base / f"{hid}_r{n}_result.json"),
           "exit_file": str(base / f"{hid}_r{n}.exit"), "log": str(base / f"{hid}_r{n}.log")}
  if exit is not None:
    put(Path(entry["exit_file"]), f"{exit}\n")
  data["launches"].append(entry)
  data["notified"] = sorted(set(data.get("notified") or []) | {f"launch:{hid}:{n}"})
  if refused is not None:
    data["refused"] = refused
  put(path, json.dumps(data))
  return entry


def wave_of(world, monkeypatch, dcard, boot):
  """A `wave` card opened on the state's `design.path` by a tick's session: `SUPEREGM_ROLE=driver`,
  `SUPEREGM_RUNCARD=dcard`, the boot id `boot`."""
  states = [p for p in (world.artifacts / "state.json", *sorted(world.artifacts.glob("*/state.json"))) if p.is_file()]  # a legacy store's is flat
  state = next(p for p in states if "design" in json.loads(p.read_text(encoding="utf-8")))
  design = json.loads(state.read_text(encoding="utf-8"))["design"]["path"]
  with monkeypatch.context() as m:
    m.setenv("SUPEREGM_ROLE", "driver"); m.setenv("SUPEREGM_RUNCARD", dcard); m.setattr(superegm, "boot_id", lambda: boot)
    return world.open_card("wave", design)


def card_of(s, cid):
  return json.loads(s.path("runcards", cid).read_text(encoding="utf-8"))


def newest_card(s, hid, skill):
  cards = sorted((s.root / hid / "runcards").glob(f"{skill}-*.json"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
  return json.loads(cards[-1].read_text(encoding="utf-8"))


def tick_launches(s, hid):
  path = driver_file(s, hid)
  return json.loads(path.read_text(encoding="utf-8"))["launches"] if path.is_file() else []


OTHER = "other-abcdef"


def arranged(world, monkeypatch, where, boot, role):
  """`seed` at boot id `boot-1`, an open `handoffs/other-abcdef.json`, the tick's launch in `hid` (`this`) or the other
  (`other`) at `boot`, `hid`'s `wave_of` card and a `running` U07 launch at `boot` unless `where` is `none`, and the
  role's env with `SUPEREGM_RUNCARD=driver-abc-0002`. Returns `(s, hid, the wave_of card or None)`."""
  monkeypatch.setattr(superegm, "boot_id", lambda: "boot-1")
  s, card, hid, _ = seed(world)
  put(s.path("handoffs", OTHER), json.dumps({"id": OTHER, "spec": str(world.spec), "opened_at": "2026-11-03T00:00:00Z", "closed_at": None}))
  live = None
  if where != "none":
    tick_launch(s, hid if where == "this" else OTHER, boot=boot)
    live = wave_of(world, monkeypatch, "driver-abc-0001", boot)
    put(s.path("launches", UNIT), json.dumps({"launches": [{"round": 1, "started_at": "2026-11-03T00:00:00Z", "status": "running", "boot_id": boot, "pid": 4242,
        "result_file": str(s.path("launches", f"{UNIT}_r1_result.json")), "worktree": "w", "branch": "b"}]}))
  if role:
    monkeypatch.setenv("SUPEREGM_ROLE", role); monkeypatch.setenv("SUPEREGM_RUNCARD", "driver-abc-0002")
  else:
    monkeypatch.delenv("SUPEREGM_ROLE", raising=False); monkeypatch.delenv("SUPEREGM_RUNCARD", raising=False)
  return s, hid, live


LIVE = "driver: a tick's session may be live; /superegm:driver reset is the owner's interrupt"
@pytest.mark.parametrize("skill, role, where, boot, expect", [*[(k, None, "this", "boot-1", "refused") for k in ("wave", "plan", "file", "integrate", "review-plan", "orient")],
  ("wave", None, "other", "boot-1", "refused"), ("plan", None, "other", "boot-1", "open"), ("wave", "driver", "this", "boot-1", "open"), ("wave", None, "this", "boot-0", "reboot"),
  ("wave", None, "none", "boot-1", "open")])
def test_runcard_open_refuses_while_a_tick_launch_may_be_live(world, monkeypatch, skill, role, where, boot, expect):
  s, hid, live = arranged(world, monkeypatch, where, boot, role); code, out = world.run("runcard", "open", "--skill", skill, "--artifact", str(world.spec)); mine = newest_card(s, hid, skill)
  if expect == "refused": assert code == 1 and LIVE in out and mine["interrupted_at"] and (where == "other" or not card_of(s, live)["interrupted_at"]); return
  assert code == 0 and mine.get("driver_card") == ("driver-abc-0002" if role else None) and mine.get("boot_id") == ("boot-1" if skill == "wave" else None)
  if expect == "reboot": assert tick_launches(s, hid)[0]["status"] == launches_of(s)[0]["status"] == "interrupted (reboot)" and card_of(s, live)["interrupted_at"]


def test_start_detached_runs_the_wrapper_in_its_own_session(tmp_path):
  pid = launch_builder.start_detached(["/bin/sh", "-c", "echo started"], tmp_path / "log", {}); assert os.getpgid(pid) == pid and os.waitpid(pid, 0)[0] == pid and (tmp_path / "log").read_text() == "started\n"


def posted(world, n, cid, outcome):
  """`head_round`'s `posted` round `n`, its `posted_at` rewritten `now_iso()` (the fixture writes `None`)."""
  head_round(world, n, "posted", cid, outcome)
  path = hstore(world).path("foreman", "U07"); data = json.loads(path.read_text(encoding="utf-8"))
  data["rounds"][-1]["posted_at"] = superegm.now_iso(); superegm.atomic_write(path, data)


def test_review_status_reads_the_stall_across_a_ticks_wave_cards(world, monkeypatch):
  monkeypatch.setattr(superegm, "boot_id", lambda: "boot-1"); spec, a, rid = opened(world, "head", reviewers="change-review", astra=None)
  head_round(world, 1, "collected", a, "not run (error)"); head_round(world, 2, "collected", a, "not run (error)")
  status = lambda cid: world.run("review", "status", "--review", rid, "--runcard", cid)[0]
  assert status(a) == 5 and status(world.run("runcard", "open", "--skill", "wave", "--artifact", str(spec))[1].strip()) == 3
  world.advance(60); c = wave_of(world, monkeypatch, "driver-abc-0001", "boot-1"); assert status(c) == 5
  world.advance(60); posted(world, 3, c, "revise"); world.advance(60); assert status(wave_of(world, monkeypatch, "driver-abc-0002", "boot-1")) == 3


def test_review_status_reads_the_stall_under_the_cards_own_rounds_after_its_post(world, monkeypatch):
  monkeypatch.setattr(superegm, "boot_id", lambda: "boot-1"); spec, a, rid = opened(world, "head", reviewers="change-review", astra=None)
  world.advance(60); c = wave_of(world, monkeypatch, "driver-abc-0001", "boot-1"); world.advance(60); posted(world, 1, c, "revise"); world.advance(60)
  head_round(world, 2, "collected", c, "not run (error)"); head_round(world, 3, "collected", c, "not run (error)")
  assert world.run("review", "status", "--review", rid, "--runcard", c)[0] == 5
  world.advance(60); b = wave_of(world, monkeypatch, "driver-abc-0002", "boot-1")  # astra-2-5: a later session reads them too
  assert world.run("review", "status", "--review", rid, "--runcard", b)[0] == 5


@pytest.mark.parametrize("path, needle", [("skills/wave/SKILL.md", "If a decision was opened this batch outside SUPEREGM_ROLE=driver, pause"),
                                          ("skills/wave/references/leavemealone_mode.md", "the batch ends as its step 7 says (under SUPEREGM_ROLE=driver it goes on"),
                                          ("skills/wave/references/leavemealone_mode.md", "ask the owner (under SUPEREGM_ROLE=driver an inbox line, never a question)"),
                                          ("skills/driver/SKILL.md", "sets the two failures aside (`set_aside`, the second one's round)"),
                                          ("skills/plan/scripts/superegm/__init__.py", "`launches[]`, `notified`, `refused`, `set_aside`")])
def test_no_wave_passage_asks_under_the_driver_role(path, needle):
  text = " ".join((ROOT / path).read_text().split()); assert needle in text, (path, needle)


def test_a_failed_boot_id_lookup_is_no_reboot():
  assert superegm.rebooted({"boot_id": "boot-1"}, "unknown") is False and superegm.rebooted({"boot_id": "boot-0"}, "boot-1") is True


def test_a_line_either_notified_set_holds_is_not_new(world, tmp_path):
  s, card, hid, _ = seed(world); tick_launch(s, hid); hook, sent = tmp_path / ".superegm/notify", tmp_path / "sent.txt"
  put(hook, f"#!/bin/sh\ncat >> '{sent}'\n"); hook.chmod(0o755)
  assert world.run("notify", "--runcard", card)[0] == 0 and f"tick launch 1" not in (sent.read_text() if sent.is_file() else "")


PROSE = [("skills/driver/SKILL.md", n, True) for n in ("/superegm:driver install", "--interval", "register", "reset", "~/.superegm/env", "0600", "loginctl enable-linger",
                                                        "runcard open --skill driver --artifact", "after every plugin update", "pmset")] + \
        [("skills/wave/SKILL.md", n, True) for n in ("SUPEREGM_ROLE=driver", "never ask", "pending a decision", "`launch-builder` starts the builder and records the launch")] + \
        [("skills/wave/SKILL.md", "record-launch --unit <U> --runcard '<CARD>'", False), ("skills/wave/SKILL.md", "`launch-builder` and `record-launch`", False), ("skills/using-superegm/SKILL.md", "`/superegm:driver`", True)]
@pytest.mark.parametrize("path, needle, present", PROSE)
def test_the_driver_skill_and_the_prose(path, needle, present):
  assert (needle in (ROOT / path).read_text()) is present, (path, needle)
