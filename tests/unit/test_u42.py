# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U42's pins of spec section 6 (the units limits: registered, validated, refused over, the bytes warning gone).

"""U42: `scan` registers and validates the `units` limits, refuses an unfiled unit over one of them,
drops the 24,576-byte warning, and the plan documents state the limits."""

import json

import pytest
import superegm as core
from superegm import scan

from conftest import REPO, set_config
from test_plan import FENCE, file_unit, find, graph, plan_text, planned


def graphed(world, *edits):
  """Plan the sample units (the plan text edited by each `(old, new)` of `edits`) and graph them; the plan file."""
  spec, sha, plan, card = planned(world)
  text = plan_text(spec)
  for old, new in edits:
    assert old in text
    text = text.replace(old, new, 1)
  plan.write_text(text, encoding="utf-8")
  assert graph(world, plan, card)[0] == 0
  return plan


def scan_with(world, *edits, plan=None, **units):
  """Scan the graphed sample units with `units.*` set in the repository's config."""
  plan = plan or graphed(world, *edits)
  set_config(world, repo=REPO, units={**core.DEFAULT_CONFIG["units"], **units})
  return world.run("scan", "--plan", plan)


@pytest.mark.parametrize("key,value,ok", [("max_body_kb", 48, True), ("max_body_kb", 49, False), ("max_body_kb", 0, False),
                                          ("max_files", 8, True), ("max_files", 7, False), ("max_steps", 1, True),
                                          ("max_steps", 0, False), ("max_steps", "16", False)])
def test_units_limits_validated(world, key, value, ok):
  # each units.* value is a positive int, max_body_kb <= 48, max_files >= 8; read live at each scan
  assert core.DEFAULT_CONFIG["units"] == {"max_body_kb": 25, "max_files": 10, "max_steps": 16}
  code, out = scan_with(world, **{key: value})
  assert (f"units.{key}" not in out) if ok else (code == 1 and f"units.{key}" in out), out


U01_STEP_END = ("   Implement `u01_fn(x: int) -> int` in `src/u01.ts`.\n   Run the same command; expected: PASS. "
                "Commit `test(S1): u01 empty` then `feat(S1): u01 empty`.\n")


def more_steps(*numbers):
  return "".join(f"{n}. Write the failing test `test_u01_{n}` in `tests/test_u01.py`:\n   {FENCE}python\n   def test_u01_{n}(): assert u01_fn({n}) == {n}\n   {FENCE}\n"
                 f"   Implement the `{n}` case of `u01_fn(x: int) -> int` in `src/u01.ts`, returning its input unchanged.\n" for n in numbers)


SCOPE = "| Scope paths | `src/u01.ts` (create), `tests/test_u01.py` (create) |"
OVER = {  # U01's section made one over the limit (nine Scope paths take Size L)
  "max_body_kb": [("| Objective | Queue exists. |", "| Objective | Queue " + "x" * 25_700 + " exists. |")],
  "max_files": [(SCOPE, SCOPE[:-2] + ", " + ", ".join(f"`src/more{n}.ts` (create)" for n in range(7)) + " |"),
                ("| Size | S |", "| Size | L |")],
  "max_steps": [(U01_STEP_END, U01_STEP_END + more_steps(2, 3))]}


@pytest.mark.parametrize("limit,setting,value", [("max_body_kb", 25, "bytes"), ("max_files", 8, 9), ("max_steps", 2, 3)])
def test_scan_refuses_an_unfiled_unit_over_a_limit(world, limit, setting, value):
  # U01 one over a valid limit: one problem line holds U01, the key and the value; once filed, none names U01
  plan = graphed(world, *OVER[limit])
  code, out = scan_with(world, plan=plan, **{limit: setting})
  lines = [l for l in out.splitlines() if f"units.{limit}" in l]
  assert code == 1 and len(lines) == 1 and "U01" in lines[0] and str(setting) in lines[0], out
  assert ("bytes" if value == "bytes" else str(value)) in lines[0], lines[0]
  file_unit(world, "U01", 7)
  code, out = scan_with(world, plan=plan, **{limit: setting})
  assert code == 0 and not [l for l in out.splitlines() if "U01" in l and "units." in l], out


def test_scan_drops_the_bytes_warning(world):
  # the 24,576-byte warning goes; the 10-step and 0.40 fenced-share warnings stay
  plan = graphed(world, ("| Objective | Queue exists. |", "| Objective | Queue " + "x" * 21_300 + " exists. |"),
                 (U01_STEP_END, U01_STEP_END + more_steps(*range(2, 12))))
  code, out = scan_with(world, plan=plan)
  numbers = json.loads(find(world, "U01.json").read_text(encoding="utf-8"))  # scan numbers of the 25,000-byte unit with 11 Steps
  assert code == 0 and 24_576 < numbers["bytes"] <= 25_600 and numbers["steps"] == 11, out
  assert not any(w.startswith("bytes") for w in numbers["warnings"])
  assert "steps 11 > 10" in numbers["warnings"]
  assert "bytes" not in scan.WARN and scan.WARN["fenced_share"][0] == 0.40
