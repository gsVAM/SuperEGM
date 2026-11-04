# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U11's tests: `judges question`, the leavemealone routing, `close`, the
# integrate skill, the docs, the README and the removed-mechanism sweep.

"""U11: leavemealone routing and finish (design sections 12, 13.2 and 15)."""

import json
import re
from pathlib import Path

import pytest

from conftest import REPO
from superegm import atomic_write, store

ROOT = Path(__file__).resolve().parents[2]
HEAD = "a" * 64
FINDING = "change-review-1-1 | high | src/x.py:3 | regression: no | the retry loop never backs off"
LOW = "change-review-1-2 | low | src/x.py:9 | regression: no | a stray print"
CI = "foreman-1-1 | high | ci | regression: no | CI not green on this head"
INTERFACE_COMMENT = ("**Deviation (interface):** `deliver(job)` needs a `retries` argument\n"
                     "**Builder status:** BLOCKED\n- (a) add `retries: int = 5` to `deliver`\n"
                     "- (b) read the ceiling from config\n")


def put(world, obj, *key):
  path = store(world.repo).path(*key)
  if isinstance(obj, str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj, encoding="utf-8")
  else:
    atomic_write(path, obj)
  return path


def seed(world):
  """One handoff: U07 filed as #410, U08 (#412) consumes a U07 name, U09 (#415) does not."""
  put(world, {"handoff_id": "sample-design-abc123",
              "design": {"path": str(world.spec.resolve())},  # require_runcard matches a --unit call against it
              "units": {"U07": {"number": 410}, "U08": {"number": 412}, "U09": {"number": 415}}}, "state")
  put(world, {"units": {"U07": {"decisions": [{"id": "D1", "question": "Retry ceiling?", "owner": "gsVAM",
                                                "options": ["(a) 5 attempts", "(b) 10 attempts"],
                                                "default": "a", "blocking": True}]}}}, "units")
  put(world, "### U08: Admin\n\n## Interfaces\n- Consumes: deliver (U07)\n", "unit", "U08")
  put(world, "### U09: Queue\n\n## Interfaces\n- Consumes: enqueue (U01)\n", "unit", "U09")


def comment(world, cid, body):
  """A builder comment served at `gh api repos/<repo>/issues/comments/<id>`; every other route stays `do_api`'s."""
  world.gh.comments[cid] = {"id": cid, "user": {"login": "builder-bot"}, "body": body}

  def api(args, cwd, token=None):
    match = re.fullmatch(rf"repos/{REPO}/issues/comments/(\d+)", world.gh.endpoint_of(args))
    return world.gh.ok(world.gh.comments[int(match.group(1))]) if match else world.gh.do_api(args)
  world.gh.extend("api", api)


def record(world, review, reviewer, lines, runcard, tmp_path):
  path = tmp_path / f"{reviewer}.txt"
  path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
  code, out = world.run("review", "record", "--review", review, "--round", "1", "--sha256", HEAD,
                        "--reviewer", reviewer, "--findings", str(path), "--isolation", "clean",
                        "--model", "inherit:opus", "--effort", "max:max", "--runcard", runcard)
  assert code == 0, out


def head_review(world, runcard, tmp_path):
  code, out = world.run("review", "open", "--kind", "head", "--artifact", "U07", "--sha256", HEAD,
                        "--reviewers", "change-review", "--runcard", runcard)
  assert code == 0, out
  review = out.strip()
  # A head's rounds are the unit's `rounds[]` entries (U04): `review record` needs round 1's.
  put(world, {"dispatch_id": "d1", "decisions": [], "rulings": [],
              "rounds": [{"round": 1, "runcard": runcard, "launch": 1, "head": HEAD, "phase": "collected",
                          "dispatch_id": "d1", "outcome": None, "posted_at": None}]}, "foreman", "U07")
  record(world, review, "change-review", [FINDING, LOW], runcard, tmp_path)
  record(world, review, "foreman", [CI], runcard, tmp_path)
  return review


@pytest.mark.parametrize("form", ["round", "cap", "decision", "blocked-comment", "blocked-launch", "blocked-closed"])
def test_judges_question_forms(world, tmp_path, form):
  seed(world)
  runcard = world.card("wave")
  review = head_review(world, runcard, tmp_path)
  comment(world, 123, INTERFACE_COMMENT)
  put(world, {"launches": [{"round": 1, "status": "exited 0"}]}, "launches", "U07")
  args, expected = {
      "round": (["--review", review, "--round", "1", "--reason", "change-review-1-1=the test covers it"],
                "## Q1 change-review-1-1 (high, src/x.py:3): the retry loop never backs off\n"
                "- (a) finding upheld\n- (b) finding overruled — the test covers it\n"),
      "cap": (["--review", review, "--cap"], f"## Q1 {review} is at its cap\n- (a) one more round\n- (b) stop\n"),
      "decision": (["--unit", "U07", "--decision", "D1"],
                   "## Q1 U07 D1: Retry ceiling?\n- (a) 5 attempts\n- (b) 10 attempts\n"),
      "blocked-comment": (["--unit", "U07", "--blocked", "123"],
                          "## Q1 U07 BLOCKED (comment 123): **Deviation (interface):** `deliver(job)` needs a `retries` argument\n"
                          "- (a) add `retries: int = 5` to `deliver`\n- (b) read the ceiling from config\n- (c) stop the unit\n"),
      "blocked-launch": (["--unit", "U07", "--blocked", "launch", "1"],
                         "## Q1 U07 launch 1 (exited 0) ended with no pull request\n- (a) relaunch\n- (b) stop the unit\n"),
      "blocked-closed": (["--unit", "U07", "--blocked", "closed", "41"],
                         "## Q1 U07: #41 was closed by the builder account\n- (a) relaunch\n- (b) stop the unit\n"),
  }[form]
  code, out = world.run("judges", "question", *args, "--runcard", runcard)
  assert code == 0, out
  path = Path(out.splitlines()[0])
  assert path.is_file() and path.read_text(encoding="utf-8") == expected
  assert f"question rendered: {path}" in (world.artifacts / "journal.md").read_text(encoding="utf-8")
  code, out = world.run("judges", "open", "--question", str(path), "--evidence", str(world.spec), "--parent", runcard)
  assert code == 0, out
  code, out = world.run("judges", "question", *args, card=None)
  assert code == 1 and "runcard: --runcard is required" in out, out


@pytest.mark.parametrize("case, args, message", [
    ("ci", ["--review", "{review}", "--round", "1", "--reason", "foreman-1-1=flaky"],
     "question: foreman-1-1 is the CI finding"),
    ("low", ["--review", "{review}", "--round", "1", "--reason", "change-review-1-2=cosmetic"],
     "question: change-review-1-2 is low"),
    ("unknown", ["--review", "{review}", "--round", "1", "--reason", "design-1-9=x"],
     "question: design-1-9 is not in round 1"),
    ("continue-used", ["--review", "{review}", "--cap"],
     "question: continue already ruled on {review}; stop is the only option"),
    ("relaunch-used", ["--unit", "U07", "--blocked", "launch", "1"],
     "question: relaunch already used on U07"),
])
def test_judges_question_refusals(world, tmp_path, case, args, message):
  seed(world)
  runcard = world.card("wave")
  review = head_review(world, runcard, tmp_path)
  put(world, {"launches": [{"round": 1, "status": "exited 1"}]}, "launches", "U07")
  if case == "continue-used":
    # `review rule` refuses `not at the cap` after one round: the ruling it would write is seeded.
    record = json.loads(store(world.repo).path("reviews", review, "review.json").read_text(encoding="utf-8"))
    record["rulings"].append({"id": "R1", "ruling": "continue", "by": "owner", "at": "2026-11-03T00:00:00Z"})
    put(world, record, "reviews", review, "review.json")
  if case == "relaunch-used":
    put(world, {"dispatch_id": None, "rounds": [], "decisions": [{"id": "d1", "point": 3}],
                "rulings": [{"decision": "d1", "ruling": "relaunch", "by": "judges:p1"}]}, "foreman", "U07")
  before = sorted(str(p) for p in world.artifacts.rglob("*.md"))
  code, out = world.run("judges", "question", *[a.format(review=review) for a in args], "--runcard", runcard)
  assert code == 1 and message.format(review=review) in out, out
  assert sorted(str(p) for p in world.artifacts.rglob("*.md")) == before
