# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U32's tests: the subcommand modules' self-registration.

"""U32: the subcommand modules register their config defaults, `init` steps and `doctor` checks."""

import json
import shutil

import superegm  # the harness reloads the package per test: read its names at call time
from superegm import discover
from conftest import ROOT, make_repo, Harness


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
