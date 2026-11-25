# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the builder's precheck of spec section 6.3 (U67); the rulings' times passed to `worktree_checks` as `collect` passes them, so a test-delta settlement binds the same entry (U102, 1.3 design section 3.5).

"""superegm precheck: the foreman's checks that need only the worktree, run by the builder in its own worktree
before every push: each DoD item's fenced output and `Run` command, the test delta, the scope check and the
test-first order. The merge base is `git merge-base refs/superegm/base HEAD`, the PR body the `--pr-body` file
and, from round 2, the unit's posted rounds, recorded rulings and issue comments are read from the store as
`collect` reads them (the issue comments as this launch fetched them), so a finding the owner settled is not
reported again. The `Run` items run in a separate clone of HEAD under a temporary directory, never in the
builder's worktree or repository; a run's output is kept in a temporary directory of its own when a `dod-<n>`
finding names it, and removed by the unit's next precheck (or at once, when no finding names it). One line per finding in the foreman's grammar, numbered for the round the next dispatch
takes; exit 0 when there is none."""

import os
import re
import shutil
import tempfile
import time
from pathlib import Path

import superegm as core
from superegm import collect, review
from superegm.launch import load_launches
from superegm.collect import parse_comments
from superegm.decision import binding_rulings, consumed_comments, recorded_rulings

WRITES = frozenset()  # the store kinds this subcommand writes: none, it reads
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own


def register(subparsers):
  p = core.add_parser(subparsers, "precheck", "run the foreman's worktree checks before a push", runcard=False)
  p.add_argument("--unit", required=True)
  p.add_argument("--pr-body", required=True, help="the pull request body file the builder writes")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  worktree = core.git_toplevel(Path.cwd())
  # the builder's worktree holds no `.superegm/config.json` (it is untracked): the store is the handoff's checkout's,
  # which the launch's script names in SUPEREGM_REPO; the git common directory's parent only without it
  named = os.environ.get("SUPEREGM_REPO")
  common = None if named else core.run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree).strip()
  repo_root = Path(named) if named else Path(common).parent
  st = core.store(repo_root, args)
  recorded = core.load_state(st.root).get("plan")
  if not recorded:
    raise core.HandoffError("state holds no plan path: run `graph --plan <file>` first")
  handoff = core.Handoff(core.rebased(recorded, repo_root), st)
  unit = args.unit
  if unit not in handoff.plan.units:
    raise core.HandoffError(f"precheck: {unit} is not a unit of the plan")
  data = core.load_foreman(st, unit)
  rnd = len(data.get("rounds") or []) + 1  # the round the next `foreman run` dispatch takes
  body = core.unit_file_body(st.path("unit", unit))
  scope = [path for path, _ in handoff.plan.units[unit].scope]
  pr_body = core.read_text(Path(args.pr_body))
  merge_base = core.run_git(["merge-base", "refs/superegm/base", "HEAD"], worktree).strip()
  prior, comments = settled(st, handoff, unit, data)
  rulings = binding_rulings([c for c in comments if c["kind"] == "issue"], handoff.config.get("owners") or [],
                            recorded_rulings(data), data.get("decisions") or [],
                            deferred=[row["fid"] for row in data.get("followups") or []], consumed=consumed_comments(data))
  head = core.run_git(["rev-parse", "HEAD"], worktree).strip()
  deadline = time.time() + 60 * handoff.config["foreman"]["run_timeout_minutes"]  # collect's bound on the DoD runs
  # each run's output is kept, outside the store and the worktree, for the builder to read when a finding names it;
  # the next precheck of this unit removes it, so at most one run's output is left at a time
  prefix = f"superegm-precheck-{st.handoff_id}-{unit}-out-"
  for earlier in Path(tempfile.gettempdir()).glob(f"{prefix}*"):
    shutil.rmtree(earlier, ignore_errors=True)
  out_dir = Path(tempfile.mkdtemp(prefix=prefix))
  try:
    with tempfile.TemporaryDirectory(prefix="superegm-precheck-") as scratch:  # never the store or the worktree
      tree = Path(scratch) / "tree"
      # the Run items run in a separate clone of HEAD: its own refs, config and files, so whatever a run writes (a
      # cache, a tracked file, a ref, a config key) goes with it. The clone keeps no `origin` (a push through it
      # would write the builder's refs) and holds the builder's refs/superegm/* and remote-tracking refs, the refs
      # `collect`'s checkout of the head sees
      core.run_git(["clone", "--quiet", "--shared", "--no-checkout", str(worktree), str(tree)], worktree)
      core.run_git(["remote", "remove", "origin"], tree)
      core.run_git(["fetch", "--quiet", "--no-write-fetch-head", str(worktree), "+refs/superegm/*:refs/superegm/*",
                    "+refs/remotes/origin/*:refs/remotes/origin/*"], tree)
      core.run_git(["checkout", "--quiet", "--detach", head], tree)
      found, _ = collect.worktree_checks(tree, merge_base, head, body, scope, pr_body, rulings, prior["links"], prior,
                                         deadline=deadline, out_dir=out_dir, config=handoff.config,  # `collect`'s own
                                         times=collect.ruling_times(comments, collect.recorded_times(data)))  # its ruling times too
  except BaseException:
    shutil.rmtree(out_dir, ignore_errors=True)
    raise
  kept = lambda m: str(out_dir / f"{m.group(1)}.out")
  named = [(re.sub(r"^dod/(\d+)\.txt$", kept, location), claim) for location, claim in found]
  if named == found:  # no finding names a run's output: nothing is left behind
    shutil.rmtree(out_dir, ignore_errors=True)
  found = named
  for i, (location, claim) in enumerate(found, 1):
    print(f"foreman-{rnd}-{i} | high | {location} | regression: no | {claim}")
  return 1 if found else 0


def settled(st, handoff, unit: str, data: dict) -> tuple:
  """What the posted rounds settle, read-only, through `collect.posted_findings`, the reading `collect` makes;
  and the issue comments: this launch's `launches/<unit>_r<n>_comments.md`, which `launch-builder` fetched for
  the prompt when it launched the builder (a ruling posted after its round and before the launch is there; one
  posted or deleted during the session is not, where `collect`, reading the comments after the push, sees it),
  else the latest posted round's own comments.md."""
  rid = review.head_review_id(st, unit)
  pr = (handoff.state.get("units", {}).get(unit) or {}).get("pr") or {}
  prior = collect.posted_findings(st, rid, data.get("rounds") or [])
  posted = [e["round"] for e in data.get("rounds") or [] if e.get("phase") == "posted"]
  seen = st.path("review", unit, f"pr{pr['number']}") / f"r{max(posted)}" / "comments.md" \
      if posted and pr.get("number") else None
  rounds = [entry["round"] for entry in load_launches(st, unit)]
  fetched = st.path("launches", f"{unit}_r{max(rounds)}_comments.md") if rounds else None
  if fetched is not None and fetched.is_file():
    seen = fetched
  return prior, (parse_comments(core.read_text(seen))[1] if seen is not None and seen.is_file() else [])
