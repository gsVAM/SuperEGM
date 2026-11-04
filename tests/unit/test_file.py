# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the filing on the confirmed write list under converged plan reviews (U07); EGM's moved tests rewritten to that form.

"""The filing (spec section 10): `gate --pass` on converged plan reviews, the dry run of the
unfiled units, `apply` on the confirmed write list with `filings[]` and `base_at_start`,
marker recovery, the tracking rewrite, `verify` over the union of every filing, the
leavemealone journal line and the `file` skill body."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from superegm import store, atomic_write, spec_slug
from conftest import HELPER, REPO, make_world, make_repo, make_plan, set_config, state_of, git, converge as converge_review

ROOT = Path(__file__).resolve().parents[2]
PKG = "skills/plan/scripts/superegm"
SLUG = "2026-11-03-sample-design"          # the spec is docs/specs/<SLUG>.md, H1 `# Sample design`
ROWS = [("U01", "Queue", "none"), ("U02", "Worker", "U01"), ("U03", "Admin endpoint", "U02")]  # (unit, title, blocked by)


def spec_text(rows) -> str:
  """`# Sample design`, `## 1. Intent` at lines 3-4, the `## Units` table of `rows` as the last H2."""
  table = "\n".join(f"| {uid} | {title} | {blocked} |" for uid, title, blocked in rows)
  return ("# Sample design\n\n## 1. Intent\nQueued webhook delivery with an admin listing.\n\n"
          f"## Units\n\n| Unit | Title | Blocked by |\n| --- | --- | --- |\n{table}\n")


def unit_section(uid, title, blocked, issue=None) -> str:
  """A unit section in the section 9.1 grammar with one Step; `issue` adds the optional `Issue` row."""
  low = uid.lower()
  issue_row = f"\n| Issue | #{issue} |" if issue is not None else ""
  return f"""### {uid}: {title}
| Field | Value |
| --- | --- |
| Objective | {title} exists. |
| Scope paths | `src/{low}.ts` (create), `tests/{low}.test.ts` (create) |
| Design range | `docs/specs/{SLUG}.md:3-4 (## 1. Intent)` |
| Blocked by | {blocked} |
| Shared files | none |
| Risk | low: new module |
| Size | S |{issue_row}

Interfaces
- Produces: {low}() -> void

Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `npm test -- tests/{low}.test.ts` — the {low} case passes
3. CI green on the head

Review focus (this unit)
- {uid}: the module — {low}() exists; pinned by `{low}_exists`

Steps
1. Write the failing test `{low}_exists` in `tests/{low}.test.ts`:
   ```ts
   test("{low}_exists", () => expect({low}()).toBeUndefined());
   ```
   Implement `{low}()` in `src/{low}.ts`.

Decide before build
- none
"""


def plan_text(spec, sections) -> str:
  """`# Handoff plan: Sample design`, the `Design:` line, the template and units H2s, `## Global constraints` last."""
  return (f"# Handoff plan: Sample design\n\nDesign: `{spec}`\n\n## 1. Issue template\n\n"
          "(the layout of references/issue_template.md)\n\n## 2. Units\n\n" + "\n".join(sections)
          + "\n## Global constraints\n- TypeScript strict mode, no new dependencies\n")


def approve(world, rows=ROWS[:2], amended=()):
  """Write and commit the spec; record its approval (U03's schema) and return (spec, handoff_id)."""
  spec = world.repo / f"docs/specs/{SLUG}.md"
  spec.parent.mkdir(parents=True, exist_ok=True)
  spec.write_text(spec_text(rows), encoding="utf-8")
  git(["add", "-A"], world.repo)
  git(["commit", "-qm", f"spec with {len(rows)} units"], world.repo)
  sha = hashlib.sha256(spec.read_bytes()).hexdigest()
  handoff_id = f"{spec_slug(spec)}-{(amended[0] if amended else sha)[:6]}"
  record = {"path": str(spec), "sha256": sha, "commit": git(["rev-parse", "HEAD"], world.repo).strip(),
            "runcard": "review-spec-0001", "review": f"spec-{spec_slug(spec)}-c1", "approved_at": "2026-11-03T00:00:00Z",
            "amended": list(amended), "voided_by": None, "handoff_id": handoff_id}
  path = world.artifacts / "approvals" / f"{spec_slug(spec)}.json"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(record), encoding="utf-8")
  return spec, handoff_id


def open_card(world, skill, artifact, mode=None) -> str:
  argv = ["runcard", "open", "--skill", skill, "--artifact", artifact] + (["--mode", mode] if mode else [])
  code, out = world.run(*argv, card=None)
  assert code == 0, out
  return out.strip()


def close_card(world, card) -> None:
  assert world.run("runcard", "close", card, card=None)[0] == 0


def graphed(world, spec, plan) -> None:
  """`graph --plan` under a plan card, closed after."""
  card = open_card(world, "plan", spec)
  code, out = world.run("graph", "--plan", plan, "--runcard", card)
  assert code == 0, out
  close_card(world, card)


def planned(world, units=("U01", "U02")):
  """approve; the plan outside the store and the repository; `graph --plan`; (spec, plan, handoff_id)."""
  rows = [r for r in ROWS if r[0] in units]
  spec, handoff_id = approve(world, rows)
  plan = world.artifacts.parent / "plan.md"
  plan.write_text(plan_text(spec, [unit_section(*r) for r in rows]), encoding="utf-8")
  graphed(world, spec, plan)
  return spec, plan, handoff_id


def converge(world, uid, cycle=1, sha=None) -> None:
  """What `review-plan` leaves for a converged unit, at its body hash unless `sha` says otherwise."""
  units = json.loads((world.artifacts / "handoff_units.json").read_text(encoding="utf-8"))["units"]
  converge_review(world.artifacts, state_of(world)["handoff_id"], uid, sha or units[uid]["body_sha256"], cycle)


def gated(world, units=("U01", "U02"), mode=None):
  """planned; every unit converged; a file card; `gate --pass`; (spec, plan, handoff_id, card)."""
  spec, plan, handoff_id = planned(world, units)
  for uid in units:
    converge(world, uid)
  card = open_card(world, "file", spec, mode)
  code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", card)
  assert code == 0, out
  return spec, plan, handoff_id, card


def dry_run(world, **kw):
  spec, plan, handoff_id, card = gated(world, **kw)
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 0, out
  return spec, plan, handoff_id, card


def applied(world, **kw):
  spec, plan, handoff_id, card = dry_run(world, **kw)
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 0, out
  world.gh.calls.clear()
  return spec, plan, handoff_id, card


def issue_edit_handler(gh) -> None:
  """The fake has no `gh issue edit --body-file` form: serve it here, every other `issue` form as before."""
  def handler(args, cwd, token=None):
    if args[1] == "edit" and "--body-file" in args:
      gh.assert_write()
      gh.issues[int(args[2])]["body"] = Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8")
      return 0, "", ""
    return gh.do_issue(args)
  gh.extend("issue", handler)


def later_filing(world):
  """A filing applied and closed; the spec amended with U03 and re-approved; U03 planned and converged;
  a new file card gated and dry-run. Returns (spec, card, the state after the first filing)."""
  spec, plan, handoff_id, card = applied(world)
  close_card(world, card)
  first = state_of(world)
  issue_edit_handler(world.gh)
  approve(world, ROWS, amended=(hashlib.sha256(spec.read_bytes()).hexdigest(),))
  text = plan.read_text(encoding="utf-8")
  plan.write_text(text.replace("## Global constraints", unit_section(*ROWS[2]) + "\n## Global constraints"), encoding="utf-8")
  graphed(world, spec, plan)
  converge(world, "U03")
  card = open_card(world, "file", spec)
  code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", card)
  assert code == 0, out
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 0, out
  world.gh.calls.clear()
  return spec, card, first


@pytest.mark.parametrize("case, expected", [
    ("unreviewed", "gate: U02 plan review not converged"),
    ("stale", "gate: U02 body differs from its converged round"),
    ("converged", None)])
def test_gate_pass_requires_a_converged_review_at_the_body_hash(world, case, expected):
  spec, plan, handoff_id = planned(world)
  converge(world, "U01")
  if case == "stale":
    converge(world, "U02", sha="0" * 64)
  elif case == "converged":
    converge(world, "U02")
  card = open_card(world, "file", spec)
  code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", card)
  state = state_of(world)
  if expected:
    assert code == 1 and expected in out, out
    assert "gate_plan_sha256" not in state and "gate" not in state
  else:
    assert code == 0 and "gate passed" in out, out
    assert re.fullmatch(r"[0-9a-f]{64}", state["gate_plan_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", state["gate_bodies_sha256"])
    assert state["gate"]["passed"] == "converged" and state["gate"]["units"] == ["U01", "U02"]


REMOVED = ["--accept", "--reviewed", "--readiness", "--what-ran", "what_ran", "What ran", "Readiness", "Stage 10",
           "gate_unreviewed", "deferred", "EGM handoff", ".egm_body_", "handoff_state.json", ".egm/",
           "Codex", "handoff_summary.md", "egm-wave", "synthesizer", "readiness test"]


@pytest.mark.parametrize("path", [f"{PKG}/gate.py", f"{PKG}/dry_run.py", f"{PKG}/apply.py", f"{PKG}/verify.py",
                                  "skills/file/SKILL.md"])
def test_removed_forms_are_gone_from_the_filing_files(world, path):
  text = (ROOT / path).read_text(encoding="utf-8")
  assert not [term for term in REMOVED if term in text], path
  with pytest.raises(SystemExit) as stop:  # `gate --accept` is not a flag any more (section 3.1)
    world.run("gate", "--accept", "--spec", world.repo / f"docs/specs/{SLUG}.md", "--runcard", "rc-none")
  assert stop.value.code == 2


def test_dry_run_records_the_confirmed_list_of_unfiled_units_with_three_reads(world):
  spec, plan, handoff_id, card = gated(world)
  repo = world.gh.repo
  world.gh.calls.clear()
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 0, out
  text = (world.artifacts / "handoff_dryrun.md").read_text(encoding="utf-8")
  assert "3 issues (1 tracking, 2 units), 2 sub-issue links, 1 blocked-by links" in text
  for label in ("superegm:unit", "superegm:tracking", "superegm:stopped", "superegm:wave-1", "superegm:wave-2",
                f"superegm:handoff-{handoff_id[-6:]}"):
    assert f"- `{label}`: create" in text, label
  assert "Confirmed write list sha256" in text
  assert [c[:2] for c in world.gh.calls] == [["auth", "status"], ["api", f"repos/{repo}"], ["api", f"repos/{repo}/labels"]]
  state = state_of(world)
  assert state["confirmed"]["sha256"] == state["confirmed_sha256"] and "filings" not in state
  writes = state["confirmed"]["writes"]
  assert writes[0] == ["repo", repo] and writes[1] == ["gate", state["gate_plan_sha256"], state["gate_bodies_sha256"]]
  assert [w[1] for w in writes if w[0] == "issue"] == ["tracking", "U01", "U02"]
  u02 = next(w for w in writes if w[:2] == ["issue", "U02"])
  assert u02[4].startswith(f"<!-- superegm:handoff={handoff_id} unit=U02 spec=")
  assert "#<U01>" in u02[4] and "#<tracking>" in u02[4]
  # refused after a change to the store's plan copy: the gate must run again
  copy = world.artifacts / "handoff_plan.md"
  copy.write_text(copy.read_text(encoding="utf-8").replace("low: new module", "low: a new module", 1), encoding="utf-8")
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 1 and "changed after the gate" in out, out


def test_dry_run_refuses_101_units_missing_extra_and_warns_above_450(world):
  spec, plan, handoff_id, card = gated(world)
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"], labels={"extra": ["needs-triage"]})
  assert world.run("gate", "--pass", "--spec", spec, "--runcard", card)[0] == 0  # the labels are in the bodies' pair
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 1 and "create the label `needs-triage`" in out
  world.gh.labels["needs-triage"] = {"name": "needs-triage"}
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 0 and "3 issues" in out
  dryrun = (world.artifacts / "handoff_dryrun.md").read_text(encoding="utf-8")
  assert "Labels: superegm:handoff-" in dryrun and "needs-triage" in dryrun
  big = [unit_section(f"U{n:02d}", f"Unit {n}",
                      "none" if n == 1 else f"U{n - 1:02d}" if n == 2 else f"U{n - 1:02d}, U{n - 2:02d}")
         for n in range(1, 102)]

  def gate_big(sections):
    plan.write_text(plan_text(spec, sections), encoding="utf-8")
    graphed(world, spec, plan)
    for n in range(1, len(sections) + 1):
      converge(world, f"U{n:02d}")
    code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", card)
    assert code == 0, out
  gate_big(big)
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 1 and "split the handoff" in out
  gate_big(big[:100])
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 0, out
  text = (world.artifacts / "handoff_dryrun.md").read_text(encoding="utf-8")
  assert "WARNING" in text and "--max-writes" in text


def test_apply_appends_the_filing_and_base_at_start_before_its_first_write(world):
  spec, plan, handoff_id, card = dry_run(world)
  world.gh.read_only = True  # the fake raises on the first write
  with pytest.raises(AssertionError, match="write in a read-only run"):
    world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  state = state_of(world)
  assert [f["sha256"] for f in state["filings"]] == [state["confirmed_sha256"]]
  assert state["filings"][0]["writes"] == state["confirmed"]["writes"]
  assert state["base_at_start"] == git(["rev-parse", "main"], world.repo).strip()  # the config's default `base`
  assert not world.gh.issues and all(s != "done" for s in state["labels"].values())
  journal = (world.artifacts / "journal.md").read_text(encoding="utf-8")
  assert f"filing {state['confirmed_sha256'][:12]}: 2 units (U01, U02)" in journal
  assert "Create: automatic" not in journal


@pytest.mark.parametrize("case, expected", [
    ("no-yes", "--yes"),
    ("stale-review", "apply: U02 body differs from its converged round"),
    ("plan-drift", "changed after the gate"),
    ("list-drift", "the write list changed since the dry run")])
def test_apply_refusals(world, case, expected):
  spec, plan, handoff_id, card = dry_run(world)
  argv = ["apply", "--spec", spec, "--runcard", card] + ([] if case == "no-yes" else ["--yes"])
  if case == "stale-review":
    converge(world, "U02", sha="0" * 64)
  if case == "plan-drift":
    copy = world.artifacts / "handoff_plan.md"
    copy.write_text(copy.read_text(encoding="utf-8").replace("low: new module", "low: a new module", 1), encoding="utf-8")
  if case == "list-drift":
    state = state_of(world)
    state["confirmed"]["writes"][0] = ["repo", "someone/else"]
    atomic_write(world.artifacts / "state.json", state)
  code, out = world.run(*argv)
  assert code == 1 and expected in out, out
  assert not any(c[0] in ("label", "issue") for c in world.gh.calls)
  assert "filings" not in state_of(world) and "base_at_start" not in state_of(world)


def test_apply_creates_labels_issues_and_links_in_order_and_a_rerun_writes_nothing(world):
  spec, plan, handoff_id, card = dry_run(world)
  world.gh.calls.clear()
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 0, out
  gh, six = world.gh, handoff_id[-6:]
  assert [c[2] for c in gh.calls if c[0] == "label"] == [
      "superegm:unit", "superegm:tracking", f"superegm:handoff-{six}", "superegm:stopped", "superegm:wave-1", "superegm:wave-2"]
  assert "bug" in gh.labels and all("--force" not in c for c in gh.calls)
  titles = [c[c.index("--title") + 1] for c in gh.calls if c[:2] == ["issue", "create"]]
  assert titles == ["Build: Sample design", "U01: Queue", "U02: Worker"]
  assert gh.issues[1]["labels"] == [f"superegm:handoff-{six}", "superegm:tracking"]
  assert gh.issues[2]["labels"] == [f"superegm:handoff-{six}", "superegm:unit", "superegm:wave-1"]
  assert gh.issues[1]["body"].startswith(f"<!-- superegm:handoff={handoff_id} unit=tracking spec=")
  body = gh.issues[3]["body"]
  assert body.startswith(f"<!-- superegm:handoff={handoff_id} unit=U02 spec=")
  assert "#2" in body and "Part of #1" in body and "#<" not in body
  assert gh.sub_issues[1] == [gh.issues[2]["id"], gh.issues[3]["id"]] and gh.blocked_by == {3: [gh.issues[2]["id"]]}
  state = state_of(world)
  assert state["tracking"]["number"] == 1 and state["tracking"]["filing"] == state["confirmed_sha256"]
  assert state["units"]["U02"]["number"] == 3 and state["links"]["blocked:U02<-U01"] == "done"
  assert state["verify"]["complete"] is True and state["verify"]["problems"] == []
  assert state["verify"]["checked"] == "12 of 12" and state["verify"]["sha256"] == state["confirmed_sha256"]
  gh.calls.clear()
  assert world.run("apply", "--spec", spec, "--runcard", card, "--yes")[0] == 0
  assert not any(c[0] == "label" or c[:2] in (["issue", "create"], ["issue", "edit"]) or "POST" in c for c in gh.calls)
  assert len(state_of(world)["filings"]) == 1


@pytest.mark.parametrize("mode, journaled", [("leavemealone", True), (None, False)])
def test_apply_journals_the_automatic_create_in_leavemealone_mode(world, mode, journaled):
  spec, plan, handoff_id, card = applied(world, mode=mode)
  journal = (world.artifacts / "journal.md").read_text(encoding="utf-8")
  assert (journal.count("Create: automatic (leavemealone)") == 1) is journaled, journal
  assert world.run("apply", "--spec", spec, "--runcard", card, "--yes")[0] == 0  # a resume journals nothing again
  assert (world.artifacts / "journal.md").read_text(encoding="utf-8").count("Create: automatic (leavemealone)") == int(journaled)


def test_apply_state_saved_after_each_write_and_422_link_reread(world):
  spec, plan, handoff_id, card = dry_run(world)
  world.gh.link_422_once.add(("sub", 1))
  saves = []
  original = world.ns["save_state"]

  def spy(folder, state):
    saves.append(json.dumps(state, sort_keys=True))
    original(folder, state)
  world.ns["save_state"] = spy
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 0, out
  assert len(saves) >= 13
  state = state_of(world)
  assert state["links"]["sub:U01"] == "done" and all(v == "done" for v in state["links"].values())


def test_apply_rate_limit_exhaustion_exits_nonzero_with_resume_message(world):
  spec, plan, handoff_id, card = dry_run(world)
  world.gh.rate_limit_hits = 5
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 1 and "rate limited: resume with `apply --yes` after" in out
  assert world.sleeps.count(60) == 3
  state = state_of(world)
  assert state["labels"]["superegm:unit"] == "done" and not state.get("tracking", {}).get("number")


def test_apply_max_writes_resumes_in_bounded_calls(world):
  spec, plan, handoff_id, card = dry_run(world)
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes", "--max-writes", 2)
  assert code == 0 and "stopped after 2 writes" in out
  state = state_of(world)
  assert state["verify"]["complete"] is False
  assert sorted(n for n, s in state["labels"].items() if s == "done") == ["superegm:tracking", "superegm:unit"]
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes", "--max-writes", 2)
  assert code == 0 and "stopped after 2 writes" in out
  state = state_of(world)
  assert sum(1 for s in state["labels"].values() if s == "done") == 4
  code, out = world.run("status", "--plan", plan, "--runcard", open_card(world, "wave", spec))
  assert code == 1 and "not fully created and verified" in out
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes", "--max-writes", 50)
  assert code == 0 and state_of(world)["verify"]["complete"] is True


def test_a_later_filing_rewrites_the_tracking_issue_and_verify_checks_the_union(world):
  spec, card, first = later_filing(world)
  gh = world.gh
  dryrun = (world.artifacts / "handoff_dryrun.md").read_text(encoding="utf-8")
  assert "### issue U03" in dryrun and "### issue tracking" in dryrun and "### issue U01" not in dryrun
  assert "Tracking issue #1 will be rewritten" in dryrun
  before = {n: dict(i) for n, i in gh.issues.items()}
  assert "U03" not in before[1]["body"]
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 0, out
  assert [c[2] for c in gh.calls if c[0] == "label"] == ["superegm:wave-3"]
  assert [c[c.index("--title") + 1] for c in gh.calls if c[:2] == ["issue", "create"]] == ["U03: Admin endpoint"]
  assert [c[2] for c in gh.calls if c[:2] == ["issue", "edit"]] == ["1"]
  assert "U03" in gh.issues[1]["body"] and "Admin endpoint" in gh.issues[1]["body"]
  assert gh.issues[2] == before[2] and gh.issues[3] == before[3]  # filed units are frozen: never touched
  state = state_of(world)
  u01, u03 = state["units"]["U01"], state["units"]["U03"]
  assert u03["number"] == 4 and gh.blocked_by[4] == [gh.issues[3]["id"]] and gh.sub_issues[1][-1] == gh.issues[4]["id"]
  assert gh.issues[4]["body"].startswith(f"<!-- superegm:handoff={first['handoff_id']} unit=U03 spec=")
  assert len(state["filings"]) == 2 and state["filings"][1]["sha256"] == state["confirmed_sha256"]
  assert {w[1] for w in state["filings"][1]["writes"] if w[0] == "issue"} == {"tracking", "U03"}
  assert state["filings"][0] == first["filings"][0] and state["base_at_start"] == first["base_at_start"]
  assert state["tracking"]["filing"] == state["confirmed_sha256"]
  assert state["verify"]["complete"] is True and state["verify"]["problems"] == [] and state["verify"]["checked"] == "16 of 16"
  code, out = world.run("verify", "--spec", spec, "--runcard", card)
  assert code == 0 and "MISMATCH" not in out and "16 of 16" in out, out
  gh.issues[u01["number"]]["body"] += "\nedited by hand"          # filed by the first list
  gh.issues[u01["number"]]["labels"].remove("superegm:unit")
  gh.blocked_by.setdefault(u01["number"], []).append(u03["id"])   # a link no filing names
  code, out = world.run("verify", "--spec", spec, "--runcard", card)
  assert code == 1, out
  problems = state_of(world)["verify"]["problems"]
  assert any(f"body of #{u01['number']} (U01)" in p for p in problems)
  assert any(f"labels of #{u01['number']} (U01)" in p and "superegm:unit" in p for p in problems)
  assert any(f"obsolete blocked-by link on #{u01['number']} (U01)" in p for p in problems)
  assert not any("obsolete sub-issue" in p for p in problems)      # the union keeps the first filing's sub-issue links
  assert not any("tracking" in p for p in problems)
  assert state_of(world)["verify"]["complete"] is True and state_of(world)["verify"]["sha256"] == state["confirmed_sha256"]


FAKE_GH = '''#!/usr/bin/env python3
import json, sys, pathlib
log = pathlib.Path(sys.argv[0]).with_name("gh.log")
state_file = pathlib.Path(sys.argv[0]).with_name("gh_state.json")
state = json.loads(state_file.read_text()) if state_file.exists() else {"issues": {}, "labels": [], "subs": {}, "blocked": {}}
args = sys.argv[1:]
log.open("a").write(json.dumps(args) + "\\n")
def save(): state_file.write_text(json.dumps(state))
def out(x): print(x if isinstance(x, str) else json.dumps(x))
if args[0] in ("api", "auth") and "-R" in args: sys.exit("unknown shorthand flag: 'R' in -R")
if args[0] == "auth": out("Logged in"); sys.exit(0)
if args[0] == "label": state["labels"].append(args[2]); save(); out("ok"); sys.exit(0)
if args[0] == "issue" and args[1] == "create":
    n = str(len(state["issues"]) + 1); body = pathlib.Path(args[args.index("--body-file") + 1]).read_text()
    labels = [args[i + 1] for i, a in enumerate(args) if a == "--label"]
    state["issues"][n] = {"number": int(n), "id": 1000 + int(n), "body": body, "labels": labels}; save()
    out("https://github.com/example-org/webhooks/issues/" + n); sys.exit(0)
if args[0] == "issue" and args[1] == "view":
    i = state["issues"][args[2]]; out({"body": i["body"], "labels": [{"name": l} for l in i["labels"]]}); sys.exit(0)
ep = next(a for i, a in enumerate(args[1:], 1) if not a.startswith("-") and args[i - 1] not in ("-X", "-F", "-f", "-q"))
if ep == "repos/example-org/webhooks": out({"push": True}); sys.exit(0)
if ep == "repos/example-org/webhooks/labels": out([[{"name": l} for l in state["labels"]]]); sys.exit(0)
if ep.startswith("repos/example-org/webhooks/issues?"): out([[]]); sys.exit(0)
import re
m = re.fullmatch(r"repos/example-org/webhooks/issues/(\\d+)", ep)
if m: out(state["issues"][m.group(1)]); sys.exit(0)
m = re.fullmatch(r"repos/example-org/webhooks/issues/(\\d+)/sub_issues", ep)
if m and "POST" in args:
    f = [a for a in args if a.startswith("sub_issue_id=")][0].split("=")[1]
    assert f.isdigit(); state["subs"].setdefault(m.group(1), []).append(int(f)); save(); out("HTTP/2.0 201 Created\\n\\n{}"); sys.exit(0)
if m: out([[{"id": i, "number": i - 1000} for i in state["subs"].get(m.group(1), [])]]); sys.exit(0)
m = re.fullmatch(r"repos/example-org/webhooks/issues/(\\d+)/dependencies/blocked_by", ep)
if m and "POST" in args:
    f = [a for a in args if a.startswith("issue_id=")][0].split("=")[1]
    assert f.isdigit(); state["blocked"].setdefault(m.group(1), []).append(int(f)); save(); out("HTTP/2.0 201 Created\\n\\n{}"); sys.exit(0)
if m: out([[{"id": i, "number": i - 1000} for i in state["blocked"].get(m.group(1), [])]]); sys.exit(0)
sys.exit("unexpected: " + " ".join(args))
'''


@pytest.mark.skipif(os.name == "nt", reason="a fake gh script on PATH needs a POSIX shell-free exec")
def test_subprocess_command_shape_with_fake_gh_on_path(tmp_path, capsys, monkeypatch):
  repo = make_repo(tmp_path / "repo", config={"repo": REPO})  # `make_repo` records the sample spec's approval
  plan = make_plan(tmp_path / "plans", repo)
  spec, artifacts = repo / "docs/designs/sample.md", tmp_path / "artifacts"
  bin_dir = tmp_path / "bin"
  bin_dir.mkdir()
  script = bin_dir / "gh"
  script.write_text(FAKE_GH.replace("#!/usr/bin/env python3", f"#!{sys.executable}"), encoding="utf-8")
  script.chmod(0o755)
  env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}

  def run(*argv):
    return subprocess.run([sys.executable, str(HELPER), *[str(a) for a in argv]], env=env,
                          cwd=str(repo), capture_output=True, text=True)
  cards = {}
  for skill in ("plan", "file"):
    opened = run("runcard", "open", "--skill", skill, "--artifact", spec)
    assert opened.returncode == 0, opened.stderr
    cards[skill] = opened.stdout.strip()
  assert run("graph", "--plan", plan, "--runcard", cards["plan"]).returncode == 0
  assert run("decide", "--unit", "U03", "--decision", "D2", "--default", "--runcard", cards["plan"]).returncode == 0
  units = json.loads((artifacts / "handoff_units.json").read_text(encoding="utf-8"))
  for uid, unit in units["units"].items():  # as `gated` writes them
    converge_review(artifacts, units["handoff_id"], uid, unit["body_sha256"])
  result = run("gate", "--pass", "--spec", spec, "--runcard", cards["file"])
  assert result.returncode == 0, result.stderr
  result = run("dry-run", "--spec", spec, "--runcard", cards["file"])
  assert result.returncode == 0, result.stderr
  log = [json.loads(l) for l in (bin_dir / "gh.log").read_text(encoding="utf-8").splitlines()]
  assert [l[:2] for l in log] == [["auth", "status"], ["api", f"repos/{REPO}"], ["api", f"repos/{REPO}/labels"]]
  assert "--paginate" in log[2]
  result = run("apply", "--spec", spec, "--yes", "--runcard", cards["file"])
  assert result.returncode == 0, result.stdout + result.stderr
  log = [json.loads(l) for l in (bin_dir / "gh.log").read_text(encoding="utf-8").splitlines()]
  posts = [l for l in log if "POST" in l]
  assert posts and all("-F" in l and "-i" in l for l in posts)
  assert all("-R" not in l for l in log if l[0] in ("api", "auth"))
  assert all("-R" in l for l in log if l[0] in ("issue", "label"))
  assert all("--paginate" in l for l in log if l[0] == "api" and l[1].endswith(("/labels", "/sub_issues", "/blocked_by")) and "POST" not in l)


def test_apply_scans_again_with_the_current_rules(world):
  """R11: a banned_terms rule added after the dry run leaves the write list,
  and therefore its hash, untouched."""
  spec, plan, handoff_id, card = dry_run(world)
  set_config(world, repo=REPO, banned_terms=["(?i)queue"])
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 1 and "the current scan refuses" in out
  assert not any(c[:2] == ["issue", "create"] for c in world.gh.calls)


def test_apply_recovers_issues_by_the_new_marker_after_a_crash(world):
  spec, plan, handoff_id, card = dry_run(world)
  issue_edit_handler(world.gh)
  # 6 labels + the tracking issue + U01 = 8 writes; then a crash before the state was saved
  assert world.run("apply", "--spec", spec, "--runcard", card, "--yes", "--max-writes", 8)[0] == 0
  state = state_of(world)
  assert state["tracking"]["number"] == 1 and state["units"]["U01"]["number"] == 2 and "number" not in state["units"].get("U02", {})
  for record in (state["tracking"], *state["units"].values()):
    for key in ("number", "id", "done", "filing"):
      record.pop(key, None)
  atomic_write(world.artifacts / "state.json", state)
  gh = world.gh
  gh.calls.clear()
  assert world.run("apply", "--spec", spec, "--runcard", card, "--yes")[0] == 0
  listing = [c for c in gh.calls if c[0] == "api" and "/issues?" in c[1]]
  assert listing and f"superegm%3Ahandoff-{handoff_id[-6:]}" in listing[0][1], listing
  after = state_of(world)
  assert after["tracking"]["number"] == 1 and after["units"]["U01"] | {"number": 2} == after["units"]["U01"]
  assert after["units"]["U01"]["id"] == gh.issues[2]["id"] and after["units"]["U02"]["number"] == 3
  assert len(gh.issues) == 3, f"no duplicate issues: {sorted(gh.issues)}"
  assert [c[2] for c in gh.calls if c[:2] == ["issue", "edit"]] == ["1"]  # the recovered tracking body is re-asserted once
  assert after["tracking"]["filing"] == after["confirmed_sha256"] and len(after["filings"]) == 1


def test_a_label_prefix_with_reserved_url_characters_still_recovers(tmp_path, capsys, monkeypatch):
  """R13: a permitted prefix such as `egm:handoff+` must survive the query."""
  w = make_world(tmp_path, capsys, monkeypatch, config={"repo": REPO, "labels": {"handoff_prefix": "egm:handoff+"}})
  spec, plan, handoff_id, card = dry_run(w)
  assert w.run("apply", "--spec", spec, "--runcard", card, "--yes")[0] == 0
  listing = [c for c in w.gh.calls if c[0] == "api" and "/issues?" in c[1]]
  assert listing and "%2B" in listing[0][1], listing
  assert w.run("verify", "--spec", spec, "--runcard", card)[0] == 0


def test_the_file_skill_body_runs_the_filing_in_order_and_asks_one_question():
  body = (ROOT / "skills/file/SKILL.md").read_text(encoding="utf-8").split("---", 2)[2]
  assert len(body.encode("utf-8")) <= 24_000
  assert "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first." in body
  order = ["runcard open --skill file", "gate --pass", "dry-run", "Create these <n> issues and <m> links on OWNER/NAME as handoff_dryrun.md shows?",
           "apply --yes", "verify", "runcard close"]
  positions = [body.index(s) for s in order]
  assert positions == sorted(positions), order
  assert "Create, Change the plan, Stop" in body
  assert "Create: automatic (leavemealone)" in body
  assert "A filed issue body is never edited; a deviation during the build is a comment on the issue (§10)." in body
  assert "filings[]" in body and "base_at_start" in body and "/superegm:wave" in body
  for helper_call in re.findall(r"<HELPER>'\s+([a-z-]+)((?:\s+--[a-z-]+(?:\s+'[^']*'|\s+<[^>]*>)?)*)", body):
    assert helper_call[0] in ("runcard", "gate", "dry-run", "apply", "verify"), helper_call


# ---------------------------------------------------------------- adoption (spec section 10, U13)

ADOPT_ROWS = [ROWS[0], ("U02", "Worker (adopts #7)", "U01"), ROWS[2]]   # the spec's `## Units` table names #7
OLD = hashlib.sha256(b"old body\n").hexdigest()


def seed_issue(gh, number) -> None:
  gh.issues[number] = {"number": number, "id": 1000 + number, "title": f"Old #{number}", "body": "old body\n",
                       "labels": ["bug"], "state": "open", "state_reason": None}


def adopt_gh(gh) -> None:
  def issue(args, cwd, token=None):
    if args[1] == "edit" and "--add-label" in args and "--remove-label" not in args:
      gh.assert_write()
      names, record = args[args.index("--add-label") + 1].split(","), gh.issues[int(args[2])]
      record["labels"] += [n for n in names if n not in record["labels"]]
      return 0, "", ""
    if args[1] == "edit" and "--body-file" in args:
      gh.assert_write()
      gh.issues[int(args[2])]["body"] = Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8")
      return 0, "", ""
    return gh.do_issue(args)
  def api(args, cwd, token=None):
    match = re.fullmatch(rf"repos/{gh.repo}/issues/(\d+)/parent", gh.endpoint_of(args))
    if not match:
      try:
        return gh.do_api(args)
      except KeyError:
        return 1, "", "gh: Not Found (HTTP 404)"
    child = gh.issues[int(match.group(1))]["id"]
    parent = next((n for n, ids in gh.sub_issues.items() if child in ids), None)
    return gh.ok(gh.issues[parent]) if parent else (1, "", "gh: Not Found (HTTP 404)")
  gh.extend("issue", issue)
  gh.extend("api", api)


def adopt_gated(world):
  adopt_gh(world.gh)
  seed_issue(world.gh, 7)
  spec, handoff_id = approve(world, ADOPT_ROWS)
  plan = world.artifacts.parent / "plan.md"
  plan.write_text(plan_text(spec, [unit_section(*ADOPT_ROWS[0]), unit_section(*ADOPT_ROWS[1], issue=7),
                                   unit_section(*ADOPT_ROWS[2])]), encoding="utf-8")
  graphed(world, spec, plan)
  for uid in ("U01", "U02", "U03"):
    converge(world, uid)
  card = open_card(world, "file", spec)
  code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", card)
  assert code == 0, out
  return spec, plan, handoff_id, card


def adopt_dry_run(world):
  spec, plan, handoff_id, card = adopt_gated(world)
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  assert code == 0, out
  world.gh.calls.clear()
  return spec, plan, handoff_id, card


def test_pending_writes_carries_the_adopted_number_and_old_body_sha(world):
  from superegm import gate
  spec, plan, handoff_id, card = adopt_gated(world)
  handoff = gate.open_handoff(spec)
  plain = gate.pending_writes(handoff)
  adopted = gate.pending_writes(handoff, adopted={"U02": (7, OLD)})
  assert [len(w) for w in plain if w[0] == "issue"] == [5, 5, 5, 5]
  assert [w[5:] for w in adopted if w[0] == "issue"] == [[], [], [7, OLD], []]
  assert [w[:5] for w in adopted] == plain
  assert gate.pending_writes(handoff, units={"U01", "U02", "U03"}, adopted={"U02": (7, OLD)}) == adopted


COMMENTS = {"ruling": "**Ruling:** (c1) (a) — keep it", "decision": "**Decision D1:** (a) 5 attempts",
            "deviation": "**Deviation (dod):** item 2 cannot pass\n**Builder status:** BLOCKED"}


@pytest.mark.parametrize("case, expected", [
  ("ok", None),
  ("closed", "adopt: #7 is closed"),
  ("not-in-repo", f"adopt: #7 not in {REPO}"),
  ("pull-request", "adopt: #7 is a pull request"),
  ("parent", "adopt: #7 has a parent"),
  ("dependencies", "adopt: #7 has dependencies"),
  ("superegm-label", "adopt: #7 carries superegm labels"),
  ("comment-ruling", "adopt: #7 carries a ruling comment"),
  ("comment-decision", "adopt: #7 carries a ruling comment"),
  ("comment-deviation", "adopt: #7 carries a ruling comment"),
])
def test_dry_run_refuses_an_issue_it_cannot_adopt(world, case, expected):
  spec, plan, handoff_id, card = adopt_gated(world)
  gh = world.gh
  if case == "closed": gh.issues[7]["state"] = "closed"
  if case == "not-in-repo": del gh.issues[7]
  if case == "pull-request": gh.issues[7]["pull_request"] = {"url": f"https://api.github.com/repos/{REPO}/pulls/7"}
  if case == "parent": seed_issue(gh, 8); gh.sub_issues[8] = [gh.issues[7]["id"]]
  if case == "dependencies": seed_issue(gh, 8); gh.blocked_by[7] = [gh.issues[8]["id"]]
  if case == "superegm-label": gh.issues[7]["labels"].append("superegm:stopped")
  if case.startswith("comment-"): gh.comments[7] = [{"id": 1, "body": COMMENTS[case[8:]], "user": {"login": "owner"}}]
  gh.calls.clear()
  code, out = world.run("dry-run", "--spec", spec, "--runcard", card)
  if expected is None:
    assert code == 0, out
    text = (world.artifacts / "handoff_dryrun.md").read_text(encoding="utf-8")
    assert f"### edit #7 U02 (old body sha256 {OLD})" in text and "### issue U02" not in text
    assert "### issue U01" in text and "### issue U03" in text
    assert "4 issues (1 tracking, 3 units), 3 sub-issue links, 2 blocked-by links" in text
    assert [c[:2] for c in gh.calls] == [
        ["auth", "status"], ["api", f"repos/{REPO}"], ["api", f"repos/{REPO}/labels"],
        ["api", f"repos/{REPO}/issues/7"], ["api", f"repos/{REPO}/issues/7/parent"],
        ["api", f"repos/{REPO}/issues/7/dependencies/blocked_by"], ["api", f"repos/{REPO}/issues/7/comments"]]
    writes = state_of(world)["confirmed"]["writes"]
    assert [w[5:] for w in writes if w[0] == "issue"] == [[], [], [7, OLD], []]
    assert state_of(world)["confirmed"]["sha256"] == hashlib.sha256(world.ns["canonical"](writes).encode("utf-8")).hexdigest()
    return
  assert code == 1 and expected in out, out
  assert "confirmed" not in state_of(world) and not (world.artifacts / "handoff_dryrun.md").exists()


def test_apply_refuses_an_adopted_body_changed_since_the_dry_run(world):
  spec, plan, handoff_id, card = adopt_dry_run(world)
  world.gh.issues[7]["body"] = "old body, edited\n"
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 1 and "adopt: #7 body changed since the dry run" in out, out
  assert not any(c[0] in ("label", "issue") or "POST" in c for c in world.gh.calls)
  assert "filings" not in state_of(world) and "base_at_start" not in state_of(world)
  assert world.gh.issues[7]["labels"] == ["bug"] and "units" not in state_of(world).get("tracking", {})
  del world.gh.issues[7]
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 1 and f"adopt: #7 not in {REPO}" in out, out


def test_apply_adopts_the_issue_labels_first_then_the_body_and_links_it(world):
  from superegm.launch_builder import filed_body
  spec, plan, handoff_id, card = adopt_dry_run(world)
  gh, six = world.gh, handoff_id[-6:]
  gh.comments[7] = [{"id": 1, "body": "an ordinary comment", "user": {"login": "someone"}}]
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 0, out
  assert [c[c.index("--title") + 1] for c in gh.calls if c[:2] == ["issue", "create"]] == ["Build: Sample design", "U01: Queue", "U03: Admin endpoint"]
  edits = [c for c in gh.calls if c[:2] == ["issue", "edit"] and c[2] == "7"]
  assert [("--add-label" in c, "--body-file" in c, "--title" in c) for c in edits] == [(True, False, False), (False, True, False)]
  assert edits[0][edits[0].index("--add-label") + 1] == f"superegm:handoff-{six},superegm:unit,superegm:wave-2"
  issue = gh.issues[7]
  assert issue["title"] == "Old #7" and issue["labels"] == ["bug", f"superegm:handoff-{six}", "superegm:unit", "superegm:wave-2"]
  assert issue["body"].startswith(f"<!-- superegm:handoff={handoff_id} unit=U02 spec=") and "Blocked by: #2 ·" in issue["body"]
  assert "Part of #1" in issue["body"] and "#<" not in issue["body"] and gh.comments[7][0]["body"] == "an ordinary comment"
  assert "Blocked by: #7 ·" in gh.issues[3]["body"]                                  # U03's placeholder resolves to the adopted number
  assert gh.sub_issues[1] == [gh.issues[2]["id"], issue["id"], gh.issues[3]["id"]]
  assert gh.blocked_by == {7: [gh.issues[2]["id"]], 3: [issue["id"]]}
  state = state_of(world)
  assert state["units"]["U02"] | {"number": 7, "id": issue["id"], "done": True, "wave": 2} == state["units"]["U02"]
  assert state["verify"]["complete"] is True and state["verify"]["problems"] == [] and state["verify"]["checked"] == "16 of 16"
  assert filed_body(state, "U02") == issue["body"]                                   # the fixed-field reader is unchanged
  gh.calls.clear()
  assert world.run("apply", "--spec", spec, "--runcard", card, "--yes")[0] == 0
  assert not any(c[0] == "label" or c[:2] in (["issue", "create"], ["issue", "edit"]) or "POST" in c for c in gh.calls)
  issue["body"] += "edited by hand\n"
  code, out = world.run("verify", "--spec", spec, "--runcard", card)
  assert code == 1 and "MISMATCH body of #7 (U02)" in out, out
