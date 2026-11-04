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
  assert world.run("decision", "rule", "--unit", "U01", "--decision", q2, "--ruling", ruling, "--by", "judges:j-1", "--runcard", card)[0] == 0
  assert f"Ruling (judges j-1, leavemealone): U01 {q2} {ruling}" in s.path("journal").read_text(encoding="utf-8")
