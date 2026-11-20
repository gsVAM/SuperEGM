# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U86

"""U86 (spec 1.2.1 section 7.6): a respec reaches the builder and the foreman. A touched filed unit is held, relaunched
with reason `respec` through `launch`'s slots, its prompt and `r<n>/amendments.md` carry the respecs its launch record
names, `finish` records the evidence that clears the mark (`head`, `builder_status`), and `status`, `tick_trigger`,
the wave and integrate act on `respec.actionable` and `respec.open`."""

import json
from pathlib import Path

import pytest

from test_u85 import HID, STARTED, MERGED_U1, R1_TEXT, BASE, respec_world

BOT = "superegm-builder[bot]"


def journal_of(st):
  path = st.path("journal")
  return path.read_text(encoding="utf-8") if path.is_file() else ""


def finish_world(world, tmp_path, pr, comment):
  """R1 applied touching filed U2 (issue 12), U2's PR `pr` (head `abc123`) or none, one running launch naming R1 and,
  when `comment`, the builder's status comment with that word posted after the launch started."""
  import superegm
  u2 = {"number": 12, **({"pr": {"number": pr, "head": "abc123"}} if pr else {})}
  spec, st = respec_world(world, [(BASE, None), (R1_TEXT, "R1")], {"R1": ["U2"]},
                          state_units={"U0": MERGED_U1["U0"], "U1": {"number": 11}, "U3": {}, "U2": u2})
  superegm.atomic_write(st.path("file", "respec_comment_U2_R1.md"), "**Spec correction R1** for U2\n")
  result = tmp_path / "U2_r1.json"
  Path(str(result) + ".exit").write_text("0\n", encoding="utf-8")
  entry = {"round": 1, "status": "running", "started_at": STARTED, "result_file": str(result), "respecs": ["R1"], "reason": "respec"}
  superegm.atomic_write(st.path("launches", "U2"), {"unit": "U2", "launches": [entry]})
  if pr:
    world.gh.prs[pr] = {"number": pr, "headRefOid": "abc123", "state": "OPEN"}
  world.gh.comments[12] = [
    {"id": 1, "user": {"login": BOT}, "body": "**Builder status:** BLOCKED", "created_at": "2026-11-12T12:00:00Z"},  # before started_at
  ] + ([{"id": 2, "user": {"login": BOT}, "body": f"**Builder status:** {comment}\n- abc123 feat", "created_at": "2026-11-13T02:00:00Z"}]
       if comment else [])
  return st


@pytest.mark.parametrize("pr, comment, gh_fails, head, word, mark", [
  (7, "DONE", None, "abc123", "DONE", None), (7, "BLOCKED", None, "abc123", "BLOCKED", "respec: R1"),
  (None, "DONE", None, None, "DONE", "respec: R1"), (7, None, None, "abc123", None, "respec: R1"),
  (7, "DONE", "head", None, "DONE", "respec: R1"), (7, "DONE", "builder_status", "abc123", None, "respec: R1")])
def test_finish_records_head_and_builder_status(world, tmp_path, pr, comment, gh_fails, head, word, mark):
  # finish reads the PR head and the last accepted builder comment since started_at; a failed read nulls that field only
  from superegm import record_launch, respec
  st = finish_world(world, tmp_path, pr, comment)
  handoff = HID
  if gh_fails == "head":
    world.gh.extend("pr", lambda args, cwd, token=None: (1, "", "gh: HTTP 502"))
  elif gh_fails == "builder_status":
    world.gh.extend("api", lambda args, cwd, token=None: (1, "", "gh: HTTP 502"))
  launches = json.loads(st.path("launches", "U2").read_text(encoding="utf-8"))["launches"]
  record_launch.finish(st, "U2", launches, launches[-1], "exited 0", None, "U2 launch 1 exited 0")
  exit_record = json.loads(st.path("launches", "U2").read_text(encoding="utf-8"))["launches"][-1]
  journal = journal_of(st)
  assert exit_record["status"] == "exited 0" and "U2 launch 1 exited 0" in journal
  assert ("head" in exit_record) is (head is not None)
  if pr and gh_fails != "head":  # the PR read by its own number, never the issue's
    assert any(c[:3] == ["pr", "view", "7"] for c in world.gh.calls)
  assert (exit_record.get("head"), exit_record["builder_status"]) == (head, word) and respec.marks(st, handoff).get("U2") == mark
  assert (f"U2 launch 1 exit read failed: {gh_fails}" in journal) == bool(gh_fails)


@pytest.mark.parametrize("login, body, accepted", [
  ("superegm-builder[bot]", "**Builder status:** DONE", True), ("superegm-builder[bot]", "**Deviation (spec):** x.md:3", True),
  ("stranger", "**Builder status:** DONE", False), ("superegm-builder[bot]", "Quoting:\n**Builder status:** DONE", False)])
def test_builder_comment_filter(login, body, accepted):
  # one filter, moved out of builder_facts, used by builder_facts and finish
  from superegm import record_launch, status
  assert status.builder_comment({"user": {"login": login}, "body": body}, {"superegm-builder[bot]"}) is accepted
  facts = Path(status.__file__).read_text(encoding="utf-8").split("def builder_facts", 1)[1].split("\ndef ", 1)[0]
  assert "builder_comment(" in facts and "builder_comment(" in Path(record_launch.__file__).read_text(encoding="utf-8")
