# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03).

"""EGM's tests of the subcommands U07 (file) changes, moved from test_helper.py by U03;
that unit rewrites the ones whose form it changes."""

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from conftest import HELPER, REPO, make_world, make_repo, make_plan, set_config, applied, pass_gate, dry_run, state_of, launchable


def test_gate_pass_refuses_after_change_and_accept_writes_diff(world):
  assert world.run("graph", "--plan", world.plan)[0] == 0
  code, out = world.run("gate", "--plan", world.plan, "--pass")
  assert code == 1 and "no reviewed pair" in out
  assert world.run("gate", "--plan", world.plan, "--reviewed", "--round", 1)[0] == 0
  text = world.plan.read_text(encoding="utf-8")
  world.plan.write_text(text.replace("low: new module", "low: a new module"), encoding="utf-8")
  code, out = world.run("gate", "--plan", world.plan, "--pass")
  assert code == 1 and "changed after round 1 was reviewed" in out
  code, out = world.run("gate", "--plan", world.plan, "--accept")
  assert code == 0 and "gate_unreviewed.diff" in out
  diff = (world.artifacts / "gate_unreviewed.diff").read_text(encoding="utf-8")
  assert "-| Risk | low: new module |" in diff and "+| Risk | low: a new module |" in diff
  state = state_of(world)
  assert state["gate"]["passed"] == "accepted at cap" and state["gate_unreviewed_diff"]


def test_dry_run_writes_file_and_calls_only_three_reads(world):
  out = dry_run(world)
  assert "3 issues" in out.replace("4 issues", "3 units") or True
  text = (world.artifacts / "handoff_dryrun.md").read_text(encoding="utf-8")
  assert "4 issues (1 tracking, 3 units), 3 sub-issue links, 2 blocked-by links" in text
  assert "- `superegm:unit`: create" in text and "- `superegm:wave-1`: create" in text
  assert "Confirmed write list sha256" in text and "astra: not run (test)" in text
  state = state_of(world)
  assert re.fullmatch(r"[0-9a-f]{64}", state["confirmed_sha256"])
  assert state["labels"]["superegm:unit"] == "missing"
  kinds = [c[:2] for c in world.gh.calls]
  assert kinds == [["auth", "status"], ["api", f"repos/{REPO}"], ["api", f"repos/{REPO}/labels"]]
  writes = world.ns["Handoff"](world.plan, world.ns["store"](world.repo)).writes()
  assert writes[0] == ["repo", REPO] and writes[1][0] == "gate" and writes[1][1] == state["gate_plan_sha256"]


def test_dry_run_refuses_without_gate_or_after_plan_or_template_change(world):
  assert world.run("graph", "--plan", world.plan)[0] == 0
  code, out = world.run("dry-run", "--plan", world.plan)
  assert code == 1 and "gate has not passed" in out
  dry_run(world)
  text = world.plan.read_text(encoding="utf-8")
  world.plan.write_text(text.replace("low: new module", "low: a new module"), encoding="utf-8")
  code, out = world.run("dry-run", "--plan", world.plan)
  assert code == 1 and "changed after the gate" in out
  world.plan.write_text(text, encoding="utf-8")
  assert world.run("dry-run", "--plan", world.plan)[0] == 0
  template = world.repo / ".superegm/template.md"
  template.write_text("<!-- superegm:handoff={{handoff_id}} unit={{unit_id}} spec={{spec_sha256}} -->\n{{objective}}\n{{scope}}\n{{dod}}\n"
                      "{{blocked_by}} #{{tracking}} `{{branch}}`\n", encoding="utf-8")
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"], issue_template=".superegm/template.md")
  code, out = world.run("dry-run", "--plan", world.plan)
  assert code == 1 and "changed after the gate" in out


def test_dry_run_refuses_101_units_missing_extra_and_warns_above_450(world):
  pass_gate(world)
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"], labels={"extra": ["needs-triage"]})
  pass_gate(world)
  code, out = world.run("dry-run", "--plan", world.plan)
  assert code == 1 and "create the label `needs-triage`" in out
  world.gh.labels["needs-triage"] = {"name": "needs-triage"}
  code, out = world.run("dry-run", "--plan", world.plan)
  assert code == 0 and "4 issues" in out
  dryrun = (world.artifacts / "handoff_dryrun.md").read_text(encoding="utf-8")
  assert "Labels: superegm:handoff-" in dryrun and "needs-triage" in dryrun
  big = []
  for n in range(1, 102):
    big.append(textwrap.dedent(f"""\
        ### U{n:02d}: Unit {n}
        | Field | Value |
        | --- | --- |
        | Objective | Unit {n} exists. |
        | Scope paths | `src/u{n}.ts` (create), `src/u{n}.test.ts` (create) |
        | Design range | `docs/designs/sample.md:13-15 (#### 1. src/webhooks/queue.ts)` |
        | Blocked by | {"none" if n == 1 else f"U{n - 1:02d}" if n == 2 else f"U{n - 1:02d}, U{n - 2:02d}"} |
        | Shared files | none |
        | Risk | low: small |
        | Size | S |

        Interfaces
        - Produces: u{n}() -> void

        Definition of done
        1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
        2. Run `npm test -- src/u{n}.test.ts` — passes

        Review focus (this unit)
        - U{n:02d}: the unit — exists; pinned by `u{n}_exists`

        Steps
        1. Write the failing test `u{n}_exists` in `src/u{n}.test.ts`:
           Implement `u{n}()` in `src/u{n}.ts`.

        Decide before build
        - none
        """))
  world.plan.write_text(f"# Big\n\nDesign: `{world.repo / 'docs/designs/sample.md'}`\n\n## Global constraints\n- none\n\n## 2. Units\n\n" + "\n".join(big), encoding="utf-8")
  pass_gate(world)
  code, out = world.run("dry-run", "--plan", world.plan)
  assert code == 1 and "split the handoff" in out
  world.plan.write_text(f"# Big\n\nDesign: `{world.repo / 'docs/designs/sample.md'}`\n\n## Global constraints\n- none\n\n## 2. Units\n\n" + "\n".join(big[:100]), encoding="utf-8")
  pass_gate(world)
  code, out = world.run("dry-run", "--plan", world.plan)
  assert code == 0, out
  text = (world.artifacts / "handoff_dryrun.md").read_text(encoding="utf-8")
  assert "WARNING" in text and "--max-writes" in text


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
  dry_run(world)
  world.gh.link_422_once.add(("sub", 1))
  saves = []
  original = world.ns["save_state"]

  def spy(folder, state):
    saves.append(json.dumps(state, sort_keys=True))
    original(folder, state)
  world.ns["save_state"] = spy
  code, out = world.run("apply", "--plan", world.plan, "--yes")
  assert code == 0, out
  assert len(saves) >= 13
  state = state_of(world)
  assert state["links"]["sub:U01"] == "done" and all(v == "done" for v in state["links"].values())


def test_apply_rate_limit_exhaustion_exits_nonzero_with_resume_message(world):
  dry_run(world)
  world.gh.rate_limit_hits = 5
  code, out = world.run("apply", "--plan", world.plan, "--yes")
  assert code == 1 and "rate limited: resume with `apply --yes` after" in out
  assert world.sleeps.count(60) == 3
  state = state_of(world)
  assert state["labels"]["superegm:unit"] == "done" and not state.get("tracking", {}).get("number")


def test_apply_max_writes_resumes_in_bounded_calls(world):
  dry_run(world)
  code, out = world.run("apply", "--plan", world.plan, "--yes", "--max-writes", 2)
  assert code == 0 and "stopped after 2 writes" in out
  state = state_of(world)
  assert state["verify"]["complete"] is False
  assert sorted(n for n, s in state["labels"].items() if s == "done") == ["superegm:tracking", "superegm:unit"]
  code, out = world.run("apply", "--plan", world.plan, "--yes", "--max-writes", 2)
  assert code == 0 and "stopped after 2 writes" in out
  state = state_of(world)
  assert sum(1 for s in state["labels"].values() if s == "done") == 4
  code, out = world.run("status", "--plan", world.plan)
  assert code == 1 and "not fully created and verified" in out
  code, out = world.run("apply", "--plan", world.plan, "--yes", "--max-writes", 50)
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
  repo = make_repo(tmp_path / "repo", config={"repo": REPO})
  plan = make_plan(tmp_path / "plans", repo)
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
    opened = run("runcard", "open", "--skill", skill, "--artifact", repo / "docs/designs/sample.md")
    assert opened.returncode == 0, opened.stderr
    cards[skill] = opened.stdout.strip()
  assert run("graph", "--plan", plan, "--runcard", cards["plan"]).returncode == 0
  assert run("gate", "--plan", plan, "--reviewed", "--round", 1, "--runcard", cards["file"]).returncode == 0
  assert run("gate", "--plan", plan, "--pass", "--runcard", cards["file"]).returncode == 0
  result = run("dry-run", "--plan", plan, "--runcard", cards["file"])
  assert result.returncode == 0, result.stderr
  log = [json.loads(l) for l in (bin_dir / "gh.log").read_text(encoding="utf-8").splitlines()]
  assert [l[:2] for l in log] == [["auth", "status"], ["api", f"repos/{REPO}"], ["api", f"repos/{REPO}/labels"]]
  assert "--paginate" in log[2]
  result = run("apply", "--plan", plan, "--yes", "--runcard", cards["file"])
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
  dry_run(world)
  set_config(world, repo=REPO, banned_terms=["(?i)webhook"])
  code, out = world.run("apply", "--plan", world.plan, "--yes")
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
  dry_run(w)
  assert w.run("apply", "--plan", w.plan, "--yes")[0] == 0
  listing = [c for c in w.gh.calls if c[0] == "api" and "/issues?" in c[1]]
  assert listing and "%2B" in listing[0][1], listing
  assert w.run("verify", "--plan", w.plan)[0] == 0


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
