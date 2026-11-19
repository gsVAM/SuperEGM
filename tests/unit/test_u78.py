# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U78's tests: a wait's journaled and kept history, and `superegm postmortem` (spec section 7.5).

"""U78: the post-mortem, and the wait history it reads."""

import hashlib
import json
import re

import pytest
from conftest import CONFIG, ROOT
from test_u43 import UNITS, Chain, jread
from test_u43 import registry  # noqa: F401  (the autouse fixture: no test reads the owner's registry)
import superegm


LOGIN = "alice"  # the owner's GitHub login: the report calls it `owner`


def sha(text):
  return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stamp(world):
  """The store's stamp of the world's clock."""
  return superegm.iso(world.clock)


def chain_world(world):
  """A chained handoff whose owner is the login `alice` and whose `gh api user` answers `alice`."""
  path = world.repo / CONFIG
  config = json.loads(path.read_text(encoding="utf-8"))
  path.write_text(json.dumps({**config, "owners": [LOGIN]}), encoding="utf-8")
  world.gh.extend("api", lambda args, cwd, token=None: (0, LOGIN + "\n", ""))
  return Chain(world)


def wait(world, c, phase, question):
  """`next wait` on a fresh card of `phase`'s skill; the `at` it is stamped with."""
  at = stamp(world)
  card = world.open_card(phase, c.spec)
  code, out = world.run("next", "wait", "--handoff", c.hid, "--phase", phase, "--question", question, "--runcard", card)
  assert code == 0, out
  return at


def answer(world, c, text):
  code, out = world.run("next", "answer", "--handoff", c.hid, "--answer", text)
  assert code == 0, out
  return stamp(world)


def journal_of(c):
  """The handoff journal's `next ...` lines, each without its leading timestamp."""
  path = c.hs.path("journal")
  lines = [line.split(" ", 1)[1] for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []
  return [line for line in lines if line.startswith("next ")]


def test_reask_keeps_the_first_answer(world):
  c = chain_world(world)
  waits = c.hs.path("file", "waits")
  q1, q2 = "split U02?", "split U02 and U03?"
  since1 = wait(world, c, "plan", q1)
  assert journal_of(c)[-1].startswith(f"next wait {c.hid} plan since {since1} source ")
  assert journal_of(c)[-1].endswith(f" question {sha(q1)}")
  assert (waits / f"plan-{since1}.md").read_text(encoding="utf-8") == q1
  world.advance(60)
  answer(world, c, "first answer")
  # a re-ask: the skill's `next wait` on a phase whose record holds an answer
  world.advance(60)
  at2 = wait(world, c, "plan", q2)
  record = jread(c.root / "chain" / f"{c.hid}.json")
  assert (waits / f"plan-{since1}.answer.md").read_text(encoding="utf-8") == "first answer"
  assert journal_of(c)[-1] == f"next reask {c.hid} plan at {at2} question {sha(q2)}"
  assert record["since"] == at2 and (waits / f"plan-{at2}.md").read_text(encoding="utf-8") == q2
  assert (waits / f"plan-{since1}.md").read_text(encoding="utf-8") == q1
  world.advance(60)
  answer(world, c, "second answer")
  assert (waits / f"plan-{at2}.answer.md").read_text(encoding="utf-8") == "second answer"
  assert (waits / f"plan-{since1}.answer.md").read_text(encoding="utf-8") == "first answer"


@pytest.mark.parametrize("event", ["reask", "stop then next clear then a second answer"])
def test_answer_json_is_never_rewritten(world, event):
  c = chain_world(world)
  c.save()
  waits = c.hs.path("file", "waits")
  since1 = wait(world, c, "plan", "split U02?")
  world.advance(60)
  at1 = answer(world, c, "first answer")
  first_bytes = (waits / f"plan-{since1}.answer.json").read_bytes()
  world.advance(60)
  if event == "reask":
    since2 = wait(world, c, "plan", "split U02 and U03?")
  else:
    since2 = stamp(world)
    card = world.open_card("plan", c.spec)
    code, out = world.run("next", "clear", "--handoff", c.hid, "--runcard", card)
    assert code == 0, out
    # the stopped record is a new wait: its own since, its question kept, the answered one's line journaled
    assert jread(c.root / "chain" / f"{c.hid}.json")["since"] == since2
    assert f"next clear {c.hid} plan answered by {LOGIN} at {at1} answer {sha('first answer')}" in journal_of(c)
    assert (waits / f"plan-{since2}.md").is_file()
  assert (waits / f"plan-{since1}.answer.json").read_bytes() == first_bytes
  assert (waits / f"plan-{since1}.answer.md").read_text(encoding="utf-8") == "first answer"
  assert (waits / f"plan-{since1}.md").read_text(encoding="utf-8") == "split U02?"
  world.advance(60)
  at2 = answer(world, c, "second answer")
  assert (waits / f"plan-{since1}.answer.json").read_bytes() == first_bytes
  second = json.loads((waits / f"plan-{since2}.answer.json").read_text(encoding="utf-8"))
  assert second == {"by": LOGIN, "at": at2, "sha": sha("second answer")}
  assert set(second) == {"by", "at", "sha"}


def test_same_second_reask_keeps_the_first_wait(world):
  """The store's stamps have one-second precision: a re-ask in the second of the first wait and answer must not
  reuse the first `since`, whose question and answer files stay as they were."""
  c = chain_world(world)
  waits = c.hs.path("file", "waits")
  since1 = wait(world, c, "plan", "first question?")
  answer(world, c, "first answer")
  wait(world, c, "plan", "second question?")  # the clock has not moved
  since2 = jread(c.root / "chain" / f"{c.hid}.json")["since"]
  assert since2 != since1
  assert (waits / f"plan-{since1}.md").read_text(encoding="utf-8") == "first question?"
  assert (waits / f"plan-{since2}.md").read_text(encoding="utf-8") == "second question?"
  first_json = (waits / f"plan-{since1}.answer.json").read_bytes()
  answer(world, c, "second answer")
  assert (waits / f"plan-{since1}.answer.md").read_text(encoding="utf-8") == "first answer"
  assert (waits / f"plan-{since1}.answer.json").read_bytes() == first_json
  assert (waits / f"plan-{since2}.answer.md").read_text(encoding="utf-8") == "second answer"
  assert journal_of(c)[-1] == f"next reask {c.hid} plan at {since2} question {sha('second question?')}"


def test_clear_of_a_proceeded_wait_journals_the_ruling_after_since(world):
  """A wait record a `proceed` ruling resolves holds no answer: its clear line names the latest `proceed` ruling made
  after the wait's `since` (not an older one), with the empty answer's sha256."""
  c = chain_world(world)
  c.plan(*UNITS)
  c.state["units"] = {}
  c.review("U01", converged="no", rulings=[
      {"id": "R1", "ruling": "proceed", "by": "bob", "at": "2026-11-14T00:00:00Z"},  # before the wait: not its answer
      {"id": "R2", "ruling": "proceed", "by": "carol", "at": "2026-11-15T02:00:00Z"}])
  c.wait(phase="review-plan", question="q", review="plan-U01-c1")  # since 2026-11-15T00:00:00Z
  c.save()
  card = world.open_card("plan", c.spec)
  code, out = world.run("next", "clear", "--handoff", c.hid, "--runcard", card)
  assert code == 0, out
  assert not (c.root / "chain" / f"{c.hid}.json").is_file()
  assert journal_of(c)[-1] == f"next clear {c.hid} review-plan answered by carol at 2026-11-15T02:00:00Z answer {sha('')}"


def jwrite(path, obj):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(obj), encoding="utf-8")


def table(report, section):
  """A section's table, first column to row: `{key: {column: cell}}`."""
  body = report.split(f"## {section}\n", 1)[1].split("\n## ", 1)[0]
  rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in body.splitlines() if line.startswith("|")]
  return {row[0]: dict(zip(rows[0], row)) for row in rows[2:]}


def two_units(world):
  """A chained handoff of U01 (two launches, the second escalated, one head round) and U02 (one launch), both merged;
  the plan phase waited twice, the second wait a re-ask, each answered by the owner. Returns the chain and the two
  waits' lengths in seconds."""
  c = chain_world(world)
  c.plan("U01", "U02")
  merged = {"U01": "2026-11-15T09:00:00Z", "U02": "2026-11-15T07:00:00Z"}
  for n, uid in enumerate(("U01", "U02"), 1):
    c.filed(uid, n, pr=10 + n, ci=None, landed=True)  # the status view holds the PR's number ...
    c.state["units"][uid]["pr"] = {"number": 10 + n, "merged_at": merged[uid]}  # ... the unit's record the whole PR
    c.hs.path("unit", uid).write_text(
        "## Issue body as posted\n\n````markdown\n## Steps\n1. Write the failing test `a` in `t.py`:\n"
        "2. Write the failing test `b` in `t.py`:\n````\n", encoding="utf-8")
  c.save()
  jwrite(c.hs.path("units"), {"order": ["U01", "U02"], "waves": {"1": ["U01"], "2": ["U02"]}, "critical_path": ["U01"],
                              "units": {"U01": {"wave": 1, "tier": "doable", "size": "M"},
                                        "U02": {"wave": 2, "tier": "easy", "size": "S"}}})
  launch = {"status": "exited 0", "subagent_calls": {"count": 1, "calls": []}}
  jwrite(c.hs.path("launches", "U01"), {"launches": [
      {**launch, "round": 1, "started_at": "2026-11-15T01:00:00Z", "model": "claude-sonnet-5-5", "fresh": "first round",
       "effective_model": "claude-sonnet-5-5", "total_cost_usd": 0.5},
      {**launch, "round": 2, "started_at": "2026-11-15T05:00:00Z", "model": "claude-opus-5-5", "resumed_from": "s1",
       "escalated": True, "effective_model": "claude-opus-5-5", "total_cost_usd": 0.25}]})
  jwrite(c.hs.path("launches", "U02"), {"launches": [
      {**launch, "round": 1, "started_at": "2026-11-15T02:00:00Z", "model": "claude-sonnet-5-5", "fresh": "first round"}]})
  jwrite(c.hs.path("foreman", "U01"), {"dispatch_id": None, "decisions": [], "rulings": [],
                                       "rounds": [{"round": 1, "phase": "posted", "outcome": "posted"},
                                                  {"round": 2, "phase": "collected", "outcome": "not run (superseded)"}]})
  world.advance(100)
  wait1, wait2 = 600, 300
  wait(world, c, "plan", "split U02?")
  world.advance(wait1)
  answer(world, c, "first answer")
  world.advance(50)
  wait(world, c, "plan", "split U02 and U03?")
  world.advance(wait2)
  answer(world, c, "second answer")
  return c, wait1, wait2


def test_tables_carry_the_store_numbers(world):
  c, wait1, wait2 = two_units(world)
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  report = c.hs.path("file", "postmortem.md").read_text(encoding="utf-8")
  assert re.findall(r"^## (.+)$", report, re.M) == ["Header", "Units", "Reviewers", "Owner time", "Plan against actual"]
  units = table(report, "Units")
  assert units["U01"]["escalated"] == "1" and units["U02"]["escalated"] == "0"
  assert (units["U01"]["launches"], units["U01"]["fresh"], units["U01"]["resumed"]) == ("2", "1", "1")
  assert units["U01"]["wall seconds"] == str(8 * 3600) and units["U02"]["wall seconds"] == str(5 * 3600)
  assert units["U01"]["cost usd"] == "0.75" and units["U01"]["head rounds"] == "1"
  owner_time = table(report, "Owner time")
  assert owner_time["plan"]["waited"] == str(wait1 + wait2)
  assert owner_time["plan"]["answered by"] == "owner"
  plan = table(report, "Plan against actual")
  assert (plan["U01"]["planned steps"], plan["U01"]["wave"], plan["U01"]["merge order"]) == ("2", "1", "2")
  assert plan["U02"]["merge order"] == "1"


def test_header_carries_the_total_wall_time(world):
  """First launch to last merge, in one Header field, and the Header's other fields: the integrate skill reads them."""
  c, _, _ = two_units(world)
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  header = table(c.hs.path("file", "postmortem.md").read_text(encoding="utf-8"), "Header")
  assert header["total wall seconds"]["value"] == str(8 * 3600)  # U01's first launch 01:00 to U01's merge 09:00
  assert (header["units"]["value"], header["waves"]["value"], header["handoff"]["value"]) == ("2", "2", c.hid)
  assert header["closed"]["value"] == "in progress"


def reviewed(c, rid, kind, uid, reviewers, found):
  """A review cycle of `uid` with its round 1: `found` is `{reviewer: record}`."""
  jwrite(c.hs.path("reviews", rid, "review.json"), {"kind": kind, "artifact": uid, "cycle": 1, "reviewers": reviewers,
                                                    "runcard": "rc", "converged": "no", "rulings": []})
  jwrite(c.hs.path("reviews", rid, "round-1.json"), {"round": 1, "runcard": "rc", "reviewers": found})


def test_reviewers_count_each_units_own_verdicts(world):
  """Finding ids repeat across units (`<reviewer>-<round>-<n>`): U01's overrule is not U02's; a reviewer that was not
  run (its own `not_run`) has no quiet round; a settled plan finding `declined` is overruled; a superseded round is none."""
  c, _, _ = two_units(world)
  posted = {"round": 1, "phase": "posted", "outcome": "posted"}
  jwrite(c.hs.path("foreman", "U01"), {"dispatch_id": None, "decisions": [], "rounds": [posted],
                                       "rulings": [{"ruling": "codebase-details-1-1 finding overruled — not a defect", "by": "owner"}]})
  jwrite(c.hs.path("foreman", "U02"), {"dispatch_id": None, "decisions": [], "rounds": [posted], "rulings": []})
  panel = ["codebase-details", "codex"]
  reviewed(c, "head-U01-c1", "head", "U01", panel,
           {"codebase-details": {"findings": [{"id": "codebase-details-1-1", "severity": "high", "regression": "no"}]},
            "codex": {"findings": [], "not_run": "unavailable"}})
  reviewed(c, "head-U02-c1", "head", "U02", panel,
           {"codebase-details": {"findings": [{"id": "codebase-details-1-1", "severity": "medium", "regression": "yes",
                                                "disposition": "fixed"}]},
            "codex": {"findings": []}})
  reviewed(c, "plan-U01-c1", "plan", "U01", ["readiness"],
           {"readiness": {"findings": [{"id": "readiness-1-1", "severity": "low", "disposition": "declined", "ruling": "owner"},
                                       {"id": "readiness-1-2", "severity": "low", "disposition": "deferred: triage 2"}]}})
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  report = c.hs.path("file", "postmortem.md").read_text(encoding="utf-8")
  reviewers = table(report, "Reviewers")
  details = reviewers["codebase-details"]
  assert (details["kind"], details["high"], details["medium"], details["fixed"]) == ("head", "1", "1", "1")
  assert (details["overruled"], details["allowed"], details["regressions"], details["quiet rounds"]) == ("1", "0", "1", "0")
  assert reviewers["codex"]["quiet rounds"] == "1"  # U02's empty record; U01's `not_run` is no round
  assert (reviewers["readiness"]["overruled"], reviewers["readiness"]["deferred"]) == ("1", "1")
  assert table(report, "Units")["U01"]["head rounds"] == "1"


def journal_add(c, *lines):
  path = c.hs.path("journal")
  with path.open("a", encoding="utf-8") as handle:
    handle.write("".join(line + "\n" for line in lines))


def test_owner_time_holds_every_decision_proceed_and_stop(world):
  """Every wait, decision, `proceed` and stop is a row; a wait the driver removed ends there, an unanswered wait a later
  wait replaces ends at that wait, a decision's answer time falls back to its review's ruling; logins read as `owner`."""
  c, _, _ = two_units(world)
  hid, t = c.hid, "2026-11-15T"
  c.state["decisions"] = {"U01/D1": {"answer": "(a)", "by": "owner", "decided_at": t + "00:30:00Z", "mode": "typed"}}
  c.save()
  jwrite(c.hs.path("foreman", "U01"), {
      "dispatch_id": None, "rounds": [{"round": 1, "phase": "posted", "outcome": "posted"}],
      "decisions": [{"id": "D2", "asked_at": t + "05:00:00Z", "source": "cap"}],
      "rulings": [{"decision": "D2", "ruling": "proceed", "by": "owner", "reason": "ok", "review": "R1"}]})
  jwrite(c.hs.path("foreman", "U02"), {"dispatch_id": None, "rounds": [], "decisions": [], "rulings": [],
                                       "stopped": {"by": "superegm", "at": t + "08:00:00Z", "reason": "cap"}})
  reviewed(c, "head-U01-c1", "head", "U01", ["codebase-details"], {})
  review = jread(c.hs.path("reviews", "head-U01-c1", "review.json"))
  review["rulings"] = [{"id": "R1", "ruling": "proceed", "by": LOGIN, "at": t + "06:00:00Z", "reason": "ok"}]
  jwrite(c.hs.path("reviews", "head-U01-c1", "review.json"), review)
  reviewed(c, "plan-U02-c1", "plan", "U02", ["readiness"], {})
  review = jread(c.hs.path("reviews", "plan-U02-c1", "review.json"))
  review["rulings"] = [{"id": "R1", "ruling": "stop", "by": "owner", "at": t + "03:00:00Z"}]
  jwrite(c.hs.path("reviews", "plan-U02-c1", "review.json"), review)
  journal_add(
      c,
      f"{t}10:00:00Z next wait {hid} review-plan since {t}10:00:00Z source rc question aa",
      f"{t}10:05:00Z driver: {hid} superseded: wait record removed",
      f"{t}11:00:00Z next wait {hid} review-code since {t}11:00:00Z source rc question bb",
      f"{t}11:01:40Z next wait {hid} review-code since {t}11:01:40Z source rc question cc",
      f"{t}11:06:40Z next clear {hid} review-code answered by progress at {t}11:06:40Z answer dd")
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  rows = table(c.hs.path("file", "postmortem.md").read_text(encoding="utf-8"), "Owner time")
  assert (rows["review-plan"]["waited"], rows["review-plan"]["answered at"]) == ("300", t + "10:05:00Z")
  assert rows["review-code"]["waited"] == "400"  # 100 until the second wait replaced the first, 300 more until the clear
  assert (rows["U01/D1"]["kind"], rows["U01/D1"]["answered by"], rows["U01/D1"]["answered at"]) == ("decision", "owner", t + "00:30:00Z")
  assert (rows["U01 D2"]["waited"], rows["U01 D2"]["answered by"], rows["U01 D2"]["answered at"]) == ("3600", "owner", t + "06:00:00Z")
  assert (rows["head-U01-c1 R1"]["kind"], rows["head-U01-c1 R1"]["answered by"]) == ("proceed", "owner")
  assert (rows["plan-U02-c1 R1"]["kind"], rows["plan-U02-c1 R1"]["answered at"]) == ("stop", t + "03:00:00Z")
  assert (rows["U02 stopped"]["kind"], rows["U02 stopped"]["answered by"]) == ("stop", "default")


def snapshot(root):
  return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_postmortem_reads_the_store_only(world):
  from superegm import postmortem
  c, _, _ = two_units(world)
  before = snapshot(c.root)
  code, out = world.run("postmortem", "--handoff", c.hid)
  after = snapshot(c.root)
  report_path = c.hs.path("file", "postmortem.md")
  assert code == 0, out
  assert postmortem.WRITES == frozenset({"file"})
  assert out.strip() == str(report_path)
  assert set(after) - set(before) == {report_path}
  assert {p for p in before if after[p] != before[p]} == set()
  assert "in progress" in report_path.read_text(encoding="utf-8").split("## Units")[0]


def test_integrate_reports_the_postmortem():
  text = (ROOT / "skills/integrate/SKILL.md").read_text(encoding="utf-8")
  assert "superegm postmortem --handoff" in text
  for phrase in ("total wall time", "the most rounds", "the most overruled"):
    assert phrase in text
