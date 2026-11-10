# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the tdd-order check of spec section 11.

"""superegm tdd-order: for each Step a `test(S<n>)` commit touching its test path precedes a `feat(S<n>)`
commit touching its implementation path, and every `test(S<n>)` commit touches only test files: the test paths the
Steps name or files the §9.3 test-file name rule names (fixtures and `conftest.py` among them)."""

import re
from pathlib import Path

import superegm as core
from superegm import body as body_mod, review
from superegm.orient import TEST_RE

WRITES = frozenset()  # the store kinds this subcommand writes: none, it reads
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)


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
  """The failures, in Step order then the test-paths-only rule; [] when the order holds."""
  failures, steps = [], body_mod.step_paths(body)
  test_paths = {test_path for _, test_path, _ in steps if test_path}  # colocated tests (`src/x.spec.ts`) count: the Steps decide, not a `tests/` prefix
  for n, test_path, impl_path in steps:
    first = lambda kind, path: next((i for i, (s, paths) in enumerate(commits) if s.startswith(f"{kind}(S{n}):") and path in paths), None)
    test, feat = first("test", test_path), first("feat", impl_path)
    if test is None:
      failures.append(f"S{n}: no test(S{n}) commit touches {test_path}")
    if feat is None:
      failures.append(f"S{n}: no feat(S{n}) commit touches {impl_path}")
    elif test is not None and feat < test:
      failures.append(f"S{n}: feat(S{n}) precedes test(S{n})")
  for subject, paths in commits:
    if re.match(r"test\(S\d+\):", subject):  # an adopted branch's own `test(…)` history enters `commits_of` in full and is not the builder's
      failures += [f"{subject.split(':', 1)[0]} touches {p}: not a test path the Steps name nor a test file by name" for p in paths if p not in test_paths and not TEST_RE.search(p)]
  return failures
