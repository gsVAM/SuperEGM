# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U14's tests of `superegm doctor` (spec section 11); the App lines and the launched environment (U15); the informational `merge:` line (U19); the informational `python3.12`, `hooks` and `core.hooksPath` lines (U25); the five driver lines (U24).

"""`superegm doctor`: one line per wave prerequisite, `ok` or the refusal `launch` or `launch-builder`
would give, in a pinned order; no run card, no store write."""

import hashlib, json, plistlib, shutil, sys
from pathlib import Path
import pytest
from conftest import REPO
from test_builders import UNIT, RULESET, SUPEREGM_RULESET, seed, app_seed, github, configure, push_to_origin, git
from test_builder_token import key, OPENSSL, FOUR  # noqa: F401  the key fixture
from superegm.launch_builder import HELPER
from test_u27 import elephant, PONY, MCP, THREE

DRIVER_NONE = ["driver: not installed", "sleep: not reported", "root: not registered", "env: absent", "notify: absent"]
# U28: the role table at init's defaults, after U24's `notify:` line
ROLES = ["model: builder doable claude-opus-5-5 medium", "model: goldfish opus xhigh", "model: astra lanes gpt-6-astra xhigh",
         "model: astra head lane gpt-6-astra high", "model: judge fable fable xhigh", "model: judge opus opus max", "model: judge astra gpt-6-astra xhigh"]

OK = ["config: ok", "owner: ok (owner)", "origin: ok", "token: ok", "builder: ok (builder-bot)", "role: ok (write)",
      "scopes: ok (classic: repo, read:org)", "protection: ok",
      "merge: gh pr merge --admin (informational: the owner merges with the admin bypass where the base ruleset restricts updates to config.owners)", "profile: ok", "plugins: none", "mcp: none", "gh: ok (/usr/local/bin/gh)", "environment: ok",
      "graphify: not on PATH (informational)", "astra: not installed (heads will record not run)",
      "python3.12: not on PATH (informational)", "hooks: none", "core.hooksPath: unset", *DRIVER_NONE, *ROLES]
NAMES = [line.split(":")[0] for line in OK]


@pytest.mark.parametrize("case, code, expected", [
  ("ok", 0, OK),
  ("config", 1, ["config: {config}: unknown keys ['bogus']"]),
  ("not-owner", 1, ["owner: owner is not in config.owners (someone-else)"]),
  ("origin", 1, ["origin: origin/main carries no workflow triggered on pull_request"]),
  ("no-token", 1, ["token: SUPEREGM_BUILDER_TOKEN is not set"]),
  ("own-login", 1, ["builder: the builder token is the elephant's own login (owner)"]),
  ("builder-owner", 1, ["builder: the builder token's login (builder-bot) is in config.owners"]),
  ("role", 1, ["role: builder-bot's role on example-org/webhooks is admin, not write"]),
  ("fine-grained", 0, ["scopes: ok (fine-grained: permissions not probed)"]),
  ("no-repo-scope", 1, ["scopes: classic token lacks repo (read:org)"]),
  ("workflow-scope", 1, ["scopes: classic token carries workflow (repo, workflow)"]),
  ("protection", 1, ["protection: base branch main: updates are not restricted to the owner (no classic restrictions, no active ruleset update rule)"]),
  ("profile", 1, ["profile: builder profile {profile} holds hooks"]),
  ("graphify", 0, ["graphify: ok (/usr/local/bin/graphify)"]),
  ("no-gh", 1, ["gh: gh is not on this machine's PATH"]),
  ("astra", 0, ["astra: ok ({runner})"]),
  ("python3.12", 0, ["python3.12: ok (/usr/local/bin/python3.12)"]),
  ("hooks", 0, ["hooks: post-checkout, pre-push", "core.hooksPath: {hooks}"]),
])
def test_doctor_lines(world, monkeypatch, tmp_path, case, code, expected):
  monkeypatch.setenv("HOME", str(tmp_path)); s, card, hid, _ = seed(world)
  runner = tmp_path / "plugins/cache/claudex-loop/claudex-loop/1.0.0/skills/claudex-loop/scripts/runner.py"
  if case == "astra":
    runner.parent.mkdir(parents=True)
    runner.write_text("", encoding="utf-8")
  hooks = tmp_path / "hooks"
  if case == "hooks":  # two executables, a `.sample` skipped, at core.hooksPath
    hooks.mkdir()
    for name in ("pre-push", "post-checkout", "pre-commit.sample"):
      (hooks / name).write_text("#!/bin/sh\n", encoding="utf-8"); (hooks / name).chmod(0o755)
    git(["config", "core.hooksPath", str(hooks)], world.repo)
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins"))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"graphify": "/usr/local/bin/graphify" if case == "graphify" else None,
                                                             "python3.12": "/usr/local/bin/python3.12" if case == "python3.12" else None,
                                                             "gh": None if case == "no-gh" else "/usr/local/bin/gh"}.get(cmd))
  config = world.repo / ".superegm/config.json"
  profile = json.loads(config.read_text(encoding="utf-8"))["builder"]["profile_dir"]
  if case == "config": configure(world, bogus=1)
  if case == "not-owner": configure(world, owners=["someone-else"])
  if case == "origin": push_to_origin(world, ".github/workflows/tests.yml", "on: [push]\n")
  git(["remote", "set-url", "--push", "origin", f"git@github.com:{REPO}.git"], world.repo)  # the SSH form a real push would break on; the launched environment rewrites it
  if case == "no-token": monkeypatch.delenv("SUPEREGM_BUILDER_TOKEN")
  if case == "own-login": github(world, builder="owner")
  if case == "builder-owner": configure(world, owners=["owner", "builder-bot"])
  if case == "role": github(world, role="admin")
  if case == "fine-grained": github(world, scopes=None)
  if case == "no-repo-scope": github(world, scopes="read:org")
  if case == "workflow-scope": github(world, scopes="repo, workflow")
  if case == "protection": github(world, rulesets=[])
  if case == "profile": (Path(profile) / "settings.json").write_text('{"hooks": {"SessionStart": []}}', encoding="utf-8")
  got, out = world.run("doctor")
  assert got == code, out
  lines = out.splitlines()
  for line in expected:
    assert line.format(config=config, profile=profile, runner=runner, hooks=hooks) in lines, out
  skipped = {"config": set(NAMES) - {"config"}, "no-token": {"builder", "role", "scopes", "protection"}, "no-gh": {"environment"}}.get(case, set())
  assert [line.split(":")[0] for line in lines] == [name for name in NAMES if name not in skipped]
  assert "ghp_builder" not in out and not s.path("launches", f"{UNIT}.json").parent.exists()


@pytest.mark.parametrize("scope, code, expected", [
  ("user", 0, [f"plugins: {PONY} 5.3.3 [SessionStart, SubagentStart, UserPromptSubmit]", "mcp: context7", "profile: ok"]),
  ("project", 1, [f"profile: plugin {PONY} not installed", f"plugins: plugin {PONY} not installed", "mcp: context7"])])
def test_doctor_prints_the_plugins_and_mcp_lines(world, monkeypatch, tmp_path, scope, code, expected):
  seed(world); git(["remote", "set-url", "--push", "origin", f"git@github.com:{REPO}.git"], world.repo)
  elephant(tmp_path, monkeypatch, [scope], {"hooks/hooks.json": THREE})
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"gh": "/usr/local/bin/gh"}.get(cmd))
  cfg = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]
  configure(world, builder={**cfg, "plugins": [PONY], "mcp": MCP})
  got, out = world.run("doctor")
  assert got == code and all(line in out.splitlines() for line in expected), out
  assert [l.split(":")[0] for l in out.splitlines()] == NAMES


OK_APP = ["config: ok", "owner: ok (owner)", "origin: ok", "credential: ok (app superegm-builder)", "key: ok ({key})", "openssl: ok ({openssl})", "artifacts_dir: ok",
          "app: ok (superegm-builder #12345)", f"permissions: ok ({FOUR[1:-1]})", "token: ok", "installation: ok (example-org/webhooks)",
          "scanning: push protection enabled, non-provider patterns enabled", "protection: ok",
          "merge: gh pr merge --admin (informational: the owner merges with the admin bypass where the base ruleset restricts updates to config.owners)", "profile: ok", "plugins: none", "mcp: none", "gh: ok ({gh})", "environment: ok", "graphify: not on PATH (informational)", "astra: not installed (heads will record not run)",
          "python3.12: not on PATH (informational)", "hooks: none", "core.hooksPath: unset", *DRIVER_NONE, *ROLES]


@pytest.mark.parametrize("case, code, expected, skipped", [
  ("ok", 0, OK_APP, ()), ("owner-config", 0, OK_APP, ()),
  ("both-set", 1, ["credential: builder.app is set (SUPEREGM_APP_KEY) and SUPEREGM_BUILDER_TOKEN is also set: one identity per repository"], ()),
  ("no-key", 1, ["key: SUPEREGM_APP_KEY is not set"], ("app", "permissions", "token", "installation")),
  ("push-url", 1, ["environment: push URL of origin under the launched environment is {origin}, not https://"], ()),
])
def test_doctor_app_lines(world, monkeypatch, key, tmp_path, case, code, expected, skipped):
  monkeypatch.setenv("HOME", str(tmp_path)); *_, gh = app_seed(world, monkeypatch, key, tmp_path, rulesets=[RULESET, SUPEREGM_RULESET])
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins"))
  if case == "both-set": monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  if case == "no-key": monkeypatch.delenv("SUPEREGM_APP_KEY")
  if case == "push-url": git(["remote", "set-url", "--push", "origin", str(world.repo.parent / "origin.git")], world.repo)
  if case == "owner-config":  # the owner's prompts, helper and SSH rewrite: all shut out of the launched environment
    askpass = tmp_path / "askpass"; askpass.write_text("#!/bin/sh\necho password=p\n", encoding="utf-8"); askpass.chmod(0o755)
    monkeypatch.setenv("GIT_ASKPASS", str(askpass)); monkeypatch.setenv("SSH_ASKPASS", str(askpass))
    (tmp_path / "gitconfig").write_text('[credential]\n\thelper = !echo password=p\n[url "git@github.com:"]\n\tpushInsteadOf = https://github.com/\n', encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
  got, out = world.run("doctor")
  assert got == code and all(l.format(key=key, openssl=OPENSSL, gh=gh, origin=world.repo.parent / "origin.git", hooks=tmp_path / "hooks") in out.splitlines() for l in expected), out
  assert [l.split(":")[0] for l in out.splitlines()] == [l.split(":")[0] for l in OK_APP if l.split(":")[0] not in skipped]


@pytest.mark.parametrize("versions, expect", [({"1.0.0": "live", "1.1.0": "orphaned", "1.2.0": "no-runner"}, "1.0.0"), ({}, None)])
def test_runner_path_picks_the_highest_unorphaned_version(tmp_path, monkeypatch, versions, expect):
  from superegm.foreman import runner_path
  for version, state in versions.items():
    scripts = tmp_path / "plugins/cache/claudex-loop/claudex-loop" / version / "skills/claudex-loop/scripts"
    scripts.mkdir(parents=True)
    state != "no-runner" and (scripts / "runner.py").write_text("", encoding="utf-8")
    state == "orphaned" and (scripts.parents[2] / ".orphaned_at").write_text("", encoding="utf-8")
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins"))
  assert runner_path() == (str(tmp_path / f"plugins/cache/claudex-loop/claudex-loop/{expect}/skills/claudex-loop/scripts/runner.py") if expect else None)


@pytest.mark.parametrize("env, base, names, expect", [
  ("CLAUDE_CODE_PLUGIN_CACHE_DIR", "plugins", ["1.0.0", "latest", "2.0.0-rc1"], "1.0.0"),
  ("CLAUDE_CONFIG_DIR", "config/plugins", ["0.9.0", "0.10.0"], "0.10.0")])
def test_runner_path_skips_non_numeric_names_and_falls_back_to_the_config_dir(tmp_path, monkeypatch, env, base, names, expect):
  from superegm.foreman import runner_path
  for name in names:
    scripts = tmp_path / base / "cache/claudex-loop/claudex-loop" / name / "skills/claudex-loop/scripts"
    scripts.mkdir(parents=True)
    (scripts / "runner.py").write_text("", encoding="utf-8")
  monkeypatch.delenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", raising=False)
  monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
  monkeypatch.setenv(env, str(tmp_path / ("plugins" if env == "CLAUDE_CODE_PLUGIN_CACHE_DIR" else "config")))
  assert runner_path() == str(tmp_path / base / f"cache/claudex-loop/claudex-loop/{expect}/skills/claudex-loop/scripts/runner.py")


def arranged(world, monkeypatch, tmp_path, setup):
  """`test_doctor_lines`'s ok case and, `setup` given, the timer, `~/.superegm/env`, the notify hook, the registry's
  entry and a fake `pmset`."""
  monkeypatch.setenv("HOME", str(tmp_path)); s, card, hid, _ = seed(world)
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins")); monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  pmset = tmp_path / "bin/pmset"
  tools = {"gh": "/usr/local/bin/gh", **({"pmset": str(pmset)} if setup else {})}
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: tools.get(cmd))
  git(["remote", "set-url", "--push", "origin", f"git@github.com:{REPO}.git"], world.repo)
  if not setup:
    return s
  pmset.parent.mkdir(parents=True)
  pmset.write_text("#!/bin/sh\necho 'System-wide power settings:'\necho ' sleep                1 (sleep prevented by caffeinate)'\n", encoding="utf-8"); pmset.chmod(0o755)
  argv = [sys.executable, str(setup.get("plist", HELPER)), "driver", "tick"]
  if setup.get("systemd"):
    units = tmp_path / ".config/systemd/user"; units.mkdir(parents=True)
    (units / "superegm-driver.service").write_text(f"[Service]\nType=oneshot\nExecStart={' '.join(argv)}\nKillMode=process\n", encoding="utf-8")
    (units / "superegm-driver.timer").write_text("[Timer]\nOnBootSec=1min\nOnUnitActiveSec=15min\n", encoding="utf-8")
  else:
    plist = tmp_path / "Library/LaunchAgents/com.superegm.driver.plist"; plist.parent.mkdir(parents=True)
    plist.write_bytes(plistlib.dumps({"Label": "com.superegm.driver", "ProgramArguments": argv, "StartInterval": 900}))
  home = tmp_path / ".superegm"; home.mkdir(exist_ok=True)
  values = {"PATH": str(tmp_path / "bin"), "CLAUDE_CONFIG_DIR": str(tmp_path / "profile"), "SUPEREGM_BUILDER_TOKEN": "ghp_builder"}
  (home / "env").write_text("".join(f"{k}={values[k]}\n" for k in setup.get("env", KEYS)), encoding="utf-8"); (home / "env").chmod(setup.get("mode", 0o600))
  (home / "notify").write_text("#!/bin/sh\n", encoding="utf-8")
  root = tmp_path / setup["root"] if "root" in setup else world.repo.resolve()
  (home / "registry.json").write_text(json.dumps([{"repo": REPO, "root": str(root), "artifacts_dir": str(s.root)}]), encoding="utf-8")
  return s


KEYS, BASE = ("PATH", "CLAUDE_CONFIG_DIR", "SUPEREGM_BUILDER_TOKEN"), {"plist": HELPER}


def test_doctor_names_a_registry_it_cannot_read(world, monkeypatch, tmp_path):
  arranged(world, monkeypatch, tmp_path, BASE); (tmp_path / ".superegm/registry.json").write_text('[{"mode": "x"}]', encoding="utf-8")
  got, out = world.run("doctor"); assert got == 0 and "root: registry: unknown key mode" in out.splitlines(), out
@pytest.mark.parametrize("setup, lines", [
  (None, ["driver: not installed", "sleep: not reported", "root: not registered", "env: absent", "notify: absent"]),
  (BASE, ["driver: installed (15 min) at {root}", "sleep: 1 (sleep prevented by caffeinate)", "root: ok", "env: ok", "notify: ok ({sha})"]),
  ({"plist": "/old/root/skills/plan/scripts/superegm.py"}, ["driver: stale (/old/root; the env profile's root {root})"]), ({"systemd": True}, ["driver: installed (15 min) at {root}"]),
  ({**BASE, "env": KEYS[::2]}, ["env: missing CLAUDE_CONFIG_DIR"]), ({**BASE, "mode": 0o644}, ["env: readable by others"]),
  ({**BASE, "root": "elsewhere"}, ["root: {tmp}/elsewhere is not a worktree of example-org/webhooks"])])
def test_doctor_driver_lines(world, monkeypatch, tmp_path, setup, lines):
  arranged(world, monkeypatch, tmp_path, setup); got, out = world.run("doctor")
  assert got == 0 and all(l.format(root=HELPER.parents[3], tmp=tmp_path, sha=hashlib.sha256(b"#!/bin/sh\n").hexdigest()) in out.splitlines() for l in lines), out


def test_doctor_prints_the_role_table(world, monkeypatch, tmp_path):
  s, card, hid, _ = seed(world)
  cfg = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))
  configure(world, builder={**cfg["builder"], "model": "claude-sonnet-5-5", "effort": "high"}, reviewers={"model": "fable", "effort": "max"},
            astra={"enabled": True, "heads_effort": "xhigh"},
            judges={"min_vendors": 1, "members": [{"name": "fable", "via": "adapter", "effort": "max", "model": "sonnet"}, {"name": "astra", "via": "runner"}]})
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins")); monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder"); monkeypatch.setenv("HOME", str(tmp_path))
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"gh": "/usr/local/bin/gh", "python3.12": "/usr/local/bin/python3.12"}.get(cmd))
  git(["remote", "set-url", "--push", "origin", f"git@github.com:{REPO}.git"], world.repo)
  code, out = world.run("doctor")
  assert code == 0 and out.splitlines()[-6:] == ["model: builder doable claude-sonnet-5-5 high", "model: goldfish fable max", "model: astra lanes gpt-6-astra xhigh",
                                                 "model: astra head lane gpt-6-astra xhigh", "model: judge fable sonnet max", "model: judge astra gpt-6-astra xhigh"], out


def test_doctor_role_table_reads_a_malformed_member_as_one_informational_line(world, monkeypatch, tmp_path):
  s, card, hid, _ = seed(world)
  configure(world, judges={"min_vendors": 1, "members": [{"name": "fable", "via": "pigeon"}]})
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins")); monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder"); monkeypatch.setenv("HOME", str(tmp_path))
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"gh": "/usr/local/bin/gh", "python3.12": "/usr/local/bin/python3.12"}.get(cmd))
  git(["remote", "set-url", "--push", "origin", f"git@github.com:{REPO}.git"], world.repo)
  code, out = world.run("doctor")
  assert code == 0 and out.splitlines()[-1] == "model: unreadable (KeyError: 'pigeon')" and "token: ok" in out, out
