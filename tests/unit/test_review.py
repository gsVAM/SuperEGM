# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03); the review loop and approve-spec (U04).

"""U04: the review loop (`review open|record|settle|status|rule`) and `approve-spec` (spec section 8)."""

import hashlib, json, re, subprocess
from pathlib import Path
import pytest
from superegm import store, atomic_write
from superegm.review import parse_findings
from superegm.review import derive_what_ran
from superegm.review import PANEL_OF


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
SPEC = ("# Sample\n\n## 1. Intent\n\nText.\n\n## 2. Units\n\n| Unit | Scope | Blocked by | Size |\n"
        "| --- | --- | --- | --- |\n| U01 | a thing | — | S |\n")
SLUG, HID, A = "2026-11-03-sample-design", "sample-abc123", "a" * 64
SKILL_OF = {"spec": "review-spec", "integrate": "integrate", "plan": "review-plan", "head": "wave"}

def git(world, *args):
  return subprocess.run(["git", "-C", str(world.repo), *args], check=True, capture_output=True, text=True).stdout.strip()

def spec_file(world, text=SPEC):
  path = world.repo / "docs" / "specs" / f"{SLUG}.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")
  return path.resolve()

def seed_handoff(world, spec, hid=HID, **extra):
  """state.json as approve-spec and graph leave it: the handoff id and the spec the plan and head cards are on."""
  state = {"units": {"U07": {}}, "design": {"path": str(spec)}, **extra}
  atomic_write(store(world.repo).path("state"), state | ({"handoff_id": hid} if hid else {}))

def card(world, artifact, skill="review-spec", mode=None, parent=None):
  argv = ["runcard", "open", "--skill", skill, "--artifact", str(artifact)]
  argv += ["--mode", mode] if mode else []
  argv += ["--parent", parent] if parent else []
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
                        reviewers or PANEL_OF[kind], "--astra", astra, "--runcard", cid)
  assert code == 0, out
  return spec, cid, out.strip()

def rpath(world, rid, *parts):
  return store(world.repo).path("reviews", rid, *parts)

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
  path = store(world.repo).path("foreman", unit)
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
  lane = astra == "on" and kind != "head"
  assert (review["kind"], review["cycle"], review["runcard"], review["artifact"]) == (kind, 1, cid, artifact)
  assert review["reviewers"] == reviewers.split(",") + (["astra"] if lane else [])
  assert review["converged"] == "no" and review["converged_round"] is None and review["rulings"] == []


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
  assert opened(world, text=SPEC.replace("Text.", "Changed."))[2] == f"spec-{SLUG}-c3"   # a spec change after convergence


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
    assert record(world, rid, 1, reviewer, found, cid, sha=A)[0] == 0
  assert [f["id"] for f in rjson(world, rid, "round-1.json")["reviewers"]["set"]["findings"]] == ["set-2-1", "set-2-3"]
  assert rjson(world, rid, "round-1.json")["what_ran"] == "completed"
  assert "review record: foreman is accepted on a head only" in record(world, rid, 1, "foreman", [F("foreman", 1, 1)], cid, sha=A)[1]
  _, wcid, hid = opened(world, "head")
  head_round(world, 1, "posted", wcid, "revise")
  assert record(world, hid, 1, "foreman", [F("foreman", 1, 1)], wcid, sha=A)[0] == 0
  assert rjson(world, hid, "round-1.json")["what_ran"] == "not run (change-review: no record)"   # foreman never counts
  assert record(world, hid, 1, "change-review", [], wcid, sha=A)[0] == 0
  assert rjson(world, hid, "round-1.json")["what_ran"] == "completed"


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
  ("plan", [], dict(n=1, reviewer="readiness"), "review record: --sha256 required for kind plan"),
  ("plan", [dict(n=1, reviewer="readiness", sha=A)], dict(n=1, reviewer="set", sha="b" * 64), "review record: sha256 differs from the round's"),
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
  ("spec", None, "design", "high", "§1", "design-1-1", "fixed", (), "design-1-1 fixed"),
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


# ---------------------------------------------------------------- S9: `review status`

def s_unopened(w, c, r): return f"spec-{SLUG}-c9"
def s_open_only(w, c, r): return r
def s_clean(w, c, r): rounds(w, r, c, [[]]); return r
def s_low_only(w, c, r): rounds(w, r, c, [[F("design", 1, 1, "low")]]); return r
def s_unsettled_high(w, c, r): rounds(w, r, c, [HIGH(1)]); return r
def s_settled(w, c, r): rounds(w, r, c, [HIGH(1)]); assert settle(w, r, "design-1-1", "fixed", c)[0] == 0; return r
def s_regression(w, c, r):
  rounds(w, r, c, [HIGH(1), [F("design", 2, 1, reg="yes")]]); assert settle(w, r, "design-2-1", "fixed", c)[0] == 0; return r
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
  (s_settled, False, 0, "round 1: clean, regressions 0, converged yes"),
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
  rec = approval(world)
  assert (rec["path"], rec["sha256"], rec["review"], rec["runcard"]) == (str(spec), sha, rid, cid)
  assert rec["commit"] == git(world, "rev-parse", "HEAD") and rec["handoff_id"] == f"2026-11-03-sample-de-{sha[:6]}"
  assert rec["amended"] == [] and rec["voided_by"] is None and rec["approved_at"]
  assert git(world, "log", "-1", "--format=%s") == f"superegm: approve {SLUG} at review {rid}"
  names = git(world, "show", "--name-only", "--format=", "HEAD").splitlines()
  assert f"docs/specs/{SLUG}.md" in names and "notes.txt" not in names and "?? notes.txt" in git(world, "status", "--porcelain")
  code, out = approve(world, spec, cid, "--leavemealone")
  assert code == 0 and "approval recorded" in out and "Approve `" not in out


# ---------------------------------------------------------------- S13: approve-spec refusals

def a_bytes_differ(w):
  spec, cid, rid = converged_spec(w); spec.write_text(SPEC + "\nmore\n", encoding="utf-8"); return spec, cid
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


# ---------------------------------------------------------------- S14: the handoff id

@pytest.mark.parametrize("carried,extra,keeps", [
  (True, {}, True),
  (True, {"closed_at": "2026-11-03T00:00:00Z"}, False),
  (False, {}, False),
])
def test_handoff_id_copy_rule(world, carried, extra, keeps):
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  first = approval(world)["handoff_id"]
  atomic_write(store(world.repo).path("state"), ({"handoff_id": first} if carried else {}) | extra)
  spec2, cid2, rid2 = converged_spec(world, SPEC.replace("Text.", "Changed."))
  assert rid2.endswith("-c2") and approve(world, spec2, cid2, "--yes")[0] == 0
  second = approval(world)["handoff_id"]
  assert (second == first) is keeps
  assert second.endswith(hashlib.sha256(spec2.read_bytes()).hexdigest()[:6]) is not keeps
