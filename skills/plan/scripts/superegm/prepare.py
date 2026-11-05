# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# From the elephant-goldfish-model (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_prepare` as the prepare module, keyed by the dispatch id; the fetched tip is the round's head; `pr_body.md` and `comments.md` beside the diff and the CI file.

"""superegm prepare: fetch the PR into refs/superegm, add the review worktree, write the diff, CI, PR body and comments."""

import json
import os
import re
import subprocess
from pathlib import Path

import superegm as core
from superegm import review

WRITES = frozenset(['foreman', 'review'])  # the store kinds this subcommand writes
SKILLS = frozenset(['wave'])  # the skills whose card this subcommand accepts
AGED = ("**Deviation", "**Decision D", "**Ruling:**")  # the comment kinds kept regardless of age (section 11)
HEADER_RE = re.compile(r"^### (issue|pr) #(\d+) comment (\d+) by (\S+) at (\S+)$")  # comments.md's entry header


def register(subparsers):
  p = core.add_parser(subparsers, "prepare", "fetch the PR into refs/superegm, add the review worktree, write the diff, CI, PR body and comments")
  p.add_argument("--unit", required=True)
  p.add_argument("--dispatch", required=True, help="the dispatch id `foreman dispatch` printed")
  p.add_argument("--clean", action="store_true", help="at landing only: remove the round's worktree and its refs")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  try:
    return prepare(args, core.require_runcard(args, SKILLS))
  except review.Refusal as refusal:
    print(refusal)
    return 1


def prepare(args, card):
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  core.require_frozen_units(handoff)
  state, config, unit = handoff.state, handoff.config, args.unit
  root, repo, base = handoff.repo_root, config["repo"], config["base"]
  remote = state.get("remote") or config["remote"]
  data = core.load_foreman(st, unit)
  entry = review.require_dispatch(unit, data, args.dispatch)
  record = (state.get("units") or {}).get(unit) or {}
  number = (record.get("pr") or {}).get("number")
  if not number:
    raise core.HandoffError(f"{unit} has no watched PR: run `status` first")
  folder = st.path("review", unit, f"pr{number}")
  tree = folder / "worktree"
  if args.clean:
    if tree.exists():
      core.remove_worktree(root, tree)
    for ref in (f"refs/superegm/pr/{number}", f"refs/superegm/pr-base/{number}"):
      subprocess.run(["git", "-C", str(root), "update-ref", "-d", ref], capture_output=True)
    core.run_git(["worktree", "prune"], root, check=False)
    entry["phase"] = "cleaned"
    core.save_foreman(st, unit, data)
    print(f"cleaned {tree}")
    return 0
  pr = core.gh_json(["pr", "view", str(number), "-R", repo, "--json", "number,headRefOid,baseRefName,body"])
  require_base(pr, base)
  url = core.run_git(["remote", "get-url", remote], root)
  if (core.parse_remote_url(url) or "").lower() != repo.lower():
    raise core.HandoffError(f"remote {remote} no longer names {repo} ({url.strip()}): refusing to fetch")
  core.run_git(["fetch", "--no-write-fetch-head", remote, f"+refs/pull/{number}/head:refs/superegm/pr/{number}",
                f"+refs/heads/{base}:refs/superegm/pr-base/{number}"], root)
  head = core.run_git(["rev-parse", f"refs/superegm/pr/{number}"], root).strip()
  merge_base = core.run_git(["merge-base", f"refs/superegm/pr-base/{number}", f"refs/superegm/pr/{number}"], root).strip()
  if tree.exists():
    if tree.resolve() not in core.registered_worktrees(root):
      raise core.HandoffError(f"{tree} exists but is not a registered worktree: remove it by hand")
    core.remove_worktree(root, tree)  # refuses a dirty one
  tree.parent.mkdir(parents=True, exist_ok=True)
  core.run_git(["worktree", "add", "--detach", str(tree), head], root)
  n = entry["round"]
  r = folder / f"r{n}"
  diff = subprocess.run(["git", "-C", str(tree), "diff", "--no-ext-diff", "--no-textconv", "--binary", merge_base, "--"],
                        capture_output=True, check=True).stdout
  core.atomic_write(r / "diff", diff)
  ci = core.read_ci(repo, head)
  ci["verdict"] = core.ci_verdict(ci)
  core.atomic_write(r / "ci.json", json.dumps(ci, indent=2) + "\n")
  core.atomic_write(r / "pr_body.md", pr.get("body") or "")
  env = config["builder"]["gh_token_env"]
  login = core.gh(["api", "user", "-q", ".login"], token=os.environ.get(env) if env else None).strip()
  issue = record["number"]
  since = max((e["posted_at"] for e in data["rounds"] if e.get("posted_at")), default=None)
  write_comments(r / "comments.md", (issue, core.gh_pages(f"repos/{repo}/issues/{issue}/comments")),
                 (number, core.gh_pages(f"repos/{repo}/issues/{number}/comments")), since, login)
  entry.update({"head": head, "phase": "prepared", "merge_base": merge_base, "worktree": str(tree)})
  core.save_foreman(st, unit, data)
  previous = max((e["round"] for e in data["rounds"] if e.get("phase") == "posted"), default=None)
  core.journal(st, f"{unit} round {n} prepared head {head[:7]} under {args.runcard}")
  print(f"prepared: head {head[:7]} merge-base {merge_base[:7]} {ci['verdict']} previous {previous or '-'}")
  return 0


def require_base(pr: dict, base: str) -> None:
  """A PR not targeting `<base>` is refused before any fetch (spec section 11)."""
  if pr.get("baseRefName") != base:
    raise review.Refusal(f"base: PR #{pr['number']} targets {pr.get('baseRefName')}, not {base}")


def write_comments(path: Path, issue: tuple, pr: tuple, since, login: str) -> None:
  """Line 1 `builder: <login>`, then each comment of `(number, comments)` created after `since` (the latest
  `posted_at`; None keeps everything) or of an aged kind (`**Deviation`, `**Decision D`, `**Ruling:**`): its
  header line, the body and a blank line."""
  lines = [f"builder: {login}"]
  for kind, (number, comments) in (("issue", issue), ("pr", pr)):
    for comment in comments:
      if since and comment["created_at"] <= since and not comment["body"].startswith(AGED):
        continue
      # a body line shaped like a header is indented: a builder's comment never forges another entry
      body = "\n".join(" " + l if HEADER_RE.match(l) else l for l in comment["body"].splitlines())
      lines += [f"### {kind} #{number} comment {comment['id']} by {comment['user']['login']} at {comment['created_at']}",
                body, ""]
  core.atomic_write(path, "\n".join(lines) + "\n")
