# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U23's tests of the inbox and the notify hook (spec section 11.2).

"""U23: `inbox_items` and `superegm inbox`, `notify_lines` and `superegm notify`.
Fixtures: conftest's `world`; `wave_store` and `open_wave_card` from test_wave.py."""

import json
import os
import time
from pathlib import Path

import pytest

from conftest import REPO, set_config
from superegm import atomic_write
from superegm.decision import ruling_form
from superegm.inbox import inbox_items, notify_lines
from superegm.review import parse_findings
from test_wave import open_wave_card, wave_store

ISSUE, PULL = f"https://github.com/{REPO}/issues/2", f"https://github.com/{REPO}/pull/70"


def seed(world, escalated=(), **units):
  """`wave_store`, then `handoffs/<id>.json`, a unit's `stopped` into its foreman file, its `reviews`
  `{rid: (review.json, {n: round-n.json})}` under `s.path("reviews", rid)`, `escalated` into
  `approvals/sample.json`'s record."""
  s = wave_store(world, **{uid: {k: v for k, v in u.items() if k not in ("stopped", "reviews")} for uid, u in units.items()})
  atomic_write(s.path("handoffs", s.handoff_id), {"id": s.handoff_id, "spec": str(world.spec), "opened_at": "t", "closed_at": None})
  for uid, u in units.items():
    if "stopped" in u:
      foreman = json.loads(s.path("foreman", uid).read_text(encoding="utf-8"))
      atomic_write(s.path("foreman", uid), foreman | {"stopped": u["stopped"]})
    for rid, (review, rounds) in (u.get("reviews") or {}).items():
      atomic_write(s.path("reviews", rid, "review.json"), review)
      for n, rnd in rounds.items():
        atomic_write(s.path("reviews", rid, f"round-{n}.json"), rnd)
  record = json.loads(s.path("approvals", "sample").read_text(encoding="utf-8"))
  (record["entries"][-1] if "entries" in record else record)["escalated"] = list(escalated)  # a 1.1 record is one entry
  atomic_write(s.path("approvals", "sample"), record)
  return s


ALLOWED = lambda fid: f"**Ruling:** {fid} allowed — <reason>"
CONTESTED = lambda fid: f"**Ruling:** {fid} finding upheld | finding overruled — <reason>"
OPTION = lambda did, menu="": f"**Ruling:** ({did}) <option> — <reason>{menu}"
CAP = "**Ruling:** one more round | stop | redesign — <reason>"
F = lambda *sevs: parse_findings("\n".join(f"foreman-1-{i} | {s} | src/x.py:3 | regression: no | c" for i, s in enumerate(sevs, 1)), "foreman", 1)
ROUND = lambda n, findings, **more: {"round": n, "runcard": "wave-1", "artifact_sha256": "a" * 40, "what_ran": "completed", "reviewers": {"foreman": {"findings": findings}}, **more}
REVIEW = lambda kind, rid, rounds, **more: {rid: ({"kind": kind, "artifact": "U01", "cycle": 1, "reviewers": ["foreman"], "runcard": "wave-1", "converged": "no", "rulings": [], **more}, rounds)}
HEAD = lambda n, findings, **more: REVIEW("head", "head-U01-c1", {i: ROUND(i, findings, **more) for i in range(1, n + 1)})
POSTED = lambda n=1, outcome="revise": [{"round": i, "phase": "posted", "outcome": outcome, "launch": i, "runcard": "wave-1"} for i in range(1, n + 1)]
D = lambda point, source, **more: [{"id": "q1", "point": point, "source": source, "question": "q", "asked_at": "t", **more}]
U = lambda **more: {"U01": {"pr": 70, "head": "a" * 40, "ci": "green", **more}}
KINDS = {"decision", "cap", "contested", "merge", "stalled", "escalated", "redesign", "test-delta", "owner", "kill_failed", "wave"}


@pytest.mark.parametrize("seeded, expect", [
  (U(decisions=D(3, "comment 77")), [("U01", "decision", f"{OPTION('77')} on {ISSUE}", "U01/decision/q1")]),
  (U(decisions=D(5, "review head-U01-c1 round 1", options=["accept", "revise"])), [("U01", "decision", f"{OPTION('q1', ' (accept | revise)')} on {ISSUE}", "U01/decision/q1")]),
  (U(decisions=D(1, "review head-U01-c1 round 1"), rounds=POSTED(), reviews=HEAD(1, F("high", "medium"), builder_contested=[{"fid": f"foreman-1-{i}", "reason": "r"} for i in (1, 2)])),
   [("U01", "contested", f"{CONTESTED(f'foreman-1-{i}')} on {ISSUE}", f"U01/contested/q1/foreman-1-{i}") for i in (1, 2)]),
  (U(decisions=D(1, "review head-U01-c1 round 5") + D(2, "review head-U01-c1 cap", id="q2"), rounds=POSTED(5), reviews=HEAD(5, F("high"), builder_contested=[{"fid": "foreman-1-1", "reason": "r"}])),
   [("U01", "cap", f"{CAP} on {ISSUE}", "U01/cap/q2")]),
  (U(rounds=POSTED(5), reviews=HEAD(5, F("high"))), [("U01", "cap", "/superegm:wave <spec>", "U01/cap/head-U01-c1")]),
  (U(reviews=REVIEW("plan", "plan-U01-c1", {n: ROUND(n, F("high")) for n in range(1, 6)})),
   [("plan-U01-c1", "cap", "superegm review rule --review plan-U01-c1 --ruling continue|accept|stop --owner --runcard <card>", "plan-U01-c1/cap/5")]),
  (U(reviews=REVIEW("plan", "plan-U01-c1", {n: ROUND(n, F("high")) for n in range(1, 6)}, rulings=[{"ruling": "stop"}])), []),
  (U(rounds=POSTED(1, "clean")), [("U01", "merge", PULL, "U01/merge/1")]),
  (U(rounds=[{"round": n, "phase": "collected", "outcome": "not run (error: x)", "runcard": "wave-1"} for n in (1, 2)], reviews=HEAD(0, [])),
   [("U01", "stalled", "/superegm:wave <spec>", "U01/stalled/head-U01-c1/2")]),
  ({"escalated": ["spec-sample-c1:design-1-1"], **U()}, [("spec-sample-c1", "escalated", "/superegm:plan <spec>", "spec-sample-c1/escalated/design-1-1")]),
  (U(reviews=REVIEW("integrate", "spec-sample-integrate-c1", {1: ROUND(1, [{**F("high")[0], "disposition": "escalated"}])})),
   [("spec-sample-integrate-c1", "escalated", "superegm review settle --review spec-sample-integrate-c1 --finding foreman-1-1 --disposition fixed | declined --owner --runcard <card>", "spec-sample-integrate-c1/escalated/foreman-1-1")]),
  (U(stopped={"by": "judges:p1", "reason": "redesign — why", "at": "t", "brief": "/s/U01-q1.brainstorm.md"}), [("U01", "redesign", "/superegm:brainstorming /s/U01-q1.brainstorm.md", "U01/redesign/U01-q1.brainstorm.md")]),
  (U(rounds=POSTED(), reviews=HEAD(1, [{**F("high")[0], "claim": "test-delta: tests/test_x.py:3 removed"}])), [("U01", "test-delta", f"{ALLOWED('foreman-1-1')} on {ISSUE}", "U01/test-delta/1/foreman-1-1")]),
  (U(rounds=POSTED(1, "owner: foreman-1-1, foreman-1-2")), [("U01", "owner", f"{ALLOWED(f'foreman-1-{i}')} on {ISSUE}", f"U01/owner/1/foreman-1-{i}") for i in (1, 2)])])
def test_inbox_items_lists_what_needs_the_owner(world, seeded, expect):
  card = open_wave_card(world)
  s = seed(world, **seeded)
  items = inbox_items(s, [s.handoff_id])
  assert [(i["subject"], i["kind"], i["action"], i["fingerprint"]) for i in items] == \
      [(sub, kind, act.replace("<spec>", str(world.spec)), fp) for sub, kind, act, fp in expect] + [(card, "wave", "information: open 0 min", card)]
  assert all(i["repo"] == REPO for i in items) and {i["kind"] for i in items} <= KINDS
  assert ALLOWED("f-1") == ruling_form(1, "f-1", "allowed")


def test_inbox_prints_one_line_per_item(world):
  assert world.run("inbox") == (0, "")
  card = open_wave_card(world)
  s = seed(world, **U(decisions=D(3, "comment 77")))
  hid, line = s.handoff_id, f"{REPO} U01 | decision | {OPTION('77')} on {ISSUE}"
  assert world.run("inbox") == (0, f"{line}\n{REPO} {card} | wave | information: open 0 min\n")
  assert json.loads(world.run("inbox", "--json")[1].splitlines()[0]) == {"repo": REPO, "subject": "U01", "kind": "decision", "action": line.split(" | ", 2)[2], "fingerprint": "U01/decision/q1"}
  assert world.run("inbox", "--all")[1] == "registry: none\n" + world.run("inbox")[1]
  atomic_write(s.path("handoffs", hid), json.loads(s.path("handoffs", hid).read_text(encoding="utf-8")) | {"closed_at": "t"})
  assert world.run("inbox") == (0, "") and "notified" not in json.loads(s.path("state").read_text(encoding="utf-8"))
  atomic_write(s.path("handoffs", "sample-ffffff"), {"id": "sample-ffffff", "spec": str(world.spec), "opened_at": "t", "closed_at": None})  # approved, never planned: no state.json
  atomic_write(s.path("approvals", "sample"), {"path": str(world.spec), "entries": [{"escalated": ["spec-sample-c1:design-1-1"]}]})
  assert world.run("inbox") == (0, f"{REPO} spec-sample-c1 | escalated | /superegm:plan {world.spec}\n")


@pytest.mark.parametrize("hook, journal", [("exit 0", "hook exit 0"), ("exit 3", "hook exit 3"), ("sleep 3", "hook timeout"), ("", "hook failed: Permission denied"), (None, "no hook")])
def test_notify_runs_the_hook_once_with_the_new_lines(world, tmp_path, monkeypatch, hook, journal):
  monkeypatch.setenv("HOME", str(tmp_path / "home"))
  got, script = tmp_path / "got", tmp_path / "home/.superegm/notify"
  if hook is not None:
    script.parent.mkdir(parents=True)
    script.write_text(f"#!/bin/sh\ncat > '{got}'\n{hook}\n", encoding="utf-8")
    script.chmod(0o755 if hook else 0o644)
  set_config(world, repo=REPO, notify_timeout_seconds=1)
  card = open_wave_card(world)
  s = seed(world, **U(decisions=D(3, "comment 77")))
  lines, notified = world.run("inbox")[1], lambda: json.loads(s.path("state").read_text(encoding="utf-8"))["notified"]
  assert world.run("notify", "--runcard", card) == (0, "")
  assert got.read_text(encoding="utf-8") == lines if hook else not got.exists()
  assert notified() == sorted(["U01/decision/q1", card]) and f"notify: {journal} (2 new)" in s.path("journal").read_text(encoding="utf-8")
  got.exists() and got.unlink()
  assert world.run("notify", "--runcard", card) == (0, "") and not got.exists() and notified() == sorted(["U01/decision/q1", card])


def test_a_point_1_decision_lists_each_finding_until_its_own_ruling(world):
  """Round 2 (astra-1-1): point 1 takes one ruling per contested finding, so a ruled fid leaves and the other stays."""
  card = open_wave_card(world)
  s = seed(world, **U(decisions=D(1, "review head-U01-c1 round 1"), rulings=[{"decision": "q1", "ruling": "foreman-1-1 finding upheld — r"}],
                      rounds=POSTED(), reviews=HEAD(1, F("high", "medium"), builder_contested=[{"fid": f"foreman-1-{i}", "reason": "r"} for i in (1, 2)])))
  assert [i["fingerprint"] for i in inbox_items(s, [s.handoff_id])] == ["U01/contested/q1/foreman-1-2", card]


def test_a_test_delta_finding_the_outcome_also_names_is_one_line(world):
  """Round 2 (astra-1-5): one finding, one line, whether `test-delta` or `owner: <ids>` names it."""
  card = open_wave_card(world)
  s = seed(world, **U(rounds=POSTED(1, "owner: foreman-1-1, foreman-1-2"),
                      reviews=HEAD(1, [{**F("high")[0], "claim": "test-delta: tests/test_x.py:3 removed"}])))
  assert [(i["kind"], i["fingerprint"]) for i in inbox_items(s, [s.handoff_id])] == \
      [("test-delta", "U01/test-delta/1/foreman-1-1"), ("owner", "U01/owner/1/foreman-1-2"), ("wave", card)]


def test_an_escalation_is_its_own_handoffs_once_and_leaves_once_handled(world):
  """Round 2 (astra-1-6, astra-1-7): two open handoffs of one spec list the approval's escalation once, under the
  handoff the entry names; a pair the spec's `## Units` names, or a unit's decision carries, is handled."""
  open_wave_card(world)
  s = seed(world, escalated=["spec-sample-c1:design-1-1"], **U(decisions=D(3, "comment 77")))
  atomic_write(s.path("handoffs", "sample-ffffff"), {"id": "sample-ffffff", "spec": str(world.spec), "opened_at": "t", "closed_at": None})
  esc = lambda: [(i["subject"], i["kind"]) for i in inbox_items(s, sorted([s.handoff_id, "sample-ffffff"])) if i["kind"] == "escalated"]
  assert esc() == [("spec-sample-c1", "escalated")]
  foreman = json.loads(s.path("foreman", "U01").read_text(encoding="utf-8"))
  atomic_write(s.path("foreman", "U01"), foreman | {"decisions": D(3, "comment 77", question="spec-sample-c1:design-1-1: the claim")})
  assert esc() == []
  atomic_write(s.path("foreman", "U01"), foreman)
  world.spec.write_text(world.spec.read_text(encoding="utf-8") + "\n## Units\n\n| U01 | spec-sample-c1:design-1-1 |\n", encoding="utf-8")
  assert esc() == []


def test_inbox_handoff_reads_the_named_handoff_alone(world):
  """Round 2 (change-review-1-1): `--handoff` names one handoff of the index; an unknown id is refused."""
  open_wave_card(world)
  s = seed(world, **U(decisions=D(3, "comment 77")))
  atomic_write(s.path("handoffs", "sample-ffffff"), {"id": "sample-ffffff", "spec": str(world.spec), "opened_at": "t", "closed_at": None})
  assert world.run("inbox", "--handoff", "sample-ffffff") == (0, "")
  assert f"{REPO} U01 | decision | " in world.run("inbox", "--handoff", s.handoff_id)[1]
  code, out = world.run("inbox", "--handoff", "sample-000000")
  assert code == 1 and "store: sample-000000: no such handoff" in out


def test_notify_lines_reads_the_cards_handoff(world):
  """Round 2 (astra-1-2): the card's `handoff`, the key `runcard open` writes, chooses the handoff."""
  open_wave_card(world)
  s = seed(world, **U(decisions=D(3, "comment 77")))
  atomic_write(s.path("handoffs", "sample-ffffff"), {"id": "sample-ffffff", "spec": str(world.spec), "opened_at": "t", "closed_at": None})
  assert [i["subject"] for i in notify_lines(s, {"handoff": "sample-ffffff"})] == []
  assert "U01" in [i["subject"] for i in notify_lines(s, {"handoff": s.handoff_id})]


def alive(pid: int) -> bool:
  try:
    os.kill(pid, 0)
  except ProcessLookupError:
    return False
  return True


@pytest.mark.parametrize("hook, journal", [("printf '\\377'", "hook exit 0"), ('sleep 30 & echo $! > "$0.pid"; wait', "hook timeout")])
def test_a_hook_that_writes_bytes_or_leaves_a_child_never_stops_notify(world, tmp_path, monkeypatch, hook, journal):
  """Round 2 (astra-1-3, astra-1-4): undecodable output is never decoded; the timeout ends the hook's process group."""
  monkeypatch.setenv("HOME", str(tmp_path / "home"))
  script = tmp_path / "home/.superegm/notify"
  script.parent.mkdir(parents=True)
  script.write_text(f"#!/bin/sh\ncat > /dev/null\n{hook}\n", encoding="utf-8")
  script.chmod(0o755)
  set_config(world, repo=REPO, notify_timeout_seconds=1)
  card = open_wave_card(world)
  s = seed(world, **U(decisions=D(3, "comment 77")))
  assert world.run("notify", "--runcard", card) == (0, "")
  assert f"notify: {journal} (2 new)" in s.path("journal").read_text(encoding="utf-8")
  assert "notified" in json.loads(s.path("state").read_text(encoding="utf-8"))
  pidfile = Path(f"{script}.pid")
  if pidfile.exists():
    pid, deadline = int(pidfile.read_text(encoding="utf-8").strip()), time.time() + 3
    while time.time() < deadline and alive(pid):
      time.sleep(0.05)
    assert not alive(pid)
