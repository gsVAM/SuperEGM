# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U72

"""U72 (spec 1.2.1 section 7.3): the inbox is a typed external skill that asks the owner in words and does the
rest; every ruling item's action points to the inbox, with its `**Ruling:**` forms and the URL it is posted on; a
review's cap or escalation points to that review's skill session; the machine steps stay typed commands."""

import json
import runpy
from pathlib import Path

import pytest

import superegm
from conftest import REPO, ROOT
from superegm import atomic_write
from superegm.inbox import inbox_items, registry_items
from test_inbox import D, F, HEAD, POSTED, REVIEW, ROUND, U, seed
from test_wave import open_wave_card, wave_store
from test_u57 import head_world, launches, proceed
from test_u43 import registry  # noqa: F401 -- autouse: HOME under tmp_path
from test_builders import spawn_fake, which, no_graphify  # noqa: F401 -- launch-builder starts no builder, finds `gh`

PACKER = runpy.run_path(str(ROOT / "scripts/pack_plugin.py"))
SKILL = ROOT / "skills/inbox/SKILL.md"

SEEDS = {  # one unit's state per kind, as test_inbox's table seeds it
  "decision": U(decisions=D(3, "comment 77")),
  "contested": U(decisions=D(1, "review head-U01-c1 round 1"), rounds=POSTED(),
                 reviews=HEAD(1, F("high"), builder_contested=[{"fid": "foreman-1-1", "reason": "r"}])),
  "test-delta": U(rounds=POSTED(), reviews=HEAD(1, [{**F("high")[0], "claim": "test-delta: tests/test_x.py:3 removed"}])),
  "owner": U(rounds=POSTED(1, "owner: foreman-1-1")),
  "cap": U(rounds=POSTED(5), reviews=HEAD(5, F("high")), decisions=D(2, "review head-U01-c1 cap")),
  "stalled": U(rounds=[{"round": n, "phase": "collected", "outcome": "not run (error: x)", "runcard": "wave-1"} for n in (1, 2)],
               reviews=HEAD(0, [])),
  "plan cap": U(reviews=REVIEW("plan", "plan-U01-c1", {n: ROUND(n, F("high")) for n in range(1, 6)})),
}


def item_of(world, kind):
  """The one item of `kind` the inbox lists for the seeded unit."""
  if kind == "proceed again":  # test_u92: a proceed, then a later launch on it: waiting proceed
    s, card, rid = head_world(world)
    assert proceed(world, rid, card, "--owner", "--reason", "accepted risk")[0] == 0
    launches(s, "U01", 1, 2)
    want = "proceed"
  elif kind == "kill_failed":
    open_wave_card(world)
    s = wave_store(world, U01={"launches": [{"round": 1, "status": "running", "started_at": "t", "result_file": "/w/r1.json",
                                             "pid": 4242, "kill_failed": "no exit file"}]})
    want = "kill_failed"
  else:
    open_wave_card(world)
    s = seed(world, **SEEDS[kind])
    want = kind.split(" ")[-1]
  found = [i for i in inbox_items(s, [s.handoff_id]) if i["kind"].split(" ")[0] == want]
  assert len(found) == 1, found
  return found[0]


def test_the_inbox_is_a_typed_external_skill():
  # the house reader returns frontmatter values as strings
  fm = PACKER["read_frontmatter"](SKILL)
  assert (fm["effects"], fm["effect_kinds"], fm["disable-model-invocation"]) == ("external", "[github-write, state-store, start-session]", "true")
  assert "inbox" in PACKER["TYPED_SKILLS"]


@pytest.mark.parametrize("kind, action", [
  ("decision", "answer in the inbox"), ("contested", "answer in the inbox"), ("test-delta", "answer in the inbox"),
  ("owner", "answer in the inbox"), ("cap", "answer in the inbox"), ("stalled", "answer in the inbox"),
  ("proceed again", "answer in the inbox"), ("plan cap", "answer in your review-plan session"),
  ("kill_failed", "/superegm:interrupt --unit U01 --launch 1, then /superegm:wave")])
def test_action_text_points_to_the_inbox(world, kind, action):
  # a ruling is answered in the inbox; the stated machine steps stay typed commands
  item = item_of(world, kind)
  assert item["action"] == action
  assert kind in ("kill_failed", "plan cap") or item["forms"] and all(f.startswith("**Ruling:**") for f in item["forms"]) and item["on"].startswith("https://")
  assert kind == "kill_failed" or "**Ruling:**" not in item["action"] and "superegm " not in item["action"]


MERGE_SEEDS = {  # round 2 (change-review-1-2, astra-1-2): the head a merge covers, and what offers none
  "covered head": (U(rounds=POSTED(1, "clean"), launches=[{"round": 1, "status": "exited 0"}]), ["merge"]),
  "pending decision": (U(rounds=POSTED(1, "clean"), launches=[{"round": 1, "status": "exited 0"}], decisions=D(3, "comment 77")),
                       ["decision"]),
  "live launch": (U(rounds=POSTED(1, "clean"), launches=[{"round": 1, "status": "running"}]), []),
}


@pytest.mark.parametrize("case", MERGE_SEEDS)
def test_a_merge_carries_its_head_and_is_offered_only_past_the_guards(world, case):
  open_wave_card(world)
  seeded, kinds = MERGE_SEEDS[case]
  s = seed(world, **seeded)
  found = [i for i in inbox_items(s, [s.handoff_id]) if i["kind"] in ("merge", "decision")]
  assert [i["kind"] for i in found] == kinds
  assert case != "covered head" or found[0]["head"] == seeded["U01"]["head"]  # the head the clean verdict covered


def test_a_proceed_item_carries_the_head_it_covers(world):
  """Round 2 (change-review-1-5): the head no longer in the action is the item's `head`."""
  item = item_of(world, "proceed again")
  assert item["head"] and item["fingerprint"].endswith("/" + item["head"])


def test_a_chained_handoff_leaves_a_plan_reviews_cap_to_its_wait_record(world, monkeypatch):
  """Round 2 (change-review-1-1): on a chained handoff (the chain on, a frozen mode) a plan review's cap reaches the
  owner as the wait record (spec 1.2.1 section 7.3), so the inbox lists no `answer in your review-plan session`."""
  open_wave_card(world)
  s = seed(world, **SEEDS["plan cap"])
  core = inbox_items.__globals__["core"]
  monkeypatch.setattr(core, "frozen_mode", lambda hs: "normal")
  monkeypatch.setattr(core, "chain_on", lambda config: True)
  monkeypatch.setitem(inbox_items.__globals__, "chain_items", lambda *a: [])  # no driver record in this store
  assert not [i for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "cap"]


def test_a_head_cap_without_its_decision_offers_no_form(world):
  """Round 3 (astra-2-1): a head at its cap whose point-2 decision is not open yet has no decision a posted ruling
  could rule (decision.verify_posted drops it), so the item offers no form until the wave opens the decision."""
  open_wave_card(world)
  s = seed(world, **U(rounds=POSTED(5), reviews=HEAD(5, F("high"))))
  [cap] = [i for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "cap"]
  assert cap["action"] == "its decision point 2 opens at the next wave" and "forms" not in cap and "on" not in cap


def test_a_chained_handoff_leaves_a_plan_decision_to_its_wait_record(world, monkeypatch):
  """Round 3 (change-review-2-1): on a chained handoff a plan's unanswered `blocking: yes` D<n> line reaches the
  owner as the wait record (spec 1.2.1 section 7.3), so no `escalated` item is listed; unchained it is."""
  open_wave_card(world)
  s = seed(world, escalated=["spec-sample-c1:design-1-1"], **U())
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state.pop("decisions")  # D2 still unanswered
  atomic_write(s.path("state"), state)
  plan = Path(state["plan"])
  plan.write_text(plan.read_text(encoding="utf-8").replace("D2 Page size for the listing?", "D2 Page size (spec-sample-c1:design-1-1: c)?"), encoding="utf-8")
  esc = lambda: [i["action"] for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "escalated"]
  assert esc() == ["answer in your plan session"]
  core = inbox_items.__globals__["core"]
  monkeypatch.setattr(core, "frozen_mode", lambda hs: "normal")
  monkeypatch.setattr(core, "chain_on", lambda config: True)
  monkeypatch.setitem(inbox_items.__globals__, "chain_items", lambda *a: [])  # no driver record in this store
  assert esc() == []


def test_a_bad_root_line_names_its_handoff(world, tmp_path):
  """Round 3 (codebase-details-2-6): every `--json` object names its handoff, a registry entry's bad-root line too."""
  open_wave_card(world)
  s = seed(world, **U(decisions=D(3, "comment 77")))
  items = registry_items({"repo": REPO, "root": str(tmp_path / "x"), "artifacts_dir": str(s.root)})
  assert [i for i in items if i["fingerprint"].startswith("root:")] and all(i.get("handoff") == s.handoff_id for i in items)


def test_inbox_withdrawn_refusal_names_the_flags_it_parses(world):
  """Round 3 (codebase-details-2-2): the refusal names only flags the inbox parser registers."""
  seed(world, **U())
  args = superegm.build_parser().parse_args(["inbox", "withdrawn", "--pr", "12", "--reason", "head moved"])
  superegm.CURRENT_WRITES, superegm.CURRENT_SUBCOMMAND = args.writes, args.command
  try:
    with pytest.raises(superegm.HandoffError) as refused:
      args.run(args)
  finally:
    superegm.CURRENT_WRITES = superegm.CURRENT_SUBCOMMAND = None
  assert "--plan" in str(refused.value) and "--spec" not in str(refused.value)


@pytest.mark.parametrize("phrase", [
  "`registry.json`", "`artifacts_dir`", "`conflict`", "pinned head", "CONFLICTING",
  "its decision point 2 opens at the next wave", "the listing never reads the respec mark"])
def test_the_inbox_skill_names_round_three_text(phrase):
  # round 3: the registered root, the conflict kind and every merge guard, the cap with no decision yet, the respec mark
  assert phrase in SKILL.read_text(encoding="utf-8")


@pytest.mark.parametrize("phrase", [
  "gh api user --jq .login", "`config.owners`", "recommended", "one-line reason",
  "leavemealone", "did not converge", "back once", "gh issue comment <n> -R <repo> --body-file",
  "proceed again", "**Ruling:** proceed — <reason>", "superegm next answer --handoff",
  "handoff_dryrun.md", "superegm approve-spec --void --spec", "answer in your",
  "superegm driver kick --root", "No skill asks the owner to post a comment or to paste a command"])
def test_the_inbox_skill_names_each_step(phrase):
  # the skill asks in words and does the rest; listing stays read-only
  assert phrase in SKILL.read_text(encoding="utf-8")


@pytest.mark.parametrize("phrase", [
  "gh pr merge <n> -R <repo> --<method> --match-head-commit <sha>", "gh repo view -R <repo> --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed",
  "`merge`, `squash` and `rebase`", "moved since", "merge with the admin bypass?", "`--admin` only on yes",
  "merges after", "did not name", "stopped", "respec mark", "pending decision", "live launch",
  "clean or proceeded", "superegm inbox withdrawn --pr <n> --reason <text> --handoff <id>", "opens and closes its own inbox card"])
def test_the_merge_step_guards_each_merge(phrase):
  # a method always, the bypass only on yes, merge order, and the state read again before each merge
  assert phrase in SKILL.read_text(encoding="utf-8")
