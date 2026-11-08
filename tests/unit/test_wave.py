# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U10b's tests of the driver: report, decision open|rule, the wave skill body; the by-hand ruling read through `ruling_of` (U22).

"""U10b: the pure functions the wave skill cites, `report`, `decision open|rule` and the skill body.
Fixtures: conftest's `world`, `applied` and `make_pr` (U03/U07)."""
import json
from pathlib import Path
import pytest
from conftest import applied, make_pr, set_config
import superegm  # the harness reloads the package per test: read load_config at call time
from superegm import store, atomic_write, DEFAULT_CONFIG, decision, launch
from test_builder_token import APP
from superegm.report import unit_state, loop_ended, word_action
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
  assert "- U01 #2: active · pr #70 head aaaaaaa · ci green · rounds 1 (r1 posted clean) · launch 2 running" in s.path("wave_report", 1).read_text(encoding="utf-8")


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
  (2, "review head-U01-c1 cap", "one more round", "**Ruling:** one more round"),
  (3, "comment 77", "(b) — Redis is already a dependency", "**Ruling:** (77) use Redis — Redis is already a dependency"),
  (3, "comment 77", "(b)", "**Ruling:** (77) use Redis — ruled in the session"),
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
  assert world.gh.comments[2][-1]["body"].startswith("**Ruling:** (q1) stop the unit — ruled in the session\n")
  code, out = world.run("report", "--runcard", card)
  assert "loop: ended" in out and "pending: none" in out
  assert "## Stopped\n- U01 (owner: stop the unit): unlanded dependants U02, U03" in s.path("wave_report", 1).read_text(encoding="utf-8")
  assert "- U01 #2: stopped ·" in s.path("wave_report", 1).read_text(encoding="utf-8")


# ---------------------------------------------------------------- S7: the by-hand ruling and the owner's close


def test_a_by_hand_ruling_naming_the_blocked_comment_rules_its_decision(world):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"], owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": author}, "body": body} for cid, author, body in (
      (78, "owner", "**Ruling:** (77) (b) use Redis — fine\n"), (79, BUILDER, "**Ruling:** (77) (a) — I decided\n"),
      (80, "owner", "**Ruling:** (12) (a) — other\n"), (81, "owner", "**Ruling:** (77) (b) use Redis\n"), (82, "owner", "**Ruling:** (77) (a) — late\n"),
      (83, "owner", "**Ruling:** f-4-1 finding upheld\n"), (84, "owner", "**Ruling:** f-4-2 finding overruled — the plan says so\n"), (85, "owner", "**Ruling:** f-4-1 finding overruled — again\n"))})
  qid = world.run("decision", "open", "--unit", "U01", "--point", 3, "--question", question(world), "--source", "comment 77", "--runcard", card)[1].splitlines()[0]
  rule = lambda posted, by="owner", ruling="(b)", d=("--decision", qid): world.run("decision", "rule", "--unit", "U01", *d, "--ruling", ruling, "--by", by, "--posted", posted, "--runcard", card)
  assert rule("79", BUILDER) == (1, f"decision: comment 79 by {BUILDER} is not an owner's ruling\n")
  assert rule("81") == (1, "decision: comment 81 by owner is not an owner's ruling\n")
  assert rule("80") == (1, "decision: comment 80 does not name comment 77\n")
  assert rule("78", "someone") == (1, "decision: comment 78 was written by owner, not someone\n")
  assert rule("78") == (0, "recorded (comment 78)\n")
  r = foreman_of(s, "U01")["rulings"][-1]
  assert (r["decision"], r["ruling"], r["by"], r["posted"]) == (qid, "(b)", "owner", "comment 78") and 2 not in world.gh.comments
  assert rule("78") == (1, "decision: comment 78 already recorded (ruling edited after record, ignored)\n")
  assert rule("82") == (1, f"decision: {qid} already ruled\n")
  journal = s.path("journal").read_text(encoding="utf-8")
  assert f"Ruling (owner, comment 78): U01 {qid} option 77" in journal and f"Ruling (owner, comment 78): U01 {qid} ruling edited after record, ignored" in journal
  assert f"ruling dropped (owner, comment 82): {qid} already ruled" in journal
  world.run("decision", "open", "--unit", "U01", "--point", 1, "--question", question(world), "--source", "round 4", "--runcard", card)
  assert rule("83", "owner", "f-4-1 finding upheld", ())[0] == 0 and rule("84", "owner", "f-4-2 finding overruled — the plan says so", ()) == (0, "recorded (comment 84)\n")
  assert rule("85", "owner", "f-4-1 finding overruled — again", ()) == (1, "decision: comment 85 does not name an open decision\n")
  q2 = world.run("decision", "open", "--unit", "U01", "--point", 2, "--question", question(world, "cap\n"), "--source", "review head-U01-c1 cap", "--runcard", card)[1].splitlines()[0]
  assert world.run("decision", "rule", "--unit", "U01", "--decision", q2, "--ruling", "stop", "--by", "judges:p-1", "--runcard", card)[0] == 0
  assert world.gh.comments[2][-1]["body"].splitlines()[:2] == ["**Ruling:** stop", "(judges p-1, leavemealone)"]


def test_a_by_hand_ruling_records_the_comments_own_ruling_on_its_own_issue(world):
  """Round 2 (PR #96 review): without `--decision`, points 2 and 3 found by the comment's form; a `--ruling` other
  than the comment's refused; a comment on another issue refused; a point-1 fid matched to the decision naming it."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"], owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "owner"}, "body": body,
                                                          "issue_url": f"https://api.github.com/repos/{REPO}/issues/{n}"} for cid, n, body in (
      (90, 2, "**Ruling:** one more round\n"), (91, 9, "**Ruling:** stop\n"), (92, 2, "**Ruling:** (q1) relaunch — again\n"),
      (93, 2, "**Ruling:** f-1-1 finding overruled — x\n"), (94, 2, "**Ruling:** f-2-1 finding overruled — y\n"), (95, 2, "**Ruling:** f-2-1 finding overruled — z\n"))})
  opened = lambda point, source, text: world.run("decision", "open", "--unit", "U01", "--point", point, "--question", question(world, text), "--source", source, "--runcard", card)[1].splitlines()[0]
  rule = lambda posted, ruling, *d: world.run("decision", "rule", "--unit", "U01", *d, "--ruling", ruling, "--by", "owner", "--posted", posted, "--runcard", card)
  q1 = opened(3, "launch 1", "exited with no PR\n")
  assert rule("90", "one more round", "--decision", q1) == (1, "decision: comment 90 rules no point-3 decision\n")
  assert rule("92", "stop the unit") == (1, "decision: comment 92 rules relaunch, not stop the unit\n")
  assert rule("92", "relaunch") == (0, "recorded (comment 92)\n")
  q2 = opened(2, "review head-U01-c1 cap", "cap\n")
  assert rule("91", "stop") == (1, "decision: comment 91 is not on issue #2\n")
  assert rule("90", "stop") == (1, "decision: comment 90 rules one more round, not stop\n")
  assert rule("90", "one more round") == (0, "recorded (comment 90)\n")
  q3 = opened(1, "review head-U01-c1 round 1", "f-1-1 | high | a.py | regression: no | x\n")
  assert rule("93", "f-1-1 finding overruled — x") == (0, "recorded (comment 93)\n")
  q4 = opened(1, "review head-U01-c1 round 2", "f-2-1 | high | a.py | regression: no | y\n")
  assert rule("94", "f-2-1 finding overruled — y") == (0, "recorded (comment 94)\n")
  assert rule("95", "f-2-1 finding overruled — z") == (1, "decision: comment 95 does not name an open decision\n")
  ruled = [(r["decision"], r["ruling"], r["posted"]) for r in foreman_of(s, "U01")["rulings"]]
  assert ruled == [(q1, "relaunch", "comment 92"), (q2, "one more round", "comment 90"), (q3, "f-1-1 finding overruled — x", "comment 93"),
                   (q4, "f-2-1 finding overruled — y", "comment 94")] and 2 not in world.gh.comments
  assert not s.path("foreman", "U01").with_name("U01-q1.brainstorm.md").exists() and "stopped" not in foreman_of(s, "U01")


def test_a_posted_ruling_is_a_form_ruling_of_reads_and_a_panels_carries_no_session_reason(world):
  """Round 2 (PR #96 review): a reason typed on `finding upheld` or `one more round` stays in the record, out of the
  posted form; a panel's point-3 ruling with no reason is not labelled `ruled in the session` but carries the panel's
  own label (round 3), so its post is still a form the builder's prompt keeps."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world)
  rule = lambda qid, ruling, by="owner": world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", ruling, "--by", by, "--runcard", card)
  opened = lambda point, source, text=BLOCKED: world.run("decision", "open", "--unit", "U01", "--point", point, "--question", question(world, text), "--source", source, "--runcard", card)[1].splitlines()[0]
  q1 = opened(1, "review head-U01-c1 round 2", "f-2-1 | high | a.py | regression: no | x\n")
  assert rule(q1, "f-2-1 finding upheld — it holds")[0] == 0
  assert world.gh.comments[2][-1]["body"].splitlines()[0] == "**Ruling:** f-2-1 finding upheld (fix it)"
  q2 = opened(2, "review head-U01-c1 cap", "cap\n")
  assert rule(q2, "one more round — once")[0] == 0 and world.gh.comments[2][-1]["body"].splitlines()[0] == "**Ruling:** one more round"
  q3 = opened(3, "comment 77")
  assert rule(q3, "(b)", "judges:p-1")[0] == 0
  assert world.gh.comments[2][-1]["body"].splitlines()[:2] == ["**Ruling:** (77) use Redis — ruled by judges p-1", "(judges p-1, leavemealone)"]
  assert [r["reason"] for r in foreman_of(s, "U01")["rulings"]] == ["it holds", "once", "ruled by judges p-1"]
  assert "Ruling (judges p-1, leavemealone): U01 q3 (b) — ruled by judges p-1" in s.path("journal").read_text(encoding="utf-8")
  from superegm.launch_builder import prompt_text
  comments = [{"id": 1, "user": {"login": "owner"}, "body": world.gh.comments[2][-1]["body"]}]
  kept = prompt_text(2, "U01", "body", "orders", "orient", comments, [], None, BUILDER, "audit", owners=["owner"], foreman=foreman_of(s, "U01"))
  assert "## owner · comment 1\n**Ruling:** (77) use Redis — ruled by judges p-1\n" in kept, "the panel's choice reaches the builder"


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
  assert code == 1 and out == "decision: --decision is required unless --posted <comment id> or closed:<n>\n"


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
  for order in ("1. `landed`", "2. `closed`", "3. `exit` and `status`", "4. `ruling`", "5. `superegm foreman dispatch`", "6. `superegm launch`",
                "7. `superegm report`"):
    assert order in body, order
  for cited in ("unit_state", "loop_ended", "word_action", "recovered", "ci_wait_minutes", "--idle", "--posted closed:",
                "status --wait", "launch-builder", "record-launch", "review settle", "review rule", "review status",
                "runcard open --skill wave", "runcard close", "decision open", "decision rule", "in one message"):
    assert cited in body, cited
  for sub in ("report", "decision", "status", "launch", "launch-builder", "record-launch", "foreman", "review", "runcard"):
    assert world.run(sub, "--help")[0] == 0, sub


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
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"], owners=["owner"])
  fake_gh(world, {"user": {"login": BUILDER}, f"repos/{REPO}/issues/comments/9": {"id": 9, "user": {"login": "someone"}, "body": "**Ruling:** redesign — why\n"}})
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
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"], owners=["owner"])
  fake_gh(world, {"user": {"login": BUILDER}, f"repos/{REPO}/issues/comments/9": {"id": 9, "user": {"login": "owner"}, "body": "**Ruling:** redesign — why\n"}})
  code, out = world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", "redesign — why", "--by", "owner", "--posted", "9", "--runcard", card)
  brief = s.path("foreman", "U01").with_name(f"U01-{qid}.brainstorm.md")
  assert (code, out) == (0, "recorded (comment 9)\n"), out
  assert brief.is_file() and foreman_of(s, "U01")["stopped"]["brief"] == str(brief) and world.gh.comments.get(2, []) == []


def test_a_by_hand_ruling_without_decision_rules_what_its_form_names_once(world, monkeypatch):
  """Round 3 (PR #96 review): a `redesign` with no `--decision` rules the pending head decision (one entry, one
  brief); `--decision` at point 1 takes only a fid of that decision, ruled nowhere else; a second `one more round`
  is refused before anything is recorded; an edit before the record is the record's time; already-ruled is keyed on
  the comment's fid."""
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "builder-token")
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 1}]})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "owner"}, "body": body, "created_at": "2026-11-03T10:00:00Z",
                                                          "updated_at": at} for cid, body, at in (
      (60, "**Ruling:** f-1-1 finding upheld\n", "2026-11-03T10:30:00Z"), (61, "**Ruling:** f-1-1 finding overruled — x\n", "2026-11-03T10:00:00Z"),
      (62, "**Ruling:** f-2-2 finding upheld\n", "2026-11-03T10:00:00Z"), (63, "**Ruling:** one more round\n", "2026-11-03T10:00:00Z"),
      (64, "**Ruling:** one more round\n", "2026-11-03T10:00:00Z"), (65, "**Ruling:** redesign — the queue is wrong\n", "2026-11-03T10:00:00Z"))})
  opened = lambda point, source, text: world.run("decision", "open", "--unit", "U01", "--point", point, "--question", question(world, text), "--source", source, "--runcard", card)[1].splitlines()[0]
  rule = lambda posted, ruling, *d: world.run("decision", "rule", "--unit", "U01", *d, "--ruling", ruling, "--by", "owner", "--posted", posted, "--runcard", card)
  q1 = opened(1, "review head-U01-c1 round 1", "f-1-1 | high | a.py | regression: no | x\n")
  assert rule("60", "f-1-1 finding upheld") == (0, "recorded (comment 60)\n")
  assert foreman_of(s, "U01")["rulings"][-1]["posted_at"] == "2026-11-03T10:30:00Z", "an edit before the record is the recorded text"
  q2 = opened(1, "review head-U01-c1 round 2", "f-2-1 | high | a.py | regression: no | y\nf-2-2 | high | b.py | regression: no | z\n")
  assert rule("61", "f-1-1 finding overruled — x", "--decision", q2) == (1, f"decision: comment 61 rules f-1-1, not a finding of {q2}\n")
  assert rule("61", "f-2-2 finding upheld", "--decision", q2) == (1, f"decision: comment 61 rules f-1-1, not a finding of {q2}\n"), \
      "keyed on the comment's fid, never the typed one"
  assert rule("62", "f-2-2 finding upheld", "--decision", q2) == (0, "recorded (comment 62)\n")
  q3 = opened(2, "review head-U01-c1 cap", "cap\n")
  assert rule("63", "one more round") == (0, "recorded (comment 63)\n")
  q4 = opened(2, "review head-U01-c1 cap", "cap\n")
  assert rule("64", "one more round") == (1, "decision: comment 64 rules one more round, already spent on U01\n")
  assert rule("65", "redesign — the queue is wrong") == (0, "recorded (comment 65)\n")
  f = foreman_of(s, "U01")
  assert [(r["decision"], r["posted"]) for r in f["rulings"]] == [(q1, "comment 60"), (q2, "comment 62"), (q3, "comment 63"), (q4, "comment 65")]
  brief = s.path("foreman", "U01").with_name(f"U01-{q4}.brainstorm.md")
  assert brief.is_file() and f["stopped"]["brief"] == str(brief) and world.gh.comments.get(2, []) == []
  assert len(list(brief.parent.glob("U01-*.brainstorm.md"))) == 1


def test_a_by_hand_ruling_rules_only_a_finding_its_decision_names_and_its_point_decides_the_effect(world, monkeypatch):
  """Round 4 (PR #96 review): a fid no question names falls back only to a point-1 decision naming no finding; a fid
  ruled on another decision is dropped with `--decision` too; an `allowed` ruling records on the open point-1 decision
  naming its fid, else is refused unjournaled (`collect` reads it); a point-3 option whose text begins `stop` or is
  `redesign` neither stops the unit nor writes a brief."""
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "builder-token")
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 1}]})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "owner"}, "body": body, "created_at": "2026-11-03T10:00:00Z"}
                  for cid, body in ((70, "**Ruling:** f-1-9 finding upheld\n"), (71, "**Ruling:** f-2-1 finding overruled — x\n"),
                                    (72, "**Ruling:** f-2-1 finding upheld\n"), (73, "**Ruling:** foreman-1-2 allowed — an adopted history\n"),
                                    (74, "**Ruling:** foreman-1-3 allowed — y\n"), (75, "**Ruling:** (51) (a) redesign — fine\n"),
                                    (76, "**Ruling:** (50) (a) stop retrying on 4xx — fine\n"))})
  opened = lambda point, source, text: world.run("decision", "open", "--unit", "U01", "--point", point, "--question", question(world, text), "--source", source, "--runcard", card)[1].splitlines()[0]
  rule = lambda posted, ruling, *d: world.run("decision", "rule", "--unit", "U01", *d, "--ruling", ruling, "--by", "owner", "--posted", posted, "--runcard", card)
  journal = lambda: s.path("journal").read_text(encoding="utf-8")
  q1 = opened(1, "review head-U01-c1 round 1", "f-1-1 | high | a.py | regression: no | x\n")
  assert rule("70", "f-1-9 finding upheld") == (1, "decision: comment 70 does not name an open decision\n")
  assert rule("70", "f-1-9 finding upheld", "--decision", q1) == (1, f"decision: comment 70 rules f-1-9, not a finding of {q1}\n")
  typed = lambda qid, ruling: world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", ruling, "--by", "owner", "--runcard", card)[0]
  assert typed(q1, "f-1-1 finding upheld") == 0
  q2 = opened(1, "review head-U01-c1 round 2", "f-2-1 | high | a.py | regression: no | y\n")
  assert rule("71", "f-2-1 finding overruled — x", "--decision", q2) == (0, "recorded (comment 71)\n")
  q3 = opened(1, "review head-U01-c1 round 3", "f-2-1 | high | a.py | regression: no | y\nf-3-1 | high | a.py | regression: no | z\n")
  assert rule("72", "f-2-1 finding upheld", "--decision", q3) == (1, "decision: f-2-1 already ruled\n")
  assert "ruling dropped (owner, comment 72): f-2-1 already ruled" in journal()
  assert typed(q3, "f-3-1 finding upheld") == 0
  q4 = opened(1, "review head-U01-c1 round 2", "foreman-1-2 | high | tests/unit/test_hooks.py | regression: no | tdd-order: S1\n")
  assert rule("73", "foreman-1-2 finding overruled") == (0, "recorded (comment 73)\n")
  r = foreman_of(s, "U01")["rulings"][-1]
  assert (r["decision"], r["ruling"], r["reason"]) == (q4, "foreman-1-2 finding overruled", "an adopted history")
  assert rule("74", "foreman-1-3 finding overruled") == (1, "decision: comment 74 allows foreman-1-3; no open decision names it\n")
  assert "comment 74" not in journal()
  opened(3, "comment 51", "**Builder status:** BLOCKED\nWhich?\n- (a) redesign\n- (b) keep it\n")
  assert rule("75", "(a)") == (0, "recorded (comment 75)\n")
  opened(3, "comment 50", "**Builder status:** BLOCKED\nWhich?\n- (a) stop retrying on 4xx\n- (b) keep retrying\n")
  assert rule("76", "(a)") == (0, "recorded (comment 76)\n")
  assert not foreman_of(s, "U01").get("stopped") and not list(s.path("foreman", "U01").parent.glob("U01-*.brainstorm.md"))


def test_a_by_hand_ruling_finds_its_fid_on_a_finding_line_alone(world):
  """Round 5 (PR #96 review): a point-1 question asks about the fids its finding lines start with (`<fid> |` or
  `## Q<n> <fid> (`), never one its claim or reason text quotes."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "owner"}, "body": body, "created_at": "2026-11-03T10:00:00Z"}
                  for cid, body in ((80, "**Ruling:** astra-3-1 finding overruled — x\n"), (81, "**Ruling:** foreman-4-1 finding overruled — y\n"),
                                    (82, "**Ruling:** foreman-4-2 finding upheld\n"))})
  opened = lambda point, source, text: world.run("decision", "open", "--unit", "U01", "--point", point, "--question", question(world, text), "--source", source, "--runcard", card)[1].splitlines()[0]
  rule = lambda posted, ruling, *d: world.run("decision", "rule", "--unit", "U01", *d, "--ruling", ruling, "--by", "owner", "--posted", posted, "--runcard", card)
  q1 = opened(1, "review head-U01-c1 round 4", "foreman-4-1 | high | pr #96 comment 1 | regression: no | contested astra-3-1: x\n"
              "## Q2 foreman-4-2 (high, pr #96 comment 2): contested astra-3-2: y\n")
  assert rule("80", "astra-3-1 finding overruled") == (1, "decision: comment 80 does not name an open decision\n")
  assert rule("80", "astra-3-1 finding overruled", "--decision", q1) == (1, f"decision: comment 80 rules astra-3-1, not a finding of {q1}\n")
  assert rule("81", "foreman-4-1 finding overruled") == (0, "recorded (comment 81)\n")
  assert rule("82", "foreman-4-2 finding upheld") == (0, "recorded (comment 82)\n")
  assert [r["decision"] for r in foreman_of(s, "U01")["rulings"]] == [q1, q1]


def test_an_allowance_on_an_open_decision_in_leavemealone_takes_the_overrule_form(world):
  """Round 5 (PR #96 review): `review settle --posted` reads only `<fid> finding overruled`, so in leavemealone-mode
  an allowance naming an open point-1 decision is refused before anything is recorded; round 6: the refusal is
  journaled as dropped, the owner's notice of it."""
  card = world.run("runcard", "open", "--skill", "wave", "--artifact", world.spec, "--mode", "leavemealone", card=None)[1].strip()
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/73": {"id": 73, "user": {"login": "owner"}, "body": "**Ruling:** foreman-1-2 allowed — adopted\n",
                                                       "created_at": "2026-11-03T10:00:00Z"}})
  q = world.run("decision", "open", "--unit", "U01", "--point", 1, "--question",
                question(world, "foreman-1-2 | high | tests/unit/test_hooks.py | regression: no | tdd-order: S1\n"),
                "--source", "review head-U01-c1 round 2", "--runcard", card)[1].splitlines()[0]
  assert world.run("decision", "rule", "--unit", "U01", "--ruling", "foreman-1-2 finding overruled", "--by", "owner", "--posted", "73", "--runcard", card) == (
      1, f"decision: comment 73 allows foreman-1-2; in leavemealone-mode {q} takes `**Ruling:** foreman-1-2 finding overruled — <reason>`\n")
  assert foreman_of(s, "U01")["rulings"] == [] and (
      f"ruling dropped (owner, comment 73): comment 73 allows foreman-1-2; in leavemealone-mode {q} takes "
      "`**Ruling:** foreman-1-2 finding overruled — <reason>`") in s.path("journal").read_text(encoding="utf-8")


def test_a_session_post_read_back_fails_is_never_read_as_edited(world, monkeypatch):
  """Round 5 (PR #96 review): when the session's own post cannot be read back, its `posted_at` is the host's time,
  not GitHub's, and the entry says so (`unread`): such a post never reads as an edit after the record."""
  from superegm.decision import overridden_comments
  from superegm.status import ruling_facts
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world)
  monkeypatch.setattr("superegm.decision.read_back", lambda st, cid: {})  # the read-back's `GhError`
  q = world.run("decision", "open", "--unit", "U01", "--point", 2, "--question", question(world, "cap\n"), "--source", "review head-U01-c1 cap", "--runcard", card)[1].splitlines()[0]
  assert world.run("decision", "rule", "--unit", "U01", "--decision", q, "--ruling", "stop", "--by", "owner", "--runcard", card)[0] == 0
  entry = foreman_of(s, "U01")["rulings"][-1]
  assert entry["posted_at"] and entry.get("unread") is True
  posted = {"id": int(entry["posted"].removeprefix("comment ")), "user": {"login": "owner"}, "body": world.gh.comments[2][-1]["body"],
            "created_at": "2099-01-01T00:00:00Z", "updated_at": "2099-01-01T00:00:00Z"}
  assert ruling_facts(s, "U01", [posted], ["owner"]) == [] and overridden_comments([posted], ["owner"], foreman_of(s, "U01")) == {}
  # round 6 (PR #96 review): an edit of the unread post (GitHub's `updated_at` past its own `created_at`) is an edit
  edited = posted | {"body": "**Ruling:** one more round", "updated_at": "2099-01-01T00:05:00Z"}
  assert [r.kind for r in ruling_facts(s, "U01", [edited], ["owner"])] == ["round"]
  assert overridden_comments([edited], ["owner"], foreman_of(s, "U01")) == {
      edited["id"]: "**Ruling:** stop\n(as recorded by owner; the comment was edited after its record)"}


def test_a_finding_line_is_a_rows_or_a_question_headings_and_takes_an_external_fid(world):
  """Round 6 (PR #96 review): `<fid> (` starts a finding line only after `## Q<n>`, so a quoted original on a line of
  its own is not the question's; an external fid (`external:<login>-<r>-<n>`) is a finding line's like any other."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "owner"}, "body": body, "created_at": "2026-11-03T10:00:00Z"}
                  for cid, body in ((90, "**Ruling:** change-review-1-4 finding overruled — x\n"),
                                    (91, "**Ruling:** external:devin-ai-integration[bot]-2-7 finding overruled — y\n"),
                                    (92, "**Ruling:** external:alice-1-1 finding upheld\n"))})
  opened = lambda text: world.run("decision", "open", "--unit", "U01", "--point", 1, "--question", question(world, text), "--source", "review head-U01-c1 round 2", "--runcard", card)[1].splitlines()[0]
  rule = lambda posted, ruling, *d: world.run("decision", "rule", "--unit", "U01", *d, "--ruling", ruling, "--by", "owner", "--posted", posted, "--runcard", card)
  q1 = opened("foreman-2-1 | high | pr #96 comment 1 | regression: no | contested change-review-1-4: x\n\n"
              "change-review-1-4 (low, declined by the owner): the path\n"
              "external:devin-ai-integration[bot]-2-7 | high | a.py:1 | regression: no | y\n"
              "## Q2 external:alice-1-1 (high, a.py:2): z\n")
  assert rule("90", "change-review-1-4 finding overruled") == (1, "decision: comment 90 does not name an open decision\n")
  assert rule("90", "change-review-1-4 finding overruled", "--decision", q1) == (1, f"decision: comment 90 rules change-review-1-4, not a finding of {q1}\n")
  assert rule("91", "external:devin-ai-integration[bot]-2-7 finding overruled") == (0, "recorded (comment 91)\n")
  assert rule("92", "external:alice-1-1 finding upheld", "--decision", q1) == (0, "recorded (comment 92)\n")
  assert [r["decision"] for r in foreman_of(s, "U01")["rulings"]] == [q1, q1]


def test_a_session_post_is_recorded_at_its_creation_so_any_edit_reads_as_one(world, monkeypatch):
  """Round 8 (PR #96 review): the session's own post is recorded at GitHub's `created_at`, never its `updated_at`, so
  an owner's edit between the record and the read-back still reads as an edit after the record."""
  from superegm.status import ruling_facts
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world)
  monkeypatch.setattr("superegm.decision.read_back", lambda st, cid: {"created_at": "2099-01-01T00:00:00Z", "updated_at": "2099-01-01T00:05:00Z"})
  q = world.run("decision", "open", "--unit", "U01", "--point", 2, "--question", question(world, "cap\n"), "--source", "review head-U01-c1 cap", "--runcard", card)[1].splitlines()[0]
  assert world.run("decision", "rule", "--unit", "U01", "--decision", q, "--ruling", "stop", "--by", "owner", "--runcard", card)[0] == 0
  entry = foreman_of(s, "U01")["rulings"][-1]
  assert entry["posted_at"] == "2099-01-01T00:00:00Z" and not entry.get("unread")
  edited = {"id": int(entry["posted"].removeprefix("comment ")), "user": {"login": "owner"}, "body": "**Ruling:** one more round",
            "created_at": "2099-01-01T00:00:00Z", "updated_at": "2099-01-01T00:05:00Z"}
  assert [r.kind for r in ruling_facts(s, "U01", [edited], ["owner"])] == ["round"]


def test_a_by_hand_option_names_one_decision_and_a_redesign_rules_every_pending_one(world, monkeypatch):
  """Round 8 (PR #96 review): a point-3 option names a decision opened on a comment by the comment's id alone, with or
  without `--decision`; a `redesign` with no `--decision` rules every pending decision, one entry each, one brief (the
  first decision's)."""
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "builder-token")
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "rounds": [{"round": 1, "phase": "posted", "outcome": "revise", "launch": 1}]})
  set_config(world, repo=REPO, owners=["owner"])
  q1 = world.run("decision", "open", "--unit", "U01", "--point", 3, "--question", question(world), "--source", "comment 77", "--runcard", card)[1].splitlines()[0]
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "owner"}, "body": body, "created_at": "2026-11-03T10:00:00Z"}
                  for cid, body in ((93, f"**Ruling:** ({q1}) (b) use Redis — fine\n"), (94, "**Ruling:** redesign — the queue is wrong\n"))})
  rule = lambda posted, ruling, *d: world.run("decision", "rule", "--unit", "U01", *d, "--ruling", ruling, "--by", "owner", "--posted", posted, "--runcard", card)
  assert rule("93", "(b)") == (1, "decision: comment 93 does not name an open decision\n")
  assert rule("93", "(b)", "--decision", q1) == (1, "decision: comment 93 does not name comment 77\n")
  f = foreman_of(s, "U01")  # `decision open` opens one at a time; a record may hold more pending (a cap beside a point-3)
  q2 = "q2"
  f["decisions"].append({"id": q2, "point": 2, "source": "review head-U01-c1 cap", "question": "cap\n",
                        "options": ["one more round", "stop"]})
  s.path("foreman", "U01").write_text(json.dumps(f), encoding="utf-8")
  assert rule("94", "redesign") == (0, "recorded (comment 94)\n")
  f = foreman_of(s, "U01")
  assert [(r["decision"], r["posted"]) for r in f["rulings"]] == [(q1, "comment 94"), (q2, "comment 94")]
  brief = s.path("foreman", "U01").with_name(f"U01-{q1}.brainstorm.md")
  assert brief.is_file() and f["stopped"]["brief"] == str(brief) and len(list(brief.parent.glob("U01-*.brainstorm.md"))) == 1
  journal = s.path("journal").read_text(encoding="utf-8")
  assert all(f"Ruling (owner, comment 94): U01 {q} redesign — the queue is wrong" in journal for q in (q1, q2))


def test_a_stop_whose_label_fails_records_nothing_so_its_comment_replays(world, monkeypatch):
  """Round 9 (PR #96 review): a stop's label is applied before the ruling is recorded, so a failed label request
  leaves the decision open and the comment unrecorded, and the same `decision rule --posted` applies it on a retry."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world, {f"repos/{REPO}/issues/comments/95": {"id": 95, "user": {"login": "owner"}, "body": "**Ruling:** stop\n",
                                                        "created_at": "2026-11-03T10:00:00Z"}})
  q = world.run("decision", "open", "--unit", "U01", "--point", 2, "--question", question(world, "cap\n"), "--source", "review head-U01-c1 cap", "--runcard", card)[1].splitlines()[0]
  real = superegm.gh
  def failing(args, *a, **kw):
    if "--add-label" in args:
      raise superegm.GhError(args, 1, "", "HTTP 502")
    return real(args, *a, **kw)
  monkeypatch.setattr(superegm, "gh", failing)
  rule = lambda: world.run("decision", "rule", "--unit", "U01", "--ruling", "stop", "--by", "owner", "--posted", "95", "--runcard", card)
  with pytest.raises(superegm.GhError):  # the helper's `gh` failure
    rule()
  f = foreman_of(s, "U01")
  assert f["rulings"] == [] and "stopped" not in f and "superegm:stopped" not in world.gh.issues[2]["labels"]
  monkeypatch.setattr(superegm, "gh", real)
  assert rule() == (0, "recorded (comment 95)\n")
  f = foreman_of(s, "U01")
  assert [r["decision"] for r in f["rulings"]] == [q] and f["stopped"]["reason"] == "stop"
  assert "superegm:stopped" in world.gh.issues[2]["labels"]


def test_a_session_stop_whose_post_fails_leaves_no_label(world, monkeypatch):
  """Round 10 (PR #96 review, change-review-10-2): a session stop's label precedes its post; a post that fails takes
  the label off again, so nothing is recorded, the issue is not stopped, and the same call runs again."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"])
  fake_gh(world)
  q = world.run("decision", "open", "--unit", "U01", "--point", 2, "--question", question(world, "cap\n"), "--source", "review head-U01-c1 cap", "--runcard", card)[1].splitlines()[0]
  real = superegm.gh
  def failing(args, *a, **kw):
    if args[:2] == ["issue", "comment"]:
      raise superegm.GhError(args, 1, "", "HTTP 502")
    return real(args, *a, **kw)
  monkeypatch.setattr(superegm, "gh", failing)
  rule = lambda: world.run("decision", "rule", "--unit", "U01", "--decision", q, "--ruling", "stop", "--by", "owner", "--runcard", card)
  with pytest.raises(superegm.GhError):
    rule()
  f = foreman_of(s, "U01")
  assert f["rulings"] == [] and "stopped" not in f and "superegm:stopped" not in world.gh.issues[2]["labels"]
  monkeypatch.setattr(superegm, "gh", real)
  assert rule()[0] == 0 and "superegm:stopped" in world.gh.issues[2]["labels"]
  assert [r["decision"] for r in foreman_of(s, "U01")["rulings"]] == [q]


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


FORMS_PROSE = [("skills/wave/SKILL.md", n) for n in ("`closed`, `ruling`", "- `ruling` lines", "ruling edited after record, ignored", "ruling dropped (")] + [
               ("skills/wave/references/builder_orders.md", n) for n in ("**Ruling:** <fid> finding upheld", "**Ruling:** <fid> finding overruled — <reason>",
               "**Ruling:** one more round", "**Ruling:** stop", "**Ruling:** <fid> allowed — <reason>",
               "**Ruling:** redesign — <reason>", "`config.owners`")]


@pytest.mark.parametrize("path, needle", FORMS_PROSE)
def test_the_wave_skill_and_the_orders_quote_the_ruling_forms(path, needle):
  assert needle in (SKILL.parents[2] / path).read_text(encoding="utf-8"), (path, needle)


@pytest.mark.parametrize("needle", [  # round 3 (PR #96 review): a ruling by comment continues as its point's typed section does
    "then, for `finding upheld` too, by `review status`: 0 → the unit awaits\n  merge; 2 → Decision point 2; else `launch-builder`",
    "a spent `one more round` is refused before anything is recorded",
    "(a `redesign` at point 1 runs no `review rule`)",
    "option on a `BLOCKED` comment → `launch-builder` now"])
def test_a_ruling_by_comment_continues_as_its_point_does(needle):
  assert needle in SKILL.read_text(encoding="utf-8"), needle


@pytest.mark.parametrize("path, needle", [  # round 4 (PR #96 review): how `--ruling` is built, the allowance, NEEDS_CONTEXT, the orders' shapes
    ("skills/wave/SKILL.md", "`--ruling` is the event's words as the point's form"),
    ("skills/wave/SKILL.md", "`<fid> allowed` as `--ruling '<fid> finding overruled'`"),
    ("skills/wave/SKILL.md", "no open decision names it"),
    ("skills/wave/SKILL.md", "`BLOCKED` or `NEEDS_CONTEXT` comment"),
    ("skills/wave/SKILL.md", "`ruling dropped (<by>, comment <id>): …`\n  for one naming no open decision or an already ruled one"),
    ("skills/wave/references/builder_orders.md", "`**Ruling:** (<decision id>) <option> — <reason>`"),
    ("skills/wave/references/builder_orders.md", "(as recorded by <by>; the comment was edited after its record)"),
    ("skills/wave/references/builder_orders.md", "(judges <panel>, leavemealone)"),
    # round 5 (PR #96 review): a redesign's `--ruling` carries no invented reason; an allowance in leavemealone-mode
    ("skills/wave/SKILL.md", "`redesign` as `--ruling 'redesign'`"),
    ("skills/wave/SKILL.md", "in leavemealone-mode an allowance naming an open decision is refused"),
    ("skills/wave/references/builder_orders.md", "(recorded on <decision id> as: <option>)"),
    # round 6 (PR #96 review): the refused allowance is journaled for the owner; a deleted recorded comment
    ("skills/wave/SKILL.md", "or a refused allowance"),
    ("skills/wave/references/builder_orders.md", "(as recorded by <by>; the comment was deleted after its record)"),
    # round 7 (PR #96 review): the finding lines `decision rule` reads; entry step 4 reads a posted ruling through the record
    ("skills/wave/SKILL.md", "each finding on a line of its own starting `<fid> |` or `## Q<n> <fid> (`"),
    ("skills/wave/SKILL.md", "binds once `decision rule --posted <comment id>` records it"),
    ("skills/wave/SKILL.md", "whose post or label request fails"),
    ("skills/wave/SKILL.md", "a `--posted` one included"),
    ("skills/wave/references/builder_orders.md", "(as recorded by <by>; the comment is in no ruling form)"),
    # round 8 (PR #96 review): the whole-file allowance; who posts the judges' ruling; a run stopped after a record
    ("skills/wave/references/builder_orders.md", "`**Ruling:** test-delta <file> allowed — <reason>`"),
    ("skills/wave/references/builder_orders.md", "posted under the elephant's token after the record"),
    ("skills/wave/SKILL.md", "a run stopped between a record and its continuation")])
def test_the_ruling_prose_names_how_a_ruling_is_applied_and_read(path, needle):
  assert needle in (ROOT / path).read_text(encoding="utf-8"), (path, needle)
