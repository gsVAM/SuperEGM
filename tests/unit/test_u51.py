# Added by SuperEGM (gsVAM), 2026: U51's tests: `close` lists the triage follow-ups; `integrate` gives them as known.

"""U51: follow-ups after the heads (spec section 5.2)."""

import json

import pytest

from conftest import ROOT
from superegm import store
from test_leavemealone_finish import seed, put


def closed_note(world, followups):
  """Run `close` once over a seeded store whose foreman records hold `followups` (unit -> rows; `{}`: no key):
  the lines of the note after the `closed` line and the journal's `close: follow-up` lines."""
  seed(world)
  state = json.loads(store(world.repo).path("state").read_text(encoding="utf-8"))
  state["units"] |= {u: {"number": 100 + i} for i, u in enumerate(("U01", "U02", "U03"))}
  put(world, state, "state")
  for unit, rows in followups.items():
    put(world, {"dispatch_id": None, "rounds": [], "decisions": [], "rulings": [], "followups": rows}, "foreman", unit)
  code, out = world.run("close", "--runcard", world.card("integrate"))
  assert code == 0, out
  journal = (world.artifacts / "journal.md").read_text(encoding="utf-8").splitlines()
  return out.splitlines()[1:], [line for line in journal if line.startswith("close: follow-up ")]


@pytest.mark.parametrize("followups, lines", [
    ({"U03": [{"fid": "F1", "round": 1, "claim": "b", "pattern": 2}], "U02": [],
      "U01": [{"fid": "F3", "round": 2, "claim": "a", "pattern": 1}, {"fid": "F3", "round": 3, "claim": "a", "pattern": 1}]},
     ["- U01 F3 (round 2, pattern 1): a", "- U01 F3 (round 3, pattern 1): a", "- U03 F1 (round 1, pattern 2): b"]),
    ({}, []),
])
def test_close_lists_the_follow_ups_in_its_closing_note(world, followups, lines):
  # every unit's foreman followups[] in the closing note and one journal line each; none: no block
  assert closed_note(world, followups) == ((["Follow-ups:", *lines] if lines else []), [f"close: follow-up {line[2:]}" for line in lines])

