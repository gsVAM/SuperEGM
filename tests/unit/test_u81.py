# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U81

"""U81: spec §6.5 conformance of `amend`: the amendment is its own file `amendments/<comment id>.json`, written before the
ruling is saved; `launch_builder.amendments_for` reads the directory and a pre.1 handoff's `amendments[]`; amend's
refusals; the judges never amend."""

import json
import re
from pathlib import Path

import pytest

from test_pre1_amend import IFACE, LINE, OPTS, opened, rule, world_on
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
