# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U10b's tests of the driver: report, decision open|rule, the wave skill body.

"""U10b: the pure functions the wave skill cites, `report`, `decision open|rule` and the skill body.
Fixtures: conftest's `world`, `applied` and `make_pr` (U03/U07)."""
import json
from pathlib import Path
import pytest
from conftest import applied, make_pr
from superegm import store, atomic_write
from superegm.report import unit_state, loop_ended, word_action

REPO, BUILDER, NOW = "example-org/webhooks", "builder-bot", 1_700_000_000.0
BLOCKED = "**Builder status:** BLOCKED\nWhich queue?\n- (a) use the in-memory queue\n- (b) use Redis\n"
CLEAN = {"launches": [{"round": 1, "status": "exited 0"}], "rounds": [{"round": 1, "phase": "posted", "outcome": "clean", "launch": 1}]}
SKILL = Path(__file__).resolve().parents[2] / "skills/wave/SKILL.md"


def open_wave_card(world):
  return world.open_card("wave", world.spec)


def fake_gh(world, routes=None):
  """U03's `extend`: `gh api <route>` from `routes` (else the built-in), `gh issue edit --add-label` into
  `world.gh.issues[<n>]["labels"]`, `gh issue comment` into `world.gh.comments[<n>]` printing
  `https://github.com/<repo>/issues/<n>#issuecomment-<k>`, k from 1."""
  routes = routes or {}

  def api(args, cwd, token=None):
    ep = world.gh.endpoint_of(args)
    return world.gh.ok(routes[ep]) if ep in routes else world.gh.do_api(args)

  def issue(args, cwd, token=None):
    if args[1] == "edit" and "--add-label" in args:
      label = args[args.index("--add-label") + 1]
      assert label in world.gh.labels, label
      world.gh.issues[int(args[2])]["labels"].append(label)
      return world.gh.ok(text="")
    if args[1] != "comment":
      return world.gh.do_issue(args)
    n, k = int(args[2]), 1 + sum(len(c) for c in world.gh.comments.values())
    world.gh.comments.setdefault(n, []).append(
        {"id": k, "body": Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8")})
    return world.gh.ok(text=f"https://github.com/{REPO}/issues/{n}#issuecomment-{k}\n")

  world.gh.extend("api", api)
  world.gh.extend("issue", issue)


def wave_store(world, **units):
  """After `apply` (issues #2.. in blocked-by order, the labels): state.json as `status --wait` saves it
  (U09b's `status.units[<id>]` keys; `units[<id>].pr.number` as `status` records the watched PR),
  one foreman and launches file per unit."""
  applied(world)
  fake_gh(world)
  s = store(world.repo)
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"] = {"units": {}, "ready": [u for u, v in units.items() if v.get("ready")], "landed": []}
  for uid, u in units.items():
    state["units"][uid]["launched"] = {"at": "2026-11-03T00:00:00Z"} if u.get("launched", True) else None
    if u.get("pr"):
      state["units"][uid]["pr"] = {"number": u["pr"]}
    state["status"]["units"][uid] = {"pr": u.get("pr"), "head": u.get("head"), "ci": u.get("ci"),
                                     "landed": u.get("landed", False)}
    atomic_write(s.path("foreman", uid), {"dispatch_id": None, "rounds": u.get("rounds", []),
                                          "decisions": u.get("decisions", []), "rulings": u.get("rulings", [])})
    atomic_write(s.path("launches", uid), {"launches": u.get("launches", [{"round": 1, "status": "running"}])})
  atomic_write(s.path("state"), state)
  return s


def foreman_of(s, uid):
  return json.loads(s.path("foreman", uid).read_text(encoding="utf-8"))


def question(world, text=BLOCKED):
  q = world.artifacts / "q.md"
  q.write_text(text, encoding="utf-8")
  return q


# ---------------------------------------------------------------- S1: the six states, the end condition, the word table


CARD = {"opened_at": NOW, "idle": [], "heads": []}


@pytest.mark.parametrize("view,foreman,card,expected", [
  ({"ci": None, "landed": True}, {}, CARD, "landed"),
  ({"ci": "green", "landed": False}, {"stopped": {"by": "owner", "reason": "stop the unit", "at": NOW}}, CARD, "stopped"),
  ({"ci": "green", "landed": False}, {"decisions": [{"id": "q1", "point": 3}], "rulings": []}, CARD, "pending"),
  ({"ci": "green", "landed": False}, {"decisions": [{"id": "q1", "point": 3}], "rulings": [{"decision": "q1"}]}, CARD, "active"),
  ({"ci": "green", "landed": False}, {}, {**CARD, "idle": [{"unit": "U01", "reason": "launch-builder: x", "at": NOW}]}, "idle"),
  ({"ci": "pending", "head": "a" * 40, "landed": False}, {},
   {**CARD, "heads": [{"unit": "U01", "head": "a" * 40, "seen_at": NOW - 31 * 60}]}, "idle"),
  ({"ci": None, "head": "a" * 40, "landed": False}, {},
   {**CARD, "heads": [{"unit": "U01", "head": "a" * 40, "seen_at": NOW - 29 * 60}]}, "active"),
  ({"ci": "green", "landed": False}, {"rounds": [{"phase": "posted", "outcome": "clean"}]}, CARD, "clean"),
  ({"ci": "green", "landed": False}, {"rounds": [{"phase": "posted", "outcome": "revise"}]}, CARD, "active"),
])
def test_unit_state_names_one_of_six_states(view, foreman, card, expected):
  assert unit_state("U01", view, foreman, card, {"ci_wait_minutes": 30}, NOW) == expected


@pytest.mark.parametrize("states,ready,slots,expected", [
  ({"U01": "clean", "U02": "landed", "U03": "stopped", "U04": "pending", "U05": "idle"}, [], 1,
   (True, "every launched unit is clean, landed, stopped, pending or idle")),
  ({"U01": "active"}, [], 4, (False, "in flight: U01")),
  ({"U01": "clean"}, ["U02"], 5, (False, "ready, unlaunched: U02")),
  ({"U01": "pending", "U04": "active"}, ["U02"], 0, (False, "in flight: U04")),
  ({"U01": "pending"}, ["U02"], 0, (True, "no free slot for U02")),
])
def test_loop_ended_is_the_end_condition(states, ready, slots, expected):
  assert loop_ended(states, ready, slots) == expected


@pytest.mark.parametrize("word,review_exit,action", [
  ("clean", 0, "await-merge"), ("revise", 3, "launch-builder"), ("contested: f-1-2, f-1-3", 3, "decision 1"),
  ("cap-reached", 2, "decision 2"), ("target-moved", 3, "redispatch"), ("error", 3, "redispatch"),
  ("error", 5, "idle: review stalled"), ("target-moved", 5, "idle: review stalled"), ("blocked", 3, "decision 3"),
  ("recovered clean", 0, "await-merge"), ("recovered contested: f-2-1", 3, "decision 1"),
  ("recovered cap-reached", 2, "decision 2"), ("a sentence instead of a word", 3, "redispatch"),
])
def test_word_action_is_the_word_table(word, review_exit, action):
  assert word_action(word, review_exit) == action


@pytest.mark.parametrize("unit,state,why", [
  ({"ci": "green", "launches": [{"round": 1, "status": "exited 0"}],
    "decisions": [{"id": "q1", "point": 3, "source": "comment 77", "head": "a" * 40, "question": BLOCKED, "asked_at": "t"}]},
   "pending", "a decision is pending"),
  ({"ci": "green", "launches": [{"round": 1, "status": "exited 0"}],
    "rounds": [{"round": 1, "phase": "posted", "outcome": "clean", "launch": 1, "head": "a" * 40}]},
   "clean", "a round was posted since the latest launch"),
  ({"ci": "green", "launches": [{"round": 2, "status": "exited 0"}],
    "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 2, "head": "a" * 40}]},
   "active", "a relaunch is needed, not a review: the posted round names this launch"),
  ({"ci": "pending", "launches": [{"round": 1, "status": "exited 0"}]}, "active", "CI is pending"),
  ({"ci": "green", "launches": [{"round": 1, "status": "running"}]}, "active", "the latest launch is not terminal"),
])
def test_the_loop_never_reviews_what_dispatch_refuses(world, unit, state, why):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, **unit})
  fake_gh(world, {f"repos/{REPO}/pulls/70/reviews": []})  # U10's recovery read: nothing posted on the PR
  make_pr(world.gh, 70, "a" * 40, closes=[(REPO, 2)])
  green = unit["ci"] == "green"
  world.gh.check_runs["a" * 40] = [{"name": "tests", "status": "completed", "conclusion": "success"}] if green else []
  world.gh.combined["a" * 40] = {"state": "success" if green else "pending", "statuses": []}
  code, out = world.run("foreman", "dispatch", "--unit", "U01", "--runcard", card)
  assert code == 1, (why, out)
  assert "dispatch refused: " in out, (why, out)
  card_json = json.loads(s.path("runcards", card).read_text(encoding="utf-8"))
  view = json.loads(s.path("state").read_text(encoding="utf-8"))["status"]["units"]["U01"]
  assert unit_state("U01", view, foreman_of(s, "U01"), card_json, {}, NOW) == state
  assert foreman_of(s, "U01")["rounds"] == unit.get("rounds", []), "a refusal writes no round"


# ---------------------------------------------------------------- S2: the report file and the end line


def test_report_rewrites_the_wave_report_and_prints_the_end_line(world):
  card = open_wave_card(world)
  s = wave_store(world,
      U01={"pr": 70, "head": "a" * 40, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}],
           "rounds": [{"round": 1, "phase": "posted", "outcome": "clean", "launch": 1, "head": "a" * 40}]},
      U02={"pr": 71, "head": "b" * 40, "ci": "pending", "launches": [{"round": 1, "status": "running"}],
           "rounds": [{"round": 1, "phase": "posted", "outcome": "contested: f-1-2", "launch": 1, "head": "b" * 40}]},
      U03={"launched": False, "ready": True})
  code, out = world.run("report", "--runcard", card)
  assert code == 0, out
  path = s.path("wave_report", 1)
  assert out.splitlines()[0] == str(path) and path.name == "wave_1_report.md"
  assert "idle: none" in out and "pending: none" in out and "loop: continuing (in flight: U02)" in out
  text = path.read_text(encoding="utf-8")
  assert text.startswith(f"# Wave 1 report\nRun card: {card}\n")
  assert "- U01 #2: clean · pr #70 head aaaaaaa · ci green · rounds 1 (r1 posted clean) · launch 1 exited 0" in text
  assert "- U02 #3: active · pr #71 head bbbbbbb · ci pending · rounds 1 (r1 posted contested: f-1-2) · launch 1 running" in text
  assert "## Non-terminal launches\n- U02 launch 1 running" in text
  assert "## Heads with pending or absent CI\n- U02 bbbbbbb waiting-for-ci" in text
  assert "## Ready, unlaunched\n- U03 (slot free)" in text
  assert "## Stopped\n- none" in text
  assert not any(c[0] in ("api", "pr", "issue") for c in world.gh.calls), "report reads the store only"
  assert world.run("report", "--runcard", card)[0] == 0
  assert path.read_text(encoding="utf-8").count("# Wave 1 report") == 1, "rewritten, not appended"
  card2 = open_wave_card(world)  # a re-typed wave is the next wave number
  assert world.run("report", "--runcard", card2)[0] == 0 and s.path("wave_report", 2).is_file()
  code, out = world.run("report", "--runcard", "no-such-card")
  assert code == 1 and out.startswith("superegm: runcard: ")  # U03's main prefixes every HandoffError
