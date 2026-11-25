# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U92
# Modified by SuperEGM (gsVAM), 2026: a head proceed names its head, `--head <sha7>` or `proceed <sha7> — <reason>` (U107, 1.3 design section 3.9).

"""U92: proceed's readers (spec section 4.2): `launch`, `report`, `inbox` and `review` read a proceeded head through
its authorizing outcome, the newer by launch of the latest round posted clean and the newest `proceeds[]` entry."""

import json
import time
import traceback
from pathlib import Path

import pytest

from conftest import make_pr, set_config  # noqa: F401
from superegm import atomic_write, launch, report
from superegm.inbox import inbox_items, line_of
from test_wave import foreman_of
from test_u57 import head_world, proceed, launches, REPO
from test_u43 import registry  # noqa: F401 -- autouse: HOME under tmp_path
from test_builders import spawn_fake, which, no_graphify  # noqa: F401 -- launch-builder starts no builder, finds `gh`

NOW = time.time()
H7 = "a" * 7  # U107: a head proceed names the head the owner was shown, `head_world`'s


def set_head(s, uid, head):
  """The pull request's head as `status --wait` saves it."""
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"][uid]["head"] = head
  atomic_write(s.path("state"), state)


def write_launches(s, uid, *entries):
  atomic_write(s.path("launches", uid), {"launches": [{"round": n, "status": status} for n, status in entries]})


def reading(s, card, uid="U01"):
  """What the readers see of `uid`: its view, foreman, launches and the wave card."""
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  view = report.unit_view(state, uid)
  card_json = json.loads(s.path("runcards", card).read_text(encoding="utf-8"))
  return view, foreman_of(s, uid), launch.load_launches(s, uid), card_json


def inbox_text(s):
  return "\n".join(line_of(i) for i in inbox_items(s, [s.handoff_id]))


# ---------------------------------------------------------------- S1: waiting proceed


@pytest.mark.parametrize("case, merge_offered", [
  ("merge launch on the proceeded head finished", False),
  ("proceed on H1 while a launch pushed H2", False),
  ("second proceed naming the later launch", True),
])
def test_waiting_proceed_after_a_later_launch(world, case, merge_offered):
  s, card, rid = head_world(world)
  if case == "proceed on H1 while a launch pushed H2":
    write_launches(s, "U01", (1, "exited 0"), (2, "running"))
    code, out = proceed(world, rid, card, "--owner", "--head", H7, "--reason", "accepted risk")
    assert code == 0, out
    set_head(s, "U01", "c" * 40)
  else:
    code, out = proceed(world, rid, card, "--owner", "--head", H7, "--reason", "accepted risk")
    assert code == 0, out
    launches(s, "U01", 1, 2)  # the merge launch after the proceed, terminal
    if case == "second proceed naming the later launch":
      set_head(s, "U01", "c" * 40)
      code, out = proceed(world, rid, card, "--owner", "--head", "c" * 7, "--reason", "the merge round is fine")
      assert code == 0, out
      assert foreman_of(s, "U01")["proceeds"][-1]["launch"] == 2
  view, foreman, entries, card_json = reading(s, card)
  # `report` holds no slot for U01 while waiting; `inbox` keys the item on that launch and head
  assert report.unit_state("U01", view, foreman, entries, card_json, {}, NOW) == ("clean" if merge_offered else "waiting proceed")
  assert launch.in_flight(s, "U01", view, set()) is False
  text = inbox_text(s)
  proceeds = [i for i in inbox_items(s, [s.handoff_id]) if i["subject"] == "U01" and i["kind"] == "proceed"]
  assert bool(proceeds) is not merge_offered, text
  assert any(i["subject"] == "U01" and i["kind"] == "merge" for i in inbox_items(s, [s.handoff_id])) is merge_offered, text
  if not merge_offered:
    head = view["head"]
    assert [(i["action"], i["fingerprint"].rsplit("/", 1)[1]) for i in proceeds] == [("answer in the inbox", head)], text
    word = report.unit_state("U01", view, foreman, entries, card_json, {}, NOW)
    assert report.next_action(word, None, entries[-1], [], None) == "proceed again"


# ---------------------------------------------------------------- S2: the merge on the authorizing head


def unposted_world(world, case):
  """U01 on head `abc123` with its head review open and no round posted on that head: its attempts collected and
  never posted, a posted round on an older head before a launch that pushed `abc123`, or no foreman round at all."""
  from test_wave import open_wave_card, wave_store
  card = open_wave_card(world)
  rounds = {"attempts never posted": [{"round": 1, "phase": "collected", "launch": 1, "head": "abc123", "outcome": None}],
            "typed proceed on a never-posted head": [{"round": 1, "phase": "posted", "launch": 1, "head": "a" * 40,
                                                     "outcome": "revise"}],
            "head cycle with no foreman round": []}[case]
  runs = [{"round": 1, "status": "exited 0"}] + ([{"round": 2, "status": "exited 0"}]
                                                if case == "typed proceed on a never-posted head" else [])
  s = wave_store(world, U01={"pr": 70, "head": "abc123", "ci": "green", "launches": runs, "rounds": rounds})
  code, out = world.run("review", "open", "--kind", "head", "--artifact", "U01", "--reviewers", "change-review",
                        "--runcard", card)
  assert code == 0, out
  make_pr(world.gh, 70, "abc123")  # U107: a head proceed reads the pull request's head afresh
  set_config(world, repo=REPO, owners=["owner"])
  return s, card, out.strip()


@pytest.mark.parametrize("case", ["attempts never posted", "typed proceed on a never-posted head",
                                  "head cycle with no foreman round"])
def test_inbox_offers_merge_on_the_authorizing_head(world, case):
  s, card, rid = unposted_world(world, case)
  code, out = proceed(world, rid, card, "--owner", "--head", "abc123", "--reason", "ship it")
  assert code == 0, out
  assert foreman_of(s, "U01")["proceeds"][-1]["head"] == "abc123"
  # proceeded on head "abc123"; inbox stays read-only and names the owner's merge command
  world.gh.calls.clear()
  item = next(i for i in inbox_items(s, [s.handoff_id]) if i["subject"].startswith("U01") and i["kind"] == "merge")
  assert "--match-head-commit abc123" in item["action"]
  assert f"gh pr merge 70 --match-head-commit abc123" in item["action"]
  assert item["fingerprint"] == f"U01/merge/{rid}/abc123"
  assert world.gh.calls == []
  # offered only while the pull request's head is the authorizing outcome's
  set_head(s, "U01", "d" * 40)
  assert not any(i["subject"] == "U01" and i["kind"] == "merge" for i in inbox_items(s, [s.handoff_id]))


# ---------------------------------------------------------------- S3: a proceed closes the point-1 decisions


@pytest.mark.parametrize("decision", ["owner-only point-1 allowance", "builder-contest point-1",
                                      "cap question naming the review"])
def test_proceed_closes_point_one_decisions(world, decision):
  s, card, rid = head_world(world)
  opened = {"owner-only point-1 allowance": {"id": "q1", "point": 1, "source": f"review {rid} round 1", "question": "owner: f1",
                                             "options": ["change-review-1-1 allowed"]},
            "builder-contest point-1": {"id": "q1", "point": 1, "source": f"review {rid} round 1",
                                        "question": "change-review-1-1 | medium | a.py | regression: no | x\n"},
            "cap question naming the review": {"id": "q1", "point": 2, "source": f"review {rid} cap", "question": "the cap",
                                               "options": ["one more round", "stop", "redesign"]}}[decision]
  f = foreman_of(s, "U01")
  f["decisions"].append(opened)
  atomic_write(s.path("foreman", "U01"), f)
  # a proceed ruling on the review the decision names
  code, out = proceed(world, rid, card, "--owner", "--head", H7, "--reason", "accepted risk")
  assert code == 0, out
  view, foreman, entries, card_json = reading(s, card)
  assert [r["ruling"] for r in foreman["rulings"] if r.get("decision") == "q1"] == ["proceed"]
  assert report.pending_decisions(foreman) == []
  assert report.unit_state("U01", view, foreman, entries, card_json, {}, NOW) != "pending"
  assert not foreman.get("stopped")
  code, out = world.run("report", "--runcard", card)
  assert code == 0 and "pending: U01" not in out, out


# ---------------------------------------------------------------- S4: the readers after a posted proceed


class Result:
  """A subcommand's run as the test reads it: its exit code, and its output with any uncaught exception's name."""

  def __init__(self, run):
    try:
      self.returncode, self.stderr = run()
    except Exception:  # an uncaught reader error is the failure this Step pins
      self.returncode, self.stderr = 1, traceback.format_exc()


def posted_proceed(foreman, rid):
  """`foreman.rulings[]` holding a proceed entry without `decision` beside the posted `proceeds[]` entry."""
  entry = {"ruling": "proceed", "by": "owner", "posted": "comment 901", "posted_at": "2026-11-10T09:00:00Z",
           "reason": "the medium is accepted risk", "review": "R1"}
  foreman["rulings"] = (foreman.get("rulings") or []) + [entry]
  foreman.setdefault("proceeds", [])
  if not foreman["proceeds"]:
    foreman["proceeds"].append({"ruling": "R1", "review": rid, "posted": "comment 901", "posted_at": entry["posted_at"],
                                "issue": 2, "head": "a" * 40, "launch": 1, "by": "owner", "reason": entry["reason"]})
  return foreman


def run_after_a_posted_proceed(world, monkeypatch, command):
  if command == "launch-builder":
    from test_builders import seed, UNIT
    s, card, _, _ = seed(world)
    monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
    assert world.run("launch", "--runcard", card)[0] == 0
    code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
    assert code == 0, out
    runs = launch.load_launches(s, UNIT)
    runs[-1]["status"] = "exited 0"
    atomic_write(s.path("launches", UNIT), {"launches": runs})
    with open(runs[-1]["result_file"] + ".exit", "w", encoding="utf-8") as exit_file:  # the wrapper's exit file
      exit_file.write("0\n")
    f = posted_proceed({"dispatch_id": None, "rounds": [], "decisions": [], "rulings": []}, f"head-{UNIT}-c1")
    atomic_write(s.path("foreman", UNIT), f)
    return world.run("launch-builder", "--unit", UNIT, "--round", 2, "--runcard", card)
  from test_u57 import comment, serve
  s, card, rid = head_world(world)
  serve(world, comment(s, 901, f"**Ruling:** proceed {H7} — the medium is accepted risk"))
  code, out = proceed(world, rid, card, "--owner", "--posted", "901")
  assert code == 0, out
  atomic_write(s.path("foreman", "U01"), posted_proceed(foreman_of(s, "U01"), rid))
  if command == "inbox":  # a later posted round naming an owner-only fid: the walk reads every ruling
    f = foreman_of(s, "U01")
    f["rounds"].append({"round": 2, "phase": "posted", "launch": 1, "head": "a" * 40,
                        "outcome": "owner: change-review-1-1"})
    atomic_write(s.path("foreman", "U01"), f)
    out = inbox_text(s)  # what `superegm inbox` prints for this handoff
    assert "U01 | owner | " in out, out  # the walk reached the owner-only fid
    return 0, out
  f = foreman_of(s, "U01")
  f["decisions"].append({"id": "q1", "point": 1, "source": f"review {rid} round 1", "question": "owner: f1",
                         "options": ["change-review-1-1 allowed"]})
  atomic_write(s.path("foreman", "U01"), f)
  return world.run("decision", "rule", "--unit", "U01", "--decision", "q1", "--ruling",
                   "change-review-1-1 allowed — accepted risk", "--by", "owner", "--runcard", card)


@pytest.mark.parametrize("command", ["inbox", "decision rule on a later point-1 decision", "launch-builder"])
def test_readers_run_after_a_posted_proceed(world, monkeypatch, spawn_fake, command):
  # foreman.rulings[] holds a proceed entry without `decision`; proceeds[] holds the posted entry
  result = Result(lambda: run_after_a_posted_proceed(world, monkeypatch, command))
  assert result.returncode == 0, result.stderr
  assert "KeyError" not in result.stderr


def read(path):
  """A repository file's text, from the repository root."""
  return (Path(__file__).resolve().parents[2] / path).read_text(encoding="utf-8")


def test_wave_lists_waiting_proceed():
  # the wave's state list names the new state
  assert "waiting proceed" in read("skills/wave/SKILL.md")


# ---------------------------------------------------------------- round 1 review: the readers' remaining paths

H1, H2 = "a" * 40, "c" * 40
VIEW = {"launched": True, "landed": False, "pr": 70, "ci": "green", "head": H1}


def proceeded_foreman(rounds=(), launch_n=1, head=H1):
  return {"rounds": list(rounds), "decisions": [], "rulings": [],
          "proceeds": [{"ruling": "R1", "review": "head-U01-c1", "head": head, "launch": launch_n}]}


def test_ready_again_reads_the_proceed():
  # change-review-1-2: a clean an ingest rewrote is ready again, unless a proceed not older by launch authorizes it
  rewritten = {"round": 1, "phase": "posted", "launch": 1, "head": H1, "outcome": "revise", "rewritten_from": "clean"}
  runs = [{"round": 1, "status": "exited 0"}]
  assert launch.ready_again({"rounds": [rewritten]}, runs) is True
  assert launch.ready_again(proceeded_foreman([rewritten]), runs) is False
  assert launch.ready_again(proceeded_foreman([rewritten], launch_n=0), runs) is True


def test_latest_clean_reads_the_head_of_a_plain_clean_round():
  # change-review-1-3: a round posted clean on a head the pull request has left no longer frees the slot
  clean = {"round": 1, "phase": "posted", "launch": 1, "head": H1, "outcome": "clean"}
  runs = [{"round": 1, "status": "exited 0"}]
  foreman = {"rounds": [clean], "decisions": [], "rulings": []}
  assert launch.latest_clean(foreman, runs, H1) is True
  assert launch.latest_clean(foreman, runs, None) is True
  assert launch.latest_clean(foreman, runs, H2) is False
  assert report.unit_state("U01", {**VIEW, "head": H2}, foreman, runs, {}, {}, NOW) == "active"
  headless = {"rounds": [{k: v for k, v in clean.items() if k != "head"}], "decisions": [], "rulings": []}
  assert launch.latest_clean(headless, runs, H2) is True


@pytest.mark.parametrize("status, exit_file, waiting", [
  ("running", False, False),  # a later launch still running on the proceeded head: no waiting proceed, it holds a slot
  ("running", True, True),    # its exit file written before its status: terminal
  ("exited 0", False, True),
])
def test_waiting_proceed_reads_the_later_launch_finished(tmp_path, status, exit_file, waiting):
  # change-review-1-4: both branches of `finished`
  result = tmp_path / "U01_r2.json"
  if exit_file:
    Path(str(result) + ".exit").write_text("0\n", encoding="utf-8")
  runs = [{"round": 1, "status": "exited 0"}, {"round": 2, "status": status, "result_file": str(result)}]
  foreman = proceeded_foreman()
  assert launch.waiting_proceed(foreman, runs, H1) is waiting
  assert launch.latest_clean(foreman, runs, H1) is False
  assert report.unit_state("U01", VIEW, foreman, runs, {}, {}, NOW) == ("waiting proceed" if waiting else "active")


def test_merge_needs_the_proceeds_pinned_head(world):
  # change-review-1-5: a proceed with no pinned head offers no merge: `--match-head-commit` has nothing to pin
  s, card, rid = head_world(world)
  code, out = proceed(world, rid, card, "--owner", "--head", H7, "--reason", "accepted risk")
  assert code == 0, out
  f = foreman_of(s, "U01")
  f["proceeds"][-1]["head"] = None
  atomic_write(s.path("foreman", "U01"), f)
  items = inbox_items(s, [s.handoff_id])
  assert not any(i["subject"] == "U01" and i["kind"] == "merge" for i in items), items
  assert "None" not in inbox_text(s)


@pytest.mark.parametrize("latest", [
  None,
  {"round": 1, "phase": "posted", "launch": 1, "outcome": "revise"},
  {"round": 1, "phase": "posted", "launch": 1, "outcome": "contested: change-review-1-1"},
  {"round": 1, "phase": "posted", "launch": 1, "outcome": "cap-reached"},
])
def test_board_action_of_a_proceeded_head(latest):
  # codebase-details-1-1: a head made clean by a proceed awaits its merge, whatever its latest posted round said
  runs = {"round": 1, "status": "exited 0"}
  assert report.next_action("clean", latest, runs, [], None, proceeded=True) == "await-merge"
  if latest:
    assert report.next_action("clean", latest, runs, [], None) != "await-merge"


# ---------------------------------------------------------------- round 2 review


def proceed_items(s):
  return [i for i in inbox_items(s, [s.handoff_id]) if i["subject"] == "U01" and i["kind"] == "proceed"]


def test_proceed_again_item_is_keyed_on_the_later_launch_and_head(world):
  # change-review-2-1: the `proceed again` item's fingerprint is the later launch and the head it left
  s, card, rid = head_world(world)
  code, out = proceed(world, rid, card, "--owner", "--head", H7, "--reason", "accepted risk")
  assert code == 0, out
  launches(s, "U01", 1, 2)  # the merge launch after the proceed, terminal
  head = reading(s, card)[0]["head"]
  assert [i["fingerprint"] for i in proceed_items(s)] == [f"U01/proceed/2/{head}"]
  set_head(s, "U01", H2)  # a moved head is a new item to `notify`
  assert [i["fingerprint"] for i in proceed_items(s)] == [f"U01/proceed/2/{H2}"]


def test_loop_ended_names_waiting_proceed():
  # change-review-2-2, codebase-details-2-1: the end reason names a unit waiting proceed
  ended, reason = report.loop_ended({"U01": "clean", "U02": "waiting proceed"}, [], 1)
  assert ended is True
  assert reason == ("every launched unit is clean, landed, stopped, pending, idle or waiting proceed"
                    " (waiting proceed: U02)")
  assert report.loop_ended({"U01": "clean"}, [], 1) == (True, "every launched unit is clean, landed, stopped, pending or idle")


def test_head_less_proceed_asks_for_a_proceed_again(world):
  # codebase-details-2-2: a proceed with no pinned head offers no merge, so the board does not say `await-merge`;
  # with a pull request head to pin, the board and the inbox both ask for the owner's proceed again on it
  latest = {"round": 1, "phase": "posted", "launch": 1, "outcome": "revise"}
  runs = {"round": 1, "status": "exited 0"}
  assert report.next_action("clean", latest, runs, [], None, proceeded=True, pinned=False) == "proceed again"
  assert report.next_action("clean", latest, runs, [], None, proceeded=True) == "await-merge"
  s, card, rid = head_world(world)
  code, out = proceed(world, rid, card, "--owner", "--head", H7, "--reason", "accepted risk")
  assert code == 0, out
  f = foreman_of(s, "U01")
  f["proceeds"][-1]["head"] = None
  atomic_write(s.path("foreman", "U01"), f)
  head = reading(s, card)[0]["head"]
  assert head
  assert [(i["action"], i["fingerprint"].rsplit("/", 1)[1]) for i in proceed_items(s)] == [("answer in the inbox", head)]


# ---------------------------------------------------------------- round 3 review


def board_row(world, s, card, uid="U01"):
  code, out = world.run("report", "--runcard", card)
  assert code == 0, out
  text = s.path("wave_report", 1).read_text(encoding="utf-8")
  return next(line for line in text.splitlines() if line.startswith(f"| {uid} #"))


@pytest.mark.parametrize("pinned, action", [(True, "await-merge"), (False, "proceed again")])
def test_board_shows_the_proceeds_action(world, pinned, action):
  # change-review-3-1: the board itself, not `next_action` alone, reads the proceed and its pinned head
  s, card, rid = head_world(world)
  code, out = proceed(world, rid, card, "--owner", "--head", H7, "--reason", "accepted risk")
  assert code == 0, out
  if not pinned:
    f = foreman_of(s, "U01")
    f["proceeds"][-1]["head"] = None
    atomic_write(s.path("foreman", "U01"), f)
  cells = [c.strip() for c in board_row(world, s, card).strip("|").split("|")]
  assert cells[1] == "clean" and cells[7] == action, cells


def test_proceed_again_names_no_missing_head(world):
  # codebase-details-3-3: a later launch finished on a proceed that pinned no head, and the pull request has
  # none: no `proceed again: U01 head None`, keyed `2/None`, until a head exists to proceed on
  s, card, rid = head_world(world)
  code, out = proceed(world, rid, card, "--owner", "--head", H7, "--reason", "accepted risk")
  assert code == 0, out
  f = foreman_of(s, "U01")
  f["proceeds"][-1]["head"] = None
  atomic_write(s.path("foreman", "U01"), f)
  launches(s, "U01", 1, 2)
  set_head(s, "U01", None)
  assert proceed_items(s) == []
  assert "None" not in inbox_text(s)
  set_head(s, "U01", H2)
  assert [i["fingerprint"] for i in proceed_items(s)] == [f"U01/proceed/2/{H2}"]


def test_waiting_proceed_reads_before_the_ci_wait():
  # codebase-details-4-1: a proceeded unit whose head moved, CI pending past `ci_wait_minutes`, reads `waiting
  # proceed` (the owner's next step), not the CI-wait `idle`; a unit with no proceed on that head reads `idle`
  view = {**VIEW, "head": H2, "ci": "pending"}
  card = {"heads": [{"unit": "U01", "head": H2, "seen_at": NOW - 3600}]}
  runs = [{"round": 1, "status": "exited 0"}]
  config = {"ci_wait_minutes": 30}
  assert report.unit_state("U01", view, proceeded_foreman(), runs, card, config, NOW) == "waiting proceed"
  clean = {"round": 1, "phase": "posted", "launch": 1, "head": H1, "outcome": "clean"}
  plain = {"rounds": [clean], "decisions": [], "rulings": []}
  assert report.unit_state("U01", view, plain, runs, card, config, NOW) == "idle"
