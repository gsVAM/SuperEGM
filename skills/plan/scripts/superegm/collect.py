# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# From the elephant-goldfish-model (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_collect` as the collect module, keyed by the dispatch id; it records the foreman's own findings of a round (spec section 11); the lane record's `brief_sha256` (U17); an unreplied external high or medium carried forward (U21); rulings read through `ruling_of` and the record, every folded deviation heading (U22); the DoD re-run and the test delta, two gates before the word (U25); its own `foreman` config key and `init` line, moved from `__init__` and `init` (U32); both `binding_rulings` calls drop the consumed comments, so an edited recorded proceed waives no check (U94); the worktree checks in `worktree_checks`, the one function `collect` and `precheck` call, the posted rounds' settled findings in `posted_findings`, the reading both share, and the changed paths read NUL-separated, one with a control character shown JSON-quoted (U67); the `spec` deviation kind in `DEVIATION_RE`, and `--spec`, the foreman's own finding of kind `spec` held in its round (U84); a contest of a settled fid, or of one derived from it, dropped, an owner's `test-delta <file> allowed` widening Scope, and a test-delta settlement keyed by the test and the line text, bound by its ruling's time to the entry it ruled on (U102, 1.3 design section 3.5).

"""superegm collect: the foreman's findings of a round through one `review record --reviewer foreman`, or a
round that could not complete with `--not-run`."""

import argparse
import ast
import contextlib
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import superegm as core
from superegm import body as body_mod, review, tdd_order
from superegm.decision import PATH_LINE, binding_rulings, check_respec, cites, consumed_comments, recorded_rulings
from superegm.foreman import head_review_id
from superegm.launch_builder import DOD_RESULT_RE, SENTINEL, launched_pairs
from superegm.orient import TEST_RE
from superegm.prepare import HEADER_RE

WRITES = frozenset(['foreman', 'review', 'reviews'])  # the store kinds this subcommand writes
CONFIG_DEFAULTS = {  # its own config key and init line (U32)
    "foreman": {"run_timeout_minutes": 8},  # the bound on one whole `collect` call, under the Bash tool's 10 (spec section 11.1)
}
INIT_STEP = ("`collect` re-runs every DoD `Run` item the PR body pastes under its `### DoD <n>` fence in the review worktree "
             "(an item without one is the `Run item <n>: no fenced output` high, not run), the whole call bounded by "
             "foreman.run_timeout_minutes (default 8, at most 9, under the Bash tool's 10-minute cap).")
DOCTOR_CHECKS = None
SKILLS = frozenset(['wave'])  # the skills whose card this subcommand accepts
DEVIATION_RE = re.compile(r"^\*\*Deviation \((interface|dod|test|spec|other)\):\*\*")
REPLY_RE = re.compile(r"^\*\*Reply (\S+):\*\* (fixed|contested)(?:\s*[—-]\s*(.*))?", re.S)
COUNTS_RE = re.compile(r"(\d+) passed|(\d+) failed")  # a pytest summary line's pass and fail counts
KILL_WAIT = 5  # seconds waited after `kill_group` at the bound before `exit: none` is recorded


def run_env(gh, worktree) -> dict:
  """The DoD runs' environment, an allow-list (spec section 11.1): `PATH`, `HOME`, `LANG`, `TMPDIR`, the sentinel
  `GH_TOKEN`, the builder's git shut-out pairs, `PIP_REQUIRE_VIRTUALENV=1` and `npm_config_prefix` at the worktree.
  The pairs are `launched_pairs`' own, after one entry of the gate's: an empty `credential.helper`, so a generic
  helper the checkout's `.git/config` names answers no host; then `launched_pairs` empty github.com's helper and
  `core.askPass` and set `!<gh> auth git-credential` as github.com's helper, as the builder's are; that helper
  answers with the sentinel `GH_TOKEN`, never a real credential."""
  env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "TMPDIR") if k in os.environ}
  pairs = dict(launched_pairs(gh, "superegm", "superegm"))
  count = int(pairs.pop("GIT_CONFIG_COUNT"))
  entries = [("credential.helper", "")] + [(pairs.pop(f"GIT_CONFIG_KEY_{i}"), pairs.pop(f"GIT_CONFIG_VALUE_{i}")) for i in range(count)]
  pairs["GIT_CONFIG_COUNT"] = str(len(entries))
  for i, (key, value) in enumerate(entries):
    pairs.update({f"GIT_CONFIG_KEY_{i}": key, f"GIT_CONFIG_VALUE_{i}": value})
  env.update(pairs)
  env.update(GH_TOKEN=SENTINEL, PIP_REQUIRE_VIRTUALENV="1", npm_config_prefix=str(worktree))
  return env


def last_line(text: str) -> str:
  return next((l.strip() for l in reversed(text.splitlines()) if l.strip()), "")


def counts(text) -> tuple | None:
  """`(passed, failed)` from the last line of `text` matching `COUNTS_RE` (an absent word 0), or None: no such line."""
  line = next((l for l in reversed((text or "").splitlines()) if COUNTS_RE.search(l)), None)
  if line is None:
    return None
  found = COUNTS_RE.findall(line)
  return (next((int(p) for p, _ in found if p), 0), next((int(f) for _, f in found if f), 0))


def dod_findings(body: str, runs: dict, ruled: set, texts: dict = None, config: dict = None) -> list:
  """The `dod-<n>` highs of the re-run, in item order, skipping an item number in `ruled`: a run cut by the bound
  `ran red (timeout)`, an item the bound left unreached `not run (timeout)`, a non-zero exit `ran red (<line>)` alone
  (`<line>` the summary with ` | ` written ` ¦ `, so the finding keeps its five fields, then `review.mask`ed with
  `config`, so a mention or a banned term in the output cannot make the review unpostable; a red run that printed
  nothing `ran red (exit <code>)`), and a green run whose pass or fail counts differ from the builder's paste
  `paste differs from the run`. `texts`, when given, maps an item number to `(output, paste)`, the whole texts
  whose last `COUNTS_RE` lines are compared; else the summary lines are."""
  found = []
  for n, kind, _ in body_mod.dod_items(body):
    run = runs.get(str(n))
    if kind != "run" or run is None or n in ruled:
      continue
    if run["summary"] is None:
      found.append(("pr_body.md", f"dod-{n}: not run (timeout)"))
    elif run["timed_out"]:
      found.append((f"dod/{n}.txt", f"dod-{n}: ran red (timeout)"))
    elif run["exit"] != 0:
      line = review.mask(run["summary"].replace(" | ", " ¦ "), config or {}) or f"exit {run['exit']}"
      found.append((f"dod/{n}.txt", f"dod-{n}: ran red ({line})"))
    elif None not in (ran := counts((texts or {}).get(n, (run["summary"], None))[0]),
                      pasted := counts((texts or {}).get(n, (None, run["paste_summary"]))[1])) and ran != pasted:
      found.append((f"dod/{n}.txt", f"dod-{n}: paste differs from the run"))
  return found


def dod_runs(items, worktree: Path, env: dict, deadline: float, out_dir: Path) -> dict:
  """Run each `(n, command, paste_summary)` through `/bin/sh` in `worktree`, in its own process group, its output
  to `out_dir/<n>.out`; the group is killed on the item's return and at `deadline`, and an item reached after
  the deadline is not run (`exit` and `summary` None, `timed_out` true)."""
  out_dir.mkdir(parents=True, exist_ok=True)
  runs = {}
  for n, command, paste in items:
    left = deadline - time.time()
    if left <= 0:
      runs[str(n)] = {"exit": None, "summary": None, "paste_summary": paste, "timed_out": True}
      continue
    out = out_dir / f"{n}.out"
    with open(out, "wb") as sink:
      p = subprocess.Popen(["/bin/sh", "-c", command], cwd=str(worktree), env=env, stdin=subprocess.DEVNULL,
                           stdout=sink, stderr=subprocess.STDOUT, start_new_session=True)
      try:
        code, timed_out = p.wait(timeout=left), False
        core.kill_group(p.pid)
      except subprocess.TimeoutExpired:
        core.kill_group(p.pid)
        with contextlib.suppress(subprocess.TimeoutExpired):
          p.wait(timeout=KILL_WAIT)
        code, timed_out = None, True
    summary = last_line(out.read_text(encoding="utf-8", errors="replace") if out.is_file() else "")  # a run may unlink it
    runs[str(n)] = {"exit": code, "summary": summary, "paste_summary": paste, "timed_out": timed_out}
  return runs


OPERATORS = ("==", " in ", "raises", "match=")  # a paired head line lacking one of its base line's is weakened
MARKER_RE = re.compile(r"@pytest\.mark\.(?:skip|skipif|xfail)\b")


def marker(line: str):
  """The `skip`, `skipif` or `xfail` decorator `line` opens with, never one a comment or a string holds."""
  return MARKER_RE.match(line.strip())
DEF_RE = re.compile(r"\s*(?:async\s+)?def (test_\w+)\s*\(")  # a test function, by name


def assertion_lines(lines: list) -> set:
  """The 0-based indexes of `lines` the gate guards: an `assert`, a `pytest.raises`, a `def test_` and a
  `parametrize` row (a line strictly between one holding `@pytest.mark.parametrize(` and the next whose stripped
  text starts with `]`)."""
  out, inside = set(), False
  for i, line in enumerate(lines):
    s = line.strip()
    if inside:
      if s.startswith("]"):
        inside = False
      else:
        out.add(i)
        continue
    if "@pytest.mark.parametrize(" in line:  # a decorator that closes its brackets on its own line opens no rows
      inside = line.count("(") > line.count(")") or line.count("[") > line.count("]")
    elif re.match(r"assert\b", s) or "pytest.raises" in s or s.startswith("def test_"):  # `assert(x)` too
      out.add(i)
  return out


def decorated(lines: list, j: int) -> int:
  """The index of the `def` line decorator line `j` decorates, past any stacked decorator and its continuation
  lines and comments, or `len(lines)` when a statement at the decorator's own indentation comes first."""
  indent = len(lines[j]) - len(lines[j].lstrip())
  for d in range(j + 1, len(lines)):
    s = lines[d].strip()
    if s.startswith(("def ", "async def ")):
      return d
    if s and len(lines[d]) - len(lines[d].lstrip()) <= indent and not s.startswith(("@", ")", "]", "}", "#")):
      break
  return len(lines)


def test_delta(base_files: dict, head_files: dict, named: set) -> list:
  """The removed or weakened assertions of each test file `base_files` maps to `(base_commit, text)`, its head
  text in `head_files` (absent: zero assertions), a file in `named` or not `.py` skipped. Lines pair as git pairs
  them: positionally within each `difflib.SequenceMatcher` `replace` block, the rest unpaired; a pair whose head
  line lacks one of the base line's `OPERATORS` is `weakened` at the head line, a head `skip`, `skipif` or `xfail`
  marker, unpaired or paired with a base line that was no marker, above a `def test_`, past any stacked decorator, is `weakened`, and an unpaired base assertion whose stripped text is in no
  head line is `removed`. Each entry carries the key a settlement matches on (spec section 3.5): `test`, the
  qualified name of the test enclosing the keyed line (`enclosing_tests`), `text`, that line stripped at its ends,
  `base_text`, the paired base line's (a `removed` entry's own `text`, `""` for an added marker), and `occurrence`,
  the text's 1-based number among identical lines of that test; a weakened assertion's is its base line's number
  among identical lines of the base test enclosing it (amended on comment 7174114054). A `removed` entry keys its base
  line in the base test; a weakened assertion its head line in the head test; an added marker its head line, in the
  test it decorates."""
  delta = []
  for path, (base_commit, base_text) in sorted(base_files.items()):
    if path in named or not path.endswith(".py"):
      continue
    base, guarded = base_text.splitlines(), assertion_lines(base_text.splitlines())
    head_text = head_files.get(path)
    head = (head_text or "").splitlines()
    names = {"base": enclosing_tests(base), "head": enclosing_tests(head)}

    def number(lines, name, k):  # line `k`'s 1-based number among identical lines of the test enclosing it
      return sum(1 for m in range(k + 1) if name[m] == name[k] and lines[m].strip() == lines[k].strip())

    def entry(line, base_line, kind, side, k, base_text=None, paired=None):  # keyed on line `k` of `side` (0-based)
      lines, name = (base, names["base"]) if side == "base" else (head, names["head"])
      text = lines[k].strip()
      # a weakened assertion (`paired`, its base line) counts its base line in the base test: two weakenings of
      # identical base assertions stay apart (amended on comment 7174114054)
      occurrence = number(base, names["base"], paired) if paired is not None else number(lines, name, k)
      return {"file": path, "line": line, "base_line": base_line, "kind": kind, "base_commit": base_commit,
              "test": name[k], "text": text, "base_text": text if base_text is None else base_text, "occurrence": occurrence}
    if head_text is None:
      delta += [entry(i + 1, i + 1, "removed", "base", i) for i in sorted(guarded)]
      continue
    stripped = {line.strip() for line in head}
    ops = difflib.SequenceMatcher(None, base, head, autojunk=False).get_opcodes()
    to_base = {j1 + k: i1 + k for tag, i1, i2, j1, j2 in ops if tag == "equal" for k in range(i2 - i1)}
    defs = {m.group(1): i for i, line in enumerate(base) if (m := DEF_RE.match(line))}
    # the markers each base test already carried: one the head keeps (a skipped test moved, decorators reordered) is no addition
    had = {(decorated(base, i), m.group(0)) for i, line in enumerate(base) if (m := marker(line))}

    def base_def(d):  # the base line of the test head line `d` defines: unchanged, else the base `def` of its name
      m = DEF_RE.match(head[d])
      return None if not m else to_base[d] if d in to_base else defs.get(m.group(1))
    for tag, i1, i2, j1, j2 in ops:
      if tag == "equal":
        continue
      paired = min(i2 - i1, j2 - j1) if tag == "replace" else 0
      for k in range(paired):
        i, j = i1 + k, j1 + k
        if i in guarded and any(op in base[i] and op not in head[j] for op in OPERATORS):
          delta.append(entry(j + 1, i + 1, "weakened", "head", j, base[i].strip(), paired=i))
      for j in range(j1, j2):  # a marker added, or written over a paired base line that was no marker
        d = decorated(head, j)
        if j - j1 < paired and marker(base[i1 + j - j1]):
          continue
        if (m := marker(head[j])) and d < len(head) and (b := base_def(d)) is not None and (b, m.group(0)) not in had:
          delta.append(entry(j + 1, b + 1, "weakened", "head", j, ""))
      for i in range(i1 + paired, i2):
        if i in guarded and base[i].strip() not in stripped:
          delta.append(entry(j1 + 1, i + 1, "removed", "base", i))
  return delta


CLASS_RE = re.compile(r"\s*class (\w+)\b")
ANY_DEF_RE = re.compile(r"\s*(?:async\s+)?def (\w+)\s*\(")


def enclosing_tests(lines: list) -> list:
  """The qualified name of the test enclosing each of `lines` (spec section 3.5): the nearest enclosing `def test_*`,
  after the classes around it (`TestA.test_x`), or `<module>` outside a test. A test spans its `def` statement as
  Python's syntax reads it (`ast`), its decorators included: a signature over several lines, or a string's lines at
  any indentation, neither ends it nor opens another. A text Python cannot parse, or whose tree is too deep for its
  parser (`RecursionError`), falls back to `indented_tests`: the round never stops on a test file's shape."""
  try:
    tree = ast.parse("\n".join(lines))
  except (SyntaxError, ValueError, RecursionError, MemoryError):
    return indented_tests(lines)
  names = ["<module>"] * len(lines)
  stack = [(tree, [])]  # an explicit stack, outer nodes first: a deep tree never recurses here
  while stack:
    node, classes = stack.pop()
    for child in ast.iter_child_nodes(node):
      if isinstance(child, ast.ClassDef):
        stack.append((child, classes + [child.name]))
        continue
      if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
        start = min([d.lineno for d in child.decorator_list] + [child.lineno]) - 1
        names[start:child.end_lineno] = [".".join(classes + [child.name])] * (child.end_lineno - start)
      stack.append((child, classes))  # a test nested in this one is named after it: the nearest encloses its lines
  return names


def indented_tests(lines: list) -> list:
  """`enclosing_tests` by indentation, for a text Python cannot parse: a block ends at the next statement line at its
  own indentation or less; a line that opens inside a bracket or a string (`statement_starts`: a signature's closing
  `):`, a triple-quoted string's lines) ends no block and opens none; a line takes the nearest enclosing
  `def test_*`, after the classes around it; a blank or comment line takes a test's name only between two lines of
  that test, as `ast`'s spans have it; a decorator line, and every line down to the `def` it decorates, belongs to
  the test that `def` opens."""
  names, scopes = [], []  # scopes: (indent, name, is_class), outermost first
  starts = statement_starts(lines)

  def qualified():
    tests = [k for k, (_, name, is_class) in enumerate(scopes) if not is_class and name.startswith("test_")]
    if not tests:
      return "<module>"
    return ".".join([name for _, name, is_class in scopes[:tests[-1]] if is_class] + [scopes[tests[-1]][1]])
  filler = []  # each blank or comment line at a statement's place: named once the next statement is
  for j, line in enumerate(lines):
    s = line.strip()
    if starts[j] and (not s or s.startswith("#")):
      filler.append(j)
      names.append(None)
      continue
    if starts[j]:
      indent = len(line) - len(line.lstrip())
      while scopes and scopes[-1][0] >= indent:
        scopes.pop()
      if m := CLASS_RE.match(line):
        scopes.append((indent, m.group(1), True))
      elif m := ANY_DEF_RE.match(line):
        scopes.append((indent, m.group(1), False))
    names.append(qualified())
    before = next((names[k] for k in range(filler[0] - 1, -1, -1) if names[k] is not None), None) if filler else None
    for k in filler:
      names[k] = names[j] if before == names[j] else "<module>"
    filler = []
  for k in filler:
    names[k] = "<module>"
  for j, line in enumerate(lines):  # a decorator and the lines down to its `def`: that def's test
    if starts[j] and line.strip().startswith("@") and (d := decorated(lines, j)) < len(lines):
      names[j:d] = [names[d]] * (d - j)
  return names


def statement_starts(lines: list) -> list:
  """Whether each of `lines` opens outside any bracket, string or backslash continuation: a light scan of quotes
  (single, double, triple), brackets and comments, for a text `ast` cannot read."""
  starts, depth, quote, joined = [], 0, None, False
  for line in lines:
    starts.append(depth == 0 and quote is None and not joined)
    i, joined = 0, False
    while i < len(line):
      ch = line[i]
      if quote:
        if line.startswith(quote, i):
          i, quote = i + len(quote), None
          continue
        i += 2 if ch == "\\" else 1
        continue
      if ch == "#":
        break
      if ch in "'\"":
        quote = ch * 3 if line.startswith(ch * 3, i) else ch
        i += len(quote)
        continue
      if ch in "([{":
        depth += 1
      elif ch in ")]}":
        depth = max(0, depth - 1)
      i += 1
    if quote and len(quote) == 1:  # a one-quote string ends at its line, unless the line continues it
      quote = quote if line.endswith("\\") else None
    joined = quote is None and depth == 0 and line.rstrip().endswith("\\") and not line.lstrip().startswith("#")
  return starts


def delta_files(worktree: Path, base: str, head: str, commits: list, named: set) -> tuple:
  """`(base_files, head_files)` for `test_delta`, read from git objects: every test file by name a commit of the
  range touches that no `Write` line names, keyed by its head path; its base the range's base when the file (or
  its rename source, by `git diff -M`) exists there, else the commit that creates it; a rename source is compared
  through its pair, never alone. The range's own `git diff` adds a file only a merge changed; a file the range
  creates then renames chains back, commit by commit (`git log -M`), to the path it was created under, and forward
  to the path it ends under at the head, test-named or not."""
  # every path NUL-delimited (`-z`), never C-quoted; `-m` reads a merge's own changes against each parent
  log = name_status(core.run_git(["log", "-m", "-M", "--reverse", "--name-status", "-z", "--format=", f"{base}..{head}"], worktree))
  diff = name_status(core.run_git(["diff", "-M", "--name-status", "-z", base, head], worktree))
  touched = [unquote(p) for _, paths in commits for p in paths]  # `commits_of` reads `--name-only`, C-quoted
  touched += [p for _, paths in log + diff for p in paths]  # a rename's source among them, and a change a merge alone made
  touched = list(dict.fromkeys(p for p in touched if TEST_RE.search(p) and p not in named))
  renames = {paths[1]: paths[0] for status, paths in diff if status.startswith("R")}
  back = {paths[1]: paths[0] for status, paths in log if status.startswith("R")}
  ahead = {old: new for new, old in renames.items()}  # a test file renamed, base to head, to a path no longer test-named

  def first(path):  # the path a file was created under in the range, down its renames
    seen = {path}
    while path in back and back[path] not in seen:
      path = back[path]
      seen.add(path)
    return path
  fwd = {old: new for new, old in back.items()}

  def last(path):  # the path a file ends under in the range, up its renames commit by commit
    seen = {path}
    while path in fwd and fwd[path] not in seen:
      path = fwd[path]
      seen.add(path)
    return path
  tree = lambda rev: set(core.run_git(["ls-tree", "-r", "-z", "--name-only", rev], worktree).split("\0")) - {""}
  at_base, at_head = tree(base), tree(head)
  show = lambda rev, path: core.run_git(["show", f"{rev}:{path}"], worktree)
  base_files, head_files = {}, {}
  candidates = set(touched)
  through = {old for new, old in [*renames.items(), *back.items()] if new in candidates and new != old}
  for path in touched:
    if path not in at_head and path in through:
      continue  # compared through the test file it was renamed to; renamed out of test naming, it compares alone
    old = renames.get(path, path)
    if old not in at_base and first(path) in at_base:  # renamed from a base file, then deleted in the range
      old = first(path)
    if old in at_base:
      base_files[path] = (base, show(base, old))
    else:
      old = first(path)
      # `-m`: a file a merge introduces, in neither parent, is created by that merge
      created = core.run_git(["log", "-m", "--reverse", "--format=%H", "--diff-filter=A", f"{base}..{head}", "--", old], worktree).split()
      if not created:
        continue
      base_files[path] = (created[0], show(created[0], old))
    if path in at_head:
      head_files[path] = show(head, path)
    elif (new := ahead.get(path) or last(path)) in at_head and new not in candidates:  # renamed out of test naming
      head_files[path] = show(head, new)  # compared with its new path, base to head or, for a file the range creates, commit by commit
  return base_files, head_files


def name_status(out: str) -> list:
  """`(status, paths)` per entry of a `--name-status -z` output: a rename or copy carries two paths, any other one."""
  tokens, entries = out.split("\0"), []
  i = 0
  while i < len(tokens):
    status = tokens[i].strip()
    if not status:
      i += 1
      continue
    n = 2 if status[0] in "RC" else 1
    entries.append((status, tokens[i + 1:i + 1 + n]))
    i += 1 + n
  return entries


ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


def unquote(path: str) -> str:
  """A path as git's `core.quotePath` C-quotes it (`"tests/caf\\303\\251.py"`), unquoted; any other path as given."""
  if not (len(path) > 1 and path[0] == path[-1] == '"'):
    return path
  s, out, i = path[1:-1], bytearray(), 0
  while i < len(s):
    if s[i] == "\\" and i + 1 < len(s):
      if s[i + 1] in "01234567":
        out.append(int(s[i + 1:i + 4], 8))
        i += 4
        continue
      out.append(ESCAPES.get(s[i + 1], ord(s[i + 1])))
      i += 2
      continue
    out += s[i].encode("utf-8")
    i += 1
  return out.decode("utf-8", "surrogateescape")


def register(subparsers):
  p = core.add_parser(subparsers, "collect", "record the foreman's findings of a round, or a round that did not run")
  p.add_argument("--unit", required=True)
  p.add_argument("--dispatch", required=True, help="the dispatch id `foreman dispatch` printed")
  p.add_argument("--not-run", dest="not_run", help="the round could not complete, with this reason")
  p.add_argument("--spec", action="append", default=[], metavar="TEXT",
                 help="a finding of kind `spec` (§7.6): the frozen spec's `path:line` and the evidence; held as `deviation (spec) unruled`")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  try:
    return collect(args, core.require_runcard(args, SKILLS))
  except review.Refusal as refusal:
    print(refusal)
    return 1


def collect(args, card):
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  deadline = time.time() + 60 * handoff.config["foreman"]["run_timeout_minutes"]  # the whole call's bound, from its entry
  unit = args.unit
  data = core.load_foreman(st, unit)
  entry = review.require_dispatch(unit, data, args.dispatch)
  n = entry["round"]
  if args.not_run:
    require_non_terminal(unit, entry)
    entry.update({"phase": "collected", "outcome": f"not run ({args.not_run})"})
    core.save_foreman(st, unit, data)
    core.journal(st, f"{unit} round {n} collected (not run ({args.not_run})) under {args.runcard}")
    print(f"{unit} round {n}: collected (not run ({args.not_run}))")
    return 0
  if entry.get("phase") != "prepared":
    raise core.HandoffError(f"{unit} round {n} is `{entry.get('phase')}`, not `prepared`")
  specs = spec_findings(args.spec, core.handoff_spec(args, st))
  number = handoff.state["units"][unit]["pr"]["number"]
  r = st.path("review", unit, f"pr{number}") / f"r{n}"
  worktree = Path(entry["worktree"])
  text = core.unit_file_body(st.path("unit", unit))
  scope = [path for path, _ in handoff.plan.units[unit].scope]
  login, comments = parse_comments(core.read_text(r / "comments.md"))
  rid = head_review_id(st, unit)
  prior = max((e["round"] for e in data["rounds"] if e.get("phase") == "posted"), default=None)
  prior_ci_fid, prior_tdd, prior_scope, contest_of, external, earlier, disposed = None, {}, {}, {}, [], set(), set()
  prior_dod, prior_delta = {}, {}
  posted = {e["round"]: e.get("posted_at") or "" for e in data["rounds"] if e.get("phase") == "posted"}
  holds = {}  # each id to the first posted round whose record holds it: a reply to it counts from that round's posting
  for k in sorted(posted) if rid else ():
    for f in review.findings_of(review.load_round(st, rid, k) or {"reviewers": {}}):
      holds.setdefault(f["id"], k)
  last = review.load_round(st, rid, prior) or {} if prior and rid else {}
  settled = posted_findings(st, rid, data["rounds"])  # the one reading `precheck` shares
  prior_scope, prior_tdd, prior_dod, prior_delta = settled["scope"], settled["tdd"], settled["dod"], settled["delta"]
  contest_of, disposed = settled["links"], settled["disposed"]
  for e in data["rounds"]:  # every posted round: its external findings and the builder's replies in its window
    if e.get("phase") == "posted":
      external += external_findings(st, rid, e["round"])
      seen = st.path("review", unit, f"pr{number}") / f"r{e['round']}" / "comments.md"
      if seen.is_file():  # a reply in an earlier round's window still answers its finding
        who, said = parse_comments(core.read_text(seen))
        earlier |= {m.group(1) for c in said if c["login"] == who and (m := REPLY_RE.match(c["body"])) and timely(m.group(1), c["at"], posted, holds)}
  for f in prior_foreman_findings(st, rid, prior):
    if f["location"] == "ci":
      prior_ci_fid = f["id"]
  verdict, pr_body = json.loads(core.read_text(r / "ci.json"))["verdict"], core.read_text(r / "pr_body.md")
  followup_fids = [row["fid"] for row in data.get("followups") or []]  # triage's deferrals (spec section 5.2)
  rulings = binding_rulings([c for c in comments if c["kind"] == "issue"], handoff.config.get("owners") or [],
                            recorded_rulings(data), data.get("decisions") or [],
                            deferred=followup_fids, consumed=consumed_comments(data))
  # the worktree's checks, shared with `precheck`: the files a run could edit (the foreman file, the round's record,
  # the worktree's git config) are held whole while the DoD `Run` items run
  checked, facts = worktree_checks(worktree, entry["merge_base"], entry["head"], text, scope, pr_body, rulings, contest_of,
                                   {"dod": prior_dod, "delta": prior_delta, "scope": prior_scope, "tdd": prior_tdd},
                                   deadline=deadline, out_dir=r / "dod", config=handoff.config, times=ruling_times(comments, recorded_times(data)),
                                   hold=[st.path("foreman", unit)] + ([st.path("reviews", rid, f"round-{n}.json")] if rid else []))
  commits, present, delta, runs, texts = (facts[k] for k in ("commits", "present", "delta", "runs", "texts"))
  for i, run in runs.items():
    if run["summary"] is not None:
      core.atomic_write(r / "dod" / f"{i}.txt", f"exit: {'none' if run['exit'] is None else run['exit']}\n"
                        f"summary: {run['summary']}\ntimed_out: {'yes' if run['timed_out'] else 'no'}\n")
  specs += [s for s in unruled_specs(last, rulings) if s not in specs]  # a spec finding stays open until the owner rules it (§7.6)
  lines, contested = foreman_findings(n, verdict, text, scope, worktree, facts["changed"], pr_body, comments, login, prior, prior_ci_fid,
                                      commits, prior_tdd, prior_scope, contest_of,
                                      external, earlier, disposed, posted, handoff.config.get("owners") or [],
                                      recorded_rulings(data), data.get("decisions") or [], recorded_times(data),
                                      handoff.state["units"][unit].get("number"), runs=runs, prior_dod=prior_dod, present=present,
                                      delta=delta, prior_delta=prior_delta, texts=texts, config=handoff.config, held=holds,
                                      open_prior=open_of(last), deferred=followup_fids, consumed=consumed_comments(data),
                                      checked=checked, specs=specs)
  lines, slots, contested = carry(lines, contested, last, prior, contest_of, rulings)
  entry.update(dod_runs=runs, test_delta=delta)
  findings = r / "foreman.findings"
  core.atomic_write(findings, "".join(line + "\n" for line in lines))
  with contextlib.redirect_stdout(io.StringIO()):
    code = review.record_round(argparse.Namespace(
        review=rid, round=n, sha256=entry["head"], reviewer="foreman", findings=str(findings), not_run=None,
        isolation="clean", model="-:-", effort="-:-", runcard=args.runcard, unit=None, design=None, plan=None))
  if code != 0:
    raise core.HandoffError(f"review record exited {code}")
  entry["phase"] = "collected"
  core.save_foreman(st, unit, data)
  rnd = review.load_round(st, rid, n)
  posted_now = iter(rnd["reviewers"]["foreman"]["findings"])  # in the order raised: `test_delta` pairs with it
  rnd["reviewers"]["foreman"]["findings"] = [slot or next(posted_now) for slot in slots]
  rnd["builder_contested"] = contested
  brief = r / "astra_brief.md"
  if "astra" in rnd["reviewers"] and brief.is_file():  # the lane's record names the brief the runner read
    rnd["reviewers"]["astra"]["brief_sha256"] = core.sha256_file(brief)
  rnd["what_ran"] = review.derive_what_ran(review.load_review(st, rid), rnd, entry)
  core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
  core.journal(st, f"{unit} round {n} collected: {len(lines)} foreman findings under {args.runcard}")
  print(f"collected: {len(lines)} foreman findings")
  return 0


def spec_findings(texts: list, spec: str) -> list:
  """The foreman's findings of kind `spec` (§7.6), `(location, claim)` each: the text must quote the frozen spec's
  `path:line` and the evidence, as the builder's `**Deviation (spec):**` comment does (`check_respec`, refused
  otherwise); the location is the quoted spec line. The claim stays on one line, with no ` | ` field separator."""
  found = []
  for text in texts:
    text = " ".join(text.split()).replace(" | ", " / ")
    check_respec("**Deviation (spec):** " + text, spec)
    found.append((next(m.group(0) for m in PATH_LINE.finditer(text) if not spec or cites(m.group(0), spec)), SPEC_CLAIM + text))
  return found


SPEC_CLAIM = "deviation (spec) unruled: "


def unruled_specs(last: dict, rulings: list) -> list:
  """The foreman's spec findings the previous posted round (`last`) holds open, `(location, claim)` each as
  `spec_findings` makes them: a finding of kind `spec` blocks until the owner rules it (§7.6), so a round that is
  not given `--spec` again still raises it, and `carry` keeps its id. A finding an `upheld`, `overruled` or
  `allowed` ruling names, or a recorded `<fid> respec` (read as an overrule), is settled and not raised again."""
  settled = {r.subject for r in rulings if r.kind in ("upheld", "overruled", "allowed")}
  prev = ((last.get("reviewers") or {}).get("foreman") or {}).get("findings") or []
  return [(f["location"], f["claim"]) for f in prev
          if f["disposition"] is None and f["claim"].startswith(SPEC_CLAIM) and f["id"] not in settled]


def require_non_terminal(unit: str, entry: dict) -> None:
  """A round is terminal in phase `posted`, or `collected` with a `not run` outcome (spec section 7)."""
  phase = entry.get("phase")
  if phase == "posted" or (phase == "collected" and (entry.get("outcome") or "").startswith("not run")):
    raise core.HandoffError(f"{unit} round {entry['round']} is terminal (`{phase}`)")


def prior_foreman_findings(st, rid, prior) -> list:
  """The `foreman` findings of the last posted round's file, or []."""
  if not prior or not rid:
    return []
  rnd = review.load_round(st, rid, prior) or {}
  return ((rnd.get("reviewers") or {}).get("foreman") or {}).get("findings") or []


def external_findings(st, rid, rnd_n) -> list:
  """The `external:<login>` findings `review ingest` recorded in a posted round's file, or []."""
  if not rnd_n or not rid:
    return []
  rnd = review.load_round(st, rid, rnd_n) or {}
  return [f for name, record in (rnd.get("reviewers") or {}).items() if name.startswith("external:")
          for f in record.get("findings") or []]


def parse_comments(text: str) -> tuple:
  """`comments.md` back: the builder login and `{kind, number, id, login, at, body}` per entry."""
  lines = text.splitlines()
  login = lines[0][len("builder: "):] if lines and lines[0].startswith("builder: ") else ""
  comments, current = [], None
  for line in lines[1:]:
    match = HEADER_RE.match(line)
    if match:
      current = {"kind": match.group(1), "number": int(match.group(2)), "id": int(match.group(3)), "login": match.group(4),
                 "at": match.group(5), "body": []}
      comments.append(current)
    elif current is not None:
      current["body"].append(line)
  for comment in comments:
    comment["body"] = "\n".join(comment["body"]).rstrip("\n")
  return login, comments


def recorded_times(foreman: dict) -> dict:
  """Each recorded ruling's comment id to `(posted_at, unread)`: the entry's time (the comment as recorded) and
  whether it is an `unread` entry, whose `posted_at` is the host's clock, not GitHub's, so the comment's own
  creation time stands while the comment is there and the host's time only once it is gone."""
  return {int(cid): (e.get("posted_at") or "", bool(e.get("unread"))) for e in foreman.get("rulings") or []
          if (cid := str(e.get("posted") or "").removeprefix("comment ")).isdigit()}


def foreman_findings(round_n: int, ci_verdict: str, body: str, scope: list, worktree: Path, changed: list, pr_body: str,
                     comments: list, login: str, prior_round, prior_ci_fid, commits: list = (), prior_tdd: dict = None,
                     prior_scope: dict = None, contest_of: dict = None, external: list = (),
                     earlier: set = frozenset(), disposed: set = frozenset(), posted: dict = None,
                     owners: list = (), recorded: list = (), decisions: list = (), recorded_at: dict = None,
                     issue_number: int = None, runs: dict = None, prior_dod: dict = None, present: set = None,
                     delta: list = None, prior_delta: dict = None, texts: dict = None, config: dict = None,
                     held: dict = None, open_prior: set = frozenset(), deferred: list = (),
                     consumed: frozenset = frozenset(), checked: list = None, specs: list = ()) -> tuple:
  """The foreman's high findings of spec section 11 in this order, which numbers the `foreman-<r>-<k>` ids: CI,
  the DoD items' fenced-output and `Exists` checks, the `dod-<n>` re-runs, the `test-delta:` entries, scope,
  tdd-order, deviations, the foreman's spec findings, contested, upheld, unreplied external; and `builder_contested[]` for the contested ones.
  `specs`, `(location, claim)` each, is the foreman's findings of kind `spec` (§7.6): the ones `--spec` raises in this round
  (`spec_findings`) and the ones the previous posted round holds open (`unruled_specs`), which `carry` then keeps under
  their ids; each is a blocker as a comment's deviation is, and numbered right after the comment deviations. Rulings
  and replies count only from the right author: a ruling is a `config.owners` login's comment `ruling_of` reads
  (spec section 13.2's one grammar) on the unit's issue, never the PR, or an entry of the record (`recorded`,
  `recorded_rulings`), replies come from the builder. Every `**Deviation**` line of a comment is one deviation; an `allowed` ruling on a posted
  round's tdd-order fid (`prior_tdd`, fid to failure) skips that failure as an overrule does, and no other.
  An external high or medium with no disposition is carried until a reply names it, or names a posted carried
  copy of it, in this round's comments or an earlier round's (`earlier`, the builder's reply ids there), or
  until one of its copies is settled (`disposed`, the copies whose disposition is set). Its group is the
  finding and every copy of it, a recorded contest of a copy included (`contest_of` followed back to the
  external id). A `contested` reply to such a finding is recorded in the round it comes in, a round late
  included, when no earlier round's comments hold a builder reply to any id of its group (`late`) and no
  ruling in this round's comments names it: a contest is recorded once (spec section 8, External review). An
  upheld ruling is answered by a `fixed` reply later than it (than its record's `posted_at`, `recorded_at`, when recorded) under the ruled id or under any id of its group;
  a recorded one binds whether or not its comment is still in `comments` (edited into prose or deleted), located
  on the unit's issue (`issue_number`). An `unread` entry's `posted_at` is the host's clock, so its comment's own
  time is the bound, and when that comment is gone the host's time is (a fixed reply before the ruling never
  counts). A reply
  to a foreman finding, `fixed` or `contested`, counts (toward the carry, or as a contest) only when it comes
  after the first posted round whose record holds it was posted (`held`, id to that round; `posted`, each posted
  round's `posted_at`): before that the copy did not exist. A contest counts when its id is open in the previous
  posted round's record (`open_prior`), carried copies included, and comes after that round was posted. The DoD re-run's `dod-<n>` highs (`runs`, `dod_runs`' record) follow the fenced-output check; an item
  number stays ruled by the owner's `dod-<n> allowed` or by an overrule or allowance of a posted `dod-<n>` fid
  (`prior_dod`, fid to item number), a contest's copy followed back to it. `present`, when given, is the `Exists`
  paths found before the runs; `texts`, item number to `(output, paste)`, the whole texts the counts are read from.
  `delta`, `test_delta`'s entries, is trimmed in place of every entry an owner's ruling allows (a posted fid's,
  through `prior_delta`, fid to its posted entries, the one a ruling binds matched by `delta_key`, or `test-delta <file> allowed`; a judges'
  recorded overrule settles a fid's entry as the owner's does) and each entry left is a `test-delta:` high, after the `dod-<n>` ones and before scope.
  The worktree's findings (fenced output through tdd-order) are `worktree_findings`' over these facts, or `checked`
  when given: `collect` passes `worktree_checks`' own, the one function `precheck` calls too (U67)."""
  found, contested = [], []
  links = contest_of or {}

  def origin(fid):
    seen = set()
    while fid in links and fid not in seen:
      seen.add(fid)
      fid = links[fid]
    return fid

  groups = {}
  for fid in set(links) | {f["id"] for f in external}:
    groups.setdefault(origin(fid), set()).add(fid)
  open_ext = {f["id"] for f in external if f["disposition"] is None and f["severity"] in ("high", "medium")
              and not groups[f["id"]] & set(disposed)}
  open_ext |= {cid for cid in links if origin(cid) in open_ext}
  late = {fid for fid in open_ext if not groups[origin(fid)] & set(earlier)}
  if ci_verdict != "ci green":
    found.append(("ci", f"CI not green on this head: {ci_verdict}"))
  # The rulings: an owner's form comment read by `ruling_of`, and the record (`rulings[]`, the judges' post included)
  # (spec section 13.2: a recorded ruling is never changed by a later comment, so the record wins on its comment ids and subjects)
  # a live `upheld` on a fid of the record's `followups[]` is a refused undo (spec section 5.2): it never blocks
  # a consumed comment (a recorded proceed's, `consumed_comments`) rules nothing, edited or not (spec section 4.2)
  rulings = binding_rulings([c for c in comments if c["kind"] == "issue"], owners, recorded, decisions,
                            deferred=deferred, consumed=consumed)  # an issue comment alone rules
  by_id = {c["id"]: c for c in comments}
  if checked is None:  # `worktree_checks`' findings, else the same checks over the facts given here
    checked = worktree_findings(body, scope, worktree, changed, pr_body, commits, rulings, links, runs=runs, texts=texts,
                                config=config, present=present, delta=delta, times=ruling_times(comments, recorded_at or {}),
                                prior={"dod": prior_dod, "delta": prior_delta, "scope": prior_scope, "tdd": prior_tdd})
  found += checked
  ruled = {int(r.subject) for r in rulings if r.kind == "option" and r.subject.isdigit()}
  for c in comments:  # every `**Deviation**` heading a comment folds; one ruling naming the comment rules them all
    for line in c["body"].splitlines():
      kind = DEVIATION_RE.match(line)
      if kind and kind.group(1) != "other" and c["id"] not in ruled:
        found.append((where(c), f"deviation ({kind.group(1)}) unruled"))
  found += specs  # the foreman's own findings of kind `spec` (§7.6), raised in this round: blockers as a builder's comment is
  if prior_round:
    settled = settled_fids(rulings, links, prior_dod or {}, prior_delta or {}, prior_scope or {},
                           ruling_times(comments, recorded_at or {}))
    for c in comments:
      reply = REPLY_RE.match(c["body"])
      if not reply or c["login"] != login or reply.group(2) != "contested":
        continue
      fid = reply.group(1)
      if fid == prior_ci_fid or settled(fid) or (fid not in open_prior and fid not in late):
        continue
      if posted is not None and not timely(fid, c["at"], posted, {fid: prior_round} if fid in open_prior else held):
        continue  # a contest of a copy not yet posted contests nothing; one the previous round already took is not new
      reason = (reply.group(3) or "").strip()
      found.append((where(c), f"contested {fid}: {reason}"))
      contested.append({"fid": f"foreman-{round_n}-{len(found)}", "reason": reason})
    times = recorded_at or {}
    for ruling in rulings:
      c = by_id.get(ruling.comment_id)  # the comment the ruling names: its time bounds the `fixed` reply
      at, unread = times.get(ruling.comment_id, ("", False))
      if c is None and ruling.comment_id in times:  # a recorded ruling whose comment is gone or no longer a form:
        c = {"kind": "issue", "number": issue_number, "id": ruling.comment_id, "at": at if unread else ""}  # an unread
      if ruling.kind not in ("upheld", "overruled") or c is None:  # one's stand-in takes the host's time, the only one left
        continue
      fid = ruling.subject
      answers = {fid, links.get(fid, fid)} | groups.get(origin(fid), set())  # the ruled finding, or any id of its group
      since = max(c["at"], "" if unread else at)  # from its record's time; an unread one from the comment's
      fixed = any(o["login"] == login and o["at"] > since and (m := REPLY_RE.match(o["body"]))
                  and m.group(1) in answers and m.group(2) == "fixed" for o in comments)
      if ruling.kind == "upheld" and not fixed:
        found.append((where(c), f"upheld {fid}: no `fixed` reply"))
  replied = {m.group(1) for c in comments if c["login"] == login and (m := REPLY_RE.match(c["body"]))
             and (posted is None or timely(m.group(1), c["at"], posted, held))} | set(earlier)
  for f in external:
    if f["id"] not in open_ext:
      continue
    if not groups[f["id"]] & replied:
      found.append((f["location"], f"unreplied {f['id']}: {f['claim']}"))
  lines = [f"foreman-{round_n}-{i} | high | {location} | regression: no | {claim}" for i, (location, claim) in enumerate(found, 1)]
  return lines, contested


def settled_fids(rulings: list, links: dict, prior_dod: dict, prior_delta: dict, prior_scope: dict = None,
                 times: dict = None):
  """Whether a fid is settled by an owner's or the judges' ruling (spec section 3.5), the predicate a builder's contest
  is dropped by: the fid, or a fid it derives from, is ruled `upheld`, `overruled` or `allowed`. A ruling rules its
  subject and what the subject names down `links` (a ruling on a contest's or a carried copy rules the original), as
  `worktree_findings`' chain reads it. The derivation is the foreman's own posted record alone, never another
  reviewer's claim or a contest's wording: a contest's or a carried copy's link (`links`) down to what it names, a
  `dod-<n>` fid (`prior_dod`) whose item is allowed (`dod-<n> allowed`) or whose item an overruled or allowed fid of
  the record raised, a test-delta fid (`prior_delta`) whose file is allowed (`test-delta <file> allowed`), and a scope
  fid (`prior_scope`) whose path the owner's `test-delta <path> allowed` widened Scope for. An overrule or allowance of
  a test-delta fid settles it only while its open entry, the last posted round's, has the key of the entry the ruling
  bound (`bound_entry`, by the ruling's time in `times`): a carried copy's later change is no settled one."""
  prior_scope, times = prior_scope or {}, times or {}

  def down(fid):
    out = [fid]
    while out[-1] in links and links[out[-1]] not in out:
      out.append(links[out[-1]])
    return out
  reaches = {}  # each fid to the rulings that rule it, on it or on a copy naming it
  for r in rulings:
    if r.kind in ("upheld", "overruled", "allowed"):
      for f in down(r.subject):
        reaches.setdefault(f, []).append(r)

  def covers(fid, r):
    if r.kind == "upheld" or fid not in prior_delta:
      return True
    bound, open_entry = bound_entry(prior_delta[fid], times.get(r.comment_id)), prior_delta[fid][-1][1]
    return delta_key(bound) in (delta_key(open_entry), delta_key(open_entry, legacy=True))
  items = {int(r.subject[4:]) for r in rulings if r.kind == "allowed" and re.fullmatch(r"dod-\d+", r.subject)}
  items |= {prior_dod[f] for f, rs in reaches.items() if f in prior_dod and any(r.kind != "upheld" for r in rs)}
  files = {r.subject for r in rulings if r.kind == "allowed-file"}
  widened = {r.subject for r in rulings if r.kind == "allowed-file" and not r.login.startswith("judges:")}

  def settled(fid):
    return any(any(covers(f, r) for r in reaches.get(f, ())) or prior_dod.get(f, -1) in items
               or delta_file(prior_delta.get(f)) in files or prior_scope.get(f) in widened for f in down(fid))
  return settled


def delta_file(held):
  """The file of a posted test-delta fid's entries (`posted_findings`' `delta`), or None."""
  return held[0][1]["file"] if held else None


def bound_entry(held: list, at) -> dict:
  """The entry a settlement made at `at` binds of a fid posted in `held` (`(posted_at, entry)` in round order): the
  fid's entry in the last round posted before the ruling's comment or record, never a later one a carried copy of
  the fid picks up; the first when no round was posted before it, or the ruling's time is unknown (`at` None)."""
  before = [entry for posted_at, entry in held if at is not None and posted_at < at]
  return before[-1] if before else held[0][1]


def delta_key(entry: dict, legacy: bool = False) -> tuple:
  """A test-delta entry's settlement key (spec section 3.5): file, kind, enclosing test, stripped line text, the
  base line's text and the occurrence; a 1.2.1 entry (no `test`), or any entry when `legacy`, is keyed on its base
  commit and line, the key a 1.2.1 settlement is still honoured on."""
  if legacy or "test" not in entry:
    return entry["file"], entry["base_commit"], entry["base_line"], entry["kind"]
  return entry["file"], entry["kind"], entry["test"], entry["text"], entry["base_text"], entry["occurrence"]


def ruling_times(comments: list, recorded: dict) -> dict:
  """Each ruling's time by its comment id, the bound `bound_entry` reads: a comment's own creation time, and a
  recorded ruling's record time (`recorded`, `recorded_times`' map) in its place, but for an `unread` record (the
  host's clock) while its comment is still there."""
  times = {c["id"]: c["at"] for c in comments if c.get("at")}
  for cid, (at, unread) in recorded.items():
    if at and not (unread and cid in times):
      times[cid] = at
  return times


def posted_findings(st, rid, rounds: list) -> dict:
  """What the posted rounds' foreman findings settle, the one reading `collect` and `precheck` share (spec section
  6.3), each fid to: `scope` its out-of-Scope path (an overrule widens the Scope for good), `tdd` its tdd-order
  failure and `dod` its item number (a ruled one stays ruled in every later round), `delta` its `test_delta` entry
  in each posted round holding it, `(posted_at, entry)` in round order (a carried copy picks up a later entry; a
  settlement binds the one it ruled on, `bound_entry`), `links` the fid a contest or carried copy names (a reply
  may answer under it); `disposed` the copies with a disposition (a settled copy settles what it carries)."""
  out = {"scope": {}, "tdd": {}, "dod": {}, "delta": {}, "links": {}, "disposed": set()}
  for e in rounds or []:
    if e.get("phase") != "posted":
      continue
    findings = prior_foreman_findings(st, rid, e["round"])
    deltas = [f["id"] for f in findings if f["claim"].startswith("test-delta: ")]
    for fid, d in zip(deltas, e.get("test_delta") or []):
      out["delta"].setdefault(fid, []).append((e.get("posted_at") or "", d))
    for f in findings:
      if f["claim"] == "changed path outside Scope paths":
        out["scope"][f["id"]] = f["location"]
      if f["claim"].startswith("tdd-order: "):
        out["tdd"][f["id"]] = f["claim"].removeprefix("tdd-order: ")
      if (m := re.match(r"dod-(\d+): ", f["claim"])):
        out["dod"][f["id"]] = int(m.group(1))
      if (m := re.match(r"(?:contested|unreplied) (\S+):", f["claim"])):
        out["links"][f["id"]] = m.group(1)
        if f.get("disposition") is not None:
          out["disposed"].add(f["id"])
  return out


def worktree_checks(worktree: Path, merge_base: str, head: str, body: str, scope: list, pr_body: str, rulings: list,
                    links: dict, prior: dict, deadline: float = None, out_dir: Path = None, gh: str = None,
                    hold=(), config: dict = None, times: dict = None) -> tuple:
  """The foreman's checks that need only the worktree, the one function `collect` and `precheck` both call
  (spec section 6.3): the changed paths, commits, `Exists` paths and test delta are read, the DoD `Run` items whose
  output `pr_body` pastes run (`dod_runs`, outputs under `out_dir`; none when it is None) with the worktree's git
  config and every `hold` path held whole and written back, then `worktree_findings` reads them, with the rulings'
  times (`times`, `ruling_times`: both callers pass the same, so a settlement binds the same entry). Returns
  `(found, facts)`: `(location, claim)` per finding and `{changed, commits, present, delta, runs, texts, pasted}`."""
  # NUL-separated: a Scope path may hold a space, and a quoted or split name would be reported outside Scope
  changed = [p for p in core.run_git(["diff", "--name-only", "-z", merge_base, "HEAD"], worktree).split("\0") if p]
  commits = tdd_order.commits_of(worktree, merge_base)
  items = body_mod.dod_items(body)
  present = {path for _, kind, path in items if kind == "exists" and (worktree / path).exists()}
  named = {test_path for _, test_path, _ in body_mod.step_paths(body) if test_path}
  delta = test_delta(*delta_files(worktree, merge_base, head, commits, named), named)
  pasted = {int(m.group(1)): m.group(2) for m in DOD_RESULT_RE.finditer(pr_body)}
  runs, texts = {}, {}
  if out_dir is not None:  # every input is read; the files a run could edit are held whole, then the `Run` items run
    git_config = worktree / core.run_git(["rev-parse", "--git-common-dir"], worktree).strip() / "config"
    held = {path: path.read_bytes() if path.is_file() else None for path in [*hold, git_config]}
    try:
      runs = dod_runs([(i, cmd, last_line(pasted[i])) for i, kind, cmd in items if kind == "run" and i in pasted], worktree,
                      run_env(gh or shutil.which("gh") or "gh", worktree), deadline, out_dir)
    finally:  # written back whole when a run changed them: an edit a run made to them is overwritten, nothing else is
      for path, raw in held.items():
        if raw is None:
          path.unlink(missing_ok=True)
        elif not path.is_file() or path.read_bytes() != raw:
          core.atomic_write(path, raw)
    out = lambda i: out_dir / f"{i}.out"
    texts = {int(i): (out(i).read_text(encoding="utf-8", errors="replace") if out(i).is_file() else "", pasted[int(i)])
             for i in runs}  # each side's whole text: its last count line is compared, not its last line
  found = worktree_findings(body, scope, worktree, changed, pr_body, commits, rulings, links, runs=runs, texts=texts,
                            config=config, present=present, delta=delta, prior=prior, times=times)
  return found, {"changed": changed, "commits": commits, "present": present, "delta": delta, "runs": runs,
                 "texts": texts, "pasted": pasted}


def worktree_findings(body: str, scope: list, worktree: Path, changed: list, pr_body: str, commits: list, rulings: list,
                      links: dict, runs: dict = None, texts: dict = None, config: dict = None, present: set = None,
                      delta: list = None, prior: dict = None, times: dict = None) -> list:
  """`(location, claim)` per worktree finding in the foreman's order: the fenced-output and `Exists` checks, the
  `dod-<n>` re-runs, the `test-delta:` entries (`delta` trimmed in place of what an owner's ruling allows), scope,
  tdd-order. `prior` holds the posted rounds' fids: `dod` (to item number), `delta` (to its posted entries), `scope`
  (to its path), `tdd` (to its failure); `links` the contest links a ruling on a copy follows back to the original;
  `times` each ruling's time by comment id (`ruling_times`), which binds a test-delta settlement to its entry."""
  prior, links, found = prior or {}, links or {}, []
  prior_dod, prior_delta, prior_scope, prior_tdd = (prior.get(k) or {} for k in ("dod", "delta", "scope", "tdd"))
  results = {int(m.group(1)) for m in DOD_RESULT_RE.finditer(pr_body)}
  for n, kind, text in body_mod.dod_items(body):
    if kind == "exists" and not (text in present if present is not None else (worktree / text).exists()):
      found.append((text, f"Exists item {n}: path absent"))
    elif kind == "run" and n not in results:
      found.append(("pr_body.md", f"Run item {n}: no fenced output"))

  # a ruling on a contest's copy (`contested <fid>: …`) rules the finding it contests, down the chain to the original
  def chain(fid):
    out = {fid}
    while fid in links and links[fid] not in out:
      fid = links[fid]
      out.add(fid)
    return out
  overruled = set().union(*(chain(r.subject) for r in rulings if r.kind == "overruled"))
  allowed = set().union(*(chain(r.subject) for r in rulings if r.kind == "allowed"))
  ruled = {int(r.subject[4:]) for r in rulings if r.kind == "allowed" and re.fullmatch(r"dod-\d+", r.subject)}
  found += dod_findings(body, runs or {}, ruled | {item for fid, item in prior_dod.items() if fid in overruled | allowed},
                        texts, config)
  if delta is not None:  # the test delta: an allowed entry or file is dropped from the round's record, then each left is a high
    # a settlement, the owner's or the judges' recorded overrule, binds the key of the entry it ruled on (`bound_entry`,
    # by the ruling's time), matched on the test and the line text (spec section 3.5), so a merge of main or a line
    # shift does not re-raise it; a 1.2.1 entry's on its base commit and line
    keys = {delta_key(bound_entry(prior_delta[fid], (times or {}).get(r.comment_id)))
            for r in rulings if r.kind in ("overruled", "allowed") for fid in chain(r.subject) if prior_delta.get(fid)}
    # a file allowance, the owner's alone, binds whole: unrecorded, its comment; recorded (`decision rule` keeps
    # `test-delta <file> allowed` beside the per-fid ones), the record, whatever a later edit or deletion of the comment does
    files = {r.subject for r in rulings if r.kind == "allowed-file" and not r.login.startswith("judges:")}
    delta[:] = [e for e in delta if e["file"] not in files and delta_key(e) not in keys and delta_key(e, legacy=True) not in keys]
    found += [(f"{e['file']}:{e['line']}", f"test-delta: {e['file']}:{e['line']} {e['kind']}") for e in delta]
  widened = {path for fid, path in prior_scope.items() if fid in overruled}  # an owner's overrule widens the Scope
  # and so does an owner's `test-delta <file> allowed`, for that file, as an overruled scope finding's path (spec section 3.5)
  widened |= {r.subject for r in rulings if r.kind == "allowed-file" and not r.login.startswith("judges:")}
  in_scope = lambda path: any(path == s or path.startswith(s.rstrip("/") + "/") for s in scope)  # a directory covers its files
  # a path holding a control character (a newline would split the finding's line) is shown JSON-quoted, as posted
  shown = lambda path: json.dumps(path, ensure_ascii=False) if any(ord(c) < 32 or ord(c) == 127 for c in path) else path
  found += [(shown(path), "changed path outside Scope paths") for path in changed
            if not in_scope(path) and shown(path) not in widened]
  # a tdd-order failure a posted round raised and a ruling overruled or allowed is skipped; any other failure is raised
  skipped = {text for fid, text in prior_tdd.items() if fid in overruled | allowed}
  tests = {n: t for n, t, _ in body_mod.step_paths(body)}
  for failure in tdd_order.check(body, list(commits)):
    if failure in skipped:
      continue
    step = re.match(r"S(\d+):", failure) or re.search(r"test\(S(\d+)\)", failure)
    found.append((tests.get(int(step.group(1)), "tests/") if step else "tests/", f"tdd-order: {failure}"))
  return found


def timely(fid: str, at: str, posted: dict, held: dict = None) -> bool:
  """A reply to a foreman finding counts only after the round `held` names for it (id → the first posted round whose
  record holds it) was posted (`posted`: round → `posted_at`); any other id always."""
  r = (held or {}).get(fid)
  return not fid.startswith("foreman-") or (r in posted and at > posted[r])


def open_of(last) -> set:
  """The previous posted round's open fids, which a contest may name: a finding with no disposition. A medium
  deferred by triage carries `deferred: triage <n>` (spec section 5.2), so it is not open, and no contest of it is
  carried as a blocking foreman finding."""
  if not last:
    return set()
  return {f["id"] for f in review.findings_of(last) if f["disposition"] is None}


def carry(lines: list, contested: list, last: dict, prior, contest_of: dict, rulings: list) -> tuple:
  """Spec section 6.5, the carry: a finding waiting on a ruling is posted once. From the previous posted round's
  record (`last`, round `prior`) alone, an open derived foreman finding this round raises again with the same claim
  and location keeps its id, and an open builder contest of a finding the foreman does not derive, with no ruling
  on it or on what it contests, is copied with its `builder_contested` entry; each copy gets `carried_from` and
  leaves `lines`. Returns `(lines left, slots, contested)`: `slots` holds a copy in a carried line's place and
  None in a posted one's, then the contest copies."""
  prev = [f for f in ((last.get("reviewers") or {}).get("foreman") or {}).get("findings") or [] if f["disposition"] is None]
  ruled = {r.subject for r in rulings}
  bc = {b["fid"]: b for b in last.get("builder_contested") or []}
  contests, kept, slots = [], [], []
  for f in prev:
    if f["id"] in bc and not contest_of.get(f["id"], "foreman-").startswith("foreman-") \
       and not {f["id"], contest_of[f["id"]]} & ruled:
      contests.append({**f, "carried_from": prior})
      contested = contested + [bc[f["id"]]]
  same = {}  # each earlier finding matches at most once, in order: two alike keep their two ids
  for f in prev:
    if f["id"] not in bc and not f["claim"].startswith("contested "):
      same.setdefault((f["location"], f["claim"]), []).append(f)
  for line in lines:
    _, _, location, _, claim = line.split(" | ", 4)
    alike = same.get((location, claim))
    slots.append({**alike.pop(0), "carried_from": prior} if alike else None)
    if slots[-1] is None:
      kept.append(line)
  return kept, slots + contests, contested


def where(comment: dict) -> str:
  return f"{comment['kind']} #{comment['number']} comment {comment['id']}"
