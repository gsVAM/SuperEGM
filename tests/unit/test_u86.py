# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U86

"""U86 (spec 1.2.1 section 7.6): a respec reaches the builder and the foreman. A touched filed unit is held, relaunched
with reason `respec` through `launch`'s slots, its prompt and `r<n>/amendments.md` carry the respecs its launch record
names, `finish` records the evidence that clears the mark (`head`, `builder_status`), and `status`, `tick_trigger`,
the wave and integrate act on `respec.actionable` and `respec.open`."""

import json
from pathlib import Path

import pytest

from test_u85 import HID, STARTED, MERGED_U1, R1_TEXT, BASE, respec_world
from test_builders import spawn_fake, no_graphify, which  # noqa: F401  the fixtures test_builders' launches run under

BOT = "superegm-builder[bot]"


def journal_of(st):
  path = st.path("journal")
  return path.read_text(encoding="utf-8") if path.is_file() else ""


def finish_world(world, tmp_path, pr, comment):
  """R1 applied touching filed U2 (issue 12), U2's PR `pr` (head `abc123`) or none, one running launch naming R1 and,
  when `comment`, the builder's status comment with that word posted after the launch started."""
  import superegm
  u2 = {"number": 12, **({"pr": {"number": pr, "head": "abc123"}} if pr else {})}
  spec, st = respec_world(world, [(BASE, None), (R1_TEXT, "R1")], {"R1": ["U2"]},
                          state_units={"U0": MERGED_U1["U0"], "U1": {"number": 11}, "U3": {}, "U2": u2})
  superegm.atomic_write(st.path("file", "respec_comment_U2_R1.md"), "**Spec correction R1** for U2\n")
  result = tmp_path / "U2_r1.json"
  Path(str(result) + ".exit").write_text("0\n", encoding="utf-8")
  entry = {"round": 1, "status": "running", "started_at": STARTED, "result_file": str(result), "respecs": ["R1"], "reason": "respec"}
  superegm.atomic_write(st.path("launches", "U2"), {"unit": "U2", "launches": [entry]})
  if pr:
    world.gh.prs[pr] = {"number": pr, "headRefOid": "abc123", "state": "OPEN"}
  world.gh.comments[12] = [
    {"id": 1, "user": {"login": BOT}, "body": "**Builder status:** BLOCKED", "created_at": "2026-11-12T12:00:00Z"},  # before started_at
  ] + ([{"id": 2, "user": {"login": BOT}, "body": f"**Builder status:** {comment}\n- abc123 feat", "created_at": "2026-11-13T02:00:00Z"}]
       if comment else [])
  return st


@pytest.mark.parametrize("pr, comment, gh_fails, head, word, mark", [
  (7, "DONE", None, "abc123", "DONE", None), (7, "BLOCKED", None, "abc123", "BLOCKED", "respec: R1"),
  (None, "DONE", None, None, "DONE", "respec: R1"), (7, None, None, "abc123", None, "respec: R1"),
  (7, "DONE", "head", None, "DONE", "respec: R1"), (7, "DONE", "builder_status", "abc123", None, "respec: R1")])
def test_finish_records_head_and_builder_status(world, tmp_path, pr, comment, gh_fails, head, word, mark):
  # finish reads the PR head and the last accepted builder comment since started_at; a failed read nulls that field only
  from superegm import record_launch, respec
  st = finish_world(world, tmp_path, pr, comment)
  handoff = HID
  if gh_fails == "head":
    world.gh.extend("pr", lambda args, cwd, token=None: (1, "", "gh: HTTP 502"))
  elif gh_fails == "builder_status":
    world.gh.extend("api", lambda args, cwd, token=None: (1, "", "gh: HTTP 502"))
  launches = json.loads(st.path("launches", "U2").read_text(encoding="utf-8"))["launches"]
  record_launch.finish(st, "U2", launches, launches[-1], "exited 0", None, "U2 launch 1 exited 0")
  exit_record = json.loads(st.path("launches", "U2").read_text(encoding="utf-8"))["launches"][-1]
  journal = journal_of(st)
  assert exit_record["status"] == "exited 0" and "U2 launch 1 exited 0" in journal
  assert ("head" in exit_record) is (head is not None)
  if pr and gh_fails != "head":  # the PR read by its own number, never the issue's
    assert any(c[:3] == ["pr", "view", "7"] for c in world.gh.calls)
  assert (exit_record.get("head"), exit_record["builder_status"]) == (head, word) and respec.marks(st, handoff).get("U2") == mark
  assert (f"U2 launch 1 exit read failed: {gh_fails}" in journal) == bool(gh_fails)


@pytest.mark.parametrize("login, body, accepted", [
  ("superegm-builder[bot]", "**Builder status:** DONE", True), ("superegm-builder[bot]", "**Deviation (spec):** x.md:3", True),
  ("stranger", "**Builder status:** DONE", False), ("superegm-builder[bot]", "Quoting:\n**Builder status:** DONE", False)])
def test_builder_comment_filter(login, body, accepted):
  # one filter, moved out of builder_facts, used by builder_facts and finish
  from superegm import record_launch, status
  assert status.builder_comment({"user": {"login": login}, "body": body}, {"superegm-builder[bot]"}) is accepted
  facts = Path(status.__file__).read_text(encoding="utf-8").split("def builder_facts", 1)[1].split("\ndef ", 1)[0]
  assert "builder_comment(" in facts and "builder_comment(" in Path(record_launch.__file__).read_text(encoding="utf-8")


CORRECTION = "**Spec correction R1** for {unit}\n\n```diff\n-- Max retries: 3\n+Max retries: 4\n```\n"


def apply_r1(s, unit):
  """Respec R1 applied to `s`'s handoff as `approve-spec --respec` leaves it: a `respec` approval entry copying the
  opening's frozen fields, `respec/R1.json` touching `unit`, and the unit's comment file (it was filed then)."""
  from test_builders import put  # written as another process writes them: no subcommand's WRITES applies
  path = next((s.root / "approvals").glob("*.json"))
  record = json.loads(path.read_text(encoding="utf-8"))
  entries = record.get("entries") or [{"kind": "opening", "escalated": [], **{k: v for k, v in record.items() if k != "path"}}]
  entries.append({**entries[0], "kind": "respec", "respec": "R1", "review": "spec-r1", "approved_at": "2026-11-14T00:00:00Z",
                  "at": "2026-11-14T00:00:00Z"})
  put(path, json.dumps({"path": record.get("path"), "entries": entries}))
  put(s.path("file", "respec", "R1.json"), json.dumps({"touched": [unit], "untouched": [], "follow_ups": [], "line_map": []}))
  put(s.path("file", f"respec_comment_{unit}_R1.md"), CORRECTION.format(unit=unit))


@pytest.mark.parametrize("approved, in_prompt, pushed_after_start", [
  ("before the prompt", True, True), ("before the prompt", True, False), ("after the prompt", False, True)])
def test_prompt_record_and_amendments_agree(world, tmp_path, capsys, monkeypatch, spawn_fake, which, no_graphify, approved, in_prompt,
                                            pushed_after_start):
  # the prompt, the launch record's respecs and r<n>/amendments.md name the same respecs; astra_brief pastes that file
  import superegm
  import test_builders as tb
  import test_foreman as tf
  from conftest import make_world
  from test_u85 import commit_at
  from superegm import launch_builder, respec
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  if in_prompt:
    apply_r1(s, tb.UNIT)
  else:  # approved once the prompt file is written, before the launch is recorded
    spawn = launch_builder.start_detached
    monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: (apply_r1(s, tb.UNIT), spawn(command, log, env))[1])
  code, out = world.run("launch-builder", "--unit", tb.UNIT, "--round", 1, "--runcard", card)
  assert code == 0, out
  record = tb.launches_of(s)[-1]
  prompt = s.path("launches", f"{tb.UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  # codebase-details-2-6: the saved PR head is a commit made after the launch's started_at (the builder pushed), or one
  # made before it (nothing pushed, and the running launch has no exit evidence): only a push clears the mark
  head = commit_at(world, monkeypatch, "pushed.txt", "2099-01-01T00:00:00Z" if pushed_after_start else "2000-01-01T00:00:00Z")
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["units"][tb.UNIT]["pr"] = {"number": tb.PR, "head": head}
  superegm.atomic_write(s.path("state"), state)
  mark = respec.marks(s, handoff).get(tb.UNIT)
  # the foreman's round on a head that launch built: prepare's amendments.md and the Astra brief from its record
  w = make_world(tmp_path / "foreman", capsys, monkeypatch)
  from superegm import foreman
  monkeypatch.setattr(foreman, "runner_path", lambda: "/x/runner.py")
  built = {"round": 2, "status": "exited 0", "started_at": "2000-01-01T00:00:00Z", "reason": record["reason"],
           "respecs": record.get("respecs", [])}  # relaunched after the posted round 1
  _, _, head2, _ = tf.pr_repo(w, tmp_path / "foreman", monkeypatch)
  st2, _, child, did, _ = tf.dispatched(w, head=head2, rounds=[tf.POSTED_R1], launches=[tf.TWO_LAUNCHES[0], built],
                                        astra={"enabled": True})
  core = __import__("superegm")  # the package as make_world reloaded it
  core.atomic_write(st2.path("file", "respec", "R1.json"), {"touched": [tf.UNIT], "untouched": [], "follow_ups": [], "line_map": []})
  core.atomic_write(st2.path("file", f"respec_comment_{tf.UNIT}_R1.md"), CORRECTION.format(unit=tf.UNIT))
  code, out = w.run("prepare", "--unit", tf.UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  r = st2.path("review", tf.UNIT, f"pr{tf.PR}") / "r2"
  amendments_md = (r / "amendments.md").read_text(encoding="utf-8")
  astra_brief = (r / "astra_brief.md").read_text(encoding="utf-8")
  # reason and respecs come from one read at prompt preparation: a later approval gives neither (finding codebase-details-1-8)
  assert ("# Spec corrections" in prompt and "+Max retries: 4" in prompt) is in_prompt and (record["reason"] == "respec") is in_prompt
  assert (record.get("respecs") == ["R1"]) is in_prompt and ("R1" in amendments_md) is in_prompt and amendments_md in astra_brief
  assert mark == (None if in_prompt and pushed_after_start else "respec: R1")


@pytest.mark.parametrize("u1_running, marked", [(True, "marked: none"), (False, "marked: U2")])
def test_respec_relaunch_waits_for_a_slot(world, monkeypatch, u1_running, marked):
  # max_in_flight 1: a respec relaunch joins the ready-again set and takes a slot only when one is free
  import test_builders as tb
  from superegm import respec
  s, card, handoff, _ = tb.seed(world, units=("U07", "U08"), max_in_flight=1)  # U07 plays U1, U08 plays U2
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07" in world.run("launch", "--runcard", card)[1]
  state = tb.state_of(s)
  state["units"]["U08"]["launched"] = {"at": "2026-11-02T00:00:00Z", "runcard": card}
  tb.put(s.path("state"), json.dumps(state))
  # U2 built and reviewed clean, then R1 touched it: its mark stands, its head waits for a respec relaunch
  tb.launched(s, "U08", "exited 0")
  tb.foreman(s, "U08", [{"round": 1, "runcard": card, "launch": 1, "head": None, "phase": "posted", "dispatch_id": "d1",
                         "outcome": "clean", "posted_at": "2026-11-03T01:00:00Z"}])
  apply_r1(s, "U08")
  if u1_running:
    tb.launched(s, "U07", "running")  # another unit's builder holds the one slot
  else:
    world.gh.issues[7]["labels"].append("superegm:stopped")  # U1 stopped: the slot is free
  assert respec.marks(s, handoff).get("U08") == "respec: R1" and ("relaunch", "R1", "U08") in respec.actionable(s, handoff)
  launch_rc, launch_out = world.run("launch", "--runcard", card)
  journal = journal_of(s)
  assert launch_rc == 0 and marked.replace("U2", "U08") in launch_out and ("U08 marked for launch" in journal) is (not u1_running), launch_out


def test_held_unit_offers_no_merge(world, monkeypatch):
  # a standing mark holds a clean head everywhere; status names open respecs; tick_trigger follows respec.actionable
  import superegm
  import test_builders as tb
  from conftest import REPO, make_pr
  from superegm import inbox, respec, status
  from test_u85 import open_respec
  s, card, handoff, _ = tb.seed(world, units=("U07", "U08"))  # U08 plays U2
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07, U08" in world.run("launch", "--runcard", card)[1]
  head = "c" * 40
  make_pr(world.gh, 71, head, closes=[(REPO, 8)])
  world.gh.graphql[8] = [{**world.gh.prs[71], "repository": {"nameWithOwner": REPO}}]
  tb.launched(s, "U08", "exited 0")
  clean = {"round": 1, "runcard": card, "launch": 1, "head": head, "phase": "posted", "dispatch_id": "d1", "outcome": "clean",
           "posted_at": "2026-11-03T01:00:00Z"}
  tb.foreman(s, "U08", [clean])
  # R1 raised on U08's deviation and not yet approved: open
  open_respec(s, "R1", "U08")
  code, open_out = world.run("status", "--runcard", card)
  assert code == 0, open_out

  def merge_items():
    state, foreman = tb.state_of(s), superegm.load_foreman(s, "U08")
    return [i for i in inbox.unit_items(s, REPO, state, "U08", foreman) if i["kind"] == "merge"]
  assert merge_items()  # the clean head is offered for merge before R1 touches it
  apply_r1(s, "U08")  # approved: applied, touching U08
  code, held_out = world.run("status", "--runcard", card)
  assert code == 0, held_out
  status_out = open_out + held_out
  assert "open: respec R1" in open_out and "open: respec R1" not in held_out and "held: respec R1" not in open_out
  assert "held: respec R1" in status_out and "open: respec R1" in status_out and not merge_items()  # inbox's merge item (unit_items' clean-head branch); launch's merge round: test below
  # another command saves state.json (a stale copy, whole-file) during status's wait: the derived mark is not lost
  stale = json.dumps(tb.state_of(s))
  monkeypatch.setitem(world.ns, "SLEEP", lambda seconds: tb.put(s.path("state"), stale))
  assert world.run("status", "--wait", 1, "--runcard", card)[0] == 0
  mark_after_concurrent_state_save = respec.marks(s, handoff).get("U08")
  assert mark_after_concurrent_state_save == "respec: R1"

  def trigger():
    state = tb.state_of(s)
    return status.tick_trigger(superegm.Handoff(Path(state["plan"]), s, state))
  assert trigger() == "respec R1 U08"
  # a pending owner decision: held, nothing actionable, no session bought
  pending = {"dispatch_id": "d1", "rounds": [clean], "rulings": [],
             "decisions": [{"id": "U08-d1", "point": 2, "question": "cap", "options": ["one more round", "stop"]}]}
  tb.put(s.path("foreman", "U08"), json.dumps(pending))
  tick_trigger_with_pending_decision = trigger()
  assert tick_trigger_with_pending_decision is None and respec.marks(s, handoff).get("U08") == "respec: R1" and not merge_items()
  tb.foreman(s, "U08", [clean])
  # settled: the comment posted, and a respec launch naming R1 exited 0 on the saved head with `DONE`
  tb.put(respec.respec_path(s, "R1.U08.posted"), "1\n")
  relaunch = {**tb.launches_of(s, "U08")[0], "round": 2, "reason": "respec", "respecs": ["R1"], "started_at": "2026-11-15T00:00:00Z",
              "status": "exited 0", "head": head, "builder_status": "DONE"}
  tb.put(s.path("launches", "U08.json"), json.dumps({"launches": tb.launches_of(s, "U08") + [relaunch]}))
  assert world.run("status", "--wait", 1, "--runcard", card)[0] == 0
  tick_trigger_once_settled = trigger()
  assert respec.marks(s, handoff).get("U08") is None and tick_trigger_once_settled is None


# ---------------------------------------------------------------- round 2: the review of PR #244


def test_finish_journals_a_failed_state_read(world, tmp_path):
  # codebase-details-1-11: an unreadable state.json is a failed read of both fields, never "no PR"
  from superegm import record_launch
  from test_builders import put
  st = finish_world(world, tmp_path, 7, "DONE")
  put(st.path("state"), "{")
  launches = json.loads(st.path("launches", "U2").read_text(encoding="utf-8"))["launches"]
  record_launch.finish(st, "U2", launches, launches[-1], "exited 0", None, "U2 launch 1 exited 0")
  exit_record = json.loads(st.path("launches", "U2").read_text(encoding="utf-8"))["launches"][-1]
  journal = journal_of(st)
  assert exit_record["status"] == "exited 0" and "head" not in exit_record and exit_record["builder_status"] is None
  assert "U2 launch 1 exit read failed: head" in journal and "U2 launch 1 exit read failed: builder_status" in journal


def test_status_wait_prints_the_respec_lines(world, monkeypatch):
  # astra-1-4, astra-1-1: integrate's and the wave's `status --wait` print the open and held lines and step 5b's work
  import test_builders as tb
  from conftest import REPO, make_pr
  from test_u85 import open_respec
  s, card, handoff, _ = tb.seed(world, units=("U07", "U08"))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  world.run("launch", "--runcard", card)
  make_pr(world.gh, 71, "c" * 40, closes=[(REPO, 8)])
  world.gh.graphql[8] = [{**world.gh.prs[71], "repository": {"nameWithOwner": REPO}}]
  tb.launched(s, "U08", "exited 0")
  open_respec(s, "R1", "U08")
  code, out = world.run("status", "--wait", 1, "--runcard", card)
  assert code == 0 and "open: respec R1" in out.splitlines() and "held: respec" not in out, out
  apply_r1(s, "U08")
  code, out = world.run("status", "--wait", 1, "--runcard", card)
  lines = out.splitlines()
  comment = s.path("file", "respec_comment_U08_R1.md")
  assert code == 0 and "U08 held: respec R1" in lines and "open: respec R1" not in lines, out
  assert f"respec post R1 U08 #8 '{comment}'" in lines and "respec relaunch R1 U08" in lines, out
  tb.put(s.path("file", "respec", "R1.U08.posted"), "1\n")
  code, out = world.run("status", "--runcard", card)
  assert code == 0 and "respec relaunch R1 U08" in out and "respec post" not in out, out


@pytest.mark.parametrize("case, marked", [("idle", "marked: none"), ("unreviewed head", "marked: U08")])
def test_respec_relaunch_set_skips_idle_and_frees_its_own_slot(world, monkeypatch, case, marked):
  # astra-1-6: an idle unit is not re-marked; astra-1-2: a terminal unit awaiting its correction holds no slot of its own
  import test_builders as tb
  s, card, handoff, _ = tb.seed(world, units=("U07", "U08"), max_in_flight=1)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  world.run("launch", "--runcard", card)
  state = tb.state_of(s)
  state["units"]["U08"]["launched"] = {"at": "2026-11-02T00:00:00Z", "runcard": card}
  tb.put(s.path("state"), json.dumps(state))
  tb.launched(s, "U08", "exited 0")  # no round posted on its head: neither clean nor ready again
  apply_r1(s, "U08")
  world.gh.issues[7]["labels"].append("superegm:stopped")  # U07 out of the way: one slot, U08's to take
  args = ("--idle", "U08") if case == "idle" else ()
  code, out = world.run("launch", *args, "--runcard", card)
  assert code == 0 and marked in out and ("U08 marked for launch" in journal_of(s)) is (case != "idle"), out


@pytest.mark.parametrize("held", [False, True])
def test_held_unit_gets_no_merge_round(held):
  # astra-1-5, codebase-details-1-3, codebase-details-1-10: launch's merge offer reads the mark too
  from superegm import launch
  head = "a" * 40
  foreman = {"rounds": [{"round": 1, "launch": 1, "head": head, "phase": "posted", "outcome": "clean"}]}
  view = {"conflict": True, "head": head, "held": held}
  assert launch.conflict_again(view, foreman, [{"round": 1, "status": "exited 0"}], True) is (not held)


@pytest.mark.parametrize("via_launch", [True, False])
def test_held_conflicting_unit_relaunches_with_its_fix_not_merge_alone(world, monkeypatch, spawn_fake, via_launch):
  # astra-1-5: a respec relaunch of a clean CONFLICTING head carries the merge with the fix, never merge-only orders;
  # astra-2-4: it starts only from `launch`'s fresh mark (its slot), never straight from a word's `launch-builder`
  import test_u62 as u62
  s, card, hid, _ = u62.seed(world)
  u62.with_rounds(s, world, 3)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  head = u62.first_round(world, s, card)
  u62.write_foreman(s, "U07", [{**u62.CLEAN, "head": head, "posted_at": "2099-01-01T00:00:00Z"}])
  u62.save_pr(s, "U07", 71, head, "CONFLICTING")
  apply_r1(s, "U07")
  if via_launch:
    code, out = world.run("launch", "--runcard", card)
    assert code == 0 and "marked: U07" in out, out
    u62.save_pr(s, "U07", 71, head, "CONFLICTING")  # the pass that marked it read the head still conflicting
  else:  # the mark round 1 started from, older than that launch (stamps are to the second)
    state = json.loads(s.path("state").read_text(encoding="utf-8"))
    state["units"]["U07"]["launched"]["at"] = "2000-01-01T00:00:00Z"
    u62.put(s.path("state"), json.dumps(state))
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  if not via_launch:
    assert code == 1 and "launch-builder: U07 holds respec R1: its relaunch waits for `launch`'s slot" in out, out
    assert len(u62.launches_of(s, "U07")) == 1
    return
  assert code == 0, out
  entry = u62.launches_of(s, "U07")[-1]
  assert (entry.get("merge"), entry["reason"], entry["respecs"]) == ("with-fix", "respec", ["R1"])


@pytest.mark.parametrize("error", ["ValueError", "HandoffError"])
def test_a_mark_read_failure_starts_no_builder(world, monkeypatch, spawn_fake, which, no_graphify, error):
  # change-review-1-6: the mark is read before the builder starts, so a failed read never leaves one unrecorded;
  # codebase-details-2-2: any failed read refuses the launch (fail closed), with a named refusal line
  import test_builders as tb
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  world.run("launch", "--runcard", card)
  apply_r1(s, tb.UNIT)
  import superegm
  from superegm import respec
  exc = ValueError("R1.json: bad JSON") if error == "ValueError" else superegm.HandoffError("approval names no spec")
  monkeypatch.setattr(respec, "marks", lambda store, handoff: (_ for _ in ()).throw(exc))
  code, out = world.run("launch-builder", "--unit", tb.UNIT, "--round", 1, "--runcard", card)
  assert code == 1 and f"launch-builder: respec marks unreadable: {exc}" in out, out
  assert not spawn_fake and not s.path("launches", f"{tb.UNIT}.json").exists()


@pytest.mark.parametrize("word, kept", [("DONE", True), ("BLOCKED", False)])
def test_a_no_push_relaunch_keeps_its_corrections(tmp_path, capsys, monkeypatch, word, kept):
  # astra-1-3, codebase-details-1-6: a respec launch that exited 0 on the reviewed head with DONE pushed nothing, so the
  # head's own launch is older; the round still reviews against the corrections that launch named
  import test_foreman as tf
  from conftest import make_world
  w = make_world(tmp_path / "foreman", capsys, monkeypatch)
  from superegm import foreman
  monkeypatch.setattr(foreman, "runner_path", lambda: "/x/runner.py")
  _, _, head, _ = tf.pr_repo(w, tmp_path / "foreman", monkeypatch)
  relaunch = {"round": 2, "status": "exited 0", "started_at": "2099-01-01T00:00:00Z", "reason": "respec", "respecs": ["R1"],
              "head": head, "builder_status": word}
  st, _, child, did, _ = tf.dispatched(w, head=head, rounds=[tf.POSTED_R1], launches=[tf.TWO_LAUNCHES[0], relaunch],
                                       astra={"enabled": True})
  core = __import__("superegm")
  core.atomic_write(st.path("file", "respec", "R1.json"), {"touched": [tf.UNIT], "untouched": [], "follow_ups": [], "line_map": []})
  core.atomic_write(st.path("file", f"respec_comment_{tf.UNIT}_R1.md"), CORRECTION.format(unit=tf.UNIT))
  code, out = w.run("prepare", "--unit", tf.UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  r = st.path("review", tf.UNIT, f"pr{tf.PR}") / "r2"
  amendments_md = (r / "amendments.md").read_text(encoding="utf-8")
  assert ("+Max retries: 4" in amendments_md) is kept and amendments_md in (r / "astra_brief.md").read_text(encoding="utf-8")


def text(path):
  from conftest import ROOT
  return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("path, phrases", [
  ("skills/wave/SKILL.md", ("the raising unit waits", "respec.actionable", "superegm respec posted", "reason `respec`")),
  ("skills/integrate/SKILL.md", ("integrate: respec R<n> is open", "integrate: <U> holds respec R<n>"))])
def test_wave_and_integrate_skill_text(path, phrases):
  # the wave posts and relaunches idempotently; integrate refuses on an open respec or a standing mark
  assert all(p in text(path) for p in phrases)


@pytest.mark.parametrize("close", [False, True])
def test_integrate_refuses_on_its_wait_output_close_included(close):
  # astra-1-4, change-review-1-2, change-review-1-3; change-review-2-2: the refusal reads Step 1's `status --wait` and
  # comes before the unlanded list ends a plain run, so it fires with and without `--close`; the inbox line stays with
  # the unlanded list; codebase-details-2-3: a failed respec read refuses too
  step1 = text("skills/integrate/SKILL.md").split("## Step 1", 1)[1].split("## Step 2", 1)[0]
  item3, item4 = step1.split("\n3. ", 1)[1].split("\n4. ", 1)
  assert "item 2's `status --wait` output" in item3 and "with or without `--close`" in item3 and "go to item 4" in item3
  assert "integrate: respec R<n> is open" in item3 and "integrate: <U> holds respec R<n>" in item3
  assert "`respec: read failed: <error>`" in item3 and "inbox" not in item3
  ending = "Without `--close`, one listed unit ends the" if not close else "With `--close` (`--patch` or not), go to Step 3"
  assert ending in " ".join(item4.split()) and "merges in the inbox" in item4


def test_wave_reaches_step_5b():
  # astra-1-1, codebase-details-1-2, codebase-details-1-12: the loop does not end on a respec line, and step 5b names
  # the lines it reads, the post command and where the comment id comes from; change-review-2-1, codebase-details-2-1:
  # the post is scanned and pinned to the host and repo, as plan Step 4 posts `decision_comment`
  wave = text("skills/wave/SKILL.md")
  assert "no 5b line in step 2 → The end" in wave and "no 5b line of a non-idle unit → The end" in wave
  assert ("`respec post R<n> <U> #<i> '<f>'` → `superegm scan --comment '<f>'` (a finding: say so, post nothing), then "
          "`GH_HOST=github.com gh issue comment <i> -R OWNER/NAME --body-file '<f>'`") in wave and "--comment <the URL's id>" in wave


def test_wave_names_the_respec_lines_of_its_wait():
  # change-review-2-3, codebase-details-2-4: the batch's `status --wait` line list names the respec lines, and which
  # need no action; astra-2-4: a held unit's `revise` waits for step 6's `launch`
  wave = " ".join(text("skills/wave/SKILL.md").split())
  assert ("then respec lines (`open: respec`, `held: respec`, `respec: read failed`: none to do; `respec post`, "
          "`respec relaunch`: 5b)") in wave
  assert "A `held: respec` unit never gets a direct `launch-builder`: step 6's `launch` marks it." in wave
  from superegm import status
  doc = status.wait_events.__doc__
  assert all(k in " ".join(doc.split()) for k in ("open: respec R<n>", "<U> held: respec R<n>", "respec post", "respec relaunch"))


# ---------------------------------------------------------------- round 3: the review of head 86f0f15


def test_corrections_and_mark_come_from_one_read(world, monkeypatch, spawn_fake, which, no_graphify):
  # astra-2-1, codebase-details-2-5: a respec applied between the corrections read and the mark read never splits the
  # launch (a standing mark whose correction the prompt lacks): the launch refuses and starts nothing
  import test_builders as tb
  from superegm import launch_builder
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  read = launch_builder.corrections_for
  monkeypatch.setattr(launch_builder, "corrections_for", lambda st, unit: (read(st, unit), apply_r1(s, unit))[0])
  code, out = world.run("launch-builder", "--unit", tb.UNIT, "--round", 1, "--runcard", card)
  assert code == 1 and f"launch-builder: {tb.UNIT}: respec R1 was applied while the launch was prepared" in out, out
  assert not spawn_fake and not s.path("launches", f"{tb.UNIT}.json").exists()


@pytest.mark.parametrize("decision, marked", [(True, "marked: none"), (False, "marked: U08")])
def test_ready_again_waits_for_a_pending_decision(world, monkeypatch, decision, marked):
  # astra-2-2: a clean round an ingest rewrote `revise` is ready again only with no owner decision pending
  import test_builders as tb
  s, card, handoff, _ = tb.seed(world, units=("U07", "U08"))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07, U08" in world.run("launch", "--runcard", card)[1]
  tb.launched(s, "U07", "running")
  tb.launched(s, "U08", "exited 0")
  rewritten = {"round": 1, "runcard": card, "launch": 1, "head": None, "phase": "posted", "dispatch_id": "d1",
               "outcome": "revise", "rewritten_from": "clean", "posted_at": "2026-11-03T01:00:00Z"}
  decisions = [{"id": "U08-d1", "point": 2, "question": "cap", "options": ["one more round", "stop"]}] if decision else []
  tb.put(s.path("foreman", "U08"), json.dumps({"dispatch_id": "d1", "rounds": [rewritten], "rulings": [], "decisions": decisions}))
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and marked in out, out


@pytest.mark.parametrize("respec_open, marked", [(True, "marked: U08"), (False, "marked: none")])
def test_a_unit_waiting_on_a_respec_holds_no_slot(world, monkeypatch, respec_open, marked):
  # astra-2-3: the raising unit of an open respec, no launch of it running, holds no slot while the owner corrects
  import test_builders as tb
  from test_u85 import open_respec
  s, card, handoff, _ = tb.seed(world, units=("U07", "U08"), max_in_flight=1)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07" in world.run("launch", "--runcard", card)[1]
  tb.launched(s, "U07", "exited 0")  # BLOCKED on a spec deviation, the owner ruled `respec`: no decision pending
  if respec_open:
    open_respec(s, "R1", "U07")
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and marked in out, out
  assert ("in flight: none" in out) is respec_open, out


def test_a_failed_respec_read_holds_and_is_reported(world, monkeypatch):
  # codebase-details-2-3: status prints a failed read (integrate refuses on it); inbox treats the unit as held
  import superegm
  import test_builders as tb
  from superegm import inbox, respec
  s, card, handoff, _ = tb.seed(world, units=("U07", "U08"))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  world.run("launch", "--runcard", card)
  monkeypatch.setattr(respec, "marks", lambda store, handoff: (_ for _ in ()).throw(superegm.HandoffError("approval names no spec")))
  for args in (("--wait", 1), ()):
    code, out = world.run("status", *args, "--runcard", card)
    assert code == 0 and "respec: read failed: approval names no spec" in out.splitlines(), out
  assert inbox.respec_held(s, "U08") is True


# ---------------------------------------------------------------- round 4: the review of head 04158c6


def u62_relaunched(world, monkeypatch):
  """test_u62's world: U07's clean CONFLICTING head, R1 applied touching it, and its respec relaunch (round 2) marked by
  `launch` and started by `launch-builder`; the store and card returned."""
  import test_u62 as u62
  s, card, hid, _ = u62.seed(world)
  u62.with_rounds(s, world, 3)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  head = u62.first_round(world, s, card)
  u62.write_foreman(s, "U07", [{**u62.CLEAN, "head": head, "posted_at": "2099-01-01T00:00:00Z"}])
  u62.save_pr(s, "U07", 71, head, "CONFLICTING")
  apply_r1(s, "U07")
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and "marked: U07" in out, out
  u62.save_pr(s, "U07", 71, head, "CONFLICTING")
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 0, out
  from superegm.launch import load_launches
  launches = load_launches(s, "U07")  # the head (the base's commit, made now) predates round 2: the mark stands
  launches[-1]["started_at"] = "2099-01-01T00:00:00Z"
  s.path("launches", "U07.json").write_text(json.dumps({"launches": launches}), encoding="utf-8")
  return s, card


def end_launch(s, uid, code, **fields):
  """The unit's latest launch exited `code` (its exit file written), with `fields` recorded on it."""
  from superegm.launch import load_launches
  launches = load_launches(s, uid)
  launches[-1].update({"status": f"exited {code}", **fields})
  s.path("launches", f"{uid}.json").write_text(json.dumps({"launches": launches}), encoding="utf-8")
  Path(launches[-1]["result_file"] + ".exit").write_text(f"{code}\n", encoding="utf-8")
  return launches[-1]


def test_a_failed_resume_of_a_respec_relaunch_reaches_a_fresh_launch(world, monkeypatch, spawn_fake):
  # codebase-details-3-1, astra-3-3: the respec relaunch fails to resume (no result, no commit), so the mark stands; a
  # direct `launch-builder` is refused, `launch` marks it again in its slot, and that fresh mark is accepted; the wave
  # and its references route a held unit to step 6's `launch`, never to a direct `launch-builder`
  s, card = u62_relaunched(world, monkeypatch)
  end_launch(s, "U07", 1, failed_resume=True)
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 3, "--runcard", card)
  assert code == 1 and "launch-builder: U07 holds respec R1: its relaunch waits for `launch`'s slot" in out, out
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and "marked: U07" in out, out
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 3, "--runcard", card)
  assert code == 0, out
  wave = " ".join(text("skills/wave/SKILL.md").split())
  assert "A `held: respec` unit never gets a direct `launch-builder`" in wave and "step 6's `launch` marks it" in wave
  for path in ("skills/wave/references/decision_points.md", "skills/wave/references/rulings.md"):
    assert "a `held: respec` unit: step 6's `launch`" in " ".join(text(path).split()), path


def test_a_mark_in_the_same_second_as_the_last_launch_is_not_fresh(world, monkeypatch, spawn_fake):
  # astra-3-2: the mark round 2 started from, stamped in the same second as round 2's `started_at`, is spent: a direct
  # `launch-builder` for round 3 is refused while another `launch` has not marked it
  s, card = u62_relaunched(world, monkeypatch)
  started = end_launch(s, "U07", 0, builder_status="BLOCKED")["started_at"]
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["units"]["U07"]["launched"]["at"] = started
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 3, "--runcard", card)
  assert code == 1 and "launch-builder: U07 holds respec R1: its relaunch waits for `launch`'s slot" in out, out


def test_an_open_respec_holds_its_raising_unit(world, monkeypatch, spawn_fake, which, no_graphify):
  # astra-3-1: the owner ruled `respec` on a BLOCKED unit, so R1 is open, not applied: the unit is not launched against
  # the uncorrected spec, `launch` marks it for nothing, and the ruling's route waits for the correction
  import test_builders as tb
  from test_u85 import open_respec
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  tb.launched(s, tb.UNIT, "exited 0")
  open_respec(s, "R1", tb.UNIT)
  code, out = world.run("launch-builder", "--unit", tb.UNIT, "--round", 2, "--runcard", card)
  assert code == 1 and f"launch-builder: {tb.UNIT} waits for respec R1: its correction is not applied yet" in out, out
  assert not spawn_fake and len(tb.launches_of(s)) == 1
  rulings = " ".join(text("skills/wave/references/rulings.md").split())
  assert "`respec` → nothing until `approve-spec --respec R<n>` applies it" in rulings


def test_an_open_respec_gets_no_merge_round(world, monkeypatch):
  # astra-3-1: `launch` marks no merge round (conflict_again) for an open respec's raising unit
  import test_u62 as u62
  from test_u85 import open_respec
  s, card, hid, _ = u62.seed(world)
  u62.with_rounds(s, world, 3)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  head = u62.first_round(world, s, card)
  u62.write_foreman(s, "U07", [{**u62.CLEAN, "head": head, "posted_at": "2099-01-01T00:00:00Z"}])
  u62.save_pr(s, "U07", 71, head, "CONFLICTING")
  open_respec(s, "R1", "U07")
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and "marked: none" in out, out


@pytest.mark.parametrize("respec_open", [True, False])
def test_report_ends_on_a_unit_waiting_on_a_respec(world, monkeypatch, respec_open):
  # astra-3-4: a terminal unit with no PR, waiting on an open respec, is not active: the loop ends and names it
  import test_builders as tb
  from test_u85 import open_respec
  from superegm import report
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  tb.launched(s, tb.UNIT, "exited 0")
  if respec_open:
    open_respec(s, "R1", tb.UNIT)
  code, out = world.run("report", "--runcard", card)
  assert code == 0, out
  loop = next(line for line in out.splitlines() if line.startswith("loop: "))
  assert loop.startswith("loop: ended") is respec_open and (f"waiting respec: {tb.UNIT}" in loop) is respec_open, loop
  assert report.loop_ended({"U1": "waiting respec"}, [], 1) == (
      True, "every launched unit is clean, landed, stopped, pending, idle or waiting respec (waiting respec: U1)")


def test_a_missing_correction_file_refuses_the_review(tmp_path, capsys, monkeypatch):
  # astra-3-5: a launch naming R1 whose comment file is gone: prepare refuses, never an empty correction
  import test_foreman as tf
  from conftest import make_world
  w = make_world(tmp_path / "foreman", capsys, monkeypatch)
  from superegm import foreman
  monkeypatch.setattr(foreman, "runner_path", lambda: "/x/runner.py")
  _, _, head, _ = tf.pr_repo(w, tmp_path / "foreman", monkeypatch)
  relaunch = {"round": 2, "status": "exited 0", "started_at": "2099-01-01T00:00:00Z", "reason": "respec", "respecs": ["R1"],
              "head": head, "builder_status": "DONE"}
  st, _, child, did, _ = tf.dispatched(w, head=head, rounds=[tf.POSTED_R1], launches=[tf.TWO_LAUNCHES[0], relaunch],
                                       astra={"enabled": True})
  core = __import__("superegm")
  core.atomic_write(st.path("file", "respec", "R1.json"), {"touched": [tf.UNIT], "untouched": [], "follow_ups": [], "line_map": []})
  code, out = w.run("prepare", "--unit", tf.UNIT, "--dispatch", did, "--runcard", child)
  assert code == 1 and f"respec R1: respec_comment_{tf.UNIT}_R1.md is missing" in out, out
  assert not (st.path("review", tf.UNIT, f"pr{tf.PR}") / "r2" / "amendments.md").exists()


@pytest.mark.parametrize("error", ["ValueError", "OSError", "HandoffError"])
def test_tick_trigger_reports_a_failed_respec_read(world, monkeypatch, error):
  # codebase-details-3-2: a bad R<n>.json never escapes to the driver: tick_trigger journals a named line, documented
  import superegm
  import test_builders as tb
  from superegm import respec, status
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  world.run("launch", "--runcard", card)
  world.run("status", "--runcard", card)
  exc = {"ValueError": ValueError("R1.json: bad JSON"), "OSError": OSError("R1.json: unreadable"),
         "HandoffError": superegm.HandoffError("approval names no spec")}[error]
  monkeypatch.setattr(respec, "actionable", lambda store, handoff: (_ for _ in ()).throw(exc))
  state = tb.state_of(s)
  status.tick_trigger(superegm.Handoff(Path(state["plan"]), s, state))
  assert f"respec: read failed: {exc}" in journal_of(s)
  doc = " ".join(status.tick_trigger.__doc__.split())
  assert "`respec R<n> <unit>`" in doc and "`respec: read failed: <error>`" in doc


def test_inbox_names_a_failed_respec_read(world, monkeypatch):
  # codebase-details-3-3: on a failed read the unit is held and the inbox says why
  import superegm
  import test_builders as tb
  from superegm import inbox, respec
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  world.run("launch", "--runcard", card)
  monkeypatch.setattr(respec, "marks", lambda store, handoff: (_ for _ in ()).throw(superegm.HandoffError("approval names no spec")))
  items = [i for i in inbox.inbox_items(s, [s.handoff_id]) if i["kind"] == "respec"]
  assert [i["action"] for i in items] == ["read failed: approval names no spec: no merge is offered on a held head until it reads"], items
  assert "the inbox's `respec` item" in " ".join(inbox.respec_held.__doc__.split())


def test_launch_header_names_the_u86_changes():
  # codebase-details-3-4
  from superegm import launch
  header = Path(launch.__file__).read_text(encoding="utf-8").splitlines()[2]
  assert all(p in header for p in ("a held view gets no merge round", "holds no slot while no launch of it runs",
                                   "`ready_again` waits for a pending owner decision"))


# ---------------------------------------------------------------- round 5: the review of head 12c1df4


def test_a_missing_comment_file_still_holds_the_head(world, monkeypatch):
  # astra-4-1: a filed unit whose respec comment file is gone reads `replan: R1`: still waiting, never corrected; the inbox
  # offers no merge and status prints it held (integrate's refusal)
  import superegm
  import test_builders as tb
  from conftest import REPO, make_pr
  from superegm import inbox, respec
  s, card, handoff, _ = tb.seed(world, units=("U07", "U08"))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  world.run("launch", "--runcard", card)
  head = "c" * 40
  make_pr(world.gh, 71, head, closes=[(REPO, 8)])
  world.gh.graphql[8] = [{**world.gh.prs[71], "repository": {"nameWithOwner": REPO}}]
  tb.launched(s, "U08", "exited 0")
  tb.foreman(s, "U08", [{"round": 1, "runcard": card, "launch": 1, "head": head, "phase": "posted", "dispatch_id": "d1",
                         "outcome": "clean", "posted_at": "2026-11-03T01:00:00Z"}])
  apply_r1(s, "U08")
  s.path("file", "respec_comment_U08_R1.md").unlink()
  code, out = world.run("status", "--runcard", card)
  assert code == 0 and respec.marks(s, handoff).get("U08") == "replan: R1", out
  assert "U08 held: respec R1" in out.splitlines(), out
  state, foreman = tb.state_of(s), superegm.load_foreman(s, "U08")
  assert not [i for i in inbox.unit_items(s, REPO, state, "U08", foreman) if i["kind"] == "merge"]
  assert inbox.respec_held(s, "U08") is True


def test_a_missing_comment_file_gets_no_merge_round(world, monkeypatch):
  # astra-4-1: `launch`'s merge offer reads the same hold
  import test_u62 as u62
  s, card, hid, _ = u62.seed(world)
  u62.with_rounds(s, world, 3)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  head = u62.first_round(world, s, card)
  u62.write_foreman(s, "U07", [{**u62.CLEAN, "head": head, "posted_at": "2099-01-01T00:00:00Z"}])
  u62.save_pr(s, "U07", 71, head, "CONFLICTING")
  apply_r1(s, "U07")
  s.path("file", "respec_comment_U07_R1.md").unlink()
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and "marked: none" in out, out


def board_row(out, uid):
  row = next(line for line in out.splitlines() if line.startswith(f"| {uid} #"))
  return [c.strip() for c in row.strip().strip("|").split("|")]


def test_report_waits_on_an_open_respec_of_a_clean_conflicting_unit(world, monkeypatch):
  # astra-4-2: a clean CONFLICTING unit that raised an open R1 is no merge round in report: it waits for the respec;
  # codebase-details-4-1: the board shows it `waiting respec`, next action none
  import test_u62 as u62
  from test_u85 import open_respec
  s, card, hid, _ = u62.seed(world)
  u62.with_rounds(s, world, 3)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  head = u62.first_round(world, s, card)
  u62.write_foreman(s, "U07", [{**u62.CLEAN, "head": head, "posted_at": "2099-01-01T00:00:00Z"}])
  u62.save_pr(s, "U07", 71, head, "CONFLICTING")
  open_respec(s, "R1", "U07")
  code, out = world.run("report", "--runcard", card)
  assert code == 0, out
  loop = next(line for line in out.splitlines() if line.startswith("loop: "))
  assert "merge round" not in loop and "waiting respec: U07" in loop, loop
  cells = board_row(out, "U07")
  assert cells[1] == "waiting respec" and cells[7] == "none", cells  # no merge round offered


def test_board_shows_a_respec_waiting_unit_as_waiting(world, monkeypatch):
  # codebase-details-4-1: the unit with no PR the loop line already ends on: its board row says the same, and the wave
  # skill names the state
  import test_builders as tb
  from test_u85 import open_respec
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  tb.launched(s, tb.UNIT, "exited 0")
  open_respec(s, "R1", tb.UNIT)
  code, out = world.run("report", "--runcard", card)
  assert code == 0, out
  cells = board_row(out, tb.UNIT)
  assert cells[1] == "waiting respec" and cells[7] == "none", cells
  assert "`waiting respec`" in text("skills/wave/SKILL.md")


@pytest.mark.parametrize("reader, error", [("marks", "ValueError"), ("actionable", "OSError"), ("open", "ValueError")])
def test_launch_refuses_on_a_malformed_respec_file(world, monkeypatch, reader, error):
  # change-review-4-1: `launch` refuses in one line naming the read failure, never a traceback; nothing is marked
  import test_builders as tb
  from superegm import respec
  s, card, handoff, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  exc = ValueError("respec/R1.json: bad JSON") if error == "ValueError" else OSError("respec/R1.json: unreadable")
  monkeypatch.setattr(respec, reader, lambda store, handoff: (_ for _ in ()).throw(exc))
  code, out = world.run("launch", "--runcard", card)
  assert code == 1 and f"launch: respec marks unreadable: {exc}" in out and "Traceback" not in out, out
  assert f"{tb.UNIT} marked for launch" not in journal_of(s)


def test_decision_points_header_names_u86():
  # codebase-details-4-2
  header = text("skills/wave/references/decision_points.md").splitlines()[1]
  assert "(U86)" in header
