# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U14's tests of `superegm doctor` (spec section 11).

"""`superegm doctor`: one line per wave prerequisite, `ok` or the refusal `launch` or `launch-builder`
would give, in a pinned order; no run card, no store write."""

import json, shutil
from pathlib import Path
import pytest
from test_builders import UNIT, seed, github, configure, push_to_origin

OK = ["config: ok", "owner: ok (owner)", "origin: ok", "token: ok", "builder: ok (builder-bot)", "role: ok (write)",
      "scopes: ok (classic: repo, read:org)", "protection: ok", "profile: ok", "graphify: not on PATH (informational)"]
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
])
def test_doctor_lines(world, monkeypatch, case, code, expected):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: "/usr/local/bin/graphify" if case == "graphify" and cmd == "graphify" else None)
  config = world.repo / ".superegm/config.json"
  profile = json.loads(config.read_text(encoding="utf-8"))["builder"]["profile_dir"]
  if case == "config": configure(world, bogus=1)
  if case == "not-owner": configure(world, owners=["someone-else"])
  if case == "origin": push_to_origin(world, ".github/workflows/tests.yml", "on: [push]\n")
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
  skipped = {"config": set(NAMES) - {"config"}, "no-token": {"builder", "role", "scopes", "protection"}}.get(case, set())
  assert [line.split(":")[0] for line in lines] == [name for name in NAMES if name not in skipped]
  assert "ghp_builder" not in out and not s.path("launches", f"{UNIT}.json").parent.exists()
