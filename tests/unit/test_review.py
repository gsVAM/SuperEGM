# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03); the review loop and approve-spec (U04).

"""U04: the review loop (`review open|record|settle|status|rule`) and `approve-spec`; EGM's approve tests moved here by U03
stay until S12 replaces them."""

import hashlib, json, re, subprocess
from pathlib import Path
import pytest
from superegm import store, atomic_write
from superegm.review import parse_findings

from conftest import DESIGN, git


def test_approve_checks_and_records(world):
  design = world.repo / "docs/designs/sample.md"
  code, out = world.run("approve-spec", "--design", design)
  assert code == 0 and "Approve `" in out and "Options: Approve | Stop" in out
  code, out = world.run("approve-spec", "--design", design, "--yes")
  assert code == 0
  record = json.loads((world.artifacts / "approvals/sample.json").read_text(encoding="utf-8"))
  assert record["path"] == str(design) and record["handoff_id"].startswith("sample-")
  design.write_text(DESIGN + "\nchanged\n", encoding="utf-8")
  code, out = world.run("approve-spec", "--design", design)
  assert code == 1 and "tracked but not clean" in out

  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1 and "spec changed since the approval: run approve-spec again" in out
  git(["checkout", "--", "docs/designs/sample.md"], world.repo)
  (world.repo / "docs/designs/plain.md").write_text("# Plain\n\nNo plan.\n", encoding="utf-8")
  git(["add", "-A"], world.repo)
  git(["commit", "-qm", "plain"], world.repo)
  plain = world.repo / "docs/designs/plain.md"
  code, out = world.run("approve-spec", "--design", plain, "--runcard", world.open_card("review-spec", plain), card=None)
  assert code == 1 and "Detailed Implementation Plan" in out and "egm-draft" in out


def test_approve_refuses_an_untracked_or_ignored_design(world):
  """A clean `git status -- <path>` says nothing about an ignored file."""
  design = world.repo / "docs/designs/ignored.md"
  design.write_text(DESIGN, encoding="utf-8")
  (world.repo / ".gitignore").write_text("docs/designs/ignored.md\n", encoding="utf-8")
  code, out = world.run("approve-spec", "--design", design, "--runcard", world.open_card("review-spec", design), card=None)
  assert code == 1 and "not tracked by git" in out


# ---------------------------------------------------------------- S1: the findings line

GOOD = "design-2-1 | high | §3 line 40 | regression: yes | the cap is unstated"

@pytest.mark.parametrize("line,error", [
  (GOOD, None),
  ("design-2-2 | low | §1 | regression: no | a nit", None),
  ("design-2-1 | high | §3 | the cap is unstated", "expected 5 fields"),
  ("zoom-out-2-1 | high | §3 | regression: no | x", "id must be design-2-<n>"),
  ("design-1-1 | high | §3 | regression: no | x", "id must be design-2-<n>"),
  ("design-2-1 | blocker | §3 | regression: no | x", "severity must be high|medium|low"),
  ("design-2-1 | high | §3 | regression: maybe | x", "regression must be yes|no"),
])
def test_findings_line_grammar(line, error):
  if error is None:
    [f] = parse_findings(line + "\n\n", "design", 2)
    assert f["id"].startswith("design-2-") and f["severity"] in {"high", "low"} and f["regression"] in {"yes", "no"}
    assert f["claim"] and f["location"] and f["disposition"] is None and f["ruling"] is None
  else:
    with pytest.raises(ValueError, match=rf"^1: {re.escape(error)}$"):
      parse_findings(line + "\n", "design", 2)
  assert parse_findings("\n  \n", "design", 1) == []
  assert parse_findings("set-2-1 | high | U07 Interfaces | regression: no | x\n", "set", 1)[0]["id"] == "set-2-1"   # a set id carries the set's own round
