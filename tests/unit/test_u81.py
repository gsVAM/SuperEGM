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
