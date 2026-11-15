# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U47, one ruling renderer (spec §8).

"""U47: `decision.ruling_line` renders every `**Ruling:**` line; the three renderers go through it."""

import pytest

from superegm import decision


@pytest.mark.parametrize("reason,expected", [(None, "**Ruling:** x"), ("", "**Ruling:** x"), ("why", "**Ruling:** x — why")])
def test_ruling_line(reason, expected):
  # the one renderer: the prefix, the text, and ` — <reason>` only for a non-empty reason
  assert decision.ruling_line("x", reason) == expected


@pytest.mark.parametrize("render,expected", [
  (lambda: decision.ruling_form(2, "one more round"), "**Ruling:** one more round"),
  (lambda: decision.ruling_form(1, "f-1", "finding upheld"), "**Ruling:** f-1 finding upheld"),
  (lambda: decision.ruling_form(3, "c9", "take b"), "**Ruling:** (c9) take b — <reason>"),
  (lambda: decision.ruling_form(1, "redesign"), "**Ruling:** redesign — <reason>"),
  (lambda: decision.record_text({"decisions": [{"id": "D1", "point": 1}]},
                                {"decision": "D1", "ruling": "f-1 finding upheld", "reason": "", "by": "owner"}),
   "**Ruling:** f-1 finding upheld\n(as recorded by owner; the comment was edited after its record)"),
  (lambda: decision.ruling_comment(2, "comment 9", "stop", "Q?"), "**Ruling:** stop\n\n> Q?\n"),
  (lambda: decision.ruling_comment(1, "comment 9", "f-1 finding upheld", "Q?", by="judges:p1"),
   "**Ruling:** f-1 finding upheld (fix it)\n(judges p1, leavemealone)\n\n> Q?\n"),
  (lambda: decision.ruling_comment(2, "comment 9", "redesign — why", "Q?", brief="b.md"),
   "**Ruling:** redesign — why\n\nStopped for redesign; the brainstorm brief is `b.md`.\n"
   "Close this issue by hand once the re-planned unit is filed.\n\n> Q?\n")])
def test_one_ruling_renderer(render, expected, monkeypatch):
  # 1.2's bytes kept; with ruling_line stubbed every one of the three carries the stub, so all go through it
  assert render() == expected
  monkeypatch.setattr(decision, "ruling_line", lambda text, reason=None: "STUB")
  assert render().startswith("STUB")
