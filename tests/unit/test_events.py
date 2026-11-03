# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03); `status --wait`, the event lines and the folding (U09b).

"""U09b: `status --wait`, the event lines, the folding; plus EGM's `status` tests U03 moved here."""

import json
import os
from pathlib import Path

import pytest

from conftest import REPO, make_pr, applied, state_of, close_as_completed, mark_launched
from superegm import store

SHA = "a" * 40
T0 = "2026-11-03T10:00:00Z"
WAIT = ("status", "--wait", 200, "--runcard")


def seed(world, monkeypatch, units=None):
  """A filed handoff as the absorbed `status` reads it (EGM's by-hand seed in
  test_foreman.py::test_prepare_fetches_from_the_recorded_remote_into_private_refs; every sample unit is filed,
  U01 #2, U02 #3, U03 #4, `units` overriding: state.json's `units[<id>].number` and one open issue each, id
  1000 + n, since `status` reads every unit's issue under its complete receipt) plus an open
  card from `runcard open --skill wave --artifact <repo>/docs/designs/sample.md` (`assert code == 0, out`).
  Stubs `world.ns["require_frozen_units"]`: the package name every module reaches as `core.<name>`.
  Comments come from conftest's fake (`/issues/<n>/comments` answers `gh.comments.get(n, [])`), since
  every `status` run reads them. Returns (gh, store(world.repo), card id)."""
  units = {"U01": 2, "U02": 3, "U03": 4} | (units or {})
  assert world.run("graph", "--plan", world.plan)[0] == 0
  path = world.artifacts / "state.json"
  state = json.loads(path.read_text(encoding="utf-8"))
  state.update({"remote": "origin", "confirmed_sha256": "x", "verify": {"complete": True, "sha256": "x", "problems": []},
                "units": {uid: {"number": n} for uid, n in units.items()}})
  path.write_text(json.dumps(state), encoding="utf-8")
  gh = world.gh
  for n in units.values():
    gh.issues[n] = {"number": n, "id": 1000 + n, "labels": [], "state": "open", "state_reason": None}
  world.ns["require_frozen_units"] = lambda handoff: None
  code, out = world.run("runcard", "open", "--skill", "wave", "--artifact", str(world.spec), card=None)
  assert code == 0, out
  return gh, store(world.repo), out.strip()


def test_wait_prints_deadline_only_and_saves_once(world, monkeypatch):
  gh, st, card = seed(world, monkeypatch)
  writes, real = [], os.replace
  monkeypatch.setattr(os, "replace", lambda src, dst: (writes.append(Path(dst).name), real(src, dst)))
  code, out = world.run(*WAIT, card)
  assert code == 0 and out == "deadline\n", out
  assert world.sleeps and max(world.sleeps) <= 90 and sum(world.sleeps) >= 200
  assert writes.count("state.json") == 1, writes
  assert "units" in json.loads(st.path("state").read_text(encoding="utf-8"))["status"]


def put(path, text):
  path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def pr(gh, ci=None, merged=None, number=70, sha=SHA, issue=2):
  """make_pr(gh, number, sha, merged=merged, closes=[(REPO, issue)]) plus its gh.graphql[issue] node (the live
  dict, so a later `gh.prs[number].update(...)` reaches both reads); `ci` adds one completed `tests` check run in
  gh.check_runs[sha] (green → success, red → failure) and a success gh.combined[sha]."""
  node = make_pr(gh, number, sha, merged=merged, closes=[(REPO, issue)])
  node["repository"] = {"nameWithOwner": REPO}
  gh.graphql[issue] = [node]
  if ci:
    gh.check_runs[sha] = [{"name": "tests", "status": "completed", "conclusion": "success" if ci == "green" else "failure"}]
    gh.combined[sha] = {"state": "success", "statuses": []}
  return node


def launch(st, result_file, status="running", started_at=T0):
  """put() one round-1 launches[] entry with `status`, `started_at` and `result_file` (U09's keys) at
  st.path("launches", "U01")."""
  put(st.path("launches", "U01"), json.dumps({"launches": [
      {"round": 1, "status": status, "started_at": started_at, "result_file": str(result_file)}]}))


def comment(gh, body, login="builder-bot", cid=500, at="2026-11-03T10:05:00Z", number=2):
  """Appends {id: cid, body, user: {login}, created_at: at} to gh.comments[number], which the fake's
  comments endpoint serves."""
  gh.comments.setdefault(number, []).append({"id": cid, "body": body, "user": {"login": login}, "created_at": at})


def closed(gh, number, login, reason="not_planned"):
  """Closes gh.issues[number] (made if absent: id 1000 + number, labels []) with state_reason=reason and
  closed_by.login."""
  issue = gh.issues.setdefault(number, {"number": number, "id": 1000 + number, "labels": []})
  issue.update({"state": "closed", "state_reason": reason, "closed_by": {"login": login}})


HEAD = f"U01 head pr=70 sha={SHA} ci="
KINDS = [
  ("head pending", lambda gh, st, tmp: pr(gh), [HEAD + "pending"]),
  ("head green", lambda gh, st, tmp: pr(gh, "green"), [HEAD + "green"]),
  ("head red", lambda gh, st, tmp: pr(gh, "red"), [HEAD + "red:tests"]),
  ("exit", lambda gh, st, tmp: (launch(st, tmp / "r1.json"), (tmp / "r1.json.exit").write_text("0\n")),
   ["U01 exit code=0 pr=none status=none"]),
  ("status", lambda gh, st, tmp: comment(gh, "**Builder status:** DONE"),
   ["U01 status word=DONE comment=500 by=builder-bot"]),
  ("landed", lambda gh, st, tmp: (pr(gh, merged="2026-11-02T10:00:00Z"), closed(gh, 2, "gsvam", "completed")),
   ["U01 landed pr=70"]),
  ("closed pr by the builder", lambda gh, st, tmp: (pr(gh, "green"), gh.prs[70].update(state="CLOSED"),
                                                     closed(gh, 70, "builder-bot")),
   [HEAD + "green", "U01 closed pr=70 by=builder-bot"]),
  ("closed issue by the owner", lambda gh, st, tmp: (pr(gh, "green"), closed(gh, 2, "gsvam")),
   [HEAD + "green", "U01 closed issue=2 by=gsvam"]),
]


@pytest.mark.parametrize("kind,arrange,lines", KINDS, ids=[k[0] for k in KINDS])
def test_six_event_kinds(world, monkeypatch, tmp_path, kind, arrange, lines):
  gh, st, card = seed(world, monkeypatch)
  arrange(gh, st, tmp_path)
  code, out = world.run(*WAIT, card)
  assert code == 0 and out.splitlines() == lines, out
  assert not world.sleeps


def exit_file(tmp, code):
  (tmp / "r1.json.exit").write_text(f"{code}\n", encoding="utf-8")


FOLD = [
  ("comment then exit, polls apart", "running",
   [lambda gh, st, tmp: comment(gh, "**Builder status:** BLOCKED\n- (a) keep the old API")], ["deadline"],
   [lambda gh, st, tmp: exit_file(tmp, 0)],
   ["U01 exit code=0 pr=none status=BLOCKED comment=500 by=builder-bot"]),
  ("comment and exit in one poll", "running",
   [lambda gh, st, tmp: (comment(gh, "**Builder status:** DONE"), exit_file(tmp, 0))],
   ["U01 exit code=0 pr=none status=DONE comment=500 by=builder-bot"], [], ["deadline"]),
  ("exit first, comment later", "running",
   [lambda gh, st, tmp: exit_file(tmp, 1)], ["U01 exit code=1 pr=none status=none"],
   [lambda gh, st, tmp: comment(gh, "**Builder status:** DONE_WITH_CONCERNS")],
   ["U01 status word=DONE_WITH_CONCERNS comment=500 by=builder-bot"]),
  ("interrupted launch, then a comment", "interrupted",
   [lambda gh, st, tmp: comment(gh, "**Builder status:** BLOCKED")],
   ["U01 status word=BLOCKED comment=500 by=builder-bot"], [], ["deadline"]),
  ("a comment older than the launch", "running",
   [lambda gh, st, tmp: (comment(gh, "**Builder status:** DONE", at="2026-11-03T09:00:00Z"), exit_file(tmp, 0))],
   ["U01 exit code=0 pr=none status=none"], [], ["deadline"]),
]


@pytest.mark.parametrize("case,launch_status,first,lines1,then,lines2", FOLD, ids=[f[0] for f in FOLD])
def test_exit_and_status_fold(world, monkeypatch, tmp_path, case, launch_status, first, lines1, then, lines2):
  gh, st, card = seed(world, monkeypatch)
  launch(st, tmp_path / "r1.json", status=launch_status)
  for arrange in first:
    arrange(gh, st, tmp_path)
  code, out = world.run(*WAIT, card)
  assert code == 0 and out.splitlines() == lines1, out
  for arrange in then:
    arrange(gh, st, tmp_path)
  code, out = world.run(*WAIT, card)
  assert code == 0 and out.splitlines() == lines2, out


def test_reported_once_and_a_base_move_is_not_an_event(world, monkeypatch):
  gh, st, card = seed(world, monkeypatch, {"U01": 2, "U02": 3})
  pr(gh, "green")
  pr(gh, number=71, sha="b" * 40, issue=3)
  code, out = world.run(*WAIT, card)
  assert out.splitlines() == [HEAD + "green", f"U02 head pr=71 sha={'b' * 40} ci=pending"], out
  saved = json.loads(st.path("state").read_text(encoding="utf-8"))["status"]["units"]
  assert world.run(*WAIT, card)[1] == "deadline\n"
  gh.prs[70]["baseRefOid"], gh.prs[70]["baseRefName"] = "f" * 40, "release-1"
  assert world.run(*WAIT, card)[1] == "deadline\n"
  pr(gh, "green", number=71, sha="b" * 40, issue=3)
  assert world.run("status", "--runcard", card)[0] == 0  # a plain status in between reports nothing
  code, out = world.run(*WAIT, card)
  assert out.splitlines() == [f"U02 head pr=71 sha={'b' * 40} ci=green"], out
  after = json.loads(st.path("state").read_text(encoding="utf-8"))["status"]["units"]
  assert after["U01"] == saved["U01"] and after["U02"] != saved["U02"]


def test_status_landed_ready_decisions_and_shared_edges(world):
  gh = applied(world)
  code, out = world.run("status", "--plan", world.plan)
  assert code == 0 and "ready: U01" in out and "landed: none" in out
  close_as_completed(gh, 2)
  code, out = world.run("status", "--plan", world.plan)
  assert "closed (no watched PR)" in out and "ready: U01" in out
  code, out = world.run("status", "--plan", world.plan, "--confirm-landed", "U01")
  assert "landed: U01" in out and "ready: U02" in out
  # U03 is blocked by U02 and shares a file after it: both edges must land.
  close_as_completed(gh, 3)
  make_pr(gh, 41, "a" * 40, merged="2026-11-02T10:00:00Z", closes=[(REPO, 3)])
  gh.graphql[3] = [{**gh.prs[41], "repository": {"nameWithOwner": REPO}}]
  code, out = world.run("status", "--plan", world.plan)
  assert "landed: U01, U02" in out and "ready: U03" in out, out
  assert world.run("decide", "--plan", world.plan, "--unit", "U03", "--decision", "D2", "--answer", "(b)")[0] == 0
  code, out = world.run("status", "--plan", world.plan)
  assert "ready: U03" in out
  assert world.run("graph", "--plan", world.plan)[0] == 0


def test_status_pr_matching_rules(world):
  gh = applied(world)
  mark_launched(world, "U01")
  # A closing reference naming another repository with the same number does not match.
  make_pr(gh, 50, "c" * 40, closes=[("other/repo", 2)], branch="superegm/U01-old")
  code, out = world.run("status", "--plan", world.plan)
  assert "U01 #2 launched: no pr; waiting-for-pr" in out, out
  # The exact branch of this handoff is a candidate, watched only after --watch.
  make_pr(gh, 51, "d" * 40, branch=f"superegm/{state_of(world)['handoff_id']}/U01")
  code, out = world.run("status", "--plan", world.plan)
  assert "candidate: PRs #51" in out
  assert not state_of(world)["units"]["U01"].get("pr")
  # A closing reference for this repository matches through the fallback listing.
  make_pr(gh, 52, "e" * 40, closes=[(REPO, 2)])
  gh.check_runs["e" * 40] = [{"name": "tests", "status": "completed", "conclusion": "success"}]
  gh.combined["e" * 40] = {"state": "success", "statuses": [{"state": "success"}]}
  code, out = world.run("status", "--plan", world.plan)
  assert "pr #52 head eeeeeee; ci green" in out, out
  # A recorded PR is read by number and never rediscovered.
  gh.calls.clear()
  gh.graphql[2] = [{**make_pr(gh, 53, "f" * 40, closes=[(REPO, 2)]), "repository": {"nameWithOwner": REPO}}]
  code, out = world.run("status", "--plan", world.plan)
  assert "pr #52" in out and not any(c[:2] == ["api", "graphql"] and "number=2" in c for c in gh.calls)
  assert any(c[:3] == ["pr", "view", "52"] for c in gh.calls)
  # Two GraphQL matches ask the user.
  gh.graphql[3] = [{**make_pr(gh, 60, "1" * 40, closes=[(REPO, 3)]), "repository": {"nameWithOwner": REPO}},
                   {**make_pr(gh, 61, "2" * 40, closes=[(REPO, 3)]), "repository": {"nameWithOwner": REPO}},
                   {**make_pr(gh, 62, "3" * 40), "repository": {"nameWithOwner": "other/repo"}}]
  code, out = world.run("status", "--plan", world.plan)
  assert "U02 #3: no pr; ambiguous: PRs #60, #61" in out, out
  code, out = world.run("status", "--plan", world.plan, "--watch", "U02=61")
  assert "U02 #3: pr #61" in out


def test_status_ci_states(world):
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  gh.graphql[2] = [{**gh.prs[70], "repository": {"nameWithOwner": REPO}}]
  mark_launched(world, "U01")
  code, out = world.run("status", "--plan", world.plan)
  assert "waiting-for-ci" in out
  for status in ("pending", "waiting", "requested", "mystery"):
    gh.check_runs["a" * 40] = [{"name": "tests", "status": status, "conclusion": None}]
    code, out = world.run("status", "--plan", world.plan)
    assert "waiting-for-ci" in out, (status, out)
  gh.check_runs["a" * 40] = [{"name": "deploy", "status": "completed", "conclusion": "action_required"}]
  gh.combined["a" * 40] = {"state": "success", "statuses": []}
  code, out = world.run("status", "--plan", world.plan)
  assert "ci red (deploy)" in out
  gh.check_runs["a" * 40] = [{"name": "tests", "status": "completed", "conclusion": "success"}]
  gh.combined["a" * 40] = {"state": "pending", "statuses": [{"state": "pending"}]}
  code, out = world.run("status", "--plan", world.plan)
  assert "waiting-for-ci" in out
  gh.check_runs["a" * 40] = []
  gh.combined["a" * 40] = {"state": "pending", "statuses": []}
  world.advance(31 * 60)
  code, out = world.run("status", "--plan", world.plan)
  assert "waiting-for-ci" in out


def test_a_landed_confirmation_lapses_when_the_issue_reopens(world):
  """R2-11: the override is for a completed issue with no watched PR."""
  gh = applied(world)
  close_as_completed(gh, 2)
  code, out = world.run("status", "--plan", world.plan, "--confirm-landed", "U01")
  assert code == 0 and "landed: U01" in out, out
  gh.issues[2]["state"], gh.issues[2]["state_reason"] = "open", None
  code, out = world.run("status", "--plan", world.plan)
  assert "landed confirmation no longer applies" in out and "landed: none" in out, out


def test_confirm_landed_refuses_when_a_pr_is_watched(world):
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  assert world.run("status", "--plan", world.plan, "--watch", "U01=70")[0] == 0
  code, out = world.run("status", "--plan", world.plan, "--confirm-landed", "U01")
  assert code == 1 and "only for an issue closed as completed" in out


def test_rewatching_writes_the_selection_and_its_observation_together(world):
  """R3-01: saving watch.number=71 while units.U01.pr still described #70 sent
  prepare to the old PR. No concurrency needed."""
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  make_pr(gh, 71, "b" * 40, closes=[(REPO, 2)])
  assert world.run("status", "--plan", world.plan, "--watch", "U01=70")[0] == 0
  assert world.run("status", "--plan", world.plan, "--watch", "U01=71")[0] == 0
  record = state_of(world)["units"]["U01"]
  assert record["watch"]["number"] == 71
  assert record["pr"]["number"] == 71, "the observation must follow the selection"


def test_a_voided_landed_confirmation_does_not_revive(world):
  """R3-04: clearing only the local variable let a close-reopen-close sequence
  resurrect the old confirmation without asking the user again."""
  gh = applied(world)
  close_as_completed(gh, 2)
  assert world.run("status", "--plan", world.plan, "--confirm-landed", "U01")[0] == 0
  gh.issues[2]["state"], gh.issues[2]["state_reason"] = "open", None
  assert world.run("status", "--plan", world.plan)[0] == 0
  close_as_completed(gh, 2)
  code, out = world.run("status", "--plan", world.plan)
  assert "landed: none" in out, out
  assert state_of(world)["units"]["U01"]["landed_confirmation_void"]


def test_a_watcher_does_not_undo_a_newer_human_selection(world):
  """R4-02: watch ownership persisted for the whole of `status --wait`, so the
  watcher wrote its stale selection back over a newer one."""
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  make_pr(gh, 71, "b" * 40, closes=[(REPO, 2)])
  assert world.run("status", "--plan", world.plan, "--watch", "U01=70")[0] == 0
  # another invocation makes the newer choice
  assert world.run("status", "--plan", world.plan, "--watch", "U01=71")[0] == 0
  # the first watcher polls again; it must not resurrect #70
  assert world.run("status", "--plan", world.plan)[0] == 0
  record = state_of(world)["units"]["U01"]
  assert record["watch"]["number"] == 71
  assert record["pr"]["number"] == 71


def test_a_reconfirmed_landing_clears_its_invalidation(world):
  """R4-03: the renewal and the removal of the invalidation must land together."""
  gh = applied(world)
  close_as_completed(gh, 2)
  assert world.run("status", "--plan", world.plan, "--confirm-landed", "U01")[0] == 0
  gh.issues[2]["state"], gh.issues[2]["state_reason"] = "open", None
  assert world.run("status", "--plan", world.plan)[0] == 0
  close_as_completed(gh, 2)
  assert world.run("status", "--plan", world.plan, "--confirm-landed", "U01")[0] == 0
  assert "landed_confirmation_void" not in state_of(world)["units"]["U01"]
  code, out = world.run("status", "--plan", world.plan)
  assert "landed: U01" in out, out


def test_an_edit_the_bodies_do_not_show_still_blocks(world):
  """R4-06: the write list carries the gate hashes as values, so an edit the
  renderer ignores left it unchanged while still reaching the foreman."""
  applied(world)
  assert world.run("status", "--plan", world.plan)[0] == 0
  text = world.plan.read_text(encoding="utf-8")
  marker = "Decide before build\n- none"
  assert marker in text
  world.plan.write_text(
      text.replace(marker, marker + "\n\nBuild note: use the legacy client.", 1),
      encoding="utf-8")
  code, out = world.run("status", "--plan", world.plan)
  assert code == 1 and "U01 is filed and frozen" in out


def test_an_answer_does_not_survive_its_question_changing(world):
  """R4-09: answers were keyed by unit/decision id alone, so an amendment that
  changed the question kept the old answer and its publication."""
  applied(world)
  assert world.run("decide", "--plan", world.plan, "--unit", "U03",
                   "--decision", "D2", "--answer", "(a)")[0] == 0
  text = world.plan.read_text(encoding="utf-8")
  world.plan.write_text(text.replace("Page size for the listing?",
                                     "Retention window for failed jobs?", 1), encoding="utf-8")
  code, out = world.run("status", "--plan", world.plan)
  # the plan no longer matches the reviewed pair, which is itself correct;
  # the answer must also not count once the question has changed
  assert code == 1 or "open blocking decision U03/D2" in out


def test_the_helper_is_single_writer_by_design(world):
  """Concurrency support was removed rather than fixed: four of the seven high
  findings across the review rounds existed only because `status --wait` could
  write while another command ran. `--wait` now only reads."""
  assert "state_lock" not in world.ns, "the lock must be gone, not reinstated"
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  code, out = world.run("status", "--plan", world.plan, "--wait", 60, "--watch", "U01=70")
  assert code == 1 and "--wait only watches" in out
  before = (world.artifacts / "state.json").read_text(encoding="utf-8")
  assert world.run("status", "--plan", world.plan, "--wait", 60)[0] == 0
  after = (world.artifacts / "state.json").read_text(encoding="utf-8")
  assert after != before, "a wait still records what it saw, once, when it returns"


def test_ci_reads_every_page_of_status_contexts(world):
  """R6-04/R7-05: the endpoint returns 30 contexts a page. A pending context
  on page 2 means CI is still running even though page 1 is all green and the
  aggregate says failure - and the fake now returns real pages, so removing
  the pagination branch would fail this test."""
  gh = applied(world)
  head = "a" * 40
  gh.combined[head] = {
      "state": "failure",
      "pages": [{"state": "failure", "statuses": [{"context": "lint", "state": "success"}]},
                {"state": "failure", "statuses": [{"context": "e2e", "state": "pending"}]}],
  }
  make_pr(gh, 70, head, closes=[(REPO, 2)])
  assert world.run("status", "--plan", world.plan, "--watch", "U01=70")[0] == 0
  code, out = world.run("status", "--plan", world.plan)
  assert "waiting-for-ci" in out, out
  assert "ci green" not in out and "ci red" not in out, out
  # The page-2 context must actually have been collected: without pagination
  # the first page is all green and the aggregate is failure, so the word on
  # the head line and in the saved fingerprint would be red, not pending.
  code, out = world.run("status", "--plan", world.plan, "--wait", 30)
  assert code == 0 and out == f"U01 head pr=70 sha={head} ci=pending\n", out
  assert state_of(world)["status"]["units"]["U01"]["ci"] == "pending"


def test_pr_discovery_matches_a_differently_cased_repository(world):
  """R9-04: GitHub may echo `Example-Org/WebHooks` for a config that says
  `example-org/webhooks`; the PR must still be found."""
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  gh.graphql[2] = [{**gh.prs[70], "repository": {"nameWithOwner": REPO.upper()}}]
  code, out = world.run("status", "--plan", world.plan)
  assert code == 0 and "U01 #2: pr #70" in out, out


PACKAGE = Path(__file__).resolve().parents[2] / "skills/plan/scripts/superegm"


@pytest.mark.parametrize("needle", ["NO_CI_SECONDS", "head_seen_at", '"no-ci"', "deadline: no change",
                                    '"changed: "', "A retarget", "exit when a unit changes"])
def test_no_removed_mechanism_named(needle):
  hits = [p.name for p in PACKAGE.glob("*.py") if needle in p.read_text(encoding="utf-8")]
  assert not hits, (needle, hits)
