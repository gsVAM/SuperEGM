# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the builder's precheck of spec section 6.3 (U67).

"""superegm precheck: the foreman's checks that need only the worktree, run by the builder in its own worktree
before every push: each DoD item's fenced output and `Run` command, the test delta, the scope check and the
test-first order. The merge base is `git merge-base refs/superegm/base HEAD`, the PR body the `--pr-body` file
and, from round 2, the unit's posted rounds, recorded rulings and issue comments are read from the store as
`collect` reads them (the issue comments as this launch fetched them), so a finding the owner settled is not
reported again. The `Run` items run in a detached checkout of HEAD under a temporary directory, never in the
builder's worktree. One line per finding in the foreman's grammar, numbered for the round the next dispatch
takes; exit 0 when there is none."""

import os
import re
import tempfile
import time
from pathlib import Path

import superegm as core
from superegm import collect, review
from superegm.launch import load_launches
from superegm.collect import parse_comments, prior_foreman_findings
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
  with tempfile.TemporaryDirectory(prefix="superegm-precheck-") as scratch:  # never the store or the builder's worktree
    tree, out_dir = Path(scratch) / "tree", Path(scratch) / "out"
    out_dir.mkdir()
    # the Run items run in a detached checkout of HEAD, as `collect` runs them in its own checkout of the head:
    # whatever a run writes (a cache, an edit to a tracked file) goes with the temporary directory
    core.run_git(["worktree", "add", "--quiet", "--detach", str(tree), head], worktree)
    try:
      found, _ = collect.worktree_checks(tree, merge_base, head, body, scope, pr_body, rulings, prior["links"], prior,
                                         deadline=deadline, out_dir=out_dir, config=handoff.config)  # `collect`'s own
    finally:
      core.run_git(["worktree", "remove", "--force", str(tree)], worktree, check=False)
      core.run_git(["worktree", "prune"], worktree, check=False)
  for i, (location, claim) in enumerate(found, 1):
    print(f"foreman-{rnd}-{i} | high | {location} | regression: no | {claim}")
  return 1 if found else 0


def settled(st, handoff, unit: str, data: dict) -> tuple:
  """What the posted rounds hold, read-only: the foreman's scope, tdd-order, `dod-<n>` and test-delta findings
  and the contest links, as `collect` reads them; and the issue comments as they are now, as `collect` reads them
  after the push: this launch's `launches/<unit>_r<n>_comments.md`, which `launch-builder` fetched for the prompt
  (a ruling posted after its round is there, a deleted one is not), else the latest posted round's."""
  rid = review.head_review_id(st, unit)
  pr = (handoff.state.get("units", {}).get(unit) or {}).get("pr") or {}
  prior = {"scope": {}, "tdd": {}, "dod": {}, "delta": {}, "links": {}}
  seen = None
  for e in data.get("rounds") or []:
    if e.get("phase") != "posted":
      continue
    findings = prior_foreman_findings(st, rid, e["round"])
    deltas = [f["id"] for f in findings if f["claim"].startswith("test-delta: ")]
    prior["delta"].update({fid: (d["file"], d["base_commit"], d["base_line"], d["kind"])
                           for fid, d in zip(deltas, e.get("test_delta") or [])})
    for f in findings:
      if f["claim"] == "changed path outside Scope paths":
        prior["scope"][f["id"]] = f["location"]
      if f["claim"].startswith("tdd-order: "):
        prior["tdd"][f["id"]] = f["claim"].removeprefix("tdd-order: ")
      if (m := re.match(r"dod-(\d+): ", f["claim"])):
        prior["dod"][f["id"]] = int(m.group(1))
      if (m := re.match(r"(?:contested|unreplied) (\S+):", f["claim"])):
        prior["links"][f["id"]] = m.group(1)
    if pr.get("number"):
      seen = st.path("review", unit, f"pr{pr['number']}") / f"r{e['round']}" / "comments.md"
  rounds = [entry["round"] for entry in load_launches(st, unit)]
  fetched = st.path("launches", f"{unit}_r{max(rounds)}_comments.md") if rounds else None
  if fetched is not None and fetched.is_file():
    seen = fetched
  return prior, (parse_comments(core.read_text(seen))[1] if seen is not None and seen.is_file() else [])
