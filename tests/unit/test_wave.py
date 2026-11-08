# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U10b's tests of the driver: report, decision open|rule, the wave skill body.

"""U10b: the pure functions the wave skill cites, `report`, `decision open|rule` and the skill body.
Fixtures: conftest's `world`, `applied` and `make_pr` (U03/U07)."""
import hashlib
import json
from pathlib import Path
import pytest
from conftest import applied, make_pr, set_config
import superegm  # the harness reloads the package per test: read load_config at call time
from superegm import store, atomic_write, DEFAULT_CONFIG, decision, launch
from test_builder_token import APP
from superegm.report import unit_state, unit_view, loop_ended, word_action
from superegm.apply import board_changed_at, splice_board
from test_builders import seed as filed, launched, foreman as foreman_file

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
  assert unit_state("U01", view, foreman, [], card, {"ci_wait_minutes": 30}, NOW) == expected


@pytest.mark.parametrize("view, card, expected", [
  ({"ci": None, "head": None, "landed": False, "launched": False, "ready": True}, CARD, "ready"),
  ({"ci": None, "head": None, "landed": False, "launched": False, "ready": True},
   {**CARD, "idle": [{"unit": "U02", "reason": "launch-builder: no token", "at": NOW}]}, "idle"),
  ({"ci": None, "head": None, "landed": False, "launched": False, "ready": False}, CARD, "waiting"),
  ({"ci": None, "head": None, "landed": True, "launched": False, "ready": False}, CARD, "landed"),
  ({"ci": "green", "head": "a" * 40, "landed": False, "launched": True, "ready": False}, CARD, "active")])
def test_unit_state_names_ready_and_waiting_for_an_unlaunched_unit(view, card, expected):
  assert unit_state("U02", view, {}, [], card, {"ci_wait_minutes": 30}, NOW) == expected
  state = {"units": {"U02": {"launched": None}}, "status": {"ready": ["U02"], "units": {"U02": {"pr": None, "head": None, "ci": None, "landed": False}}}}
  assert unit_view(state, "U02") == {"pr": None, "head": None, "ci": None, "landed": False, "launched": False, "ready": True}


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
  ("owner: f-1-2", 3, "decision open"),
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
  assert unit_state("U01", view, foreman_of(s, "U01"), launch.load_launches(s, "U01"), card_json, {}, NOW) == state
  assert foreman_of(s, "U01")["rounds"] == unit.get("rounds", []), "a refusal writes no round"


def test_a_launch_after_a_clean_round_keeps_the_unit_active(world):
  """Defect 2: a clean verdict is bound to its launch (§11.1's predicate names the launch count); a launch
  recorded after it is in flight again, so the loop neither ends on the unit nor frees its slot."""
  card = open_wave_card(world)
  launches = [{"round": 1, "status": "exited 0"}, {"round": 2, "status": "running"}]
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "launches": launches,
                             "rounds": [{"round": 1, "phase": "posted", "outcome": "clean", "launch": 1, "head": "a" * 40}]})
  view = {"ci": "green", "landed": False}
  assert unit_state("U01", view, foreman_of(s, "U01"), launches[:1], CARD, {}, NOW) == "clean"
  assert unit_state("U01", view, foreman_of(s, "U01"), launches, CARD, {}, NOW) == "active"
  code, out = world.run("report", "--runcard", card)
  assert code == 0 and "loop: continuing (in flight: U01)" in out, out
  assert "| U01 #2 | active | r1 posted clean | 2 running | aaaaaaa | #70 | none | none | none |" in s.path("wave_report", 1).read_text(encoding="utf-8")


# ---------------------------------------------------------------- S2: the report file and the end line


def test_the_report_names_its_handoff(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  assert world.run("report", "--runcard", card)[0] == 0
  assert s.path("wave_report", 1).read_text(encoding="utf-8").startswith(f"# Wave 1 report (handoff {s.handoff_id})\n")


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
  assert text.startswith(f"# Wave 1 report (handoff {s.handoff_id})\nRun card: {card}\n")
  assert "| U01 #2 | clean | r1 posted clean | 1 exited 0 | aaaaaaa | #70 | none | await-merge | none |" in text
  assert "| U02 #3 | active | r1 posted contested: f-1-2 | 1 running | bbbbbbb | #71 | ci, U01 | decision 1 | none |" in text
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


# ---------------------------------------------------------------- S3: the CI-wait bound and `--idle`


@pytest.mark.parametrize("minutes,idle_at_31", [(None, True), (45, False)])
def test_ci_wait_minutes_bounds_the_wait_in_time(world, minutes, idle_at_31):
  cfg = world.repo / ".superegm/config.json"
  if minutes:
    cfg.write_text(json.dumps({**json.loads(cfg.read_text(encoding="utf-8")), "ci_wait_minutes": minutes}), encoding="utf-8")
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "pending"},
                 U02={"pr": 71, "head": "b" * 40, "ci": "green", **CLEAN})
  assert "idle: none" in world.run("report", "--runcard", card)[1]
  card_json = json.loads(s.path("runcards", card).read_text(encoding="utf-8"))
  assert [(h["unit"], h["head"][:7]) for h in card_json["heads"]] == [("U01", "aaaaaaa"), ("U02", "bbbbbbb")]
  world.advance(29 * 60)
  assert "idle: none" in world.run("report", "--runcard", card)[1]
  world.advance(2 * 60)
  code, out = world.run("report", "--runcard", card)
  assert ("idle: U01" in out) is idle_at_31, out
  if idle_at_31:
    assert "## Idle\n- U01: ci pending for 31 min (ci_wait_minutes 30)" in s.path("wave_report", 1).read_text(encoding="utf-8")
    assert "loop: ended" in out
  # A new head restarts the clock; the first report of a new card starts it afresh.
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"]["U01"]["head"] = "c" * 40
  atomic_write(s.path("state"), state)
  assert "idle: none" in world.run("report", "--runcard", card)[1]


def test_report_idle_names_a_launch_builder_refusal(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", **CLEAN}, U02={"launched": False, "ready": True})
  code, out = world.run("report", "--runcard", card, "--idle", "U02=launch-builder: the builder profile has plugins")
  assert code == 0 and "idle: U02" in out and "loop: ended" in out, out
  assert "## Idle\n- U02: launch-builder: the builder profile has plugins" in s.path("wave_report", 1).read_text(encoding="utf-8")
  assert "idle: U02" in world.run("report", "--runcard", card)[1], "idle persists for the invocation"
  assert "idle: none" in world.run("report", "--runcard", open_wave_card(world))[1], "and not beyond it"
  assert world.run("report", "--runcard", card, "--idle", "U09=stalled")[0] == 1, "an unknown unit"


# ---------------------------------------------------------------- S4: decision open


PRIOR = {"id": "q1", "point": 3, "source": "comment 60", "head": "a" * 40, "question": BLOCKED, "asked_at": "t"}
A = "a" * 40
HEAD = "| unit | state | round | launch | head | PR | waits on | next action | cost |"


@pytest.mark.parametrize("units, idle, row", [
  ({"U01": {"pr": 70, "head": A, "ci": "green", "launches": [{"round": 1, "status": "exited 0", "total_cost_usd": 1.5}],
            "rounds": [{"round": 1, "phase": "posted", "outcome": "clean", "launch": 1, "head": A}]}}, None,
   "| U01 #2 | clean | r1 posted clean | 1 exited 0 | aaaaaaa | #70 | none | await-merge | 1.50 |"),
  ({"U01": {"pr": 70, "head": A, "ci": "green", "launches": [{"round": 1, "status": "exited 0", "total_cost_usd": 0.5}],
            "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 1, "head": A}]}}, None,
   "| U01 #2 | active | r1 posted revise | 1 exited 0 | aaaaaaa | #70 | none | launch-builder | 0.50 |"),
  ({"U01": {"pr": 70, "head": A, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}, {"round": 2, "status": "running"}],
            "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 1, "head": A}]}}, None,
   "| U01 #2 | active | r1 posted revise | 2 running | aaaaaaa | #70 | none | none | none |"),
  ({"U01": {"pr": 70, "head": A, "ci": "green", "launches": [{"round": 1, "status": "exited 0", "total_cost_usd": 1.0},
                                                            {"round": 2, "status": "exited 137", "total_cost_usd": "unrecorded"}]}}, None,
   "| U01 #2 | active | none | 2 exited 137 | aaaaaaa | #70 | none | foreman dispatch | 1.00 (partial) |"),
  ({"U01": {"pr": 70, "head": A, "ci": "green", "launches": [{"round": 1, "status": "interrupted", "total_cost_usd": 2.0}]}}, None,
   "| U01 #2 | active | none | 1 interrupted | aaaaaaa | #70 | none | foreman dispatch | 2.00 |"),
  ({"U01": {"pr": 70, "head": A, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}],
            "rounds": [{"round": 1, "phase": "posted", "outcome": "owner: f-1-2", "launch": 1, "head": A}]}}, None,
   "| U01 #2 | active | r1 posted owner: f-1-2 | 1 exited 0 | aaaaaaa | #70 | none | decision open | none |"),
  ({"U01": {"launches": []}}, None, "| U01 #2 | active | none | none | none | none | none | foreman dispatch | none |"),
  ({"U01": {"pr": 70, "head": A, "ci": "pending"}}, None, "| U01 #2 | active | none | 1 running | aaaaaaa | #70 | ci | none | none |"),
  ({"U01": {"pr": 70, "head": A, "ci": "green", "decisions": [PRIOR]}}, None, "| U01 #2 | pending | none | 1 running | aaaaaaa | #70 | q1 | decision 3 | none |"),
  ({"U01": {"pr": 70, "head": A, "ci": "green"}}, "U01=launch-builder: no token",
   "| U01 #2 | idle | none | 1 running | aaaaaaa | #70 | none | launch-builder: no token | none |"),
  ({"U01": {"pr": 70, "head": A, "ci": None, "landed": True}}, None, "| U01 #2 | landed | none | 1 running | aaaaaaa | #70 | none | none | none |"),
  ({"U01": {"launched": False, "ready": True, "launches": []}}, None, "| U01 #2 | ready | none | none | none | none | none | launch-builder | none |"),
  ({"U01": {"pr": 70, "head": A, "ci": "green"}, "U02": {"launched": False, "launches": []}}, None,
   "| U02 #3 | waiting | none | none | none | none | U01 | none | none |")])
def test_the_board_row_per_unit(world, units, idle, row):
  card = open_wave_card(world)
  s = wave_store(world, **units)
  code, out = world.run("report", "--runcard", card, *(["--idle", idle] if idle else []))
  assert code == 0, out
  text = s.path("wave_report", 1).read_text(encoding="utf-8")
  header = (f"handoff {s.handoff_id} · base main · spec {hashlib.sha256(world.spec.read_bytes()).hexdigest()[:12]}"
            " · waves {U01} → {U02} → {U03} · changed none")
  assert f"## Units\n{header}\n{HEAD}\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n" in text
  assert row in text and row in out and out.splitlines()[0] == str(s.path("wave_report", 1)) and "- U01 #2:" not in text


BLOCK = "handoff h · base main · spec 0123456789ab · waves {U01} · changed 2026-11-03T00:00:00Z\n| unit | state |\n| --- | --- |\n| U01 #2 | ready |"
LATER = BLOCK.replace("T00:00:00Z", "T01:00:00Z")
WRAPPED = "# Build\n\ntext\n\n<!-- superegm:board -->\n" + BLOCK + "\n<!-- /superegm:board -->\n"
MOVED = WRAPPED.replace("| ready |", "| active |").replace("T00:00:00Z", "T01:00:00Z")


@pytest.mark.parametrize("body, block, expected", [
  ("# Build\n\ntext\n", BLOCK, WRAPPED), ("# Build\n\ntext", BLOCK, WRAPPED), (WRAPPED, LATER, WRAPPED),
  (WRAPPED, LATER.replace("| ready |", "| active |"), MOVED),
  (WRAPPED + "\nafter\n", LATER.replace("| ready |", "| active |"), MOVED + "\nafter\n")])
def test_splice_board_replaces_appends_or_keeps(body, block, expected):
  assert splice_board(body, block) == expected
  assert splice_board(expected, block) == expected


@pytest.mark.parametrize("orphan", ["<!-- /superegm:board -->", "<!-- superegm:board -->"])
def test_splice_board_appends_once_past_an_orphan_marker(orphan):
  body = f"# Build\n\n{orphan}\nowner text\n"
  first = splice_board(body, BLOCK)
  assert first == body + "\n<!-- superegm:board -->\n" + BLOCK + "\n<!-- /superegm:board -->\n"
  assert splice_board(first, LATER) == first
  moved = splice_board(first, LATER.replace("| ready |", "| active |"))
  assert moved.startswith(body) and "| U01 #2 | active |" in moved and moved.count("<!-- /superegm:board -->") == first.count("<!-- /superegm:board -->")


def test_splice_board_keeps_the_board_above_a_trailing_orphan_marker():
  orphan = "\n<!-- superegm:board -->\nowner note\n"
  assert splice_board(WRAPPED + orphan, LATER) == WRAPPED + orphan
  assert splice_board(WRAPPED + orphan, LATER.replace("| ready |", "| active |")) == MOVED + orphan


def test_splice_board_keeps_a_crlf_body_whose_rows_are_unchanged():
  crlf = WRAPPED.replace("\n", "\r\n")
  assert splice_board(crlf, LATER) == crlf
  assert "| U01 #2 | active |" in splice_board(crlf, LATER.replace("| ready |", "| active |"))


def test_board_changed_at_reads_the_header_time_of_the_held_board():
  assert board_changed_at(WRAPPED) == "2026-11-03T00:00:00Z"
  assert board_changed_at(WRAPPED.replace("\n", "\r\n")) == "2026-11-03T00:00:00Z"
  assert board_changed_at("# Build\n\ntext\n") is None


def test_a_board_whose_write_landed_unrecorded_gives_its_time_to_the_state(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"launched": False, "ready": True, "launches": []}, U02={"launched": False, "launches": []}, U03={"launched": False, "launches": []})
  assert world.run("status", "--runcard", card)[0] == 0
  landed = json.loads(s.path("state").read_text(encoding="utf-8"))["board_changed_at"]
  state = json.loads(s.path("state").read_text(encoding="utf-8")); state["board_changed_at"] = "2026-01-01T00:00:00Z"; atomic_write(s.path("state"), state)
  world.advance(60)
  edits = lambda: [c for c in world.gh.calls if c[:2] == ["issue", "edit"] and "--body-file" in c]
  assert world.run("status", "--runcard", card)[0] == 0 and len(edits()) == 1
  assert json.loads(s.path("state").read_text(encoding="utf-8"))["board_changed_at"] == landed


def test_the_board_names_the_latest_idle_reason(world):
  card = open_wave_card(world)
  wave_store(world, U01={"pr": 70, "head": A, "ci": "green"})
  assert world.run("report", "--runcard", card, "--idle", "U01=first reason")[0] == 0
  out = world.run("report", "--runcard", card, "--idle", "U01=second reason")[1]
  assert "| U01 #2 | idle | none | 1 running | aaaaaaa | #70 | none | second reason | none |" in out, out


def test_the_board_waits_on_a_shared_file_predecessor_and_an_open_blocking_decision(world):
  class Graph(world.ns["Graph"]):  # U03 after U01 by a shared file alone, beside its blocker U02
    def __init__(self, plan):
      super().__init__(plan)
      self.preds["U03"].add("U01")
  world.ns["Graph"] = Graph
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": A, "ci": "green"}, U02={"pr": 71, "head": A, "ci": None, "landed": True},
                 U03={"launched": False, "launches": []})
  out = world.run("report", "--runcard", card)[1]
  assert "| U03 #4 | waiting | none | none | none | none | U01 | none | none |" in out, out
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["open_blocking"] = {"U03": ["D1"]}
  atomic_write(s.path("state"), state)
  out = world.run("report", "--runcard", card)[1]
  assert "| U03 #4 | waiting | none | none | none | none | U01, U03/D1 | none | none |" in out, out


def test_the_board_escapes_its_cells(world):
  card = open_wave_card(world)
  wave_store(world, U01={"pr": 70, "head": A, "ci": "green"})
  code, out = world.run("report", "--runcard", card, "--idle", "U01=a | b\nc <!-- /superegm:board -->")
  assert code == 0, out
  board = out.split("\nidle: ")[0]
  assert "| U01 #2 | idle | none | 1 running | aaaaaaa | #70 | none | a \\| b c &lt;!-- /superegm:board --> | none |" in board
  assert "<!-- /superegm:board -->" not in board


def test_a_unit_idle_on_ci_keeps_a_steady_board_row(world):
  card = open_wave_card(world)
  wave_store(world, U01={"pr": 70, "head": A, "ci": "pending"})
  assert world.run("report", "--runcard", card)[0] == 0
  world.advance(31 * 60)
  first = world.run("report", "--runcard", card)[1]
  world.advance(5 * 60)
  later = world.run("report", "--runcard", card)[1]
  row = "| U01 #2 | idle | none | 1 running | aaaaaaa | #70 | ci | ci pending (ci_wait_minutes 30) | none |"
  assert row in first and row in later


def test_a_plain_wave_status_pass_saves_the_board_change(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"launched": False, "ready": True, "launches": []}, U02={"launched": False, "launches": []}, U03={"launched": False, "launches": []})
  assert world.run("status", "--runcard", card)[0] == 0
  edits = [c for c in world.gh.calls if c[:2] == ["issue", "edit"] and "--body-file" in c]
  changed = json.loads(s.path("state").read_text(encoding="utf-8")).get("board_changed_at")
  assert len(edits) == 1 and changed == world.ns["now_iso"]() and f" · changed {changed}\n" in world.gh.issues[1]["body"]


def test_a_wave_status_pass_writes_the_board_once_and_only_on_change(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"launched": False, "ready": True, "launches": []}, U02={"launched": False, "launches": []}, U03={"launched": False, "launches": []})
  edits = lambda: [c for c in world.gh.calls if c[:2] == ["issue", "edit"] and "--body-file" in c]
  reads = lambda: [c for c in world.gh.calls if c[:2] == ["api", f"repos/{REPO}/issues/1"]]
  changed_at = lambda: json.loads(s.path("state").read_text(encoding="utf-8")).get("board_changed_at")
  before = world.gh.issues[1]["body"]
  assert world.run("status", "--wait", 1, "--runcard", card) == (0, "deadline\n")
  body, first = world.gh.issues[1]["body"], world.ns["now_iso"]()
  assert (len(reads()), len(edits()), changed_at()) == (1, 1, first)
  assert body.startswith(before.rstrip("\n") + "\n\n<!-- superegm:board -->\nhandoff ") and body.endswith("\n<!-- /superegm:board -->\n")
  assert f" · changed {first}\n| unit | state |" in body and "| U01 #2 | ready | none | none | none | none | none | launch-builder | none |" in body
  world.advance(60)
  assert world.run("status", "--runcard", card)[0] == 0 and (len(edits()), changed_at()) == (1, first), "equal rows: no write"
  state = json.loads(s.path("state").read_text(encoding="utf-8")); state["units"]["U01"]["launched"] = {"at": "t"}; atomic_write(s.path("state"), state)
  assert world.run("status", "--wait", 1, "--runcard", card)[0] == 0 and len(edits()) == 2 and changed_at() == world.ns["now_iso"]() != first
  assert "| U01 #2 | active | none | none | none | none | none | foreman dispatch | none |" in world.gh.issues[1]["body"]
  assert world.gh.issues[1]["body"].split("<!-- superegm:board -->")[0] == body.split("<!-- superegm:board -->")[0]
  state["units"]["U02"]["launched"] = {"at": "t"}; atomic_write(s.path("state"), state)
  assert world.run("status", "--wait", 1, "--runcard", world.open_card("integrate", world.spec))[0] == 0 and len(edits()) == 2, "integrate reads"
  world.gh.extend("issue", lambda args, cwd, token=None: (1, "", "HTTP 502") if "--body-file" in args else world.gh.do_issue(args))
  assert world.run("status", "--wait", 1, "--runcard", card) == (0, "deadline\n")
  assert "board write failed" in s.path("journal").read_text(encoding="utf-8")


def test_verify_compares_the_tracking_body_outside_the_board(world):
  wave_store(world, U01={"launched": False, "ready": True, "launches": []})
  posted = world.gh.issues[1]["body"]
  world.gh.issues[1]["body"] = splice_board(posted, BLOCK)
  code, out = world.run("verify", "--spec", world.spec)
  assert code == 0 and out.startswith("verify: complete, ") and "0 problem(s)" in out, out
  world.gh.issues[1]["body"] = splice_board(posted + "\nedited by hand\n", BLOCK)
  code, out = world.run("verify", "--spec", world.spec)
  assert code == 1 and "MISMATCH body of #1 (tracking) differs from the rendered body" in out, out


@pytest.mark.parametrize("point,source,decisions,rulings,expect", [
  (1, "review head-U01-c1 round 2", [], [], "options: finding upheld; finding overruled"),
  (2, "review head-U01-c1 cap", [], [], "options: one more round; stop"),
  (3, "comment 77", [], [], "options: (a) use the in-memory queue; (b) use Redis; stop the unit"),
  (3, "launch 2", [], [], "options: relaunch; stop the unit"),
  (3, "closed 70", [PRIOR], [{"decision": "q1", "ruling": "relaunch", "by": "owner", "posted_at": "t"}],
   "ruled: stop the unit (relaunch already used)"),
  (3, "comment 79", [PRIOR, {**PRIOR, "id": "q2", "source": "comment 70"}],
   [{"decision": "q1", "ruling": "(a)", "by": "owner", "posted_at": "t"}, {"decision": "q2", "ruling": "(a)", "by": "owner", "posted_at": "t"}],
   "options: relaunch; stop the unit"),
  (3, "comment 79", [PRIOR, {**PRIOR, "id": "q2", "head": "b" * 40}],
   [{"decision": "q1", "ruling": "(a)", "by": "owner", "posted_at": "t"}, {"decision": "q2", "ruling": "(a)", "by": "owner", "posted_at": "t"}],
   "options: (a) use the in-memory queue; (b) use Redis; stop the unit"),
])
def test_decision_open_records_the_question_and_prints_its_options(world, point, source, decisions, rulings, expect):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "decisions": decisions, "rulings": rulings})
  q = question(world, BLOCKED if source.startswith("comment") else "rounds: 5 -> 3 -> 2\n")
  argv = ["decision", "open", "--unit", "U01", "--point", point, "--question", q, "--source", source, "--runcard", card]
  code, out = world.run(*argv)
  assert code == 0, out
  qid, line2 = out.splitlines()[:2]
  assert qid == f"q{len(decisions) + 1}" and line2 == expect
  f = foreman_of(s, "U01")
  d = f["decisions"][-1]
  assert (d["id"], d["point"], d["source"], d["head"], d["question"]) == (qid, point, source, "a" * 40, q.read_text(encoding="utf-8"))
  assert d["asked_at"]
  if expect.startswith("ruled"):
    assert f["rulings"][-1] == {"decision": qid, "ruling": "stop the unit", "by": "superegm",
                                "reason": "relaunch already used", "posted": None, "posted_at": f["rulings"][-1]["posted_at"]}
    assert f["stopped"]["reason"] == "stop the unit" and "superegm:stopped" in world.gh.issues[2]["labels"]
  else:
    code, out = world.run(*argv)
    assert code == 1 and out == f"decision: U01 has a pending decision {qid}\n"
  assert f"Decision {qid} (point {point}, {source}): U01" in s.path("journal").read_text(encoding="utf-8")


# ---------------------------------------------------------------- S5: decision rule


def test_point_1_takes_one_ruling_per_contested_finding(world):
  """1.1.3 fix (wave-0021, U18 round 4): a point-1 decision carries every contested finding of the round, and the
  leavemealone row rules them one call per finding; only a second ruling on the same finding is refused."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  qid = world.run("decision", "open", "--unit", "U01", "--point", 1, "--question", question(world),
                  "--source", "review head-U01-c1 round 4", "--runcard", card)[1].splitlines()[0]
  rule = lambda ruling: world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", ruling, "--by", "judges:p-1", "--runcard", card)
  assert rule("f-4-1 finding upheld")[0] == 0
  assert rule("f-4-2 finding overruled — the plan says so")[0] == 0
  assert rule("f-4-1 finding overruled — changed my mind") == (1, f"decision: {qid} already ruled\n")
  rulings = foreman_of(s, "U01")["rulings"]
  assert [r["ruling"] for r in rulings if r["decision"] == qid] == ["f-4-1 finding upheld", "f-4-2 finding overruled — the plan says so"]
  assert len(world.gh.comments[2]) == 2, "one **Ruling:** comment per finding, none for the refusal"


@pytest.mark.parametrize("point,source,ruling,posted", [
  (1, "review head-U01-c1 round 2", "f-2-1 finding overruled — the test already covers it",
   "**Ruling:** f-2-1 finding overruled — the test already covers it"),
  (1, "review head-U01-c1 round 2", "f-2-1 finding upheld", "**Ruling:** f-2-1 finding upheld (fix it)"),
  (2, "review head-U01-c1 cap", "one more round", "**Ruling:** (cap) one more round"),
  (3, "comment 77", "(b) — Redis is already a dependency", "**Ruling:** (77) use Redis — Redis is already a dependency"),
])
def test_decision_rule_records_posts_and_journals(world, point, source, ruling, posted):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  q = question(world)
  qid = world.run("decision", "open", "--unit", "U01", "--point", point, "--question", q, "--source", source,
                  "--runcard", card)[1].splitlines()[0]
  rule = lambda *extra: world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", ruling,
                                  "--by", "owner", "--runcard", card, *extra)
  code, out = rule()
  assert code == 0 and out.strip() == f"https://github.com/{REPO}/issues/2#issuecomment-1", out
  comment = world.gh.comments[2][-1]
  assert comment["body"].startswith(posted + "\n") and (point != 3 or "Which queue?" in comment["body"])
  r = foreman_of(s, "U01")["rulings"][-1]
  assert (r["decision"], r["ruling"], r["by"], r["posted"]) == (qid, ruling, "owner", "comment 1") and r["posted_at"]
  assert f"Ruling (owner): U01 {qid} {ruling}" in s.path("journal").read_text(encoding="utf-8")
  code, out = rule()
  assert code == 1 and out == f"decision: {qid} already ruled\n"
  assert len(world.gh.comments[2]) == 1, "a refusal posts nothing"
  code, out = world.run("decision", "rule", "--unit", "U01", "--decision", "q9", "--ruling", ruling, "--by", "owner", "--runcard", card)
  assert code == 1 and out == "decision: U01 has no decision q9\n"
  q2 = world.run("decision", "open", "--unit", "U01", "--point", point, "--question", q, "--source", source,
                 "--runcard", card)[1].splitlines()[0]
  code, out = world.run("decision", "rule", "--unit", "U01", "--decision", q2, "--ruling", "(z) nonsense", "--by", "owner", "--runcard", card)
  assert code == 1 and out.startswith("decision: ruling is none of the options:")
  assert out.rstrip("\n").endswith("; redesign — <one sentence why>") == (point in (1, 2)), "a head's third ruling is named at points 1 and 2 only"
  assert world.run("decision", "rule", "--unit", "U01", "--decision", q2, "--ruling", "f-2-1", "--by", "owner", "--runcard", card)[0] == 1, \
      "a finding id alone names no option"
  assert world.run("decision", "rule", "--unit", "U01", "--decision", q2, "--ruling", ruling, "--by", "judges:j-1", "--runcard", card)[0] == 0
  assert f"Ruling (judges j-1, leavemealone): U01 {q2} {ruling}" in s.path("journal").read_text(encoding="utf-8")


# ---------------------------------------------------------------- S6: a stop ruling and the report's stopped line


def test_a_stop_ruling_labels_the_issue_and_the_report_lists_unlanded_dependants(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"}, U02={"launched": False}, U03={"launched": False})
  atomic_write(s.path("handoff_units"), {"order": ["U01", "U02", "U03"], "units": {
      "U01": {"blockers": []}, "U02": {"blockers": ["U01"]}, "U03": {"blockers": ["U02"]}}})
  qid = world.run("decision", "open", "--unit", "U01", "--point", 3, "--question", question(world), "--source", "launch 1",
                  "--runcard", card)[1].splitlines()[0]
  code, out = world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", "stop the unit", "--by", "owner", "--runcard", card)
  assert code == 0, out
  f = foreman_of(s, "U01")
  assert f["stopped"] == {"by": "owner", "reason": "stop the unit", "at": f["rulings"][-1]["posted_at"]}
  assert "superegm:stopped" in world.gh.issues[2]["labels"]
  assert world.gh.comments[2][-1]["body"].startswith("**Ruling:** (launch 1) stop the unit\n")
  code, out = world.run("report", "--runcard", card)
  assert "loop: ended" in out and "pending: none" in out
  assert "## Stopped\n- U01 (owner: stop the unit): unlanded dependants U02, U03" in s.path("wave_report", 1).read_text(encoding="utf-8")
  assert "| U01 #2 | stopped | none | 1 running | aaaaaaa | #70 | none | none | none |" in s.path("wave_report", 1).read_text(encoding="utf-8")


# ---------------------------------------------------------------- S7: the by-hand ruling and the owner's close


@pytest.mark.parametrize("app", [False, True])
def test_a_by_hand_ruling_naming_the_blocked_comment_rules_its_decision(world, monkeypatch, app):
  card = open_wave_card(world)
  if app:  # the App path: the login is derived from the config, no token, no `user` route
    set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"], builder={**DEFAULT_CONFIG["builder"], "app": APP})
    monkeypatch.delenv("SUPEREGM_BUILDER_TOKEN", raising=False)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  login = "superegm-builder[bot]" if app else BUILDER
  app or monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "builder-token")  # config.builder.gh_token_env, U03's default
  fake_gh(world, {**({} if app else {"user": {"login": BUILDER}}), **{f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": author}, "body": body}
                  for cid, author, body in ((78, "owner", "**Ruling:** (77) (b) use Redis — fine\n"),
                                            (79, login, "**Ruling:** (77) (a) — I decided\n"),
                                            (80, "owner", "**Ruling:** (12) (a) — another comment\n"))}})
  assert decision.builder_login(superegm.load_config(world.repo)) == login and launch.app_login(superegm.load_config(world.repo)) == (login if app else None)
  qid = world.run("decision", "open", "--unit", "U01", "--point", 3, "--question", question(world), "--source", "comment 77",
                  "--runcard", card)[1].splitlines()[0]
  rule = lambda posted, by="owner": world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", "(b)",
                                              "--by", by, "--posted", posted, "--runcard", card)
  code, out = rule("79", login)
  assert code == 1 and out == f"decision: comment 79 was written by the builder account {login} and is not honoured\n"
  code, out = rule("80")
  assert code == 1 and out == "decision: comment 80 does not name comment 77\n"
  code, out = rule("78", "someone")
  assert code == 1 and out == "decision: comment 78 was written by owner, not someone\n"
  assert foreman_of(s, "U01")["rulings"] == []
  code, out = rule("78")
  assert code == 0 and out.strip() == "recorded (comment 78)"
  r = foreman_of(s, "U01")["rulings"][-1]
  assert (r["decision"], r["ruling"], r["by"], r["posted"]) == (qid, "(b)", "owner", "comment 78")
  assert 2 not in world.gh.comments, "nothing is posted for a by-hand ruling"
  assert "pending: none" in world.run("report", "--runcard", card)[1]


def test_the_owners_close_is_stop_without_a_question(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  code, out = world.run("decision", "rule", "--unit", "U01", "--ruling", "stop the unit", "--by", "owner", "--posted", "closed:70", "--runcard", card)
  assert code == 0 and out.strip() == "recorded (closed #70)", out
  f = foreman_of(s, "U01")
  assert f["decisions"] == [] and f["rulings"] == [] and f["stopped"]["reason"] == "closed #70 by owner"
  assert "superegm:stopped" in world.gh.issues[2]["labels"] and 2 not in world.gh.comments
  assert "- U01 (owner: closed #70 by owner): unlanded dependants" in (world.run("report", "--runcard", card), s.path("wave_report", 1).read_text(encoding="utf-8"))[1]
  code, out = world.run("decision", "rule", "--unit", "U01", "--ruling", "stop the unit", "--by", "owner", "--runcard", card)
  assert code == 1 and out == "decision: --decision is required unless --posted closed:<n>\n"


# ---------------------------------------------------------------- S8: a re-typed wave resumes from the store


def test_a_retyped_wave_raises_every_pending_decision_before_its_first_batch(world):
  card1 = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"},
                 U02={"pr": 71, "head": "b" * 40, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}],
                      "rounds": [{"round": 1, "phase": "collected", "outcome": "not run (error: fetch failed)", "launch": 1, "head": "b" * 40}]})
  qid = world.run("decision", "open", "--unit", "U01", "--point", 3, "--question", question(world), "--source", "comment 77",
                  "--runcard", card1)[1].splitlines()[0]
  card2 = open_wave_card(world)  # the re-typed wave; card1 is interrupted (section 6)
  code, out = world.run("report", "--runcard", card2)
  assert code == 0 and f"pending: U01 {qid} (point 3, comment 77)" in out and "loop: continuing (in flight: U02)" in out, out
  assert f"## Pending decisions\n- U01 {qid} (point 3, comment 77): Which queue?" in s.path("wave_report", 2).read_text(encoding="utf-8")
  assert world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", "(a)", "--by", "owner", "--runcard", card2)[0] == 0
  code, out = world.run("report", "--runcard", card2)
  assert "pending: none" in out and "loop: continuing (in flight: U01, U02)" in out
  assert world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", "(a)", "--by", "owner", "--runcard", card2)[0] == 1
  assert world.run("report", "--runcard", card1)[0] == 1, "an interrupted card is not open"


# ---------------------------------------------------------------- S9: the skill body


def test_the_wave_skill_body_is_the_driver_loop(world):
  text = SKILL.read_text(encoding="utf-8")
  body = text.split("---", 2)[2]
  assert len(body.encode("utf-8")) <= 24_000
  assert "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first." in body
  for heading in ("## Entry: resume from the store", "## A batch", "## The word table", "### Decision point 1",
                  "### Decision point 2", "### Decision point 3", "## Stops and by-hand rulings", "## Retries", "## The end"):
    assert heading in body, heading
  assert body.count("Leavemealone-mode: U11 wires §13.2 here.") == 3
  for order in ("1. `landed`", "2. `closed`", "3. `exit` and `status`", "4. `superegm foreman dispatch`", "5. `superegm launch`",
                "6. `superegm report`"):
    assert order in body, order
  for cited in ("unit_state", "loop_ended", "word_action", "recovered", "ci_wait_minutes", "--idle", "--posted closed:",
                "status --wait", "launch-builder", "record-launch", "review settle", "review rule", "review status",
                "runcard open --skill wave", "runcard close", "decision open", "decision rule", "in one message"):
    assert cited in body, cited
  for sub in ("report", "decision", "status", "launch", "launch-builder", "record-launch", "foreman", "review", "runcard"):
    assert world.run(sub, "--help")[0] == 0, sub


@pytest.mark.parametrize("needle", ["`<!-- superegm:board -->`", "the tracking issue's body", "none when the rows are unchanged",
                                    "the inbox stays the action list", "read the card's handoff alone", "report path, the board, `idle:`",
                                    "- `owner: <ids>` → `decision open`", "the plan and the spec"])
def test_the_wave_skill_names_the_board(needle):
  body = SKILL.read_text(encoding="utf-8").split("---", 2)[2]
  assert needle in body, needle
  assert len(body.encode("utf-8")) <= 24_000


def test_the_wave_entry_refreshes_the_snapshot_before_report():
  """Defect 5: `report` reads the snapshot only `status --wait` saves (§11.1: a re-typed wave resumes from the
  store); the entry refreshes it, with the batch's timeout, and handles its lines before `report`."""
  entry = SKILL.read_text(encoding="utf-8").split("## Entry: resume from the store", 1)[1].split("## A batch", 1)[0]
  assert entry.index("status --wait 1 --runcard '<CARD>'") < entry.index("report --runcard '<CARD>'")
  assert "run_in_background: true" in entry and "1,800,000" in entry and "steps 1–3" in entry


@pytest.mark.parametrize("removed", [
  "Codex", "ChatGPT", "Astra `inspect`", "claudex", "defer", "--published", "--watch", "--confirm-landed", "Candidate PR",
  "wave_<n>_plan.md", "foreman_<id>_state.json", "egm-handoff", "**`Panel`**", "astra_lane", "review_panels",
  "marking a PR ready", "head-moved", "merge locally", "egm/<handoff-id>", "`--wait 1500`", "two consecutive `deadline`s",
  "--not-run <reason>", "ask the user whether to re-review", "max 1 re-audit", "Blocker or Major"])
def test_the_wave_skill_names_no_removed_mechanism(removed):
  assert removed not in SKILL.read_text(encoding="utf-8"), removed


# ---------------------------------------------------------------- U18: the redesign ruling

FINDING = "change-review-1-1 | high | src/x.py:3 | regression: no | the retry loop never backs off"


@pytest.mark.parametrize("point, source", [(1, "review head-U01-c1 round 1"), (2, "review head-U01-c1 cap")])
def test_a_redesign_ruling_stops_the_unit_and_writes_the_brainstorm_brief(world, point, source):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 1}]})
  folder = s.path("review", "U01", 70) / "r1"
  atomic_write(folder / "diff", b"diff --git a/src/x.py b/src/x.py\n" + (b"+" + b"x" * 200 + b"\n") * 300)
  atomic_write(folder / "comments.md", "builder: builder-bot\n### issue #2 comment 5 by builder-bot at t\n**Deviation (other):** renamed a fixture\n\n")
  qid = world.run("decision", "open", "--unit", "U01", "--point", point, "--question", question(world, FINDING + "\n"), "--source", source, "--runcard", card)[1].splitlines()[0]
  rule = lambda text: world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", text, "--by", "owner", "--runcard", card)
  assert rule("redesign") == (1, "decision: redesign needs — <one sentence why>\n") and rule("redesign — the retry design is wrong")[0] == 0
  f, brief = foreman_of(s, "U01"), s.path("foreman", "U01").with_name(f"U01-{qid}.brainstorm.md")
  assert f["stopped"] == {"by": "owner", "reason": "redesign — the retry design is wrong", "at": f["rulings"][-1]["posted_at"], "brief": str(brief)}
  assert "superegm:stopped" in world.gh.issues[2]["labels"]
  assert world.gh.comments[2][-1]["body"].startswith(f"**Ruling:** redesign — the retry design is wrong\n\nStopped for redesign; the brainstorm brief is `{brief}`.\n")
  assert world.gh.comments[2][-1]["body"].splitlines()[3:] == ["Close this issue by hand once the re-planned unit is filed.", "", "> " + FINDING]
  text = brief.read_text(encoding="utf-8")
  assert [l for l in text.splitlines() if l.startswith("# ")] == ["# What the owner asked", "# Findings", "# Unit body", "# Diff", "# Deviations"]
  assert "redesign — the retry design is wrong" in text and FINDING in text and "<!-- superegm:handoff=" in text
  assert "src/x.py" in text and sum(l.startswith("+x") for l in text.splitlines()) == 199 and "**Deviation (other):** renamed a fixture" in text
  assert not any(c[:2] == ["api", f"repos/{REPO}/pulls/70"] for c in world.gh.calls)


def test_the_report_names_a_redesign_units_brief(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"}, U02={"launched": False})
  atomic_write(s.path("handoff_units"), {"order": ["U01", "U02"], "units": {"U01": {"blockers": []}, "U02": {"blockers": ["U01"]}}})
  data = foreman_of(s, "U01"); data["stopped"] = {"by": "owner", "reason": "redesign — why", "at": "t", "brief": "/store/foreman/U01-q1.brainstorm.md"}
  atomic_write(s.path("foreman", "U01"), data)
  assert world.run("report", "--runcard", card)[0] == 0
  assert "## Stopped\n- U01 (owner: redesign — why): unlanded dependants U02; brief /store/foreman/U01-q1.brainstorm.md" in s.path("wave_report", 1).read_text(encoding="utf-8")


def test_a_refused_redesign_ruling_leaves_no_brief_and_a_small_diff_is_copied_whole(world, monkeypatch):
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "builder-token")
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 1}]})
  folder = s.path("review", "U01", 70) / "r1"
  # 300 lines of invalid UTF-8: 13.5 KB on disk, 40.5 KB if re-encoded after `errors="replace"`: under 40 KB on disk, so copied whole
  atomic_write(folder / "diff", b"diff --git a/src/x.py b/src/x.py\n" + (b"+" + b"\xff" * 45 + b"\n") * 300)
  qid = world.run("decision", "open", "--unit", "U01", "--point", 2, "--question", question(world, FINDING + "\n"),
                  "--source", "review head-U01-c1 cap", "--runcard", card)[1].splitlines()[0]
  brief = s.path("foreman", "U01").with_name(f"U01-{qid}.brainstorm.md")
  fake_gh(world, {"user": {"login": BUILDER}, f"repos/{REPO}/issues/comments/9": {"id": 9, "user": {"login": "someone"}, "body": "**Ruling:** (cap) redesign — why\n"}})
  rule = lambda *more: world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", "redesign — why", "--by", "owner",
                                 *more, "--runcard", card)
  assert rule("--posted", "9") == (1, "decision: comment 9 was written by someone, not owner\n")
  assert not brief.exists() and "stopped" not in foreman_of(s, "U01") and foreman_of(s, "U01")["rulings"] == []
  assert "Brainstorm brief" not in s.path("journal").read_text(encoding="utf-8")
  assert rule()[0] == 0
  text = brief.read_text(encoding="utf-8")
  assert sum(l.startswith("+�") for l in text.splitlines()) == 300
  assert text.split("# Deviations")[1].strip() == "(none)"  # no comments.md for the round


def test_a_brief_with_no_posted_round_names_no_diff_and_no_deviations(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  qid = world.run("decision", "open", "--unit", "U01", "--point", 2, "--question", question(world, FINDING + "\n"),
                  "--source", "review head-U01-c1 cap", "--runcard", card)[1].splitlines()[0]
  assert world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", "redesign — why", "--by", "owner", "--runcard", card)[0] == 0
  text = s.path("foreman", "U01").with_name(f"U01-{qid}.brainstorm.md").read_text(encoding="utf-8")
  assert text.split("# Diff")[1].split("# Deviations")[0].split() == ["(none)", "```diff", "```"]
  assert text.split("# Deviations")[1].strip() == "(none)"


def test_a_by_hand_redesign_ruling_stops_the_unit_and_posts_nothing(world, monkeypatch):
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "builder-token")
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 1}]})
  qid = world.run("decision", "open", "--unit", "U01", "--point", 2, "--question", question(world, FINDING + "\n"),
                  "--source", "review head-U01-c1 cap", "--runcard", card)[1].splitlines()[0]
  fake_gh(world, {"user": {"login": BUILDER}, f"repos/{REPO}/issues/comments/9": {"id": 9, "user": {"login": "owner"}, "body": "**Ruling:** (cap) redesign — why\n"}})
  code, out = world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", "redesign — why", "--by", "owner", "--posted", "9", "--runcard", card)
  brief = s.path("foreman", "U01").with_name(f"U01-{qid}.brainstorm.md")
  assert (code, out) == (0, "recorded (comment 9)\n"), out
  assert brief.is_file() and foreman_of(s, "U01")["stopped"]["brief"] == str(brief) and world.gh.comments.get(2, []) == []


def test_launch_marks_a_unit_whose_clean_outcome_an_ingest_rewrote(world, monkeypatch):
  s, card, hid, _ = filed(world, units=("U07", "U08"), max_in_flight=1)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07" in world.run("launch", "--runcard", card)[1]
  launched(s, "U07", "exited 0")
  entry = {"round": 1, "launch": 1, "head": "a" * 40, "phase": "posted", "outcome": "revise"}
  foreman_file(s, "U07", [{**entry, "rewritten_from": "clean"}])
  one = [{"round": 1, "status": "exited 0"}]
  assert launch.ready_again(foreman_of(s, "U07"), one) and not launch.ready_again({"rounds": [entry]}, one) and not launch.ready_again(foreman_of(s, "U07"), one + [{"round": 2}])
  assert not launch.ready_again({"rounds": [{**entry, "outcome": "cap-reached", "rewritten_from": "clean"}]}, one)
  code, out = world.run("launch", "--runcard", card)
  assert "in flight: none" in out and "marked: U07" in out, out
  launched(s, "U07", "running", rnd=2)
  assert "in flight: U07" in world.run("launch", "--runcard", card)[1]


def test_an_idle_unit_an_ingest_rewrote_is_not_marked_again(world, monkeypatch):
  s, card, hid, _ = filed(world, units=("U07", "U08"), max_in_flight=1)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07" in world.run("launch", "--runcard", card)[1]
  launched(s, "U07", "exited 0")
  foreman_file(s, "U07", [{"round": 1, "launch": 1, "head": "a" * 40, "phase": "posted", "outcome": "revise", "rewritten_from": "clean"}])
  code, out = world.run("launch", "--idle", "U07", "--runcard", card)
  assert "marked: U07" not in out, out


ROOT = SKILL.parents[2]
INGEST_PROSE = [("skills/wave/SKILL.md", n) for n in ("3b. `superegm review ingest`", "awaiting-merge units included, stopped units excluded", "`0 ingested` before its first posted round",
  "`outcome: revise`", "never `launch-builder` here", "`outcome: cap-reached` → Decision point 2",
  "for every unit with an open PR", "Before the close, run batch step 3b once and `report` again",
  "Exit 1: report the unit and the refusal line in chat", "(never a landed unit)", "clear on the next batch's retry",
  "repeat until the owner resolves them by hand", "`header present on` and a `review ingest: comment:<n>:` scan refusal")] + [
                ("resources/review_panels.md", "`external:<login>`"), ("resources/review_panels.md", "`review ingest`")]


@pytest.mark.parametrize("path, needle", INGEST_PROSE)
def test_the_batch_ingest_step_and_the_external_reviewer_id_prose(path, needle):
  assert needle in (ROOT / path).read_text(encoding="utf-8"), (path, needle)
