# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the doctor subcommand (spec section 11).

"""superegm doctor: one line per wave prerequisite, `ok` or the refusal `launch` or `launch-builder`
would give; read-only, no run card."""

import os
import re
import shutil
from pathlib import Path

import superegm as core
from superegm.launch import builder_login, origin_problems, protection_problems
from superegm.launch_builder import profile_problem

WRITES = frozenset()  # doctor writes nothing


def register(subparsers):
  p = core.add_parser(subparsers, "doctor", "print every wave prerequisite as ok or the refusal launch would give",
                      runcard=False)
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  repo_root = core.git_toplevel(Path.cwd())
  try:
    config = core.load_config(repo_root)
  except core.HandoffError as error:
    print(f"config: {error}")
    return 1
  lines = [("config", "ok"), *checks(config, repo_root, os.environ.get(config["builder"]["gh_token_env"]))]
  for name, text in lines:
    print(f"{name}: {text}")
  return 0 if all(text.startswith("ok") for name, text in lines if name != "graphify") else 1


def checks(config, repo_root, token):
  """The lines after `config`, in the order owner, origin, token, builder, role, scopes, protection,
  profile, graphify: `launch`'s and `launch-builder`'s own predicates, each line `ok…` or the
  refusal they would give (a check's HandoffError or GhError text is its line); the builder, role,
  scopes and protection lines need the token and are absent without it; graphify never fails."""
  repo, base, owners, team = config["repo"], config["base"], config["owners"], config["owner_team"]
  lines, found = [], {}

  def check(name, fn):
    try:
      text = fn()
    except (core.HandoffError, core.GhError) as error:
      text = str(error)
    lines.append((name, text))

  def owner():
    me = core.gh(["api", "user", "-q", ".login"]).strip()
    return f"ok ({me})" if me in owners else f"{me} is not in config.owners ({', '.join(owners)})"

  def origin():
    core.run_git(["fetch", "--no-write-fetch-head", config["remote"], f"+refs/heads/{base}:refs/superegm/base"], repo_root)
    problems = origin_problems(repo_root, base)
    return problems[0] if problems else "ok"

  def builder():
    found["login"] = builder_login(config, token)
    return f"ok ({found['login']})"

  def token_login():
    if "login" not in found:  # the builder check refused: the token's own login, read once
      found["login"] = core.gh(["api", "user", "-q", ".login"], token=token).strip()
    return found["login"]

  def role():
    name = (core.gh_json(["api", f"repos/{repo}/collaborators/{token_login()}/permission"]) or {}).get("role_name")
    return "ok (write)" if name == "write" else f"{token_login()}'s role on {repo} is {name}, not write"

  def scopes():
    head = re.split(r"\r?\n\r?\n", core.gh(["api", "-i", "user"], token=token), 1)[0]
    match = re.search(r"(?im)^x-oauth-scopes:[ \t]*(.*?)[ \t\r]*$", head)
    if not match:
      return "ok (fine-grained: permissions not probed)"
    names = [s.strip() for s in match.group(1).split(",") if s.strip()]
    listed = ", ".join(names)
    if "repo" not in names:
      return f"classic token lacks repo ({listed})"
    if "workflow" in names:
      return f"classic token carries workflow ({listed})"
    return f"ok (classic: {listed})"

  def protection():
    problems = protection_problems(repo, base, token_login(), "superegm/x/U01", owners, team)
    return problems[0] if problems else "ok"

  check("owner", owner)
  check("origin", origin)
  if not token:
    lines.append(("token", f"{config['builder']['gh_token_env']} is not set"))
  else:
    lines.append(("token", "ok"))
    for name, fn in (("builder", builder), ("role", role), ("scopes", scopes), ("protection", protection)):
      check(name, fn)
  check("profile", lambda: profile_problem(Path(config["builder"]["profile_dir"]).expanduser()) or "ok")
  graphify = shutil.which("graphify")
  lines.append(("graphify", f"ok ({graphify})" if graphify else "not on PATH (informational)"))
  return lines
