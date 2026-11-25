# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U98's `status --wait` writes no stale copy (1.3 design section 3.1)

"""U98 (1.3 design section 3.1): `status --wait` makes its GitHub reads first and, when the pass that ends the wait is
done, loads `state.json` again and copies onto that fresh copy only what its passes set, so a write another process made
during the wait survives the wait's save."""

import functools
import json
from pathlib import Path

import pytest

from superegm import status as status_module
from test_events import WAIT, seed, pr


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
