# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U119's tests (1.3 design section 3.3): a head whose checks all concluded neutral or skipped is red, and the full suite is CI's.

"""U119: `ci_verdict` reads "green" as "a check ran"; the plan and builder wording says the full suite is CI's."""

from pathlib import Path

import pytest

import superegm
from superegm import status


def make_ci(conclusions, contexts):
  states = [s for _, s in contexts]
  combined = None
  if states:
    combined = "failure" if "failure" in states else "success"
  return {"check_runs": [{"name": f"run{i}", "status": "completed", "conclusion": c}
                         for i, c in enumerate(conclusions)],
          "combined_state": combined,
          "contexts": [{"context": n, "state": s} for n, s in contexts],
          "statuses": len(contexts)}


@pytest.mark.parametrize("conclusions, contexts, verdict", [
    (["success"], [], "ci green"),
    (["success", "skipped"], [], "ci green"),
    (["success", "neutral"], [], "ci green"),
    (["neutral"], [], "ci red (no check ran)"),
    (["skipped"], [], "ci red (no check ran)"),
    (["neutral", "skipped"], [], "ci red (no check ran)"),
    (["skipped"], [("ci/ext", "success")], "ci green"),
    ([], [("ci/ext", "success")], "ci green"),
    (["skipped"], [("ci/ext", "failure")], "ci red (ci/ext)"),
    ([], [], "waiting-for-ci"),
])
def test_no_check_ran_is_red(conclusions, contexts, verdict):
  # "green" means a check ran: a run concluded `success` or a status context is `success`; neutral and skipped alone are red
  assert superegm.ci_verdict(make_ci(conclusions, contexts)) == verdict
  assert status.ci_word("ci red (no check ran)") == "red:no check ran"


def read(path):
  return (Path(__file__).resolve().parents[2] / path).read_text()


def test_full_suite_is_ci():
  # a unit's own test file is a Run item; the full suite is covered by `CI green on the head` and is CI's, never the builder's
  plan_skill = read("skills/plan/SKILL.md")
  writing_plans = read("skills/plan/references/writing_plans.md")
  builder_orders = read("skills/wave/references/builder_orders.md")
  for text in (plan_skill, writing_plans):
    assert "a unit's own test file is a `Run` item" in text
    assert "the full suite is covered by `CI green on the head`" in text
  assert "Before a push you run your unit's own test file; the full suite is CI's" in builder_orders
  assert "full test command" not in builder_orders
