# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U59

"""U59 (spec section 3.3): `superegm builder-setup` creates the builder profile with its two settings, copies the
owner's named MCP servers into `builder.mcp` with their `mcp__<name>__*` rule and adds each `Bash(<prefix>:*)` rule."""

import json

import pytest

from conftest import CONFIG, REPO, set_config


def setup(world, tmp_path, monkeypatch, builder=None):
  """The config's `builder.profile_dir` under `tmp_path`; `CLAUDE_CONFIG_DIR` and `HOME` under it too, so nothing reads the owner's."""
  profile = tmp_path / "profile"
  set_config(world, repo=REPO, builder={"profile_dir": str(profile), **(builder or {})})
  monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
  monkeypatch.setenv("HOME", str(tmp_path / "home"))
  return profile


@pytest.mark.parametrize("settings, refused", [
  (None, None),                                    # profile dir absent: created
  ({"theme": "dark"}, None),                       # theme kept
  ({"hooks": {"SessionStart": []}}, "holds hooks"),
])
def test_builder_profile(world, tmp_path, monkeypatch, settings, refused):
  from superegm import builder_setup
  assert builder_setup.WRITES == frozenset()
  profile = setup(world, tmp_path, monkeypatch)
  if settings is not None:
    profile.mkdir()
    (profile / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    (profile / ".credentials.json").write_text('{"login": 1}', encoding="utf-8")
  config_before = (world.repo / CONFIG).read_bytes()
  before = (profile / "settings.json").read_bytes() if settings is not None else None
  code, out = world.run("builder-setup")
  assert (world.repo / CONFIG).read_bytes() == config_before
  if refused:
    assert code == 1 and f"superegm: builder profile {profile} {refused}" in out, out
    assert (profile / "settings.json").read_bytes() == before
    return
  assert code == 0, out
  assert json.loads((profile / "settings.json").read_text(encoding="utf-8")) == {
      **(settings or {}), "syncClaudeAiPlugins": False, "disableClaudeAiConnectors": True}
  if settings is not None:
    assert (profile / ".credentials.json").read_text(encoding="utf-8") == '{"login": 1}'
