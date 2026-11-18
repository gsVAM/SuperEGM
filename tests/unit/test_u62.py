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


@pytest.mark.parametrize("same_head, status_word, changed", [(True, "conflict", False), (False, "ci green", True)])
def test_unknown_keeps_a_conflict_on_its_head(world, monkeypatch, same_head, status_word, changed):
  # codebase-details-1-5: §6.1 UNKNOWN is read again next pass, so it neither clears a conflict on that head nor
  # wakes `tick_trigger` and `wait_events` twice; a new head is a new read
  gh, st, card = status_seed(world, monkeypatch)
  node = status_pr(gh, "green")
  node["mergeable"] = "CONFLICTING"
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  handoff = superegm.Handoff(Path(state["plan"]), st, state)
  saved_view = status.fingerprint(status.unit_view(handoff, "U01"))
  node["mergeable"] = "UNKNOWN"
  if not same_head:
    handoff.state["units"]["U01"]["pr"]["head"] = "b" * 40  # the saved read was of another head
  fresh = status.unit_view(handoff, "U01")
  assert fresh["status"] == status_word and fresh["ci"] == "green"
  assert (status.fingerprint(fresh) != saved_view) == changed
  assert handoff.state["units"]["U01"]["pr"]["mergeable"] == ("CONFLICTING" if same_head else "UNKNOWN")


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
  ("clean, CONFLICTING, stopped", [], []),
  ("clean, CONFLICTING, open cap question D2", [], []),
  ("clean, CONFLICTING, head moved", [], []),
  ("proceeded during launch 2, it exited on a new head, CONFLICTING", [], []),
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
  moved = "head moved" in case or "new head" in case  # the pull request's head is not the authorizing outcome's
  open_pr(world, mergeable, head="b" * 40 if moved else HEAD)
  rounds, proceeds, decisions, runs = [CLEAN], [], [], [(1, "exited 0")]
  if "launch running" in case:
    runs = [(1, "running")]
  if "open decision" in case:
    decisions = [{"id": "D1", "point": 3}]
  if "open cap question" in case:
    decisions = [{"id": "D2", "point": 2}]
  if "during launch 2" in case:  # the owner proceeded on HEAD while launch 2 ran; it pushed a new head and exited
    proceeds, runs = [proceed_entry(2)], [(1, "exited 0"), (2, "exited 0")]
  if case.startswith("proceeded with no posted round"):
    rounds, proceeds = [], [proceed_entry(1)]
  if case.startswith("merge round recorded"):  # a first conflict's merge round ran, the owner proceeded on its head again
    proceeds, runs = [proceed_entry(1), proceed_entry(2)], [(1, "exited 0"), (2, "exited 0")]
  write_foreman(s, "U01", rounds, proceeds, decisions)
  if case.endswith("stopped"):  # the owner's stop, recorded on the foreman file
    foreman = json.loads(s.path("foreman", "U01").read_text(encoding="utf-8"))
    put(s.path("foreman", "U01"), json.dumps({**foreman, "stopped": {"reason": "stop the unit"}}))
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


def commit_on(world, start, path, text, push, message=None):
  """A commit on `start` writing `path` as `text`, pushed to origin's `push` ref, made in a scratch clone; its sha."""
  side = world.repo.parent / "side"
  if not side.exists():
    git(["clone", "-q", str(world.repo.parent / "origin.git"), str(side)], world.repo.parent)
  git(["fetch", "-q", "origin", "+refs/*:refs/remotes/all/*"], side)
  git(["checkout", "-q", "--detach", start], side)
  put(side / path, text)
  git(["add", path], side)
  git(["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", message or f"edit {path}"], side)
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


def merge_revision(world, s, card, head_path="src/worker.py", base_path="src/worker.py", base_text="landed\n",
                   base_message=None):
  """S4's arrange: U07's pull request #71 `CONFLICTING` with a revise round, the base advanced past the batch's."""
  batch_base = first_round(world, s, card)
  head = commit_on(world, batch_base, "src/worker.py", "the head's worker\n", "refs/heads/side-head")
  if head_path != "src/worker.py":
    head = commit_on(world, head, head_path, "the head's\n", "refs/heads/side-head")
  new_base = commit_on(world, batch_base, base_path, base_text, "refs/heads/main", base_message)
  make_pr(world.gh, 71, head, closes=[(REPO, 7)])
  git(["push", "-q", str(world.repo.parent / "origin.git"), f"{head}:refs/pull/71/head"], world.repo.parent / "side")
  write_foreman(s, "U07", [{**REVISE, "head": head, "posted_at": "2099-01-01T00:00:00Z"}])
  save_pr(s, "U07", 71, head, "CONFLICTING")
  return batch_base, new_base


def test_merge_launch_checks_the_base_it_fetched(world, monkeypatch, spawn_fake):
  # codebase-details-1-2: the merge launch moves `refs/superegm/base`; it checks it as `launch` does, so no later
  # launch of the batch starts from a base `origin_problems` never read
  s, card, hid, _ = seed(world, units=("U07", "U08"))
  with_rounds(s, world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  spec = next(world.repo.glob("docs/**/*.md")).relative_to(world.repo).as_posix()
  batch_base, _ = merge_revision(world, s, card, base_path=spec, base_text="# an unapproved spec\n")
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 1 and "neither the approved bytes nor a later link" in out, out
  assert launches_of(s, "U07")[-1]["round"] == 1  # no merge launch recorded
  # astra-2-1, change-review-2-1, codebase-details-2-2: the refused base never reaches the shared ref, so a later
  # round-1 launch of the batch builds from the base `launch` checked
  assert git(["rev-parse", "refs/superegm/base"], world.repo).strip() == batch_base


def test_merge_brief_names_paths_unquoted(world, monkeypatch, spawn_fake):
  # astra-1-4: a path Git would C-quote is named as it is in the tree
  s, card, hid, _ = seed(world, units=("U07", "U08"))
  with_rounds(s, world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  merge_revision(world, s, card, head_path="src/café.py", base_path="src/café.py")
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 0, out
  prompt = s.path("launches", "U07_r2_prompt.md").read_text(encoding="utf-8")
  assert "- `src/café.py`" in prompt and "\\303" not in prompt


def test_merge_launch_scratch_ref_is_its_own(world, monkeypatch, spawn_fake):
  # astra-3-1: a concurrent launch's scratch ref is neither read nor deleted; the pinned commit is the one checked
  s, card, hid, _ = seed(world, units=("U07", "U08"))
  with_rounds(s, world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  batch_base, new_base = merge_revision(world, s, card)
  # codebase-details-4-2: a concurrent invocation's scratch ref, mid-launch, in the namespace every invocation writes
  theirs = "refs/superegm/scratch/" + "0" * 32
  git(["update-ref", theirs, batch_base], world.repo)
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 0, out
  assert launches_of(s, "U07")[-1]["base"] == new_base
  assert git(["rev-parse", theirs], world.repo).strip() == batch_base  # neither read nor moved nor deleted
  assert git(["rev-parse", "refs/superegm/base"], world.repo).strip() == new_base
  left = git(["for-each-ref", "--format=%(refname)", "refs/superegm/"], world.repo).split()
  assert {r for r in left if not r.startswith("refs/superegm/pr/")} == {"refs/superegm/base", theirs}  # its own scratch removed


@pytest.mark.parametrize("message, landed", [
  ("U08's worker (#72)", "(landed: U08)"),  # squash merge: the saved status has not seen U08 land
  ("Merge pull request #72 from o/feature", "(landed: U08)"),
  ("Merge pull request #90 from o/superegm/2026-01-01-other-abcdef/U03", "(landed: 2026-01-01-other-abcdef/U03)"),
])
def test_merge_brief_names_holders_from_the_base(world, monkeypatch, spawn_fake, message, landed):
  # astra-3-2: the holders are read from the pinned base's commits, not the last status pass alone, a unit of
  # another handoff included; the base commits that touch each path are named
  s, card, hid, _ = seed(world, units=("U07", "U08"))
  with_rounds(s, world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  _, new_base = merge_revision(world, s, card, base_message=message)
  save_pr(s, "U08", 72, "b" * 40, "MERGEABLE")  # U08's pull request, saved before it merged; landed not yet read
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 0, out
  prompt = s.path("launches", "U07_r2_prompt.md").read_text(encoding="utf-8")
  assert f"- `src/worker.py` {landed}" in prompt
  assert f"base commit `{new_base[:12]}`: {message}" in prompt


OTHER = "2026-01-01-other-abcdef"


def other_handoff(s, uid="U03", number=90, scope="src/worker.py"):
  """Another handoff in the store whose unit `uid` holds `scope` and whose saved pull request is #`number`."""
  import superegm as core
  put(s.root / "handoffs" / f"{OTHER}.json", json.dumps({"id": OTHER, "spec": None, "opened_at": None, "closed_at": None}))
  hs = core.handoff_store(s, OTHER)
  put(hs.path("state"), json.dumps({"handoff_id": OTHER, "units": {uid: {"number": 9, "pr": {"number": number}}}}))
  put(hs.path("units"), json.dumps({"handoff_id": OTHER, "order": [uid],
                                    "units": {uid: {"id": uid, "scope": [{"path": scope, "action": "modify"}]}}}))


def land_by_merge(world, start, branch_message, merge_message):
  """A unit branch off `start` writing `src/worker.py`, landed on origin's main by a real two-parent merge commit
  (GitHub's "Merge pull request"); the merge's sha."""
  side = world.repo.parent / "side"
  branch_tip = commit_on(world, start, "src/worker.py", "the landed unit's worker\n", "refs/heads/landing", branch_message)
  git(["checkout", "-q", "--detach", start], side)
  git(["-c", "user.name=t", "-c", "user.email=t@example.com", "merge", "-q", "--no-ff", "-m", merge_message, branch_tip], side)
  git(["push", "-q", "origin", "HEAD:refs/heads/main"], side)
  return git(["rev-parse", "HEAD"], side).strip()


@pytest.mark.parametrize("merge_message, landed, other", [
  ("Merge pull request #72 from o/feature", "(landed: U08)", False),
  (f"Merge pull request #90 from o/{superegm.BRANCH_PREFIX}/{OTHER}/U03", f"(landed: {OTHER}/U03)", False),
  ("Merge pull request #90 from o/feature", f"(landed: {OTHER}/U03)", True),
])
def test_merge_brief_names_holders_landed_by_a_merge_commit(world, monkeypatch, spawn_fake, merge_message, landed, other):
  # astra-4-1, codebase-details-4-1: a unit landed by a two-parent merge commit is named from that commit, which
  # Git's default history simplification would leave out (it is TREESAME to the unit branch)
  s, card, hid, _ = seed(world, units=("U07", "U08"))
  with_rounds(s, world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  _, main = merge_revision(world, s, card)
  new_base = land_by_merge(world, main, "the unit's own work", merge_message)
  save_pr(s, "U08", 72, "b" * 40, "MERGEABLE")
  if other:
    other_handoff(s)
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 0, out
  entry = launches_of(s, "U07")[-1]
  prompt = s.path("launches", "U07_r2_prompt.md").read_text(encoding="utf-8")
  assert entry["base"] == new_base
  assert f"- `src/worker.py` {landed}" in prompt, prompt
  assert f"base commit `{new_base[:12]}`: {merge_message}" in prompt


@pytest.mark.parametrize("scope, landed", [
  ("src/worker.py", f"(landed: {OTHER}/U03)"),
  ("src/other.py", None),  # its scope does not hold the path: not a holder
])
def test_merge_brief_names_another_handoffs_squash(world, monkeypatch, spawn_fake, scope, landed):
  # astra-4-2: a squash merge of another handoff's unit names only its pull request number; that handoff's saved
  # pull request and Scope paths name the unit
  s, card, hid, _ = seed(world, units=("U07", "U08"))
  with_rounds(s, world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  merge_revision(world, s, card, base_message="Update worker (#90)")
  other_handoff(s, scope=scope)
  code, out = world.run("launch-builder", "--unit", "U07", "--round", 2, "--runcard", card)
  assert code == 0, out
  prompt = s.path("launches", "U07_r2_prompt.md").read_text(encoding="utf-8")
  if landed:
    assert f"- `src/worker.py` {landed}" in prompt, prompt
  else:
    assert "- `src/worker.py`\n" in prompt and OTHER not in prompt, prompt


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


def test_merge_orders_square_with_never_merge():
  # codebase-details-1-1, -1-11: the never-merge rules are about the pull request; an alone round only merges
  from superegm import launch_builder
  merging = launch_builder.orders_text(["Bash(git merge:*)"], "/bin/gh", 0, merge=True)
  assert "never merges (a pull request;" in merging and "they never merge your pull request" in merging
  assert "change nothing beyond the merge and its conflict resolution" in merging
  # change-review-3-1, codebase-details-3-1: an ordinary launch is pointed at no merge orders it does not carry
  plain = launch_builder.orders_text([], "/bin/gh", 0)
  assert "merge orders below" not in plain and "they never merge your pull request" not in plain


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


# ---------------------------------------------------------------- R1: the review's findings on the board, the inbox and the loop


def conflict_wave(world, case):
  """test_wave's store with U01 conflicting at HEAD: clean (`rounds` set or not), its launch 2 running, or stopped."""
  import superegm as core
  from test_wave import wave_store, CLEAN as WAVE_CLEAN
  u01 = {"pr": 71, "head": HEAD, "ci": "green", **WAVE_CLEAN}
  if case in ("running", "proceeded, running"):
    u01["launches"] = [{"round": 1, "status": "exited 0"}, {"round": 2, "status": "running"}]
  if case == "revise, point 5":
    u01["rounds"] = [{**WAVE_CLEAN["rounds"][0], "outcome": "revise"}]
    u01["decisions"] = [{"id": "D1", "point": 5, "source": "review head-U01-c1", "question": "accept or revise?",
                         "options": ["accept", "revise"]}]
  if case == "proceeded on revise, relaunched":  # change-review-4-1: proceeded on a revise round, launch 2 finished
    u01["rounds"] = [{**WAVE_CLEAN["rounds"][0], "outcome": "revise"}]
    u01["launches"] = [{"round": 1, "status": "exited 0"}, {"round": 2, "status": "exited 0"}]
  if case == "proceeded, ci pending":
    u01["ci"] = "pending"
  s = wave_store(world, U01=u01)
  if case.startswith("proceeded"):  # the owner proceeded on HEAD: on launch 2 while it runs, or on launch 1
    foreman = json.loads(s.path("foreman", "U01").read_text(encoding="utf-8"))
    launch_n = 2 if case.endswith("running") else 1
    put(s.path("foreman", "U01"), json.dumps({**foreman, "proceeds": [proceed_entry(launch_n)]}))
  if case != "clean, 1.2.0":
    with_rounds(s, world)
  if case == "stopped":
    foreman = json.loads(s.path("foreman", "U01").read_text(encoding="utf-8"))
    put(s.path("foreman", "U01"), json.dumps({**foreman, "stopped": {"reason": "stop the unit"}}))
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["status"]["units"]["U01"] |= {"status": "conflict", "conflict": True}
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  return s, core.Handoff(core.here(state["plan"]), s)


@pytest.mark.parametrize("case, board, inbox_action", [
    ("clean", "conflict: merge round", "a merge round"),
    ("clean, 1.2.0", "conflict: the owner resolves it", "the owner resolves it"),
    ("running", "conflict; ", "once the launch ends or the owner rules"),
    ("stopped", "conflict; ", "stopped"),
    ("proceeded, running", "conflict: a merge round once the launch ends", "once the launch ends or the owner rules"),
    ("revise, point 5", "conflict; ", "once the launch ends or the owner rules"),
    ("proceeded on revise, relaunched", "conflict; proceed again", "once the launch ends or the owner rules"),
])
def test_conflict_board_action_and_inbox_line(world, case, board, inbox_action):
  # astra-1-3, change-review-1-1, change-review-1-2, codebase-details-1-4, codebase-details-1-7: §6.1
  from superegm import report, inbox
  from test_wave import open_wave_card
  s, handoff = conflict_wave(world, case)
  card = json.loads(s.path("runcards", open_wave_card(world)).read_text(encoding="utf-8"))
  row = next(r for r in report.board_table(handoff, handoff.state, card, 0).splitlines() if "U01 #" in r)
  assert board in row, row
  if case == "proceeded, running":  # codebase-details-2-3: `launch` marks nothing while the launch runs
    assert "conflict: merge round" not in row, row
  items = [i for i in inbox.inbox_items(s, [s.handoff_id]) if i["subject"] == "U01"]
  conflicts = [i for i in items if i["kind"] == "conflict"]
  assert len(conflicts) == 1 and inbox_action in conflicts[0]["action"], items
  assert not [i for i in items if i["kind"] == "merge"], items  # no merge GitHub would refuse


@pytest.mark.parametrize("case, loop", [
    ("clean", "loop: continuing (merge round: U01)"),
    ("clean, 1.2.0", "loop: ended"),
])
def test_conflict_keeps_the_loop(world, case, loop):
  # astra-1-1, codebase-details-1-6: a clean conflicting unit a merge round takes is pending work
  from test_wave import open_wave_card
  s, _ = conflict_wave(world, case)
  code, out = world.run("report", "--runcard", open_wave_card(world))
  assert code == 0 and loop in out, out


def test_ci_wait_idle_is_no_merge_round(world):
  # astra-2-2: a unit idle on its CI wait is idle for `launch` too, so it is no merge round that keeps the loop
  from test_wave import open_wave_card
  conflict_wave(world, "proceeded, ci pending")
  card = open_wave_card(world)
  assert world.run("report", "--runcard", card)[0] == 0  # the card sees the head
  world.advance(31 * 60)
  code, out = world.run("report", "--runcard", card)
  assert code == 0 and "idle: U01" in out and "merge round" not in out, out


def test_conflict_cleared_is_an_event(world, monkeypatch):
  # astra-2-3: a head GitHub reads MERGEABLE again, its CI unchanged, wakes `tick_trigger` and `wait_events`
  gh, st, card = status_seed(world, monkeypatch)
  node = status_pr(gh, "green")
  node["mergeable"] = "CONFLICTING"
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  handoff = superegm.Handoff(Path(state["plan"]), st, state)
  saved_view = status.fingerprint(status.unit_view(handoff, "U01"))
  node["mergeable"] = "MERGEABLE"
  view = status.fingerprint(status.unit_view(handoff, "U01"))
  assert [line.split(" pr=")[0] for line in status.unit_events("U01", saved_view, view)] == ["U01 conflict cleared"]


def test_wave_skill_names_the_merge_round_end():
  # change-review-2-2, codebase-details-2-1, codebase-details-2-4: the skill's end condition and its `conflict` line
  wave_skill = " ".join((ROOT / "skills/wave/SKILL.md").read_text(encoding="utf-8").split())
  assert "no ready unlaunched unit with a free slot, nor a merge round `launch` would mark" in wave_skill
  assert "`conflict` lines need nothing before step 6" in wave_skill
