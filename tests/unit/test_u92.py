# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U92

"""U92: proceed's readers (spec section 4.2): `launch`, `report`, `inbox` and `review` read a proceeded head through
its authorizing outcome, the newer by launch of the latest round posted clean and the newest `proceeds[]` entry."""

import json
import time
import traceback

import pytest

from conftest import set_config  # noqa: F401
from superegm import atomic_write, launch, report
from superegm.inbox import inbox_items, line_of
from test_wave import foreman_of
from test_u57 import head_world, proceed, launches, REPO
from test_u43 import registry  # noqa: F401 -- autouse: HOME under tmp_path
from test_builders import spawn_fake, which, no_graphify  # noqa: F401 -- launch-builder starts no builder, finds `gh`

NOW = time.time()


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
    code, out = proceed(world, rid, card, "--owner", "--reason", "accepted risk")
    assert code == 0, out
    set_head(s, "U01", "c" * 40)
  else:
    code, out = proceed(world, rid, card, "--owner", "--reason", "accepted risk")
    assert code == 0, out
    launches(s, "U01", 1, 2)  # the merge launch after the proceed, terminal
    if case == "second proceed naming the later launch":
      set_head(s, "U01", "c" * 40)
      code, out = proceed(world, rid, card, "--owner", "--reason", "the merge round is fine")
      assert code == 0, out
      assert foreman_of(s, "U01")["proceeds"][-1]["launch"] == 2
  view, foreman, entries, card_json = reading(s, card)
  # `report` holds no slot for U01 while waiting; `inbox` keys the item on that launch and head
  assert report.unit_state("U01", view, foreman, entries, card_json, {}, NOW) == ("clean" if merge_offered else "waiting proceed")
  assert launch.in_flight(s, "U01", view, set()) is False
  text = inbox_text(s)
  assert ("proceed again: U01 head" in text) is not merge_offered, text
  assert any(i["subject"] == "U01" and i["kind"] == "merge" for i in inbox_items(s, [s.handoff_id])) is merge_offered, text
  if not merge_offered:
    head = view["head"]
    assert f"proceed again: U01 head {head}" in text, text
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
  set_config(world, repo=REPO, owners=["owner"])
  return s, card, out.strip()


@pytest.mark.parametrize("case", ["attempts never posted", "typed proceed on a never-posted head",
                                  "head cycle with no foreman round"])
def test_inbox_offers_merge_on_the_authorizing_head(world, case):
  s, card, rid = unposted_world(world, case)
  code, out = proceed(world, rid, card, "--owner", "--reason", "ship it")
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
  code, out = proceed(world, rid, card, "--owner", "--reason", "accepted risk")
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
  serve(world, comment(s, 901, "**Ruling:** proceed — the medium is accepted risk"))
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
