# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U48's tests: one close_card, the driver's STORE switch, sigkill_hook.

"""U48: the driver and `runcard close` share one `runcard.close_card`; `inbox.kill_group` is `sigkill_hook`."""

import json
import shlex

import pytest

from conftest import SCRIPTS, handoff_store


@pytest.mark.parametrize("call, closed_before, exit_code, last_journal", [
  ("runcard close <id> --note n", False, 0, "runcard close <id> note n"),
  ("runcard close <id> --note ''", False, 0, "runcard close <id>"),
  ("runcard close <id>", True, 1, "<unchanged>"),
  ("runcard.close_card(st, <id>, 'n')", False, None, "runcard close <id> note n"),
  ("runcard.close_card(st, <id>)", True, None, "<unchanged>"),
])
def test_one_close_card(world, call, closed_before, exit_code, last_journal):
  # one close for the subcommand and the driver; only the subcommand refuses a closed card ("runcard: <id> is closed")
  from superegm import runcard
  st = handoff_store(world)
  cid = world.open_card("plan", world.spec)
  if closed_before:
    runcard.close_card(st, cid)
  card_path, journal = st.path("runcards", cid), st.path("journal")
  card_before = card_path.read_text(encoding="utf-8")
  journal_before = journal.read_text(encoding="utf-8")
  if call.startswith("runcard close"):
    argv = shlex.split(call.replace("<id>", cid))
    code, out = world.run(*argv, card=None)
    assert code == exit_code
    if exit_code == 1:
      assert f"runcard: {cid} is closed" in out
  else:
    note = "n" if "'n'" in call else None
    assert runcard.close_card(st, cid, note) is None
  if last_journal == "<unchanged>":
    assert card_path.read_text(encoding="utf-8") == card_before
    assert journal.read_text(encoding="utf-8") == journal_before
  else:
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert lines[-1].split(" ", 1)[1] == last_journal.replace("<id>", cid)
    assert json.loads(card_path.read_text(encoding="utf-8"))["closed_at"]


def test_driver_closes_through_runcard():
  # the driver's closes use the shared close, and its STORE switch says why it is a global
  src = (SCRIPTS / "superegm" / "driver.py").read_text()
  assert "def close_card" not in src and "runcard.close_card(" in src
  assert all("STORE" in line.split("#", 1)[1] for line in src.splitlines() if "core.STORE = hs" in line)
