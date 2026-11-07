# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_launch` as the launch module; it marks the ready units up to `max_in_flight` after the protection checks of spec section 11, the owners set and the team bypass included; the builder as a GitHub App (U15); a unit whose `clean` outcome an ingest rewrote is ready again (U21).

"""superegm launch: check what the launch needs, then mark the ready units up to `max_in_flight`."""

import hashlib
import json
import os
import re
import subprocess
import urllib.parse
from pathlib import Path

import superegm as core
from superegm.builder_token import app_lines, key_path, tool

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
  entries = core.load_approvals(st, spec)
  own = [i for i, e in enumerate(entries) if e.get("handoff_id") == st.handoff_id] or ([len(entries) - 1] if entries else [])
  if not own:
    raise core.HandoffError(f"{spec} has no approval record")
  # the handoff's own entry (the last carrying its id) and the later links of the chain (spec section 7)
  problems = origin_problems(repo_root, base, {**entries[own[-1]], "path": str(spec)}, entries[own[-1] + 1:])
  if problems:
    raise core.HandoffError(problems[0])
  handoff = core.Handoff(plan, st)
  core.require_frozen_units(handoff)
  state = handoff.state
  core.require_receipt(state)
  core.require_repo(handoff)
  builder, app = builder_login(config, os.environ.get(token_env)), config["builder"]["app"]
  if app:  # the App's reads that can change under a wave (spec section 11), repeated at every launch
    openssl = tool("openssl")
    key = key_path(app["private_key_env"])
    for name, text in app_lines(app, config["repo"], key, openssl):
      if not text.startswith("ok"):
        raise core.HandoffError(f"{name}: {text}")
  problems = protection_problems(config["repo"], base, builder, handoff.branch(handoff.graph.order[0]), config["owners"], config["owner_team"],
                                 app_id=app["app_id"] if app else None)
  if problems:
    raise core.HandoffError(problems[0])
  core.card_add(st, args.runcard, "builder", {"login": builder, "email": builder_email(builder), "token_env": None if app else token_env,
                                              "app_id": app["app_id"] if app else None})
  me = core.gh(["api", "user", "-q", ".login"]).strip()  # this session's login: the PR body's audit-trail line (spec section 11)
  summary, _ = core.status_pass(handoff, save=False)
  label = urllib.parse.quote(config["labels"]["stopped"], safe="")
  stopped_numbers = {issue["number"] for issue in core.gh_pages(f"repos/{config['repo']}/issues?labels={label}&state=all&per_page=100")}
  stopped = {uid for uid, record in state["units"].items() if record.get("number") in stopped_numbers}
  idle = set(filter(None, args.idle.split(",")))
  views = {uid: {**summary["units"][uid], "launched": state["units"][uid].get("launched"), "stopped": uid in stopped}
           for uid in handoff.graph.order}
  flying = [uid for uid in handoff.graph.order if in_flight(st, uid, views[uid], idle)]
  again = {uid for uid in handoff.graph.order if uid not in stopped and uid not in idle and not views[uid].get("landed")
           and ready_again(core.load_foreman(st, uid), load_launches(st, uid))}
  ready = set(summary["ready"]) | again  # a unit an ingest returned to `revise` waits for a slot as a ready unit does
  marked = [uid for uid in handoff.graph.order if uid in ready and uid not in stopped][:max(0, config["max_in_flight"] - len(flying))]
  for uid in marked:
    state["units"].setdefault(uid, {})["launched"] = {"at": core.now_iso(), "runcard": args.runcard, "by": me}
    core.journal(st, f"{uid} marked for launch")
  core.save_state(handoff.artifact_dir, state)
  print("in flight: " + (", ".join(flying) or "none"))
  print("marked: " + (", ".join(marked) or "none"))
  return 0


def in_flight(store, uid, view, idle):
  """True from the unit's mark (the mark reserves the slot) until its latest round is posted
  `clean`, it has landed, it carries the stopped label, or this invocation names it idle; a
  launch recorded after the clean round holds the slot again. A unit whose `clean` an ingest rewrote
  (`ready_again`) holds no slot until its relaunch records a launch."""
  if not view.get("launched") or view.get("landed") or view.get("stopped") or uid in idle:
    return False
  foreman, launches = core.load_foreman(store, uid), load_launches(store, uid)
  return not latest_clean(foreman, launches) and not ready_again(foreman, launches)


def ready_again(foreman: dict, launches: list) -> bool:
  """The latest round's `clean` outcome an ingest rewrote `revise` (spec section 8, External review) and no
  launch recorded after it: the unit is ready again, not in flight, until its relaunch records one."""
  latest = max(foreman.get("rounds") or [], key=lambda r: r.get("round") or 0, default={})
  return (latest.get("phase") == "posted" and latest.get("outcome") == "revise" and latest.get("rewritten_from") == "clean"
          and not (launches and launches[-1]["round"] > (latest.get("launch") or 0)))


def latest_clean(foreman: dict, launches: list) -> bool:
  """The latest round is posted `clean` and no launch was recorded after it: a verdict names its
  launch (spec section 11's predicate), so a later launch is a builder the round never saw."""
  latest = max(foreman.get("rounds") or [], key=lambda r: r.get("round") or 0, default={})
  return (latest.get("phase") == "posted" and latest.get("outcome") == "clean"
          and not (launches and launches[-1]["round"] > (latest.get("launch") or 0)))


def load_launches(store, unit):
  """`launches/<unit>.json`'s `launches[]` (spec section 7); [] before the first record."""
  path = store.path("launches", unit)
  return json.loads(core.read_text(path))["launches"] if path.is_file() else []


def terminal(entry):
  """Spec section 4: a launch is terminal only with its exit file or the owner's typed `interrupted`."""
  return entry.get("status") == "interrupted" or Path(entry["result_file"] + ".exit").is_file()


def app_login(config):
  """`<slug>[bot]`, the builder's login on the App path (derived from the config, no token), or None."""
  app = config["builder"]["app"]
  return f"{app['slug']}[bot]" if app else None


def builder_email(login: str) -> str:
  """The commit identity's address, `<id>+<login>@users.noreply.github.com`, the id a public read."""
  return f"{core.gh(['api', f'users/{login}', '-q', '.id']).strip()}+{login}@users.noreply.github.com"


def builder_login(config, token_env_value):
  """The builder's login: `<slug>[bot]` from the config on the App path (refused when the machine
  account's variable is also set: one identity per repository), else the machine account's login
  under its token, refused when the token is unset or is the elephant's own."""
  env, app = config["builder"]["gh_token_env"], config["builder"]["app"]
  if app:
    if token_env_value:
      raise core.HandoffError(f"builder.app is set ({app['private_key_env']}) and {env} is also set: one identity per repository")
    return app_login(config)
  if not token_env_value:
    raise core.HandoffError(f"{env} is not set")
  builder = core.gh(["api", "user", "-q", ".login"], token=token_env_value).strip()
  me = core.gh(["api", "user", "-q", ".login"]).strip()
  if builder == me:
    raise core.HandoffError(f"the builder token is the elephant's own login ({me})")
  if builder in config["owners"]:
    raise core.HandoffError(f"the builder token's login ({builder}) is in config.owners")
  return builder


def origin_problems(repo_root, base, approval=None, later=()):
  """What `refs/superegm/base` (origin/<base>, just fetched) lacks for a launch (spec section 11): the
  spec at the approved bytes of `approval` (the handoff's own entry, its `path` the spec) or at a later
  link of the chain (`later`, the entries after it); without an approval (`doctor`) that line is skipped."""
  ref, problems = "refs/superegm/base", []
  if approval:
    rel = Path(approval["path"]).resolve().relative_to(repo_root.resolve()).as_posix()
    blob = subprocess.run(["git", "cat-file", "-p", f"{ref}:{rel}"], cwd=str(repo_root), capture_output=True).stdout
    if hashlib.sha256(blob).hexdigest() not in {approval["sha256"], *(e["sha256"] for e in later)}:
      problems.append(f"spec at origin/{base} is neither the approved bytes nor a later link of the approval chain")
  if subprocess.run(["git", "cat-file", "-e", f"{ref}:.superegm/config.json"], cwd=str(repo_root), capture_output=True).returncode:
    problems.append(f".superegm/config.json is absent at origin/{base}")
  names = core.run_git(["ls-tree", "--name-only", f"{ref}:.github/workflows"], repo_root, check=False).split()
  texts = [core.run_git(["cat-file", "-p", f"{ref}:.github/workflows/{name}"], repo_root, check=False) for name in names]
  if not any(re.search(r"\bpull_request\b", text) for text in texts):
    problems.append(f"origin/{base} carries no workflow triggered on pull_request")
  return problems


def protection_problems(repo, base, builder_login, branch, owners, owner_team=None, app_id=None):
  """What the repository's protection lacks (spec section 11): updates to <base> restricted to the
  owner (a classic restriction naming a non-empty subset of `owners`, or a ruleset whose bypass
  names neither the builder's role nor a team but `owner_team`, which the builder is outside),
  and a ruleset that forbids force-push and deletion on the unit branches. With `app_id` (the App path)
  the builder has no repository role: the App must be no bypass actor and no classic `apps` entry."""
  problems = [] if owners else ["config.owners is empty: set the owner logins in .superegm/config.json"]
  role = None if app_id else (core.gh_json(["api", f"repos/{repo}/collaborators/{builder_login}/permission"]) or {}).get("role_name")
  try:
    classic = core.gh_json(["api", f"repos/{repo}/branches/{base}/protection"]) or {}
  except core.GhError:  # 404: not protected in classic form
    classic = {}
  restrictions = classic.get("restrictions") or {}
  users = [u.get("login") for u in restrictions.get("users") or []]
  strangers = [u for u in users if u not in owners]
  apps = [a.get("slug") for a in restrictions.get("apps") or []]
  if not (users and not strangers and builder_login not in users and not restrictions.get("teams") and not apps):
    problem = f"base branch {base}: classic restriction lets {strangers[0]} push: not in config.owners" if strangers else \
        f"base branch {base}: classic restriction lets app {builder_login.removesuffix('[bot]')} push" if app_id and builder_login.removesuffix("[bot]") in apps else \
        f"base branch {base}: updates are not restricted to the owner (no classic restrictions, no active ruleset update rule)"
    for summary in core.gh_pages(f"repos/{repo}/rulesets"):
      ruleset = core.gh_json(["api", f"repos/{repo}/rulesets/{summary['id']}"]) or {}
      include = ((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include") or []
      if ruleset.get("enforcement") != "active" or ruleset.get("target") != "branch" \
          or not {f"refs/heads/{base}", "~DEFAULT_BRANCH"} & set(include) \
          or not any(rule.get("type") == "update" for rule in ruleset.get("rules") or []):
        continue
      offences = [o for o in (bypass_offence(a, role, base, ruleset.get("name"), builder_login, owner_team, app_id)
                              for a in ruleset.get("bypass_actors") or []) if o]
      if not offences:
        problem = None
        break
      problem = offences[0]
    if problem:
      problems.append(problem)
  rules = {rule.get("type") for rule in core.gh_json(["api", f"repos/{repo}/rules/branches/{urllib.parse.quote(branch, safe='')}"]) or []}
  if "non_fast_forward" not in rules:
    problems.append("superegm/**: no active ruleset forbids force-push (non_fast_forward)")
  if "deletion" not in rules:
    problems.append("superegm/**: no active ruleset forbids deletion")
  return problems


def bypass_offence(actor, role, base, name, builder_login, owner_team, app_id=None):
  """Why a ruleset's bypass actor fails spec section 11, or None: the builder's own repository role, the
  builder App itself, or a team that is not `config.owner_team`, that GitHub does not have, or that the
  builder belongs to."""
  kind, actor_id = actor.get("actor_type"), actor.get("actor_id")
  if kind == "RepositoryRole":
    return f"base branch {base}: ruleset {name} lets the builder's role ({role}) bypass" if role and actor_id == ROLE_IDS.get(role) else None
  if kind == "Integration":
    return f"base branch {base}: ruleset {name} lets the App (#{actor_id}) bypass" if app_id and actor_id == app_id else None
  if kind != "Team":
    return None
  if not owner_team:
    return f"base branch {base}: ruleset {name} lets team #{actor_id} bypass, not config.owner_team (unset)"
  org, slug = owner_team.split("/")
  try:
    team = core.gh_json(["api", f"orgs/{org}/teams/{slug}"]) or {}
  except core.GhError as error:
    if error.http_status != 404:
      raise
    return f"config.owner_team {owner_team} does not exist"
  if team.get("id") != actor_id:
    return f"base branch {base}: ruleset {name} lets team #{actor_id} bypass, not config.owner_team ({owner_team})"
  try:
    core.gh(["api", f"orgs/{org}/teams/{slug}/memberships/{builder_login}"])
  except core.GhError as error:
    if error.http_status != 404:
      raise
    return None
  return f"base branch {base}: ruleset {name} lets {owner_team} bypass, and {builder_login} is a member"
