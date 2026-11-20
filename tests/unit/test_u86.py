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


@pytest.mark.parametrize("approved, in_prompt", [("before the prompt", True), ("after the prompt", False)])
def test_prompt_record_and_amendments_agree(world, tmp_path, capsys, monkeypatch, spawn_fake, which, no_graphify, approved, in_prompt):
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
  # the builder pushes after its start: the saved PR head is a commit made after the launch's started_at
  pushed_after_start = True
  head = commit_at(world, monkeypatch, "pushed.txt", "2099-01-01T00:00:00Z")
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
  assert ("# Spec corrections" in prompt and "+Max retries: 4" in prompt) is in_prompt and record["reason"] == "respec"
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
  assert "held: respec R1" in status_out and "open: respec R1" in status_out and not merge_items()  # the one merge offer today: inbox.py:138-141
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


def text(path):
  from conftest import ROOT
  return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("path, phrases", [
  ("skills/wave/SKILL.md", ("the raising unit waits", "respec.actionable", "superegm respec posted", "reason `respec`")),
  ("skills/integrate/SKILL.md", ("integrate: respec R<n> is open", "integrate: <U> holds respec R<n>"))])
def test_wave_and_integrate_skill_text(path, phrases):
  # the wave posts and relaunches idempotently; integrate refuses on an open respec or a standing mark
  assert all(p in text(path) for p in phrases)
