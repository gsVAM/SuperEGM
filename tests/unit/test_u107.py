# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U107's tests of the inbox (1.3 design section 3.9): a head proceed pins the head
# the owner was shown, the repository check, no undo beside a proceed's merge, a capped round's contest no panel will
# rule, a decision's own verdict file, and the inbox skill's and `rulings.md`'s new forms.

"""U107 (1.3 design section 3.9): the inbox. Fixtures: conftest's `world`; test_u57's head world, test_inbox's seeds."""

import json

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import atomic_write
from superegm.inbox import inbox_items
from test_inbox import HEAD, U, seed
from test_wave import foreman_of, open_wave_card
from test_u57 import OWNER, UPDATED, comment, head_world, issue_of, launches, proceed, round_zero, serve
from test_u43 import registry  # noqa: F401 -- autouse: HOME under tmp_path

NEEDS = 'proceed needs the head: write "proceed <sha7> — <reason>"'


def set_head(s, uid, head):
  """The pull request's head as `status --wait` saves it."""
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"][uid]["head"] = head
  atomic_write(s.path("state"), state)


# ---------------------------------------------------------------- S1: a head proceed pins the head shown


@pytest.mark.parametrize("how, head_now, outcome", [
  ("posted **Ruling:** proceed <shown7> — ok", "shown", "recorded"),
  ("typed --head <shown7> --reason ok", "shown", "recorded"),
  ("posted **Ruling:** proceed <shown7> — ok", "moved", "moved"),
  ("typed --head <shown7> --reason ok", "moved", "moved"),
  ("posted **Ruling:** proceed — ok", "shown", NEEDS),
  ("typed --reason ok", "shown", NEEDS),
  ("posted comment 901, recorded before 1.3 from **Ruling:** proceed — ship it", "shown", "replayed"),
])
def test_head_proceed_pins_the_shown_head(world, how, head_now, outcome):
  # a head proceed records the head the owner saw, and is refused once the unit's head moved or without a head;
  # a proceeds[] entry recorded before 1.3 (head == shown) replays as recorded and its merge keeps its pinned head
  s, card, rid = head_world(world)
  shown = "a" * 40
  shown7 = shown[:7]
  recorded_entry = {"ruling": "R1", "review": rid, "posted": "comment 901", "posted_at": UPDATED,
                    "issue": issue_of(s, "U01"), "head": shown, "launch": 1, "by": OWNER, "reason": "ship it"}
  if outcome == "replayed":
    f = foreman_of(s, "U01")
    f["proceeds"] = [recorded_entry]
    atomic_write(s.path("foreman", "U01"), f)
    serve(world, comment(s, 901, "**Ruling:** proceed — ship it"))
  elif how.startswith("posted"):
    serve(world, comment(s, 901, "**Ruling:** proceed " + (f"{shown7} — ok" if "<shown7>" in how else "— ok")))
  if head_now == "moved":  # the builder pushed after the owner was shown `shown`
    set_head(s, "U01", "d" * 40)
  before = foreman_of(s, "U01").get("proceeds", [])
  if how.startswith("posted"):
    code, out = proceed(world, rid, card, "--owner", "--posted", "901")
  else:
    code, out = proceed(world, rid, card, "--owner", *(["--head", shown7] if "--head" in how else []), "--reason", "ok")
  foreman = foreman_of(s, "U01")
  if outcome == "recorded":
    assert code == 0 and foreman["proceeds"][-1]["head"] == shown and shown.startswith(shown7), out
  elif outcome == "replayed":
    assert (code, out.strip()) == (0, json.dumps(recorded_entry, sort_keys=True)) and foreman["proceeds"] == before, out
    [merge_item] = [i for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "merge"]
    assert f"--match-head-commit {shown}" in merge_item["action"]
  else:
    assert code == 1 and foreman.get("proceeds", []) == [] and (outcome == "moved" or NEEDS in out), out
  # a spec or plan review keeps the bare typed form
  _, cid, plan_rid, _, _ = round_zero(world)
  bare_typed_proceed_on_a_plan_review_code, out = proceed(world, plan_rid, cid, "--owner", "--reason", "planned enough")
  assert bare_typed_proceed_on_a_plan_review_code == 0, out


# ---------------------------------------------------------------- S2: every proceed offer shows its head


def proceed_offer_store(world, kind):
  """`proceed`: U01 proceeded on its head, then a later launch finished (waiting proceed); `stalled`: U01's head
  review stalled (`review status` exit 5)."""
  if kind == "proceed":
    s, card, rid = head_world(world)
    assert proceed(world, rid, card, "--owner", "--head", "a" * 7, "--reason", "accepted risk")[0] == 0
    launches(s, "U01", 1, 2)
    return s
  open_wave_card(world)
  return seed(world, **U(rounds=[{"round": n, "phase": "collected", "outcome": "not run (error: x)", "runcard": "wave-1"}
                                 for n in (1, 2)], reviews=HEAD(0, [])))


@pytest.mark.parametrize("kind", ["proceed", "stalled"])
def test_inbox_proceed_offers_show_the_head(world, kind):
  # every proceed the inbox offers carries the head it covers in the form the owner posts
  st = proceed_offer_store(world, kind)
  handoff_id = st.handoff_id
  [offer] = [i for i in inbox_items(st, [handoff_id]) if i["kind"] == kind]
  assert offer["forms"] == [f"**Ruling:** proceed {offer['head'][:7]} — <reason>"]


# ---------------------------------------------------------------- S3: the repository check


def mismatch_store(tmp_path, frozen):
  """A store whose config names `o/new`, holding handoff x-abc123 frozen on `frozen` (its `state.json`'s `repo`, as
  `core.require_repo` binds it): unit U01 filed as issue #2 with one pending point-3 decision, no wave card."""
  root = tmp_path / "store"
  st = superegm.Store(root, config={**superegm.DEFAULT_CONFIG, "repo": "o/new", "artifacts_dir": str(root)})
  hs = superegm.handoff_store(st, "x-abc123")
  spec = tmp_path / "x.md"
  spec.write_text("# x\n", encoding="utf-8")
  atomic_write(st.path("handoffs", "x-abc123"), {"id": "x-abc123", "spec": str(spec), "opened_at": "t", "closed_at": None})
  atomic_write(hs.path("state"), {"handoff_id": "x-abc123", "repo": frozen, "units": {"U01": {"number": 2}},
                                  "status": {"units": {"U01": {"pr": None, "head": None, "ci": None, "landed": False}}}})
  atomic_write(hs.path("foreman", "U01"), {"dispatch_id": None, "rounds": [], "rulings": [],
                                           "decisions": [{"id": "q1", "point": 3, "source": "comment 77", "question": "q",
                                                          "asked_at": "t"}]})
  return st


@pytest.mark.parametrize("frozen, actions", [
  ("o/old", ["repo mismatch: x-abc123 was approved for o/old"]),
  ("o/new", ["answer in the inbox"]),
])
def test_repo_mismatch_replaces_the_handoffs_lines(tmp_path, frozen, actions):
  # config.repo is o/new; handoff x-abc123 is frozen on `frozen` with one pending point-3 decision and no wave card
  st = mismatch_store(tmp_path, frozen)
  items = inbox_items(st, ["x-abc123"])
  assert [i["action"] for i in items] == actions
  assert frozen == "o/new" or not any("forms" in i or "on" in i for i in items)


# ---------------------------------------------------------------- S4: no undo beside a proceed's merge


@pytest.mark.parametrize("authorized_by, refused", [("proceed", True), ("clean round", False)])
def test_undo_refused_while_a_proceeds_merge_is_offered(world, tmp_path, monkeypatch, authorized_by, refused):
  # U01's merge is offered; its latest posted round deferred change-review-1-1; the owner posts
  # `**Ruling:** change-review-1-1 finding upheld`
  from test_u40 import F1, UPHELD, deferred_round, owner_comment, rule_posted
  w = deferred_round(world, tmp_path, monkeypatch)
  st, handoff_id = w.st, w.st.handoff_id
  if authorized_by == "proceed":  # the owner's proceed on the clean round's head: the proceed authorizes the merge
    code, out = world.run("review", "rule", "--review", w.rid, "--ruling", "proceed", "--owner", "--head", w.head[:7],
                          "--reason", "ship it", "--runcard", w.child)
    assert code == 0, out
  [merge] = [i for i in inbox_items(st, [handoff_id]) if i["kind"] == "merge"]
  assert ("undo" in merge) is not refused  # the inbox offers no undo the helper would refuse
  before = foreman_of(st, "U01")["followups"]
  owner_comment(world, 77, UPHELD)
  code, out = rule_posted(world, w, f"{F1} finding upheld", 77)
  foreman = foreman_of(st, "U01")
  assert code == (1 if refused else 0), out
  if refused:
    assert "decision: undo refused: " in out and "the follow-up row stays" in out and foreman["followups"] == before
  else:
    assert foreman["followups"] == []


# ---------------------------------------------------------------- S5: a capped round's contest no panel will rule


@pytest.mark.parametrize("panel, fingerprints", [
  ("none opened", ["U01/contested/q1/foreman-1-1"]),
  ("split at its cap", ["U01/contested/q1/foreman-1-1"]),
  ("open, rounds to go", []),
])
def test_capped_round_contest_without_a_ruling_panel_is_listed(world, panel, fingerprints):
  # head-U01-c1 at its cap (review status exit 2): its round 5 of 5; point-1 decision q1 on its round; foreman-1-1
  # high and contested; the store's panel record for the round: none, one split at its cap, or one with rounds to go
  from test_u88 import CONTEST, SPLIT_LINE, contested_items
  record = {"none opened": None, "split at its cap": "capped", "open, rounds to go": "between"}[panel]
  line = SPLIT_LINE.replace("-r1-", "-r5-") if record == "capped" else ""
  assert contested_items(world, CONTEST.format("high") + line, n=5, panel=record) == fingerprints
