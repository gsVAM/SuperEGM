# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U75's tests: reference documents reviewed with the spec, their scope, their `refs` manifest and its settle and approval checks.

"""U75: reference documents, reviewed with the spec."""

from conftest import git
from test_review import opened
from test_u37 import configure
from test_u74 import DIR, ROLES, commit_files

INV, GLOSSARY = f"{DIR}/invariants.md", f"{DIR}/glossary.md"


def branch_with_changed_invariants(world):
  """Two reference documents on `main`; a branch off it that changes one of them; the folder configured."""
  commit_files(world, {INV: "Invariants.\n", GLOSSARY: "Glossary.\n"})
  git(["switch", "-q", "-c", "spec-branch"], world.repo)
  commit_files(world, {INV: "Invariants, revised.\n"})
  configure(world, [{"dir": DIR, "to": ROLES}])


def test_review_scope_lists_a_changed_reference_document(world):
  """Whole files under the configured dir changed between the merge base with <base> and HEAD."""
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  code, out = world.run("review", "scope", "--review", rid, "--runcard", cid)
  assert code == 0 and [l for l in out.splitlines() if l.startswith("changed docs/")] == ["changed docs/reference/invariants.md"], out
