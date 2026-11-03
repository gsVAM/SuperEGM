# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the init subcommand.

"""superegm init: write .superegm/config.json with every key's default; print the owner's by-hand steps."""

import json
from pathlib import Path

import superegm as core

WRITES = frozenset()  # the config is in the working tree, not the store

STEPS = """wrote {path}
By hand, before the first typed skill runs:
1. Create the builder account (its own GitHub login with write access to {repo}) and put a
   token for it in the environment variable SUPEREGM_BUILDER_TOKEN (config key builder.gh_token_env).
2. Create the builder's empty profile at {profile_dir} (config key builder.profile_dir):
   no hooks, no plugins, only the login.
3. Set the branch protection of spec section 11 on `{base}`: updates restricted to the owner with
   no bypass for the builder account's role; `superegm/**` protected from force-push and deletion.
4. Add a workflow triggered on `pull_request` so every builder head gets CI.
5. Commit {path}; approve-spec commits it with the spec.
The store is {artifacts_dir} (config key artifacts_dir); it is never committed."""


def register(subparsers):
  p = core.add_parser(subparsers, "init", "write .superegm/config.json with every key's default; print the owner's by-hand steps",
                      runcard=False)
  p.add_argument("--artifacts-dir", dest="artifacts_dir",
                 help="the store, outside the working tree (default: ~/.superegm/<owner>/<name>)")
  p.add_argument("--base", help="the default branch; init refuses another")
  p.set_defaults(run=run, writes=WRITES)


def default_branch(repo_root: Path) -> str:
  head = core.run_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo_root, check=False).strip()
  if head.startswith("origin/"):
    return head[len("origin/"):]
  return core.run_git(["branch", "--show-current"], repo_root).strip()


def run(args):
  root = core.git_toplevel(Path.cwd())
  path = root / ".superegm" / "config.json"
  if path.exists():
    raise core.HandoffError(f"{path} exists: edit it by hand, or remove it to start over")
  origin = core.run_git(["remote", "get-url", "origin"], root)
  repo = core.parse_remote_url(origin)
  if not repo:
    raise core.HandoffError(f"cannot parse OWNER/NAME from origin `{origin.strip()}`")
  base = default_branch(root)
  if args.base and args.base != base:
    raise core.HandoffError(f"--base {args.base} is not the default branch ({base}): SuperEGM builds on the default branch")
  artifacts = Path(args.artifacts_dir).expanduser() if args.artifacts_dir else Path.home() / ".superegm" / repo
  artifacts = artifacts.resolve()
  if artifacts.is_relative_to(root.resolve()):
    raise core.HandoffError(f"artifacts_dir {artifacts} is inside the working tree {root}: "
                            f"the store lives outside the working tree")
  config = {**core.DEFAULT_CONFIG, "repo": repo, "base": base, "artifacts_dir": str(artifacts)}
  core.atomic_write(path, json.dumps(config, indent=2) + "\n")
  print(STEPS.format(path=path, repo=repo, base=base, artifacts_dir=artifacts,
                     profile_dir=config["builder"]["profile_dir"]))
  return 0
