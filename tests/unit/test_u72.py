# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U72

"""U72 (spec 1.2.1 section 7.3): the inbox is a typed external skill that asks the owner in words and does the
rest; every ruling item's action points to the inbox, with its `**Ruling:**` forms and the URL it is posted on; a
review's cap or escalation points to that review's skill session; the machine steps stay typed commands."""

import runpy
from pathlib import Path

import pytest

from conftest import ROOT
from superegm.inbox import inbox_items
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
  "cap": U(rounds=POSTED(5), reviews=HEAD(5, F("high"))),
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
