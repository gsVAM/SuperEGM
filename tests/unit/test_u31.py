# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U31

"""U31 (spec section 11.1): the watchdog's key `builder.stall_minutes` and the `kill_failed` lines."""

import re

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, set_config


@pytest.mark.parametrize("value, loaded", [(30, 30), (45, 45), ("absent", 30), (0, None), ("30", None), (True, None)])
def test_stall_minutes_is_30_and_a_positive_integer(world, value, loaded):
  assert superegm.DEFAULT_CONFIG["builder"]["stall_minutes"] == 30
  builder = {**superegm.DEFAULT_CONFIG["builder"], "stall_minutes": value}
  value == "absent" and builder.pop("stall_minutes")
  set_config(world, repo=REPO, builder=builder)
  if loaded:
    assert superegm.load_config(world.repo)["builder"]["stall_minutes"] == loaded
    return
  with pytest.raises(superegm.HandoffError, match=re.escape("builder.stall_minutes must be a positive integer")):
    superegm.load_config(world.repo)
