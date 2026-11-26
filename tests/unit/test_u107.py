# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U107's tests of the inbox (1.3 design section 3.9): a head proceed pins the head
# the owner was shown, the repository check, no undo beside a proceed's merge, a capped round's contest no panel will
# rule, a decision's own verdict file, and the inbox skill's and `rulings.md`'s new forms.

"""U107 (1.3 design section 3.9): the inbox. Fixtures: conftest's `world`; test_u57's head world, test_inbox's seeds."""

import json

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import make_pr
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
  # round 2 (astra-1-1): the builder pushed and the wave has not saved the new head yet: GitHub's head is read afresh
  ("posted **Ruling:** proceed <shown7> — ok", "pushed, not yet saved", "moved"),
  ("typed --head <shown7> --reason ok", "pushed, not yet saved", "moved"),
  # round 3 (astra-2-1): no `status --wait` snapshot, the pull request known from `status`'s `units[<id>].pr` alone
  ("posted **Ruling:** proceed <shown7> — ok", "pushed, no status snapshot", "moved"),
  ("typed --head <shown7> --reason ok", "pushed, no status snapshot", "moved"),
  # round 5 (astra-3-1): `status --watch` replaced the pull request; the snapshot still names the old one at `shown`
  ("posted **Ruling:** proceed <shown7> — ok", "watched a replacement pull request", "moved"),
  ("typed --head <shown7> --reason ok", "watched a replacement pull request", "moved"),
  ("posted comment 901, recorded before 1.3 from **Ruling:** proceed — ship it", "watched a replacement pull request", "moved"),
  ("posted **Ruling:** proceed — ok", "shown", NEEDS),
  ("typed --reason ok", "shown", NEEDS),
  ("posted comment 901, recorded before 1.3 from **Ruling:** proceed — ship it", "shown", "replayed"),
  # round 3 (astra-2-2): the recorded comment replayed once GitHub's head moved: refused, nothing written
  ("posted comment 901, recorded before 1.3 from **Ruling:** proceed — ship it", "pushed, not yet saved", "moved"),
])
def test_head_proceed_pins_the_shown_head(world, how, head_now, outcome):
  # a head proceed records the head the owner saw, and is refused once the unit's head moved or without a head;
  # a proceeds[] entry recorded before 1.3 (head == shown) replays as recorded and its merge keeps its pinned head
  s, card, rid = head_world(world)
  shown = "a" * 40
  shown7 = shown[:7]
  recorded_entry = {"ruling": "R1", "review": rid, "posted": "comment 901", "posted_at": UPDATED,
                    "issue": issue_of(s, "U01"), "head": shown, "launch": 1, "by": OWNER, "reason": "ship it"}
  if "recorded before 1.3" in how:
    f = foreman_of(s, "U01")
    f["proceeds"] = [recorded_entry]
    atomic_write(s.path("foreman", "U01"), f)
    serve(world, comment(s, 901, "**Ruling:** proceed — ship it"))
  elif how.startswith("posted"):
    serve(world, comment(s, 901, "**Ruling:** proceed " + (f"{shown7} — ok" if "<shown7>" in how else "— ok")))
  if head_now == "moved":  # the builder pushed after the owner was shown `shown`, and `status --wait` saved it
    set_head(s, "U01", "d" * 40)
    world.gh.prs[70]["headRefOid"] = "d" * 40
  elif head_now == "pushed, not yet saved":  # the saved head is still `shown`; the pull request's is not
    world.gh.prs[70]["headRefOid"] = "d" * 40
  elif head_now == "pushed, no status snapshot":  # no saved view: the head the latest round reviewed is `shown`
    state = json.loads(s.path("state").read_text(encoding="utf-8"))
    state["status"]["units"].pop("U01")
    atomic_write(s.path("state"), state)
    world.gh.prs[70]["headRefOid"] = "d" * 40
  elif head_now == "watched a replacement pull request":  # `status --watch U01=72`: #70 still at `shown`, #72 is not
    make_pr(world.gh, 72, "d" * 40)
    state = json.loads(s.path("state").read_text(encoding="utf-8"))
    state["units"]["U01"].update(watch={"number": 72, "at": UPDATED}, pr={"number": 72, "head": "d" * 40})
    atomic_write(s.path("state"), state)
  before = foreman_of(s, "U01").get("proceeds", [])
  review_before = s.path("reviews", rid, "review.json").read_bytes()
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
    assert code == 1 and foreman.get("proceeds", []) == before and (outcome == "moved" or NEEDS in out), out
    assert s.path("reviews", rid, "review.json").read_bytes() == review_before  # nothing recorded, no finding settled
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


@pytest.mark.parametrize("authorized_by, refused", [
  ("proceed", True), ("clean round", False),
  # round 2 (change-review-1-1, codebase-details-1-1): the proceed's pull request merged since: refused for that reason
  ("proceed, its pull request merged", True),
])
def test_undo_refused_while_a_proceeds_merge_is_offered(world, tmp_path, monkeypatch, authorized_by, refused):
  # U01's merge is offered; its latest posted round deferred change-review-1-1; the owner posts
  # `**Ruling:** change-review-1-1 finding upheld`
  from test_foreman import PR
  from test_u40 import F1, UPHELD, deferred_round, owner_comment, rule_posted
  w = deferred_round(world, tmp_path, monkeypatch)
  st, handoff_id = w.st, w.st.handoff_id
  if authorized_by.startswith("proceed"):  # the owner's proceed on the clean round's head: it authorizes the merge
    code, out = world.run("review", "rule", "--review", w.rid, "--ruling", "proceed", "--owner", "--head", w.head[:7],
                          "--reason", "ship it", "--runcard", w.child)
    assert code == 0, out
  if authorized_by.endswith("merged"):
    world.gh.prs[PR].update({"state": "MERGED", "mergedAt": "2026-11-03T08:00:00Z"})
  [merge] = [i for i in inbox_items(st, [handoff_id]) if i["kind"] == "merge"]
  assert ("undo" in merge) is not refused  # the inbox offers no undo the helper would refuse
  before = foreman_of(st, "U01")["followups"]
  owner_comment(world, 77, UPHELD)
  code, out = rule_posted(world, w, f"{F1} finding upheld", 77)
  foreman = foreman_of(st, "U01")
  assert code == (1 if refused else 0), out
  if refused:
    assert "decision: undo refused: " in out and "the follow-up row stays" in out and foreman["followups"] == before
    why = f"pull request #{PR} is merged" if authorized_by.endswith("merged") else "merge on the owner's proceed is still offered"
    assert why in out and why in st.path("journal").read_text(encoding="utf-8"), out  # the reason the wave reads
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


# ---------------------------------------------------------------- S6: a decision's own verdict file


@pytest.mark.parametrize("last_line, pending", [
  ("The judges did not converge (judges/head-U01-c1-r1-a1b2c3/verdict.json), their last choices: Q1 …", True),
  ("The judges did not converge (judges/head-U01-c2-r1-a1b2c3/verdict.json), their last choices: Q1 …", False),
  ("foreman-1-2 | high | src/x.py:9 | regression: no | see (judges/p1/verdict.json), their last choices: x", False),
  ("foreman-1-2 | high | src/x.py:9 | regression: no | The judges did not converge (judges/head-U01-c1-r1-a1b2c3/verdict.json)", False),
])
def test_pending_decision_reads_its_own_verdict_file(last_line, pending):
  # q1: point 1, source `review head-U01-c1 round 1`, asks foreman-1-1 and foreman-1-2, its question ending last_line; foreman-1-1 is ruled
  from superegm import report
  asks = "foreman-1-1 | high | src/x.py:3 | regression: no | a\nforeman-1-2 | high | src/x.py:9 | regression: no | b\n"
  q1 = {"id": "q1", "point": 1, "source": "review head-U01-c1 round 1", "question": asks + last_line + "\n",
        "options": ["finding upheld", "finding overruled"]}
  foreman = {"decisions": [q1], "rulings": [{"decision": "q1", "ruling": "foreman-1-1 finding upheld"}]}
  assert (report.pending_decisions(foreman) == [q1]) == pending


# ---------------------------------------------------------------- S7: the inbox skill and rulings.md


def line_starting(text, prefix):
  """The one line of `text` that starts with `prefix` (a kind's bullet, a numbered step)."""
  [found] = [line for line in text.splitlines() if line.startswith(prefix)]
  return found


def test_inbox_and_rulings_show_the_new_forms():
  # the head proceed forms; #236: the cap command's --runcard, the unpinned proceed among undo's reasons, `undo` in
  # step 4, no undo beside a proceed's merge, the respec hold in the merge and undo bullets; L21: a draft readied before the merge
  from conftest import ROOT
  inbox_skill = (ROOT / "skills/inbox/SKILL.md").read_text(encoding="utf-8")
  rulings = (ROOT / "skills/wave/references/rulings.md").read_text(encoding="utf-8")
  cap_bullet, undo_bullet = line_starting(inbox_skill, "- `cap`:"), line_starting(inbox_skill, "- `undo`:")
  merge_bullet = line_starting(inbox_skill, "- `merge`:")
  step_4, step_9 = line_starting(inbox_skill, "4. "), line_starting(inbox_skill, "9. ")
  for text in (inbox_skill, rulings):
    assert "**Ruling:** proceed <sha7> — <reason>" in text and "**Ruling:** proceed — <reason>" not in text
  assert "review rule --ruling proceed --head <sha7> --owner --reason <text>" in rulings
  assert "--runcard" in cap_bullet and "without a pinned head" in undo_bullet and "respec" in undo_bullet and "undo" in step_4
  assert "respec" in merge_bullet and "refused while the proceed's merge is still offered" in merge_bullet
  assert step_9.index("gh pr ready <n> -R <repo>") < step_9.index("gh pr merge <n> -R <repo>")
