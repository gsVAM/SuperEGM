# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U75's tests: reference documents reviewed with the spec, their scope, their `refs` manifest and its settle and approval checks.

"""U75: reference documents, reviewed with the spec."""

import pytest

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


def test_a_reference_only_edit_is_a_changed_round(world):
  """Every sha stays the spec's raw sha256; the reference manifest rides beside it as `refs`."""
  from test_review import approval, approve, rjson, rounds, status
  from superegm import launch, sha256_file
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  (world.repo / INV).write_text("Invariants, revised again.\n", encoding="utf-8")   # a reference document alone moves
  rounds(world, rid, cid, [[]], start=2)
  round1, round2, spec_sha256 = rjson(world, rid, "round-1.json"), rjson(world, rid, "round-2.json"), sha256_file(spec)
  assert [r["file"] for r in round1["refs"]] == [INV] and round2["refs"] != round1["refs"]
  assert round2["artifact_sha256"] == round1["artifact_sha256"] == spec_sha256
  assert status(world, rid, cid)[0] == 0
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  entry = approval(world)["entries"][-1]
  graph_sha = entry["sha256"]   # what `graph` reads as the handoff's spec sha
  # `launch` reads the spec at origin against that same sha: the approved bytes pass its check
  assert launch.origin_problems(world.repo, "main", {**entry, "path": str(spec)}, ref="HEAD", spec_only=True) == []
  assert graph_sha == entry["sha256"] == spec_sha256


@pytest.mark.parametrize("location, recorded, settled", [
  ("docs/reference/invariants.md:12", True, "fixed"),
  ("docs/reference/unlisted.md:12", False, None)])
def test_a_finding_on_a_reference_document_is_in_scope_and_settles(world, location, recorded, settled):
  """A `changed <path>` file is in scope whatever its line; any other non-spec path answers `none`."""
  from test_review import F, record, rjson, settle
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  code, record_out = record(world, rid, 1, "design", [F("design", 1, 1, loc=location)], cid)
  assert code == 0, record_out
  found = rjson(world, rid, "round-1.json")["reviewers"]["design"]["findings"]
  disposition = None
  if found:
    (world.repo / INV).write_text("Invariants, fixed.\n", encoding="utf-8")   # the fix: a reference document alone
    code, out = settle(world, rid, "design-1-1", "fixed", cid)
    assert code == 0, out
    disposition = rjson(world, rid, "round-1.json")["reviewers"]["design"]["findings"][0]["disposition"]
  assert ("not recorded" not in record_out) == recorded and disposition == settled
