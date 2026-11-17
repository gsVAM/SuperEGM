# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U92

"""U92: proceed's readers (spec section 4.2): `launch`, `report`, `inbox` and `review` read a proceeded head through
its authorizing outcome, the newer by launch of the latest round posted clean and the newest `proceeds[]` entry."""

import json
import time

import pytest

from conftest import set_config  # noqa: F401
from superegm import atomic_write, launch, report
from superegm.inbox import inbox_items, line_of
from test_wave import foreman_of
from test_u57 import head_world, proceed, launches, REPO
from test_u43 import registry  # noqa: F401 -- autouse: HOME under tmp_path

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
