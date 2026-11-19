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
  commit_files(world, {INV: "Invariants, revised again.\n"})   # a reference document alone moves
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
    commit_files(world, {INV: "Invariants, fixed.\n"})   # the fix: a reference document alone
    code, out = settle(world, rid, "design-1-1", "fixed", cid)
    assert code == 0, out
    disposition = rjson(world, rid, "round-1.json")["reviewers"]["design"]["findings"][0]["disposition"]
  assert ("not recorded" not in record_out) == recorded and disposition == settled


@pytest.mark.parametrize("cycle", ["converged", "proceed at round 0", "proceed after the cap"])
def test_approve_spec_refuses_a_reference_edit_after_review(world, cycle):
  """Unchanged passes; a reference-only edit after the reviewed manifest refuses until a new proceed."""
  from test_review import HIGH, approve, rounds
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  proceed = lambda: world.run("review", "rule", "--review", rid, "--ruling", "proceed", "--owner", "--reason", "accepted risk", "--runcard", cid)
  if cycle == "converged":
    rounds(world, rid, cid, [[]])
  elif cycle == "proceed after the cap":
    rounds(world, rid, cid, [HIGH(n) for n in range(1, 4)])   # `configure` leaves the default cap, 3 rounds
  if cycle != "converged":
    assert proceed()[0] == 0
  code, out = approve(world, spec, cid)   # no --yes: the refusals run, the prompt is printed, nothing is written
  approve_unchanged = code
  commit_files(world, {INV: "Invariants, edited after the review.\n"})
  refused_code, refused_out = approve(world, spec, cid)
  assert approve_unchanged == 0, out
  assert refused_code == 1 and "approve-spec: docs/reference/invariants.md: differs from the reviewed round" in refused_out, refused_out
  if cycle != "converged":
    assert proceed()[0] == 0
    approve_after_new_proceed = approve(world, spec, cid)[0]
    assert approve_after_new_proceed == 0


def test_the_manifest_reads_head_not_the_working_tree(world):
  """An uncommitted reference edit is neither scoped nor recorded: the approval freezes HEAD's bytes."""
  from test_review import approve, rjson, rounds
  from test_u37 import blob_sha
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  (world.repo / INV).write_text("Invariants, edited but not committed.\n", encoding="utf-8")
  rounds(world, rid, cid, [[]], start=2)
  assert rjson(world, rid, "round-1.json")["refs"] == rjson(world, rid, "round-2.json")["refs"] == [{"file": INV, "sha": blob_sha(b"Invariants, revised.\n")}]
  assert approve(world, spec, cid)[0] == 0


@pytest.mark.parametrize("when", ["before the review", "after the reviewed round"])
def test_a_deleted_reference_document_is_a_changed_path(world, when):
  """A deletion is a change: scoped and recorded before the review, refused by approve-spec after it."""
  from test_review import approve, rjson, rounds
  branch_with_changed_invariants(world)
  remove = lambda: (git(["rm", "-q", GLOSSARY], world.repo), git(["commit", "-qm", "drop the glossary"], world.repo))
  if when == "before the review":
    remove()
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  scoped = [l for l in world.run("review", "scope", "--review", rid, "--runcard", cid)[1].splitlines() if l.startswith("changed docs/")]
  if when == "before the review":
    assert scoped == [f"changed {GLOSSARY}", f"changed {INV}"] and [r["file"] for r in rjson(world, rid, "round-1.json")["refs"]] == [GLOSSARY, INV]
    assert approve(world, spec, cid)[0] == 0
  else:
    assert scoped == [f"changed {INV}"]
    remove()
    code, out = approve(world, spec, cid)
    assert code == 1 and f"approve-spec: {GLOSSARY}: differs from the reviewed round" in out, out


def test_a_reference_only_edit_moves_a_converged_review(world):
  """review status reads a committed reference-only edit as moved bytes: not converged, `fixed: re-review`, no accept."""
  from test_review import rounds, rule, status
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert status(world, rid, cid)[0] == 0
  commit_files(world, {INV: "Invariants, edited after the review.\n"})
  code, out = status(world, rid, cid)
  assert code == 3 and "converged no" in out and out.splitlines()[2] == "fixed: re-review on the current bytes", out
  assert rule(world, rid, "accept", cid)[0] != 0


def test_a_later_record_into_a_round_refuses_a_moved_reference(world):
  """One round, one reference snapshot: a record after a reference edit is refused as a moved sha is."""
  from test_review import record
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  assert record(world, rid, 1, "design", [], cid)[0] == 0
  commit_files(world, {INV: "Invariants, edited between the two records.\n"})
  code, out = record(world, rid, 1, "zoom-out", [], cid)
  assert code == 1 and "review record: reference documents differ from the round's" in out, out


def test_a_renamed_reference_document_is_a_changed_path(world):
  """Rename detection never hides the old path: moving a reviewed folder's document is a deletion plus an addition."""
  from test_review import approve, rounds
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  git(["mv", GLOSSARY, GLOSSARY.replace(".md", ".txt")], world.repo)
  git(["commit", "-qm", "rename the glossary out of the folder's documents"], world.repo)
  code, out = approve(world, spec, cid)
  assert code == 1 and f"approve-spec: {GLOSSARY}: differs from the reviewed round" in out, out


def test_a_record_refuses_reviewers_who_read_other_reference_bytes(world):
  """The round's `refs` are what its panel's stored brief listed: a commit between the render and the first record is refused."""
  from superegm.instructions import render_stored
  from test_review import hstore, record
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  render_stored(hstore(world), "reviewers", "local", review=rid, round=1, root=world.repo)   # the brief the panel reads: version A
  commit_files(world, {INV: "Invariants, committed after the brief was rendered.\n"})
  code, out = record(world, rid, 1, "design", [], cid)
  assert code == 1 and f"review record: {INV}: differs from the reviewers' brief" in out, out


def test_approve_names_the_moved_reference_when_a_later_round_is_partly_recorded(world):
  """A later round only partly recorded holds the current manifest but is not completed: approval still names the path."""
  from test_review import approve, record, rounds
  branch_with_changed_invariants(world)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  commit_files(world, {INV: "Invariants, edited after the review.\n"})
  assert record(world, rid, 2, "design", [], cid)[0] == 0   # round 2 pins the new manifest; zoom-out has not recorded
  code, out = approve(world, spec, cid)
  assert code == 1 and f"approve-spec: {INV}: differs from the reviewed round" in out, out


SPEC_TEXT = "# Spec\n\n## A\nline\nline\n\n## B\nline\nline\n"
REF_ROW = ("changed", "docs/reference/domain model.md", 0, 0)


@pytest.mark.parametrize("rows, location, answer", [
  ([REF_ROW], "docs/reference/domain model.md:500", None),                       # a listed path with a space, any line
  ([REF_ROW], "docs/reference/unlisted.md:4", "none"),                           # any other file
  ([REF_ROW], "§3.5 line 4", "## A"),                                             # a dotted section cite is no file
  ([REF_ROW], "3.5:4", "## A"),
  ([("whole", "(no approval)", 1, 9), REF_ROW], "§3.5 line 4", None),             # a whole round exempts a spec location
  ([("changed", "B", 7, 9), REF_ROW], "skills/x.py:8", "none"),                  # a reference is listed: any other file answers none
  ([("whole", "(whole)", 1, 9), REF_ROW], "skills/x.py:8", "none"),
  ([("changed", "B", 7, 9), REF_ROW], "other/design.md:8", "none"),              # a same-named file of another directory
  ([("changed", "B", 7, 9), REF_ROW], "docs/specs/design.md:8", None),
  ([("changed", "B", 7, 9), REF_ROW], "design.md:8", None),
  ([("changed", "B", 7, 9), REF_ROW], "/abs/repo/docs/specs/design.md:8", None),
  ([("changed", "B", 7, 9), REF_ROW], "§2 line 8", None),
  ([("changed", "B", 7, 9), REF_ROW], "./docs/reference/domain model.md:12", None),           # a listed document by any form of its path
  ([("changed", "B", 7, 9), REF_ROW], "/abs/repo/docs/reference/domain model.md:12", None),
  ([("changed", "B", 7, 9), REF_ROW], "domain model.md:12", None),
  ([("changed", "B", 7, 9), REF_ROW], "docs/reference/domain model.md#L12", None),
  ([("changed", "B", 7, 9), REF_ROW], "docs/specs/design.md#L8", None),                       # `#` and `,` end a file name as `:` does
  ([("changed", "B", 7, 9), REF_ROW], "skills/x.py, line 8", "none"),
  ([("changed", "B", 7, 9), REF_ROW], "other/domain model.md:12", "none")])               # another directory's same-named document
def test_the_scope_filter_reads_a_path_before_its_line(rows, location, answer):
  """Only a spec location goes through cited_line and the sections; a path other than the spec's or a changed document answers none."""
  from superegm.review import out_of_scope, sections
  assert out_of_scope(rows, sections(SPEC_TEXT), location, "docs/specs/design.md") == answer


@pytest.mark.parametrize("phrase", ["reference documents", "offer once", "docs/reference/", "`dir` entry", "all four roles",
                                    "commits them with the step's commit", "records nothing"])
def test_the_brainstorm_offers_reference_documents_once(phrase):
  """The brainstorm nudges, never requires."""
  from pathlib import Path
  assert phrase in (Path(__file__).resolve().parents[2] / "skills/brainstorming/SKILL.md").read_text(encoding="utf-8")
