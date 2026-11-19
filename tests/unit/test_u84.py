# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U84's tests, spec §7.6 "The deviation" and "The ruling": the `spec` deviation kind and the owner's `respec`.

"""U84: a `**Deviation (spec):**` comment blocks until ruled, its decision offers `respec` (the owner's alone,
never in the judges' question), `decision rule ... respec` writes `respec/R<n>.open.json` and never `state.json`,
and the builder orders and the foreman brief define the kind."""

import json

import pytest

from superegm.collect import DEVIATION_RE
from test_foreman import UNIT, c, prepared

SPEC_LINE = "**Deviation (spec):** docs/specs/x.md:12 says 3; `pytest -k t` fails"
SPEC_COMMENT = SPEC_LINE + "\n- (a) keep the spec\n- (b) follow the code\n**Builder status:** BLOCKED"


@pytest.mark.parametrize("ruled, blockers", [(False, 1), (True, 0)])
def test_spec_deviation_blocks_until_ruled(world, tmp_path, monkeypatch, ruled, blockers):
  # a `spec` deviation is a blocker as `interface`, `dod` and `test` are (collect.py:600-605)
  assert DEVIATION_RE.match(SPEC_LINE).group(1) == "spec"
  comments = [c(12, "builder-bot", SPEC_COMMENT)] + ([c(13, "owner", "**Ruling:** (12) (a) — the spec stands")] if ruled else [])
  w = prepared(world, tmp_path, monkeypatch, comments={2: comments})
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"collected: {blockers} foreman findings"), out
  lines = (w.dir / "r1/foreman.findings").read_text(encoding="utf-8").splitlines()
  assert lines == (["foreman-1-1 | high | issue #2 comment 12 | regression: no | deviation (spec) unruled"] if blockers else [])
