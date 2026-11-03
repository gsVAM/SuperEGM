# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_prepare` as the prepare module.

"""superegm prepare: fetch the PR into refs/egm, add a worktree, write the diff and CI file."""

import json
import subprocess
from pathlib import Path

import superegm as core

WRITES = frozenset(['file', 'foreman'])  # the store kinds this subcommand writes
SKILLS = frozenset(['wave'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "prepare", "fetch the PR into refs/egm, add a worktree, write the diff and CI file")
  p.add_argument("--unit", required=True)
  p.add_argument("--round", type=int, default=1)
  p.add_argument("--wave", type=int, default=1)
  p.add_argument("--runner", help="write the inspect launch line for this runner path")
  p.add_argument("--model")
  p.add_argument("--effort")
  p.add_argument("--clean", action="store_true",
                 help="at landing only: remove the round's worktree, its refs, and prune")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  core.require_frozen_units(handoff)
  state = handoff.state
  root = Path(state.get("repo_root") or handoff.repo_root)
  remote, repo = state.get("remote") or handoff.config["remote"], handoff.config["repo"]
  record = state.get("units", {}).get(args.unit) or {}
  pr = record.get("pr")
  if not pr:
    raise core.HandoffError(f"{args.unit} has no watched PR: run `status` first")
  selected = (record.get("watch") or {}).get("number")
  if selected is not None and selected != pr["number"]:
    raise core.HandoffError(
        f"{args.unit} watches PR #{selected} but the recorded observation "
        f"describes #{pr['number']}: run `status` again before preparing")
  number = pr["number"]
  foreman = core.load_foreman(handoff.store, args.unit)
  rounds = foreman["rounds"]
  this_round = next((r for r in rounds if r.get("round") == args.round), {})
  running = [v["round"] for v in rounds
             if v.get("phase") == "launched"
             and v.get("run_status", v.get("status")) == "running"]
  if not args.clean and this_round.get("run_folder"):
    # Re-preparing would keep the old run folder, so the replacement launch
    # would be refused and left unrecorded (R12-03). An interrupted launched
    # round is collected as not run; its replacement is the NEXT round. This
    # runs before any fetch or worktree work.
    raise core.HandoffError(
        f"{args.unit} round {args.round} already recorded a launch "
        f"({this_round['run_folder']}): collect it (--not-run <reason> if it was "
        f"interrupted), then prepare round {args.round + 1}.")
  if args.clean:
    # Only at landing. There is no mid-round removal any more: a review
    # worktree lives until the unit lands, so no cleanup can race a runner
    # that still reads it (rounds 9-11 each found a door to that race).
    if not this_round.get("pr") or not this_round.get("worktree"):
      raise core.HandoffError(
          f"{args.unit} round {args.round} has no recorded PR and worktree, so "
          f"there is nothing safe to clean: falling back to the PR watched now "
          f"would delete a different round's refs. Name the round that was "
          f"prepared, or remove the worktree by hand.")
    number = this_round["pr"]
    tree = Path(this_round["worktree"])
    # Liveness comes from the run folder, never from the administrative phase:
    # a round collected as "interrupted" still has a runner that may be
    # reading this worktree (panel, cap decision, Q2).
    unresolved = [v["round"] for v in rounds
                  if v.get("run_folder") and not core.run_terminated(v["run_folder"])
                  and (v["round"] == args.round or (v.get("worktree") or "") == str(tree))]
    if unresolved:
      # Refusing to REMOVE must not refuse to LAND: a leftover worktree costs
      # disk; a failed landing becomes a stop that reaches the owner. Keep it,
      # say so, and finish. Removal is a human's option, never an agent's
      # inference (panel, cap decision, Q2).
      core.round_entry(foreman, args.round)["phase"] = "kept"
      core.save_foreman(handoff.store, args.unit, foreman)
      print(f"kept {tree}: round {unresolved[0]} of {args.unit} recorded a launch with no "
            f"terminal result, so this helper cannot know its runner has stopped reading "
            f"the worktree. Landing is complete; the worktree and refs stay. A human may "
            f"remove them later with `git -C {root} worktree remove {tree}`.")
      return 0
    if tree.resolve() in core.registered_worktrees(root):
      core.remove_worktree(root, tree)
    if args.clean:
      for ref in (f"refs/egm/pr/{number}", f"refs/egm/base/{number}"):
        subprocess.run(["git", "-C", str(root), "update-ref", "-d", ref], capture_output=True)
      core.run_git(["worktree", "prune"], root)
    core.round_entry(foreman, args.round)["phase"] = "cleaned"
    core.save_foreman(handoff.store, args.unit, foreman)
    print(f"cleaned {tree}")
    return 0
  tree = core.worktree_path(handoff.handoff_id, args.unit, number)
  if running:
    raise core.HandoffError(
        f"{args.unit} round {running[0]} is still running: wait for its completion "
        f"notice, then `collect --unit {args.unit} --round {running[0]}` (or "
        f"`collect ... --not-run <reason>` to skip its result once the runner "
        f"has terminated), before preparing another round")
  url = core.run_git(["remote", "get-url", remote], root)
  if (core.parse_remote_url(url) or "").lower() != repo.lower():
    raise core.HandoffError(f"remote {remote} no longer names {repo} ({url.strip()}): refusing to fetch")
  core.run_git(["fetch", "--no-write-fetch-head", remote,
           f"+refs/pull/{number}/head:refs/egm/pr/{number}",
           f"+refs/heads/{pr['base_ref']}:refs/egm/base/{number}"], root)
  core.round_entry(foreman, args.round).update(
      {"pr": number, "phase": "fetched", "worktree": str(tree), "runcard": card["parent"] or args.runcard})
  core.save_foreman(handoff.store, args.unit, foreman)
  fetched = core.run_git(["rev-parse", f"refs/egm/pr/{number}"], root).strip()
  if fetched != pr["head"]:
    print(f"head-moved: refs/egm/pr/{number} is {fetched[:7]}, status recorded {pr['head'][:7]}; run status again")
    return 3
  if tree.exists():
    if tree.resolve() not in core.registered_worktrees(root):
      raise core.HandoffError(f"{tree} exists but is not a registered worktree: remove it by hand")
    if core.run_git(["status", "--porcelain"], tree).strip():
      raise core.HandoffError(f"worktree {tree} has changes: remove it by hand")
    unresolved = [v["round"] for v in rounds
                  if v.get("run_folder") and not core.run_terminated(v["run_folder"])
                  and (v.get("worktree") or "") == str(tree)]
    if unresolved:
      raise core.HandoffError(f"worktree {tree} belongs to round {unresolved[0]}, whose launch has no "
                         f"terminal result: wait for its completion notice, then `collect` it. "
                         f"This helper never removes it on a guess; only a human may, with "
                         f"`git -C {root} worktree remove {tree}`.")
    core.remove_worktree(root, tree)
  tree.parent.mkdir(parents=True, exist_ok=True)
  core.run_git(["worktree", "add", "--detach", str(tree), pr["head"]], root)
  merge_base = core.run_git(["merge-base", pr["base_sha"], "HEAD"], tree).strip()
  diff = subprocess.run(["git", "-C", str(tree), "diff", "--no-ext-diff", "--no-textconv", "--binary",
                         merge_base, "--"], capture_output=True, check=True).stdout
  diff_path = handoff.artifact_dir / f"pr_{number}_r{args.round}.diff"
  core.atomic_write(diff_path, diff)
  ci = core.read_ci(repo, pr["head"])
  ci["verdict"] = core.ci_verdict(ci)
  ci_path = handoff.artifact_dir / f"ci_{number}_r{args.round}.json"
  core.atomic_write(ci_path, json.dumps(ci, indent=2) + "\n")
  round_record = {"pr": number, "phase": "prepared", "worktree": str(tree), "head": pr["head"],
                  "base_ref": pr["base_ref"], "base_sha": pr["base_sha"], "merge_base": merge_base,
                  "diff": str(diff_path), "ci": str(ci_path), "ci_verdict": ci["verdict"]}
  # Update, never replace: the PR this round reviewed is what `--remove` and
  # `--clean` resolve from, and a later round may watch a different PR.
  core.round_entry(foreman, args.round).update(round_record)
  core.save_foreman(handoff.store, args.unit, foreman)
  if args.runner:
    if not core.MODEL_RE.match(args.model or "") or args.effort not in core.EFFORTS:
      raise core.HandoffError("--runner needs --model matching the allowlist and --effort in low|medium|high|xhigh")
    brief = handoff.artifact_dir / f"astra_brief_w{args.wave}_u{args.unit}_r{args.round}.md"
    unit_file = handoff.unit_file(args.unit)
    paths = [str(args.runner), str(tree), str(unit_file), str(brief)]
    if any("'" in p for p in paths):
      raise core.HandoffError("a path holds a single quote: record `not run (path quoting)`")
    line = (f"python3 '{args.runner}' inspect --host claude --repo '{tree}' --plan '{unit_file}' "
            f"--base '{merge_base}' --feedback '{brief}' --model {args.model} --effort {args.effort} "
            f"--timeout 3600 --artifacts \"${{TMPDIR:-/tmp}}/egm-astra\"")
    launch = handoff.artifact_dir / f"foreman_{args.unit}_r{args.round}_launch.md"
    core.atomic_write(launch, f"Bash timeout: 3900000 ms (run_in_background: true, from the main conversation)\n\n    {line}\n")
    print(f"launch line in {launch}")
  print(f"prepared: worktree {tree} at {pr['head'][:7]}, merge base {merge_base[:7]}, "
        f"diff {diff_path.name}, {ci['verdict']} ({ci_path.name})")
  return 0
