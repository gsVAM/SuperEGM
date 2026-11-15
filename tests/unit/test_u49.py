# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U49

"""U49 (spec section 8): an interrupted launch keeps its subagent calls, read through one helper."""

import json, re, uuid
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import ROOT

SCRIPTS = ROOT / "skills/plan/scripts/superegm"


def jsonl(path, items):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")


def agent(tid):
  return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "Agent", "input": {"prompt": "p"}}]}}


def two_calls(profile, sid):
  """A transcript for `sid` under `profile` holding two `Agent` calls."""
  jsonl(Path(profile) / "projects/-wt" / f"{sid}.jsonl", [agent("a1"), agent("a2")])


def test_launch_subagent_calls_reads_the_entry_session(tmp_path, monkeypatch):
  from superegm import traces
  monkeypatch.setenv("HOME", str(tmp_path))
  two_calls(tmp_path / "prof", "s1")
  assert traces.launch_subagent_calls("~/prof", {"session_id": "s1"}) == traces.subagent_calls(Path.home() / "prof", "s1")
  assert traces.launch_subagent_calls("~/prof", {"session_id": "s1"})["count"] == 2
  assert traces.launch_subagent_calls("~/prof", {}) == {"count": 0, "calls": []}


def test_one_reader_of_subagent_calls():
  # every reader counts through the helper, so U63 changes one place
  users = {p.name for p in SCRIPTS.glob("*.py") if re.search(r"\bsubagent_calls\(", p.read_text(encoding="utf-8")) and p.name != "traces.py"}
  assert users == set()
  assert all("launch_subagent_calls(" in (SCRIPTS / n).read_text(encoding="utf-8") for n in ("record_launch.py", "interrupt.py", "__init__.py"))


@pytest.mark.parametrize("ender, status", [("interrupt", "interrupted"), ("reboot", "interrupted (reboot)")])
def test_interrupted_launch_records_subagent_calls(world, ender, status):
  from superegm import traces
  from test_builders import seed, launched, launches_of, UNIT
  s, card, hid, _ = seed(world)
  launched(s, UNIT, "running")
  profile = Path(json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]["profile_dir"])
  sid = str(uuid.uuid4())
  path = s.path("launches", f"{UNIT}.json")
  data = json.loads(path.read_text(encoding="utf-8"))
  data["launches"][0].update({"session_id": sid, "boot_id": "boot-old"})
  path.write_text(json.dumps(data), encoding="utf-8")
  two_calls(profile, sid)
  if ender == "interrupt":
    code, out = world.run("runcard", "open", "--skill", "interrupt", "--artifact", UNIT)
    assert code == 0, out
    code, out = world.run("interrupt", "--unit", UNIT, "--launch", 1, "--runcard", out.split()[-1])
    assert code == 0, out
  else:
    superegm.reboot_launches(superegm.store(world.repo), UNIT, "boot-new")  # seed's `s` read the config before seed rewrote it
  entry = launches_of(s)[0]
  assert entry["status"] == status
  assert entry["subagent_calls"] == traces.launch_subagent_calls(profile, entry) and entry["subagent_calls"]["count"] == 2
