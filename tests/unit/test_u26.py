# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U26's keys

"""U26: external review on the elephant's own PR (`review ingest --pr`, `approve-spec`'s ingest and refusal)."""

import json, re
import pytest
from superegm import store
from superegm import review as review_mod
from conftest import REPO, make_pr
from test_review import opened, rounds, rule, rjson, status, settle, approve, approval, move, HIGH, SLUG

BOT, HUMAN = "external:devin-ai-integration[bot]", "external:alice"
THREADS = [{"id": 11, "login": "devin-ai-integration[bot]", "bot": True, "body": "**bug** the cap is unstated", "path": "docs/specs/x.md", "line": 4, "commit_id": "c" * 40, "review_body": False, "created_at": "2026-11-05T00:00:00Z"},
           {"id": 12, "login": "alice", "bot": False, "body": "low: a typo | here", "path": "docs/specs/x.md", "line": 2, "commit_id": "c" * 40, "review_body": False, "created_at": "2026-11-05T00:00:01Z"}]

def reader(monkeypatch, threads=THREADS, role="write"):
  seen = []
  monkeypatch.setattr(review_mod, "read_threads", lambda repo, number, skip: seen.append(set(skip)) or [t for t in threads if t["id"] not in skip])
  monkeypatch.setattr(review_mod, "collaborator_role", lambda repo, login: role)
  return seen

def ingest(world, cid, number=7):
  return world.run("review", "ingest", "--pr", str(number), "--runcard", cid)

@pytest.mark.parametrize("state, n", [("open", 1), ("accept", 5), ("no round", None)])
def test_ingest_pr_records_threads_into_the_latest_round(world, monkeypatch, state, n):
  seen = reader(monkeypatch)
  spec, cid, rid = opened(world)
  if n:
    rounds(world, rid, cid, [[]] if n == 1 else [HIGH(k) for k in range(1, 6)])
  if state == "accept":
    assert rule(world, rid, "accept", cid)[0] == 0
  code, out = ingest(world, cid)
  if n is None:
    assert (code, out.strip(), seen) == (1, f"review ingest: {rid} has no round", [])
    return
  assert (code, out.strip(), seen) == (0, "2 ingested", [set()])
  records = rjson(world, rid, f"round-{n}.json")["reviewers"]
  assert [(f["id"], f["severity"], f["thread"], f["disposition"]) for r in (BOT, HUMAN) for f in records[r]["findings"]] == [(f"{BOT}-{n}-1", "high", 11, None), (f"{HUMAN}-{n}-1", "low", 12, None)]
  assert rjson(world, rid)["ingested"] == [11, 12] and rjson(world, rid)["converged"] == ("by ruling R1" if state == "accept" else "no")
  assert (ingest(world, cid)[1].strip(), seen[-1]) == ("0 ingested", {11, 12})   # every cycle's ids are the reader's skip
  assert status(world, rid, cid)[0] == (0 if state == "accept" else 3)

def test_ingest_pr_carries_an_unsettled_external_forward_and_settles_both(world, monkeypatch):
  reader(monkeypatch)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [HIGH(k) for k in range(1, 6)])
  assert ingest(world, cid)[0] == 0 and rule(world, rid, "stop", cid)[0] == 0        # c1 holds the bot's high and alice's low, then stops at its cap
  _, cid2, rid2 = opened(world)
  rounds(world, rid2, cid2, [[]])
  assert ingest(world, cid2)[1].strip() == "0 ingested"
  fid, carried = f"{BOT}-5-1", rjson(world, rid2, "round-1.json")["reviewers"]
  assert [(f["id"], f["thread"]) for f in carried[BOT]["findings"]] == [(fid, 11)] and HUMAN not in carried   # a low is not carried
  assert status(world, rid2, cid2)[0] == 3
  assert settle(world, rid2, fid, "declined", cid2, "--owner")[0] == 0
  both = [f for r in (rjson(world, rid, "round-5.json"), rjson(world, rid2, "round-1.json")) for f in r["reviewers"][BOT]["findings"]]
  assert [(f["disposition"], f["ruling"]) for f in both] == [("declined", "owner")] * 2
  assert status(world, rid2, cid2)[0] == 0 and ingest(world, cid2)[0] == 0
  assert len(rjson(world, rid2, "round-1.json")["reviewers"][BOT]["findings"]) == 1      # settled: carried no more, never twice
