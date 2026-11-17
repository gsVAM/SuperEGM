# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U61's tests: shared-file units ready together under an approval entry with `rounds`, the merge order on the board and in the inbox, the cycle check over both edge sets and the issue body's `merges after`/`merges before`.

"""U61: parallel readiness and the merge order (spec 1.2.1 section 6.1)."""

import json
import re
from types import SimpleNamespace

import pytest

import superegm
from superegm import atomic_write, status as events
from conftest import REPO, handoff_store, make_plan
from test_wave import A, CLEAN, open_wave_card, wave_store

PR_URL = f"https://github.com/{REPO}/pull/"


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
    ({"kind": "amend-units"}, {"U02"}, set()),  # an `--amend-units` entry over a 1.2.0 entry: no `rounds` copied
    ({"kind": "amend-units", "rounds": 3}, set(), {"U02"}),  # over a 1.2.1 entry: `rounds` copied, parallel
    (None, {"U02"}, set()),
])
def test_shared_file_units_are_ready_together(approval, preds_u01, merge_u01, tmp_path, monkeypatch):
  # U01 shares a file after U02, no Blocked by; only a `rounds` key in the entry splits the orders
  g = superegm.Graph(shared_plan(tmp_path), approval)
  assert g.preds == {"U01": preds_u01, "U02": set()}
  assert g.merge_after == {"U01": merge_u01, "U02": set()}
  assert g.order == ["U02", "U01"]
  assert sorted(ready_of(g, tmp_path, monkeypatch)) == (["U01", "U02"] if merge_u01 else ["U02"])


def merge_world(world, rounds=True):
  """The world with U01 sharing `src/shared.py` after U02, no blocker, the approval record carrying `rounds` only when `rounds` is true."""
  units = (unit_section("U01", "none", "`src/shared.py`: after U02")
           + unit_section("U02", "none", "`src/shared.py`: before U01"))
  make_plan(world.plan.parent, world.repo, units)
  path = world.artifacts / "approvals" / "sample.json"
  record = json.loads(path.read_text(encoding="utf-8"))
  if rounds:
    (record["entries"][-1] if "entries" in record else record)["rounds"] = 3
  atomic_write(path, record)


def clean_store(world):
  """Both heads clean (a posted clean round after an exited launch), U02 unlanded."""
  return wave_store(world, U01={"pr": 70, "head": A, "ci": "green", **CLEAN},
                    U02={"pr": 71, "head": A, "ci": "green", **CLEAN})


def land_u02(s, landed=True):
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"]["U02"].update(landed=landed, ci=None if landed else "green")
  atomic_write(s.path("state"), state)


def board_row(world, card, uid):
  out = world.run("report", "--runcard", card)[1]
  return next(line for line in out.splitlines() if line.startswith(f"| {uid} #"))


def inbox_merges(s, units_file=True):
  from superegm.inbox import inbox_items
  if not units_file:
    s.path("units").unlink()
  return [i for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "merge"]


def test_clean_head_awaits_merge_after(world):
  # §6.1: U01 merges after U02; both heads clean, U02 unlanded; the owner still merges
  merge_world(world)
  card = open_wave_card(world)
  s = clean_store(world)
  units = json.loads(s.path("units").read_text(encoding="utf-8"))
  assert units["order"] == ["U02", "U01"]
  assert {u: units["units"][u]["merge_after"] for u in ("U01", "U02")} == {"U01": ["U02"], "U02": []}
  assert "| await-merge after U02 |" in board_row(world, card, "U01")
  assert "await-merge after" not in board_row(world, card, "U02")
  merges = inbox_merges(s)
  assert [i["subject"] for i in merges] == ["U02", "U01"]  # in merge order, not by id
  assert merges[1]["action"] == f"await-merge after U02 · {PR_URL}70"
  assert merges[0]["action"] == f"{PR_URL}71"
  land_u02(s)
  assert "await-merge after" not in board_row(world, card, "U01")
  assert [i["action"] for i in inbox_merges(s)] == [f"{PR_URL}70"]
  land_u02(s, landed=False)
  bare = inbox_merges(s, units_file=False)  # no handoff_units.json: no merge order, by id
  assert [(i["subject"], i["action"]) for i in bare] == [("U01", f"{PR_URL}70"), ("U02", f"{PR_URL}71")]


def test_a_merge_item_is_new_again_once_its_merge_order_lands(world):
  # §6.1: notify dedupes on the fingerprint; U01's line changes when U02 lands, so its fingerprint must too
  merge_world(world)
  open_wave_card(world)
  s = clean_store(world)
  prints = lambda: {i["subject"]: i["fingerprint"] for i in inbox_merges(s)}
  held = prints()
  assert prints() == held  # unchanged while nothing lands
  land_u02(s)
  after = prints()
  assert after["U01"] != held["U01"]


def test_a_1_2_0_entry_writes_no_merge_order(world):
  # §6.1: without `rounds` the file holds `merge_after: []` for every unit and the board keeps its text
  merge_world(world, rounds=False)
  card = open_wave_card(world)
  s = clean_store(world)
  units = json.loads(s.path("units").read_text(encoding="utf-8"))["units"]
  assert {u: units[u]["merge_after"] for u in units} == {"U01": [], "U02": []}
  assert "await-merge after" not in board_row(world, card, "U01")


def test_cycle_through_a_shared_order_is_refused(tmp_path):
  # §6.1: U02 is blocked by U01 while U01 merges after U02; the cycle check runs over blockers and merge orders together
  plan = shared_plan(tmp_path, u02_blocked="U01")
  with pytest.raises(superegm.HandoffError, match="shared-file chain contradicts the blockers"):
    superegm.Graph(plan, {"rounds": 3})


@pytest.mark.parametrize("rounds, after, before", [
    (True, "`src/shared.py`: merges after ", "`src/shared.py`: merges before "),
    (False, "`src/shared.py`: after ", "`src/shared.py`: before "),
])
def test_issue_body_says_merges_after(world, rounds, after, before):
  # §6.1: with `rounds` the body's shared-file line names a merge order, not a code dependency
  merge_world(world, rounds=rounds)
  assert world.run("graph", "--plan", world.plan)[0] == 0
  text = handoff_store(world).path("bodies").read_text(encoding="utf-8")
  body_of = lambda uid: next(p for p in re.split(r"\n## (?=U\d+\n)", text) if p.startswith(uid))
  assert after in body_of("U01") and before in body_of("U02")
  if rounds:  # the plain words are gone, not alongside
    assert "`src/shared.py`: after " not in body_of("U01") and "`src/shared.py`: before " not in body_of("U02")
