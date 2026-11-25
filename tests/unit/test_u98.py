# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U98's `status --wait` writes no stale copy (1.3 design section 3.1)

"""U98 (1.3 design section 3.1): `status --wait` makes its GitHub reads first and, when the pass that ends the wait is
done, loads `state.json` again and copies onto that fresh copy only what its passes set, so a write another process made
during the wait survives the wait's save."""

import functools
import json
from pathlib import Path

import pytest

from conftest import REPO, make_plan, make_pr
from superegm import status as status_module
from test_events import WAIT, seed, pr
from test_u61 import unit_section


def edit_state(st, change):
  """`change(state)` applied to `state.json` as another process leaves it."""
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  change(state)
  st.path("state").write_text(json.dumps(state), encoding="utf-8")


def put_at(state, path, value):
  holder = state
  for key in path[:-1]:
    holder = holder.setdefault(key, {})
  holder[path[-1]] = value


def sleeping_writer(world, monkeypatch, writes):
  """`SLEEP` as the wait sleeps in: `writes()` (another process's work) once, on the first sleep, before the clock moves."""
  real, done = world.ns["SLEEP"], []

  def sleep(seconds):
    if not done:
      done.append(1)
      writes()
    real(seconds)
  monkeypatch.setitem(world.ns, "SLEEP", sleep)


@pytest.mark.parametrize("path, value", [
    (("units", "U01", "launched"), {"at": "2026-11-25T10:00:00Z", "runcard": "wave-card"}),
    (("units", "U01", "launched"), None),  # a mark the wait's loaded copy held, cleared during the wait
    (("decisions", "U01/D1"), {"answer": "(b)", "by": "owner", "decided_at": "2026-11-25T10:00:00Z"}),
])
def test_wait_keeps_what_another_process_wrote(world, monkeypatch, path, value):
  gh, st, card = seed(world, monkeypatch)
  if value is None:
    edit_state(st, lambda state: put_at(state, path, {"at": "2026-11-24T10:00:00Z", "runcard": "wave-card"}))

  def another_process():
    edit_state(st, lambda state: put_at(state, path, value))
    pr(gh, number=52, issue=3)  # U02's pull request, discovered by the pass that ends the wait
  sleeping_writer(world, monkeypatch, another_process)
  code, out = world.run(*WAIT, card)
  assert code == 0, out
  assert "U02 head pr=52" in out, out
  saved = json.loads(st.path("state").read_text(encoding="utf-8"))
  assert functools.reduce(dict.get, path, saved) == value
  assert saved["units"]["U02"]["pr"]["number"] == 52
  assert saved["status"]["units"]["U02"]["pr"] == 52
  status_source = Path(status_module.__file__).read_text(encoding="utf-8")
  assert "no other command can be overwritten by a sleeping watcher" not in status_source


SHA52, SHA53, SHA51 = "5" * 40, "6" * 40, "7" * 40
OLD, VOID_OLD = "2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"


@pytest.mark.parametrize("card", ["integrate", "wave"])
def test_wait_copies_only_what_its_passes_set(world, monkeypatch, card):
  # Six filed units, U01 #2 .. U06 #7, and a tracking issue #1 the wave card's board is written into.
  scope = lambda uid: f"`src/{uid.lower()}.py` (create), `tests/test_{uid.lower()}.py` (create)"
  make_plan(world.plan.parent, world.repo, "".join(unit_section(f"U0{n}", scope=scope(f"U0{n}")) for n in range(1, 7)))
  gh, st, wave = seed(world, monkeypatch, units={"U04": 5, "U05": 6, "U06": 7})
  gh.issues[1] = {"number": 1, "id": 1001, "title": "tracking", "body": "# Build\n", "labels": [], "state": "open", "state_reason": None}
  edit_state(st, lambda state: state.update(tracking={"number": 1}))
  world.cards["wave"] = wave
  pr(gh, number=52, sha=SHA52, issue=7)  # U06's pull request, read by a pass of the wait
  make_pr(gh, 53, SHA53, closes=[(REPO, 7)])  # the pull request `status --watch U06=53` records during the wait
  assert world.run("status", "--wait", 1, "--runcard", wave)[0] == 0  # saves the fingerprints the wait reports against: no event on its first pass
  world.advance(60)
  wait_card = wave if card == "wave" else world.open_card("integrate", str(world.spec))

  def confirmations(state):
    state["units"]["U03"].update(landed_confirmed=OLD, landed_confirmation_void=VOID_OLD)  # a void the loaded copy held
    state["units"]["U04"]["landed_confirmed"] = OLD  # voided by the wait's first pass: its issue is open
    state["units"]["U05"]["landed_confirmed"] = OLD  # voided by the wait's first pass, then given again during the wait
  edit_state(st, confirmations)

  during = {}  # what the other process saved during the wait

  def another_process():
    for number in (4, 5, 6):  # U03, U04 and U05's issues are closed as completed
      gh.issues[number].update(state="closed", state_reason="completed")
    assert world.run("status", "--confirm-landed", "U03", "--confirm-landed", "U05", "--runcard", wave)[0] == 0
    assert world.run("status", "--watch", "U06=53", "--runcard", wave)[0] == 0
    left = json.loads(st.path("state").read_text(encoding="utf-8"))  # as the other process leaves it
    during.update(board=left["board_changed_at"], U03=left["units"]["U03"]["landed_confirmed"], U05=left["units"]["U05"]["landed_confirmed"])
    pr(gh, number=51, sha=SHA51, issue=3)  # U02's pull request, which the wait's second pass discovers
  sleeping_writer(world, monkeypatch, another_process)
  code, out = world.run(*WAIT, wait_card)
  assert code == 0, out
  assert "U02 head pr=51" in out, out
  saved = json.loads(st.path("state").read_text(encoding="utf-8"))
  assert during["U03"] != OLD != during["U05"] and during["board"] != world.ns["now_iso"]()
  assert "landed_confirmation_void" not in saved["units"]["U03"]
  assert saved["units"]["U03"]["landed_confirmed"] == during["U03"]
  assert saved["units"]["U04"]["landed_confirmation_void"]
  assert "landed_confirmation_void" not in saved["units"]["U05"]
  assert saved["units"]["U05"]["landed_confirmed"] == during["U05"]
  assert saved["units"]["U06"]["watch"]["number"] == saved["units"]["U06"]["pr"]["number"] == 53
  assert saved["board_changed_at"] == (during["board"] if card == "integrate" else world.ns["now_iso"]())
