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
from conftest import HELPER, REPO, make_world, make_repo, make_plan, set_config, state_of, launchable, git, \
    converge as converge_review

ROOT = Path(__file__).resolve().parents[2]
PKG = "skills/plan/scripts/superegm"
SLUG = "2026-11-03-sample-design"          # the spec is docs/specs/<SLUG>.md, H1 `# Sample design`
ROWS = [("U01", "Queue", "none"), ("U02", "Worker", "U01"), ("U03", "Admin endpoint", "U02")]  # (unit, title, blocked by)


def spec_text(rows) -> str:
  """`# Sample design`, `## 1. Intent` at lines 3-4, the `## Units` table of `rows` as the last H2."""
  table = "\n".join(f"| {uid} | {title} | {blocked} |" for uid, title, blocked in rows)
  return ("# Sample design\n\n## 1. Intent\nQueued webhook delivery with an admin listing.\n\n"
          f"## Units\n\n| Unit | Title | Blocked by |\n| --- | --- | --- |\n{table}\n")


def unit_section(uid, title, blocked) -> str:
  """A unit section in the section 9.1 grammar with one Step."""
  low = uid.lower()
  return f"""### {uid}: {title}
| Field | Value |
| --- | --- |
| Objective | {title} exists. |
| Scope paths | `src/{low}.ts` (create), `tests/{low}.test.ts` (create) |
| Design range | `docs/specs/{SLUG}.md:3-4 (## 1. Intent)` |
| Blocked by | {blocked} |
| Shared files | none |
| Risk | low: new module |
| Size | S |

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


def test_apply_refusals(world):
  dry_run(world)
  code, out = world.run("apply", "--plan", world.plan)
  assert code == 1 and "--yes" in out
  state = state_of(world)
  confirmed = state.pop("confirmed_sha256")
  (world.artifacts / "state.json").write_text(json.dumps(state), encoding="utf-8")
  code, out = world.run("apply", "--plan", world.plan, "--yes")
  assert code == 1 and "no confirmed_sha256" in out
  state["confirmed_sha256"] = confirmed
  state["repo"] = "someone/else"
  (world.artifacts / "state.json").write_text(json.dumps(state), encoding="utf-8")
  code, out = world.run("apply", "--plan", world.plan, "--yes")
  assert code == 1 and "differs from the state's" in out
  state["repo"] = REPO
  (world.artifacts / "state.json").write_text(json.dumps(state), encoding="utf-8")
  text = world.plan.read_text(encoding="utf-8")
  world.plan.write_text(text.replace("low: new module", "low: a new module"), encoding="utf-8")
  code, out = world.run("apply", "--plan", world.plan, "--yes")
  # The reviewed-pair check is stricter and fires first (R6-02): a plan edited
  # after the gate is refused before the write list is even compared.
  assert code == 1, out
  assert ("changed since the dry run" in out
          or "differ from the pair the gate reviewed" in out), out
  assert not any(c[0] in ("label", "issue") for c in world.gh.calls)


def test_apply_creates_in_order_and_rerun_writes_nothing(world):
  dry_run(world)
  world.gh.calls.clear()
  code, out = world.run("apply", "--plan", world.plan, "--yes")
  assert code == 0, out
  gh = world.gh
  labels = [c[2] for c in gh.calls if c[0] == "label"]
  assert labels == ["superegm:unit", "superegm:tracking", "superegm:handoff-" + state_of(world)["handoff_id"],
                    "superegm:wave-1", "superegm:wave-2", "superegm:wave-3"]
  assert "bug" in gh.labels and all("--force" not in c for c in gh.calls)
  creates = [c for c in gh.calls if c[:2] == ["issue", "create"]]
  titles = [c[c.index("--title") + 1] for c in creates]
  assert titles == ["Build: Webhook delivery", "U01: Webhook queue", "U02: Delivery worker", "U03: Admin endpoint"]
  first_label_or_issue = next(i for i, c in enumerate(gh.calls) if c[0] in ("label", "issue"))
  first_issue = next(i for i, c in enumerate(gh.calls) if c[:2] == ["issue", "create"])
  assert first_label_or_issue < first_issue
  assert gh.issues[3]["body"].count("#1") >= 1 and "**Blocked by.** #2" in gh.issues[3]["body"]
  assert "after #2, before U03 (Admin endpoint)" in gh.issues[3]["body"]
  assert "**Blocked by.** #3" in gh.issues[4]["body"]
  assert gh.issues[2]["labels"] == ["superegm:handoff-" + state_of(world)["handoff_id"], "superegm:unit", "superegm:wave-1"]
  assert world.sleeps.count(1) >= 4
  assert gh.sub_issues[1] == [gh.issues[2]["id"], gh.issues[3]["id"], gh.issues[4]["id"]]
  assert gh.blocked_by == {3: [gh.issues[2]["id"]], 4: [gh.issues[3]["id"]]}
  state = state_of(world)
  assert state["units"]["U02"]["number"] == 3 and state["tracking"]["number"] == 1
  assert state["links"]["blocked:U03<-U02"] == "done" and state["verify"]["complete"] is True
  assert state["verify"]["problems"] == [] and state["verify"]["sha256"] == state["confirmed_sha256"]
  assert state["verify"]["checked"] == "15 of 15"
  gh.calls.clear()
  code, out = world.run("apply", "--plan", world.plan, "--yes")
  assert code == 0, out
  assert not any(c[0] == "label" or c[:2] == ["issue", "create"] or "POST" in c for c in gh.calls)


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


def test_verify_records_mismatches(world):
  dry_run(world)
  assert world.run("apply", "--plan", world.plan, "--yes")[0] == 0
  world.gh.issues[3]["body"] += "\nedited by hand"
  world.gh.issues[2]["labels"].remove("superegm:unit")
  code, out = world.run("verify", "--plan", world.plan)
  assert code == 1
  state = state_of(world)
  problems = state["verify"]["problems"]
  assert any("body of #3" in p for p in problems) and any("labels of #2" in p and "superegm:unit" in p for p in problems)
  assert state["verify"]["complete"] is True
  code, out = world.run("status", "--plan", world.plan)
  assert code == 1 and "not fully created and verified" in out


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


def test_verify_refuses_a_plan_edited_since_the_confirmation(world):
  """R08: a receipt must describe what the user confirmed, not a plan since
  edited, or removing a blocker locally would make a unit look ready."""
  applied(world)
  launchable(world)
  assert world.run("verify", "--plan", world.plan)[0] == 0
  world.plan.write_text(world.plan.read_text(encoding="utf-8")
                        .replace("| Blocked by | U01 |", "| Blocked by | none |"), encoding="utf-8")
  # verify reports on what was confirmed, so it stays clean...
  code, out = world.run("verify", "--plan", world.plan)
  assert code == 0 and "MISMATCH" not in out, out
  # ...and readiness, which the edit would have changed, is refused outright
  for argv in (("status", "--plan", world.plan),
               ("launch", "--plan", world.plan)):
    code, out = world.run(*argv)
    assert code == 1 and "is filed and frozen" in out, argv


def test_apply_scans_again_with_the_current_rules(world):
  """R11: a banned_terms rule added after the dry run leaves the write list,
  and therefore its hash, untouched."""
  spec, plan, handoff_id, card = dry_run(world)
  set_config(world, repo=REPO, banned_terms=["(?i)queue"])
  code, out = world.run("apply", "--spec", spec, "--runcard", card, "--yes")
  assert code == 1 and "the current scan refuses" in out
  assert not any(c[:2] == ["issue", "create"] for c in world.gh.calls)


def test_marker_recovery_finds_issues_created_before_a_crash(world):
  """R2-13/R13: the recovery listing is the only way home after a crash between
  the create call and the state write, and its label is URL-encoded."""
  dry_run(world)
  gh = world.gh
  # a crash after creating the tracking issue and U01, before either was saved
  assert world.run("apply", "--plan", world.plan, "--yes", "--max-writes", 8)[0] == 0
  state = state_of(world)
  created = {u: d["number"] for u, d in (state.get("units") or {}).items() if d.get("number")}
  assert created, "the bounded apply must have created something"
  # erase every local trace of those writes, as an interrupted save would
  for unit in (state.get("units") or {}).values():
    unit.pop("number", None), unit.pop("id", None), unit.pop("done", None)
  for key in ("number", "id", "done"):
    (state.get("tracking") or {}).pop(key, None)
  (world.artifacts / "state.json").write_text(json.dumps(state), encoding="utf-8")
  before = len([c for c in gh.calls if c[:2] == ["issue", "create"]])
  assert world.run("apply", "--plan", world.plan, "--yes")[0] == 0
  after = state_of(world)
  for uid, number in created.items():
    assert after["units"][uid]["number"] == number, "recovery must reuse the issue"
    assert after["units"][uid]["id"], "recovery must backfill the database id"
  assert len(gh.issues) == 4, f"no duplicate issues: {sorted(gh.issues)}"


def test_a_label_prefix_with_reserved_url_characters_still_recovers(tmp_path, capsys, monkeypatch):
  """R13: a permitted prefix such as `egm:handoff+` must survive the query."""
  w = make_world(tmp_path, capsys, monkeypatch, config={"repo": REPO, "labels": {"handoff_prefix": "egm:handoff+"}})
  spec, plan, handoff_id, card = dry_run(w)
  assert w.run("apply", "--spec", spec, "--runcard", card, "--yes")[0] == 0
  listing = [c for c in w.gh.calls if c[0] == "api" and "/issues?" in c[1]]
  assert listing and "%2B" in listing[0][1], listing
  assert w.run("verify", "--spec", spec, "--runcard", card)[0] == 0


def test_verify_reports_a_link_the_handoff_no_longer_wants(world):
  """R3-06: checking only that expected links exist cannot see an obsolete one
  left behind by an amendment."""
  gh = applied(world)
  assert world.run("verify", "--plan", world.plan)[0] == 0
  state = state_of(world)
  # U01 is blocked by nothing; an amendment that removed a blocker would leave
  # exactly this: a live dependency the confirmed write list no longer names.
  stale = state["units"]["U03"]["id"]
  gh.blocked_by.setdefault(state["units"]["U01"]["number"], []).append(stale)
  code, out = world.run("verify", "--plan", world.plan)
  assert code == 1 and "obsolete blocked-by link" in out, out


def test_apply_refuses_a_body_invisible_plan_edit(world):
  """R6-02: the guard was added next to a scan_handoff call that lives in
  cmd_dry_run, so apply - where the writes happen - never had it."""
  dry_run(world)
  text = world.plan.read_text(encoding="utf-8")
  marker = "Decide before build\n- none"
  assert marker in text
  world.plan.write_text(
      text.replace(marker, marker + "\n\nBuild note: use the legacy client.", 1),
      encoding="utf-8")
  code, out = world.run("apply", "--plan", world.plan, "--yes")
  assert code == 1 and "differ from the pair the gate reviewed" in out, out
  assert not any(c[:2] == ["issue", "create"] for c in world.gh.calls)
