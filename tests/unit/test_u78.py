# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U78's tests: a wait's journaled and kept history, and `superegm postmortem` (spec section 7.5).

"""U78: the post-mortem, and the wait history it reads."""

import hashlib
import json
import re

import pytest
from conftest import CONFIG, ROOT
from test_u43 import Chain, jread
from test_u43 import registry  # noqa: F401  (the autouse fixture: no test reads the owner's registry)
import superegm


def sha(text):
  return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stamp(world):
  """The store's stamp of the world's clock."""
  return superegm.iso(world.clock)


def chain_world(world):
  """A chained handoff whose owner is `owner` and whose `gh api user` answers `owner`."""
  path = world.repo / CONFIG
  config = json.loads(path.read_text(encoding="utf-8"))
  path.write_text(json.dumps({**config, "owners": ["owner"]}), encoding="utf-8")
  world.gh.extend("api", lambda args, cwd, token=None: (0, "owner\n", ""))
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
    assert f"next clear {c.hid} plan answered by owner at {at1} answer {sha('first answer')}" in journal_of(c)
    assert (waits / f"plan-{since2}.md").is_file()
  assert (waits / f"plan-{since1}.answer.json").read_bytes() == first_bytes
  assert (waits / f"plan-{since1}.answer.md").read_text(encoding="utf-8") == "first answer"
  assert (waits / f"plan-{since1}.md").read_text(encoding="utf-8") == "split U02?"
  world.advance(60)
  at2 = answer(world, c, "second answer")
  assert (waits / f"plan-{since1}.answer.json").read_bytes() == first_bytes
  second = json.loads((waits / f"plan-{since2}.answer.json").read_text(encoding="utf-8"))
  assert second == {"by": "owner", "at": at2, "sha": sha("second answer")}
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
    c.filed(uid, n, pr={"number": 10 + n, "merged_at": merged[uid]}, ci=None, landed=True)
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
                                       "rounds": [{"round": 1, "outcome": "posted"}]})
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
