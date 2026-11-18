# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U62

"""U62 (spec sections 6.1 and 4.2): a pull request GitHub reads `CONFLICTING` gives its unit the view status
`conflict`; a clean or proceeded head with no launch since its authorizing outcome's launch is relaunched once for a
merge round, a revising unit's next fix round carries the merge orders `with-fix`, and every such launch fetches and
pins the current base, briefs the builder from `git merge-tree --write-tree` and admits `Bash(git merge:*)` alone."""

import json
from pathlib import Path

import pytest

import superegm
from superegm import status
from test_events import seed as status_seed, pr as status_pr


@pytest.mark.parametrize("mergeable, status_word, ci, changed", [
  ("CONFLICTING", "conflict", "green", True),
  ("MERGEABLE", "ci green", "green", False),
  ("UNKNOWN", "ci green", "green", False),
])
def test_conflict_view(world, monkeypatch, mergeable, status_word, ci, changed):
  # §6.1: conflict is set after the CI column is read, so ci keeps its value; UNKNOWN is read again next pass
  gh, st, card = status_seed(world, monkeypatch)
  node = status_pr(gh, "green")
  node["mergeable"] = "MERGEABLE"
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  handoff = superegm.Handoff(Path(state["plan"]), st, state)
  saved_view = status.fingerprint(status.unit_view(handoff, "U01"))
  node["mergeable"] = mergeable
  fresh = status.unit_view(handoff, "U01")
  view = status.fingerprint(fresh)
  assert fresh["status"] == status_word and view["ci"] == ci
  assert (view != saved_view) == changed
  assert bool(status.unit_events("U01", saved_view, view)) == changed  # the view change `tick_trigger` and `wait_events` read
  assert handoff.state["units"]["U01"]["pr"]["mergeable"] == mergeable  # the saved pull request `launch-builder` reads


# ---------------------------------------------------------------- S2: the `again` set's conflict rule


from conftest import REPO, make_pr  # noqa: E402
from superegm import spec_slug  # noqa: E402
from test_builders import spawn_fake, no_graphify, which  # noqa: E402,F401  the fixtures `launch-builder` and `launch` need
from test_builders import seed, put, launches_of, git  # noqa: E402

HEAD = "a" * 40
CLEAN = {"round": 1, "runcard": "c", "launch": 1, "head": HEAD, "phase": "posted", "dispatch_id": "d1", "outcome": "clean",
         "posted_at": "2026-11-03T01:00:00Z"}
REVISE = {**CLEAN, "outcome": "revise"}


def proceed_entry(launch_n, head=HEAD):
  return {"ruling": f"R{launch_n}", "review": "head-U01-c1", "head": head, "launch": launch_n}


def with_rounds(s, world, rounds=3):
  """The handoff's approval entry extended under 1.2.1 (spec section 6): `rounds` set."""
  spec = next(world.repo.glob("docs/**/*.md")).resolve()
  path = s.path("approvals", f"{spec_slug(spec)}.json")
  record = json.loads(path.read_text(encoding="utf-8"))
  put(path, json.dumps({**record, "rounds": rounds}))


def write_launches(s, uid, *entries):
  """`launches/<uid>.json` with one entry per (round, status); an `exited` one's exit file written."""
  rows = []
  for rnd, status_text in entries:
    entry = {"round": rnd, "worktree": str(s.path("worktrees", uid, f"r{rnd}")), "branch": f"superegm/h/{uid}",
             "started_at": "2026-11-03T00:00:00Z", "status": status_text,
             "result_file": str(s.path("launches", f"{uid}_r{rnd}_result.json")), "prompt_sha256": "0" * 64}
    if status_text.startswith("exited"):
      put(Path(entry["result_file"] + ".exit"), status_text.split()[1] + "\n")
    rows.append(entry)
  put(s.path("launches", f"{uid}.json"), json.dumps({"launches": rows}))


def write_foreman(s, uid, rounds=(), proceeds=(), decisions=()):
  put(s.path("foreman", uid), json.dumps({"dispatch_id": "d1", "rounds": list(rounds), "decisions": list(decisions),
                                          "rulings": [], "proceeds": list(proceeds)}))


def open_pr(world, mergeable, head=HEAD, number=71, issue=7):
  """The unit's open pull request (closing issue #`issue`), CI green on `head`, GitHub reading `mergeable`."""
  node = make_pr(world.gh, number, head, closes=[(REPO, issue)])
  node["mergeable"] = mergeable
  world.gh.graphql[issue] = [{**node, "repository": {"nameWithOwner": REPO}}]
  world.gh.check_runs[head] = [{"name": "tests", "status": "completed", "conclusion": "success"}]
  world.gh.combined[head] = {"state": "success", "statuses": []}
  return node


def marked(out):
  line = next(line for line in out.splitlines() if line.startswith("marked: "))
  return [] if line == "marked: none" else line[len("marked: "):].split(", ")


@pytest.mark.parametrize("case, marked_first, marked_second", [
  ("clean, CONFLICTING", ["U01"], []),
  ("clean, MERGEABLE", [], []),
  ("clean, UNKNOWN", [], []),
  ("clean, CONFLICTING, launch running", [], []),
  ("clean, CONFLICTING, open decision D1", [], []),
  ("clean, CONFLICTING, approval without rounds", [], []),
  ("proceeded with no posted round, CONFLICTING", ["U01"], []),
  ("merge round recorded, second proceed, CONFLICTING again", ["U01"], []),
])
def test_conflict_relaunches_once(world, monkeypatch, case, marked_first, marked_second):
  # §6.1/§4.2: again takes a conflict unit with no launch since its authorizing outcome's launch
  s, card, hid, _ = seed(world, units=("U01",))
  if "without rounds" not in case:
    with_rounds(s, world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and marked(out) == ["U01"], out  # the unit's first launch
  mergeable = next(word for word in ("CONFLICTING", "MERGEABLE", "UNKNOWN") if word in case)
  open_pr(world, mergeable)
  rounds, proceeds, decisions, runs = [CLEAN], [], [], [(1, "exited 0")]
  if "launch running" in case:
    runs = [(1, "running")]
  if "open decision" in case:
    decisions = [{"id": "D1", "point": 3}]
  if case.startswith("proceeded"):
    rounds, proceeds = [], [proceed_entry(1)]
  if case.startswith("merge round recorded"):  # a first conflict's merge round ran, the owner proceeded on its head again
    proceeds, runs = [proceed_entry(1), proceed_entry(2)], [(1, "exited 0"), (2, "exited 0")]
  write_foreman(s, "U01", rounds, proceeds, decisions)
  write_launches(s, "U01", *runs)
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and marked(out) == marked_first, out
  # the merge launch (or none) recorded: the next pass marks nothing again
  if marked_first:
    runs = runs + [(runs[-1][0] + 1, "running")]
    write_launches(s, "U01", *runs)
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and marked(out) == marked_second, out
