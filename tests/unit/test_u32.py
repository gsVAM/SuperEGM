# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U32's tests: the subcommand modules' self-registration.

"""U32: the subcommand modules register their config defaults, `init` steps and `doctor` checks."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import types
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import discover
from conftest import ROOT, git, make_repo, Harness


def fresh(tmp_path, capsys, monkeypatch):
  """A repository with no config, the cwd, and a harness serving `gh api user -q .login`, as `init` needs."""
  repo = make_repo(tmp_path / "fresh")
  monkeypatch.chdir(repo)
  harness = Harness(capsys)
  harness.gh.extend("api", lambda args, cwd, token=None: (0, "octocat\n", "") if args[1:] == ["user", "-q", ".login"] else (1, "", "unexpected"))
  return harness


# ---------------------------------------------------------------- S5: the modules register their defaults, init steps and doctor checks

CORE = ["repo", "base", "artifacts_dir", "mode", "max_in_flight", "labels", "issue_template", "tracking_issue_title", "banned_terms",
        "fix_request_mention", "allowed_mentions", "reviewers", "commit_trailer", "owners", "owner_team", "pr_block_file"]
OWNED = {"collect": ["foreman"], "inbox": ["notify_timeout_seconds"], "judges": ["judges"], "launch_builder": ["builder"],
         "report": ["ci_wait_minutes"], "review": ["astra", "ingest"]}

def test_modules_register_their_defaults_init_steps_and_doctor_checks(tmp_path, capsys, monkeypatch):
  harness = fresh(tmp_path, capsys, monkeypatch)
  assert harness.run("init", "--artifacts-dir", str(tmp_path / "store"))[0] == 0
  written = json.loads((tmp_path / "fresh" / ".superegm" / "config.json").read_text(encoding="utf-8"))
  from superegm import foreman, init, orient, review
  modules = discover()
  assert list(modules) == sorted(modules) and "body" not in modules and "traces" not in modules and tuple(modules) == superegm.SUBCOMMANDS
  assert {n: list(m.CONFIG_DEFAULTS) for n, m in modules.items() if m.CONFIG_DEFAULTS} == OWNED
  assert list(superegm.CORE_CONFIG)[:len(CORE)] == CORE   # U34 appends brainstorm
  assert list(superegm.DEFAULT_CONFIG) == list(superegm.CORE_CONFIG) + [k for m in modules.values() for k in m.CONFIG_DEFAULTS] == list(written)
  assert "SUBCOMMANDS = (" not in (ROOT / "skills/plan/scripts/superegm/__init__.py").read_text(encoding="utf-8")
  assert review.INIT_STEP.startswith("The Astra lane is off until you set astra.enabled") and init.steps().endswith(review.INIT_STEP + "\nthen run `superegm doctor`")
  monkeypatch.setattr(foreman, "runner_path", lambda: None); monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: None)
  assert foreman.DOCTOR_CHECKS({}, ROOT, None) == [("astra", "not installed (heads will record not run)")]
  assert orient.DOCTOR_CHECKS({}, ROOT, None) == [("graphify", "not on PATH (informational)")] and [m for m in modules.values() if m.DOCTOR_CHECKS] == [foreman, orient]


# ---------------------------------------------------------------- S6: a faulty module is named, every command exits 1

@pytest.mark.parametrize("name, present, message", [("nodefaults", True, "superegm.nodefaults exposes no CONFIG_DEFAULTS"),
                                                     ("bogus", False, "superegm.bogus: No module named 'superegm.bogus'")])
def test_discover_names_a_module_without_defaults_or_failing_import(tmp_path, capsys, monkeypatch, name, present, message):
  harness = fresh(tmp_path, capsys, monkeypatch)
  real = superegm.pkgutil.iter_modules
  monkeypatch.setattr(superegm.pkgutil, "iter_modules", lambda path: [*real(path), types.SimpleNamespace(name=name)])
  if present:
    module = types.ModuleType(f"superegm.{name}")
    vars(module).update(register=lambda s: None, run=lambda a: 0, WRITES=frozenset(), INIT_STEP="", DOCTOR_CHECKS=None)
    monkeypatch.setitem(sys.modules, f"superegm.{name}", module)
  code, out = harness.run("init", "--artifacts-dir", str(tmp_path / "store"))
  assert code == 1 and f"superegm: {message}" in out, out


# ---------------------------------------------------------------- S7: spec_blob and store's explicit inputs

def test_spec_blob_and_store_take_their_inputs_explicitly(world):
  from superegm import approve_spec, launch_builder, review, spec_blob, store
  first = world.spec.read_bytes(); sha = hashlib.sha256(first).hexdigest()
  world.spec.write_text("changed\n", encoding="utf-8"); git(["commit", "-qam", "edit"], world.repo)
  assert spec_blob(world.repo, "docs/designs/sample.md", sha) == first.decode("utf-8") and spec_blob(world.repo, "docs/designs/sample.md", "0" * 64) is None
  assert not hasattr(approve_spec, "branch_holds") and all("hashlib.sha256(blob" not in Path(m.__file__).read_text(encoding="utf-8") for m in (approve_spec, launch_builder, review))
  superegm.CURRENT_ARGS = argparse.Namespace(design=str(world.spec))
  with pytest.raises(superegm.HandoffError, match="store: nope: no such handoff"):
    store(world.repo, argparse.Namespace(handoff="nope"))


# ---------------------------------------------------------------- S8: the prose

PROSE = [("skills/wave/references/builder_orders.md", "HEAD detached", True), ("skills/integrate/SKILL.md", "[--close [--patch]]", True),
         ("skills/integrate/SKILL.md", "effect_kinds: [state-store, start-session, github-write]", True),
         ("skills/integrate/SKILL.md", "of every unit whose PR merged, its issue open or not", True),
         ("skills/review-spec/references/review_loop.md", "citing no line, or a line the spec does not hold, takes the same path", True),
         ("skills/review-spec/references/review_loop.md", "<6 hex>-plan-<unit>", False), ("skills/plan/references/handoff_plan.md", "may hold only", False),
         ("skills/plan/references/handoff_plan.md", "<6hex>/", False), ("skills/plan/references/issue_template.md", "<6hex>/", False),
         ("skills/orient/SKILL.md", "<6 hex>/orient", False), ("skills/brainstorming/SKILL.md", "layer in the flat store", False)]

@pytest.mark.parametrize("path, needle, present", PROSE)
def test_the_prose_of_u32(path, needle, present):
  text = (ROOT / path).read_text(encoding="utf-8")
  assert (needle in text) is present, (path, needle)
  assert re.search(r"(Added|[Mm]odified) by SuperEGM \(gsVAM\), 2026: ", text), path
