# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U81

"""U81: spec §6.5 conformance of `amend`: the amendment is its own file `amendments/<comment id>.json`, written before the
ruling is saved; `launch_builder.amendments_for` reads the directory and a pre.1 handoff's `amendments[]`; amend's
refusals; the judges never amend."""

import json
import re
from pathlib import Path

import pytest

from test_pre1_amend import IFACE, LINE, OPTS, REPO, opened, rule, world_on
from test_wave import foreman_of

ISO = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def spy_writes(monkeypatch):
  """Every path `atomic_write` is given, in order."""
  import superegm
  order, real = [], superegm.atomic_write

  def spy(path, obj):
    order.append(Path(path))
    real(path, obj)
  monkeypatch.setattr(superegm, "atomic_write", spy)
  return order


def test_amendment_file_before_ruling(world, monkeypatch):
  # the amendment is its own file, written before the ruling is saved
  from superegm import decision
  card, s = world_on(world)
  world.gh.comments[9] = [{"id": i, "body": "x"} for i in range(1, 21)]  # the ruling comment is then comment 21
  qid = opened(world, card, IFACE + OPTS, source="comment 11")
  write_order = spy_writes(monkeypatch)
  code, out = rule(world, card, qid, f"amend — {LINE}")
  assert code == 0, out
  hdir = s.path("file")
  [entry] = json.loads((hdir / "amendments" / "11.json").read_text())  # file named by deviation comment 11
  assert ISO.match(entry["at"])
  assert entry == {"unit": "U01", "name": "dequeue", "text": LINE, "comment_id": 21, "at": entry["at"]}  # entry carries ruling comment 21
  assert write_order.index(hdir / "amendments" / "11.json") < write_order.index(s.path("foreman", "U02"))
  assert decision.WRITES == frozenset({"foreman", "reviews", "state", "file"})
  assert "amendments" not in json.loads((hdir / "state.json").read_text())


def test_rerun_after_crash_records_once(world, monkeypatch):
  # the ruling save fails after the amendment file is written; the rerun succeeds
  import superegm
  from superegm import launch_builder
  card, s = world_on(world)
  body = "## Interfaces\n- Produces: dequeue() -> Job | null\n"
  qid = opened(world, card, IFACE + OPTS, source="comment 11")
  real = superegm.save_foreman

  def crash(*args, **kwargs):
    monkeypatch.setattr(superegm, "save_foreman", real)
    raise OSError("disk full")
  monkeypatch.setattr(superegm, "save_foreman", crash)
  with pytest.raises(OSError):
    rule(world, card, qid, f"amend — {LINE}")
  hdir = s.path("file")
  first_bytes = (hdir / "amendments" / "11.json").read_bytes()
  assert not foreman_of(s, "U02")["rulings"]
  code, out = rule(world, card, qid, f"amend — {LINE}")  # the rerun posts a new ruling comment
  assert code == 0, out
  assert sorted(p.name for p in (hdir / "amendments").iterdir()) == ["11.json"]
  assert (hdir / "amendments" / "11.json").read_bytes() == first_bytes
  assert len(launch_builder.amendments_for(s, "U01", body)) == 1


@pytest.mark.parametrize("second, texts", [
  ("amend — enqueue() -> Job | null", ["enqueue() -> Job | null"]),
  ("(b) return null", ["return null"]),
  ("stop the unit", []),
])
def test_rerun_after_crash_with_another_ruling(world, monkeypatch, second, texts):
  # a crash left the first ruling's file; the rerun's ruling is the one saved, and no amendment outlives it
  import superegm
  from superegm import launch_builder
  card, s = world_on(world)
  body = "## Interfaces\n- Produces: dequeue() -> Job | null\n"
  qid = opened(world, card, IFACE + OPTS, source="comment 11")
  real = superegm.save_foreman

  def crash(*args, **kwargs):
    monkeypatch.setattr(superegm, "save_foreman", real)
    raise OSError("disk full")
  monkeypatch.setattr(superegm, "save_foreman", crash)
  with pytest.raises(OSError):
    rule(world, card, qid, f"amend — {LINE}")
  code, out = rule(world, card, qid, second)
  assert code == 0, out
  saved = foreman_of(s, "U02")["rulings"]
  assert [r["ruling"] for r in saved] == [second]
  got = launch_builder.amendments_for(s, "U01", body)
  assert [a["text"] for a in got] == texts
  assert [f"comment {a['comment_id']}" for a in got] == [saved[0]["posted"]] * len(got)  # the saved ruling's own comment


def test_reads_directory_and_legacy(world):
  # a pre.1 handoff: comment 7 in state.json amendments[], comment 11 in the directory, comment 7 in both
  from superegm import launch_builder
  import test_builders as tb
  from test_pre1_launch import amend, with_amendments
  s, card, hid, _ = tb.seed(world)
  body = "## Interfaces\n- Produces: dequeue() -> Job | null\n"
  seven, eleven = amend("U01", "dequeue", "2026-11-01T00:00:00Z", 7), amend("U01", "dequeue", "2026-11-02T00:00:00Z", 11)
  with_amendments(s, [seven])
  folder = s.path("file", "amendments")
  folder.mkdir(parents=True)
  (folder / "11.json").write_text(json.dumps([eleven]), encoding="utf-8")
  (folder / "7.json").write_text(json.dumps([seven]), encoding="utf-8")
  got = launch_builder.amendments_for(s, "U01", body)
  assert [a["comment_id"] for a in got] == [7, 11]
  assert [a["at"] for a in got] == sorted(a["at"] for a in got)


@pytest.mark.parametrize("case, message", [
  ("ruling with no line", "decision: amend needs — <the Interfaces line as it now reads>"),
  ("comment with two deviation headings", "decision: amend needs a comment with one interface deviation and no other"),
  ("name not in U01's Interfaces", "decision: amend names U01 nope, not in U01's Interfaces lines"),
  ("ruled by the judges", "decision: amend is the owner's alone"),
])
def test_amend_refusals(world, case, message):
  # each refusal leaves no amendment file and no ruling
  from test_pre1_amend import DOD
  card, s = world_on(world)
  texts = {"comment with two deviation headings": IFACE + DOD, "name not in U01's Interfaces": "**Deviation (interface):** U01 nope: missing\n"}
  qid = opened(world, card, texts.get(case, IFACE) + OPTS)
  ruling = "amend" if case == "ruling with no line" else f"amend — {LINE}"
  code, err = rule(world, card, qid, ruling, "judges:p-1" if case == "ruled by the judges" else "owner")
  assert err.strip() == message and code == 1
  hdir = s.path("file")
  assert not (hdir / "amendments").exists() or not any((hdir / "amendments").iterdir())
  assert not foreman_of(s, "U02")["rulings"]


def test_amend_names_the_interface_without_its_signature(world):
  # a heading naming `dequeue():` is the Interfaces name `dequeue`, as Consumes lines and amendments read it
  card, s = world_on(world)
  qid = opened(world, card, "**Deviation (interface):** U01 dequeue(): returns null\n" + OPTS, source="comment 11")
  code, out = rule(world, card, qid, f"amend — {LINE}")
  assert code == 0, out
  assert [a["name"] for a in json.loads((s.path("file") / "amendments" / "11.json").read_text())] == ["dequeue"]


def test_the_judges_cannot_amend_by_option_letter(world):
  # the builder's own option line `(a) amend` is no way round the owner's alone: no file, no ruling
  card, s = world_on(world)
  qid = opened(world, card, IFACE + "**Builder status:** BLOCKED\nWhich?\n- (a) amend\n- (b) return null\n")
  for ruling in ("(a) — " + LINE, "(a) amend", "amend"):
    code, err = rule(world, card, qid, ruling, "judges:p-1")
    assert code == 1 and "amend" in err, (ruling, err)
  assert not (s.path("file") / "amendments").exists()
  assert not foreman_of(s, "U02")["rulings"]


def test_the_judges_blocked_question_reaches_the_producers_other_consumers(world):
  # U02 posts a deviation naming U01's contract: the question goes to U01's other filed consumer (U03), not U02's
  # (none), and the builder's own `(a) amend` line never reaches the judges
  card, s = world_on(world, {f"repos/{REPO}/issues/comments/11": {
    "id": 11, "user": {"login": "builder-bot"},
    "body": IFACE + "**Builder status:** BLOCKED\nWhich?\n- (a) amend\n- (b) return null\n"}})
  opened(world, card, IFACE + OPTS, source="comment 11")
  code, out = world.run("judges", "question", "--unit", "U02", "--blocked", "11", "--runcard", card)
  assert code == 0, out
  first, consumers = out.splitlines()[:2]
  assert "amend" not in Path(first).read_text(encoding="utf-8")
  units = json.loads(s.path("state").read_text(encoding="utf-8"))["units"]
  assert consumers == f"consumers: #{units['U03']['number']}"


def test_the_judges_blocked_question_reads_every_interface_heading_of_the_comment(world):
  # an option ruling settles every heading of a comment, so a dod heading first hides no interface heading's consumers
  from test_pre1_amend import DOD
  card, s = world_on(world, {f"repos/{REPO}/issues/comments/11": {
    "id": 11, "user": {"login": "builder-bot"}, "body": DOD + IFACE + OPTS}})
  opened(world, card, DOD + IFACE + OPTS, source="comment 11")
  code, out = world.run("judges", "question", "--unit", "U02", "--blocked", "11", "--runcard", card)
  assert code == 0, out
  units = json.loads(s.path("state").read_text(encoding="utf-8"))["units"]
  assert out.splitlines()[1] == f"consumers: #{units['U03']['number']}"


def test_judges_never_amend(world):
  # judges get no amend option; the interface question reaches filed consumers; their option ruling on an interface
  # decision records the option's text, and their `amend` records nothing
  from superegm import judges
  card, s = world_on(world)
  cap = opened(world, card, IFACE + OPTS, "review head-U02-c1 cap", 2)
  code, out = rule(world, card, cap, "one more round", "judges:p-1")
  assert code == 0, out
  assert foreman_of(s, "U02")["rulings"][-1]["ruling"] == "one more round"
  assert not (s.path("file") / "amendments").exists()  # a point-2 ruling is no contract change
  did = opened(world, card, IFACE + OPTS)
  decision = foreman_of(s, "U02")["decisions"][-1]
  assert "amend" in decision["options"]
  assert "- amend\n" not in judges.decision_question(s, "U02", did)
  units = json.loads(s.path("state").read_text(encoding="utf-8"))["units"]
  assert judges.fan_out(s, "U01") == sorted(units[u]["number"] for u in ("U02", "U03"))  # every filed consumer of U01's names
  # the panel's option ruling on that interface decision is the chosen option's text (§6.5); its `amend` is refused
  assert rule(world, card, did, f"amend — {LINE}", "judges:p-1") == (1, "decision: amend is the owner's alone\n")
  assert not (s.path("file") / "amendments").exists()
  code, out = rule(world, card, did, "(b) return null", "judges:p-1")
  assert code == 0, out
  [entry] = json.loads((s.path("file") / "amendments" / "77.json").read_text())
  assert (entry["unit"], entry["name"], entry["text"]) == ("U01", "dequeue", "return null")


def test_the_judges_decision_question_drops_a_builders_amend_line(world):
  # a builder's `- (a) amend` option is the owner's alone, whatever its letter
  from superegm import judges
  card, s = world_on(world)
  did = opened(world, card, IFACE + "**Builder status:** BLOCKED\nWhich?\n- (a) amend\n- (b) return null\n")
  [q] = judges.parse_questions(judges.decision_question(s, "U02", did))  # the panel's own parser takes it whole
  assert q["options"] == {"a": "return null", "b": "stop the unit"}


def test_a_by_hand_amend_not_offered_is_refused_as_amends_own(world):
  # a by-hand `amend — <line>` on a comment with a dod heading: the comment carries the line, so the refusal is the
  # one-interface-deviation one, not the missing line
  from test_pre1_amend import DOD
  routes = {f"repos/{REPO}/issues/comments/88": {"id": 88, "user": {"login": "owner"}, "body": f"**Ruling:** (77) amend — {LINE}\n"}}
  card, s = world_on(world, routes)
  qid = opened(world, card, IFACE + DOD + OPTS)
  code, err = rule(world, card, qid, "amend", "owner", "--posted", "88")
  assert code == 1 and err.strip() == "decision: amend needs a comment with one interface deviation and no other"
  assert not foreman_of(s, "U02")["rulings"]
  assert not (s.path("file") / "amendments").exists()


def test_an_interface_option_that_keeps_the_contract_records_no_amendment(world):
  # an interface comment's own `one more round` option leaves the contract as it was (spec §6.5): no amendment file
  card, s = world_on(world)
  qid = opened(world, card, IFACE + "**Builder status:** BLOCKED\nWhich?\n- (a) one more round\n- (b) return null\n")
  code, out = rule(world, card, qid, "(a) one more round — try again")
  assert code == 0, out
  assert not (s.path("file") / "amendments").exists() or not any((s.path("file") / "amendments").iterdir())


def test_amend_names_only_a_declared_contract(world):
  # `Job` and `undefined` occur in U01's `dequeue() -> Job | undefined` line, but are no name U01 produces
  card, s = world_on(world)
  qid = opened(world, card, "**Deviation (interface):** U01 Job: a different shape\n" + OPTS, source="comment 11")
  code, err = rule(world, card, qid, "amend — Job = {id}")
  assert (code, err.strip()) == (1, "decision: amend names U01 Job, not in U01's Interfaces lines")
  assert not (s.path("file") / "amendments").exists()
  assert not foreman_of(s, "U02")["rulings"]
