# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U37's tests: the `instructions` key, its freezing at approval, the one renderer, the stored first render and the builder's section.

"""U37: instructions, the key and the builder."""

import json

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, git, set_config
from test_review import SLUG, approve, converged_spec, hstore

BANNED = ["(?i)secret-codename"]
RULES = ".superegm/rules.md"


def configure(world, value):
  """The repository's config with `instructions` set to `value` (a malformed value stays as written)."""
  set_config(world, repo=REPO, banned_terms=BANNED, instructions=value)


def commit_file(world, rel, data):
  """`rel` written (text or bytes) and committed."""
  path = world.repo / rel
  path.parent.mkdir(parents=True, exist_ok=True)
  (path.write_bytes if isinstance(data, bytes) else lambda d: path.write_text(d, encoding="utf-8"))(data)
  git(["add", "--", rel], world.repo)
  git(["commit", "-qm", f"add {rel}"], world.repo)


@pytest.mark.parametrize("value, refused", [
  ([], False),
  ([{"file": RULES, "to": ["builder", "judges"]}], False),
  ([{"file": RULES, "to": []}], True),
  ([{"file": RULES, "to": ["owner"]}], True),
  ([{"to": ["builder"]}], True),
  ({"file": "x"}, True),
])
def test_instructions_key_validated(world, value, refused):
  """approve-spec and instructions --spec refuse a malformed key, naming it."""
  assert superegm.DEFAULT_CONFIG["instructions"] == []
  commit_file(world, RULES, "Run the suite.\n")
  configure(world, value)
  spec, cid, rid = converged_spec(world)
  code, err = approve(world, spec, cid, "--yes")
  assert "unknown keys" not in err
  assert (code == 1 and "instructions" in err) if refused else code == 0, err
  git(["add", "-A"], world.repo)
  git(["commit", "-qm", "config at HEAD", "--allow-empty"], world.repo)
  code, err = world.run("instructions", "--role", "reviewers", "--spec", str(spec), "--review", rid, "--round", 1, "--runcard", cid)
  assert (code == 1 and "instructions" in err) if refused else code == 0, err
