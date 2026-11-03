# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_launch` as the launch module; it marks the ready units up to `max_in_flight` after the protection checks of spec section 11.

"""superegm launch: check what the launch needs, then mark the ready units up to `max_in_flight`."""

import os
from pathlib import Path

import superegm as core

WRITES = frozenset(["state", "runcards"])  # the store kinds this subcommand writes
SKILLS = frozenset(["wave"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "launch", "mark the ready units up to max_in_flight after the protection checks")
  p.add_argument("--idle", default="", help="comma-separated units that hold no slot in this invocation")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  try:
    return launch(args, card)
  except core.HandoffError as error:
    raise core.HandoffError(f"launch: {error}") from None


def launch(args, card):
  plan, st = core.locate(args)
  config = st.config
  base, token_env = config["base"], config["builder"]["gh_token_env"]
  repo_root = core.git_toplevel(Path.cwd())
  core.run_git(["fetch", "--no-write-fetch-head", config["remote"], f"+refs/heads/{base}:refs/superegm/base"], repo_root)
  handoff = core.Handoff(plan, st)
  core.require_frozen_units(handoff)
  state = handoff.state
  core.require_receipt(state)
  core.require_repo(handoff)
  builder = builder_login(config, os.environ.get(token_env))
  core.card_add(st, args.runcard, "builder", {"login": builder, "token_env": token_env})
  summary, _ = core.status_pass(handoff, save=False)
  marked = list(summary["ready"])
  for uid in marked:
    state.setdefault("units", {}).setdefault(uid, {})["launched"] = {"at": core.now_iso(), "runcard": args.runcard}
    core.journal(st, f"{uid} marked for launch")
  core.save_state(handoff.artifact_dir, state)
  print("in flight: " + (", ".join(summary["in_flight"]) or "none"))
  print("marked: " + (", ".join(marked) or "none"))
  return 0


def builder_login(config, token_env_value):
  """The builder account's login under its token, refused when the token is unset or is the elephant's own."""
  env = config["builder"]["gh_token_env"]
  if not token_env_value:
    raise core.HandoffError(f"{env} is not set")
  builder = core.gh(["api", "user", "-q", ".login"], token=token_env_value).strip()
  me = core.gh(["api", "user", "-q", ".login"]).strip()
  if builder == me:
    raise core.HandoffError(f"the builder token is the elephant's own login ({me})")
  return builder
