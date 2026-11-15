# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U42's pins of spec section 6 (the units limits: registered, validated, refused over, the bytes warning gone).

"""U42: `scan` registers and validates the `units` limits, refuses an unfiled unit over one of them,
drops the 24,576-byte warning, and the plan documents state the limits."""

import pytest
import superegm as core

from conftest import REPO, set_config
from test_plan import graph, planned


def scan_with(world, **units):
  """Plan and graph the sample units, then scan them with `units.*` set in the repository's config."""
  spec, sha, plan, card = planned(world)
  assert graph(world, plan, card)[0] == 0
  set_config(world, repo=REPO, units={**core.DEFAULT_CONFIG["units"], **units})
  return world.run("scan", "--plan", plan)


@pytest.mark.parametrize("key,value,ok", [("max_body_kb", 48, True), ("max_body_kb", 49, False), ("max_body_kb", 0, False),
                                          ("max_files", 8, True), ("max_files", 7, False), ("max_steps", 1, True),
                                          ("max_steps", 0, False), ("max_steps", "16", False)])
def test_units_limits_validated(world, key, value, ok):
  # each units.* value is a positive int, max_body_kb <= 48, max_files >= 8; read live at each scan
  assert core.DEFAULT_CONFIG["units"] == {"max_body_kb": 25, "max_files": 10, "max_steps": 16}
  code, out = scan_with(world, **{key: value})
  assert (f"units.{key}" not in out) if ok else (code == 1 and f"units.{key}" in out), out
