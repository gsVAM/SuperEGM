# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U33

"""U33 (spec sections 9.1, 7, 11): `builder.tiers`, the loader's refusals, `tier_pair`, `unit_tier` and the
board's tier column."""

import json
import re

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, set_config
from superegm import atomic_write
from test_wave import open_wave_card, wave_store


def tier_pair(config, tier):
  return superegm.tier_pair(config, tier)


def unit_tier(store, uid):
  return superegm.unit_tier(store, uid)


TIERS = {"difficult": {"model": "claude-opus-5-5", "effort": "high"}, "easy": {"model": "claude-sonnet-5-5", "effort": "medium"}}


@pytest.mark.parametrize("builder, tier, expect", [
  ({}, "difficult", ("claude-opus-5-5", "high")),
  ({}, "easy", ("claude-sonnet-5-5", "medium")),
  ({}, "doable", None),
  ({"tiers": {"difficult": TIERS["difficult"]}}, "easy", None),
  ({"tiers": {"hard": TIERS["difficult"]}}, "doable", "builder.tiers keys must be difficult or easy"),
  ({"tiers": {"easy": {"model": "claude-sonnet-5-5"}}}, "doable", "builder.tiers.easy must be {model, effort}"),
  ({"tiers": {"easy": {"model": "claude-sonnet-5-5", "effort": "huge"}}}, "doable", "builder.tiers.easy must be {model, effort}"),
  ({"tiers": {"easy": {"model": "Claude Sonnet", "effort": "medium"}}}, "doable", "builder.tiers.easy must be {model, effort}"),
  ({"tiers": ["easy"]}, "doable", "builder.tiers keys must be difficult or easy")])
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


@pytest.mark.parametrize("tier, cell", [(None, "doable"), ("difficult", "difficult"), ("hard", "doable"), ("", "doable")])
def test_the_board_carries_the_tier_column(world, tier, cell):
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  units = json.loads(s.path("units").read_text(encoding="utf-8"))
  units["units"]["U01"].pop("tier", None)
  tier is not None and units["units"]["U01"].update(tier=tier)
  atomic_write(s.path("units"), units)
  assert unit_tier(s, "U01") == cell
  code, out = world.run("report", "--runcard", card)
  assert code == 0, out
  for text in (s.path("wave_report", 1).read_text(encoding="utf-8"), out):
    row = next(l for l in text.splitlines() if l.lstrip("|- ").startswith("U01"))
    assert row.rstrip(" |").endswith(cell), row
