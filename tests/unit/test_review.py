# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03).

"""EGM's tests of the subcommands U04 (the review loop and spec review) changes, moved from test_helper.py by U03;
that unit rewrites the ones whose form it changes."""

import json

import pytest

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
