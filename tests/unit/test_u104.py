# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U104's tests: a foreman spec finding reaches the owner (1.3 design section 3.8).

"""U104: a `deviation (spec)` finding raised by `collect --spec` is the owner's alone, never the judges', and opens the round's
one point-1 decision at once, offering `<fid> respec` beside `finding upheld` and `finding overruled`."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import superegm as core
from conftest import REPO, set_config
from superegm import review
from test_wave import foreman_of, wave_store

ROOT = Path(__file__).resolve().parents[2]
SPEC = "deviation (spec) unruled: docs/designs/sample.md:12 says 3; `pytest -k t` fails"
HEAD = "a" * 40
LOCATIONS = {"deviation (spec)": "docs/designs/sample.md:12", "test-delta": "tests/unit/test_q.py:3", "tdd-order": "tests/unit/test_q.py"}


def finding(fid, claim, severity="high"):
  location = next((loc for prefix, loc in LOCATIONS.items() if claim.startswith(prefix)), "src/x.py:3")
  return {"id": fid, "severity": severity, "location": location, "regression": "no", "claim": claim,
          "disposition": None, "ruling": None}


def round_of(fid) -> int:
  return int(fid.split("-")[1])


def unit_world(world, open_findings, builder_contested, mode="normal", posted=False):
  """A wave card in `mode`, U01 with an opened head review whose round `n` (the round of the first fid) holds `open_findings` and
  `builder_contested`, round 1 an ordinary high foreman-1-1 when `n` is 2; U01's earlier rounds posted `revise`, round `n` collected
  with its gates run (or posted `revise` when `posted`), its dispatch `d<n>`."""
  extra = ["--mode", "leavemealone"] if mode == "leavemealone" else []
  card = world.run("runcard", "open", "--skill", "wave", "--artifact", world.spec, *extra, card=None)[1].strip()
  n = round_of(open_findings[0][0])
  s = wave_store(world, U01={"pr": 70, "head": HEAD, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"], reviewers={"spec": [], "plan": [], "head": ["change-review"], "integrate": []})
  rid = review.review_id(s, "head", "U01", 1)
  core.atomic_write(s.path("reviews", rid, "review.json"),
                    {"kind": "head", "artifact": "U01", "cycle": 1, "handoff_id": s.handoff_id, "scope": None,
                     "reviewers": ["change-review"], "cap": 5, "runcard": card, "artifact_sha256": "a" * 64,
                     "astra_incomplete": 0, "converged": "no", "converged_round": None, "rulings": []})
  for k in range(1, n + 1):
    found = [finding(fid, claim) for fid, claim in open_findings] if k == n else [finding("foreman-1-1", "the hook never fires")]
    core.atomic_write(s.path("reviews", rid, f"round-{k}.json"),
                      {"round": k, "runcard": card, "artifact_sha256": "a" * 64, "what_ran": "completed",
                       "builder_contested": [{"fid": fid, "reason": "r"} for fid in builder_contested] if k == n else [],
                       "reviewers": {"change-review": {"findings": []}, "foreman": {"findings": found}}})
  entry = lambda k: {"round": k, "runcard": card, "launch": 1, "head": HEAD, "dispatch_id": f"d{k}", "dod_runs": {}, "test_delta": []} \
      | ({"phase": "posted", "outcome": "revise", "posted_at": "2026-11-03T08:00:00Z"} if k < n or posted else {"phase": "collected"})
  core.atomic_write(s.path("foreman", "U01"), foreman_of(s, "U01") | {"dispatch_id": f"d{n}", "rounds": [entry(k) for k in range(1, n + 1)]})
  return SimpleNamespace(card=card, s=s, rid=rid, n=n)


def post_round(world, w) -> str:
  """`superegm review post` on round `n`, its review already on the pull request: the word it writes."""
  world.gh.reviews[70] = [{"id": 5, "commit_id": HEAD, "submitted_at": "2026-11-03T09:00:00Z", "body": review.header(w.n, HEAD)}]
  code, out = world.run("review", "post", "--unit", "U01", "--round", w.n, "--dispatch", f"d{w.n}", "--runcard", w.card)
  assert code == 0, out
  return next(e for e in foreman_of(w.s, "U01")["rounds"] if e["round"] == w.n)["outcome"]


def round_json(w, n=None) -> dict:
  return json.loads(w.s.path("reviews", w.rid, f"round-{n or w.n}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- S1: the owner's word


@pytest.mark.parametrize("open_findings, builder_contested, owner_fids", [
    ([("foreman-1-1", SPEC)], [], ["foreman-1-1"]),
    ([("foreman-1-1", "tdd-order: S1: no test commit"), ("foreman-1-2", SPEC)], [], ["foreman-1-2"]),
    ([("foreman-1-1", "test-delta: tests/unit/test_q.py:3 removed"), ("foreman-1-2", SPEC)], [], ["foreman-1-2", "foreman-1-1"]),
    ([("foreman-2-1", SPEC), ("foreman-2-2", "contested foreman-2-1: the code is right")], ["foreman-2-2"], ["foreman-2-1"]),
    ([("foreman-2-1", SPEC), ("foreman-2-3", "contested foreman-1-1: the test came first")], ["foreman-2-3"], ["foreman-2-1"]),
    ([("foreman-1-1", "tdd-order: S1: no test commit")], [], []),
])
def test_a_foreman_spec_finding_is_the_owners_word(world, open_findings, builder_contested, owner_fids):
  # a spec finding is owner-only, contested or not, even while the round has other blockers; `round_json` the round record
  # holding `open_findings` and `builder_contested`, `posted_outcome` the word `superegm review post` writes for it
  w = unit_world(world, open_findings, builder_contested)
  posted_outcome = post_round(world, w)
  assert review.owner_only_fids(round_json(w)) == owner_fids
  assert posted_outcome == ("owner: " + ", ".join(owner_fids) if owner_fids else "revise")
