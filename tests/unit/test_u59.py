# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U59

"""U59 (spec section 3.3): `superegm builder-setup` creates the builder profile with its two settings, copies the
owner's named MCP servers into `builder.mcp` with their `mcp__<name>__*` rule and adds each `Bash(<prefix>:*)` rule."""

import json

import pytest

from conftest import CONFIG, REPO, ROOT, set_config


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


def owner_servers(folder, local, user, project, repo_root):
  """`<folder>/.claude.json` with `relay` in local scope (under `projects[repo_root]`) and user scope, `<repo>/.mcp.json` with it
  under the project's; a decoy local entry under another project is never read. Returns the entry a tag stands for."""
  entry = lambda tag: {"command": f"relay-{tag}", "args": ["serve"]}
  decoy = {"/elsewhere": {"mcpServers": {"relay": entry("decoy")}}}
  held = {"projects": {**decoy, str(repo_root): {"mcpServers": {"relay": entry(local)} if local else {}}},
          "mcpServers": {"relay": entry(user)} if user else {}}
  folder.mkdir(parents=True, exist_ok=True)
  (folder / ".claude.json").write_text(json.dumps(held), encoding="utf-8")
  if project:
    (repo_root / ".mcp.json").write_text(json.dumps({"mcpServers": {"relay": entry(project)}}), encoding="utf-8")
  return entry


@pytest.mark.parametrize("via_env", [True, False])
@pytest.mark.parametrize("local, user, project, copied", [
  ("L", "U", "P", "L"), (None, "U", "P", "U"), (None, None, "P", "P"), (None, None, None, None)])
def test_mcp_source_order(world, tmp_path, monkeypatch, local, user, project, copied, via_env):
  import superegm
  profile = setup(world, tmp_path, monkeypatch)
  if not via_env:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
  entry = owner_servers(tmp_path / "claude" if via_env else tmp_path / "home", local, user, project, world.repo)
  config_before = (world.repo / CONFIG).read_bytes()
  code, out = world.run("builder-setup", "--mcp", "relay")
  if copied is None:
    assert code == 1 and "relay" in out, out
    assert (world.repo / CONFIG).read_bytes() == config_before and not profile.exists()
    return
  assert code == 0, out
  builder = superegm.load_config(world.repo)["builder"]
  assert builder["mcp"] == {"relay": entry(copied)}
  assert "mcp__relay__*" in builder["allowed_tools"] and "Bash(pytest:*)" in builder["allowed_tools"]


@pytest.mark.parametrize("entry, key", [
  ({"command": "x", "env": {"API_KEY": "sk-live"}}, "API_KEY"),
  ({"url": "https://h", "headers": {"Authorization": "Bearer ${TOKEN}"}}, "Authorization"),
  ({"command": "x", "env": {"API_KEY": "${API_KEY}"}}, None),
])
def test_literal_secret_refused(world, tmp_path, monkeypatch, entry, key):
  import superegm
  profile = setup(world, tmp_path, monkeypatch)
  good = {"command": "good-server"}
  (tmp_path / "claude").mkdir()
  (tmp_path / "claude" / ".claude.json").write_text(json.dumps({"mcpServers": {"good": good, "bad": entry}}), encoding="utf-8")
  config_before = (world.repo / CONFIG).read_bytes()
  code, out = world.run("builder-setup", "--mcp", "good", "--mcp", "bad")
  if key:
    assert code == 1 and key in out and "sk-live" not in out, out
    assert (world.repo / CONFIG).read_bytes() == config_before and not profile.exists()
    return
  assert code == 0, out
  builder = superegm.load_config(world.repo)["builder"]
  assert builder["mcp"] == {"good": good, "bad": entry}
  assert "mcp__good__*" in builder["allowed_tools"] and "mcp__bad__*" in builder["allowed_tools"]


def test_builder_setup_is_idempotent(world, tmp_path, monkeypatch):
  import superegm
  from superegm import init
  profile = setup(world, tmp_path, monkeypatch)
  owner_servers(tmp_path / "claude", "L", None, None, world.repo)
  argv = ("builder-setup", "--mcp", "relay", "--allow", "relay register")
  code, first = world.run(*argv)
  assert code == 0, first
  config_after, settings_after = (world.repo / CONFIG).read_bytes(), (profile / "settings.json").read_bytes()
  code, second = world.run(*argv)
  assert code == 0, second
  assert (world.repo / CONFIG).read_bytes() == config_after and (profile / "settings.json").read_bytes() == settings_after
  allowed = superegm.load_config(world.repo)["builder"]["allowed_tools"]
  assert allowed.count("mcp__relay__*") == 1 and allowed.count("Bash(relay register:*)") == 1
  assert first.strip().splitlines()[-1] == second.strip().splitlines()[-1] == "then run superegm doctor --probe"
  assert second.strip() == "then run superegm doctor --probe"
  step = init.STEPS.split("\n2. ", 1)[1].split("\n3. ", 1)[0]
  assert "superegm builder-setup" in step and "superegm doctor --probe" in step and '"disableClaudeAiConnectors": true' in step
  step = (ROOT / "docs" / "getting_started.md").read_text(encoding="utf-8").split("\n2. ", 1)[1].split("\n3. ", 1)[0]
  assert "superegm builder-setup" in step and "doctor --probe" in step


def test_config_key_order_is_kept(world, tmp_path, monkeypatch):
  setup(world, tmp_path, monkeypatch)
  held = json.loads((world.repo / CONFIG).read_text(encoding="utf-8"))
  held = {key: held[key] for key in sorted(held, reverse=True)}  # an order `sort_keys` would change
  (world.repo / CONFIG).write_text(json.dumps(held, indent=2) + "\n", encoding="utf-8")
  order = list(held)
  code, out = world.run("builder-setup", "--allow", "relay register")
  assert code == 0, out
  after = json.loads((world.repo / CONFIG).read_text(encoding="utf-8"))
  assert list(after) == order and list(after["builder"])[:len(held["builder"])] == list(held["builder"])
  assert "Bash(relay register:*)" in after["builder"]["allowed_tools"]


@pytest.mark.parametrize("argv", [("--allow", "relay 'register"), ("--mcp", "re'lay")])
def test_a_quoted_name_is_refused(world, tmp_path, monkeypatch, argv):
  profile = setup(world, tmp_path, monkeypatch)
  (tmp_path / "claude").mkdir()
  (tmp_path / "claude" / ".claude.json").write_text(json.dumps({"mcpServers": {"re'lay": {"command": "x"}}}), encoding="utf-8")
  config_before = (world.repo / CONFIG).read_bytes()
  code, out = world.run("builder-setup", *argv)
  assert code == 1 and "holds a quote" in out, out
  assert (world.repo / CONFIG).read_bytes() == config_before and not profile.exists()
