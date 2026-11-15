# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U47, one ruling renderer (spec §8).

"""U47: `decision.ruling_line` renders every `**Ruling:**` line; the three renderers go through it."""

import pytest

from superegm import decision


@pytest.mark.parametrize("reason,expected", [(None, "**Ruling:** x"), ("", "**Ruling:** x"), ("why", "**Ruling:** x — why")])
def test_ruling_line(reason, expected):
  # the one renderer: the prefix, the text, and ` — <reason>` only for a non-empty reason
  assert decision.ruling_line("x", reason) == expected
