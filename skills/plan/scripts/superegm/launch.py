# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_launch` as the launch module; it marks the ready units up to `max_in_flight` after the protection checks of spec section 11.

"""superegm launch: check what the launch needs, then mark the ready units up to `max_in_flight`."""

import hashlib
import os
import re
import subprocess
import urllib.parse
from pathlib import Path

import superegm as core

WRITES = frozenset(["state", "runcards"])  # the store kinds this subcommand writes
SKILLS = frozenset(["wave"])  # the skills whose card this subcommand accepts
ROLE_IDS = {"write": 4, "maintain": 2, "admin": 5}  # GitHub's RepositoryRole actor ids


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
  spec = Path(core.handoff_spec(args, st))
  approval = core.load_approval(st, spec)
  if not approval:
    raise core.HandoffError(f"{spec} has no approval record")
  problems = origin_problems(repo_root, base, approval)
  if problems:
    raise core.HandoffError(problems[0])
  handoff = core.Handoff(plan, st)
  core.require_frozen_units(handoff)
  state = handoff.state
  core.require_receipt(state)
  core.require_repo(handoff)
  builder = builder_login(config, os.environ.get(token_env))
  problems = protection_problems(config["repo"], base, builder, handoff.branch(handoff.graph.order[0]))
  if problems:
    raise core.HandoffError(problems[0])
  core.card_add(st, args.runcard, "builder", {"login": builder, "token_env": token_env})
  summary, _ = core.status_pass(handoff, save=False)
  label = urllib.parse.quote(config["labels"]["stopped"], safe="")
  stopped_numbers = {issue["number"] for issue in core.gh_pages(f"repos/{config['repo']}/issues?labels={label}&state=all&per_page=100")}
  stopped = {uid for uid, record in state["units"].items() if record.get("number") in stopped_numbers}
  idle = set(filter(None, args.idle.split(",")))
  views = {uid: {**summary["units"][uid], "launched": state["units"][uid].get("launched"), "stopped": uid in stopped}
           for uid in handoff.graph.order}
  flying = [uid for uid in handoff.graph.order if in_flight(st, uid, views[uid], idle)]
  marked = [uid for uid in summary["ready"] if uid not in stopped][:max(0, config["max_in_flight"] - len(flying))]
  for uid in marked:
    state["units"].setdefault(uid, {})["launched"] = {"at": core.now_iso(), "runcard": args.runcard}
    core.journal(st, f"{uid} marked for launch")
  core.save_state(handoff.artifact_dir, state)
  print("in flight: " + (", ".join(flying) or "none"))
  print("marked: " + (", ".join(marked) or "none"))
  return 0


def in_flight(store, uid, view, idle):
  """True from the unit's mark (the mark reserves the slot) until its latest round is posted
  `clean`, it has landed, it carries the stopped label, or this invocation names it idle."""
  if not view.get("launched") or view.get("landed") or view.get("stopped") or uid in idle:
    return False
  latest = max(core.load_foreman(store, uid)["rounds"], key=lambda r: r.get("round") or 0, default={})
  return not (latest.get("phase") == "posted" and latest.get("outcome") == "clean")


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


def origin_problems(repo_root, base, approval):
  """What `refs/superegm/base` (origin/<base>, just fetched) lacks for a launch (spec section 11)."""
  ref, problems = "refs/superegm/base", []
  rel = Path(approval["path"]).resolve().relative_to(repo_root.resolve()).as_posix()
  blob = subprocess.run(["git", "cat-file", "-p", f"{ref}:{rel}"], cwd=str(repo_root), capture_output=True).stdout
  if hashlib.sha256(blob).hexdigest() != approval["sha256"]:
    problems.append(f"spec at origin/{base} is not the approved bytes")
  if subprocess.run(["git", "cat-file", "-e", f"{ref}:.superegm/config.json"], cwd=str(repo_root), capture_output=True).returncode:
    problems.append(f".superegm/config.json is absent at origin/{base}")
  names = core.run_git(["ls-tree", "--name-only", f"{ref}:.github/workflows"], repo_root, check=False).split()
  texts = [core.run_git(["cat-file", "-p", f"{ref}:.github/workflows/{name}"], repo_root, check=False) for name in names]
  if not any(re.search(r"\bpull_request\b", text) for text in texts):
    problems.append(f"origin/{base} carries no workflow triggered on pull_request")
  return problems


def protection_problems(repo, base, builder_login, branch):
  """What the repository's protection lacks (spec section 11): updates to <base> restricted to the
  owner with no bypass for the builder's role, in classic or ruleset form, and a ruleset that
  forbids force-push and deletion on the unit branches."""
  problems = []
  role = (core.gh_json(["api", f"repos/{repo}/collaborators/{builder_login}/permission"]) or {}).get("role_name")
  try:
    classic = core.gh_json(["api", f"repos/{repo}/branches/{base}/protection"]) or {}
  except core.GhError:  # 404: not protected in classic form
    classic = {}
  restrictions = classic.get("restrictions") or {}
  users = [u.get("login") for u in restrictions.get("users") or []]
  if not (users and builder_login not in users and not restrictions.get("teams") and not restrictions.get("apps")):
    problem = f"base branch {base}: updates are not restricted to the owner (no classic restrictions, no active ruleset update rule)"
    for summary in core.gh_pages(f"repos/{repo}/rulesets"):
      ruleset = core.gh_json(["api", f"repos/{repo}/rulesets/{summary['id']}"]) or {}
      include = ((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include") or []
      if ruleset.get("enforcement") != "active" or ruleset.get("target") != "branch" \
          or not {f"refs/heads/{base}", "~DEFAULT_BRANCH"} & set(include) \
          or not any(rule.get("type") == "update" for rule in ruleset.get("rules") or []):
        continue
      bypass = [a for a in ruleset.get("bypass_actors") or [] if a.get("actor_type") == "Team"
                or (a.get("actor_type") == "RepositoryRole" and a.get("actor_id") == ROLE_IDS.get(role))]
      if not bypass:
        problem = None
        break
      problem = f"base branch {base}: ruleset {ruleset.get('name')} lets " + (
          "a team bypass" if bypass[0]["actor_type"] == "Team" else f"the builder's role ({role}) bypass")
    if problem:
      problems.append(problem)
  rules = {rule.get("type") for rule in core.gh_json(["api", f"repos/{repo}/rules/branches/{urllib.parse.quote(branch, safe='')}"]) or []}
  if "non_fast_forward" not in rules:
    problems.append("superegm/**: no active ruleset forbids force-push (non_fast_forward)")
  if "deletion" not in rules:
    problems.append("superegm/**: no active ruleset forbids deletion")
  return problems
