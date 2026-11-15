# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U40's tests: review triage on a pull-request head (spec section 5.2): the eligible mediums, the triage file and its refusals, the deferral and its follow-up row, the owner's undo and its refusals.

"""U40: review triage and the blocking rule (spec section 5.2)."""

import json
import pytest
from superegm import atomic_write, sha256_file
from test_foreman import UNIT, prepared, record

PATTERNS = [{"reach": "agent"}, {"reach": "forged", "later": "easy"},
            {"critical": "no", "later": "easy", "verified": "confirmed"}]


def M(reviewer, i=1, sev="medium", reg="no", claim="a claim", n=1, loc="src/hooks.py:1"):
  """One findings line of round `n`."""
  return f"{reviewer}-{n}-{i} | {sev} | {loc} | regression: {reg} | {claim}\n"


def triage_on(world, st, patterns=PATTERNS):
  """The handoff's approval entry at the spec's bytes, with its frozen `triage` (None: triage off)."""
  atomic_write(st.path("approvals", "sample"), {"entries": [{"kind": "opening", "handoff_id": st.handoff_id, "escalated": [],
                                                             "sha256": sha256_file(world.spec.resolve()), "rounds": 5,
                                                             "triage": patterns}]})


def foreman(w):
  return json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))


def save_foreman(w, data):
  atomic_write(w.st.path("foreman", UNIT), data)


def head(world, tmp_path, monkeypatch, findings, patterns=PATTERNS, **kw):
  """Round 1 of the unit's head review, collected, its findings recorded; triage frozen as `patterns`."""
  w = prepared(world, tmp_path, monkeypatch, **kw)
  triage_on(world, w.st, patterns)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert code == 0, out
  record(world, w.st, w.rid, 1, w.head, w.child, findings)
  return w


def eligible(world, w, n=1):
  code, out = world.run("review", "triage", "--review", w.rid, "--round", n, "--eligible")
  assert code == 0, out
  return out


@pytest.mark.parametrize("case, eligible_", [
    ("panel medium", True), ("panel high", False), ("regression medium", False),
    ("test-delta: medium", False), ("medium named in an owner: line", False),
    ("external:<login> medium", False), ("medium in a unit whose triage was undone", False),
])
def test_eligible_mediums(world, tmp_path, monkeypatch, case, eligible_):
  """--eligible prints exactly the eligible fids: a panel medium, not a regression, not `test-delta:`, not named in an
  `owner:` line, not an external's, in a unit the owner has not turned triage off for by an undo."""
  fid, findings = "change-review-1-1", {"change-review": M("change-review")}
  if case == "panel high":
    findings = {"change-review": M("change-review", sev="high")}
  if case == "regression medium":
    findings = {"change-review": M("change-review", reg="yes")}
  if case == "test-delta: medium":
    fid, findings = "foreman-1-1", {"foreman": M("foreman", loc="tests/unit/test_hooks.py", claim="test-delta: an assertion went")}
  if case == "external:<login> medium":
    fid, findings = "external:alice-1-1", {"external:alice": M("external:alice")}
  w = head(world, tmp_path, monkeypatch, findings)
  if case == "medium named in an owner: line":
    data = foreman(w); data["rounds"][0]["outcome"] = f"owner: {fid}"; save_foreman(w, data)
  if case == "medium in a unit whose triage was undone":
    data = foreman(w)
    data["rulings"].append({"kind": "undo", "decision": None, "fid": "change-review-0-1", "by": "owner", "posted": "comment 77",
                            "ruling": "change-review-0-1 finding upheld", "posted_at": "2026-11-03T11:00:00Z", "at": "2026-11-03T11:00:00Z"})
    save_foreman(w, data)
  out = eligible(world, w)
  assert (fid in out.split()) == eligible_, out
  assert all(line == "change-review-1-1" for line in out.split()), out
