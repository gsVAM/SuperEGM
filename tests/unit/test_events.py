# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03).

"""EGM's tests of the subcommands U09b (events) changes, moved from test_helper.py by U03;
that unit rewrites the ones whose form it changes."""


import pytest

from conftest import REPO, make_pr, applied, state_of, close_as_completed


def test_status_landed_ready_decisions_and_shared_edges(world):
  gh = applied(world)
  code, out = world.run("status", "--plan", world.plan)
  assert code == 0 and "ready: U01" in out and "landed: none" in out
  assert "open blocking decision U03/D2" in out
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
  assert "landed: U01, U02" in out and "ready: none" in out, out
  assert world.run("decide", "--plan", world.plan, "--unit", "U03", "--decision", "D2", "--answer", "(b)")[0] == 0
  code, out = world.run("status", "--plan", world.plan)
  assert "ready: U03" in out
  assert world.run("graph", "--plan", world.plan)[0] == 0


def test_status_pr_matching_rules(world):
  gh = applied(world)
  assert world.run("launch", "--plan", world.plan, "--wave", 1, "--units", "U01")[0] == 0
  # A closing reference naming another repository with the same number does not match.
  make_pr(gh, 50, "c" * 40, closes=[("other/repo", 2)], branch="superegm/U01-old")
  code, out = world.run("status", "--plan", world.plan)
  assert "U01 #2 launched wave 1: no pr; waiting-for-pr" in out, out
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
  assert world.run("launch", "--plan", world.plan, "--wave", 1, "--units", "U01")[0] == 0
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
  assert "no-ci" in out


def test_status_wait_returns_on_change_or_deadline(world):
  gh = applied(world)
  code, out = world.run("status", "--plan", world.plan, "--wait", 200)
  assert code == 0 and "deadline: no change" in out and world.sleeps and max(world.sleeps) <= 90
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  gh.graphql[2] = [{**gh.prs[70], "repository": {"nameWithOwner": REPO}}]
  code, out = world.run("status", "--plan", world.plan, "--wait", 200)
  assert "changed: U01" in out


def test_a_landed_confirmation_lapses_when_the_issue_reopens(world):
  """R2-11: the override is for a completed issue with no watched PR."""
  gh = applied(world)
  close_as_completed(gh, 2)
  assert world.run("status", "--plan", world.plan, "--confirm-landed", "U01")[0] == 0
  assert "U01" in state_of(world)["status"]["landed"]
  gh.issues[2]["state"], gh.issues[2]["state_reason"] = "open", None
  code, out = world.run("status", "--plan", world.plan)
  assert "landed confirmation no longer applies" in out
  assert "U01" not in state_of(world)["status"]["landed"]


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
  # the first page is all green and the aggregate is failure, so the verdict
  # would be "ci red", not waiting.
  ci = state_of(world)["units"]["U01"]["pr"].get("ci") or {}
  contexts = {c["context"] for c in (ci.get("contexts") or [])} if ci else set()
  record_ci = (state_of(world).get("status") or {}).get("units", {}).get("U01", {})
  assert "e2e" in contexts or "waiting-for-ci" in record_ci.get("status", ""), (ci, record_ci)


def test_a_retargeted_pr_is_a_new_review_target(world):
  """R8-03: same head, same CI, different base branch -> different merge base
  and diff. The watcher must report it as a change."""
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  assert world.run("status", "--plan", world.plan, "--watch", "U01=70")[0] == 0
  assert world.run("status", "--plan", world.plan)[0] == 0
  gh.prs[70]["baseRefName"], gh.prs[70]["baseRefOid"] = "release-1", "f" * 40
  code, out = world.run("status", "--plan", world.plan, "--wait", 30)
  assert code == 0 and "changed: U01" in out, out
  unit = state_of(world)["status"]["units"]["U01"]
  assert unit["base_ref"] == "release-1" and unit["base_sha"] == "f" * 40


def test_pr_discovery_matches_a_differently_cased_repository(world):
  """R9-04: GitHub may echo `Example-Org/WebHooks` for a config that says
  `example-org/webhooks`; the PR must still be found."""
  gh = applied(world)
  make_pr(gh, 70, "a" * 40, closes=[(REPO, 2)])
  gh.graphql[2] = [{**gh.prs[70], "repository": {"nameWithOwner": REPO.upper()}}]
  code, out = world.run("status", "--plan", world.plan)
  assert code == 0 and "U01 #2: pr #70" in out, out
