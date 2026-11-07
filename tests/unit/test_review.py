# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03); the review loop and approve-spec (U04).

"""U04: the review loop (`review open|record|settle|status|rule`) and `approve-spec` (spec section 8)."""

import argparse, hashlib, json, re, shutil, subprocess
from pathlib import Path
import pytest
import superegm
from superegm import store, atomic_write, sha256_text, handoffs
from superegm.review import parse_findings
from superegm.review import derive_what_ran
from superegm.review import PANEL_OF
from superegm.review import scope_sections
from superegm.review import findings_of

from conftest import REPO, set_config


# ---------------------------------------------------------------- S1: the findings line

GOOD = "design-2-1 | high | §3 line 40 | regression: yes | the cap is unstated"

@pytest.mark.parametrize("line,error", [
  (GOOD, None),
  ("design-2-2 | low | §1 | regression: no | a nit", None),
  ("design-2-1 | high | §3 | the cap is unstated", "expected 5 fields"),
  ("zoom-out-2-1 | high | §3 | regression: no | x", "id must be design-2-<n>"),
  ("design-1-1 | high | §3 | regression: no | x", "id must be design-2-<n>"),
  ("design-2-1 | blocker | §3 | regression: no | x", "severity must be high|medium|low"),
  ("design-2-1 | high | §3 | regression: maybe | x", "regression must be yes|no"),
])
def test_findings_line_grammar(line, error):
  if error is None:
    [f] = parse_findings(line + "\n\n", "design", 2)
    assert f["id"].startswith("design-2-") and f["severity"] in {"high", "low"} and f["regression"] in {"yes", "no"}
    assert f["claim"] and f["location"] and f["disposition"] is None and f["ruling"] is None
  else:
    with pytest.raises(ValueError, match=rf"^1: {re.escape(error)}$"):
      parse_findings(line + "\n", "design", 2)
  assert parse_findings("\n  \n", "design", 1) == []
  assert parse_findings("set-2-1 | high | U07 Interfaces | regression: no | x\n", "set", 1)[0]["id"] == "set-2-1"   # a set id carries the set's own round


# ---------------------------------------------------------------- S2: the shared fixtures and `review open`

ROOT = Path(__file__).resolve().parents[2]


def test_repo_config_panels_start_with_panel_of():
  """I-3: every panel in the repository's own config opens with the spec's fixed reviewers, so a
  dispatch of each (`proportion` on plan) records on the panel."""
  reviewers = json.loads((ROOT / ".superegm/config.json").read_text(encoding="utf-8"))["reviewers"]
  for kind, panel in PANEL_OF.items():
    assert reviewers[kind][:len(panel.split(","))] == panel.split(","), kind
SPEC = ("# Sample\n\n## 1. Intent\n\nText.\n\n## 2. Units\n\n| Unit | Scope | Blocked by | Size |\n"
        "| --- | --- | --- | --- |\n| U01 | a thing | — | S |\n")
SLUG, HID, A = "2026-11-03-sample-design", "sample-abc123", "a" * 64
BODY = f"<!-- superegm:handoff={HID} unit=U07 spec={'f' * 64} -->\n# U07 — Title\n"
SKILL_OF = {"spec": "review-spec", "integrate": "integrate", "plan": "review-plan", "head": "wave"}

def git(world, *args):
  return subprocess.run(["git", "-C", str(world.repo), *args], check=True, capture_output=True, text=True).stdout.strip()

def spec_file(world, text=SPEC):
  path = world.repo / "docs" / "specs" / f"{SLUG}.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")
  return path.resolve()

def hstore(world):
  """The store as a `--spec <the sample spec>` subcommand resolves it: the spec's latest approval's handoff;
  before any approval, none (a seeded flat `state.json` makes it a legacy store)."""
  superegm.CURRENT_ARGS = argparse.Namespace(design=str(world.repo / "docs" / "specs" / f"{SLUG}.md"))
  return store(world.repo)

def seed_handoff(world, spec, hid=HID, **extra):
  """state.json as approve-spec and graph leave it: the handoff id and the spec the plan and head cards are on;
  in the spec's latest approval's handoff (its id) once one exists, else flat under `hid`."""
  st = hstore(world)
  hid = (st.handoff_id or hid) if hid else None
  state = {"units": {"U07": {}}, "design": {"path": str(spec)}, **extra}
  atomic_write(st.path("state"), state | ({"handoff_id": hid} if hid else {}))
  if hid:
    seed_body(world, "U07")

def seed_body(world, uid, text=BODY):
  """`unit_<id>.md` as `graph`'s `unit_file_text` writes it: the section, then the body in its fence."""
  atomic_write(hstore(world).path("unit", uid), f"### {uid}: Title\n\n## Issue body as posted\n\n````markdown\n{text}````\n")

def card(world, artifact, skill="review-spec", mode=None, parent=None, handoff=None):
  argv = ["runcard", "open", "--skill", skill, "--artifact", str(artifact)]
  argv += ["--mode", mode] if mode else []
  argv += ["--parent", parent] if parent else []
  argv += ["--handoff", handoff] if handoff else []
  code, out = world.run(*argv)
  assert code == 0, out
  return out.strip()

def opened(world, kind="spec", reviewers=None, astra="off", mode=None, text=SPEC):
  spec = spec_file(world, text)
  if kind in ("plan", "head"):
    seed_handoff(world, spec)
  cid = card(world, spec, SKILL_OF[kind], mode)
  artifact = str(spec) if kind in ("spec", "integrate") else "U07"
  code, out = world.run("review", "open", "--kind", kind, "--artifact", artifact, "--reviewers",
                        reviewers or PANEL_OF[kind], *(["--astra", astra] if astra is not None else []), "--runcard", cid)
  assert code == 0, out
  return spec, cid, out.strip()

def rpath(world, rid, *parts):
  return hstore(world).path("reviews", rid, *parts)

def rjson(world, rid, name="review.json"):
  return json.loads(rpath(world, rid, name).read_text(encoding="utf-8"))

def F(reviewer, n, i, sev="high", reg="no", loc="§1"):
  return f"{reviewer}-{n}-{i} | {sev} | {loc} | regression: {reg} | claim {i}"

HIGH = lambda n: [F("design", n, 1)]

def record(world, rid, n, reviewer, lines=(), cid=None, sha=None, not_run=None):
  argv = ["review", "record", "--review", rid, "--round", str(n), "--reviewer", reviewer, "--runcard", cid]
  if not_run:
    argv += ["--not-run", not_run]
  else:
    path = world.repo.parent / f"{rid}-{n}-{reviewer}.txt"
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    argv += ["--findings", str(path), "--isolation", "clean", "--model", "inherit:opus", "--effort", "inherit:high"]
  return world.run(*argv, *(["--sha256", sha] if sha else []))

def rounds(world, rid, cid, per_round, start=1):
  """One spec round per item: design's lines (None = design never recorded); zoom-out always empty."""
  for n, lines in enumerate(per_round, start):
    if lines is not None:
      assert record(world, rid, n, "design", lines, cid)[0] == 0
    assert record(world, rid, n, "zoom-out", [], cid)[0] == 0

def head_round(world, n, phase, cid, outcome=None, unit="U07"):
  path = hstore(world).path("foreman", unit)
  data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"rounds": [], "decisions": [], "rulings": []}
  data["rounds"].append({"round": n, "runcard": cid, "launch": 1, "head": "f" * 40, "phase": phase,
                         "dispatch_id": f"d{n}", "outcome": outcome, "posted_at": None})
  atomic_write(path, data)

def status(world, rid, cid):
  return world.run("review", "status", "--review", rid, "--runcard", cid)

def settle(world, rid, fid, disposition, cid, *extra):
  return world.run("review", "settle", "--review", rid, "--finding", fid, "--disposition", disposition, "--runcard", cid, *extra)

def rule(world, rid, ruling, cid, by=("--owner",)):
  return world.run("review", "rule", "--review", rid, "--ruling", ruling, *by, "--runcard", cid)

def move(world, kind, spec):
  """The reviewed bytes move: a plan's body is re-seeded with a line appended, a spec gets one."""
  if kind == "plan":
    seed_body(world, "U07", BODY + "moved\n")
  else:
    spec.write_text(spec.read_text(encoding="utf-8") + "more\n", encoding="utf-8")

def panel_round(world, kind, rid, n, cid):
  """Every panel reviewer of the kind records round `n` with an empty file; a head's `rounds[]` entry first."""
  if kind == "head":
    head_round(world, n, "posted", cid, "revise")
  for reviewer in PANEL_OF[kind].split(","):
    assert record(world, rid, n, reviewer, [], cid, sha=A if kind == "head" else None)[0] == 0

def cap_question(world, rid, cid):
  """`judges question --cap`: the exit code with the rendered file's text, or the refusal."""
  code, out = world.run("judges", "question", "--review", rid, "--cap", "--runcard", cid)
  return code, Path(out.strip()).read_text(encoding="utf-8") if code == 0 else out

def reopen(world, kind, cid):
  """`review open` on the spec file with the kind's panel: the id it prints."""
  spec = (world.repo / "docs" / "specs" / f"{SLUG}.md").resolve()
  code, out = world.run("review", "open", "--kind", kind, "--artifact", str(spec), "--reviewers", PANEL_OF[kind], "--runcard", cid)
  assert code == 0, out
  return out.strip()

def converged_spec(world, text=SPEC):
  spec, cid, rid = opened(world, text=text)
  rounds(world, rid, cid, [[]])
  assert status(world, rid, cid)[0] == 0
  return spec, cid, rid

def approve(world, spec, cid, *extra):
  return world.run("approve-spec", "--spec", str(spec), "--runcard", cid, *extra)

def approval(world):
  return json.loads(store(world.repo).path("approvals", SLUG).read_text(encoding="utf-8"))

@pytest.mark.parametrize("kind,reviewers,astra,expect", [
  ("spec", "design,zoom-out", "off", f"spec-{SLUG}-c1"),
  ("integrate", "zoom-out,design", "off", f"spec-{SLUG}-integrate-c1"),
  ("plan", "readiness,proportion,set", "off", "abc123-plan-U07-c1"),
  ("head", "change-review,codebase-details", "off", "abc123-head-U07-c1"),
  ("spec", "design", "on", f"spec-{SLUG}-c1"),
  ("head", "change-review", "on", "abc123-head-U07-c1"),
  ("spec", "zoom-out,design", "off", "review open: first reviewer must be design"),
  ("plan", "set,readiness", "off", "review open: first reviewer must be readiness"),
  ("head", "codebase-details", "off", "review open: first reviewer must be change-review"),
  ("spec", "design,critic", "off", "review open: unknown reviewer critic"),
  ("spec", "design,zoom-out,comprehension,readiness,structural,style,codebase-details", "off", "review open: 1 to 6 reviewers"),
  ("plan", "readiness", "off", "review open: no handoff_id in state.json"),
])
def test_review_open_ids_panel_and_lane(world, kind, reviewers, astra, expect):
  spec = spec_file(world)
  seed_handoff(world, spec, hid=None if "handoff_id" in expect else HID)
  cid = card(world, spec, SKILL_OF[kind])
  artifact = str(spec) if kind in ("spec", "integrate") else "U07"
  code, out = world.run("review", "open", "--kind", kind, "--artifact", artifact, "--reviewers", reviewers,
                        "--astra", astra, "--runcard", cid)
  if expect.startswith("review open:"):
    assert code == 1 and expect in out, out
    return
  assert code == 0 and out.strip() == expect, out
  review = rjson(world, expect)
  lane = astra == "on"
  assert (review["kind"], review["cycle"], review["runcard"], review["artifact"]) == (kind, 1, cid, artifact)
  assert review["reviewers"] == reviewers.split(",") + (["astra"] if lane else [])
  assert review["converged"] == "no" and review["converged_round"] is None and review["rulings"] == []


@pytest.mark.parametrize("kind, astra, flag, panel, lane", [
  ("head", {"enabled": True}, None, "change-review,astra", True),
  ("head", {"enabled": True, "heads": False}, None, "change-review", False),
  ("head", {"enabled": False}, None, "change-review,astra", False),
  ("head", {"enabled": True}, "off", "change-review", False),
  ("plan", {"enabled": True, "heads": False}, None, "readiness", True)])
def test_review_open_seats_the_lane_on_a_head_by_the_one_control(world, kind, astra, flag, panel, lane):
  set_config(world, repo=REPO, astra=astra)
  spec, cid, rid = opened(world, kind, reviewers=panel, astra=flag)
  assert rjson(world, rid)["reviewers"] == panel.replace(",astra", "").split(",") + (["astra"] if lane else [])


def test_a_not_installed_lane_record_is_not_an_incomplete_run(world):
  set_config(world, repo=REPO, astra={"enabled": True})
  spec, cid, rid = opened(world, "head", reviewers="change-review", astra=None)
  for n, reason in ((1, "not installed"), (2, "timeout"), (3, "killed"), (4, "stopped: two incomplete runs")):
    head_round(world, n, "posted", cid, "revise")
    assert record(world, rid, n, "change-review", [], cid, sha=A)[0] == 0 and record(world, rid, n, "astra", cid=cid, sha=A, not_run=reason)[0] == 0
    assert rjson(world, rid, f"round-{n}.json")["what_ran"] == "completed" and rjson(world, rid)["astra_incomplete"] == min(n - 1, 2)


# ---------------------------------------------------------------- S3: cycles

def test_review_open_cycles(world):
  _, _, rid = opened(world)
  spec, cid, again = opened(world, reviewers="design")      # a re-typed skill resumes the open cycle
  assert again == rid and rjson(world, rid)["reviewers"] == ["design", "zoom-out"]   # the panel cannot change
  rounds(world, rid, cid, [HIGH(n) for n in range(1, 6)])
  assert status(world, rid, cid)[0] == 2 and rule(world, rid, "stop", cid)[0] == 0
  _, cid, rid2 = opened(world)
  assert rid2 == f"spec-{SLUG}-c2" and rjson(world, rid2)["cycle"] == 2                 # stop closed c1
  rounds(world, rid2, cid, [[]])
  assert status(world, rid2, cid)[0] == 0 and opened(world)[2] == rid2                # converged, same bytes: same cycle


def test_latest_cycle_closes_by_the_approval_the_handoff_and_the_rulings(world):
  spec, cid, rid = converged_spec(world)
  spec.write_text(SPEC + "\nmore\n")
  assert reopen(world, "spec", cid) == rid
  spec.write_text(SPEC)
  assert approve(world, spec, cid, "--yes")[0] == 0 and reopen(world, "spec", cid) == rid
  spec.write_text(SPEC + "\nmore\n")
  assert reopen(world, "spec", cid) == f"spec-{SLUG}-c2"
  seed_handoff(world, spec)
  icid = card(world, spec, "integrate")
  i1 = reopen(world, "integrate", icid)
  assert rjson(world, i1)["handoff_id"] == approval(world)["entries"][-1]["handoff_id"] and record(world, i1, 1, "design", [], icid)[0] == 0
  spec.write_text(SPEC + "\nmore rows\n")
  assert reopen(world, "integrate", icid) == i1
  assert approve(world, spec, icid, "--amend-units")[0] == 0
  i2 = reopen(world, "integrate", icid)
  assert i2 == f"spec-{SLUG}-integrate-c2" and reopen(world, "integrate", icid) == i2
  assert record(world, i2, 1, "design", [], icid)[0] == 0
  spec.write_text(SPEC + "\nmore rows\nand more\n")
  assert approve(world, spec, icid, "--amend-units")[0] == 0
  assert reopen(world, "integrate", icid) == f"spec-{SLUG}-integrate-c3"
  seed_handoff(world, spec, closed_at="2026-11-04")
  assert reopen(world, "integrate", icid) == f"spec-{SLUG}-integrate-c4"


# ---------------------------------------------------------------- S4: `review record`

def test_review_record_writes_the_round(world):
  spec, cid, rid = opened(world, astra="on")
  sha = hashlib.sha256(spec.read_bytes()).hexdigest()
  code, out = record(world, rid, 1, "design", [F("design", 1, 1), F("design", 1, 2, "low")], cid)
  assert (code, out.strip()) == (0, "round 1 design recorded, what_ran not run (zoom-out: no record)"), out
  rnd = rjson(world, rid, "round-1.json")
  assert (rnd["round"], rnd["runcard"], rnd["artifact_sha256"], rnd["builder_contested"]) == (1, cid, sha, [])
  design = rnd["reviewers"]["design"]
  assert (design["isolation"], design["model"], design["effort"], design["not_run"]) == ("clean", "inherit:opus", "inherit:high", None)
  assert [(f["id"], f["severity"], f["regression"], f["disposition"], f["ruling"]) for f in design["findings"]] == [
      ("design-1-1", "high", "no", None, None), ("design-1-2", "low", "no", None, None)]
  assert "what_ran not run (astra: no record)" in record(world, rid, 1, "zoom-out", [], cid)[1]   # an empty file is a record
  assert record(world, rid, 1, "astra", cid=cid, not_run="result.json: failed")[0] == 0        # the lane's not-run counts
  rnd = rjson(world, rid, "round-1.json")
  assert rnd["what_ran"] == "completed" and rnd["reviewers"]["astra"]["not_run"] == "result.json: failed"
  assert record(world, rid, 1, "design", [F("design", 1, 1)], cid)[0] == 0                     # a retry's record replaces the first
  assert len(rjson(world, rid, "round-1.json")["reviewers"]["design"]["findings"]) == 1
  assert rjson(world, rid)["astra_incomplete"] == 1


# ---------------------------------------------------------------- S5: the set and foreman reviewers

def test_record_set_and_foreman_reviewers(world):
  spec, cid, rid = opened(world, "plan")
  lines = [F("set", 2, 1, loc="U07 Interfaces"), F("set", 2, 2, loc="U08 Interfaces"), F("set", 2, 3, loc="the cut")]   # the set's round 2 into the unit's round 1
  for reviewer, found in (("readiness", []), ("proportion", []), ("set", lines)):
    assert record(world, rid, 1, reviewer, found, cid)[0] == 0
  assert [f["id"] for f in rjson(world, rid, "round-1.json")["reviewers"]["set"]["findings"]] == ["set-2-1", "set-2-3"]
  assert rjson(world, rid, "round-1.json")["what_ran"] == "completed"
  assert "review record: foreman is accepted on a head only" in record(world, rid, 1, "foreman", [F("foreman", 1, 1)], cid)[1]
  _, wcid, hid = opened(world, "head")
  head_round(world, 1, "posted", wcid, "revise")
  assert record(world, hid, 1, "foreman", [F("foreman", 1, 1)], wcid, sha=A)[0] == 0
  assert rjson(world, hid, "round-1.json")["what_ran"] == "not run (change-review: no record)"   # foreman never counts
  assert record(world, hid, 1, "change-review", [], wcid, sha=A)[0] == 0
  assert rjson(world, hid, "round-1.json")["what_ran"] == "completed"


def test_plan_reviews_hash_the_stored_body(world):
  spec, cid, rid = opened(world, "plan")
  assert rjson(world, rid)["artifact_sha256"] == sha256_text(BODY)
  argv = ["review", "open", "--kind", "plan", "--artifact", "U07", "--sha256", A, "--reviewers", "readiness", "--runcard", cid]
  assert "review open: --sha256 is refused for kind plan" in world.run(*argv)[1]
  assert "review record: --sha256 is refused for kind plan" in record(world, rid, 1, "readiness", [], cid, sha=A)[1]
  assert record(world, rid, 1, "readiness", [], cid)[0] == 0 and rjson(world, rid, "round-1.json")["artifact_sha256"] == sha256_text(BODY)


# ---------------------------------------------------------------- S6: what_ran

SPEC_PANEL = {"kind": "spec", "reviewers": ["design", "zoom-out"], "astra_incomplete": 0}
LANE = lambda n: {"kind": "spec", "reviewers": ["design", "astra"], "astra_incomplete": n}
HEAD = {"kind": "head", "reviewers": ["change-review"], "astra_incomplete": 0}
REC, NR = {"findings": [], "not_run": None}, lambda why: {"findings": [], "not_run": why}

@pytest.mark.parametrize("review,recs,entry,expect", [
  (SPEC_PANEL, {"design": REC, "zoom-out": REC}, None, "completed"),
  (SPEC_PANEL, {"design": REC}, None, "not run (zoom-out: no record)"),
  (SPEC_PANEL, {"zoom-out": REC, "design": NR("timeout")}, None, "not run (design: timeout)"),
  (LANE(1), {"design": REC, "astra": NR("killed")}, None, "completed"),
  (LANE(2), {"design": REC}, None, "completed"),
  (LANE(0), {"design": REC}, None, "not run (astra: no record)"),
  (HEAD, {"change-review": REC, "foreman": REC}, {"phase": "posted", "outcome": "revise"}, "completed"),
  (HEAD, {"change-review": REC}, {"phase": "collected", "outcome": "not run (superseded)"}, "not run (superseded)"),
  (HEAD, {"change-review": REC}, {"phase": "prepared", "outcome": None}, "not run (phase prepared)"),
  (HEAD, {}, {"phase": "collected", "outcome": "not run (fetch failed)"}, "not run (fetch failed)"),
  (HEAD, {"foreman": REC}, {"phase": "posted", "outcome": "revise"}, "not run (change-review: no record)"),
])
def test_what_ran_derivation(review, recs, entry, expect):
  assert derive_what_ran(review, {"reviewers": recs}, entry) == expect


# ---------------------------------------------------------------- S7: record refusals

@pytest.mark.parametrize("kind,prior,call,expect", [
  ("spec", [], dict(n=1, reviewer="comprehension"), "review record: comprehension is not on the panel"),
  ("spec", [], dict(n=1, reviewer="astra"), "review record: astra is not on the panel"),
  ("spec", [], dict(n=2, reviewer="design"), "review record: round 1 is next"),
  ("head", [], dict(n=1, reviewer="change-review", sha=A), "review record: no rounds[] entry for round 1"),
  ("spec", [], dict(n=1, reviewer="design", lines=["design-1-1 | high | §1"]), ":1: expected 5 fields"),
  ("spec", [], dict(n=1, reviewer="design", lines=[F("zoom-out", 1, 1)]), ":1: id must be design-1-<n>"),
])
def test_record_refusals(world, kind, prior, call, expect):
  spec, cid, rid = opened(world, kind)
  for kw in prior:
    assert record(world, rid, cid=cid, **kw)[0] == 0
  code, out = record(world, rid, cid=cid, **call)
  assert code == 1 and expect in out, out
  if not prior:
    assert not rpath(world, rid, f"round-{call['n']}.json").exists()


# ---------------------------------------------------------------- S8: `review settle`

@pytest.mark.parametrize("kind,mode,reviewer,sev,loc,fid,disposition,extra,expect", [
  ("spec", None, "design", "high", "§1", "design-1-1", "contested", (), "review settle: design-1-1 is high: --owner required in normal mode"),
  ("spec", None, "design", "medium", "§1", "design-1-1", "declined", ("--owner",), "design-1-1 declined"),
  ("spec", "leavemealone", "design", "high", "§1", "design-1-1", "contested", ("--owner",), "review settle: design-1-1 is high: --judges required in leavemealone-mode"),
  ("spec", "leavemealone", "design", "medium", "§1", "design-1-1", "declined", ("--judges", "j1"), "design-1-1 declined"),
  ("spec", None, "design", "low", "§1", "design-1-1", "contested", (), "design-1-1 contested"),
  ("spec", None, "design", "high", "§1", "design-1-1", "escalated", (), "design-1-1 escalated"),
  ("spec", None, "design", "high", "§1", "design-1-1", "fix-design", (), "design-1-1 fix-design"),
  ("head", None, "change-review", "high", "src/x.py", "change-review-1-1", "fix-design", (), "review settle: fix-design is refused on a head"),
  ("head", None, "foreman", "high", "ci", "foreman-1-1", "fixed", (), "review settle: the CI finding is settled by no one"),
  ("spec", None, "design", "high", "§1", "design-1-9", "fixed", (), "review settle: no finding design-1-9"),
])
def test_settle_and_its_refusals(world, kind, mode, reviewer, sev, loc, fid, disposition, extra, expect):
  spec, cid, rid = opened(world, kind, mode=mode)
  if kind == "head":
    head_round(world, 1, "posted", cid, "revise")
  assert record(world, rid, 1, reviewer, [F(reviewer, 1, 1, sev, loc=loc)], cid, sha=A if kind == "head" else None)[0] == 0
  code, out = settle(world, rid, fid, disposition, cid, *extra)
  finding = rjson(world, rid, "round-1.json")["reviewers"][reviewer]["findings"][0]
  if expect.startswith("review settle:"):
    assert code == 1 and expect in out and finding["disposition"] is None, out
  else:
    assert (code, out.strip()) == (0, expect) and finding["disposition"] == disposition
    assert finding["ruling"] == (None if not extra else "owner" if extra == ("--owner",) else f"judges:{extra[1]}")


@pytest.mark.parametrize("author, body, expect", [
  ("owner", "**Ruling:** design-1-1 finding overruled — Scope widened", "design-1-1 declined"),
  ("passer-by", "**Ruling:** design-1-1 finding overruled — Scope widened", "review settle: comment 13 is by passer-by, not a login in config.owners"),
  ("owner", "**Ruling:** design-1-1 finding upheld (fix it)", "review settle: comment 13 does not rule design-1-1 overruled"),
])
def test_settle_takes_the_owners_posted_overrule_in_leavemealone(world, author, body, expect):
  """1.1.3 fix (wave-0021, U17 round 5): in leavemealone the owner's word still counts, by hand: `--owner --posted
  <comment>` settles a high when the comment is an owner's `**Ruling:** <fid> finding overruled` (one GitHub read)."""
  set_config(world, repo=REPO, owners=["owner"])
  spec, cid, rid = opened(world, "spec", mode="leavemealone")
  assert record(world, rid, 1, "design", [F("design", 1, 1, "high", loc="§1")], cid)[0] == 0
  served = {"id": 13, "user": {"login": author}, "body": body}
  world.gh.extend("api", lambda args, cwd, token=None: world.gh.ok(served) if world.gh.endpoint_of(args) == f"repos/{REPO}/issues/comments/13" else world.gh.do_api(args))
  code, out = settle(world, rid, "design-1-1", "declined", cid, "--owner", "--posted", "13")
  finding = rjson(world, rid, "round-1.json")["reviewers"]["design"]["findings"][0]
  if expect.startswith("review settle:"):
    assert code == 1 and expect in out and finding["disposition"] is None, out
  else:
    assert (code, out.strip()) == (0, expect) and (finding["disposition"], finding["ruling"]) == ("declined", "owner")


# ---------------------------------------------------------------- S9: `review status`

def s_unopened(w, c, r): return f"spec-{SLUG}-c9"
def s_open_only(w, c, r): return r
def s_clean(w, c, r): rounds(w, r, c, [[]]); return r
def s_low_only(w, c, r): rounds(w, r, c, [[F("design", 1, 1, "low")]]); return r
def s_unsettled_high(w, c, r): rounds(w, r, c, [HIGH(1)]); return r
def s_settled(w, c, r):
  rounds(w, r, c, [HIGH(1)]); move(w, "spec", spec_file(w)); assert settle(w, r, "design-1-1", "fixed", c)[0] == 0
  rounds(w, r, c, [[]], start=2); return r
def s_regression(w, c, r):
  rounds(w, r, c, [HIGH(1), [F("design", 2, 1, reg="yes")]]); move(w, "spec", spec_file(w))
  assert settle(w, r, "design-2-1", "fixed", c)[0] == 0; return r
def s_fix_design(w, c, r): rounds(w, r, c, [HIGH(1)]); assert settle(w, r, "design-1-1", "fix-design", c)[0] == 0; return r
def s_cap(w, c, r): rounds(w, r, c, [HIGH(n) for n in range(1, 6)]); return r
def s_cap_short(w, c, r): rounds(w, r, c, [HIGH(n) for n in range(1, 5)] + [None]); return r
def s_continue(w, c, r): s_cap(w, c, r); assert rule(w, r, "continue", c)[0] == 0; return r
def s_accept(w, c, r): s_cap(w, c, r); assert rule(w, r, "accept", c)[0] == 0; return r
def s_stop(w, c, r): s_cap(w, c, r); assert rule(w, r, "stop", c)[0] == 0; return r
def s_stalled(w, c, r): rounds(w, r, c, [HIGH(1), None, None]); return r

@pytest.mark.parametrize("scenario,new_card,code,fragment", [
  (s_unopened, False, 3, f"review spec-{SLUG}-c9: not opened"),
  (s_open_only, False, 3, "round 0: not clean, regressions 0, converged no, cap no, stalled no, sha256 none"),
  (s_clean, False, 0, "round 1: clean, regressions 0, converged yes, cap no, stalled no, sha256 "),
  (s_low_only, False, 0, "converged yes"),
  (s_unsettled_high, False, 3, "round 1: not clean, regressions 0, converged no"),
  (s_settled, False, 0, "round 2: clean, regressions 0, converged yes"),
  (s_regression, False, 3, "round 2: clean, regressions 1, converged no"),
  (s_fix_design, False, 4, "converged no"),
  (s_cap, False, 2, "round 5: not clean, regressions 0, converged no, cap yes, stalled no"),
  (s_cap_short, False, 3, "converged no, cap no, stalled no"),
  (s_continue, False, 3, "cap no"),
  (s_accept, False, 0, "converged by ruling R1, cap yes"),
  (s_stop, False, 2, "converged no, cap yes"),
  (s_stalled, False, 5, "stalled yes"),
  (s_stalled, True, 3, "stalled no"),
])
def test_status_exit_codes(world, scenario, new_card, code, fragment):
  spec, cid, rid = opened(world)
  rid = scenario(world, cid, rid)
  if new_card:
    cid = card(world, spec)          # a re-typed skill: the two not-run rounds carry the old card
  got, out = status(world, rid, cid)
  assert (got, fragment in out) == (code, True), out
  if scenario is s_regression:
    assert "rounds: 1 -> 1 (regressions 0, 1)" in out


@pytest.mark.parametrize("kind", ["spec", "plan", "integrate", "head"])
def test_settle_fixed_needs_changed_bytes(world, kind):
  spec, cid, rid = opened(world, kind)
  first = PANEL_OF[kind].split(",")[0]
  if kind == "head":
    head_round(world, 1, "posted", cid, "revise")
  assert record(world, rid, 1, first, [F(first, 1, 1)], cid, sha=A if kind == "head" else None)[0] == 0
  code, out = settle(world, rid, f"{first}-1-1", "fixed", cid)
  if kind != "head":
    assert code == 1 and "review settle: fixed needs changed bytes" in out
    assert settle(world, rid, f"{first}-1-1", "escalated", cid)[0] == 0
    move(world, kind, spec)
    code, out = settle(world, rid, f"{first}-1-1", "fixed", cid)
  assert code == 0, out


@pytest.mark.parametrize("kind", ["spec", "plan", "integrate", "head"])
def test_status_prints_fixed_on_clean_rounds_whose_bytes_moved(world, kind):
  spec, cid, rid = opened(world, kind)
  panel_round(world, kind, rid, 1, cid)
  assert status(world, rid, cid)[0] == 0
  move(world, kind, spec)
  code, out = status(world, rid, cid)
  if kind == "head":
    assert code == 0 and "fixed:" not in out
    return
  assert code == 3 and "converged no" in out and out.splitlines()[2] == "fixed: re-review on the current bytes"
  panel_round(world, kind, rid, 2, cid)
  assert status(world, rid, cid)[0] == 0


# ---------------------------------------------------------------- S10: `review rule`

def test_review_rule(world):
  spec, cid, rid = opened(world)
  assert "review rule: not at the cap" in rule(world, rid, "continue", cid)[1]
  rounds(world, rid, cid, [HIGH(n) for n in range(1, 6)])
  code, out = rule(world, rid, "continue", cid, ("--judges", "j1"))
  assert (code, out.strip()) == (0, "ruling R1 continue") and status(world, rid, cid)[0] == 3
  assert "review rule: continue already ruled this cycle" in rule(world, rid, "continue", cid)[1]
  rounds(world, rid, cid, [HIGH(6)], start=6)
  assert status(world, rid, cid)[0] == 2 and rule(world, rid, "accept", cid)[0] == 0
  review = rjson(world, rid)
  assert (review["converged"], review["converged_round"]) == ("by ruling R2", 6)
  assert [(r["id"], r["ruling"], r["by"]) for r in review["rulings"]] == [("R1", "continue", "judges:j1"), ("R2", "accept", "owner")]
  _, cid2, rid2 = opened(world)                                            # accept closed c1
  rounds(world, rid2, cid2, [HIGH(n) for n in range(1, 6)])
  assert rule(world, rid2, "stop", cid2)[0] == 0 and status(world, rid2, cid2)[0] == 2
  assert "review rule: cycle stopped" in rule(world, rid2, "accept", cid2)[1]
  assert "review record: review at its cap" in record(world, rid2, 6, "design", [], cid2)[1]
  _, wcid, hid = opened(world, "head")
  for n in range(1, 6):
    head_round(world, n, "posted", wcid, "revise")
    assert record(world, hid, n, "change-review", [F("change-review", n, 1)], wcid, sha=A)[0] == 0
  assert "review rule: accept is refused on a head" in rule(world, hid, "accept", wcid)[1]


def test_rule_refuses_accept_while_the_bytes_moved_and_stop_needs_no_ruler(world):
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [HIGH(n) for n in range(1, 6)])
  spec.write_text(SPEC + "\nmore\n")
  refusal = "review rule: the reviewed bytes moved: continue or stop"
  assert status(world, rid, cid)[0] == 2 and refusal in rule(world, rid, "accept", cid)[1]
  assert cap_question(world, rid, cid)[1].endswith("- (a) continue one bounded round\n- (b) stop\n")
  assert "review rule: --owner or --judges required" in rule(world, rid, "stop", cid, by=())[1]
  assert rule(world, rid, "continue", cid)[0] == 0
  rounds(world, rid, cid, [HIGH(6)], start=6)
  spec.write_text(SPEC + "\neven more\n")
  code, out = cap_question(world, rid, cid)
  assert code == 1 and "question: one option: stop" in out and refusal in rule(world, rid, "accept", cid)[1]
  code, out = rule(world, rid, "stop", cid, by=())
  assert (code, out.strip()) == (0, "ruling R2 stop") and rjson(world, rid)["rulings"][-1]["by"] == "helper"
  assert opened(world)[2] == f"spec-{SLUG}-c2"


def test_set_fixed_settles_every_copy(world):
  spec, cid, r7 = opened(world, "plan")
  seed_body(world, "U08", BODY.replace("U07", "U08"))
  r8 = world.run("review", "open", "--kind", "plan", "--artifact", "U08", "--reviewers", PANEL_OF["plan"], "--runcard", cid)[1].strip()
  for rid in (r7, r8):
    for reviewer in ("readiness", "proportion", "set"):
      assert record(world, rid, 1, reviewer, [F("set", 1, 1, loc="the cut")] if reviewer == "set" else [], cid)[0] == 0
  seed_body(world, "U07", BODY + "fixed\n")
  assert "review settle: fixed needs changed bytes" in settle(world, r8, "set-1-1", "fixed", cid)[1]
  assert settle(world, r7, "set-1-1", "fixed", cid)[0] == 0
  assert rjson(world, r8, "round-1.json")["reviewers"]["set"]["findings"][0]["disposition"] == "fixed"
  assert status(world, r8, cid)[0] == 0 and status(world, r7, cid)[0] == 3


# ---------------------------------------------------------------- S11: a head's outcome

def test_settle_writes_head_outcome(world):
  spec, wcid, hid = opened(world, "head")
  head_round(world, 1, "posted", wcid, "revise")
  assert record(world, hid, 1, "change-review", [F("change-review", 1, 1)], wcid, sha=A)[0] == 0
  assert status(world, hid, wcid)[0] == 3
  assert settle(world, hid, "change-review-1-1", "contested", wcid, "--owner")[0] == 0
  entry = json.loads(store(world.repo).path("foreman", "U07").read_text(encoding="utf-8"))["rounds"][0]
  assert entry["outcome"] == "clean" and status(world, hid, wcid)[0] == 0
  assert "U07 awaiting merge" in store(world.repo).path("journal").read_text(encoding="utf-8")
  child = card(world, spec, "wave", parent=wcid)                           # a foreman dispatch's child card
  head_round(world, 2, "posted", wcid, "revise")
  assert record(world, hid, 2, "change-review", [], child, sha=A)[0] == 0
  assert rjson(world, hid, "round-2.json")["runcard"] == wcid              # the round carries the top-level card


# ---------------------------------------------------------------- S12: `approve-spec`

def test_approve_spec_asks_then_commits_by_path(world):
  spec, cid, rid = converged_spec(world)
  sha = hashlib.sha256(spec.read_bytes()).hexdigest()
  (world.repo / "notes.txt").write_text("untracked\n", encoding="utf-8")
  code, out = approve(world, spec, cid)
  assert code == 0 and f"Approve `{spec}` (sha256 `{sha[:12]}`) at review {rid}?" in out and "--yes" in out
  assert not store(world.repo).path("approvals", SLUG).exists()
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0 and "approval recorded" in out, out
  rec = approval(world)["entries"][0]
  assert (approval(world)["path"], rec["sha256"], rec["review"], rec["runcard"]) == (str(spec), sha, rid, cid)
  assert rec["commit"] == git(world, "rev-parse", "HEAD") and rec["handoff_id"] == f"2026-11-03-sample-de-{sha[:6]}"
  assert rec["kind"] == "opening" and rec["voided_by"] is None and rec["approved_at"]
  assert git(world, "log", "-1", "--format=%s") == f"superegm: approve {SLUG} at review {rid}"
  names = git(world, "show", "--name-only", "--format=", "HEAD").splitlines()
  assert f"docs/specs/{SLUG}.md" in names and "notes.txt" not in names and "?? notes.txt" in git(world, "status", "--porcelain")
  code, out = approve(world, spec, cid, "--leavemealone")
  assert code == 0 and "approval recorded" in out and "Approve `" not in out


def test_approve_spec_appends_history_entries_and_opens_one_handoff_per_opening(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  rec, sha = approval(world), hashlib.sha256(spec.read_bytes()).hexdigest()
  assert list(rec) == ["entries", "path"] and [list(e) for e in rec["entries"]] == [["approved_at", "commit", "escalated", "handoff_id", "kind", "review", "runcard", "sha256", "voided_by"]]
  first = rec["entries"][0]
  assert (first["sha256"], first["kind"], first["handoff_id"]) == (sha, "opening", f"2026-11-03-sample-de-{sha[:6]}")
  assert json.loads(store(world.repo).path("handoffs", first["handoff_id"]).read_text(encoding="utf-8")) == {"id": first["handoff_id"], "spec": str(spec), "opened_at": first["approved_at"], "closed_at": None}
  spec2, cid2, rid2 = converged_spec(world, SPEC.replace("Text.", "Changed.")); assert approve(world, spec2, cid2, "--yes")[0] == 0
  second = approval(world)["entries"][1]
  assert second["kind"] == "opening" and second["handoff_id"] != first["handoff_id"] and store(world.repo).path("handoffs", second["handoff_id"]).is_file()
  assert [h["id"] for h in handoffs(world.artifacts)] == sorted([first["handoff_id"], second["handoff_id"]])


# ---------------------------------------------------------------- S13: approve-spec refusals

def a_bytes_differ(w):
  spec, cid, rid = opened(w); s_accept(w, cid, rid); spec.write_text(SPEC + "\nmore\n", encoding="utf-8"); return spec, cid
def a_not_converged(w):
  spec, cid, rid = opened(w); rounds(w, rid, cid, [HIGH(1)]); return spec, cid
def a_units_not_last(w):
  return converged_spec(w, SPEC + "\n## 3. Appendix\n\nText.\n")[:2]
def a_no_review(w):
  spec = spec_file(w); return spec, card(w, spec)

@pytest.mark.parametrize("scenario,expect", [
  (a_bytes_differ, "approve-spec: spec bytes differ from the converged round's"),
  (a_not_converged, f"approve-spec: review spec-{SLUG}-c1 is not converged (review status exit 3)"),
  (a_units_not_last, "approve-spec: last H2 must be `Units`"),
  (a_no_review, f"approve-spec: no spec review for {SLUG}"),
])
def test_approve_spec_refusals(world, scenario, expect):
  spec, cid = scenario(world)
  head = git(world, "rev-parse", "HEAD")
  code, out = approve(world, spec, cid, "--yes")
  assert code == 1 and expect in out and git(world, "rev-parse", "HEAD") == head, out
  assert not store(world.repo).path("approvals", SLUG).exists()


@pytest.mark.parametrize("named", [False, True])
def test_approve_spec_records_the_escalated_pairs(world, named):
  pair = f"spec-{SLUG}-c1:design-1-1"
  text = SPEC + (f"Escalated: {pair} is U01's.\n" if named else "")
  spec, cid, rid = opened(world, text=text)
  rounds(world, rid, cid, [HIGH(n) for n in range(1, 6)])
  assert settle(world, rid, "design-1-1", "escalated", cid)[0] == 0 and rule(world, rid, "stop", cid)[0] == 0
  _, cid, rid2 = opened(world, text=text)
  rounds(world, rid2, cid, [[]])
  code, out = approve(world, spec, cid)
  assert code == 0 and (f"approve-spec: 1 escalated finding(s) await the owner: {pair}" in out) is not named
  assert approve(world, spec, cid, "--yes")[0] == 0 and approval(world)["entries"][-1]["escalated"] == ([] if named else [pair])
  spec, cid, rid3 = opened(world, text=text.replace("Text.", "Changed."))
  rounds(world, rid3, cid, [HIGH(1)])
  assert settle(world, rid3, "design-1-1", "escalated", cid)[0] == 0 and approve(world, spec, cid, "--leavemealone")[0] == 0
  assert (rid3, approval(world)["entries"][-1]["escalated"]) == (f"spec-{SLUG}-c3", [f"{rid3}:design-1-1"])


@pytest.mark.parametrize("trailer", ["", "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"])
def test_approve_spec_appends_the_commit_trailer(world, trailer):
  set_config(world, repo=REPO, commit_trailer=trailer)
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  subject = f"superegm: approve {SLUG} at review {rid}"
  assert git(world, "log", "-1", "--format=%B") == (f"{subject}\n\n{trailer}" if trailer else subject)


# ---------------------------------------------------------------- S14: the handoff id

@pytest.mark.parametrize("filed,voided,keeps", [
  (True, True, True),
  (True, False, False),
  (False, True, False),
])
def test_handoff_id_copy_rule(world, filed, voided, keeps):
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  first = approval(world)["entries"][-1]["handoff_id"]
  atomic_write(world.artifacts / first / "state.json", {"handoff_id": first, "units": {"U07": {"number": 7} if filed else {}}})
  if voided:  # as `--void` leaves the last entry
    rec = approval(world); rec["entries"][-1]["voided_by"] = f"spec-{SLUG}-c1"; atomic_write(store(world.repo).path("approvals", SLUG), rec)
  spec2, cid2, rid2 = converged_spec(world, SPEC.replace("Text.", "Changed."))
  assert rid2.endswith("-c2") and approve(world, spec2, cid2, "--yes")[0] == 0
  second = approval(world)["entries"][-1]
  assert (second["handoff_id"] == first) is keeps and second["kind"] == ("after-void" if keeps else "opening")
  assert second["handoff_id"].endswith(hashlib.sha256(spec2.read_bytes()).hexdigest()[:6]) is not keeps


# ---------------------------------------------------------------- S15: `approve-spec --void`

def test_approve_spec_void(world):
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  earlier = approval(world)["entries"][-1]["handoff_id"]
  changed = SPEC.replace("Text.", "Changed.")
  spec, cid, rid = converged_spec(world, changed)
  assert approve(world, spec, cid, "--yes")[0] == 0
  hid = approval(world)["entries"][-1]["handoff_id"]
  _, pcid, prid = opened(world, "plan", text=changed)
  assert record(world, prid, 1, "readiness", [F("readiness", 1, 1)], pcid)[0] == 0
  assert record(world, prid, 1, "proportion", [], pcid)[0] == 0 and record(world, prid, 1, "set", [], pcid)[0] == 0
  code, out = approve(world, spec, pcid, "--void", "--review", prid)
  assert code == 1 and f"approve-spec: review {prid} has no fix-design finding" in out and approval(world)["entries"][-1]["voided_by"] is None
  assert settle(world, prid, "readiness-1-1", "fix-design", pcid)[0] == 0 and status(world, prid, pcid)[0] == 4
  code, out = approve(world, spec, pcid, "--void", "--review", prid, "--handoff", earlier)
  assert code == 1 and f"approve-spec: {earlier}: not the latest approval: plan the rows in the latest handoff" in out
  assert approve(world, spec, pcid, "--void", "--review", prid)[0] == 0 and approval(world)["entries"][-1]["voided_by"] == prid
  closed_at = json.loads((world.artifacts / hid / "state.json").read_text(encoding="utf-8"))["closed_at"]
  assert closed_at and json.loads(store(world.repo).path("handoffs", hid).read_text(encoding="utf-8"))["closed_at"] == closed_at
  assert "closed: voided" in (world.artifacts / hid / "journal.md").read_text(encoding="utf-8")
  store(world.repo).path("approvals", SLUG).unlink()
  assert f"approve-spec: no approval for {SLUG}" in approve(world, spec, pcid, "--void", "--review", prid)[1]


# ---------------------------------------------------------------- S16: `approve-spec --amend-units`

def test_approve_spec_amend_units(world):
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  first = approval(world)["entries"][-1]
  icid = card(world, spec, "integrate")
  spec.write_text(SPEC + "| U02 | more (from integrate, review spec-x-integrate-c1) | U01 | S |\n", encoding="utf-8")
  code, out = approve(world, spec, icid, "--amend-units")
  assert code == 0, out
  whole = approval(world)
  rec = whole["entries"][-1]
  assert rec["handoff_id"] == first["handoff_id"] and rec["sha256"] == hashlib.sha256(spec.read_bytes()).hexdigest() != first["sha256"]
  assert rec["commit"] == git(world, "rev-parse", "HEAD") != first["commit"] and [e["kind"] for e in whole["entries"]] == ["opening", "amend-units"]
  assert git(world, "log", "-1", "--format=%s") == f"superegm: approve {SLUG} at review {rid}"
  spec.write_text(spec.read_text(encoding="utf-8").replace("Text.", "Changed."), encoding="utf-8")
  code, out = approve(world, spec, icid, "--amend-units")
  assert code == 1 and "approve-spec: a line outside ## Units changed" in out and approval(world) == whole
  store(world.repo).path("approvals", SLUG).unlink()
  assert "approve-spec: no approval to amend" in approve(world, spec, icid, "--amend-units")[1]


def test_amend_units_and_void_act_on_the_latest_entry_alone(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  a = approval(world)["entries"][0]["handoff_id"]
  spec2, cid2, rid2 = converged_spec(world, SPEC.replace("Text.", "Changed.")); assert approve(world, spec2, cid2, "--yes")[0] == 0
  b = approval(world)["entries"][1]["handoff_id"]
  icid = card(world, spec, "integrate")
  spec.write_text(spec.read_text(encoding="utf-8") + "| U02 | more (from integrate, review x) | U01 | S |\n", encoding="utf-8")
  assert f"approve-spec: {a}: not the latest approval: plan the rows in the latest handoff" in world.run("approve-spec", "--spec", str(spec), "--amend-units", "--handoff", a, "--runcard", icid)[1]
  assert approve(world, spec, icid, "--amend-units")[0] == 0
  assert [(e["kind"], e["handoff_id"]) for e in approval(world)["entries"]] == [("opening", a), ("opening", b), ("amend-units", b)]


def test_amend_units_keeps_the_escalated_pairs_of_the_entry_it_amends(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  record = approval(world); record["entries"][0]["escalated"] = [f"{rid}:design-1-1"]
  atomic_write(store(world.repo).path("approvals", SLUG), record)
  icid = card(world, spec, "integrate")
  spec.write_text(spec.read_text(encoding="utf-8") + "| U02 | more (from integrate, review x) | U01 | S |\n", encoding="utf-8")
  assert approve(world, spec, icid, "--amend-units")[0] == 0
  assert [e["escalated"] for e in approval(world)["entries"]] == [[f"{rid}:design-1-1"]] * 2


def test_approve_spec_writes_a_legacy_handoffs_file_the_first_time_it_touches_it(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  first = approval(world)["entries"][0]
  root = world.artifacts
  shutil.rmtree(root / "handoffs"); shutil.rmtree(root / first["handoff_id"], ignore_errors=True)
  record = {k: v for k, v in first.items() if k not in ("kind", "escalated")} | {"path": str(spec), "amended": []}
  atomic_write(root / f"approvals/{SLUG}.json", record)
  atomic_write(root / "state.json", {"handoff_id": first["handoff_id"], "units": {}, "design": {"path": str(spec)}})
  assert store(world.repo).legacy
  icid = card(world, spec, "integrate")
  spec.write_text(spec.read_text(encoding="utf-8") + "| U02 | more (from integrate, review x) | U01 | S |\n", encoding="utf-8")
  assert approve(world, spec, icid, "--amend-units")[0] == 0
  assert json.loads((root / f"handoffs/{first['handoff_id']}.json").read_text(encoding="utf-8")) == \
      {"id": first["handoff_id"], "spec": str(spec), "opened_at": None, "closed_at": None}


def test_plan_and_head_review_ids_drop_the_hex_and_a_frozen_handoff_refuses_fix_design(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  a = approval(world)["entries"][0]["handoff_id"]
  seed_handoff(world, spec, hid=a)
  assert opened(world, "plan")[2] == "plan-U07-c1" and opened(world, "head")[2] == "head-U07-c1"
  spec2, cid2, rid2 = converged_spec(world, SPEC.replace("Text.", "Changed.")); assert approve(world, spec2, cid2, "--yes")[0] == 0
  pcid = card(world, spec, "review-plan", handoff=a)
  assert f"review open: {a}: not the latest approval: plan the rows in the latest handoff" in world.run("review", "open", "--kind", "plan", "--artifact", "U07", "--reviewers", "readiness", "--runcard", pcid)[1]
  icid = card(world, spec, "integrate", handoff=a)
  irid = world.run("review", "open", "--kind", "integrate", "--artifact", str(spec), "--reviewers", "design", "--runcard", icid)[1].strip()
  assert record(world, irid, 1, "design", [F("design", 1, 1)], icid)[0] == 0
  assert "review settle: fix-design is refused on a frozen handoff's integrate: settle it escalated" in settle(world, irid, "design-1-1", "fix-design", icid)[1]


def test_approve_spec_refuses_a_branch_not_holding_the_last_entrys_bytes(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  sha7 = approval(world)["entries"][0]["sha256"][:7]
  git(world, "checkout", "-qb", "stale", "HEAD~1")
  spec2, cid2, rid2 = converged_spec(world, SPEC.replace("Text.", "Elsewhere."))
  head = git(world, "rev-parse", "HEAD")
  assert f"approve-spec: fold main first: approval {sha7} is not in this branch" in approve(world, spec2, cid2, "--yes")[1] and git(world, "rev-parse", "HEAD") == head
  spec2.unlink()  # the stale branch's untracked copy: `main` tracks the file, so checkout would refuse to overwrite it
  git(world, "checkout", "-q", "main"); git(world, "commit", "-q", "--amend", "--no-edit", "--allow-empty")
  # the stale branch's cycle c2 is still open (no approval names it): its round 2 converges at these bytes
  spec3, cid3, rid3 = spec_file(world, SPEC.replace("Text.", "Changed.")), cid2, rid2
  rounds(world, rid3, cid3, [[]], start=2); assert status(world, rid3, cid3)[0] == 0
  assert approve(world, spec3, cid3, "--yes")[0] == 0


def test_amend_units_refuses_a_branch_not_holding_the_last_entrys_bytes(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  rec = approval(world); sha7 = rec["entries"][0]["sha256"][:7]
  icid = card(world, spec, "integrate")
  git(world, "checkout", "-qb", "stale", "HEAD~1")
  spec.parent.mkdir(parents=True, exist_ok=True)
  spec.write_text(SPEC + "| U02 | more (from integrate, review x) | U01 | S |\n", encoding="utf-8")
  head = git(world, "rev-parse", "HEAD")
  code, out = approve(world, spec, icid, "--amend-units")
  assert code == 1 and f"approve-spec: fold main first: approval {sha7} is not in this branch" in out
  assert git(world, "rev-parse", "HEAD") == head and approval(world) == rec


# ---------------------------------------------------------------- S17: the references

REFS = ROOT / "skills" / "review-spec" / "references"

def test_review_loop_and_resolve_references():
  loop = (REFS / "review_loop.md").read_text(encoding="utf-8")
  for phrase in ("superegm review open", "superegm review record", "superegm review settle", "superegm review status", "superegm review rule",
                 "exit 0", "exit 5", "exit 2", "exit 4", "exit 3", "regression: yes|no",
                 "EGM's second consecutive clean round for document reviews is dropped",
                 "one `completed`, clean, non-regressing round converges every kind",
                 "SUPEREGM_GOLDFISH_MODEL", "SUPEREGM_GOLDFISH_EFFORT", "requested -> effective",
                 "runner.py", "review --host claude", "--resume", "astra-<round>-<n>", "two incomplete runs",
                 "run_in_background", "SUPEREGM_ROLE=goldfish", "change the thing, not the round", "--not-run"):
    assert phrase in loop, phrase
  resolve = (REFS / "resolve.md").read_text(encoding="utf-8")
  for phrase in ("fixed", "contested", "declined", "escalated", "fix-design", "superegm review settle",
                 "A contest must be checkable", "Do not contest a comprehension gap", "Do not change a severity"):
    assert phrase in resolve, phrase
  assert len(loop.encode()) < 24_000 and len(resolve.encode()) < 12_000


# ---------------------------------------------------------------- S18: the skill body

SKILL = ROOT / "skills" / "review-spec" / "SKILL.md"

def test_review_spec_skill_body():
  text = SKILL.read_text(encoding="utf-8")
  assert text.startswith("---\nname: review-spec\n")
  front, body = text.split("\n---\n", 1)
  assert len(body.encode()) <= 24_000
  assert "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first." in body
  for phrase in ("<spec-path> [--reviewers design,zoom-out,…] [--astra on|off] [--leavemealone]", "superegm init",
                 "superegm runcard open --skill review-spec", "superegm review open --kind spec", "config.reviewers.spec",
                 "`design` is first", "references/review_loop.md", "references/resolve.md", "superegm review status",
                 "superegm approve-spec", "--leavemealone", "approve-spec --void", "origin/<base>", "superegm runcard close"):
    assert phrase in body, phrase
  for ref in set(re.findall(r"`(references/[^`]+)`", body)):
    assert (SKILL.parent / ref).is_file(), ref


# ---------------------------------------------------------------- S19: the sweep for removed mechanisms

STALE = ["egm-review-loop", "egm-resolve", "synthesizer", "Stage 7", "Stage 9", "re-audit", "two consecutive clean",
         "Blocker", "Major", "Nit", "goldfish_dispositions", "goldfish_review_report", "EGM_ASTRA", "EGM_GOLDFISH",
         "Codex integration", "Antigravity", "spawn_agent", "What ran", "Churn", "--what-ran"]

@pytest.mark.parametrize("rel,phrases", [
  ("skills/review-spec/SKILL.md", STALE),
  ("skills/review-spec/references/review_loop.md", STALE),
  ("skills/review-spec/references/resolve.md", STALE),
  ("resources/review_panels.md", ["two consecutive clean rounds", "handoff gate may also require"]),
])
def test_no_removed_mechanism_named(rel, phrases):
  path = ROOT / rel
  if rel.startswith("resources/") and not path.exists():
    pytest.skip("D1 (b): resources/review_panels.md was not kept by U01")
  text = path.read_text(encoding="utf-8")
  assert [p for p in phrases if re.search(rf"(?<!SUPER){re.escape(p)}", text)] == []   # SUPEREGM_GOLDFISH_* is not EGM_GOLDFISH


# ---------------------------------------------------------------- S20: the scope's sections and neighbours (U19)

OLD = "# T\n\npre\n\n## 1. A\n\na\n\n### 1.1 B\n\nb\n\n### 1.2 C\n\nc\n\n## 2. D\n\nd\n\n## 3. E\n\ne\n\n```\n## not a heading\n```\n"

@pytest.mark.parametrize("new, expect", [
  (OLD.replace("\nc\n", "\nc changed\n"), [("neighbour", "### 1.1 B", 9, 12), ("changed", "### 1.2 C", 13, 16), ("neighbour", "## 2. D", 17, 20)]),
  (OLD.replace("\nd\n", "\nd changed\n"), [("neighbour", "### 1.2 C", 13, 16), ("changed", "## 2. D", 17, 20), ("neighbour", "## 3. E", 21, 27)]),
  (OLD.replace("\npre\n", "\npre changed\n"), [("changed", "(preamble)", 1, 4), ("neighbour", "## 1. A", 5, 8)]),
  (OLD.replace("\nb\n", "\nb changed\n"), [("neighbour", "## 1. A", 5, 8), ("changed", "### 1.1 B", 9, 12), ("neighbour", "### 1.2 C", 13, 16)]),
  (OLD.replace("## not a heading", "## not a heading, changed"), [("neighbour", "## 2. D", 17, 20), ("changed", "## 3. E", 21, 27)]),
  (OLD.replace("\nb\n", "\nb changed\n").replace("\nc\n", "\nc changed\n"), [("neighbour", "## 1. A", 5, 8), ("changed", "### 1.1 B", 9, 12), ("changed", "### 1.2 C", 13, 16), ("neighbour", "## 2. D", 17, 20)]),
  (OLD.replace("\nc\n", "\n"), [("neighbour", "### 1.1 B", 9, 12), ("changed", "### 1.2 C", 13, 15), ("neighbour", "## 2. D", 16, 19)]),
  (OLD, [])])
def test_scope_sections_and_neighbours(new, expect):
  assert scope_sections(OLD, new) == expect


# ---------------------------------------------------------------- S21: `review open --scope` (U19)

@pytest.mark.parametrize("scope, approved, expect", [
  (None, False, "auto"), ("whole", False, "whole"), ("## 1. Intent;## 2. Units", True, ["## 1. Intent", "## 2. Units"]),
  ("## 9. Nope", True, "review open: --scope: ## 9. Nope is not in the spec"), ("## 1. Intent", False, "review open: --scope <list>: no approval: use whole")])
def test_review_open_records_the_scope_form(world, scope, approved, expect):
  if approved:
    spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0; move(world, "spec", spec)
  else:
    spec = spec_file(world); cid = card(world, spec)
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", str(spec), "--reviewers", "design", *(["--scope", scope] if scope else []), "--runcard", cid)
  assert (code == 0 and rjson(world, out.strip())["scope"] == expect) or (code == 1 and expect in out), out


# ---------------------------------------------------------------- S22: `review scope`, derived from the approval's commit (U19)

def test_review_scope_derives_the_round_from_the_approval_commit(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  spec.write_text(SPEC.replace("Text.", "Changed."), encoding="utf-8")
  rid2 = reopen(world, "spec", cid)
  lines = lambda: world.run("review", "scope", "--review", rid2, "--runcard", cid)[1].strip().splitlines()
  assert lines() == ["neighbour 1-2 (preamble)", "changed 3-6 ## 1. Intent", "neighbour 7-11 ## 2. Units"]
  rec = approval(world); rec["entries"][-1]["commit"] = "0" * 40; atomic_write(store(world.repo).path("approvals", SLUG), rec)
  assert lines()[1] == "changed 3-6 ## 1. Intent"
  rec["entries"][-1]["sha256"] = "1" * 64; atomic_write(store(world.repo).path("approvals", SLUG), rec)
  assert lines() == ["whole 1-11 (no commit holds 1111111)"]


# ---------------------------------------------------------------- S23: `review record` refuses a finding out of scope (U19)

SPEC4 = SPEC.replace("## 2. Units", "## 2. Goals\n\nGoals.\n\n## 3. Risks\n\nRisks.\n\n## 4. Units")

@pytest.mark.parametrize("location, kept", [("§1 line 5", True), ("line 2", True), ("docs/specs/x.md:13", False), ("§1", True)])
def test_record_refuses_out_of_scope_findings_and_stores_them(world, location, kept):
  spec, cid, rid = converged_spec(world, SPEC4); assert approve(world, spec, cid, "--yes")[0] == 0
  spec.write_text(SPEC4.replace("Text.", "Changed."), encoding="utf-8")
  rid2 = reopen(world, "spec", cid)
  line = f"design-1-1 | high | {location} | regression: no | claim"
  code, out = record(world, rid2, 1, "design", [line], cid)
  rnd = rjson(world, rid2, "round-1.json")
  assert code == 0 and rnd["out_of_scope"] == ([] if kept else [line]) and len(rnd["reviewers"]["design"]["findings"]) == int(kept)
  assert rnd["scope"] == [["neighbour", "(preamble)", 1, 2], ["changed", "## 1. Intent", 3, 6], ["neighbour", "## 2. Goals", 7, 10]]
  assert ("record: design-1-1 out of scope (## 3. Risks): not recorded" in out) is not kept
  assert ("out of scope: design-1-1" in (world.artifacts / "journal.md").read_text(encoding="utf-8")) is not kept


# ---------------------------------------------------------------- S24: `review settle --file`, all or nothing (U19)

def test_settle_file_is_all_or_nothing(world):
  spec, cid, rid = opened(world)
  rounds(world, rid, cid, [[F("design", 1, 1), F("design", 1, 2, "medium"), F("design", 1, 3, "low")]])
  path = world.repo.parent / "dispositions.txt"
  path.write_text("design-1-1 | fixed | moved\ndesign-1-2 | contested | wrong\ndesign-1-3 | declined | not worth it\n", encoding="utf-8")
  code, out = world.run("review", "settle", "--review", rid, "--file", str(path), "--owner", "--runcard", cid)
  assert code == 1 and "review settle: design-1-1 | fixed | moved: fixed needs changed bytes: nothing written" in out
  assert all(f["disposition"] is None for f in findings_of(rjson(world, rid, "round-1.json")))
  move(world, "spec", spec)
  assert world.run("review", "settle", "--review", rid, "--file", str(path), "--owner", "--runcard", cid) == (0, "design-1-1 fixed\ndesign-1-2 contested\ndesign-1-3 declined\n")
  assert [(f["disposition"], f["note"]) for f in findings_of(rjson(world, rid, "round-1.json"))] == [("fixed", "moved"), ("contested", "wrong"), ("declined", "not worth it")]
  path.write_text("design-1-9 | fixed | gone\n", encoding="utf-8")
  assert "review settle: design-1-9 | fixed | gone: no finding design-1-9" in world.run("review", "settle", "--review", rid, "--file", str(path), "--runcard", cid)[1]
  path.write_text("\ndesign-1-1 fixed\n", encoding="utf-8")
  assert "review settle: design-1-1 fixed: not <fid> | <disposition> | <note>: nothing written" in world.run("review", "settle", "--review", rid, "--file", str(path), "--runcard", cid)[1]


# ---------------------------------------------------------------- S25: the cap question names the scope (U19)

def test_cap_question_names_the_scope(world):
  spec, cid, rid = converged_spec(world); assert approve(world, spec, cid, "--yes")[0] == 0
  spec.write_text(SPEC.replace("Text.", "Changed."), encoding="utf-8")
  rid2 = reopen(world, "spec", cid)
  rounds(world, rid2, cid, [HIGH(n) for n in range(1, 6)])
  assert cap_question(world, rid2, cid)[1].startswith(f"## Q1 {rid2} is at its cap (scope: (preamble), ## 1. Intent, ## 2. Units)\n")


# ---------------------------------------------------------------- S26: the four rules and the scope prose (U19)

RULES_PROSE = [("skills/using-superegm/SKILL.md", n) for n in ("fresh session per phase", "never switches branches", "one worktree per handoff", "gh pr merge --admin", "after a plugin install or update")] + [
  ("skills/review-spec/SKILL.md", n) for n in ("[--scope auto|whole|<sections>]", "start on the branch you want the commits on", "superegm review scope --review <id>",
                                               "superegm review settle --review <id> --file <dispositions>", "out of scope")] + [
  ("skills/review-spec/references/review_loop.md", "findings only inside the changed sections and, on a neighbour, only on its fit with them; a finding on any other section is out of scope"),
  ("skills/review-spec/references/review_loop.md", "out_of_scope[]"), ("skills/review-spec/references/review_loop.md", "--file <dispositions>"),
  ("skills/wave/SKILL.md", "gh pr merge --admin"), ("skills/integrate/SKILL.md", "gh pr merge --admin")]

@pytest.mark.parametrize("path, needle", RULES_PROSE)
def test_the_four_rules_and_the_scope_prose(path, needle):
  assert needle in (ROOT / path).read_text(encoding="utf-8"), (path, needle)


# ---------------------------------------------------------------- review round 1 of PR #69 (U19): the branches the Steps leave untested

def test_scope_refusals_resume_and_settle_arguments(world):
  spec = spec_file(world); cid = card(world, spec, "integrate")
  code, out = world.run("review", "open", "--kind", "integrate", "--artifact", str(spec), "--reviewers", "design", "--scope", "whole", "--runcard", cid)
  assert code == 1 and "review open: --scope is refused for kind integrate" in out
  code, out = world.run("review", "open", "--kind", "integrate", "--artifact", str(spec), "--reviewers", "design", "--runcard", cid)
  assert code == 0, out
  rid = out.strip()
  assert rjson(world, rid)["scope"] is None
  code, out = world.run("review", "scope", "--review", rid, "--runcard", cid)
  assert code == 1 and f"review scope: {rid} is not a spec review" in out
  spec, cid, rid = opened(world)
  assert world.run("review", "open", "--kind", "spec", "--artifact", str(spec), "--reviewers", PANEL_OF["spec"], "--scope", "whole", "--runcard", cid) == (0, rid + "\n")
  assert rjson(world, rid)["scope"] == "auto"
  rounds(world, rid, cid, [HIGH(1)])
  path = world.repo.parent / "dispositions.txt"; path.write_text("design-1-1 | contested | wrong\n", encoding="utf-8")
  for extra in ([], ["--finding", "design-1-1"], ["--file", str(path), "--finding", "design-1-1", "--disposition", "contested"]):
    code, out = world.run("review", "settle", "--review", rid, *extra, "--owner", "--runcard", cid)
    assert code == 1 and "review settle: --file, or --finding with --disposition" in out, extra


def test_record_keeps_a_set_reviewers_raw_lines_paired_after_its_unit_filter(world):
  spec, cid, rid = converged_spec(world, SPEC4); assert approve(world, spec, cid, "--yes")[0] == 0
  spec.write_text(SPEC4.replace("Text.", "Changed."), encoding="utf-8")
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", str(spec), "--reviewers", "design,set", "--runcard", cid)
  assert code == 0, out
  rid2 = out.strip()
  other, refused = "set-1-1 | high | U42 line 5 | regression: no | another unit", "set-1-2 | high | line 13 | regression: no | risks"
  assert record(world, rid2, 1, "set", [other, refused], cid)[0] == 0
  rnd = rjson(world, rid2, "round-1.json")
  assert rnd["out_of_scope"] == [refused] and rnd["reviewers"]["set"]["findings"] == []


@pytest.mark.parametrize("approved", [True, False])
def test_record_keeps_a_line_past_the_specs_end(world, approved):
  if approved:
    spec, cid, rid = converged_spec(world, SPEC4); assert approve(world, spec, cid, "--yes")[0] == 0
    spec.write_text(SPEC4.replace("Text.", "Changed."), encoding="utf-8")
    rid = reopen(world, "spec", cid)
  else:
    spec, cid, rid = opened(world, text=SPEC4)
  line = "design-1-1 | high | skills/x.py:500 | regression: no | claim"
  code, out = record(world, rid, 1, "design", [line], cid)
  rnd = rjson(world, rid, "round-1.json")
  assert code == 0 and rnd["out_of_scope"] == [] and len(rnd["reviewers"]["design"]["findings"]) == 1 and "out of scope" not in out


# ---------------------------------------------------------------- U21: external-review ingest

from superegm import init

INGEST = {"severity_words": {"bug": "high", "issue": "medium", "nit": "low", "suggestion": "low"}, "human_role": "write"}

@pytest.mark.parametrize("ingest, expect", [
  (None, INGEST), ({"severity_words": {"bug": "blocker"}}, "ingest.severity_words must map words to high|medium|low"),
  ({"human_role": "owner"}, "ingest.human_role must be one of read, triage, write, maintain, admin")])
def test_ingest_config_key_and_the_init_sentence(world, ingest, expect):
  assert superegm.DEFAULT_CONFIG["ingest"] == INGEST and "ingest.severity_words" in init.STEPS and "ingest.human_role" in init.STEPS
  set_config(world, repo=REPO, **({"ingest": ingest} if ingest is not None else {}))
  if isinstance(expect, str):
    with pytest.raises(superegm.HandoffError, match=re.escape(expect)):
      superegm.load_config(world.repo)
    return
  assert superegm.load_config(world.repo)["ingest"] == expect


from superegm.review import read_threads, header

SHA, AT = "c" * 40, "2026-11-04T10:00:00Z"
rv = lambda rid, login, body, state="COMMENTED": {"id": rid, "user": {"login": login}, "body": body, "state": state, "commit_id": SHA, "submitted_at": AT}
cm = lambda cid, login, body, reply_to=None, review_id=None: {"id": cid, "user": {"login": login}, "body": body, "in_reply_to_id": reply_to,
  "pull_request_review_id": review_id, "path": "src/x.py", "line": 3, "commit_id": SHA, "created_at": AT}

def test_read_threads_keeps_roots_and_qualifying_review_bodies(world):
  world.gh.threads[70] = [cm(1, "devin-ai-integration[bot]", "**Bug**: off by one", review_id=10), cm(2, "alice", "agreed", reply_to=1), cm(3, "bob", "why?")]
  world.gh.reviews[70] = [rv(10, "devin-ai-integration[bot]", "2 issues found"), rv(11, "carol", "ship it", "APPROVED"),
                          rv(13, "owner", f"{header(1, SHA)}\n\nchange-review-1-1 | high | x | regression: no | y"), rv(14, "erin", "**Issue**: the retry never backs off")]
  threads = read_threads(REPO, 70, skip={3})
  assert [(t["id"], t["bot"], t["review_body"], t["path"], t["line"], t["commit_id"], t["created_at"]) for t in threads] == [(1, True, False, "src/x.py", 3, SHA, AT), (14, False, True, None, None, SHA, AT)]
  assert threads[0]["body"] == "**Bug**: off by one\n\nagreed" and threads[1]["login"] == "erin"


from superegm.review import collaborator_role, thread_severity

T = lambda body, login="devin-ai-integration[bot]", review_body=False: {"login": login, "bot": login.endswith("[bot]"), "body": body, "review_body": review_body}

@pytest.mark.parametrize("thread, role, severity", [
  (T("**Bug**: off by one"), None, "high"), (T("Found a **bug** here"), None, "high"), (T("[issue] the retry never backs off"), None, "medium"),
  (T("[Medium] the cap is off"), None, "medium"), (T("nit: typo"), None, "low"), (T("this is not an issue"), None, "low"), (T("2 issues found", review_body=True), None, "low"),
  (T("bug: the cap is off", "alice"), "write", "high"), (T("bug: the cap is off", "alice"), "none", "low"),
  (T("an issue in the loop", "alice", True), "admin", "medium"), (T("LGTM, merging tomorrow", "alice", True), "admin", "low")])
def test_thread_severity_rules_and_the_role_read(world, thread, role, severity):
  if role not in (None, "none"):
    world.gh.roles["alice"] = {"permission": "write", "role_name": role}
  seen = collaborator_role(REPO, "alice") if role else None
  assert seen == role and thread_severity(thread, {"ingest": INGEST}, seen) == severity


@pytest.mark.parametrize("answer, role", [({"permission": "write", "role_name": "security-reviewer"}, "write"),
                                          ({"permission": "nonsense", "role_name": "custom"}, "none")])
def test_a_custom_repository_role_reads_as_its_base_permission(world, answer, role):
  world.gh.roles["alice"] = answer
  assert collaborator_role(REPO, "alice") == role


from superegm.review import thread_line

@pytest.mark.parametrize("thread, severity, line", [
  ({"path": "src/x.py", "line": 3, "commit_id": "c" * 40, "body": "**Bug**: a | b\nmore"}, "high",
   "external:devin-ai-integration[bot]-2-7 | high | src/x.py:3 at ccccccc | regression: no | **Bug**: a / b"),
  ({"path": "README.md", "line": None, "commit_id": "c" * 40, "body": "ping @alice about secret-codename"}, "low",
   "external:alice-2-1 | low | README.md at ccccccc | regression: no | ping @ alice about s ecret-codename"),
  ({"path": None, "line": None, "commit_id": "c" * 40, "body": "x" * 300}, "low", "external:alice-2-1 | low | PR at ccccccc | regression: no | " + "x" * 200)])
def test_thread_line_form_and_masking(world, thread, severity, line):
  fid, config = line.split(" | ")[0], superegm.load_config(world.repo)   # banned_terms: ["(?i)secret-codename"]
  assert thread_line(fid.rsplit("-", 2)[0], 2, int(fid.rsplit("-", 1)[1]), thread, severity, config) == line
  assert superegm.scan_text(line, config, "comment", label="comment") == []


@pytest.mark.parametrize("kind, code", [("head", 0), ("spec", 0), ("plan", 1)])
def test_record_takes_an_external_reviewer_outside_the_panel_and_appends(world, kind, code):
  spec, cid, rid = opened(world, kind)
  ext, sha = "external:devin-ai-integration[bot]", A if kind == "head" else None
  kind == "head" and head_round(world, 1, "posted", cid, "clean")
  if code:
    assert f"review record: {ext} is accepted on a head or a spec only" in record(world, rid, 1, ext, [F(ext, 1, 1)], cid, sha=sha)[1]
    return
  for reviewer in PANEL_OF[kind].split(","):
    assert record(world, rid, 1, reviewer, [], cid, sha=sha)[0] == 0
  assert record(world, rid, 1, ext, [F(ext, 1, 1)], cid, sha=sha)[0] == 0
  assert settle(world, rid, f"{ext}-1-1", "contested", cid, "--owner")[0] == 0
  assert record(world, rid, 1, ext, [F(ext, 1, 2, "medium")], cid, sha=sha)[0] == 0
  rnd = rjson(world, rid, "round-1.json")
  assert [(f["id"], f["disposition"]) for f in rnd["reviewers"][ext]["findings"]] == [(f"{ext}-1-1", "contested"), (f"{ext}-1-2", None)]
  assert rnd["what_ran"] == "completed" and status(world, rid, cid)[0] == 3
