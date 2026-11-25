# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U102, settled findings stay settled (spec section 3.5).

"""U102: `collect` drops a builder's contest of a settled fid (or of one derived from a settled fid), an owner's
`test-delta <file> allowed` widens Scope for that file, and a test-delta settlement follows the test and the line
text across a merge of main, a 1.2.1 entry's base-commit-and-line key and a judges' overrule still honoured.
Fixtures: conftest's `world` and test_foreman's `seed`, `pr_repo`, `prepared` and `open_head_review`."""

import json
from pathlib import Path

import pytest

from superegm import atomic_write, foreman as foreman_mod
import test_foreman
from test_foreman import (POSTED_R1, PR, PR_BODY, UNIT, builder_token, c, open_head_review, pr_repo, prepared,  # noqa: F401
                          record, seed)
from test_u67 import tmpdir_in_tmp_path  # noqa: F401  every temporary directory `precheck` makes, under tmp_path

R2 = {**POSTED_R1, "round": 2, "launch": 2, "dispatch_id": "d2"}
REPLY_AT, RULING_AT = "2026-11-02T14:00:00Z", "2026-11-02T13:00:00Z"
Q = "tests/unit/test_q.py"


def located(claim: str) -> str:
  """The location a foreman finding with `claim` takes in the fixtures' posted rounds."""
  if claim.startswith("dod-"):
    return f"dod/{claim[4:].split(':')[0]}.txt"
  if claim.startswith("test-delta: "):
    return claim.removeprefix("test-delta: ").split(" ")[0]
  if claim.startswith("contested "):
    return "pr #70 comment 9"
  return "src/hooks.py:1"


@pytest.mark.parametrize("contested, claim, ruling, by, raised", [
    ("foreman-1-1", "dod-4: ran red (timeout)", "dod-4 allowed — CI runs the suite", "owner", False),
    ("foreman-1-1", "dod-4: ran red (timeout)", "foreman-1-1 finding overruled — CI runs the suite", "owner", False),
    ("foreman-1-1", "dod-4: ran red (timeout)", "foreman-1-1 finding overruled — CI runs the suite", "judges:p-1", False),
    ("foreman-1-1", "dod-4: ran red (timeout)", "foreman-1-1 finding upheld", "owner", False),
    ("foreman-1-1", "test-delta: tests/unit/test_q.py:3 removed", "test-delta tests/unit/test_q.py allowed — by design", "owner", False),
    ("foreman-2-1", "contested foreman-1-1: CI runs the suite", "foreman-1-1 finding overruled — CI runs the suite", "owner", False),
    ("foreman-1-1", "dod-4: ran red (timeout)", "dod-5 allowed — another item", "owner", True),
    ("astra-1-2", "dod-4 never passes on this head", "foreman-1-1 finding overruled — CI runs the suite", "owner", True),
    ("astra-1-2", "dod-4: ran red (timeout)", "dod-4 allowed — CI runs the suite", "owner", True),
])
def test_a_contest_of_a_settled_fid_is_dropped(world, tmp_path, monkeypatch, contested, claim, ruling, by, raised):
  # the last posted round holds `contested` (`claim`) open; the ruling (a comment, or a recorded judges' entry) precedes
  # the builder's `**Reply <contested>:** contested — CI runs the suite`; the match is by fid and derivation, never by wording;
  # `foreman_findings_lines` is the `foreman.findings` file `superegm collect` writes, `builder_contested` its round's list
  reply = c(14, "builder-bot", f"**Reply {contested}:** contested — CI runs the suite", at=REPLY_AT)
  comments = {PR: [reply]}
  kw = {}
  if by == "owner":
    comments[2] = [c(13, "owner", f"**Ruling:** {ruling}", at=RULING_AT)]
  else:  # the judges' ruling, recorded (`rulings[]`): it binds from the record
    text, _, reason = ruling.partition(" — ")
    kw.update(decisions=[{"id": "q1", "point": 1, "source": "review r round 1"}],
              rulings=[{"decision": "q1", "ruling": text, "by": by, "reason": reason, "posted": "comment 13", "posted_at": RULING_AT}])
  if contested.startswith("astra-"):  # the head's Astra lane on the panel, its runner absent
    monkeypatch.setattr(foreman_mod, "runner_path", lambda: None)
    kw["astra"] = {"enabled": True}
  two = contested.startswith("foreman-2-")  # a contest's copy, posted in round 2, contested in round 3
  rounds = [POSTED_R1, R2] if two else [POSTED_R1]
  if claim.startswith("test-delta: "):  # round 1's entry of the finding (a 1.2.1 entry: no test or text)
    rounds = [{**POSTED_R1, "test_delta": [{"file": Q, "line": 3, "base_line": 3, "kind": "removed", "base_commit": "0" * 40}]}]
  n = len(rounds) + 1
  kw.update(rounds=rounds, launches=[{"round": i, "status": "exited 0"} for i in range(1, n + 1)], comments=comments)
  st0, card0, _ = seed(world, **kw)
  round_1 = {"change-review": ""}
  if contested.startswith("astra-"):  # another reviewer's finding: the foreman derives nothing from its claim
    round_1["foreman"] = "foreman-1-1 | high | dod/4.txt | regression: no | dod-4: ran red (timeout)\n"
    round_1["astra"] = ("astra-1-1 | medium | src/hooks.py:1 | regression: no | a name is unclear\n"
                        f"astra-1-2 | high | {located(claim)} | regression: no | {claim}\n")
  elif two:
    round_1["foreman"] = "foreman-1-1 | high | dod/4.txt | regression: no | dod-4: ran red (timeout)\n"
  else:
    round_1["foreman"] = f"foreman-1-1 | high | {located(claim)} | regression: no | {claim}\n"
  rid = open_head_review(world, st0, card0, "0" * 40, round_1)
  if two:
    record(world, st0, rid, 2, "0" * 40, card0, {"change-review": "",
                                                 "foreman": f"foreman-2-1 | high | {located(claim)} | regression: no | {claim}\n"})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert code == 0, out
  foreman_findings_lines = (w.dir / f"r{n}/foreman.findings").read_text(encoding="utf-8").splitlines()
  builder_contested = json.loads(w.st.path("reviews", w.rid, f"round-{n}.json").read_text(encoding="utf-8"))["builder_contested"]
  assert any(line.endswith(f"contested {contested}: CI runs the suite") for line in foreman_findings_lines) is raised, foreman_findings_lines
  assert len(builder_contested) == (1 if raised else 0)


S1 = [("test(S1): hook", "tests/unit/test_hooks.py"), ("feat(S1): hook", "src/hooks.py")]
FILE_RULING = "test-delta tests/unit/test_q.py allowed"


@pytest.mark.parametrize("how", ["comment", "recorded"])
def test_a_test_delta_file_allowance_widens_scope(world, tmp_path, monkeypatch, how):
  # Scope lacks tests/unit/test_q.py and src/other.py; the head changes both; the owner's
  # `**Ruling:** test-delta tests/unit/test_q.py allowed — by design` is on the issue, or recorded by `decision rule`
  monkeypatch.setattr(test_foreman, "SECTION", test_foreman.SECTION.replace("`tests/unit/test_q.py` (modify), ", ""))
  if how == "comment":
    kw = {"comments": {2: [c(13, "owner", f"**Ruling:** {FILE_RULING} — by design", at=RULING_AT)]}}
  else:  # the record alone: its comment deleted
    kw = {"decisions": [{"id": "q1", "point": 1, "source": "review r round 1"}],
          "rulings": [{"decision": "q1", "ruling": FILE_RULING, "by": "owner", "reason": "by design", "posted": "comment 13",
                       "posted_at": RULING_AT}]}
  commits = S1 + [("chore: note", Q, "def test_a():\n  assert 1 == 1\n# a note\n"), ("chore: other", "src/other.py")]
  w = prepared(world, tmp_path, monkeypatch, commits=commits, base_files={Q: "def test_a():\n  assert 1 == 1\n"}, **kw)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert code == 0, out
  foreman_findings_lines = (w.dir / "r1/foreman.findings").read_text(encoding="utf-8").splitlines()
  located = [line.split(" | ", 2)[2] for line in foreman_findings_lines]
  assert "tests/unit/test_q.py | regression: no | changed path outside Scope paths" not in located
  assert "src/other.py | regression: no | changed path outside Scope paths" in located


# Rounds driven as the foreman drives them: each head through `foreman dispatch`, `prepare` and `collect`, each
# collected round marked posted as `review post` marks it; `precheck` then run from the builder's worktree.
BRANCH = "superegm/sample-42aff4/U01"
ALLOWED = "**Ruling:** foreman-1-1 allowed — kept by design"
POSTED_AT = {1: "2026-11-02T12:00:00Z", 2: "2026-11-02T15:00:00Z"}  # the ruling (RULING_AT) falls between them


def move_head(world, st, g, text, merge=None):
  """A new PR head on the branch: `text` as test_q.py (when it differs), or a merge of main whose own commit wrote
  `merge` as test_q.py (two lines added above the base's first line); the PR, its CI and the state follow it."""
  if merge:
    target = g("rev-parse", "--show-toplevel")
    Path(target, Q).write_text(merge, encoding="utf-8")
    g("commit", "-qam", "main: import pytest")
  g("checkout", "-q", BRANCH)
  if merge:
    g("merge", "-q", "--no-edit", "main")
  target = g("rev-parse", "--show-toplevel")
  if not merge and Path(target, Q).read_text(encoding="utf-8") != text:
    Path(target, Q).write_text(text, encoding="utf-8")
    g("commit", "-qam", "chore: later")
  head = g("rev-parse", "HEAD")
  g("update-ref", f"refs/pull/{PR}/head", head)
  g("checkout", "-q", "main")
  world.gh.prs[PR]["headRefOid"] = head
  world.gh.check_runs[head] = [{"name": "tests", "status": "completed", "conclusion": "success"}]
  world.gh.combined[head] = {"state": "success", "statuses": []}
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  state["units"][UNIT]["pr"]["head"] = head
  atomic_write(st.path("state"), state)
  return head


def collect_round(world, st, card, n) -> dict:
  """Round `n` on the PR's head, after launch `n`: dispatched, prepared and collected; its record."""
  launches = json.loads(st.path("launches", UNIT).read_text(encoding="utf-8"))
  if len(launches["launches"]) < n:
    launches["launches"].append({"round": n, "status": "exited 0"})
    atomic_write(st.path("launches", UNIT), launches)
  code, out = world.run("foreman", "dispatch", "--unit", UNIT, "--runcard", card)
  assert code == 0, out
  did, child = out.split()
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  head = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][-1]["head"]
  record(world, st, test_foreman.head_rid(st), n, head, child, {"change-review": ""})  # the round's panel completed
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  return json.loads(st.path("reviews", test_foreman.head_rid(st), f"round-{n}.json").read_text(encoding="utf-8"))


def post(st, n):
  """Round `n`, collected, marked posted at `POSTED_AT[n]`."""
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  entry = data["rounds"][-1]
  assert entry["round"] == n and entry["phase"] == "collected"
  entry.update(phase="posted", posted_at=POSTED_AT[n], outcome="revise")
  atomic_write(st.path("foreman", UNIT), data)


def precheck_on_head(world, st, g, tmp_path, monkeypatch, snapshot: str) -> list:
  """`superegm precheck` from the builder's worktree on the PR's head, the latest launch's comment snapshot `snapshot`."""
  g("fetch", "-q", "--no-write-fetch-head", "origin", "+refs/heads/main:refs/superegm/base",
    f"+refs/pull/{PR}/head:refs/heads/{BRANCH}", cwd=world.repo)
  worktree = tmp_path / "wt"
  g("worktree", "add", "-q", str(worktree), BRANCH, cwd=world.repo)
  latest = max(l["round"] for l in json.loads(st.path("launches", UNIT).read_text(encoding="utf-8"))["launches"])
  st.path("launches", f"{UNIT}_r{latest}_comments.md").write_text(snapshot, encoding="utf-8")
  body = tmp_path / "pr_body.md"
  body.write_text(PR_BODY, encoding="utf-8")
  monkeypatch.chdir(worktree)
  code, out = world.run("precheck", "--handoff", st.handoff_id, "--unit", UNIT, "--pr-body", body)
  monkeypatch.chdir(world.repo)
  return out.splitlines()


def nth(text, old, new, n):
  """`text` with the `n`-th (1-based) occurrence of `old` replaced by `new`."""
  parts = text.split(old)
  return old.join(parts[:n]) + new + old.join(parts[n:])


BASE = ("class TestA:\n    def test_x(self):\n        assert y == 1\n        assert y == 1\n        assert y in s\n\n"
        "class TestB:\n    def test_x(self):\n        assert y == 1\n")
WEAK = "TestA.test_x's first `assert y == 1` weakened to `assert y`"
SKIP = "`@pytest.mark.skip` added above TestA.test_x"
ROUND_1 = {WEAK: nth(BASE, "assert y == 1", "assert y", 1),
           SKIP: BASE.replace("class TestA:\n", "class TestA:\n    @pytest.mark.skip\n")}
LATER = {
  "as in round 1": lambda r1: r1,
  "as in round 1, after a merge of main added two lines above TestA and moved the base commit": lambda r1: r1,
  "both `assert y == 1` lines of TestA.test_x weakened to `assert y`": lambda r1: BASE.replace("assert y == 1", "assert y", 2),
  "as in round 1, and TestB.test_x's `assert y == 1` weakened to `assert y` too": lambda r1: nth(r1, "assert y == 1", "assert y", 2),
  "TestA.test_x's first `assert y == 1` weakened further, to `assert True`": lambda r1: nth(BASE, "assert y == 1", "assert True", 1),
  "TestA.test_x's first `assert y == 1` weakened further, to `assert True`; round 3 on the same head":
      lambda r1: nth(BASE, "assert y == 1", "assert True", 1),
  "the first `assert y == 1` restored, and TestA.test_x's `assert y in s` weakened to `assert y`":
      lambda r1: BASE.replace("assert y in s", "assert y"),
  "the `@pytest.mark.skip` moved from TestA.test_x to TestB.test_x":
      lambda r1: BASE.replace("class TestB:\n", "class TestB:\n    @pytest.mark.skip\n"),
}


@pytest.mark.parametrize("round_1, later_head, counted, highs", [
    (WEAK, "as in round 1", 2, 0),
    (WEAK, "as in round 1, after a merge of main added two lines above TestA and moved the base commit", 2, 0),
    (WEAK, "both `assert y == 1` lines of TestA.test_x weakened to `assert y`", 2, 1),
    (WEAK, "as in round 1, and TestB.test_x's `assert y == 1` weakened to `assert y` too", 2, 1),
    (WEAK, "TestA.test_x's first `assert y == 1` weakened further, to `assert True`", 2, 1),
    (WEAK, "TestA.test_x's first `assert y == 1` weakened further, to `assert True`; round 3 on the same head", 3, 1),
    (WEAK, "the first `assert y == 1` restored, and TestA.test_x's `assert y in s` weakened to `assert y`", 2, 1),
    (SKIP, "as in round 1", 2, 0),
    (SKIP, "the `@pytest.mark.skip` moved from TestA.test_x to TestB.test_x", 2, 1),
])
def test_a_test_delta_settlement_follows_the_test_and_the_line_text(world, tmp_path, monkeypatch, round_1, later_head, counted, highs):
  # round 1's change (foreman-1-1) is ruled `**Ruling:** foreman-1-1 allowed — kept by design` by the owner on the issue before
  # round 2, with no `decision rule`, so a later finding at its line keeps the id foreman-1-1 by the carry; the key per entry kind:
  # `removed` the base line in the base test enclosing it; a weakened assertion the head line in the head test enclosing it,
  # beside its base line's text; an added marker its head line in the test it decorates (past stacked decorators);
  # `round_findings` the open foreman findings of round `counted`'s record, carried copies included
  comments = {2: []}
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch, commits=S1 + [("chore: round 1", Q, ROUND_1[round_1])],
                                  base_files={Q: BASE})
  st, card, _ = seed(world, head=head, comments=comments)
  first = collect_round(world, st, card, 1)
  assert [f["claim"] for f in first["reviewers"]["foreman"]["findings"]] == [f"test-delta: {Q}:{2 if round_1 == SKIP else 3} weakened"]
  post(st, 1)
  comments[2].append(c(13, "owner", ALLOWED, at=RULING_AT))  # after round 1's post, before round 2's
  move_head(world, st, g, LATER[later_head](ROUND_1[round_1]), merge="merge of main" in later_head and "import pytest\n\n" + BASE)
  for n in range(2, counted + 1):
    rnd = collect_round(world, st, card, n)
    if n < counted:
      post(st, n)
  round_findings = [f for f in rnd["reviewers"]["foreman"]["findings"] if f["disposition"] is None]
  snapshot = f"builder: builder-bot\n### issue #2 comment 13 by owner at {RULING_AT}\n{ALLOWED}\n"
  precheck_lines = precheck_on_head(world, st, g, tmp_path, monkeypatch, snapshot)
  assert sum(f["claim"].startswith("test-delta: tests/unit/test_q.py:") for f in round_findings) == highs, round_findings
  assert sum("test-delta: tests/unit/test_q.py:" in line for line in precheck_lines) == highs, precheck_lines  # `superegm precheck` on the later head


THREE, TWO = "def test_a():\n  assert 1 == 1\n  assert 2 == 2\n", "def test_a():\n  assert 1 == 1\n"
REMOVED = {"file": Q, "line": 3, "base_line": 3, "kind": "removed"}  # round 1's entry: `assert 2 == 2` of test_a, removed
ENTRIES = {"1.3": {"test": "test_a", "text": "assert 2 == 2", "base_text": "assert 2 == 2", "occurrence": 1},
           "1.2.1: {file, line, base_line, kind, base_commit} only": {}}
SETTLED_BY = {
  "judges:p-1, recorded `foreman-1-1 finding overruled`": {
      "decisions": [{"id": "q1", "point": 1, "source": "review r round 1"}],
      "rulings": [{"decision": "q1", "ruling": "foreman-1-1 finding overruled", "by": "judges:p-1", "reason": "moved",
                   "posted": "comment 13", "posted_at": RULING_AT}]},
  "owner, `foreman-1-1 allowed — moved`": {"comments": {2: [c(13, "owner", "**Ruling:** foreman-1-1 allowed — moved", at=RULING_AT)]}}}


@pytest.mark.parametrize("settled_by, entry, base_moved, highs", [
    ("judges:p-1, recorded `foreman-1-1 finding overruled`", "1.3", True, 0),
    ("owner, `foreman-1-1 allowed — moved`", "1.2.1: {file, line, base_line, kind, base_commit} only", False, 0),
    ("owner, `foreman-1-1 allowed — moved`", "1.2.1: {file, line, base_line, kind, base_commit} only", True, 1),
])
def test_judges_and_1_2_1_test_delta_settlements_carry(world, tmp_path, monkeypatch, settled_by, entry, base_moved, highs):
  # round 1's foreman-1-1 removed `assert 2 == 2` of tests/unit/test_q.py::test_a; round 2's head still lacks it
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch, commits=S1 + [("chore: trim", Q, TWO)], base_files={Q: THREE})
  posted = {**POSTED_R1, "test_delta": [{**REMOVED, "base_commit": base, **ENTRIES[entry]}]}  # taken at round 1's base
  st, card, _ = seed(world, head=head, rounds=[posted], launches=test_foreman.TWO_LAUNCHES, **SETTLED_BY[settled_by])
  open_head_review(world, st, card, "0" * 40, {"change-review": "",
                                               "foreman": f"foreman-1-1 | high | {Q}:3 | regression: no | test-delta: {Q}:3 removed\n"})
  if base_moved:  # a merge of main whose commit added two lines above test_a: the base commit and the line move
    move_head(world, st, g, None, merge="import os\n\n" + THREE)
  rnd = collect_round(world, st, card, 2)
  round_2_claims = [f["claim"] for f in rnd["reviewers"]["foreman"]["findings"]]
  assert sum(claim.startswith("test-delta: tests/unit/test_q.py:") for claim in round_2_claims) == highs, round_2_claims


# Round 2's review (PR #293): the fixes, each pinned.

SYNTAX = ("import pytest\n"                         # 1
          "\n"                                       # 2
          "def test_a(\n"                            # 3  a signature over several lines, closed at the def's indent
          "    tmp_path,\n"                          # 4
          "):\n"                                     # 5
          "    text = '''\n"                         # 6  a string whose lines sit at column 0
          "def x(\n"                                 # 7
          "'''\n"                                    # 8
          "    assert y == 1\n"                      # 9
          "\n"                                       # 10
          "class TestB:\n"                           # 11
          "    @pytest.mark.parametrize('x', [\n"    # 12
          "        1,\n"                             # 13
          "    ])\n"                                 # 14
          "    def test_b(self, x):\n"               # 15
          "        def test_inner():\n"              # 16 a test nested in a test: the nearest encloses its lines
          "            assert x\n"                   # 17
          "        assert y == 1\n")                 # 18


def test_the_enclosing_test_is_read_from_the_syntax_not_the_indentation():
  # astra-1-2, codebase-details-1-2, change-review-1-2: a multi-line signature or a string's column-0 lines end no
  # test, a string's `def x(` opens none, and a line takes the nearest enclosing `def test_*` with its class
  from superegm.collect import enclosing_tests
  names = enclosing_tests(SYNTAX.splitlines())
  assert names == (["<module>"] * 2 + ["test_a"] * 7 + ["<module>"] * 2 + ["TestB.test_b"] * 4
                   + ["TestB.test_inner"] * 2 + ["TestB.test_b"])


K = lambda text: {"file": Q, "line": 3, "base_line": 3, "kind": "weakened", "base_commit": "0" * 40, "test": "test_a",
                  "text": text, "base_text": "assert y == 1", "occurrence": 1}
WEAKENED = f"test-delta: {Q}:3 weakened"
FOLLOWS = {  # each case: round 1's and round 2's foreman records, their test_delta entries, the ruling, the contested fid
  # astra-1-3, codebase-details-1-5: a ruling on a contest's copy settles the original it contests
  # (round 2 holds foreman-1-1 carried, as foreman-2-1 below, and its contest's copy foreman-2-2)
  "copy-ruled": ({"foreman": "foreman-1-1 | high | dod/4.txt | regression: no | dod-4: ran red (timeout)\n"},
                 {"foreman": "foreman-2-1 | high | dod/4.txt | regression: no | dod-4: ran red (timeout)\n"
                             "foreman-2-2 | high | pr #70 comment 9 | regression: no | contested foreman-1-1: red\n"},
                 None, None, "foreman-2-2 finding overruled — CI runs the suite", "foreman-1-1", False),
  # codebase-details-1-3: the owner's file allowance widens Scope, so a contest of that path's scope finding is moot
  "scope-file": ({"foreman": f"foreman-1-1 | high | {Q} | regression: no | changed path outside Scope paths\n"}, None,
                 None, None, "test-delta tests/unit/test_q.py allowed — by design", "foreman-1-1", False),
  # codebase-details-1-4, change-review-1-3: the ruling binds round 1's entry; the carried copy's new change is open
  "carried-new-change": ({"foreman": f"foreman-1-1 | high | {Q}:3 | regression: no | {WEAKENED}\n"},
                         {"foreman": f"foreman-2-1 | high | {Q}:3 | regression: no | {WEAKENED}\n"},
                         K("assert y"), K("assert True"), "foreman-1-1 allowed — kept by design", "foreman-1-1", True),
  "carried-same-change": ({"foreman": f"foreman-1-1 | high | {Q}:3 | regression: no | {WEAKENED}\n"},
                          {"foreman": f"foreman-2-1 | high | {Q}:3 | regression: no | {WEAKENED}\n"},
                          K("assert y"), K("assert y"), "foreman-1-1 allowed — kept by design", "foreman-1-1", False),
}


@pytest.mark.parametrize("case", list(FOLLOWS))
def test_a_contest_is_dropped_only_where_a_ruling_settles_what_it_contests(world, tmp_path, monkeypatch, case):
  round_1, round_2, entry_1, entry_2, ruling, contested, raised = FOLLOWS[case]
  if case == "scope-file":  # round 1's scope finding: test_q.py outside Scope
    monkeypatch.setattr(test_foreman, "SECTION", test_foreman.SECTION.replace("`tests/unit/test_q.py` (modify), ", ""))
  rounds = [{**POSTED_R1, **({"test_delta": [entry_1]} if entry_1 else {})}]
  if round_2:  # round 2, posted after the ruling when it carries a test-delta entry, else with round 1
    rounds.append({**R2, **({"test_delta": [entry_2], "posted_at": "2026-11-02T15:00:00Z"} if entry_2 else {})})
  n = len(rounds) + 1
  reply_at = "2026-11-02T16:00:00Z"
  comments = {2: [c(13, "owner", f"**Ruling:** {ruling}", at=RULING_AT)],
              PR: [c(14, "builder-bot", f"**Reply {contested}:** contested — CI runs the suite", at=reply_at)]}
  kw = dict(rounds=rounds, launches=[{"round": i, "status": "exited 0"} for i in range(1, n + 1)], comments=comments)
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", **round_1})
  if round_2:  # recorded under round 2's ids, then its foreman-2-1 made round 1's carried copy, as `collect`'s carry writes it
    record(world, st0, rid, 2, "0" * 40, card0, {"change-review": "", **round_2})
    path = st0.path("reviews", rid, "round-2.json")
    held = json.loads(path.read_text(encoding="utf-8"))
    first = held["reviewers"]["foreman"]["findings"][0]
    first.update(id="foreman-1-1", carried_from=1)
    atomic_write(path, held)
  w = prepared(world, tmp_path, monkeypatch, **kw)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert code == 0, out
  lines = (w.dir / f"r{n}/foreman.findings").read_text(encoding="utf-8").splitlines()
  builder_contested = json.loads(w.st.path("reviews", w.rid, f"round-{n}.json").read_text(encoding="utf-8"))["builder_contested"]
  assert any(line.endswith(f"contested {contested}: CI runs the suite") for line in lines) is raised, lines
  assert len(builder_contested) == (1 if raised else 0)
