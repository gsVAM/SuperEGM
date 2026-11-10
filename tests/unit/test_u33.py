# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U33

"""U33 (spec sections 9.1, 7, 11): `builder.tiers`, the loader's refusals, `tier_pair`, `unit_tier` and the
board's tier column."""

import re

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, set_config


def tier_pair(config, tier):
  return superegm.tier_pair(config, tier)


TIERS = {"difficult": {"model": "claude-opus-5-5", "effort": "high"}, "easy": {"model": "claude-sonnet-5-5", "effort": "medium"}}


@pytest.mark.parametrize("builder, tier, expect", [
  ({}, "difficult", ("claude-opus-5-5", "high")),
  ({}, "easy", ("claude-sonnet-5-5", "medium")),
  ({}, "doable", None),
  ({"tiers": {"difficult": TIERS["difficult"]}}, "easy", None),
  ({"tiers": {"hard": TIERS["difficult"]}}, "doable", "builder.tiers keys must be difficult or easy"),
  ({"tiers": {"easy": {"model": "claude-sonnet-5-5"}}}, "doable", "builder.tiers.easy must be {model, effort}"),
  ({"tiers": {"easy": {"model": "claude-sonnet-5-5", "effort": "huge"}}}, "doable", "builder.tiers.easy must be {model, effort}")])
def test_builder_tiers_defaults_the_loader_and_the_pair(world, builder, tier, expect):
  assert superegm.DEFAULT_CONFIG["builder"]["tiers"] == TIERS
  set_config(world, repo=REPO, builder={"profile_dir": "p", **builder})
  if isinstance(expect, str):
    with pytest.raises(superegm.HandoffError, match=re.escape(expect)):
      superegm.load_config(world.repo)
    return
  config = superegm.load_config(world.repo)
  assert config["builder"]["tiers"] == (builder.get("tiers") or TIERS)
  assert tier_pair(config, tier) == (expect or (config["builder"]["model"], config["builder"]["effort"]))
