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


REVIEW = {"id": 13, "login": "alice", "bot": False, "body": "medium: the cap is unstated", "path": None, "line": None, "commit_id": "c" * 40, "review_body": True, "created_at": "2026-11-05T00:00:02Z"}

def test_ingest_pr_replies_fixed_once_on_each_thread_settled_fixed(world, monkeypatch):
  reader(monkeypatch, threads=THREADS + [REVIEW])
  posted = []
  def api(args, cwd, token=None):
    endpoint = world.gh.endpoint_of(args)
    if args[1:4] == ["-i", "-X", "POST"] and re.fullmatch(rf"repos/{REPO}/(pulls/7/comments/\d+/replies|issues/7/comments)", endpoint):
      posted.append((endpoint, dict(a.split("=", 1) for a in args[args.index("-F") + 1::2])["body"], token))
      return world.gh.ok(text="HTTP/2.0 201 Created\n\n" + json.dumps({"id": 90 + len(posted)}))
    return world.gh.do_api(args)
  world.gh.extend("api", api)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert ingest(world, cid)[0] == 0 and posted == []
  move(world, "spec", spec)
  for fid, disposition in ((f"{BOT}-1-1", "fixed"), (f"{HUMAN}-1-1", "declined"), (f"{HUMAN}-1-2", "fixed")):
    assert settle(world, rid, fid, disposition, cid)[0] == 0
  assert ingest(world, cid)[0] == 0 and posted == [(f"repos/{REPO}/pulls/7/comments/11/replies", f"**Reply {BOT}-1-1:** fixed", None),
                                                   (f"repos/{REPO}/issues/7/comments", f"**Reply {HUMAN}-1-2:** fixed", None)]   # the fixed threads alone, the review-body thread's reply a PR comment, under the session's own token
  findings = rjson(world, rid, "round-1.json")["reviewers"]
  assert [f.get("replied") for r in (BOT, HUMAN) for f in findings[r]["findings"]] == [91, None, 92]
  assert ingest(world, cid)[0] == 0 and len(posted) == 2


@pytest.mark.parametrize("ruled, flag, pr", [(False, "--yes", True), (True, "--yes", True), (True, "--leavemealone", True), (False, "--yes", False)])
def test_approve_spec_ingests_once_and_refuses_an_unsettled_external(world, monkeypatch, ruled, flag, pr):
  seen = reader(monkeypatch, threads=THREADS[:1])
  if pr:
    make_pr(world.gh, 7, "c" * 40, branch="main")
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [HIGH(k) for k in range(1, 6)] if ruled else [[]])
  if ruled:
    assert rule(world, rid, "accept", cid)[0] == 0
  fid = f"{BOT}-{5 if ruled else 1}-1"
  code, out = approve(world, spec, cid, flag)
  if not pr:
    assert (code, seen) == (0, []) and approval(world)["entries"][-1]["review"] == rid   # none means nothing to read
    return
  assert code == 1 and f"approve-spec: {BOT} {fid} unsettled on PR 7" in out and len(seen) == 1 and not store(world.repo).path("approvals", SLUG).exists()
  assert [c[c.index("--head") + 1] for c in world.gh.calls if c[:2] == ["pr", "list"]] == ["main"]
  assert settle(world, rid, fid, "declined", cid, "--owner")[0] == 0
  assert approve(world, spec, cid, flag)[0] == 0 and len(seen) == 2 and approval(world)["entries"][-1]["review"] == rid
  spec.write_text(spec.read_text(encoding="utf-8") + "| U02 | more | U01 | S |\n", encoding="utf-8")
  assert approve(world, spec, cid, "--amend-units")[0] == 0 and len(seen) == 2             # never under --amend-units


def test_ingest_pr_numbers_a_new_thread_after_the_findings_it_carries(world, monkeypatch):
  reader(monkeypatch)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [HIGH(k) for k in range(1, 6)])
  assert ingest(world, cid)[0] == 0 and rule(world, rid, "stop", cid)[0] == 0
  later = {**THREADS[0], "id": 14, "body": "**bug** another claim", "line": 6}
  reader(monkeypatch, threads=THREADS + [later])
  _, cid2, rid2 = opened(world)
  rounds(world, rid2, cid2, [HIGH(k) for k in range(1, 6)])
  assert ingest(world, cid2)[1].strip() == "1 ingested"
  found = rjson(world, rid2, "round-5.json")["reviewers"][BOT]["findings"]
  assert [(f["id"], f["thread"]) for f in found] == [(f"{BOT}-5-1", 11), (f"{BOT}-5-2", 14)]   # the carried id taken first, never twice in a round
  assert settle(world, rid2, f"{BOT}-5-2", "declined", cid2, "--owner")[0] == 0
  assert [f["disposition"] for f in rjson(world, rid2, "round-5.json")["reviewers"][BOT]["findings"]] == [None, "declined"]


def test_ingest_pr_skips_a_thread_recorded_before_its_ingested_write(world, monkeypatch):
  seen = reader(monkeypatch)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert ingest(world, cid)[0] == 0
  path = store(world.repo).path("reviews", rid, "review.json")
  path.write_text(json.dumps({**rjson(world, rid), "ingested": []}), encoding="utf-8")   # interrupted between the round's write and review.json's
  assert (ingest(world, cid)[1].strip(), seen[-1]) == ("0 ingested", {11, 12})
  assert rjson(world, rid)["ingested"] == [11, 12] and len(rjson(world, rid, "round-1.json")["reviewers"][BOT]["findings"]) == 1


def test_ingest_pr_records_each_reply_as_it_posts_on_the_threads_own_pr(world, monkeypatch):
  reader(monkeypatch, threads=THREADS + [REVIEW])
  posted, failing = [], {"issues/7/comments"}
  def api(args, cwd, token=None):
    endpoint = world.gh.endpoint_of(args)
    if args[1:4] == ["-i", "-X", "POST"] and re.fullmatch(rf"repos/{REPO}/(pulls/\d+/comments/\d+/replies|issues/\d+/comments)", endpoint):
      if endpoint.split(f"{REPO}/", 1)[1] in failing:
        return 1, "", "gh: Server Error (HTTP 500)"
      posted.append(endpoint)
      return world.gh.ok(text="HTTP/2.0 201 Created\n\n" + json.dumps({"id": 90 + len(posted)}))
    return world.gh.do_api(args)
  world.gh.extend("api", api)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert ingest(world, cid)[0] == 0
  move(world, "spec", spec)
  for fid in (f"{BOT}-1-1", f"{HUMAN}-1-2"):
    assert settle(world, rid, fid, "fixed", cid)[0] == 0
  code, out = ingest(world, cid)
  assert code == 0 and f"review ingest: reply {HUMAN}-1-2 not posted: " in out and "Traceback" not in out   # a failed reply is named, never a refusal
  assert posted == [f"repos/{REPO}/pulls/7/comments/11/replies"] and rjson(world, rid, "round-1.json")["reviewers"][BOT]["findings"][0]["replied"] == 91
  failing.clear()
  assert ingest(world, cid, number=8)[0] == 0   # a later PR of the spec: each reply on its own thread's PR
  assert posted == [f"repos/{REPO}/pulls/7/comments/11/replies", f"repos/{REPO}/issues/7/comments"]


def test_ingest_pr_refuses_a_failed_read_in_one_line(world, monkeypatch):
  def broken(repo, number, skip):
    raise review_mod.core.GhError(["api"], 1, "", "gh: Server Error (HTTP 502)")
  monkeypatch.setattr(review_mod, "read_threads", broken)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  code, out = ingest(world, cid)
  assert code == 1 and out.strip().startswith("review ingest: gh api: exit 1") and "Traceback" not in out


def test_approve_spec_with_no_round_reads_nothing_and_refuses_as_unconverged(world, monkeypatch):
  seen = reader(monkeypatch)
  make_pr(world.gh, 7, "c" * 40, branch="main")
  spec, cid, rid = opened(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 1 and f"approve-spec: review {rid} is not converged" in out and seen == []


def test_ingest_pr_never_reuses_an_id_an_earlier_cycle_holds(world, monkeypatch):
  reader(monkeypatch)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [HIGH(k) for k in range(1, 6)])
  assert ingest(world, cid)[0] == 0 and rule(world, rid, "stop", cid)[0] == 0          # c1 round 5 holds the bot's -5-1
  _, cid2, rid2 = opened(world)
  rounds(world, rid2, cid2, [HIGH(1)])
  assert ingest(world, cid2)[0] == 0 and settle(world, rid2, f"{BOT}-5-1", "declined", cid2, "--owner")[0] == 0   # carried, then settled: carried no more
  rounds(world, rid2, cid2, [HIGH(k) for k in range(2, 6)], start=2)
  reader(monkeypatch, threads=THREADS + [{**THREADS[0], "id": 15, "body": "**bug** a new claim", "line": 8}])
  assert ingest(world, cid2)[1].strip() == "1 ingested"
  assert [f["id"] for f in rjson(world, rid2, "round-5.json")["reviewers"][BOT]["findings"]] == [f"{BOT}-5-2"]   # never c1's -5-1 again
  assert settle(world, rid2, f"{BOT}-5-2", "declined", cid2, "--owner")[0] == 0
  assert rjson(world, rid2, "round-5.json")["reviewers"][BOT]["findings"][0]["disposition"] == "declined"


def test_ingest_pr_finds_a_reply_posted_but_never_recorded(world, monkeypatch):
  reader(monkeypatch, threads=THREADS + [REVIEW])
  posted = []
  owner_api(world, posted, reply_body="")   # posted, its answer unreadable
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert ingest(world, cid)[0] == 0
  move(world, "spec", spec)
  for fid in (f"{BOT}-1-1", f"{HUMAN}-1-2"):
    assert settle(world, rid, fid, "fixed", cid)[0] == 0
  world.gh.threads[7] = [{"id": 95, "in_reply_to_id": 11, "user": {"login": "owner"}, "body": f"**Reply {BOT}-1-1:** fixed"}]   # an earlier run's post, its id never saved
  assert ingest(world, cid)[0] == 0 and posted == [f"repos/{REPO}/issues/7/comments"]
  findings = rjson(world, rid, "round-1.json")["reviewers"]
  assert (findings[BOT]["findings"][0]["replied"], findings[HUMAN]["findings"][1]["replied"]) == (95, True)
  assert ingest(world, cid)[0] == 0 and len(posted) == 1   # never reposted, its id read or not


@pytest.mark.parametrize("broken", ["pr list", "threads"])
def test_approve_spec_refuses_a_gh_failure_in_one_line(world, monkeypatch, broken):
  seen = reader(monkeypatch)
  make_pr(world.gh, 7, "c" * 40, branch="main")
  if broken == "pr list":
    world.gh.extend("pr", lambda args, cwd, token=None: (1, "", "gh: Server Error (HTTP 502)"))
  else:
    def failing(repo, number, skip):
      raise review_mod.core.GhError(["api"], 1, "", "gh: Server Error (HTTP 502)")
    monkeypatch.setattr(review_mod, "read_threads", failing)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  code, out = approve(world, spec, cid, "--yes")
  assert code == 1 and out.strip().startswith("superegm: approve-spec: gh ") and len(out.strip().splitlines()) == 1 and "Traceback" not in out
  assert not store(world.repo).path("approvals", SLUG).exists() and seen == []


def test_approve_spec_refuses_a_missing_config_before_any_github_call(world, monkeypatch):
  from superegm import approve_spec
  reader(monkeypatch)
  make_pr(world.gh, 7, "c" * 40, branch="main")
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  monkeypatch.setattr(approve_spec, "CONFIG", ".superegm/absent.json")
  code, out = approve(world, spec, cid, "--yes")
  assert (code, out.strip()) == (1, "superegm: approve-spec: .superegm/absent.json missing: run superegm init")
  assert not [c for c in world.gh.calls if c[:2] == ["pr", "list"]]


def test_spec_cycles_are_found_beside_a_handoff_directory(world):
  spec, cid, rid = opened(world)
  st = store(world.repo)
  handoff = review_mod.core.Store(st.root, handoff_id="2026-11-03-other-abcdef", config=st.config)   # an explicit --handoff
  assert review_mod.cycle_ids(handoff, "spec", str(spec)) == [rid] and review_mod.latest_cycle(handoff, "spec", str(spec))[0]["cycle"] == 1


def test_a_carried_external_escalated_is_one_pair(world, monkeypatch):
  reader(monkeypatch, threads=THREADS[:1])
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [HIGH(k) for k in range(1, 6)])
  assert ingest(world, cid)[0] == 0 and rule(world, rid, "stop", cid)[0] == 0
  _, cid2, rid2 = opened(world)
  rounds(world, rid2, cid2, [[]])
  assert ingest(world, cid2)[0] == 0 and settle(world, rid2, f"{BOT}-5-1", "escalated", cid2)[0] == 0   # both copies escalated
  code, out = approve(world, spec, cid2, "--yes")
  assert code == 0 and f"approve-spec: 1 escalated finding(s) await the owner: {rid2}:{BOT}-5-1" in out
  assert approval(world)["entries"][-1]["escalated"] == [f"{rid2}:{BOT}-5-1"]


def owner_api(world, posted, reply_body="{}", broken=None):
  """The fake `gh api` with the session's own login, `owner`, a recorded POST, and a failing PR-comments read while `broken`."""
  def api(args, cwd, token=None):
    endpoint = world.gh.endpoint_of(args)
    if endpoint == "user":
      return world.gh.ok({"login": "owner"})
    if args[1:4] == ["-i", "-X", "POST"]:
      posted.append(endpoint)
      return world.gh.ok(text="HTTP/2.0 201 Created\n\n" + (json.dumps({"id": 90 + len(posted)}) if reply_body is None else reply_body))
    if broken and broken["read"] and endpoint == f"repos/{REPO}/pulls/7/comments":
      return 1, "", "gh: Server Error (HTTP 502)"
    return world.gh.do_api(args)
  world.gh.extend("api", api)


def test_reply_reconcile_takes_only_the_sessions_own_reply_where_it_belongs(world, monkeypatch):
  reader(monkeypatch, threads=THREADS + [REVIEW])
  posted, broken = [], {"read": True}
  owner_api(world, posted, reply_body=None, broken=broken)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert ingest(world, cid)[0] == 0
  move(world, "spec", spec)
  for fid in (f"{BOT}-1-1", f"{HUMAN}-1-2"):
    assert settle(world, rid, fid, "fixed", cid)[0] == 0
  code, out = ingest(world, cid)   # the PR's comments unreadable: named, nothing posted, retried next run
  assert code == 0 and f"review ingest: reply {BOT}-1-1 not posted: " in out and posted == []
  broken["read"] = False
  world.gh.threads[7] = [{"id": 96, "in_reply_to_id": 11, "user": {"login": "mallory"}, "body": f"**Reply {BOT}-1-1:** fixed"},   # another participant's
                         {"id": 97, "in_reply_to_id": 11, "user": {"login": "owner"}, "body": f"**Reply {HUMAN}-1-2:** fixed"}]  # inline: not the review body's
  assert ingest(world, cid)[0] == 0 and posted == [f"repos/{REPO}/pulls/7/comments/11/replies", f"repos/{REPO}/issues/7/comments"]
  findings = rjson(world, rid, "round-1.json")["reviewers"]
  assert (findings[BOT]["findings"][0]["replied"], findings[HUMAN]["findings"][1]["replied"]) == (91, 92)


def test_reply_reconcile_finds_a_review_body_reply_posted_as_a_pr_comment(world, monkeypatch):
  reader(monkeypatch, threads=THREADS + [REVIEW])
  posted = []
  owner_api(world, posted)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert ingest(world, cid)[0] == 0
  move(world, "spec", spec)
  assert settle(world, rid, f"{HUMAN}-1-2", "fixed", cid)[0] == 0
  world.gh.comments[7] = [{"id": 98, "user": {"login": "owner"}, "body": f"**Reply {HUMAN}-1-2:** fixed"}]   # an earlier run's, its id never saved
  assert ingest(world, cid)[0] == 0 and posted == []
  assert rjson(world, rid, "round-1.json")["reviewers"][HUMAN]["findings"][1]["replied"] == 98


def test_approve_spec_names_the_pr_a_carried_finding_came_from(world, monkeypatch):
  reader(monkeypatch, threads=THREADS[:1])
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [HIGH(k) for k in range(1, 6)])
  assert ingest(world, cid)[0] == 0 and rule(world, rid, "stop", cid)[0] == 0          # PR 7's thread, unsettled
  make_pr(world.gh, 8, "c" * 40, branch="main")                                          # the branch's PR now
  _, cid2, rid2 = opened(world)
  rounds(world, rid2, cid2, [[]])
  code, out = approve(world, spec, cid2, "--yes")
  assert code == 1 and f"approve-spec: {BOT} {BOT}-5-1 unsettled on PR 7" in out


def test_step_4_sends_a_fixed_settle_to_review_status():
  from pathlib import Path
  body = (Path(__file__).resolve().parents[2] / "skills" / "review-spec" / "SKILL.md").read_text(encoding="utf-8")
  assert "`fixed` edits the spec, so run `superegm review status` and act on its exit code (3: back to step 3, the next round; 2: step 5)" in body
