# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the doctor subcommand (spec section 11); the App lines and the launched environment (U15).

"""superegm doctor: one line per wave prerequisite, `ok` or the refusal `launch` or `launch-builder`
would give; read-only, no run card."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import superegm as core
from superegm.builder_token import app_lines, key_path, tool
from superegm.launch import app_login, builder_login, origin_problems, protection_problems
from superegm.launch_builder import SENTINEL, UNSET, launched_pairs, profile_problem

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
  return 0 if all(text.startswith("ok") for name, text in lines if name not in ("graphify", "scanning")) else 1


def checks(config, repo_root, token):
  """The lines after `config`: `launch`'s and `launch-builder`'s own predicates, each line `ok…` or the
  refusal they would give (a check's HandoffError or GhError text is its line). On the machine-account
  path the order is owner, origin, token, builder, role, scopes, protection, profile, gh, environment,
  graphify; the builder, role, scopes and protection lines need the token and are absent without it.
  On the App path: owner, origin, credential, key, openssl, artifacts_dir, app, permissions, token,
  installation, scanning, protection, profile, gh, environment, graphify; the four App lines are absent
  after a failing key or openssl. The environment line is absent after a failing gh line; graphify and
  scanning are informational and never fail."""
  repo, base, owners, team, app = config["repo"], config["base"], config["owners"], config["owner_team"], config["builder"]["app"]
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
    problems = protection_problems(repo, base, app_login(config) or token_login(), "superegm/x/U01", owners, team,
                                   app_id=app["app_id"] if app else None)
    return problems[0] if problems else "ok"

  def credential():
    builder_login(config, token)  # the both-set refusal
    return f"ok (app {app['slug']})"

  def key():
    found["key"] = key_path(app["private_key_env"])
    return f"ok ({found['key']})"

  def openssl():
    found["openssl"] = tool("openssl")
    return f"ok ({found['openssl']})"

  def artifacts_dir():
    return f"artifacts_dir {config['artifacts_dir']} holds whitespace" if re.search(r"\s", config["artifacts_dir"]) else "ok"

  def scanning():
    data = (core.gh_json(["api", f"repos/{repo}"]) or {}).get("security_and_analysis")
    if not data:
      return "not reported (informational)"
    status = lambda field: (data.get(field) or {}).get("status") or "not reported"
    return f"push protection {status('secret_scanning_push_protection')}, non-provider patterns {status('secret_scanning_non_provider_patterns')}"

  def gh():
    found["gh"] = tool("gh")
    return f"ok ({found['gh']})"

  check("owner", owner)
  check("origin", origin)
  if app:
    for name, fn in (("credential", credential), ("key", key), ("openssl", openssl), ("artifacts_dir", artifacts_dir)):
      check(name, fn)
    if "key" in found and "openssl" in found:
      lines += app_lines(app, repo, found["key"], found["openssl"])
    check("scanning", scanning)
    check("protection", protection)
  elif not token:
    lines.append(("token", f"{config['builder']['gh_token_env']} is not set"))
  else:
    lines.append(("token", "ok"))
    for name, fn in (("builder", builder), ("role", role), ("scopes", scopes), ("protection", protection)):
      check(name, fn)
  check("profile", lambda: profile_problem(Path(config["builder"]["profile_dir"]).expanduser()) or "ok")
  check("gh", gh)
  if "gh" in found:
    check("environment", lambda: environment_problem(repo_root, found["gh"], bool(app)) or "ok")
  graphify = shutil.which("graphify")
  lines.append(("graphify", f"ok ({graphify})" if graphify else "not on PATH (informational)"))
  return lines


def environment_problem(repo_root: Path, gh: str, app: bool):
  """What the launched environment (spec section 11: the process environment minus `UNSET` plus
  `launched_pairs`, and the sentinel `GH_TOKEN` on the App path) would let through, or None: on the
  App path `<gh> auth token` prints the sentinel; `git credential fill` with the helper's slot replaced by
  `!false` answers nothing (the owner's askpass, global helper and keyring are shut out); origin's push
  URL is HTTPS (an SSH `pushInsteadOf` of the owner's is shut out)."""
  env = {k: v for k, v in os.environ.items() if k not in UNSET}
  env.update(launched_pairs(gh, "superegm", "superegm"))
  if app:
    env["GH_TOKEN"] = SENTINEL
    printed = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, env=env).stdout.strip()
    if printed != SENTINEL:
      return f"gh auth token under the launched environment prints {printed}, not {SENTINEL}"
  helper = f"!{gh} auth git-credential"
  fill = subprocess.run(["git", "credential", "fill"], input="url=https://github.com\n\n", capture_output=True, text=True,
                        cwd=str(repo_root), env={k: "!false" if v == helper else v for k, v in env.items()})
  if fill.returncode == 0:
    return "git credential fill under the launched environment answered"
  url = subprocess.run(["git", "remote", "get-url", "--push", "origin"], capture_output=True, text=True,
                       cwd=str(repo_root), env=env).stdout.strip()
  if not url.startswith("https://"):
    return f"push URL of origin under the launched environment is {url}, not https://"
  return None
