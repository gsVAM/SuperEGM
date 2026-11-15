# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U96's tests, spec §6.5 "amend": the one reader of an interface name, the amendment files, the judges' options and the interface fan-out.

"""U96: `scan.names_of` is the one reader of an interface name; `amend` writes `amendments/<deviation comment id>.json`
before the ruling is saved; `amendments_for` reads ruled files and a 1.2.1-pre.1 handoff's legacy `amendments[]`;
the judges never see `amend`; an interface question fans out to the named producer's filed consumers."""

import json
from pathlib import Path

import pytest

from superegm import decision, judges, launch_builder, scan
import superegm as core
from test_pre1_amend import OPTS, opened, rule, world_on
from test_wave import REPO, foreman_of

LINE = "the interface as it now reads"


def deviation(heading):
  return f"**Deviation (interface):** {heading}\n" + OPTS


def produces_file(s, unit, *lines):
  s.path("unit", unit).write_text("## Interfaces\n" + "".join(f"- Produces: {l}\n" for l in lines), encoding="utf-8")


def consumer_body(*lines):
  return "## Interfaces\n" + "".join(f"- Consumes: {l}\n" for l in lines)


def recorded_amendments(s, cid):
  """What `decision rule` recorded for the deviation comment `cid`: its file, else (before the file) `state.json`."""
  path = s.base() / "amendments" / f"{cid}.json"
  if path.is_file():
    return json.loads(path.read_text(encoding="utf-8"))
  return json.loads(s.path("state").read_text(encoding="utf-8")).get("amendments") or []


@pytest.mark.parametrize("produces, heading, consumes", [
  ("`load(path) -> dict`", "U01 load:", "`load` (U01)"),
  ("`core.store.path(kind)`", "U01 core.store.path:", "`core.store.path` (U01)"),
  ("`superegm review open --kind spec`", "U01 superegm review open:", "`superegm review open` (U01)"),
  ("`state.json` key `units.<id>.number`", "U01 units.<id>.number:", "`state.json` key `units.<id>.number` (U01)"),
  ("`load(path) -> dict`", "U01 `load`:", "`load` (U01)"),
])
def test_name_forms(world, produces, heading, consumes):
  # amend accepts the name scan reads; the consumer's prompt gets the amendment
  card, s = world_on(world)
  produces_file(s, "U01", produces)
  qid = opened(world, card, deviation(f"{heading} changed"))
  code, out = rule(world, card, qid, f"amend — {LINE}")
  amendments = recorded_amendments(s, 77)
  assert code == 0, out
  assert [a["name"] for a in amendments] == scan.names_of(produces.strip("`"))[:1]
  assert [a["name"] for a in launch_builder.amendments_for(s, "U02", consumer_body(consumes))] == [a["name"] for a in amendments]
  assert scan.names_of("`f.read()`") == ["f.read"]


def test_amendment_file_before_ruling(world, monkeypatch):
  # the amendment is its own file, written before the ruling is saved
  line = "f(x) -> int | None"
  routes = {f"repos/{REPO}/issues/comments/21": {"id": 21, "user": {"login": "owner"}, "body": f"**Ruling:** (11) amend — {line}\n"}}
  card, s = world_on(world, routes)
  produces_file(s, "U01", "`f(x) -> int`")
  qid = opened(world, card, deviation("U01 f: returns None"), source="comment 11")
  write_order, real = [], core.atomic_write

  def spy(path, obj):
    write_order.append(path)
    return real(path, obj)

  monkeypatch.setattr(core, "atomic_write", spy)
  assert rule(world, card, qid, "amend", "owner", "--posted", "21") == (0, "recorded (comment 21)\n")
  hdir = s.base()
  entries = json.loads((hdir / "amendments" / "11.json").read_text(encoding="utf-8"))
  assert [(e["unit"], e["name"], e["text"], e["comment_id"]) for e in entries] == [("U01", "f", line, 21)]
  assert {"at", "recorded_at"} <= set(entries[0])
  assert write_order.index(hdir / "amendments" / "11.json") < write_order.index(s.path("foreman", "U02"))
  assert "recorded_at" not in json.dumps(foreman_of(s, "U02")["rulings"])
  assert decision.WRITES == frozenset({"foreman", "reviews", "state", "file"})


def test_rerun_after_crash(world, monkeypatch):
  # a file whose ruling was never saved is not read; the rerun rewrites or deletes it
  card, s = world_on(world)
  produces_file(s, "U01", "`f(x) -> int`")
  body = consumer_body("`f` (U01)")
  hdir, real = s.base(), core.save_foreman

  # a `one more round` ruling on a handoff with no amendment records none: the directory is never made
  round_qid = opened(world, card, deviation("U01 f: returns None"), source="review head-U02-c1 cap", point=2)
  assert rule(world, card, round_qid, "one more round")[0] == 0
  assert not (hdir / "amendments").exists()

  def crash(*args, **kwargs):
    raise core.HandoffError("crash before the ruling is saved")

  qid = opened(world, card, deviation("U01 f: returns None"), source="comment 11")
  monkeypatch.setattr(core, "save_foreman", crash)
  assert rule(world, card, qid, "amend — first line")[0] == 1
  path = hdir / "amendments" / "11.json"
  assert json.loads(path.read_text(encoding="utf-8"))[0]["text"] == "first line"
  assert launch_builder.amendments_for(s, "U01", body) == []
  monkeypatch.setattr(core, "save_foreman", real)
  rerun_line = "f(x) -> int | None"
  assert rule(world, card, qid, f"amend — {rerun_line}")[0] == 0
  assert json.loads(path.read_text(encoding="utf-8"))[0]["text"] == rerun_line
  assert [a["text"] for a in launch_builder.amendments_for(s, "U01", body)] == [rerun_line]

  # a rerun that rules `stop the unit` deletes the file the crashed run wrote
  qid = opened(world, card, deviation("U01 f: returns None"), source="comment 12")
  monkeypatch.setattr(core, "save_foreman", crash)
  assert rule(world, card, qid, "amend — second line")[0] == 1
  deleted_path = hdir / "amendments" / "12.json"
  assert deleted_path.exists()
  monkeypatch.setattr(core, "save_foreman", real)
  assert rule(world, card, qid, "stop the unit")[0] == 0
  assert not deleted_path.exists()


def test_close_after_crash(world, monkeypatch):
  # a crashed amend, then the decision ruled by the owner's close: the saved ruling records no amendment, so the file goes
  card, s = world_on(world)
  produces_file(s, "U01", "`f(x) -> int`")
  qid = opened(world, card, deviation("U01 f: returns None"), source="comment 11")
  real = core.save_foreman

  def crash(*args, **kwargs):
    raise core.HandoffError("crash before the ruling is saved")

  monkeypatch.setattr(core, "save_foreman", crash)
  assert rule(world, card, qid, "amend — crashed line")[0] == 1
  path = s.base() / "amendments" / "11.json"
  assert path.exists()
  monkeypatch.setattr(core, "save_foreman", real)
  assert rule(world, card, qid, "stop the unit", "owner", "--posted", "closed:5")[0] == 0
  assert not path.exists()
  assert launch_builder.amendments_for(s, "U01", consumer_body("`f` (U01)")) == []


@pytest.mark.parametrize("case, message", [
  ("empty line", "decision: amend needs — <the Interfaces line as it now reads>"),
  ("two headings", "decision: ruling is none of the options: "),  # amend is offered only on one interface heading
  ("dod heading", "decision: ruling is none of the options: "),
  ("interface heading with no `<Uxx> <name>:`", "decision: amend needs a comment with one interface deviation and no other"),
  ("name not read", "decision: amend names U01 nope, not in U01's Interfaces lines"),
  ("judges answer (c), stored amend", "decision: amend is the owner's alone"),
])
def test_amend_refusals(world, case, message):
  # each refusal leaves no amendment file and no ruling
  card, s = world_on(world)
  produces_file(s, "U01", "`f(x) -> int`")
  text, ruling, by = {
    "empty line": (deviation("U01 f: changed"), "amend", "owner"),
    "two headings": (deviation("U01 f: changed") + deviation("U01 g: changed"), f"amend — {LINE}", "owner"),
    "dod heading": ("**Deviation (dod):** U01 f: changed\n" + OPTS, f"amend — {LINE}", "owner"),
    "interface heading with no `<Uxx> <name>:`": (deviation("f changed"), f"amend — {LINE}", "owner"),
    "name not read": (deviation("U01 nope: changed"), f"amend — {LINE}", "owner"),
    "judges answer (c), stored amend": (deviation("U01 f: changed"), "(c)", "judges:p-1"),
  }[case]
  qid = opened(world, card, text, source="comment 11")
  code, err = rule(world, card, qid, ruling, by)
  assert err.strip().startswith(message) and code == 1
  assert not (s.base() / "amendments").exists() or not any((s.base() / "amendments").iterdir())
  assert not foreman_of(s, "U02")["rulings"]


def test_a_bare_letter_resolves_to_the_option_at_its_position(world):
  # the judges' `(d)` on stored `keep undefined`, `return null`, `amend`, `stop the unit` rules `stop the unit`;
  # a bare `(a)` on a launch decision rules `relaunch`
  card, s = world_on(world)
  qid = opened(world, card, deviation("U01 f: changed"), source="comment 11")
  code, out = rule(world, card, qid, "(d)", "judges:p-1")
  assert code == 0, out
  assert foreman_of(s, "U02")["stopped"]["reason"] == "stop the unit"
  assert world.gh.comments[3][-1]["body"].startswith("**Ruling:** (11) stop the unit")
  assert not (s.base() / "amendments").exists()
  launch_qid = opened(world, card, "launch 1 stalled (last commit none)\n", source="launch 1")
  code, out = rule(world, card, launch_qid, "(a)", "judges:p-1")
  assert code == 0, out
  assert world.gh.comments[3][-1]["body"].startswith(f"**Ruling:** ({launch_qid}) relaunch")


def test_judges_never_amend(world):
  # stored: keep undefined, return null, amend, stop the unit; amend left out, letters kept
  text = deviation("U01 f: changed")
  routes = {f"repos/{REPO}/issues/comments/11": {"id": 11, "user": {"login": "builder-bot"}, "body": text}}
  card, s = world_on(world, routes)
  opened(world, card, text, source="comment 11")
  stored_options = foreman_of(s, "U02")["decisions"][-1]["options"]
  assert stored_options == ["(a) keep undefined", "(b) return null", "amend", "stop the unit"]
  code, out = world.run("judges", "question", "--unit", "U02", "--blocked", "11", "--runcard", card)
  assert code == 0, out
  blocked_text = Path(out.splitlines()[0]).read_text(encoding="utf-8")
  assert "amend" not in blocked_text and blocked_text.endswith("- (a) keep undefined\n- (b) return null\n- (d) stop the unit\n")
  plan_time = {"id": "D1", "question": "Which?", "options": stored_options}
  s.path("units").write_text(json.dumps({"units": {"U01": {"decisions": [plan_time]}}}), encoding="utf-8")
  assert judges.decision_question(s, "U01", "D1").splitlines()[1:] == ["- " + o for o in stored_options]
  with pytest.raises(core.HandoffError, match="--blocked"):
    judges.decision_question(s, "U01", "q1")


def test_fan_out_named_producer(world):
  # U03 consumes U01 and raises `U01 f:`; U02 and U04 also consume U01
  text = deviation("U01 f: changed")
  routes = {f"repos/{REPO}/issues/comments/11": {"id": 11, "user": {"login": "builder-bot"}, "body": text},
            f"repos/{REPO}/issues/comments/12": {"id": 12, "user": {"login": "builder-bot"}, "body": deviation("`g` changed")}}
  card, s = world_on(world, routes)
  state = core.load_state(s.root)
  state["units"] = {f"U0{n}": {"number": 100 + n} for n in range(1, 6)}
  core.save_state(s.root, state)
  for unit, consumes in (("U02", "`f` (U01)"), ("U03", "`f` (U01)"), ("U04", "`f` (U01)"), ("U05", "`g` (U03)")):
    s.path("unit", unit).write_text(consumer_body(consumes), encoding="utf-8")
  assert judges.fan_out(s, "U01", "U03") == [102, 104]
  old_form_consumers = judges.fan_out(s, "U03", "U03")
  assert old_form_consumers == [105]  # a heading with no `<Uxx> <name>:`
  # `blocked_question` passes the heading's producer, else the raising unit
  assert judges.blocked_question(s, "U03", ["11"])[1] == [102, 104]
  assert judges.blocked_question(s, "U03", ["12"])[1] == old_form_consumers


def test_reads_directory_and_legacy(world):
  # a 1.2.1-pre.1 handoff's amendments[] and a directory file are both read, sorted by `at`
  card, s = world_on(world)
  produces_file(s, "U03", "`f(x) -> int`")
  state = core.load_state(s.root)
  state["amendments"] = [{"unit": "U01", "name": "g", "text": "g() -> int", "comment_id": 5, "at": "2020-01-01T00:00:00Z"}]
  core.save_state(s.root, state)
  qid = opened(world, card, deviation("U03 f: returns None"), source="comment 11")
  assert rule(world, card, qid, "amend — f(x) -> int | None")[0] == 0
  body = consumer_body("`g` (U01)")
  assert [(a["unit"], a["name"]) for a in launch_builder.amendments_for(s, "U03", body)] == [("U01", "g"), ("U03", "f")]
