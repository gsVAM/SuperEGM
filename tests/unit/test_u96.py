# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U96's tests, spec §6.5 "amend": the one reader of an interface name, the amendment files, the judges' options and the interface fan-out.

"""U96: `scan.names_of` is the one reader of an interface name; `amend` writes `amendments/<deviation comment id>.json`
before the ruling is saved; `amendments_for` reads ruled files and a 1.2.1-pre.1 handoff's legacy `amendments[]`;
the judges never see `amend`; an interface question fans out to the named producer's filed consumers."""

import json

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
