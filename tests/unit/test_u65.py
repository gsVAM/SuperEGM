# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U65's tests: the plan's words for shared files (spec section 6.1).

"""U65: a code dependency goes in `Blocked by`; a shared-file order is a merge order only (spec section 6.1)."""

from pathlib import Path


def _read(p):
  return " ".join(Path(p).read_text().split())


def test_plan_skill_says_shared_files_build_in_parallel():
  t = _read("skills/plan/SKILL.md")
  assert "calling a function, extending a change or consuming an interface of another unit lists it in `Blocked by`" in t
  assert "says only which pull request merges first" in t
  assert "units sharing a file build in parallel" in t
  assert "the Shared files order for any file both edit" in t


def test_handoff_plan_says_shared_files_are_a_merge_order():
  t = _read("skills/plan/references/handoff_plan.md")
  assert "a merge order: `after` merges after that unit, `before` merges before it" in t
  assert "readiness reads `Blocked by` alone (an approval without `rounds` keeps 1.2's edges)" in t
  assert "`after` adds an edge" not in t
  assert "shared-file chain contradicts the blockers" in t


def test_issue_template_documents_merges_after_words():
  t = _read("skills/plan/references/issue_template.md")
  assert "`merges after` / `merges before` for a handoff whose approval carries `rounds`" in t
  assert "`after` / `before` for one approved under 1.2.0" in t


def test_plan_skill_widens_blocked_by_and_states_the_rounds_condition():
  t = _read("skills/plan/SKILL.md")
  assert "only where one consumes the other's interface" not in t
  assert "a `Blocked by` edge where one calls its function, extends its change or consumes its interface" in t
  assert "for a handoff whose approval carries `rounds`" in t
  assert "an approval without `rounds` keeps 1.2's serial edges" in t
  assert t.index("The one exception is the release's closing sweep") < t.index("a `Shared files` order says only")


def test_plan_skill_width_advice_is_per_approval():
  t = _read("skills/plan/SKILL.md")
  assert "under an approval with `rounds` a shared-file chain forces no wave" in t


def test_handoff_plan_blocker_definition_graph_and_units_json_row():
  t = _read("skills/plan/references/handoff_plan.md")
  assert "A blocker is a unit whose code this unit calls, whose change it extends or whose interface it consumes; a file both edit is a `Shared files` order, never a blocker." in t
  assert "`merge_after` list" in t
  assert "`edges` lists both kinds" in t
  assert "A unit's wave is `1 + max(wave of its predecessors)`, predecessors being the `Blocked by` entries alone" in t


def test_changed_files_carry_a_u65_notice_entry():
  for p in ("skills/plan/SKILL.md", "skills/plan/references/handoff_plan.md", "skills/plan/references/issue_template.md"):
    head = [l for l in Path(p).read_text().splitlines() if "Modified by SuperEGM (gsVAM), 2026:" in l][0]
    assert "(U65)" in head, p
