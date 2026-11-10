# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the init subcommand; `owners` from `gh api user` and the pointer to the README's token recipe and to `doctor` (spec section 11); the astra.enabled and astra.heads sentence (U17); the ingest sentence (U21); the ~/.superegm/notify sentence (U23); the foreman.run_timeout_minutes sentence (U25); step 2's disableClaudeAiConnectors, builder.plugins and builder.mcp (U27); `steps()` composing the modules' INIT_STEPs, those four sentences moved to their modules (U32).

"""superegm init: write .superegm/config.json with every key's default; print the owner's by-hand steps."""

import json
from pathlib import Path

import superegm as core

WRITES = frozenset()  # the config is in the working tree, not the store

OWN = """wrote {path}
By hand, before the first typed skill runs:
1. Create the builder account and its token as README.md, "Before the first run" step 1 says; put the token in SUPEREGM_BUILDER_TOKEN (config key builder.gh_token_env), never in the repository or the config, or register a GitHub App as that step says and set builder.app (SUPEREGM_BUILDER_TOKEN then stays unset: one identity per repository).
2. Create the builder's empty profile at {profile_dir} (config key builder.profile_dir):
   no hooks, no plugins, no skills/ or commands/ directory, only the login (`CLAUDE_CONFIG_DIR={profile_dir} claude`,
   `/login`, exit) and a settings.json with "syncClaudeAiPlugins": false and "disableClaudeAiConnectors": true,
   written before the login. A plugin the builder is to load is named in builder.plugins (its <name>@<marketplace>
   id, installed once into this session's profile, disabled there) and passed by --plugin-dir per launch; the
   builder's MCP servers go in builder.mcp (mcpServers form: the server map under that key, a secret by ${{VAR}} reference, never its value),
   passed by --mcp-config --strict-mcp-config.
3. Set the branch protection of spec section 11 on `{base}`: updates restricted to the logins in
   config.owners (a classic restriction) or, by a ruleset, with no bypass for the builder account's
   role and no team but config.owner_team; `superegm/**` protected from force-push and deletion by a
   ruleset whose include pattern is exactly `refs/heads/superegm/**/*` (`refs/heads/superegm/**`
   matches no branch on GitHub).
4. Add a workflow triggered on `pull_request` so every builder head gets CI.
5. Commit {path}; approve-spec commits it with the spec.
The store is {artifacts_dir} (config key artifacts_dir); it is never committed."""
LAST = "then run `superegm doctor`"
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # its own text is OWN (U32)


def steps() -> str:
  """Its own text, the modules' non-empty INIT_STEPs in discovery order, then the doctor line (U32)."""
  return "\n".join([OWN, *(m.INIT_STEP for m in core.discover().values() if m.INIT_STEP), LAST])


def __getattr__(name):
  if name == "STEPS":  # the composed text under its earlier name, for the readers that pin it
    return steps()
  raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
  try:
    owner = core.gh(["api", "user", "-q", ".login"]).strip()
  except core.GhError as error:
    raise core.HandoffError(f"owners: {error}") from None
  config = {**core.DEFAULT_CONFIG, "repo": repo, "base": base, "artifacts_dir": str(artifacts), "owners": [owner]}
  core.atomic_write(path, json.dumps(config, indent=2) + "\n")
  print(steps().format(path=path, repo=repo, base=base, artifacts_dir=artifacts,
                     profile_dir=config["builder"]["profile_dir"]))
  return 0
