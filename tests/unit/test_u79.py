# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U79's pins of spec section 6.5 (the planning documents, the Step grammar, scan's cite rules).

"""U79: the planning documents state section 6.5's rules; an old-grammar and a new-grammar plan read the same;
scan refuses a line cite on a Consumes/Produces line and only warns on more than ten Scope cites."""

import json
from pathlib import Path

import pytest
from superegm import body, scan, tdd_order

from test_plan import find, graph, plan_text, planned

ROOT = Path(__file__).resolve().parents[2]
FENCE = chr(96) * 3


@pytest.mark.parametrize("path, phrases", [
  ("skills/plan/references/writing_plans.md", ["Implement the behaviour in"]),
  ("skills/plan/references/handoff_plan.md", ["conftest", "fixture"]),
  ("resources/document_standards/handoff-standard.md",
   ["Q9", "test name, the behaviour and the expected values", "Q11", "private or harness detail"]),
  ("agents/readiness.md", ["product, security or cross-unit contract decision"]),
  ("skills/review-plan/references/proportion.md", ["five shapes", "private or harness detail", "medium"]),
  ("skills/plan/SKILL.md", ["evidence, never a requirement"]),
  ("skills/review-plan/SKILL.md", ["product, security or cross-unit contract decision"]),
])
def test_documents_state_the_planning_rules(path, phrases):
  # each document states §6.5's rule and drops the check-fixtures and current-line-number instructions
  text = " ".join((ROOT / path).read_text(encoding="utf-8").split())
  assert all(p in text for p in phrases) and "current line numbers" not in text


def steps_body(old: bool) -> str:
  """A unit body whose one Step is a 1.2 full-body Step or a §6.5 thin Step, naming the same paths."""
  if old:
    step = (f"1. Write the failing test `test_x` in `tests/unit/test_u01.py`:\n   {FENCE}python\n"
            f"   def test_x(tmp_path):\n     fx = make_fixture(tmp_path)\n     assert a.f(fx) == 1\n   {FENCE}\n"
            "   Run `pytest tests/unit/test_u01.py::test_x -q`; expected: FAIL (`AttributeError`).\n"
            "   Implement `f(fx)` in `src/a.py`.\n"
            "   Run the same command; expected: PASS. Commit `test(S1): x` then `feat(S1): x`.\n")
  else:
    step = (f"1. Write the failing test `test_x` in `tests/unit/test_u01.py`:\n   {FENCE}python\n"
            f"   def test_x():\n     # f returns 1\n     assert a.f() == 1\n   {FENCE}\n"
            "   Implement the behaviour in `src/a.py`.\n")
  return ("<!-- superegm:handoff=h unit=U01 spec=abc -->\n# U01\n\n## Definition of done\n"
          "1. The test for each Step was committed before its implementation (checked by superegm tdd-order)\n"
          "2. Run `pytest tests/unit/test_u01.py -q` — the cases pass\n3. Exists `tests/unit/test_u01.py`\n"
          f"4. CI green on the head\n\n## Steps\n{step}\n## Decide before build\n- none\n")


def test_old_and_new_steps_read_the_same():
  # a 1.2 full-body Step and a §6.5 thin Step naming the same test and implementation paths
  old, new = steps_body(True), steps_body(False)
  commits = [("test(S1): x", ["tests/unit/test_u01.py"]), ("feat(S1): x", ["src/a.py"])]
  assert body.step_paths(old) == body.step_paths(new) == [(1, "tests/unit/test_u01.py", "src/a.py")]
  assert body.run_commands(old) == body.run_commands(new)
  assert tdd_order.check(old, commits) == tdd_order.check(new, commits) == []
  assert tdd_order.check(old, commits[::-1]) == tdd_order.check(new, commits[::-1]) != []
  assert [n for n, _, _ in body.dod_items(old)] == [n for n, _, _ in body.dod_items(new)] == [2, 3, 4]


def test_scan_produces_cite_names():
  # the unit's Produces line: the cite pattern and the Scope-cite limit
  assert scan.CITE_RE.pattern == r"(?<![\w./-])([\w./-]*\w\.[A-Za-z]\w*):\d+"
  assert scan.SCOPE_CITES == 10


@pytest.mark.parametrize("line, cites, form, refused, warned", [
  ("- Consumes: `x` at `review.py:52` (U02)", 0, "", True, False),
  ("- Produces: `y` — see skills/plan/scripts/superegm/review.py:52", 0, "", True, False),
  ("- Produces: `y`", 10, "src/u03.ts:{n}", False, False),
  ("- Produces: `y`", 11, "src/u03.ts:{n}", False, True),
  ("- Produces: `y`", 11, "u03.ts:{n}", False, True),   # a bare cite counts for the Scope path it ends
  ("- Produces: `y`", 10, "u03.ts:{n}", False, False),
  ("- Produces: `y`", 11, "other/file.py:{n}", False, False),   # cites outside Scope never count
])
def test_scan_cite_rules(world, line, cites, form, refused, warned):
  # interface-cite refuses a cite on a Consumes/Produces line; more than ten Scope cites only warn
  spec, _, plan, card = planned(world)
  text = plan_text(spec)
  produces = "- Produces: u03_fn(x: int) -> int"
  assert produces in text
  text = text.replace(produces, f"{produces}\n{line}", 1)
  if cites:
    cited = ", ".join("`" + form.format(n=n) + "`" for n in range(cites))
    text = text.replace("| Objective | Admin exists. |", f"| Objective | Admin exists; see {cited}. |", 1)
  plan.write_text(text, encoding="utf-8")
  graphed = graph(world, plan, card)
  assert graphed[0] == 0, graphed[1]
  code, out = world.run("scan", "--plan", plan)
  scan_json = json.loads(find(world, "U03.json").read_text(encoding="utf-8"))
  refusals = out.splitlines()
  assert any(f.startswith("interface-cite: U03: ") for f in refusals) is refused
  assert any(w.startswith("scope_cites") for w in scan_json["warnings"]) is warned
  assert (not warned) or "scope_cites 11 > 10" in scan_json["warnings"]
  assert (code == 1) is refused
