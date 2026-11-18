# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U68

"""U68 (spec 1.2.1 section 6.4): a unit whose current head cycle has `builder.escalate_after` failing posted rounds
launches on the `difficult` tier's pair, records `tier: difficult` and `escalated: true` (so the new model starts a
fresh session) and stays escalated for the rest of its rounds; `0`, a unit planned `difficult` and a config with no
`difficult` row change nothing."""

import json

import pytest

import superegm
from test_builders import launches_of, UNIT, no_graphify, which  # noqa: F401  the autouse fixtures
from test_u63 import started, resumable, launch_round, write_launches, ended, profile_of  # noqa: F401  `started` is a fixture

DIFFICULT = {"model": "claude-fable-5-2", "effort": "high"}  # a row with its own model: the gain in model needs one


def finding(fid, claim="a fault", severity="high"):
  return {"id": fid, "severity": severity, "disposition": None, "claim": claim, "location": "a.py:1", "regression": "no"}


def round_of(n, word):
  """`(foreman rounds[] entry, round file or None)` for the outcome `word` of round `n`, the form `contested: <what>`
  naming what its open findings are."""
  entry = {"round": n, "phase": "posted", "outcome": word}
  if word.startswith("not run"):
    return entry | {"phase": "collected"}, None
  contest = finding(f"foreman-{n}-1")  # the builder's contest, waiting on a ruling
  findings = {"contested: open high": [contest, finding(f"foreman-{n}-2")],
              "contested: builder contest only": [contest],
              "contested: test-delta only": [contest, finding(f"foreman-{n}-2", "test-delta: tests/unit/test_x.py")],
              "contested: unruled point-1 only": [contest, finding(f"foreman-{n}-2", "changed path outside Scope paths")],
              "owner: medium-1": [finding(f"foreman-{n}-1", "test-delta: tests/unit/test_x.py", "medium")]}.get(word, [finding(f"foreman-{n}-1")])
  if word.startswith("contested:"):
    word = entry["outcome"] = f"contested: foreman-{n}-1"
  rnd = {"round": n, "reviewers": {"foreman": {"findings": findings}},
         "builder_contested": [{"fid": f"foreman-{n}-1"}] if word.startswith("contested:") else []}
  return entry, rnd


def store_rounds(s, rounds, planned, escalate_after, difficult_row=True, earlier=False):
  """The unit's head cycles and foreman rounds as the words `rounds` read (`proceed` closes the cycle, `... merge: true`
  marks a merge round), its planned tier and the builder's config; the launch file's first entry escalated when `earlier`."""
  from superegm import review
  cycle, entries, data = 1, [], superegm.load_foreman(s, UNIT)
  rid, opened = review.review_id(s, "head", UNIT, cycle), {}
  opened[rid] = {"kind": "head", "artifact": UNIT, "cycle": cycle, "rulings": []}
  for word in rounds:
    if word == "proceed":
      opened[rid]["rulings"].append({"id": "R1", "ruling": "proceed", "by": "owner"})
      cycle += 1
      rid = review.review_id(s, "head", UNIT, cycle)
      opened[rid] = {"kind": "head", "artifact": UNIT, "cycle": cycle, "rulings": []}
      continue
    merge = word.endswith(" merge: true")
    entry, rnd = round_of(len(entries) + 1, word.removesuffix(" merge: true"))
    entries.append(entry | ({"merge": True} if merge else {}))
    if rnd:
      superegm.atomic_write(s.path("reviews", rid, f"round-{entry['round']}.json"), rnd)
  for name, review_json in opened.items():
    superegm.atomic_write(s.path("reviews", name, "review.json"), review_json)
  data["rounds"] = entries
  superegm.save_foreman(s, UNIT, data)
  units = json.loads(s.path("units").read_text(encoding="utf-8")) if s.path("units").is_file() else {"units": {}}
  units["units"].setdefault(UNIT, {})["tier"] = planned
  superegm.atomic_write(s.path("units"), units)
  path = s.path("launches", f"{UNIT}.json")
  launches = json.loads(path.read_text(encoding="utf-8"))["launches"]
  launches[0] |= {"escalated": True} if earlier else {}
  superegm.atomic_write(path, {"launches": launches})


def configure(world, escalate_after, difficult_row=True):
  path = world.repo / ".superegm/config.json"
  config = json.loads(path.read_text(encoding="utf-8"))
  config["builder"]["escalate_after"] = escalate_after
  config["builder"]["tiers"] = {"difficult": DIFFICULT} if difficult_row else {"easy": {"model": "claude-sonnet-5-5", "effort": "medium"}}
  path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
  return config


def second_launch(world, s, card, rounds, planned, escalate_after=2, difficult_row=True, earlier=False):
  """Round 1 launched and ended as a resume needs, the store as `rounds` say, then launch 2: its entry and its prompt."""
  from superegm import launch_builder
  resumable(world, s, card)
  config = configure(world, escalate_after, difficult_row)
  store_rounds(s, rounds, planned, escalate_after, difficult_row, earlier)
  made = []
  real = launch_builder.prompt_text
  launch_builder.prompt_text = lambda *a, **k: made.append(real(*a, **k)) or made[-1]
  try:
    launch_round(world, card, 2)
  finally:
    launch_builder.prompt_text = real
  return launches_of(s)[-1], made[-1], config


@pytest.mark.parametrize("planned, rounds, tier", [
  ("doable", ["revise", "revise"], "difficult"),
  ("doable", ["revise", "cap-reached"], "difficult"),
  ("easy", ["revise", "revise"], "difficult"),
  ("doable", ["revise"], "doable"),
  ("doable", ["revise", "contested: open high"], "difficult"),
  ("doable", ["revise", "contested: builder contest only"], "doable"),
  ("doable", ["revise", "contested: test-delta only"], "doable"),
  ("doable", ["revise", "contested: unruled point-1 only"], "doable"),
  ("doable", ["revise", "not run (timeout)"], "doable"),
  ("doable", ["revise", "revise merge: true"], "doable"),
  ("doable", ["revise", "owner: medium-1"], "doable"),
  ("doable", ["revise", "revise", "proceed", "revise"], "doable")])
def test_failing_head_rounds_escalate(world, started, planned, rounds, tier):
  # a difficult row with its own model; escalate_after 2 over the current head cycle's counted rounds
  s, card, _ = started
  entry, brief, config = second_launch(world, s, card, rounds, planned)
  assert (entry["tier"], entry.get("escalated")) == (tier, True if tier != planned else None)
  assert (entry["model"], entry["effort"]) == superegm.tier_pair(config, tier)
  assert entry.get("fresh") == ("model changed" if tier != planned else entry.get("fresh"))
  # the same round unescalated: the fix brief is the prompt's text beside the resume's stale-paths line
  from superegm import launch_builder
  write_launches(s, launches_of(s)[:1])
  superegm.run_git(["checkout", "--detach"], s.path("worktrees", UNIT, "r2"))  # the first launch's worktree, free to reuse
  configure(world, 0)
  store_rounds(s, rounds, planned, 0)
  made = []
  real = launch_builder.prompt_text
  launch_builder.prompt_text = lambda *a, **k: made.append(real(*a, **k)) or made[-1]
  try:
    launch_round(world, card, 2)
  finally:
    launch_builder.prompt_text = real
  assert made[-1] == brief


@pytest.mark.parametrize("after", ["proceed", "merge: true"])
def test_an_escalated_unit_stays_escalated(world, started, after):
  # an earlier launch entry with escalated: true keeps every later launch difficult
  s, card, _ = started
  rounds = ["revise", "revise", "proceed", "revise"] if after == "proceed" else ["revise", "revise merge: true"]
  entry, _, config = second_launch(world, s, card, rounds, "doable", earlier=True)
  assert (entry["tier"], entry["escalated"]) == ("difficult", True)
  assert (entry["model"], entry["effort"]) == superegm.tier_pair(config, "difficult")
