# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: renamed from test_egm_handoff.py; helper and skill paths under skills/plan and skills/wave.

"""U03's tests: the helper package, the store, run cards, the gating, init, the body
parsers, the schemas, the renames and the removals; EGM's tests of the shared names."""

import argparse
import hashlib
import importlib
import json
import re
import sys
from pathlib import Path

import pytest

from conftest import (ROOT, SCRIPTS, HELPER, REPO, DESIGN, Harness, make_world, make_repo, make_pr, set_config, applied, dry_run, state_of, unit_path, close_as_completed, git, mark_launched, launchable)


# ---------------------------------------------- EGM's tests of the shared names


def test_long_derived_label_is_refused(tmp_path, capsys, monkeypatch):
  w = make_world(tmp_path, capsys, monkeypatch, config={"repo": REPO, "labels": {"handoff_prefix": "x" * 45}})
  code, out = w.run("graph", "--plan", w.plan)
  assert code == 1 and "longer than 50 characters" in out


def test_config_defaults_and_remote_resolution(tmp_path, capsys, monkeypatch):
  w = make_world(tmp_path, capsys, monkeypatch, config={"repo": REPO},
                 origin_url="git@github.com:fork-user/webhooks.git")
  git(["remote", "add", "upstream", f"ssh://git@github.com/{REPO}"], w.repo)
  assert w.run("graph", "--plan", w.plan)[0] == 0
  state = state_of(w)
  assert state["remote"] == "upstream" and state["repo"] == REPO
  config = w.ns["load_config"](w.repo)
  assert config["banned_terms"] == [] and config["fix_request_mention"] is None
  set_config(w, repo="other/name")
  code, out = w.run("graph", "--plan", w.plan)
  assert code == 1 and "no remote for other/name" in out
  set_config(w, repo=REPO, bogus=1)
  code, out = w.run("graph", "--plan", w.plan)
  assert code == 1 and "unknown keys" in out


def test_artifacts_dir_and_profile_dir_expand_tilde(tmp_path, capsys, monkeypatch):
  """A committed config names no local username: `~` expands before the
  absolute-outside-the-tree check, and the expanded path is what the store uses."""
  w = make_world(tmp_path, capsys, monkeypatch)
  monkeypatch.setenv("HOME", str(tmp_path))
  path = w.repo / ".superegm/config.json"

  def load(artifacts):
    builder = {**w.ns["DEFAULT_CONFIG"]["builder"], "profile_dir": "~/builder"}
    path.write_text(json.dumps({"repo": REPO, "artifacts_dir": artifacts, "builder": builder}), encoding="utf-8")
    return w.ns["load_config"](w.repo)

  config = load("~/.cache/superegm/build")
  assert config["artifacts_dir"] == str(tmp_path / ".cache/superegm/build")
  assert config["builder"]["profile_dir"] == str(tmp_path / "builder")
  assert w.ns["store"](w.repo).root == tmp_path / ".cache/superegm/build"
  for refused in ("build/store", "~/repo/store"):
    with pytest.raises(w.ns["HandoffError"], match="absolute path outside the working tree"):
      load(refused)





def test_gh_is_pinned_to_github_com_whatever_gh_host_says(monkeypatch):
  """R03: GH_HOST would send writes to an enterprise server that no approval,
  remote check or confirmed destination in this helper ever looked at."""
  if str(HELPER.parent) not in sys.path:
    sys.path.insert(0, str(HELPER.parent))
  import superegm
  monkeypatch.setenv("GH_HOST", "github.enterprise.invalid")
  monkeypatch.setenv("GH_ENTERPRISE_TOKEN", "tok")
  env = superegm.gh_env()
  assert env["GH_HOST"] == "github.com"
  assert "GH_ENTERPRISE_TOKEN" not in env


def test_state_is_written_atomically_and_a_poll_keeps_other_writers_fields(world):
  """R01: a watcher that saves its whole in-memory copy erases a decision or a
  launch the main conversation recorded while it slept."""
  gh = applied(world)
  assert world.run("verify", "--spec", world.spec)[0] == 0
  # another writer records a decision while a poll is in flight
  assert world.run("decide", "--plan", world.plan, "--unit", "U03",
                   "--decision", "D2", "--answer", "(a)")[0] == 0
  mark_launched(world, "U01")
  assert world.run("status", "--plan", world.plan)[0] == 0
  after = state_of(world)
  assert after["decisions"]["U03/D2"]["answer"] == "(a)"
  assert after["units"]["U01"]["launched"]["runcard"] == world.card("wave")
  assert after["units"]["U01"]["number"]
  # no temporary file is left behind by the atomic replace
  assert not list(world.artifacts.glob("state.json.tmp*"))


def test_operations_refuse_a_repository_the_numbers_do_not_belong_to(world):
  """R02: issue numbers are not portable; only apply checked the destination."""
  applied(world)
  assert world.run("verify", "--spec", world.spec)[0] == 0
  set_config(world, repo="other/elsewhere", banned_terms=["(?i)secret-codename"])
  git(["remote", "set-url", "origin", "https://github.com/other/elsewhere.git"], world.repo)
  code, out = world.run("status", "--plan", world.plan)
  assert code == 1, out
  assert "frozen once anything exists" in out or "not portable between repositories" in out, out


def test_duplicate_decision_ids_in_one_unit_are_refused(world):
  """R15: two blocking questions sharing an id share one state key, so
  answering the first would release the unit while the second is open."""
  world.plan.write_text(world.plan.read_text(encoding="utf-8").replace(
      "- D2 Page size for the listing? options: (a) 50; (b) 25; owner: the user; default: (a); blocking: yes",
      "- D2 Page size for the listing? options: (a) 50; (b) 25; owner: the user; default: (a); blocking: yes\n"
      "- D2 Retry budget? options: (a) 3; (b) 5; owner: the user; default: (a); blocking: yes"), encoding="utf-8")
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1 and "two" in out and "D2" in out


def test_a_dirty_review_worktree_is_never_force_removed(world, tmp_path):
  """R04: the foreman removes a worktree after every round; --force would
  delete someone's uncommitted work without asking."""
  remove = world.ns["remove_worktree"]
  HandoffError = world.ns["HandoffError"]
  root = make_repo(tmp_path / "wt-root")
  tree = tmp_path / "wt-copy"
  git(["worktree", "add", "-q", str(tree)], root)
  (tree / "scratch.txt").write_text("unsaved\n", encoding="utf-8")
  with pytest.raises(HandoffError) as caught:
    remove(root, tree)
  assert "uncommitted changes" in str(caught.value)
  assert (tree / "scratch.txt").is_file()
  (tree / "scratch.txt").unlink()
  remove(root, tree)
  assert not tree.exists()


def test_a_completed_label_write_binds_the_destination(world):
  """R3-03: created_anything ignored labels, so a bounded apply that only made
  labels left the destination free to move."""
  dry_run(world)
  assert world.run("apply", "--spec", world.spec, "--yes", "--max-writes", 2)[0] == 0
  state = state_of(world)
  assert not any(u.get("number") for u in state["units"].values()), "this bounded apply must not reach an issue"
  assert "done" in state["labels"].values()
  set_config(world, repo="other/elsewhere")
  git(["remote", "add", "other", "https://github.com/other/elsewhere.git"], world.repo)
  code, out = world.run("status", "--plan", world.plan)
  assert code == 1 and "frozen once anything exists" in out


def test_a_mixed_case_remote_url_resolves(tmp_path, capsys, monkeypatch):
  """R10-02: find_remote and the pre-fetch recheck compared case-sensitively,
  rejecting a valid remote before discovery could run."""
  w = make_world(tmp_path, capsys, monkeypatch, config={"repo": REPO},
                 origin_url="https://github.com/Example-Org/WebHooks.git")
  code, out = w.run("graph", "--plan", w.plan)
  assert code == 0, out
  state = state_of(w)
  assert state["remote"] == "origin" and state["repo"] == REPO


def test_binding_checks_fold_repository_case(world):
  """R11-04: after confirmation, a case-only change to the config or remote is
  the same repository, not a different frozen destination."""
  applied(world)
  set_config(world, repo=REPO.upper(), banned_terms=["(?i)secret-codename"])
  git(["remote", "set-url", "origin", f"https://github.com/{REPO.upper()}.git"], world.repo)
  code, out = world.run("status", "--plan", world.plan)
  assert code == 0, out
  assert state_of(world)["confirmed"]["repo"] == REPO, "the confirmed spelling is kept"


def test_helper_runs_under_its_new_name(world):
  """U01: EGM's helper, one file, renamed; every contract still EGM's."""
  assert HELPER == ROOT / "skills/plan/scripts/superegm.py"
  assert world.ns["build_parser"]().prog == "superegm.py"
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 0, out
  assert (world.artifacts / "handoff_units.json").is_file()
  for skill in ("skills/plan/SKILL.md", "skills/wave/SKILL.md"):
    assert "egm_handoff.py" not in (ROOT / skill).read_text(encoding="utf-8"), skill


MODULES = ("init", "runcard", "approve_spec", "graph", "scan", "review", "gate", "dry_run", "apply",
           "verify", "status", "launch", "launch_builder", "record_launch", "foreman", "prepare",
           "collect", "tdd_order", "decide", "decision", "interrupt", "clean", "report", "close", "judges",
           "review_plan", "orient", "doctor")


@pytest.mark.parametrize("name", MODULES)
def test_one_module_per_subcommand(name):
  import argparse, importlib, sys
  scripts = Path(__file__).resolve().parents[2] / "skills/plan/scripts"
  if str(scripts) not in sys.path:
    sys.path.insert(0, str(scripts))
  import superegm
  assert set(superegm.SUBCOMMANDS) == set(MODULES)
  module = importlib.import_module(f"superegm.{name}")
  assert callable(module.register) and callable(module.run)
  parser = superegm.build_parser()
  choices = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction)).choices
  assert name.replace("_", "-") in choices
  assert choices[name.replace("_", "-")].get_default("run") is module.run
  defs = [l for l in (scripts / "superegm.py").read_text(encoding="utf-8").splitlines() if l.startswith("def ")]
  assert defs == ["def main(argv=None):"]


def test_world_fixture_lives_in_conftest_and_injects_the_package(world):
  import conftest, superegm
  # A definition sits at column 0; the plan's bare `"def world("` would match this very line.
  assert callable(conftest.make_pr) and "\ndef world(" not in Path(__file__).read_text(encoding="utf-8")
  assert world.ns is vars(superegm) and superegm.GH is world.gh and superegm.NOW() == world.clock
  world.gh.extend("widget", lambda args, cwd, token=None: (0, json.dumps({"args": args[1:], "token": token}), ""))
  seen = json.loads(superegm.gh(["widget", "list"], token="t0k"))
  assert seen == {"args": ["list"], "token": "t0k"} and world.gh.calls[-1] == ["widget", "list"]
  with pytest.raises(superegm.GhError):
    superegm.gh(["nope"])
  assert world.spec == world.repo / "docs/designs/sample.md" and Path.cwd() == world.repo


def test_store_paths_are_prefixed_by_the_handoff_hex(world):
  import superegm
  root = world.artifacts
  assert superegm.store(world.repo).root == root and not str(root).startswith(str(world.repo))
  assert superegm.load_config(world.repo)["_source"].endswith(".superegm/config.json")
  a, b = superegm.Store(root, handoff_id="sample-111111"), superegm.Store(root, handoff_id="sample-222222")
  assert a.path("state") == b.path("state") == root / "state.json"
  assert a.path("runcards", "plan-0001") == root / "runcards/plan-0001.json"
  assert a.path("approvals", "sample") == root / "approvals/sample.json"
  assert a.path("plan") == root / "handoff_plan.md" and a.path("report", 2) == root / "wave_2_report.md"
  assert a.path("unit", "U01") == root / "111111/unit_U01.md" and b.path("unit", "U01") == root / "222222/unit_U01.md"
  assert a.path("foreman", "U01") == root / "111111/foreman/U01.json"
  assert a.path("launches", "U01_r1_prompt.md") == root / "111111/launches/U01_r1_prompt.md"
  assert a.path("review", "U01", 7) == root / "111111/review/U01/pr7" and a.path("worktrees", "U01") == root / "111111/worktrees/U01"
  with pytest.raises(superegm.HandoffError, match="no handoff in this store"):
    superegm.Store(root).path("foreman", "U01")
  superegm.atomic_write(a.path("foreman", "U01"), {"rounds": []})
  assert json.loads((root / "111111/foreman/U01.json").read_text(encoding="utf-8")) == {"rounds": []}
  superegm.atomic_write(a.path("file", "x.diff"), b"\x00bin")
  assert (root / "x.diff").read_bytes() == b"\x00bin"
  superegm.journal(a, "first fact"); superegm.journal(a, "second fact")
  lines = (root / "journal.md").read_text(encoding="utf-8").splitlines()
  assert [l.split(" ", 1)[1] for l in lines] == ["first fact", "second fact"] and lines[0].startswith("2023-")
  assert superegm.spec_slug("/x/docs/specs/2026-11-03-superegm-design.md") == "2026-11-03-superegm-design"
  assert not list(root.rglob("*.tmp*"))
  assert world.run("graph", "--plan", world.plan)[0] == 0 and (root / "state.json").is_file()


WRITES = {"approve_spec": {"approvals"}, "graph": {"state", "plan", "units", "unit", "bodies"},
          "scan": {"file"}, "gate": {"state"},
          "dry_run": {"file", "state"}, "apply": {"state", "file"},
          "verify": {"state"}, "status": {"state"}, "launch": {"state", "runcards"}, "decide": {"state", "plan", "units", "unit", "bodies", "file"},
          "record_launch": {"launches"}, "collect": {"foreman", "review", "reviews"}, "prepare": {"foreman", "review"},
          "launch_builder": {"launches", "orient_unit"}, "interrupt": {"launches", "foreman"}, "clean": set(),
          "orient": {"orient", "orient_unit"},
          "runcard": {"runcards"}, "init": set(), "doctor": set()}


@pytest.mark.parametrize("name, kinds", sorted(WRITES.items()))
def test_atomic_write_enforces_each_modules_writes(world, monkeypatch, name, kinds):
  import superegm
  module = importlib.import_module(f"superegm.{name}")
  assert module.WRITES == frozenset(kinds)
  st = superegm.Store(world.artifacts, handoff_id="sample-abcdef")
  monkeypatch.setattr(superegm, "STORE", st)
  monkeypatch.setattr(superegm, "CURRENT_WRITES", module.WRITES)
  monkeypatch.setattr(superegm, "CURRENT_SUBCOMMAND", name)
  for kind in kinds:
    superegm.atomic_write(st.path(kind, *{"review": ("U01", 1), "report": (1,)}.get(kind, ("U01",) if kind not in ("state", "plan", "units", "bodies") else ())), "x")
  with pytest.raises(superegm.HandoffError, match=f"{name} may not write judges"):
    superegm.atomic_write(st.path("judges", "q1", "verdict.json"), {})
  superegm.atomic_write(world.plan, world.plan.read_text(encoding="utf-8"))  # outside the store: unchecked
  assert not list(world.artifacts.rglob("*.tmp*"))


@pytest.mark.parametrize("where, expected", [
  ("labels.unit", "superegm:unit"), ("labels.wave_prefix", "superegm:wave-"),
  ("labels.handoff_prefix", "superegm:handoff-"), ("labels.tracking", "superegm:tracking"),
  ("labels.stopped", "superegm:stopped"), ("BRANCH_PREFIX", "superegm"),
  ("error prefix", "superegm: "), ("state file", "state.json"),
])
def test_config_and_label_renames(world, where, expected):
  import superegm
  config = superegm.load_config(world.repo)
  if where.startswith("labels."):
    assert config["labels"][where[7:]] == expected
    assert set(superegm.DEFAULT_CONFIG["labels"]) == {"unit", "wave_prefix", "handoff_prefix", "tracking", "stopped", "extra"}
  elif where == "BRANCH_PREFIX":
    assert superegm.BRANCH_PREFIX == expected
    assert world.run("graph", "--plan", world.plan)[0] == 0
    body = (world.artifacts / "handoff_bodies.md").read_text(encoding="utf-8")
    assert f"Branch: `superegm/{state_of(world)['handoff_id']}/U01`" in body
  elif where == "error prefix":
    code, out = world.run("graph", "--plan", world.repo / "missing.md")
    assert code == 1 and out.startswith(expected) and "egm_handoff" not in out
  else:
    assert world.run("graph", "--plan", world.plan)[0] == 0
    assert (world.artifacts / expected).is_file() and not (world.artifacts / "handoff_state.json").exists()


def test_commit_trailer_defaults_empty_and_must_be_a_string(world):
  import superegm
  assert superegm.DEFAULT_CONFIG["commit_trailer"] == "" and superegm.load_config(world.repo)["commit_trailer"] == ""
  set_config(world, repo=REPO, commit_trailer=1)
  with pytest.raises(superegm.HandoffError, match="commit_trailer must be a string"):
    superegm.load_config(world.repo)


def test_init_writes_the_config_with_every_key_and_refuses_another_base(tmp_path, capsys, monkeypatch):
  repo = make_repo(tmp_path / "fresh")
  monkeypatch.chdir(repo)
  harness = Harness(capsys)
  harness.gh.extend("api", lambda args, cwd, token=None: (0, "octocat\n", "") if args[1:] == ["user", "-q", ".login"] else (1, "", "unexpected"))
  code, out = harness.run("init", "--artifacts-dir", str(tmp_path / "store"))
  assert code == 0 and '1. Create the builder account and its token as README.md, "Before the first run" step 1 says' in out
  assert "SUPEREGM_BUILDER_TOKEN" in out and "fine-grained" not in out and "Contents read" not in out
  assert "branch protection" in out and "config.owners" in out and out.rstrip().splitlines()[-1] == "then run `superegm doctor`"
  config = json.loads((repo / ".superegm/config.json").read_text(encoding="utf-8"))
  assert set(config) == {"repo", "base", "artifacts_dir", "mode", "max_in_flight", "labels", "issue_template",
                         "tracking_issue_title", "banned_terms", "fix_request_mention", "allowed_mentions",
                         "reviewers", "astra", "judges", "builder", "ci_wait_minutes", "commit_trailer", "owners", "owner_team",
                         "pr_block_file"}
  assert config["owners"] == ["octocat"] and config["owner_team"] is None and config["pr_block_file"] is None
  assert config["repo"] == REPO and config["base"] == "main" and config["artifacts_dir"] == str(tmp_path / "store")
  assert config["mode"] == "normal" and config["max_in_flight"] == 5 and config["ci_wait_minutes"] == 30
  assert config["labels"]["stopped"] == "superegm:stopped"
  assert config["reviewers"] == {"spec": ["design", "zoom-out"], "plan": ["readiness", "proportion", "set"],
                                 "head": ["change-review"], "integrate": ["design"]}  # I-2: the spec's panels
  assert config["judges"]["min_vendors"] == 1 and [m["name"] for m in config["judges"]["members"]] == ["fable", "opus", "astra"]
  assert config["builder"]["permission_mode"] == "acceptEdits" and config["builder"]["gh_token_env"] == "SUPEREGM_BUILDER_TOKEN"
  pinned = json.loads((ROOT / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]["allowed_tools"]
  assert config["builder"]["allowed_tools"] == pinned and "Bash(gh pr create:*)" in pinned  # I-1: the spec's prefix forms
  assert not any("git push" in tool for tool in pinned)
  assert git(["status", "--porcelain"], repo).strip().startswith("??"), "init writes; approve-spec commits (§7)"
  import superegm
  assert superegm.load_config(repo)["ci_wait_minutes"] == 30
  code, out = harness.run("init", "--artifacts-dir", str(tmp_path / "store"))
  assert code == 1 and ".superegm/config.json exists" in out
  (repo / ".superegm/config.json").unlink()
  code, out = harness.run("init", "--artifacts-dir", str(tmp_path / "store"), "--base", "develop")
  assert code == 1 and "default branch" in out
  code, out = harness.run("init", "--artifacts-dir", str(repo / "inside"))
  assert code == 1 and "outside the working tree" in out
  harness.gh.extend("api", lambda args, cwd, token=None: (1, "", "gh: not logged in"))
  code, out = harness.run("init", "--artifacts-dir", str(tmp_path / "store"))
  assert code == 1 and "gh api user" in out and not (repo / ".superegm/config.json").exists()


@pytest.mark.parametrize("key, value, message", [
  ("owners", "gsVAM", "owners must be a list of GitHub logins"),
  ("owner_team", "owners", "owner_team must be `<org>/<slug>` or null"),
  ("pr_block_file", ["x"], "pr_block_file must be a path relative to the repository root or null"),
])
def test_launch_policy_keys_default_and_validate(world, key, value, message):
  import superegm
  assert [superegm.DEFAULT_CONFIG[k] for k in ("owners", "owner_team", "pr_block_file")] == [[], None, None]
  assert superegm.load_config(world.repo)["owners"] == []            # the world's config has no `owners` key
  set_config(world, repo=REPO, **{key: value})
  with pytest.raises(superegm.HandoffError, match=re.escape(message)):
    superegm.load_config(world.repo)


F = chr(96) * 3
BODY = f"""<!-- superegm:handoff=sample-abc123 unit=U07 spec=deadbeef -->
# U07 — File
Spec: `docs/specs/x.md` @ a263acc · `docs/specs/x.md:732-756 (## 10. File (phase 4))`

## Objective
One sentence.
## Interfaces
- Consumes: store(repo_root) (U03)
- Consumes: superegm runcard open (U03)
- Produces: superegm apply --yes → one line; exit 0/1
## Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `pytest tests/unit/test_file.py -q` — the filing tests pass
3. Exists `skills/plan/scripts/superegm/apply.py`
4. CI green on the head
## Global constraints
- Python 3.11, standard library only
## Review focus (this unit)
- U07: a crash mid-apply — recovery reuses the issue; pinned by `test_marker_recovery`
## Steps
1. Write the failing test `test_marker_recovery` in `tests/unit/test_file.py`:
   {F}python
   def test_marker_recovery(world): ...
   {F}
   Run `pytest tests/unit/test_file.py::test_marker_recovery -q`; expected: FAIL (`AttributeError`).
   Implement `recover(handoff) -> dict` in `skills/plan/scripts/superegm/apply.py`.
   Run the same command; expected: PASS. Commit `test(S1): recovery` then `feat(S1): recovery`.
## Decide before build
- none
## Scope, order and risk
Scope: … · Size: M
"""


def test_body_parsers_markers_and_heading():
  from superegm import body
  assert body.run_commands(BODY) == ["pytest tests/unit/test_file.py -q", "pytest tests/unit/test_file.py::test_marker_recovery -q"]
  assert body.step_paths(BODY) == [(1, "tests/unit/test_file.py", "skills/plan/scripts/superegm/apply.py")]
  assert body.dod_items(BODY) == [(2, "run", "pytest tests/unit/test_file.py -q"),
                                  (3, "exists", "skills/plan/scripts/superegm/apply.py"), (4, "ci", "CI green on the head")]
  assert body.consumes(BODY) == [("store", "U03"), ("superegm runcard open", "U03")]
  assert body.MARKER_RE.match(BODY).groups() == ("sample-abc123", "U07", "deadbeef")
  assert body.MARKER_RE.match("<!-- egm:handoff=x unit=U01 -->") is None
  assert body.fill_numbers("see #<U04> and #<tracking>", {"U04": 12}, 7) == "see #12 and #7"
  assert body.normalise("a \r\nb  \n\n") == "a\nb"
  assert body.DECISION_HEADING.format(id="D1") == "**Decision D1:**"
  import superegm
  assert superegm.DEFAULT_TEMPLATE.splitlines()[0] == "<!-- superegm:handoff={{handoff_id}} unit={{unit_id}} spec={{spec_sha256}} -->"
  assert superegm.TRACKING_TEMPLATE.splitlines()[0] == "<!-- superegm:handoff={{handoff_id}} unit=tracking spec={{spec_sha256}} -->"


def test_runcard_open_close_child_and_interrupt(world):
  import superegm
  read = lambda rid: json.loads((world.artifacts / f"runcards/{rid}.json").read_text(encoding="utf-8"))
  code, out = world.run("runcard", "open", "--skill", "plan", "--artifact", world.spec)
  first = out.strip()
  assert code == 0 and first == "plan-0001"
  card = read(first)
  assert set(card) == {"skill", "artifact", "artifact_sha256", "reviewers", "tiering", "mode", "parent",
                       "opened_at", "closed_at", "interrupted_at", "produced"}
  assert card["artifact"] == str(world.spec) and card["artifact_sha256"] == hashlib.sha256(world.spec.read_bytes()).hexdigest()
  assert card["mode"] == "normal" and card["produced"] == [] and card["closed_at"] is None and card["parent"] is None
  assert world.run("runcard", "open", "--skill", "wave", "--artifact", world.spec, "--mode", "leavemealone")[1].strip() == "wave-0002"
  assert read("wave-0002")["mode"] == "leavemealone"
  code, out = world.run("runcard", "open", "--skill", "judges", "--artifact", "q.md", "--parent", first)
  child = out.strip()
  assert code == 0 and read(child)["parent"] == first and read(child)["artifact"] == "q.md"
  code, out = world.run("runcard", "open", "--skill", "judges", "--artifact", "q.md", "--parent", "plan-9999")
  assert code == 1 and "runcard: parent plan-9999 not found" in out
  second = world.run("runcard", "open", "--skill", "plan", "--artifact", world.spec)[1].strip()
  assert read(first)["interrupted_at"] and read(child)["interrupted_at"] is None and read("wave-0002")["interrupted_at"] is None
  superegm.card_add(superegm.store(world.repo), second, "produced", "handoff_plan.md")
  assert read(second)["produced"] == ["handoff_plan.md"]
  assert world.run("runcard", "close", second) == (0, f"closed {second}\n")
  assert read(second)["closed_at"]
  code, out = world.run("runcard", "close", second)
  assert code == 1 and f"runcard: {second} is closed" in out
  lines = (world.artifacts / "journal.md").read_text(encoding="utf-8")
  assert f"runcard open {first} plan" in lines and f"runcard interrupted {first}" in lines and f"runcard close {second}" in lines


def _closed(w):
  rid = w.open_card("wave", w.spec); assert w.run("runcard", "close", rid)[0] == 0; return rid
def _interrupted(w):
  rid = w.open_card("wave", w.spec); w.open_card("wave", w.spec); return rid
def _child_of_interrupted(w):
  parent = _interrupted(w); return w.run("runcard", "open", "--skill", "foreman", "--artifact", "U01", "--parent", parent)[1].strip()


@pytest.mark.parametrize("setup, unit, reason", [
  (lambda w: None, "U01", r"--runcard is required"),
  (lambda w: "plan-9999", "U01", r"plan-9999 not found"),
  (_closed, "U01", r"wave-\d+ is closed"),
  (_interrupted, "U01", r"wave-\d+ is interrupted"),
  (lambda w: w.card("plan"), "U01", r"plan-\d+ belongs to plan, not foreman\|wave"),
  (lambda w: w.open_card("wave", "U02"), "U01", r"wave-\d+ is for U02, not U01"),
  (lambda w: w.open_card("wave", "U02"), None, r"wave-\d+ is for U02, not .*sample\.md"),
  (lambda w: w.card("wave"), "U01", None),
  (lambda w: w.open_card("wave", "U01"), "U01", None),
  (_child_of_interrupted, "U01", None),
])
def test_runcard_refusals(world, setup, unit, reason):
  import superegm
  assert world.run("graph", "--plan", world.plan)[0] == 0
  args = argparse.Namespace(runcard=setup(world), unit=unit)
  if reason is None:
    assert superegm.require_runcard(args, {"wave", "foreman"})["skill"] in ("wave", "foreman")
  else:
    with pytest.raises(superegm.HandoffError, match="^runcard: " + reason):
      superegm.require_runcard(args, {"wave", "foreman"})


GATED = [(("approve-spec", "--spec", "SPEC", "--yes"), "review-spec"), (("graph",), "plan"),
         (("gate", "--pass", "--spec", "SPEC"), "file"), (("dry-run", "--spec", "SPEC"), "file"), (("apply", "--yes", "--spec", "SPEC"), "file"),
         (("verify", "--spec", "SPEC"), "file"), (("status",), "wave"), (("launch",), "wave"),
         (("decide", "--unit", "U03", "--decision", "D2", "--answer", "25"), "plan"),
         (("record-launch", "--unit", "U01"), "wave"),
         (("collect", "--unit", "U01", "--dispatch", "d1"), "wave"), (("prepare", "--unit", "U01", "--dispatch", "d1"), "wave")]


@pytest.mark.parametrize("argv, skill", GATED)
def test_every_absorbed_writing_subcommand_is_gated(world, argv, skill):
  argv = [str(world.spec) if a == "SPEC" else a for a in argv]
  other = world.open_card("brainstorming", world.spec)
  snapshot = lambda: sorted(str(p) for p in world.artifacts.rglob("*") if p.name != "journal.md")
  before = snapshot()
  code, out = world.run(*argv, "--plan", world.plan, card=None)
  assert code == 1 and "runcard: --runcard is required" in out, out
  code, out = world.run(*argv, "--plan", world.plan, "--runcard", other, card=None)
  assert code == 1 and f"runcard: {other} belongs to brainstorming" in out, out
  assert snapshot() == before and not world.gh.calls, "refused before any store write or GitHub read"
  if argv[0] == "launch":
    launchable(world)  # past its card, launch fetches origin first: never GitHub from a test
  code, out = world.run(*argv, "--plan", world.plan, "--runcard", world.card(skill), card=None)
  assert "runcard:" not in out, out
  assert "scan" not in {a for a, _ in GATED} and "--runcard" not in world.run("scan", "--help", card=None)[1]


def test_approve_spec_writes_the_approvals_record_with_handoff_id(world):
  """U04: the spec ends in `## Units`, its review is converged, and the record names the review (spec section 8)."""
  world.spec.write_text(DESIGN + "\n## Units\n\n| Unit | Scope | Blocked by | Size |\n| --- | --- | --- | --- |\n| U01 | queue | — | S |\n",
                        encoding="utf-8")
  cid = world.card("review-spec")
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", world.spec, "--reviewers", "design", "--runcard", cid)
  assert code == 0, out
  rid = out.strip()
  (world.artifacts.parent / "design-1.txt").write_text("", encoding="utf-8")
  code, out = world.run("review", "record", "--review", rid, "--round", "1", "--reviewer", "design",
                        "--findings", world.artifacts.parent / "design-1.txt", "--runcard", cid)
  assert code == 0, out
  code, out = world.run("approve-spec", "--spec", world.spec)
  assert code == 0 and "Approve | Stop" in out and not (world.artifacts / "state.json").exists()
  code, out = world.run("approve-spec", "--spec", world.spec, "--yes")
  assert code == 0, out
  record = json.loads((world.artifacts / "approvals/sample.json").read_text(encoding="utf-8"))
  sha = hashlib.sha256(world.spec.read_bytes()).hexdigest()
  assert set(record) == {"path", "sha256", "commit", "runcard", "review", "approved_at", "escalated", "amended", "voided_by", "handoff_id"}
  assert record["path"] == str(world.spec) and record["sha256"] == sha and record["handoff_id"] == f"sample-{sha[:6]}"
  assert record["runcard"] == cid and record["review"] == rid and record["amended"] == [] and record["voided_by"] is None
  assert record["commit"] == git(["rev-parse", "HEAD"], world.repo).strip()
  assert world.run("graph", "--plan", world.plan)[0] == 0
  assert state_of(world)["handoff_id"] == record["handoff_id"]
  assert json.loads((world.artifacts / "handoff_units.json").read_text(encoding="utf-8"))["handoff_id"] == record["handoff_id"]


def test_foreman_file_schema_and_round_entries(world):
  import superegm
  assert world.run("graph", "--plan", world.plan)[0] == 0
  st = superegm.store(world.repo)
  assert superegm.load_foreman(st, "U01") == {"dispatch_id": None, "rounds": [], "decisions": [], "rulings": []}
  data = superegm.load_foreman(st, "U01")
  superegm.round_entry(data, 2)["runcard"] = world.card("wave")  # as a foreman subcommand records a round
  superegm.save_foreman(st, "U01", data)
  path = world.artifacts / state_of(world)["handoff_id"][-6:] / "foreman/U01.json"
  data = json.loads(path.read_text(encoding="utf-8"))
  assert set(data) == {"dispatch_id", "rounds", "decisions", "rulings"} and len(data["rounds"]) == 1
  entry = data["rounds"][0]
  assert entry["round"] == 2 and entry["runcard"] == world.card("wave")
  assert {"round", "runcard", "launch", "head", "phase", "dispatch_id", "outcome", "posted_at"} <= set(entry)
  assert superegm.round_entry(data, 2) is data["rounds"][0]
  assert superegm.round_entry(data, 3)["round"] == 3 and [r["round"] for r in data["rounds"]] == [2, 3]
  assert not list(world.artifacts.glob("foreman_*_state.json"))


def test_require_frozen_units_refuses_a_filed_units_drift(world):
  applied(world)
  launchable(world)
  assert world.run("status")[0] == 0
  text = world.plan.read_text(encoding="utf-8")
  world.plan.write_text(text.replace("An in-memory queue with enqueue and dequeue exists.", "A queue exists."), encoding="utf-8")
  for argv in (("status",), ("launch",), ("prepare", "--unit", "U01", "--dispatch", "d1")):
    world.gh.calls.clear()
    code, out = world.run(*argv)
    assert code == 1 and "U01 is filed and frozen: its section in handoff_plan.md differs from the stored one" in out, (argv, out)
    assert not world.gh.calls
  world.plan.write_text(text, encoding="utf-8")
  state = state_of(world)
  state["filings"] = [{"sha256": state["confirmed_sha256"], "writes": state["confirmed"]["writes"], "at": "2026-11-03T00:00:00Z"}]
  (world.artifacts / "state.json").write_text(json.dumps(state), encoding="utf-8")
  assert world.run("status")[0] == 0
  unit_file = world.artifacts / state["handoff_id"][-6:] / "unit_U01.md"
  unit_file.write_text(unit_file.read_text(encoding="utf-8") + "\n## Decisions answered since the issue was posted\n\n- none\n", encoding="utf-8")
  assert world.run("status")[0] == 0, "text outside the fence is not the body"
  unit_file.write_text(unit_file.read_text(encoding="utf-8").replace("## Objective\nAn in-memory queue", "## Objective\nA queue"), encoding="utf-8")
  code, out = world.run("status")
  assert code == 1 and "U01 is filed and frozen: unit_U01.md no longer carries the filed body" in out
  for name in ("status", "launch", "prepare"):
    source = (SCRIPTS / f"superegm/{name}.py").read_text(encoding="utf-8")
    assert "require_frozen_units" in source and "require_confirmed_plan" not in source and "require_reviewed_pair" not in source
  assert "not what the reviewed plan renders" not in (SCRIPTS / "superegm/prepare.py").read_text(encoding="utf-8")


def test_defer_and_published_are_gone(world):
  import superegm
  subs = next(a for a in superegm.build_parser()._actions if isinstance(a, argparse._SubParsersAction)).choices
  assert "defer" not in subs
  assert "--published" not in {f for a in subs["decide"]._actions for f in a.option_strings}
  gh = applied(world)
  assert state_of(world)["decisions"]["U03/D2"]["answer"] == "(a)"  # answered before the filing (spec section 9.1)
  code, out = world.run("decide", "--unit", "U03", "--decision", "D2", "--answer", "(b)")
  assert code == 0 and "PUBLISHED" not in out
  code, out = world.run("status")
  assert code == 0 and "U03/D2" not in out and "PUBLISHED" not in out
  assert set(state_of(world)["decisions"]["U03/D2"]) == {"answer", "by", "decided_at"}
  close_as_completed(gh, 2); close_as_completed(gh, 3)
  make_pr(gh, 41, "a" * 40, merged="2026-11-02T10:00:00Z", closes=[(REPO, 3)])
  gh.graphql[3] = [{**gh.prs[41], "repository": {"nameWithOwner": REPO}}]
  assert world.run("status", "--confirm-landed", "U01")[0] == 0
  assert "ready: U03" in world.run("status")[1]  # released; `launch` marks the ready units (test_builders.py)
  for name in ("apply", "verify", "launch", "status"):
    assert "deferred" not in (SCRIPTS / f"superegm/{name}.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("path, pattern", [
  ("skills/plan/scripts/superegm.py", r"defer|egm-handoff|egm-wave|egm_handoff"),
  ("skills/plan/scripts/superegm/__init__.py", r"\.egm/handoff\.json|handoff_state\.json|egm_handoff|re-run the gate|(?<!super)egm:(?!generated)|unpublished|NOT PUBLISHED"),
  ("skills/plan/scripts/superegm/decide.py", r"PUBLISHED|--published|stays blocked until"),
  ("skills/plan/scripts/superegm/launch.py", r"unpublished"),
  ("skills/plan/scripts/superegm/status.py", r"PUBLISHED"),
  ("skills/plan/scripts/superegm/verify.py", r"defer"),
  ("skills/plan/scripts/superegm/apply.py", r"defer"),
  ("skills/plan/scripts/superegm/prepare.py", r"reviewed plan renders|the gate"),
  ("tests/unit/conftest.py", r"\.egm/|handoff_state\.json|(?<!super)egm:|egm_handoff"),
])
def test_removed_mechanisms_are_not_named(path, pattern):
  hits = [l for l in (ROOT / path).read_text(encoding="utf-8").splitlines() if re.search(pattern, l)]
  assert not hits, hits


MOVED = [("test_plan.py", "test_scan_banned_terms_mentions_and_size"),
         ("test_file.py", "test_apply_creates_labels_issues_and_links_in_order_and_a_rerun_writes_nothing"),
         ("test_file.py", "test_subprocess_command_shape_with_fake_gh_on_path"),
         ("test_file.py", "test_apply_recovers_issues_by_the_new_marker_after_a_crash"),
         ("test_builders.py", "test_launch_refuses_each_precondition"),
         ("test_builders.py", "test_record_launch_appends_running_then_records_the_exit"),
         ("test_events.py", "test_wait_prints_deadline_only_and_saves_once"),
         ("test_events.py", "test_status_pr_matching_rules"),
         ("test_events.py", "test_the_helper_is_single_writer_by_design"),
         ("test_foreman.py", "test_prepare_reviews_the_tip_it_fetches"),
         ("test_foreman.py", "test_collect_records_foreman_findings")]
DELETED = ("test_every_helper_command_the_skills_document_exists", "test_the_command_reference_documents_only_real_flags",
           "test_defer_edits_one_label_and_verifies", "test_defer_refuses_a_wave_label_the_repository_does_not_have",
           "test_repeated_deferrals_verify_against_the_current_wave", "test_an_unpublished_decision_does_not_release_the_unit",
           "test_the_wave_skill_records_decision_publication", "test_prepare_refuses_a_unit_file_the_plan_does_not_render")


@pytest.mark.parametrize("target, name", MOVED)
def test_later_units_tests_live_in_their_own_files(target, name):
  here = Path(__file__).parent
  assert f"def {name}(" in (here / target).read_text(encoding="utf-8")
  assert f"def {name}(" not in (here / "test_helper.py").read_text(encoding="utf-8")
  everywhere = "".join(p.read_text(encoding="utf-8") for p in here.glob("test_*.py"))
  assert not [d for d in DELETED if f"def {d}(" in everywhere]


def test_store_kinds_answer_to_the_interfaces_names(world):
  """The Interfaces block names `handoff_plan|handoff_units|handoff_bodies|wave_report|questions`;
  S3's test names `plan|units|bodies|report`. A sibling unit may use either."""
  import superegm
  root = world.artifacts
  a = superegm.Store(root, handoff_id="sample-111111")
  assert a.path("handoff_plan") == a.path("plan") and a.path("handoff_units") == a.path("units")
  assert a.path("handoff_bodies") == a.path("bodies") and a.path("wave_report", 2) == a.path("report", 2)
  assert a.path("approvals", "sample.json") == a.path("approvals", "sample")
  assert a.path("runcards", "plan-0001.json") == a.path("runcards", "plan-0001")
  assert a.path("questions", "q1.md") == root / "questions/q1.md" and a.kind_of(root / "questions/q1.md") == "questions"
  assert a.kind_of(a.path("handoff_units")) == "units"
  superegm.STORE, superegm.CURRENT_WRITES, superegm.CURRENT_SUBCOMMAND = a, frozenset({"handoff_units"}), "x"
  try:
    superegm.atomic_write(a.path("units"), {})  # a module may declare the kind under either name
    with pytest.raises(superegm.HandoffError, match="x may not write plan"):
      superegm.atomic_write(a.path("handoff_plan"), "")
  finally:
    superegm.STORE = superegm.CURRENT_WRITES = superegm.CURRENT_SUBCOMMAND = None
