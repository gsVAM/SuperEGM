# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U102, settled findings stay settled (spec section 3.5).

"""U102: `collect` drops a builder's contest of a settled fid (or of one derived from a settled fid), an owner's
`test-delta <file> allowed` widens Scope for that file, and a test-delta settlement follows the test and the line
text across a merge of main, a 1.2.1 entry's base-commit-and-line key and a judges' overrule still honoured.
Fixtures: conftest's `world` and test_foreman's `seed`, `pr_repo`, `prepared` and `open_head_review`."""

import json

import pytest

from superegm import foreman as foreman_mod

from test_foreman import (POSTED_R1, PR, UNIT, builder_token, c, open_head_review, prepared, record,  # noqa: F401
                          seed)

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
