# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U24's tests of the registry, the refusals, the detached start, the stall read and the prose.

"""U24 (spec section 11.2): `register` and the registry, `runcard open`'s refusal while a tick's launch may be
live, `start_detached`, the stall read across a tick's `wave` cards and the driver skill's prose.
`HOME` is `tmp_path` in every test here."""

import json
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO
from test_builders import seed, put, git, launched, launches_of, UNIT  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def home(monkeypatch, tmp_path):
  monkeypatch.setenv("HOME", str(tmp_path))


def test_register_keeps_one_entry_per_store(world, monkeypatch, tmp_path):
  s, card, hid, _ = seed(world); dcard, root, wt2 = world.open_card("driver", world.spec), str(world.repo.resolve()), tmp_path / "wt2"
  assert world.run("register", "--runcard", dcard)[0] == 0 and superegm.load_registry() == [{"repo": REPO, "root": root, "artifacts_dir": str(s.root)}]
  git(["worktree", "add", "-q", str(wt2), "-b", "wt2"], world.repo); monkeypatch.chdir(wt2); assert world.run("register", "--runcard", dcard)[0] == 0
  assert [e["root"] for e in superegm.load_registry()] == [str(wt2.resolve())] and f"registry: {s.root} root {root} → {wt2.resolve()}" in s.path("journal").read_text()
  assert world.run("register", "--remove", "--runcard", dcard)[0] == 0 and superegm.load_registry() == [] and s.kind_of(s.path("driver", hid)) == "driver" and superegm.boot_id() == superegm.boot_id() != ""
  put(tmp_path / ".superegm/registry.json", '[{"mode": "x"}]'); assert "register: registry: unknown key mode" in world.run("register", "--runcard", dcard)[1]
