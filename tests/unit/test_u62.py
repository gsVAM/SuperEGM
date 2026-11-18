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


# ---------------------------------------------------------------- S3: the merge orders on a launch


def first_round(world, s, card, uid="U07", number=71):
  """`launch`, round 1 launched and exited, its pull request #`number` open at the base's commit; the head returned."""
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", uid, "--round", 1, "--runcard", card)[0] == 0
  Path(launches_of(s, uid)[0]["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", uid, "--exit", 0, "--runcard", card)[0] == 0
  head = git(["rev-parse", "refs/superegm/base"], world.repo).strip()
  git(["update-ref", f"refs/pull/{number}/head", head], world.repo.parent / "origin.git")
  make_pr(world.gh, number, head, closes=[(REPO, 7)])
  return head


def save_pr(s, uid, number, head, mergeable):
  """The saved pull request (`status.py`'s `record["pr"]`) as the last status pass read it."""
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["units"][uid]["pr"] = {"number": number, "head": head, "base_ref": "main", "mergeable": mergeable}
  s.path("state").write_text(json.dumps(state), encoding="utf-8")


@pytest.mark.parametrize("latest, mergeable, rounds, merge, reason", [
  ("clean", "CONFLICTING", 3, "alone", "merge"),
  ("proceeded", "CONFLICTING", 3, "alone", "merge"),
  ("revise", "CONFLICTING", 3, "with-fix", "review"),
  ("revise", "MERGEABLE", 3, None, "review"),
  ("revise", "CONFLICTING", None, None, "review"),
])
def test_merge_orders_on_launch(world, monkeypatch, spawn_fake, latest, mergeable, rounds, merge, reason):
  # §6.1: orders from the saved mergeable; git merge admitted on this launch only
  s, card, hid, _ = seed(world)
  if rounds is not None:
    with_rounds(s, world, rounds)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  head = first_round(world, s, card)
  posted = {**CLEAN, "head": head, "posted_at": "2099-01-01T00:00:00Z"}  # posted after round 1 started
  round_one = {**posted, "outcome": "clean" if latest == "clean" else "revise"}
  write_foreman(s, "U07", [round_one], [proceed_entry(1, head)] if latest == "proceeded" else [])
  save_pr(s, "U07", 71, head, mergeable)
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 0, out
  entry = launches_of(s, "U07")[-1]
  prompt = s.path("launches", "U07_r2_prompt.md").read_text(encoding="utf-8")
  tools = entry["command"]
  assert entry.get("merge") == merge and entry["reason"] == reason
  assert ("Merge orders" in prompt) == (merge is not None)
  assert ("Bash(git merge:*)" in tools) == (merge is not None)
  first = launches_of(s, "U07")[0]
  assert "merge" not in first and "Bash(git merge:*)" not in first["command"]  # the first launch carried none


# ---------------------------------------------------------------- S4: the brief pins the current base


def commit_on(world, start, path, text, push):
  """A commit on `start` writing `path` as `text`, pushed to origin's `push` ref, made in a scratch clone; its sha."""
  side = world.repo.parent / "side"
  if not side.exists():
    git(["clone", "-q", str(world.repo.parent / "origin.git"), str(side)], world.repo.parent)
  git(["fetch", "-q", "origin", "+refs/*:refs/remotes/all/*"], side)
  git(["checkout", "-q", "--detach", start], side)
  put(side / path, text)
  git(["add", path], side)
  git(["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", f"edit {path}"], side)
  git(["push", "-q", "origin", f"HEAD:{push}"], side)
  return git(["rev-parse", "HEAD"], side).strip()


def test_merge_brief_pins_the_current_base(world, monkeypatch, spawn_fake):
  # §6.1: base advanced after the batch's launch; the direct with-fix revision fetches and pins it itself
  s, card, hid, _ = seed(world, units=("U07", "U08"))
  with_rounds(s, world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  batch_base = first_round(world, s, card)  # the base `launch` fetched for the batch
  head = commit_on(world, batch_base, "src/worker.py", "the head's worker\n", "refs/pull/71/head")
  new_base = commit_on(world, batch_base, "src/worker.py", "the landed unit's worker\n", "refs/heads/main")  # U08 landed
  make_pr(world.gh, 71, head, closes=[(REPO, 7)])
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state.setdefault("status", {}).setdefault("units", {}).setdefault("U08", {})["landed"] = True
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  write_foreman(s, "U07", [{**REVISE, "head": head, "posted_at": "2099-01-01T00:00:00Z"}])
  save_pr(s, "U07", 71, head, "CONFLICTING")
  assert git(["rev-parse", "refs/superegm/base"], world.repo).strip() == batch_base  # no `launch` ran since
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 0, out
  entry = launches_of(s, "U07")[-1]
  prompt = s.path("launches", "U07_r2_prompt.md").read_text(encoding="utf-8")
  assert entry["merge"] == "with-fix"
  assert entry["base"] == new_base != batch_base
  assert f"git merge {new_base}" in prompt and batch_base not in prompt
  assert "`src/worker.py` (landed: U08)" in prompt  # the fixture's units all hold `src/worker.py`


# ---------------------------------------------------------------- S5: the merge orders' text


ROOT = Path(__file__).resolve().parents[2]


def test_merge_orders_text():
  # skill text: the orders sit behind a marker launch-builder fills only on a merge launch
  from superegm import launch_builder
  builder_orders = (ROOT / "skills/wave/references/builder_orders.md").read_text(encoding="utf-8")
  wave_skill = (ROOT / "skills/wave/SKILL.md").read_text(encoding="utf-8")
  assert "<!-- merge: " in builder_orders and "merge commit" in builder_orders
  assert "no rebase" in builder_orders and "no force push" in builder_orders and "keeping both units' intent" in builder_orders
  assert "merge round" in wave_skill and "await-merge after" in wave_skill and "conflict" in wave_skill
  plain = launch_builder.orders_text([], "/bin/gh", 0)
  merging = launch_builder.orders_text(["Bash(git merge:*)"], "/bin/gh", 0, merge=True)
  assert "<!-- merge: " not in plain and "merge commit" not in plain  # an ordinary launch reads no merge orders
  assert "<!-- merge: " not in merging and "merge commit" in merging and "keeping both units' intent" in merging


# ---------------------------------------------------------------- S6: the board and the inbox


def test_conflict_on_board_and_inbox(world):
  # §6.1: a unit whose saved view is `conflict` shows it on the board and in the inbox
  import superegm as core
  from superegm import report, inbox
  from test_wave import wave_store, open_wave_card, CLEAN as WAVE_CLEAN
  s = wave_store(world, U01={"pr": 71, "head": HEAD, "ci": "green", **WAVE_CLEAN})
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"]["U01"] |= {"status": "conflict", "conflict": True}
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  card = json.loads(s.path("runcards", open_wave_card(world)).read_text(encoding="utf-8"))
  handoff = core.Handoff(core.here(state["plan"]), s)
  hid = s.handoff_id
  row = next(r for r in report.board_table(handoff, handoff.state, card, 0).splitlines() if "U01 #" in r)
  assert "conflict" in row
  assert any("U01" in line and "conflict" in line for line in map(inbox.line_of, inbox.inbox_items(s, [hid])))
