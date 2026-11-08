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
from superegm import atomic_write, handoff_store
from superegm.decision import ruling_form
from superegm.inbox import inbox_items, notify_lines
from superegm.review import parse_findings
from superegm.decision import parse_form
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
# round 7 (foreman-6-1 upheld, comment 6727690269): each choice is its own form, the reason on the forms that take one
CONTESTED = lambda fid: f"**Ruling:** {fid} finding upheld | **Ruling:** {fid} finding overruled — <reason>"
OPTION = lambda did, menu="": f"**Ruling:** ({did}) <option> — <reason>{menu}"
CAP = "**Ruling:** one more round | **Ruling:** stop | **Ruling:** redesign — <reason>"
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


@pytest.mark.parametrize("hook, journal", [("printf '\\377'", "hook exit 0"), ('sleep 30 & echo $! > "$0.pid"; wait', "hook timeout"),
                                           # round 3 (astra-2-6, change-review-2-2): a child that leaves the group keeps no pipe of notify's open
                                           ("python3 -c 'import os, time; os.setsid(); time.sleep(8)' & echo $! > \"$0.setsid\"; sleep 30", "hook timeout")])
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
  started = time.time()
  assert world.run("notify", "--runcard", card) == (0, "")
  escaped = Path(f"{script}.setsid")
  if escaped.exists() and alive(int(escaped.read_text(encoding="utf-8").strip())):
    os.kill(int(escaped.read_text(encoding="utf-8").strip()), 9)
  assert time.time() - started < 6
  assert f"notify: {journal} (2 new)" in s.path("journal").read_text(encoding="utf-8")
  assert "notified" in json.loads(s.path("state").read_text(encoding="utf-8"))
  pidfile = Path(f"{script}.pid")
  if pidfile.exists():
    pid, deadline = int(pidfile.read_text(encoding="utf-8").strip()), time.time() + 3
    while time.time() < deadline and alive(pid):
      time.sleep(0.05)
    assert not alive(pid)


def second_handoff(world, s, hid="sample-ffffff"):
  """A second open handoff of the same spec, its state and foremen copied from the first's."""
  atomic_write(s.path("handoffs", hid), {"id": hid, "spec": str(world.spec), "opened_at": "t", "closed_at": None})
  b = handoff_store(s, hid)
  atomic_write(b.path("state"), json.loads(s.path("state").read_text(encoding="utf-8")))
  for path in s.path("foreman", "U01").parent.glob("*.json"):
    atomic_write(b.path("foreman", path.stem), json.loads(path.read_text(encoding="utf-8")))
  return b


def test_two_handoffs_each_list_their_own_units_lines(world):
  """Round 3 (astra-2-1, codebase-details-2-1): unit and decision ids repeat across handoffs, so each handoff's
  unit lines are its own; only a spec-level escalation is listed once."""
  open_wave_card(world)
  s = seed(world, escalated=["spec-sample-c1:design-1-1"], **U(decisions=D(3, "comment 77")))
  second_handoff(world, s)
  items = inbox_items(s, sorted([s.handoff_id, "sample-ffffff"]))
  assert [i["fingerprint"] for i in items if i["kind"] == "decision"] == ["U01/decision/q1", "U01/decision/q1"]
  assert len([i for i in items if i["kind"] == "escalated"]) == 1


def test_notify_writes_the_cards_handoffs_set_whatever_handoff_resolved(world):
  """Round 3 (astra-2-2, change-review-2-1, codebase-details-2-4): the lines, the journal and the `notified` set are
  the card's handoff's; `--handoff` naming another leaves that one's set alone."""
  card = open_wave_card(world)
  s = seed(world, **U(decisions=D(3, "comment 77")))
  b = second_handoff(world, s)
  atomic_write(b.path("state"), json.loads(b.path("state").read_text(encoding="utf-8")) | {"notified": ["x"]})
  assert world.run("notify", "--handoff", "sample-ffffff", "--runcard", card)[0] == 0
  assert json.loads(b.path("state").read_text(encoding="utf-8"))["notified"] == ["x"]
  assert json.loads(s.path("state").read_text(encoding="utf-8"))["notified"] == sorted(["U01/decision/q1", card])
  assert "notify: no hook (2 new)" in s.path("journal").read_text(encoding="utf-8")


def test_an_owner_finding_settled_or_ruled_leaves_the_inbox(world):
  """Round 3 (astra-2-4): the outcome keeps naming a settled fid until the round converges; the line leaves at its
  settlement or its point-1 ruling."""
  card = open_wave_card(world)
  findings = F("high", "high", "high")
  findings[0]["disposition"] = "allowed"
  s = seed(world, **U(rounds=POSTED(1, "owner: foreman-1-1, foreman-1-2, foreman-1-3"), reviews=HEAD(1, findings),
                      decisions=D(1, "review head-U01-c1 round 1", question="foreman-1-2 | high | src/x.py:3 | regression: no | c"),
                      rulings=[{"decision": "q1", "ruling": "foreman-1-2 finding overruled — r"}]))
  assert [i["fingerprint"] for i in inbox_items(s, [s.handoff_id])] == ["U01/owner/1/foreman-1-3", card]


def test_an_allowance_on_an_open_decision_takes_the_overrule_form_in_leavemealone(world):
  """Round 3 (astra-2-3): in leavemealone-mode `decision rule` refuses an `allowed` comment naming an open point-1
  decision, so the line offers the overrule form there; elsewhere, and in normal mode, the allowance."""
  set_config(world, repo=REPO, mode="leavemealone")
  card = open_wave_card(world)
  s = seed(world, **U(rounds=POSTED(1, "owner: foreman-1-1, foreman-1-2"), reviews=HEAD(1, F("high", "high")),
                      decisions=D(1, "review head-U01-c1 round 1", question="foreman-1-1 | high | src/x.py:3 | regression: no | c")))
  assert [i["action"] for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "owner"] == \
      [f"{ruling_form(1, 'foreman-1-1', 'finding overruled')} on {ISSUE}", f"{ALLOWED('foreman-1-2')} on {ISSUE}"]
  assert card


def test_an_escalation_a_plan_decision_routes_leaves_once_answered(world):
  """Round 3 (astra-2-5, codebase-details-2-2): graph accepts an escalated pair a `blocking: yes` D<n> line names;
  until `decide` answers it the line names that decide call, then it leaves."""
  open_wave_card(world)
  s = seed(world, escalated=["spec-sample-c1:design-1-1"], **U())
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  answers = state.pop("decisions")  # `apply` filed after `decide` answered D2; here it is still open
  atomic_write(s.path("state"), state)
  plan = Path(state["plan"])
  plan.write_text(plan.read_text(encoding="utf-8").replace("D2 Page size for the listing?", "D2 Page size (spec-sample-c1:design-1-1: c)?"), encoding="utf-8")
  esc = lambda: [(i["subject"], i["action"]) for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "escalated"]
  assert esc() == [("spec-sample-c1", "superegm decide --unit U03 --decision D2 --answer <option> --runcard <card>")]
  atomic_write(s.path("state"), state | {"decisions": answers})
  assert "U03/D2" in answers and esc() == []


@pytest.fixture(autouse=True)
def no_owner_hook(tmp_path, monkeypatch):
  """Round 4 (astra-3-2): every test here runs with HOME under `tmp_path`, so no owner's ~/.superegm/notify runs."""
  monkeypatch.setenv("HOME", str(tmp_path / "home"))


def test_a_spec_review_is_listed_under_its_own_specs_handoff_alone(world, tmp_path):
  """Round 4 (astra-3-3): the store's `reviews/spec-*` are the spec's: a capped review of spec B is listed under B's
  handoff and never under A's, whether one handoff or both are read."""
  open_wave_card(world)
  s = seed(world, **U())
  second_handoff(world, s)
  other = tmp_path / "other.md"
  other.write_text(world.spec.read_text(encoding="utf-8"), encoding="utf-8")
  atomic_write(s.path("handoffs", "sample-ffffff"), {"id": "sample-ffffff", "spec": str(other), "opened_at": "t", "closed_at": None})
  rid = "spec-other-c1"
  review, rounds = REVIEW("spec", rid, {n: ROUND(n, F("high")) for n in range(1, 6)}, artifact=str(other))[rid]
  atomic_write(s.root / "reviews" / rid / "review.json", review)
  for n, rnd in rounds.items():
    atomic_write(s.root / "reviews" / rid / f"round-{n}.json", rnd)
  caps = lambda ids: [i["subject"] for i in inbox_items(s, ids) if i["kind"] == "cap"]
  assert caps([s.handoff_id]) == [] and caps(["sample-ffffff"]) == [rid]
  assert caps(sorted([s.handoff_id, "sample-ffffff"])) == [rid]


@pytest.mark.parametrize("menu", [CAP, CONTESTED("foreman-1-1")])
def test_each_choice_of_a_menu_is_a_form_ruling_of_reads(menu):
  """Round 7 (astra-6-1, foreman-6-1 upheld): a choice copied from a menu, its reason filled in, is a ruling."""
  for choice in menu.split(" | "):
    assert parse_form(choice.replace("<reason>", "why")) is not None, choice


def legacy_handoff(world, s, hid="sample-legacy"):
  """A flat 1.0/1.1 handoff of the spec at the store's root, its unit U01 copied from the first handoff's."""
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  atomic_write(s.root / "state.json", state | {"handoff_id": hid, "design": {"path": str(world.spec)}})
  b = handoff_store(s, hid)
  atomic_write(b.path("foreman", "U01"), json.loads(s.path("foreman", "U01").read_text(encoding="utf-8")))
  return b


def capped_spec_review(s, rid, artifact):
  review, rounds = REVIEW("spec", rid, {n: ROUND(n, F("high")) for n in range(1, 6)}, artifact=str(artifact))[rid]
  atomic_write(s.root / "reviews" / rid / "review.json", review)
  for n, rnd in rounds.items():
    atomic_write(s.root / "reviews" / rid / f"round-{n}.json", rnd)


def test_a_legacy_handoff_lists_its_own_specs_reviews_alone(world, tmp_path):
  """Round 7 (astra-6-2, codebase-details-6-1): a flat store's `reviews/` is the store's own: a legacy handoff lists
  its spec's review and never another spec's, and a spec's review read under two handoffs is listed once."""
  open_wave_card(world)
  s = seed(world, **U())
  other = tmp_path / "other.md"
  other.write_text(world.spec.read_text(encoding="utf-8"), encoding="utf-8")
  atomic_write(s.path("handoffs", s.handoff_id), {"id": s.handoff_id, "spec": str(other), "opened_at": "t", "closed_at": None})
  legacy = legacy_handoff(world, s)
  assert legacy.legacy and legacy.path("reviews") == s.root / "reviews"
  capped_spec_review(s, "spec-other-c1", other)
  capped_spec_review(s, "spec-sample-c1", world.spec)
  caps = lambda ids: sorted(i["subject"] for i in inbox_items(s, ids) if i["kind"] == "cap")
  assert caps(["sample-legacy"]) == ["spec-sample-c1"] and caps([s.handoff_id]) == ["spec-other-c1"]
  assert caps(sorted(["sample-legacy", s.handoff_id])) == ["spec-other-c1", "spec-sample-c1"]


@pytest.mark.parametrize("mode, severity, flags", [("normal", "high", "--owner"), ("leavemealone", "low", "--owner"),
                                                   ("leavemealone", "high", "--owner --posted <comment id>")])
def test_an_escalated_integrate_findings_settle_line_carries_what_its_mode_needs(world, mode, severity, flags):
  """Round 7 (astra-6-3): in leavemealone a blocking finding is declined by the owner only with the comment id of
  their `**Ruling:** <fid> finding overruled — <reason>` (review.check_settle), so the line carries `--posted`."""
  set_config(world, repo=REPO, mode=mode)
  open_wave_card(world)
  rid = "spec-sample-integrate-c1"
  s = seed(world, **U(reviews=REVIEW("integrate", rid, {1: ROUND(1, [{**F(severity)[0], "disposition": "escalated"}])})))
  [line] = [i["action"] for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "escalated"]
  assert line == f"superegm review settle --review {rid} --finding foreman-1-1 --disposition fixed | declined {flags} --runcard <card>"
