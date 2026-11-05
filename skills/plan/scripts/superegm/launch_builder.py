# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the launch-builder subcommand (spec section 11); the prompt's # Orient section from orient (spec section 9.3); the PR block read from the launch's ref and the profile's hooks check (U14).

"""superegm launch-builder: a fresh worktree, the prompt file and the command line of one builder launch."""

import json
import os
import re
import subprocess
from pathlib import Path

import superegm as core
from superegm import body, orient
from superegm.launch import builder_login, load_launches, terminal

WRITES = frozenset(["launches", "orient_unit"])  # the store kinds this subcommand writes
SKILLS = frozenset(["wave"])  # the skills whose card this subcommand accepts
PROMPT_COMMENT_RE = re.compile(r"^\*\*(Deviation \([a-z]+\)|Decision D\d+|Ruling):\*\*")
# The PR body's DoD-results form (the orders): `### DoD <n>` then one fenced block per item.
DOD_RESULT_RE = re.compile(r"^### DoD (\d+)\n```[^\n]*\n(.*?)\n```", re.M | re.S)
ORDERS = Path(__file__).resolve().parents[4] / "skills/wave/references/builder_orders.md"
# The PR body's line 2 (owner ruling 2026-11-04): the login of the session that ran `launch`, no `@`, so it mentions nobody.
AUDIT_LINE = "Launched by {owner} · run card {runcard} · unit {unit} · handoff {handoff}"


def register(subparsers):
  p = core.add_parser(subparsers, "launch-builder", "a fresh worktree, the prompt file and the command line of one builder launch")
  p.add_argument("--unit", required=True)
  p.add_argument("--round", type=int, required=True, help="the launch count")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  try:
    return prepare(args, card)
  except core.HandoffError as error:
    raise core.HandoffError(f"launch-builder: {error}") from None


def prepare(args, card):
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  state, config, unit, rnd = handoff.state, handoff.config, args.unit, args.round
  repo, builder_config = config["repo"], config["builder"]
  builder = builder_login(config, os.environ.get(builder_config["gh_token_env"]))
  problem = refusal(st, state, config, unit, rnd, builder)
  if problem:
    raise core.HandoffError(problem)
  record = state["units"][unit]
  branch, number = handoff.branch(unit), record["number"]
  issue_body = filed_body(state, unit)
  tools = allowed_tools(builder_config["allowed_tools"], branch, issue_body)
  pr = (record.get("pr") or {}).get("number") if rnd >= 2 else None
  ref = "refs/superegm/base"  # the launch's ref: origin/<base> as `launch` fetched it, the PR tip from round 2
  if pr:
    ref = f"refs/superegm/pr/{pr}"
    core.run_git(["fetch", "--no-write-fetch-head", st.config["remote"], f"+refs/pull/{pr}/head:{ref}"], handoff.repo_root)
  pr_block = pr_block_text(handoff.repo_root, ref, config["pr_block_file"]) if config["pr_block_file"] else None
  # The launch's tree, before any worktree: an orient refusal is an ordinary precondition.
  orient_text = core.read_text(orient.orient_unit(st, handoff.repo_root, ref, unit))
  comments = core.gh_pages(f"repos/{repo}/issues/{number}/comments")
  reviews = core.gh_pages(f"repos/{repo}/pulls/{pr}/reviews") if pr else []
  audit = AUDIT_LINE.format(owner=record["launched"]["by"], runcard=args.runcard, unit=unit, handoff=st.handoff_id)
  text = prompt_text(number, unit, issue_body, core.read_text(ORDERS), orient_text, comments, reviews, pr, builder, audit, pr_block)
  worktree = add_worktree(handoff.repo_root, st, unit, rnd, branch, pr)
  prompt = st.path("launches", f"{unit}_r{rnd}_prompt.md")
  core.atomic_write(prompt, text)
  core.journal(st, f"{unit} launch {rnd} prepared")
  print(command_line(config, worktree, prompt, st.path("launches", f"{unit}_r{rnd}_result.json"), args.runcard, tools))
  return 0


def refusal(store, state, config, unit, rnd, builder):
  """The first precondition of spec section 11 this launch fails, or None; evaluated before any
  git or file write."""
  record = (state.get("units") or {}).get(unit) or {}
  if not record.get("launched"):
    return f"{unit} is not marked by launch"
  launches = load_launches(store, unit)
  for entry in launches:
    if not terminal(entry):
      return f"{unit} launch {entry['round']} is not terminal"
  if rnd != len(launches) + 1:
    return f"--round {rnd} is not the next launch count ({len(launches) + 1})"
  problem = profile_problem(Path(config["builder"]["profile_dir"]).expanduser())
  if problem:
    return problem
  issue = core.gh_json(["api", f"repos/{config['repo']}/issues/{record['number']}"]) or {}
  if body.normalise(filed_body(state, unit)) != body.normalise(issue.get("body") or ""):
    return f"issue #{record['number']} body differs from the filed body"
  if rnd >= 2 and not (record.get("pr") or {}).get("number"):
    return f"{unit} round {rnd} has no recorded PR: run status first"
  return None


def profile_problem(profile_dir):
  """Spec sections 4 and 11: the builder profile exists, holds no CLAUDE.md, no plugins and no hooks
  (a `settings.json` with a `hooks` key)."""
  plugins, settings = profile_dir / "plugins", profile_dir / "settings.json"
  if not profile_dir.is_dir():
    return f"builder profile {profile_dir} does not exist"
  if (profile_dir / "CLAUDE.md").exists():
    return f"builder profile {profile_dir} holds CLAUDE.md"
  if plugins.is_dir() and any(plugins.iterdir()):
    return f"builder profile {profile_dir} holds plugins"
  if settings.is_file():
    try:
      data = json.loads(settings.read_text(encoding="utf-8"))
    except ValueError:  # not JSON: no hooks key to find
      data = None
    if isinstance(data, dict) and "hooks" in data:
      return f"builder profile {profile_dir} holds hooks"
  return None


def pr_block_text(repo_root, ref, path):
  """`config.pr_block_file`'s bytes at the launch's ref, verbatim (spec section 11); absent, the launch is refused."""
  result = subprocess.run(["git", "cat-file", "-p", f"{ref}:{path}"], cwd=str(repo_root), capture_output=True)
  if result.returncode:
    raise core.HandoffError(f"pr_block_file {path} is absent at {ref}")
  return result.stdout.decode("utf-8")


def allowed_tools(configured, branch, body_text):
  """The configured allow-list plus a push prefix for the unit's own branch and `Bash(<first
  word>:*)` for every command the body runs; `Agent`, `Skill` and unrestricted Bash are refused."""
  for entry in ("Agent", "Skill", "Bash", "Bash(*)"):
    if entry in configured:
      raise core.HandoffError(f"allowed_tools carries {entry}: a builder never spawns, never invokes skills, never runs unrestricted Bash")
  tools = list(configured) + [f"Bash(git push origin {branch}:*)"]
  for command in body.run_commands(body_text):
    if f"Bash({command.split()[0]}:*)" not in tools:
      tools.append(f"Bash({command.split()[0]}:*)")
  return tools


def filed_body(state, unit):
  """The body the filing that created the unit's issue stores, with its numbers filled (spec section 7)."""
  filed = next(w[4] for f in state.get("filings") or [] for w in f["writes"] if w[0] == "issue" and w[1] == unit)
  numbers = {uid: r["number"] for uid, r in state["units"].items() if r.get("number")}
  return body.fill_numbers(filed, numbers, (state.get("tracking") or {}).get("number"))


def prompt_text(issue_number, unit, body, orders, orient, comments, reviews, pr, builder, audit, pr_block=None):
  """Exactly what spec section 3's anti-goal 3 allows: the issue body, the audit-trail line, the orders, the repository's
  PR block when `pr_block_file` is set, the unit's orient file, every Deviation comment, every
  Decision and Ruling comment not by the builder account, and from round 2 the foreman's reviews on the PR."""
  kept = [c for c in comments if PROMPT_COMMENT_RE.match(c["body"])
          and (c["body"].startswith("**Deviation") or c["user"]["login"] != builder)]
  parts = [f"# Issue #{issue_number} — {unit}\n\n{body}", f"# Audit trail\n\n{audit}", f"# Builder orders\n\n{orders}"]
  if pr_block is not None:
    parts.append(f"# PR block\n\n{pr_block}")
  parts.append(f"# Orient\n\n{orient}")
  parts.append(f"# Comments on issue #{issue_number}\n\n" + "\n".join(f"## {c['user']['login']} · comment {c['id']}\n{c['body']}\n" for c in kept))
  if pr:
    kept = [r for r in reviews if r.get("body") and r["user"]["login"] != builder]
    parts.append(f"# Review comments on PR #{pr}\n\n" + "\n".join(
        f"## {r['user']['login']} · review {r['id']} on {r['commit_id'][:7]}\n{r['body']}\n" for r in kept))
  return "\n\n---\n\n".join(parts)


def add_worktree(repo_root, store, unit, rnd, branch, pr):
  """A fresh worktree for the launch on the unit's branch: round 1 from `refs/superegm/base`,
  later rounds at the PR tip (`refs/superegm/pr/<n>`, fetched by `prepare`) after detaching the
  earlier launches' worktrees (nothing in them is removed; that is `clean`'s)."""
  path = store.path("worktrees", unit, f"r{rnd}")
  path.parent.mkdir(parents=True, exist_ok=True)
  if rnd == 1:
    core.run_git(["worktree", "add", "-b", branch, str(path), "refs/superegm/base"], repo_root)
    return path
  for earlier in core.registered_worktrees(repo_root):
    if earlier.is_relative_to(path.parent.resolve()) and earlier.is_dir():
      core.run_git(["switch", "--detach"], earlier)
  core.run_git(["worktree", "prune"], repo_root, check=False)
  core.run_git(["branch", "-f", branch, f"refs/superegm/pr/{pr}"], repo_root)
  core.run_git(["worktree", "add", str(path), branch], repo_root)
  return path


def command_line(config, worktree, prompt, result, runcard, tools):
  """The launched command (spec section 11): the builder profile, the token as the shell variable
  `GH_TOKEN` expands (never its value), gh as git's credential helper with pushes rewritten to
  HTTPS, the role and card, `claude -p` on the prompt file, the result and exit files."""
  b = config["builder"]
  for value in (worktree, prompt, result, b["profile_dir"], b["model"], b["permission_mode"], runcard, *tools):
    if "'" in str(value):
      raise core.HandoffError(f"{value} holds a quote and cannot go on the command line")
  return (f"cd '{worktree}' && env CLAUDE_CONFIG_DIR='{b['profile_dir']}' GH_TOKEN=\"${b['gh_token_env']}\" "
          f"SUPEREGM_ROLE=builder SUPEREGM_RUNCARD='{runcard}' GIT_CONFIG_COUNT=3 "
          "GIT_CONFIG_KEY_0=credential.https://github.com.helper GIT_CONFIG_VALUE_0='!gh auth git-credential' "
          "GIT_CONFIG_KEY_1=url.https://github.com/.pushInsteadOf GIT_CONFIG_VALUE_1=git@github.com: "
          "GIT_CONFIG_KEY_2=url.https://github.com/.pushInsteadOf GIT_CONFIG_VALUE_2=ssh://git@github.com/ "
          f"claude -p \"$(cat '{prompt}')\" --model '{b['model']}' --permission-mode '{b['permission_mode']}' "
          f"--allowedTools '{','.join(tools)}' --output-format json > '{result}'; echo $? > '{result}.exit'")
