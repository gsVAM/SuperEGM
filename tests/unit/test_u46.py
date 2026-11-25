# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U46's tests: the registry-driven config merge.
# Modified by SuperEGM (gsVAM), 2026: the 60-minute `stall_minutes` default pin (U100, 1.3 design section 3.3)

"""U46: `load_config` merges every registered object default one level and takes the builder defaults from the registry."""

import types

import pytest

import superegm
from conftest import ROOT, set_config


@pytest.mark.parametrize("file,key,expected", [
  ({"builder": {"tiers": {"easy": {"model": "m1", "effort": "low"}}}}, "builder",
   {"tiers": {"easy": {"model": "m1", "effort": "low"}}, "model": "claude-opus-5-5"}),
  ({"ingest": {"severity_words": {"blocker": "high"}}}, "ingest", {"severity_words": {"blocker": "high"}}),
  ({"judges": {"min_vendors": 2}}, "judges", {"min_vendors": 2}),
  ({"probe": {"b": 2}}, "probe", {"a": 1, "b": 2})])
def test_registered_object_keys_merge_one_level(world, monkeypatch, file, key, expected):
  # probe is a module registering {"probe": {"a": 1}} outside 1.2's set; each expected item holds, siblings from the default
  probe = types.SimpleNamespace(CONFIG_DEFAULTS={"probe": {"a": 1}})
  monkeypatch.setitem(superegm._MODULES, "probe", probe)
  monkeypatch.setitem(superegm.DEFAULT_CONFIG, "probe", {"a": 1})
  set_config(world, **file)
  config = superegm.load_config(world.repo)
  assert all(config[key][k] == v for k, v in expected.items())
  assert set(config[key]) >= set(superegm.DEFAULT_CONFIG[key])


@pytest.mark.parametrize("app,ok", [({"app_id": 7, "slug": "b"}, True), ({"app_id": 7, "slug": "b", "x": 1}, False)])
def test_builder_defaults_from_the_registry(world, app, ok):
  # the redundant builder setdefaults go: an old file reads launch_builder.CONFIG_DEFAULTS; the app default and check stay
  set_config(world, builder={"profile_dir": "~/p", "app": app})
  if ok:
    config = superegm.load_config(world.repo)
    assert config["builder"]["app"]["private_key_env"] == "SUPEREGM_APP_KEY"
    assert {k: config["builder"][k] for k in ("plugins", "mcp", "max_subagent_calls", "stall_minutes")} == \
        {"plugins": [], "mcp": {}, "max_subagent_calls": 12, "stall_minutes": 60}
  else:
    with pytest.raises(superegm.HandoffError, match="builder.app"):
      superegm.load_config(world.repo)
  assert 'setdefault("stall_minutes"' not in (ROOT / "skills/plan/scripts/superegm/__init__.py").read_text(encoding="utf-8")
