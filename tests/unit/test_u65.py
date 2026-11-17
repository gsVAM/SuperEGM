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
