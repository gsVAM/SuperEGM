# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U14's tests of `superegm doctor` (spec section 11); the App lines and the launched environment (U15).

"""`superegm doctor`: one line per wave prerequisite, `ok` or the refusal `launch` or `launch-builder`
would give, in a pinned order; no run card, no store write."""

import json, shutil
from pathlib import Path
import pytest
from conftest import REPO
from test_builders import UNIT, RULESET, SUPEREGM_RULESET, seed, app_seed, github, configure, push_to_origin, git
from test_builder_token import key, OPENSSL, FOUR  # noqa: F401  the key fixture

OK = ["config: ok", "owner: ok (owner)", "origin: ok", "token: ok", "builder: ok (builder-bot)", "role: ok (write)",
      "scopes: ok (classic: repo, read:org)", "protection: ok", "profile: ok", "gh: ok (/usr/local/bin/gh)", "environment: ok",
      "graphify: not on PATH (informational)"]
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
])
def test_doctor_lines(world, monkeypatch, case, code, expected):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"graphify": "/usr/local/bin/graphify" if case == "graphify" else None,
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
    assert line.format(config=config, profile=profile) in lines, out
  skipped = {"config": set(NAMES) - {"config"}, "no-token": {"builder", "role", "scopes", "protection"}, "no-gh": {"environment"}}.get(case, set())
  assert [line.split(":")[0] for line in lines] == [name for name in NAMES if name not in skipped]
  assert "ghp_builder" not in out and not s.path("launches", f"{UNIT}.json").parent.exists()


OK_APP = ["config: ok", "owner: ok (owner)", "origin: ok", "credential: ok (app superegm-builder)", "key: ok ({key})", "openssl: ok ({openssl})", "artifacts_dir: ok",
          "app: ok (superegm-builder #12345)", f"permissions: ok ({FOUR[1:-1]})", "token: ok", "installation: ok (example-org/webhooks)",
          "scanning: push protection enabled, non-provider patterns enabled", "protection: ok", "profile: ok", "gh: ok ({gh})", "environment: ok", "graphify: not on PATH (informational)"]


@pytest.mark.parametrize("case, code, expected, skipped", [
  ("ok", 0, OK_APP, ()), ("owner-config", 0, OK_APP, ()),
  ("both-set", 1, ["credential: builder.app is set (SUPEREGM_APP_KEY) and SUPEREGM_BUILDER_TOKEN is also set: one identity per repository"], ()),
  ("no-key", 1, ["key: SUPEREGM_APP_KEY is not set"], ("app", "permissions", "token", "installation")),
  ("push-url", 1, ["environment: push URL of origin under the launched environment is {origin}, not https://"], ()),
])
def test_doctor_app_lines(world, monkeypatch, key, tmp_path, case, code, expected, skipped):
  *_, gh = app_seed(world, monkeypatch, key, tmp_path, rulesets=[RULESET, SUPEREGM_RULESET])
  if case == "both-set": monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  if case == "no-key": monkeypatch.delenv("SUPEREGM_APP_KEY")
  if case == "push-url": git(["remote", "set-url", "--push", "origin", str(world.repo.parent / "origin.git")], world.repo)
  if case == "owner-config":  # the owner's prompts, helper and SSH rewrite: all shut out of the launched environment
    askpass = tmp_path / "askpass"; askpass.write_text("#!/bin/sh\necho password=p\n", encoding="utf-8"); askpass.chmod(0o755)
    monkeypatch.setenv("GIT_ASKPASS", str(askpass)); monkeypatch.setenv("SSH_ASKPASS", str(askpass))
    (tmp_path / "gitconfig").write_text('[credential]\n\thelper = !echo password=p\n[url "git@github.com:"]\n\tpushInsteadOf = https://github.com/\n', encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
  got, out = world.run("doctor")
  assert got == code and all(l.format(key=key, openssl=OPENSSL, gh=gh, origin=world.repo.parent / "origin.git") in out.splitlines() for l in expected), out
  assert [l.split(":")[0] for l in out.splitlines()] == [l.split(":")[0] for l in OK_APP if l.split(":")[0] not in skipped]
