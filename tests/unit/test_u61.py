# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U61's tests: shared-file units ready together under an approval entry with `rounds`, the merge order on the board and in the inbox, the cycle check over both edge sets and the issue body's `merges after`/`merges before`.

"""U61: parallel readiness and the merge order (spec 1.2.1 section 6.1)."""

from types import SimpleNamespace

import pytest

import superegm
from superegm import status as events
from conftest import make_plan


def unit_section(uid, blocked="none", shared="none", scope=None):
  n = uid.lower()
  scope = scope or f"`src/{n}.py` (create), `tests/test_{n}.py` (create), `src/shared.py` (modify)"
  return f"""### {uid}: Unit {uid}
| Field | Value |
| --- | --- |
| Objective | {uid} exists. |
| Scope paths | {scope} |
| Design range | `docs/designs/sample.md:13-15 (#### 1. src/webhooks/queue.ts)` |
| Blocked by | {blocked} |
| Shared files | {shared} |
| Risk | low: new module |
| Size | S |

Interfaces
- Produces: {n}_fn(x: int) -> int

Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `pytest tests/test_{n}.py -q` — the module's cases pass
3. CI green on the head

Review focus (this unit)
- {uid}: an empty input — returns 0; pinned by `test_{n}_empty`

Steps
1. Write the failing test `test_{n}_empty` in `tests/test_{n}.py`:
   ```python
   def test_{n}_empty(): assert {n}_fn(0) == 0
   ```
   Implement `{n}_fn(x: int) -> int` in `src/{n}.py`.

Decide before build
- none

"""


def shared_plan(tmp_path, u01_blocked="none", u02_blocked="none"):
  """U01 shares `src/shared.py` after U02 (U02 before U01), each with the blockers named."""
  units = (unit_section("U01", u01_blocked, "`src/shared.py`: after U02")
           + unit_section("U02", u02_blocked, "`src/shared.py`: before U01"))
  return superegm.parse_plan(make_plan(tmp_path, tmp_path, units))


def ready_of(graph, tmp_path, monkeypatch):
  """`status_pass`'s ready list over `graph`, no unit landed or launched and no decision open."""
  blank = lambda handoff, uid: {"unit": uid, "number": None, "issue_state": None, "state_reason": None,
                                "launched": None, **events.EMPTY, "status": "waiting-for-pr", "candidates": []}
  monkeypatch.setattr(events, "unit_view", blank)
  handoff = SimpleNamespace(graph=graph, plan=graph.plan, state={"units": {}}, artifact_dir=tmp_path)
  return superegm.status_pass(handoff, save=False)[0]["ready"]


@pytest.mark.parametrize("approval, preds_u01, merge_u01", [
    ({"rounds": 3}, set(), {"U02"}),
    ({}, {"U02"}, set()),
    ({"amended": True}, {"U02"}, set()),
    (None, {"U02"}, set()),
])
def test_shared_file_units_are_ready_together(approval, preds_u01, merge_u01, tmp_path, monkeypatch):
  # U01 shares a file after U02, no Blocked by; only a raw `rounds` key splits the orders
  g = superegm.Graph(shared_plan(tmp_path), approval)
  assert g.preds == {"U01": preds_u01, "U02": set()}
  assert g.merge_after == {"U01": merge_u01, "U02": set()}
  assert g.order == ["U02", "U01"]
  assert sorted(ready_of(g, tmp_path, monkeypatch)) == (["U01", "U02"] if merge_u01 else ["U02"])
