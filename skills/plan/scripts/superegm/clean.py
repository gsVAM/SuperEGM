# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the clean subcommand (spec section 11).

"""superegm clean: remove a unit's review and builder worktrees and its private refs once every
launch and round is terminal; keeps what it cannot prove."""

from pathlib import Path

import superegm as core
from superegm.launch import load_launches, terminal

WRITES = frozenset()  # the store kinds this subcommand writes
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SKILLS = frozenset(["clean"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "clean", "remove a unit's worktrees and private refs once every launch and round is terminal")
  p.add_argument("--unit", required=True)
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  try:
    return clean(args)
  except core.HandoffError as error:
    raise core.HandoffError(f"clean: {error}") from None


def clean(args):
  root = core.git_toplevel(Path.cwd())
  st, unit = core.store(root), args.unit
  problems = terminal_problems(st, unit)
  if problems:
    raise core.HandoffError(problems[0])
  for tree in sorted(p for p in st.path("review", unit, "pr0").parent.glob("pr*") if p.is_dir()):
    core.remove_worktree(root, tree)  # EGM's dirty refusal: a person's edits in a review worktree are never discarded
    for ref in (f"refs/superegm/pr/{tree.name[2:]}", f"refs/superegm/pr-base/{tree.name[2:]}"):
      core.run_git(["update-ref", "-d", ref], root, check=False)
  recorded = {Path(entry["worktree"]).resolve() for entry in load_launches(st, unit)}
  for tree in sorted(p for p in st.path("worktrees", unit).glob("r*") if p.is_dir()):
    if tree.resolve() in recorded:
      core.run_git(["worktree", "remove", "--force", str(tree)], root)
    else:
      print(f"kept {tree}: no launch records it")
  core.run_git(["worktree", "prune"], root, check=False)
  core.journal(st, f"{unit} cleaned")
  print(f"{unit} cleaned")
  return 0


def terminal_problems(store, unit):
  """Every launch without its exit file or `interrupted`, every round not `posted` nor
  `collected` with a `not run` outcome (spec section 4)."""
  problems = [f"{unit} launch {entry['round']} is not terminal" for entry in load_launches(store, unit) if not terminal(entry)]
  for entry in core.load_foreman(store, unit)["rounds"]:
    if not (entry.get("phase") == "posted" or (entry.get("phase") == "collected" and str(entry.get("outcome") or "").startswith("not run"))):
      problems.append(f"{unit} round {entry.get('round')} is not terminal ({entry.get('phase')})")
  return problems
