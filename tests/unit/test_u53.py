# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U53's tests: no superseding a partly filed handoff, the restore of its last filing, and the owner's void without a review.

"""U53: `approve-spec` over a partly filed handoff."""

import json

import pytest
from test_review import converged_spec, approve, approval, hstore, git, SPEC, SLUG
from superegm import atomic_write, store

FIRST_DRY_RUN_SHA, SECOND_DRY_RUN_SHA = "a" * 64, "b" * 64
WRITES = [["issue", "U07", "U07 title", ["bug"], "the body"]]
SECOND_WRITES = WRITES + [["issue", "U08", "U08 title", ["bug"], "another body"]]
CHANGED = SPEC.replace("Text.", "Changed.")


def jread(path):
  return json.loads(path.read_text(encoding="utf-8"))


def filing_state(hid, **extra):
  """`state.json` of a handoff whose filing of the first dry run ran: one `filings[]` entry, `unit U07` filed as #7."""
  state = {"handoff_id": hid, "units": {"U07": {"number": 7}}, "confirmed_sha256": FIRST_DRY_RUN_SHA,
           "confirmed": {"sha256": FIRST_DRY_RUN_SHA, "repo": "o/r", "writes": WRITES},
           "filings": [{"sha256": FIRST_DRY_RUN_SHA, "writes": WRITES, "at": "2026-11-12T10:00:00Z"}]}
  state.update(extra)
  return state


def receipt(sha=FIRST_DRY_RUN_SHA, complete=True, problems=()):
  return {"sha256": sha, "complete": complete, "problems": list(problems)}


def latest_state(hid, latest):
  if latest == "filing started, no verify receipt":
    return filing_state(hid)
  if latest == "filing complete, receipt problems set":
    return filing_state(hid, verify=receipt(problems=["U07 differs"]))
  if latest == "filing complete, then graph adds an amended unit with no number":
    state = filing_state(hid, verify=receipt())
    state["units"]["U08"] = {}
    return state
  if latest == "filing complete, then a second dry run never applied":
    return filing_state(hid, verify=receipt(), confirmed_sha256=SECOND_DRY_RUN_SHA,
                        confirmed={"sha256": SECOND_DRY_RUN_SHA, "repo": "o/r", "writes": SECOND_WRITES})
  if latest == "filing complete and problem-free":
    return filing_state(hid, verify=receipt())
  if latest == "confirmed list, no filings[] entry":
    state = filing_state(hid)
    del state["filings"]
    state["units"] = {"U07": {}}
    return state
  if latest == "filing started, no verify receipt, approval voided":
    return filing_state(hid)
  raise AssertionError(latest)


def approve_over(world, latest, approval_kind):
  """The spec approved, its handoff left as `latest` says, then the second approval `approval_kind` says: (exit code, output)."""
  spec, cid, _ = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  first = approval(world)["entries"][-1]["handoff_id"]
  atomic_write(world.artifacts / first / "state.json", latest_state(first, latest))
  if approval_kind == "after the void":
    record = approval(world)
    record["entries"][-1]["voided_by"] = f"spec-{SLUG}-c1"
    atomic_write(store(world.repo).path("approvals", SLUG), record)
  if approval_kind == "same-cycle re-approval, same id":
    spec2, cid2 = spec, cid
  else:
    spec2, cid2, _ = converged_spec(world, CHANGED)
  head, before = git(world, "rev-parse", "HEAD"), approval(world)
  code, out = approve(world, spec2, cid2, "--yes")
  if code == 1:  # a refusal writes nothing
    assert git(world, "rev-parse", "HEAD") == head and approval(world) == before
    assert jread(world.artifacts / first / "state.json") == latest_state(first, latest)
  return code, out


@pytest.mark.parametrize("latest, approval_kind, refused", [
  ("filing started, no verify receipt", "opening, new id", True),
  ("filing complete, receipt problems set", "opening, new id", True),
  ("filing complete, then graph adds an amended unit with no number", "opening, new id", True),
  ("filing complete, then a second dry run never applied", "opening, new id", False),
  ("filing complete and problem-free", "opening, new id", False),
  ("confirmed list, no filings[] entry", "opening, new id", False),
  ("filing started, no verify receipt", "same-cycle re-approval, same id", False),
  ("filing started, no verify receipt, approval voided", "after the void", False),
])
def test_opening_approval_over_a_partly_filed_handoff(world, latest, approval_kind, refused):
  # only an approval that supersedes a partly filed, unvoided handoff refuses, before any write
  code, out = approve_over(world, latest, approval_kind)
  assert (code, "has an incomplete filing: finish /superegm:file first" in out) == ((1, True) if refused else (0, False)), out
