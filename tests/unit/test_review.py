# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03); the review loop and approve-spec (U04).

"""U04: the review loop (`review open|record|settle|status|rule`) and `approve-spec`; EGM's approve tests moved here by U03
stay until S12 replaces them."""

import hashlib, json, re, subprocess
from pathlib import Path
import pytest
from superegm import store, atomic_write
from superegm.review import parse_findings
from superegm.review import PANEL_OF

from conftest import DESIGN, git as conftest_git   # S2's `git(world, *args)` fixture shadows conftest's; the EGM tests go at S12


def test_approve_checks_and_records(world):
  design = world.repo / "docs/designs/sample.md"
  code, out = world.run("approve-spec", "--design", design)
  assert code == 0 and "Approve `" in out and "Options: Approve | Stop" in out
  code, out = world.run("approve-spec", "--design", design, "--yes")
  assert code == 0
  record = json.loads((world.artifacts / "approvals/sample.json").read_text(encoding="utf-8"))
  assert record["path"] == str(design) and record["handoff_id"].startswith("sample-")
  design.write_text(DESIGN + "\nchanged\n", encoding="utf-8")
  code, out = world.run("approve-spec", "--design", design)
  assert code == 1 and "tracked but not clean" in out

  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1 and "spec changed since the approval: run approve-spec again" in out
  conftest_git(["checkout", "--", "docs/designs/sample.md"], world.repo)
  (world.repo / "docs/designs/plain.md").write_text("# Plain\n\nNo plan.\n", encoding="utf-8")
  conftest_git(["add", "-A"], world.repo)
  conftest_git(["commit", "-qm", "plain"], world.repo)
  plain = world.repo / "docs/designs/plain.md"
  code, out = world.run("approve-spec", "--design", plain, "--runcard", world.open_card("review-spec", plain), card=None)
  assert code == 1 and "Detailed Implementation Plan" in out and "egm-draft" in out


def test_approve_refuses_an_untracked_or_ignored_design(world):
  """A clean `git status -- <path>` says nothing about an ignored file."""
  design = world.repo / "docs/designs/ignored.md"
  design.write_text(DESIGN, encoding="utf-8")
  (world.repo / ".gitignore").write_text("docs/designs/ignored.md\n", encoding="utf-8")
  code, out = world.run("approve-spec", "--design", design, "--runcard", world.open_card("review-spec", design), card=None)
  assert code == 1 and "not tracked by git" in out


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
