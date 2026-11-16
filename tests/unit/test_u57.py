# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U57

"""U57: proceed, the owner's go-ahead (`review rule --ruling proceed --owner`, spec section 4.2): its refusals, its
records, the convergence it gives ahead of every other test, and its readers downstream."""

import json
import pytest

from conftest import ROOT, set_config
from superegm import atomic_write
from test_wave import open_wave_card, wave_store, fake_gh, foreman_of, head_review
from test_u43 import registry  # noqa: F401 -- autouse: HOME under tmp_path, so `next` never reads the owner's registry

REPO, OWNER = "example-org/webhooks", "owner"
UPDATED = "2026-11-10T09:00:00Z"


def issue_of(s, uid):
  return json.loads(s.path("state").read_text(encoding="utf-8"))["units"][uid]["number"]


def comment(s, n, body, uid="U01", author=OWNER, updated=UPDATED):
  """Comment `n` as `gh api repos/<repo>/issues/comments/<n>` serves it, on `uid`'s issue."""
  return {"id": n, "user": {"login": author}, "body": body + "\n", "updated_at": updated,
          "issue_url": f"https://api.github.com/repos/{REPO}/issues/{issue_of(s, uid)}"}


def head_world(world):
  """U01 and U02 filed, each with a pull request; U01's head review opened and its round 1 posted with one medium;
  `config.owners` names `owner`. The store, the wave card and the review id."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}]},
                 U02={"pr": 71, "head": "b" * 40, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}]})
  rid = head_review(world, s, card)
  set_config(world, repo=REPO, owners=[OWNER])
  return s, card, rid


def serve(world, *comments):
  fake_gh(world, {f"repos/{REPO}/issues/comments/{c['id']}": c for c in comments})


def proceed(world, rid, card, *extra):
  return world.run("review", "rule", "--review", rid, "--ruling", "proceed", *extra, "--runcard", card)


def snapshot(s, rid, *units):
  paths = [s.path("reviews", rid, "review.json"), s.path("journal")] + [s.path("foreman", u) for u in units]
  return [p.read_bytes() if p.exists() else None for p in paths]


# ---------------------------------------------------------------- S1: the refusals


@pytest.mark.parametrize("case, message", [
  ("--judges", "review rule: proceed is the owner's"),
  ("posted by a non-owner", "review rule: comment 901 is by passer-by, not a login in config.owners"),
  ("posted comment not of the proceed form", "review rule: comment 901 does not rule proceed"),
  ("posted on another unit's issue", "review rule: comment 901 is not on issue #"),
  ("head of a stopped unit", "review rule: U01 is stopped"),
  ("comment another entry names", "review rule: comment 901 already ruled"),
  ("same comment and review, the unit's moved head", "review rule: comment 901 already ruled"),
])
def test_proceed_refusals(world, case, message):
  s, card, rid = head_world(world)
  body = "**Ruling:** proceed — ship it"
  served = {"posted by a non-owner": comment(s, 901, body, author="passer-by"),
            "posted comment not of the proceed form": comment(s, 901, "**Ruling:** stop"),
            "posted on another unit's issue": comment(s, 901, body, uid="U02")}.get(case, comment(s, 901, body))
  serve(world, served)
  by = ("--owner", "--posted", "901")
  if case == "--judges":
    by = ("--judges", "j1", "--reason", "ship it")
  elif case == "head of a stopped unit":
    f = foreman_of(s, "U01")
    f["stopped"] = {"by": OWNER, "reason": "stop the unit", "at": UPDATED}
    atomic_write(s.path("foreman", "U01"), f)
  elif case == "comment another entry names":
    f = foreman_of(s, "U02")
    f["proceeds"] = [{"ruling": "R1", "review": "other-head-U02-c1", "posted": "comment 901", "posted_at": UPDATED,
                      "issue": issue_of(s, "U02"), "head": "b" * 40, "launch": 1, "by": OWNER, "reason": "ship it"}]
    atomic_write(s.path("foreman", "U02"), f)
  elif case == "same comment and review, the unit's moved head":
    f = foreman_of(s, "U01")
    f["proceeds"] = [{"ruling": "R1", "review": rid, "posted": "comment 901", "posted_at": UPDATED,
                      "issue": issue_of(s, "U01"), "head": "c" * 40, "launch": 1, "by": OWNER, "reason": "ship it"}]
    atomic_write(s.path("foreman", "U01"), f)
  before = snapshot(s, rid, "U01", "U02")
  code, out = proceed(world, rid, card, *by)
  assert code == 1 and message in out, out
  assert snapshot(s, rid, "U01", "U02") == before


# ---------------------------------------------------------------- S2: a head's proceed is recorded


def launches(s, uid, *rounds):
  atomic_write(s.path("launches", uid), {"launches": [{"round": n, "status": "exited 0"} for n in rounds]})


def test_proceed_records_the_head(world):
  s, card, rid = head_world(world)
  launches(s, "U01", 1, 2)
  serve(world, comment(s, 901, "**Ruling:** proceed — the medium is accepted risk"),
        comment(s, 902, "**Ruling:** proceed — again, after the merge round", updated="2026-11-11T09:00:00Z"))
  rulings_before = foreman_of(s, "U01")["rulings"]
  code, out = proceed(world, rid, card, "--owner", "--posted", "901")
  assert code == 0, out
  entry = {"ruling": "R1", "review": rid, "posted": "comment 901", "posted_at": UPDATED, "issue": issue_of(s, "U01"),
           "head": "a" * 40, "launch": 2, "by": OWNER, "reason": "the medium is accepted risk"}
  assert foreman_of(s, "U01")["proceeds"] == [entry]
  ruling = json.loads(s.path("reviews", rid, "review.json").read_text(encoding="utf-8"))["rulings"][-1]
  assert {k: ruling[k] for k in ("id", "ruling", "by", "reason", "sha256")} == {
    "id": "R1", "ruling": "proceed", "by": "owner", "reason": "the medium is accepted risk", "sha256": "a" * 40}
  # the same comment, review and head again: the recorded entry, nothing written
  before = snapshot(s, rid, "U01")
  code, out = proceed(world, rid, card, "--owner", "--posted", "901")
  assert code == 0 and json.loads(out) == entry, out
  assert snapshot(s, rid, "U01") == before
  # a newer launch, then a second proceed on a new comment
  launches(s, "U01", 1, 2, 3)
  code, out = proceed(world, rid, card, "--owner", "--posted", "902")
  assert code == 0, out
  proceeds = foreman_of(s, "U01")["proceeds"]
  assert len(proceeds) == 2 and proceeds[-1]["launch"] == 3 and proceeds[-1]["ruling"] == "R2", proceeds
  assert proceeds[-1]["posted_at"] == "2026-11-11T09:00:00Z"
  # a typed head proceed on another unit: no comment, by the owner
  code, out = world.run("review", "open", "--kind", "head", "--artifact", "U02", "--reviewers", "change-review",
                        "--runcard", card)
  assert code == 0, out
  rid2 = out.strip()
  u02_rulings = foreman_of(s, "U02")["rulings"]
  code, out = proceed(world, rid2, card, "--owner", "--reason", "typed in session")
  assert code == 0, out
  assert foreman_of(s, "U02")["proceeds"] == [
    {"ruling": "R1", "review": rid2, "posted": None, "posted_at": None, "issue": issue_of(s, "U02"),
     "head": "b" * 40, "launch": 1, "by": "owner", "reason": "typed in session"}]
  assert foreman_of(s, "U01")["rulings"] == rulings_before and foreman_of(s, "U02")["rulings"] == u02_rulings
  rulings_md = (ROOT / "skills" / "wave" / "references" / "rulings.md").read_text(encoding="utf-8")
  assert "review rule --ruling proceed --owner --posted <cid>" in rulings_md


# ---------------------------------------------------------------- S3: a proceed converges first


def head_at_the_cap(world):
  """test_foreman's unit U01: round 1 posted at the repository's HEAD with two unsettled mediums, the cap at 1, and a
  cap decision naming the review open. (store, card, review id, first reviewer, head)."""
  import subprocess
  import test_foreman as tf
  head = subprocess.run(["git", "-C", str(world.repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                        text=True).stdout.strip()
  st, card, _ = tf.seed(world, head=head, rounds=[{**tf.POSTED_R1, "head": head, "outcome": "revise"}], owners=[OWNER])
  lines = "".join(f"change-review-1-{i} | medium | src/hooks.py:{i} | regression: no | claim {i}\n" for i in (1, 2))
  rid = tf.open_head_review(world, st, card, head, {"change-review": lines})
  tf.cap_at_one(st, rid)
  q = world.artifacts.parent / "cap.md"
  q.write_text("the cap is reached\n", encoding="utf-8")
  code, out = world.run("decision", "open", "--unit", "U01", "--point", "2", "--question", str(q),
                        "--source", f"review {rid} cap", "--runcard", card)
  assert code == 0, out
  return st, card, rid, "change-review", head


def spec_moved(world, monkeypatch):
  """A spec cycle's round 1 clean for its panel, the PR's two threads ingested (a high, a low), the spec then edited."""
  from test_review import opened, rounds, hstore, move
  from test_u26 import reader, ingest
  reader(monkeypatch)
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert ingest(world, cid)[0] == 0
  move(world, "spec", spec)
  return hstore(world), cid, rid, "design", None


def plan_review(world, case):
  """U07's plan cycle under `readiness,set`: round 1's readiness findings by the case; a fix-design settled, or two
  rounds with readiness missing after it (the stall)."""
  from test_review import opened, record, settle, hstore, F
  _, cid, rid = opened(world, "plan", reviewers="readiness,set")
  sevs = {"below the cap, a high open": ["high", "medium", "low"], "a fix-design finding": ["high", "medium"],
          "stalled": ["high", "high", "medium", "low"]}[case]
  assert record(world, rid, 1, "readiness", [F("readiness", 1, i, s) for i, s in enumerate(sevs, 1)], cid)[0] == 0
  assert record(world, rid, 1, "set", [], cid)[0] == 0
  if case == "a fix-design finding":
    assert settle(world, rid, "readiness-1-1", "fix-design", cid, "--owner")[0] == 0
  if case == "stalled":
    for n in (2, 3):
      assert record(world, rid, n, "set", [], cid)[0] == 0
  return hstore(world), cid, rid, "readiness", None


def round_zero(world):
  """test_file's planned handoff (U01, U02): U01's plan cycle opened, no round recorded."""
  from test_file import planned, open_card, hp
  from superegm import store
  spec, plan, handoff_id = planned(world)
  cid = open_card(world, "review-plan", str(spec))
  code, out = world.run("review", "open", "--kind", "plan", "--artifact", "U01", "--reviewers", "readiness",
                        "--runcard", cid)
  assert code == 0, out
  hp(world, "state")
  return store(world.repo), cid, out.splitlines()[0], "readiness", spec


def findings(st, rid):
  return [f for p in sorted(st.path("reviews", rid).glob("round-*.json"))
          for r in json.loads(p.read_text(encoding="utf-8"))["reviewers"].values() for f in r["findings"]]


def verdict(st, rid):
  return json.loads(st.path("reviews", rid, "review.json").read_text(encoding="utf-8"))["converged"]


@pytest.mark.parametrize("case, kind, k, h", [
  ("below the cap, a high open", "plan", 3, 1), ("head at the cap", "head", 2, 0),
  ("a fix-design finding", "plan", 1, 0), ("bytes moved after the last round", "spec", 2, 1),
  ("round 0", "plan", 0, 0), ("stalled", "plan", 4, 2),
])
def test_proceed_converges_first(world, monkeypatch, case, kind, k, h):
  from superegm import review as review_mod
  if kind == "head":
    st, cid, rid, first, head = head_at_the_cap(world)
  elif kind == "spec":
    st, cid, rid, first, head = spec_moved(world, monkeypatch)
  elif case == "round 0":
    st, cid, rid, first, spec = round_zero(world)
  else:
    st, cid, rid, first, head = plan_review(world, case)
  run_status = lambda: world.run("review", "status", "--review", rid, "--runcard", cid)
  before = run_status()[0]
  assert before != 0 or case == "round 0", before
  open_before = {f["id"] for f in findings(st, rid) if f["disposition"] is None}
  assert len(open_before) == k
  code, out = proceed(world, rid, cid, "--owner", "--reason", "accepted risk")
  assert code == 0, out
  assert verdict(st, rid) == "by proceed R1"
  assert run_status()[0] == 0
  assert f"review {rid} proceeded by the owner: {k} findings accepted ({h} high)" in st.path("journal").read_text(encoding="utf-8")
  for f in findings(st, rid):
    if f["id"] in open_before:
      assert (f["disposition"], f.get("by"), f["ruling"]) == ("declined", "owner", "R1"), f
  if kind == "head":
    data = foreman_of(st, "U01")
    assert [r for r in data["rulings"] if r.get("ruling") == "proceed"] == [
      {"decision": "q1", "ruling": "proceed", "by": "owner", "reason": "accepted risk", "review": "R1"}]
    assert review_mod.open_decisions(st, "U01") == []
    assert data["rounds"][0]["outcome"] == "clean"  # the clean outcome, as an accept writes it
  # a later settle and an ingest keep the verdict
  if open_before:
    fid = sorted(open_before)[0]
    code, out = world.run("review", "settle", "--review", rid, "--finding", fid, "--disposition", "declined",
                          "--owner", "--runcard", cid)
    assert code == 0, out
    assert verdict(st, rid) == "by proceed R1"
  if kind == "spec":
    from test_u26 import ingest
    assert ingest(world, cid)[0] == 0 and verdict(st, rid) == "by proceed R1"
  # a reviewer round's record is refused
  path = world.artifacts.parent / "next.findings"
  path.write_text("", encoding="utf-8")
  latest = max(review_mod.round_numbers(st, rid), default=0)
  code, out = world.run("review", "record", "--review", rid, "--round", str(latest + 1), "--reviewer", first,
                        "--findings", str(path), "--isolation", "clean", "--model", "m:m", "--effort", "e:e",
                        "--runcard", cid, *(["--sha256", head] if kind == "head" else []))
  assert code == 1 and f"review {rid} proceeded by R1" in out, out
  if case == "round 0":
    from test_file import converge, open_card
    converge(world, "U02")
    code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", open_card(world, "file", str(spec)))
    assert code == 0, out
  if kind == "head":
    import test_foreman as tf
    monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")  # the fake `gh` answers the builder's login
    atomic_write(st.path("review", "U01", f"pr{tf.PR}") / "r1/ci.json", json.dumps({"verdict": "ci green"}))
    world.gh.threads[tf.PR] = [{"id": 1, "user": {"login": "alice"}, "body": "bug: the hook never fires",
                                "path": "src/hooks.py", "line": 3, "commit_id": head, "created_at": "t"}]
    world.gh.roles.update({"alice": {"role_name": "write"}})
    code, out = world.run("review", "ingest", "--unit", "U01", "--runcard", cid)
    assert code == 0 and out.split()[:2] == ["1", "ingested"], out
    assert foreman_of(st, "U01")["ingested"] == [1] and verdict(st, rid) == "by proceed R1"
    assert any(f["id"].startswith("external:alice-1-") for f in findings(st, rid))
    files = lambda: [p.read_bytes() for p in sorted(st.path("reviews", rid).glob("*.json"))] + [st.path("foreman", "U01").read_bytes()]
    kept = files()
    code, out = world.run("review", "ingest", "--unit", "U01", "--runcard", cid)
    assert code == 0 and out.split()[:2] == ["0", "ingested"] and files() == kept, out


# ---------------------------------------------------------------- S4: a proceed is honoured downstream


def honoured_spec(world, monkeypatch):
  """approve-spec on a proceeded spec cycle: an unsettled external finding no refusal, the pinned bytes the test."""
  from conftest import make_pr
  from test_review import opened, rounds, approve, move, hstore, card
  from test_u26 import reader, ingest, THREADS
  reader(monkeypatch, threads=THREADS[:1])
  make_pr(world.gh, 7, "c" * 40, branch="main")
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[]])
  assert ingest(world, cid)[0] == 0
  code, out = proceed(world, rid, cid, "--owner", "--reason", "ship it")
  assert code == 0, out
  # approve-spec's own ingest now reads a new high thread: unsettled on the proceeded cycle
  reader(monkeypatch, threads=[THREADS[0], {**THREADS[0], "id": 13, "body": "**bug** the stall is unstated",
                                            "created_at": "2026-11-05T00:00:02Z"}])
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  move(world, "spec", spec)
  cid2 = card(world, spec)
  code, out = approve(world, spec, cid2, "--yes")
  assert code == 1 and "approve-spec: spec bytes differ from the converged round's" in out, out
  code, out = proceed(world, rid, cid2, "--owner", "--reason", "ship the edit")
  assert code == 0, out
  assert verdict(hstore(world), rid) == "by proceed R2"
  code, out = approve(world, spec, cid2, "--yes")
  assert code == 0, out


def honoured_plan(world):
  """U03's plan cycle proceeded at round 0: converged for the gate and for `review-plan due`."""
  from test_file import planned, open_card, converge, hp
  from superegm import gate, review_plan, store
  spec, _, _ = planned(world, ("U01", "U02", "U03"))
  cid = open_card(world, "review-plan", str(spec))
  code, out = world.run("review", "open", "--kind", "plan", "--artifact", "U03", "--reviewers", "readiness",
                        "--runcard", cid)
  assert code == 0, out
  rid = out.splitlines()[0]
  code, out = proceed(world, rid, cid, "--owner", "--reason", "planned enough")
  assert code == 0, out
  pinned = json.loads(hp(world, "units").read_text(encoding="utf-8"))["units"]["U03"]["body_sha256"]
  st = store(world.repo)
  assert gate.converged_review(st, "U03") == (True, pinned)
  assert [r for r in review_plan.due_rows(st, cid) if r[0] == "U03"] == [("U03", "converged", rid, "-", pinned)]
  for uid in ("U01", "U02"):
    converge(world, uid)
  code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", open_card(world, "file", str(spec)))
  assert code == 0, out


def honoured_next(world):
  """A plan review stopped, then proceeded: `next` passes the stopped row and the review row to `file`."""
  from test_u43 import Chain, SHA
  c = Chain(world)
  c.all_filed()
  c.state["units"].pop("U02")
  c.review("U02", converged="by proceed R2", rulings=[
    {"id": "R1", "ruling": "stop", "by": "owner", "at": "2026-11-15T00:00:00Z"},
    {"id": "R2", "ruling": "proceed", "by": "owner", "at": "2026-11-15T01:00:00Z", "reason": "r", "sha256": SHA["U02"]}])
  path = c.hs.path("reviews", "plan-U02-c1", "review.json")  # `evaluate` stores a proceed at the latest round
  path.write_text(json.dumps({**json.loads(path.read_text(encoding="utf-8")), "converged_round": 1}), encoding="utf-8")
  c.save()
  code, out, _, _ = c.next()
  assert (code, out) == (0, "file")


@pytest.mark.parametrize("part", ["spec", "plan", "next"])
def test_proceed_is_honoured_downstream(world, monkeypatch, part):
  if part == "spec":
    honoured_spec(world, monkeypatch)
  elif part == "plan":
    honoured_plan(world)
  else:
    honoured_next(world)
