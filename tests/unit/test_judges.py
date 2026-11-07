# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
"""U08: the judge panel (judges open|record|diff|verdict, the grammars, the adapter, persona and skill)."""
import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from superegm import judges

ROOT = Path(__file__).resolve().parents[2]

QUESTIONS = """## Q1 Is finding design-2-1 upheld?
- (a) finding upheld
- (b) finding overruled: the reason, copied verbatim

## Q2 The review is at its cap: what next?
- (a) continue one bounded round
- (b) accept the remainder
- (c) stop
"""
ONE = "## Q1 Is finding design-2-1 upheld?\n- (a) finding upheld\n- (b) finding overruled: reason\n"
ANSWERS = "Q1: (a)\nreason: the evidence shows it\nQ2: (c)\n"


def open_card(world, skill, artifact, parent=None):
  argv = ["runcard", "open", "--skill", skill, "--artifact", artifact]
  if parent:
    argv += ["--parent", parent]
  code, out = world.run(*argv)
  assert code == 0, out
  return out.strip()


def open_panel(world, text=QUESTIONS, name="q-test", parent=None):
  question = world.repo.parent / f"{name}.md"
  question.write_text(text, encoding="utf-8")
  card = parent or open_card(world, "judges", question)
  code, out = world.run("judges", "open", "--question", question, "--parent" if parent else "--runcard", card)
  assert code == 0, out
  return out.strip(), card, question


def panel_json(world, pid):
  return json.loads((world.artifacts / "judges" / pid / "panel.json").read_text(encoding="utf-8"))


def journal(world):
  return (world.artifacts / "journal.md").read_text(encoding="utf-8")


def record(world, pid, card, rnd, judge, answers=None, not_run=None, isolation="clean", extra=()):
  argv = ["judges", "record", "--panel", pid, "--round", rnd, "--judge", judge, "--runcard", card, *extra]
  if not_run:
    argv += ["--not-run", not_run]
  else:
    verdict = world.repo.parent / f"{pid}-r{rnd}-{judge}.md"
    verdict.write_text("".join(f"{q}: ({o})\n" for q, o in answers.items()), encoding="utf-8")
    argv += ["--verdict", verdict]
    if isolation:
      argv += ["--isolation", isolation]
  return world.run(*argv)


@pytest.mark.parametrize("text, reason", [
    ("Is it upheld?\n- (a) yes\n- (b) no\n", "line 1: expected `## Q<n> <question>` or `- (<id>) <option>`"),
    ("## Q1 Upheld?\n- (a) yes\n", "Q1: fewer than two options"),
    ("## Q1 Upheld?\n- (a) yes\n- (a) no\n", "Q1: duplicate option (a)"),
    ("## Q1 Upheld?\n- (a) yes\n- (b) no\n## Q1 Again?\n- (a) yes\n- (b) no\n", "duplicate question Q1"),
    ("- (a) yes\n## Q1 Upheld?\n- (a) yes\n- (b) no\n", "line 1: option before any question"),
    ("", "no questions"),
])
def test_question_grammar_refusals(text, reason):
  with pytest.raises(ValueError, match=re.escape(reason)):
    judges.parse_questions(text)


def test_parse_questions_several():
  parsed = judges.parse_questions(QUESTIONS)
  assert [q["id"] for q in parsed] == ["Q1", "Q2"]
  assert parsed[0]["text"] == "Is finding design-2-1 upheld?"
  assert parsed[1]["options"] == {"a": "continue one bounded round", "b": "accept the remainder", "c": "stop"}


@pytest.mark.parametrize("text, reason", [
    ("Q1: (z)\nQ2: (a)\n", "Q1: unknown option (z)"),
    ("Q1: (a)\nQ3: (a)\n", "unknown question Q3"),
    ("Q1: a\n", "line 1: expected `Q<n>: (<id>)`"),
    ("Q1: (a)\nQ1: (b)\n", "duplicate answer Q1"),
])
def test_verdict_file_refusals(text, reason):
  with pytest.raises(ValueError, match=re.escape(reason)):
    judges.parse_verdict(text, judges.parse_questions(QUESTIONS))


def test_verdict_file_parses_reason_and_change():
  answers = judges.parse_verdict(
      "Q1: (b)\nreason: the fix is in the spec\nwould change my mind: a test that fails\nQ2: (c)\n",
      judges.parse_questions(QUESTIONS))
  assert answers == {"Q1": {"option": "b", "reason": "the fix is in the spec", "would_change": "a test that fails"},
                     "Q2": {"option": "c", "reason": None, "would_change": None}}


@pytest.mark.parametrize("members", [
    {"fable": {"via": "adapter", "effort": "max"}, "opus": {"via": "adapter", "effort": "max"}, "astra": {"via": "runner"}},
    [{"id": "fable", "via": "adapter"}, {"id": "opus", "via": "adapter"}, {"id": "astra", "via": "runner"}],
    ["fable", "opus", "astra"],
])
def test_judge_members_forms(members):
  config = {"judges": {"min_vendors": 1, "members": members},
            "astra": {"enabled": True, "model": "gpt-6-astra", "effort": "xhigh"}}
  got = judges.judge_members(config)
  assert list(got) == ["fable", "opus", "astra"]
  assert got["fable"] == {"via": "adapter", "vendor": "anthropic", "model": "fable", "effort": "max"}
  assert got["astra"] == {"via": "runner", "vendor": "openai", "model": "gpt-6-astra", "effort": "xhigh"}
  assert judges.judge_members({})["opus"] == {"via": "adapter", "vendor": "anthropic", "model": "opus", "effort": "max"}
  assert judges.judge_members({})["fable"]["effort"] == "xhigh"


def test_open_records_panel_and_round_one_brief(world):
  evidence = world.repo / "evidence.md"
  evidence.write_text("the finding's location\n", encoding="utf-8")
  question = world.repo.parent / "q-test.md"
  question.write_text(QUESTIONS, encoding="utf-8")
  card = open_card(world, "judges", question)
  code, out = world.run("judges", "open", "--question", question, "--evidence", evidence, "--runcard", card)
  assert code == 0, out
  sha = hashlib.sha256(QUESTIONS.encode("utf-8")).hexdigest()
  pid = out.strip()
  assert pid == f"q-test-{sha[:6]}"
  panel = panel_json(world, pid)
  assert (panel["question"], panel["question_sha256"], panel["runcard"], panel["parent"]) == (str(question), sha, card, None)
  assert panel["evidence"] == [{"path": str(evidence), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}]
  assert list(panel["judges"]) == ["fable", "opus", "astra"] and panel["min_vendors"] == 1 and panel["rounds"] == {}
  store = world.artifacts / "judges" / pid
  assert (store / "question.md").read_text(encoding="utf-8") == QUESTIONS
  brief = (store / "round-1/brief.md").read_text(encoding="utf-8")
  assert brief.startswith(f"JUDGE BRIEF, panel {pid}, round 1.")
  assert f"Question file: {question} (sha256 {sha})" in brief and f"Evidence: {evidence}" in brief
  assert "Q<n>: (<id>)" in brief and "Questions still open" not in brief
  assert f"judges {pid}: opened (fable, opus, astra; min_vendors 1)" in journal(world)


def test_open_with_parent_opens_a_child_card(world):
  (world.repo / "spec.md").write_text("# spec\n\n## Units\n", encoding="utf-8")
  wave = open_card(world, "wave", world.repo / "spec.md")
  pid, _, question = open_panel(world, parent=wave)
  panel = panel_json(world, pid)
  assert panel["parent"] == wave and panel["runcard"] != wave
  child = json.loads((world.artifacts / "runcards" / f"{panel['runcard']}.json").read_text(encoding="utf-8"))
  assert (child["skill"], child["artifact"], child["parent"]) == ("judges", str(question), wave)


@pytest.mark.parametrize("setup, reason", [
    ("missing-question", "judges: question file"),
    ("grammar", "judges: question file: Q1: fewer than two options"),
    ("missing-evidence", "judges: evidence"),
    ("exists", "judges: panel"),
])
def test_open_refusals(world, setup, reason):
  question = world.repo.parent / "q-test.md"
  question.write_text("## Q1 Upheld?\n- (a) yes\n" if setup == "grammar" else QUESTIONS, encoding="utf-8")
  argv = ["judges", "open", "--question", question, "--runcard", open_card(world, "judges", question)]
  if setup == "missing-question":
    question.unlink()
  if setup == "missing-evidence":
    argv += ["--evidence", world.repo / "none.md"]
  if setup == "exists":
    assert world.run(*argv)[0] == 0
  code, out = world.run(*argv)
  assert code == 1 and reason in out, out
  if setup != "exists":
    assert not (world.artifacts / "judges").exists()


@pytest.mark.parametrize("case", ["other-artifact", "judges-card-as-parent", "parent-closed"])
def test_runcard_rules(world, case):
  (world.repo / "spec.md").write_text("# spec\n\n## Units\n", encoding="utf-8")
  if case == "other-artifact":
    other = world.repo.parent / "other.md"
    other.write_text(QUESTIONS, encoding="utf-8")
    question = world.repo.parent / "q-test.md"
    question.write_text(QUESTIONS, encoding="utf-8")
    code, out = world.run("judges", "open", "--question", question, "--runcard", open_card(world, "judges", other))
  elif case == "judges-card-as-parent":
    pid, card, question = open_panel(world)
    code, out = world.run("judges", "open", "--question", question, "--parent", card)
  else:
    wave = open_card(world, "wave", world.repo / "spec.md")
    pid, _, _ = open_panel(world, parent=wave)
    assert world.run("runcard", "close", wave)[0] == 0
    code, out = record(world, pid, wave, 1, "fable", {"Q1": "a", "Q2": "a"})
  assert code == 1 and "runcard: " in out, out


def test_record_claude_verdict(world):
  pid, card, _ = open_panel(world)
  code, out = record(world, pid, card, 1, "fable", {"Q1": "a", "Q2": "c"},
                     extra=["--model", "fable:fable-5-1", "--effort", "max:max"])
  assert (code, out.strip()) == (0, "recorded"), out
  assert (world.artifacts / "judges" / pid / "round-1/fable.md").read_text(encoding="utf-8") == "Q1: (a)\nQ2: (c)\n"
  entry = panel_json(world, pid)["rounds"]["1"]["fable"]
  assert (entry["isolation"], entry["model"], entry["effort"]) == ("clean", "fable:fable-5-1", "max:max")
  assert entry["options"] == {"Q1": "a", "Q2": "c"}
  assert record(world, pid, card, 1, "opus", {"Q1": "a", "Q2": "c"}, isolation="exposed:SubagentStart hook")[0] == 0
  opus = panel_json(world, pid)["rounds"]["1"]["opus"]
  assert (opus["isolation"], opus["model"], opus["effort"]) == ("exposed:SubagentStart hook", "opus:opus", "max:max")
  assert f"judges {pid}: round 1 fable recorded (clean)" in journal(world)


@pytest.mark.parametrize("where, saw", [("first", "CLAUDE.md"), ("last", "none"), ("none", None)])
def test_record_accepts_the_saw_line_first_or_last(world, where, saw):
  pid, card, _ = open_panel(world)
  text = {"first": f"saw: {saw}\n\n{ANSWERS}", "last": f"{ANSWERS}saw: {saw}\n", "none": ANSWERS}[where]
  verdict = world.repo.parent / "verdict.md"
  verdict.write_text(text)
  isolation = "clean" if saw in (None, "none") else f"exposed:{saw}"
  argv = ["judges", "record", "--panel", pid, "--round", 1, "--judge", "fable", "--verdict", verdict, "--isolation", isolation, "--runcard", card]
  assert world.run(*argv)[0] == 0
  entry = panel_json(world, pid)["rounds"]["1"]["fable"]
  assert (entry["saw"], entry["isolation"], entry["options"]) == (saw, isolation, {"Q1": "a", "Q2": "c"})


@pytest.mark.parametrize("judge, rnd, answers, isolation, reason", [
    ("sonnet", 1, {"Q1": "a", "Q2": "a"}, "clean", "judges: unknown judge sonnet"),
    ("fable", 0, {"Q1": "a", "Q2": "a"}, "clean", "judges: round must be 1..5"),
    ("fable", 2, {"Q1": "a", "Q2": "a"}, "clean", "judges: round 1 not diffed"),
    ("fable", 1, {"Q1": "a"}, "clean", "judges: verdict file: no answer for Q2"),
    ("fable", 1, {"Q1": "a", "Q2": "a"}, "dirty", "judges: isolation must be clean or exposed:<what>"),
    ("fable", 1, {"Q1": "a", "Q2": "a"}, None, "judges: --isolation required with --verdict"),
    ("fable", 1, "again", "clean", "judges: round 1: fable already recorded"),
])
def test_record_refusals(world, judge, rnd, answers, isolation, reason):
  pid, card, _ = open_panel(world)
  if answers == "again":
    answers = {"Q1": "a", "Q2": "a"}
    assert record(world, pid, card, 1, "fable", answers)[0] == 0
  code, out = record(world, pid, card, rnd, judge, answers, isolation=isolation)
  assert code == 1 and reason in out, out


@pytest.mark.parametrize("result, expect", [
    ({"status": "completed", "effective_model": "gpt-6-astra", "effective_effort": "xhigh",
      "response": {"verdict": "REVISE", "summary": "Q1: (a)\nreason: the evidence shows it\nQ2: (c)\n"}}, "recorded"),
    ({"status": "failed", "error": "codex not logged in"}, "not run (codex not logged in)"),
    ({"status": "completed", "response": {"verdict": "BLOCKED", "limitations": "question file unreadable"}},
     "not run (blocked: question file unreadable)"),
    ({"status": "running"}, "not run (killed)"),
    ({"status": "completed", "response": {"verdict": "APPROVED", "summary": "Q1: (a)\n"}}, "not run (no answer for Q2)"),
])
def test_record_astra_result(world, result, expect):
  pid, card, _ = open_panel(world)
  path = world.repo.parent / "result.json"
  path.write_text(json.dumps(result), encoding="utf-8")
  code, out = world.run("judges", "record", "--panel", pid, "--round", 1, "--judge", "astra",
                        "--result", path, "--runcard", card)
  assert (code, out.strip()) == (0, expect), out
  panel = panel_json(world, pid)
  entry = panel["rounds"]["1"]["astra"]
  if expect == "recorded":
    requested = panel["judges"]["astra"]["model"]
    assert entry == {"isolation": "runner", "model": f"{requested}:gpt-6-astra",
                     "effort": f"{panel['judges']['astra']['effort']}:xhigh",
                     "options": {"Q1": "a", "Q2": "c"}, "recorded_at": entry["recorded_at"]}
    assert (world.artifacts / "judges" / pid / "round-1/astra.md").read_text(encoding="utf-8") == result["response"]["summary"]
  else:
    assert entry == {"not_run": expect[len("not run ("):-1], "recorded_at": entry["recorded_at"]}
    assert f"judges {pid}: round 1 astra not run ({entry['not_run']})" in journal(world)


def test_diff_writes_neutral_list_and_next_brief(world):
  pid, card, _ = open_panel(world)
  for judge, q2 in (("fable", "a"), ("opus", "b"), ("astra", "b")):
    assert record(world, pid, card, 1, judge, {"Q1": "a", "Q2": q2})[0] == 0
  code, out = world.run("judges", "diff", "--panel", pid, "--round", 1, "--runcard", card)
  store = world.artifacts / "judges" / pid
  assert (code, out.strip()) == (0, str(store / "round-1/diff.md")), out
  diff = (store / "round-1/diff.md").read_text(encoding="utf-8")
  assert diff == (f"# Panel {pid}, round 1: where positions differ\n"
                  "## Q1: converged on (a)\n"
                  "## Q2\n- (a): fable\n- (b): opus, astra\n")
  brief = (store / "round-2/brief.md").read_text(encoding="utf-8")
  assert brief.startswith(f"JUDGE BRIEF, panel {pid}, round 2.")
  assert "Questions still open: Q2\n" in brief and "no one adds arguments between rounds" in brief
  for judge in ("fable", "opus", "astra"):
    assert f"### Round 1, {judge}\n" + (store / f"round-1/{judge}.md").read_text(encoding="utf-8") in brief
  assert diff in brief
  assert f"judges {pid}: round 1 diff written, open Q2" in journal(world)


def test_diff_refuses_an_unrecorded_judge(world):
  pid, card, _ = open_panel(world)
  assert record(world, pid, card, 1, "fable", {"Q1": "a", "Q2": "a"})[0] == 0
  code, out = world.run("judges", "diff", "--panel", pid, "--round", 1, "--runcard", card)
  assert code == 1 and "judges: round 1: opus not recorded" in out, out


@pytest.mark.parametrize("case, votes, min_vendors, code, converged, degraded", [
    ("all agree", {"fable": "a", "opus": "a", "astra": "a"}, 1, 0, True, False),
    ("one differs", {"fable": "a", "opus": "a", "astra": "b"}, 1, 2, False, False),
    ("degraded one vendor", {"fable": "a", "opus": "a", "astra": None}, 1, 0, True, True),
    ("one vendor below min_vendors", {"fable": "a", "opus": "a", "astra": None}, 2, 2, False, True),
])
def test_verdict_convergence(world, case, votes, min_vendors, code, converged, degraded):
  config_path = world.repo / ".superegm/config.json"
  config = json.loads(config_path.read_text(encoding="utf-8"))
  config.setdefault("judges", {})["min_vendors"] = min_vendors
  config_path.write_text(json.dumps(config), encoding="utf-8")
  pid, card, _ = open_panel(world, text=ONE)
  for judge, option in votes.items():
    assert record(world, pid, card, 1, judge, {"Q1": option} if option else None,
                  not_run=None if option else "no claudex-loop runner")[0] == 0
  got, out = world.run("judges", "verdict", "--panel", pid, "--runcard", card)
  assert got == code, out
  verdict = json.loads(out)
  assert verdict == json.loads((world.artifacts / "judges" / pid / "verdict.json").read_text(encoding="utf-8"))
  q1 = verdict["questions"]["Q1"]
  assert (verdict["converged"], q1["converged"], verdict["degraded"]) == (converged, converged, degraded)
  assert verdict["min_vendors"] == min_vendors and verdict["cap_reached"] is False
  if converged:
    assert (q1["option"], q1["round"]) == ("a", 1)
  if case == "one differs":
    assert q1["positions"] == {"a": ["fable", "opus"], "b": ["astra"]}
  if case == "one vendor below min_vendors":
    assert q1["reason"] == "vendors 1 < min_vendors 2"
  if votes["astra"] is None:
    assert verdict["rounds"]["1"]["astra"]["not_run"] == "no claudex-loop runner"
  assert verdict["judges"]["astra"]["vendor"] == "openai" and verdict["rounds"]["1"]["fable"]["isolation"] == "clean"
  assert (f"judges {pid}: Q1 converged (a) round 1" in journal(world)) is converged


def test_converged_answers_stay_converged_across_rounds(world):
  pid, card, _ = open_panel(world)
  for judge, q2 in (("fable", "a"), ("opus", "b"), ("astra", "b")):
    assert record(world, pid, card, 1, judge, {"Q1": "a", "Q2": q2})[0] == 0
  code, out = world.run("judges", "verdict", "--panel", pid, "--runcard", card)
  assert code == 2 and json.loads(out)["questions"]["Q1"]["converged"] is True, out
  assert world.run("judges", "diff", "--panel", pid, "--round", 1, "--runcard", card)[0] == 0
  for judge in ("fable", "opus", "astra"):
    assert record(world, pid, card, 2, judge, {"Q2": "b"})[0] == 0
  code, out = world.run("judges", "verdict", "--panel", pid, "--runcard", card)
  assert code == 0, out
  questions = json.loads(out)["questions"]
  assert {q: (v["option"], v["round"]) for q, v in questions.items()} == {"Q1": ("a", 1), "Q2": ("b", 2)}
  assert journal(world).count(f"judges {pid}: Q1 converged (a) round 1") == 1
  assert f"judges {pid}: Q2 converged (b) round 2" in journal(world)


def test_cap_of_five_rounds(world):
  pid, card, _ = open_panel(world, text=ONE)
  for rnd in range(1, 6):
    for judge, option in (("fable", "a"), ("opus", "b"), ("astra", "a")):
      assert record(world, pid, card, rnd, judge, {"Q1": option})[0] == 0
    assert world.run("judges", "diff", "--panel", pid, "--round", rnd, "--runcard", card)[0] == 0
  assert not (world.artifacts / "judges" / pid / "round-6").exists()
  code, out = world.run("judges", "verdict", "--panel", pid, "--runcard", card)
  assert code == 2 and json.loads(out)["cap_reached"] is True, out
  code, out = record(world, pid, card, 6, "fable", {"Q1": "a"})
  assert code == 1 and "judges: cap of 5 rounds reached" in out, out
  assert f"judges {pid}: verdict not converged: Q1 (cap reached)" in journal(world)


def test_judge_adapter_and_persona():
  adapter = (ROOT / ".claude-plugin/agents/judge.md").read_text(encoding="utf-8")
  config = yaml.safe_load(adapter.split("---", 2)[1])
  assert config["name"] == "judge" and set(config["tools"]) == {"Read", "Grep", "Glob"}
  assert config["model"] == "inherit" and config["omitClaudeMd"] is True and "memory" not in config
  assert "${CLAUDE_PLUGIN_ROOT}/agents/judge.md" in adapter
  persona = (ROOT / "agents/judge.md").read_text(encoding="utf-8")
  canonical = yaml.safe_load(persona.split("---", 2)[1])
  assert canonical["name"] == "judge" and "tools" not in canonical and "omitClaudeMd" not in canonical
  for phrase in ("Q<n>: (<id>)", "reason:", "would change my mind:", "only the question file and the evidence",
                 "no findings", "option id", "saw:", "never spawn"):
    assert phrase in persona, phrase
  assert "Severity" not in persona and "Mode:" not in persona


def test_judges_skill_body():
  text = (ROOT / "skills/judges/SKILL.md").read_text(encoding="utf-8")
  assert len(text.split("---", 2)[2].encode("utf-8")) <= 24_000
  assert "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first." in text
  for phrase in ("superegm runcard open --skill judges", "superegm judges open", "superegm judges record",
                 "superegm judges diff", "superegm judges verdict", "superegm runcard close", "superegm:judge",
                 "run_in_background", "SUPEREGM_ROLE=goldfish", "no one adds arguments between rounds",
                 "advisory", "references/astra_judge.md", "concurrently", "degraded", "round-<n>/brief.md",
                 "--isolation", "saw:", "cap of 5"):
    assert phrase in text, phrase
  assert "--judges 1" not in text and "--cap" not in text
  ref = (ROOT / "skills/judges/references/astra_judge.md").read_text(encoding="utf-8")
  for phrase in ("Modified by SuperEGM (gsVAM), 2026", "review --host claude", "--plan '<QUESTION_FILE>'",
                 "--feedback", "--timeout 1800", "result.json", "--result", "not run (", "fresh session"):
    assert phrase in ref, phrase
  scenarios = yaml.safe_load((ROOT / "skills/judges/test_scenarios.yaml").read_text(encoding="utf-8"))
  assert scenarios["skill"] == "judges"
  assert {s["scenario_id"] for s in scenarios["scenarios"]} >= {"advisory_never_applies", "astra_down_runs_claude_only"}


REMOVED = ("--judges 1", "--judges 3", "Blocker |", "| Major", "| Nit", "synthesizer", "goldfish_dispositions",
           "EGM_ASTRA", "Mode: BRAINSTORM")
# EGM's own names (egm-<skill>, egm:<skill>, egm_handoff); SuperEGM's (superegm:judge, superegm-judges) are not removed forms.
EGM_NAME_RE = re.compile(r"(?<!super)egm[-:_]")


@pytest.mark.parametrize("path", [
    "skills/judges/SKILL.md", "skills/judges/references/astra_judge.md", "skills/judges/test_scenarios.yaml",
    "agents/judge.md", ".claude-plugin/agents/judge.md", "skills/plan/scripts/superegm/judges.py",
])
def test_no_removed_forms(path):
  text = (ROOT / path).read_text(encoding="utf-8")
  for term in REMOVED:
    assert term not in text, f"{path}: {term}"
  assert not EGM_NAME_RE.search(text), f"{path}: {EGM_NAME_RE.search(text).group()}"
