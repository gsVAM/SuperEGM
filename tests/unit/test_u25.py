# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U25, the foreman verifies: the DoD re-run and the test delta (spec §11.1).

"""U25: the `foreman` config key, `kill_group`, `dod_runs`, `test_delta`, the forced removal and the hook-free checkouts."""

import re

import pytest

import superegm
from conftest import REPO, set_config
from superegm import init


@pytest.mark.parametrize("given, expect", [(None, 8), ({"run_timeout_minutes": 0.02}, 0.02), ({"run_timeout_minutes": 10}, None)])
def test_foreman_config_key_and_the_init_sentence(world, given, expect):
  assert superegm.DEFAULT_CONFIG["foreman"] == {"run_timeout_minutes": 8} and "foreman.run_timeout_minutes" in init.STEPS
  set_config(world, repo=REPO, **({"foreman": given} if given else {}))
  if expect is None:
    with pytest.raises(superegm.HandoffError, match=re.escape("foreman.run_timeout_minutes must be a number above 0 and at most 9")):
      superegm.load_config(world.repo)
  else:
    assert superegm.load_config(world.repo)["foreman"] == {"run_timeout_minutes": expect}
