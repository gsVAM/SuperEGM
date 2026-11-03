# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the tdd-order check of spec section 11.

"""superegm tdd-order: for each Step a `test(S<n>)` commit touching its test path precedes a `feat(S<n>)`
commit touching its implementation path, and every `test(…)` commit touches only paths under `tests/`."""

from pathlib import Path

import superegm as core
from superegm import body as body_mod, review

WRITES = frozenset()  # the store kinds this subcommand writes: none, it reads


def register(subparsers):
  p = core.add_parser(subparsers, "tdd-order", "check that each Step's test commit precedes its implementation", runcard=False)
  p.add_argument("--unit", required=True)
  p.add_argument("--dispatch", required=True, help="the dispatch id of the prepared round")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  st = core.store(core.git_toplevel(Path.cwd()))
  try:
    entry = review.require_dispatch(args.unit, core.load_foreman(st, args.unit), args.dispatch)
  except review.Refusal as refusal:
    print(refusal)
    return 1
  if not entry.get("worktree"):
    raise core.HandoffError(f"{args.unit} round {entry['round']} is not prepared")
  failures = check(core.unit_file_body(st.path("unit", args.unit)), commits_of(Path(entry["worktree"]), entry["merge_base"]))
  print("\n".join(failures) if failures else "tdd-order: ok")
  return 1 if failures else 0


def commits_of(worktree, merge_base: str) -> list:
  """`(subject, touched paths)` oldest first over `<merge_base>..HEAD` in the worktree."""
  out = core.run_git(["log", "--reverse", "--format=%x1e%s", "--name-only", f"{merge_base}..HEAD"], worktree)
  commits = []
  for record in out.split("\x1e")[1:]:
    subject, _, rest = record.partition("\n")
    commits.append((subject, [l for l in rest.splitlines() if l.strip()]))
  return commits


def check(body: str, commits: list) -> list:
  """The failures, in Step order then the `tests/`-only rule; [] when the order holds."""
  failures = []
  for n, test_path, impl_path in body_mod.step_paths(body):
    first = lambda kind, path: next((i for i, (s, paths) in enumerate(commits) if s.startswith(f"{kind}(S{n}):") and path in paths), None)
    test, feat = first("test", test_path), first("feat", impl_path)
    if test is None:
      failures.append(f"S{n}: no test(S{n}) commit touches {test_path}")
    if feat is None:
      failures.append(f"S{n}: no feat(S{n}) commit touches {impl_path}")
    elif test is not None and feat < test:
      failures.append(f"S{n}: feat(S{n}) precedes test(S{n})")
  for subject, paths in commits:
    if subject.startswith("test("):
      failures += [f"{subject.split(':', 1)[0]} touches {p} outside tests/" for p in paths if not p.startswith("tests/")]
  return failures
