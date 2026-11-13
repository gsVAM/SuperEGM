# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: 1.2.1-pre.1 P3's tests of scan's line cites (spec section 6.5, "What a Step holds").

"""P3: `scan` refuses a `path:<line>` cite on an Interfaces or Produces line and warns, without
refusing, on more than ten cites into the unit's own Scope paths."""

import json
import pytest
from superegm import scan

from test_plan import find, graph, plan_text, planned

PRODUCES = "- Produces: u02_fn(x: int) -> int"
CONSUMES = "- Consumes: u01_fn(x: int) -> int (U01)\n- Produces: u02_fn"
OBJECTIVE = "| Objective | Worker exists. |"


def rescan(world, old, new):
  spec, sha, plan, card = planned(world)
  text = plan_text(spec)
  assert old in text
  plan.write_text(text.replace(old, new, 1), encoding="utf-8")
  assert graph(world, plan, card)[0] == 0
  code, out = world.run("scan", "--plan", plan)
  return code, out, json.loads(find(world, "U02.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("old,new,line", [
  pytest.param(PRODUCES, PRODUCES + ", as in `review.py:758`", PRODUCES + ", as in `review.py:758`", id="produces"),
  pytest.param(CONSUMES, "- Consumes: u01_fn(x: int) -> int, see src/u01.ts:12 (U01)\n- Produces: u02_fn",
               "- Consumes: u01_fn(x: int) -> int, see src/u01.ts:12 (U01)", id="consumes"),
])
def test_scan_refuses_a_line_cite_on_an_interfaces_line(world, old, new, line):
  code, out, _ = rescan(world, old, new)
  assert code == 1 and f"interface-cite: U02: {line}" in out and out.rstrip().endswith("problem(s)"), out


@pytest.mark.parametrize("old,new", [
  pytest.param(OBJECTIVE, "| Objective | Worker exists, as `review.py:758` shows. |", id="cite-elsewhere"),
  pytest.param(PRODUCES, PRODUCES + ", as in `review.py`", id="bare-path-on-produces"),
])
def test_scan_allows_a_line_cite_elsewhere_and_a_bare_path_on_an_interfaces_line(world, old, new):
  code, out, _ = rescan(world, old, new)
  assert code == 0 and out.rstrip().endswith("scan: clean"), out


@pytest.mark.parametrize("cites,warnings", [
  pytest.param([f"`src/u02.ts:{n}`" for n in range(11)], ["scope_cites 11 > 10"], id="eleven"),
  pytest.param([f"`src/u02.ts:{n}`" for n in range(10)], [], id="exactly-ten"),
  pytest.param([f"`tests/test_u02.py:{n}`" for n in range(6)] + [f"u02.ts:{n}" for n in range(5)],
               ["scope_cites 11 > 10"], id="both-scope-paths-and-a-bare-name"),
  pytest.param([f"`src/u01.ts:{n}`" for n in range(11)], [], id="outside-scope"),
])
def test_scan_warns_without_refusing_on_more_than_ten_scope_cites(world, cites, warnings):
  code, out, numbers = rescan(world, OBJECTIVE, f"| Objective | Worker exists; see {', '.join(cites)}. |")
  assert code == 0 and out.rstrip().endswith("scan: clean"), out
  assert numbers["warnings"] == warnings and all(w in out for w in warnings)


def test_scan_byte_size_and_fenced_share_limits_unchanged():
  assert scan.WARN["bytes"][0] == 24_576 and scan.WARN["fenced_share"][0] == 0.40 and scan.BODY_LIMIT == 49_152
