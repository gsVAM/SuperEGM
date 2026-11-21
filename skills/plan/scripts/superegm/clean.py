# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the clean subcommand (spec section 11).

"""superegm clean: remove a unit's review and builder worktrees and its private refs once every
launch and round is terminal; keeps what it cannot prove."""

import json
import os
import re
import signal
import subprocess
from pathlib import Path

import superegm as core
from superegm.launch import load_launches, terminal
from superegm.report import unit_state, unit_view

WRITES = frozenset()  # the store kinds this subcommand writes
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SKILLS = frozenset(["clean", "wave", "integrate"])  # the skills whose card this subcommand accepts
KILL_WAIT = 5  # seconds between SIGTERM and SIGKILL


def register(subparsers):
  p = core.add_parser(subparsers, "clean", "remove a unit's worktrees and private refs once every launch and round is terminal; "
                         "--auto cleans every landed, merged or stopped unit and refuses nothing")
  group = p.add_mutually_exclusive_group()
  group.add_argument("--unit", help="the unit to clean (not with --auto)")
  group.add_argument("--auto", action="store_true",
                     help="clean every landed, merged or stopped unit that is terminal, silently skipping the rest (not with --unit)")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  try:
    core.require_runcard(args, SKILLS)
    return clean(args)
  except core.HandoffError as error:
    if args.auto:  # `--auto` refuses nothing: a refused card or a missing checkout is one line and exit 0
      print(f"clean: {error}")
      return 0
    if str(error).startswith("runcard:"):
      raise
    raise core.HandoffError(f"clean: {error}") from None
  except Exception as error:  # an unparseable card or config under `--auto` is one line and exit 0; `--unit` keeps its traceback
    if not args.auto:
      raise
    print(f"clean: {error}")
    return 0


def clean(args):
  root = core.git_toplevel(Path.cwd())
  if args.auto:
    return clean_auto(root, args)
  if not args.unit:
    raise core.HandoffError("pass --unit <unit> or --auto")
  clean_unit(root, core.store(root), args.unit)
  return 0


def clean_auto(root, args):
  """The wave's and integrate's end-of-invocation sweep: every unit that has `landed` (`report.unit_state`), whose recorded pull
  request is merged (its issue still open, which `status` does not mark landed) or that is `stopped`, and that `terminal_problems`
  passes, one `<unit> cleaned` line per unit cleaned. Any other unit is skipped silently, and so is a folder that holds only round
  records; a line a person should read (a process that cannot be listed, signalled or killed, uncommitted changes in a legacy tree, a
  symlinked folder, a removal git refused) still prints, and so does `clean --auto: <unit or handoff>: <error>` for any error. A refused card
  prints `clean: <reason>`. It always exits 0, so the caller never stops."""
  try:
    plan, st = core.locate(args)
    handoff = core.Handoff(plan, st)
    state, card, now, order = handoff.state, core.load_card(st, args.runcard), core.NOW(), list(handoff.graph.order)
  except Exception as error:
    print(f"clean --auto: handoff: {error}")
    return 0
  for uid in order:
    try:
      foreman, entries = core.load_foreman(st, uid), load_launches(st, uid)
      word = unit_state(uid, unit_view(state, uid), foreman, entries, card, st.config, now)
      merged = ((state.get("units") or {}).get(uid, {}).get("pr") or {}).get("merged_at")
      if (word in ("landed", "stopped") or merged) and not terminal_problems(st, uid) and has_remnants(root, st, uid):
        clean_unit(root, st, uid, quiet=True)
    except Exception as error:
      print(f"clean --auto: {uid}: {error}")
  return 0


def linked(st, unit, tree):
  """True when `tree`, or any folder above it inside the store (`review/`, `review/<unit>/`, `pr<n>/`, `worktrees/<unit>/`), is a
  symlink: a link can reach another unit's tree, so nothing is signalled or removed through one."""
  store = st.path("review", unit, "pr0").parent.parent.parent
  while tree != store and tree != tree.parent:
    if tree.is_symlink():
      return True
    tree = tree.parent
  return False


def review_dir(st, unit):
  return st.path("review", unit, "pr0").parent


def pr_folders(st, unit):
  """The `review/<unit>/pr<digits>` folders, none when `review/<unit>` is itself a link (it could be another unit's); a folder
  named `private` or `pr-old` is not one."""
  folder = review_dir(st, unit)
  if linked(st, unit, folder):
    return []
  return sorted(p for p in folder.glob("pr*") if p.is_dir() and re.fullmatch(r"pr\d+", p.name))


def pr_numbers(st, unit):
  """The pull request numbers whose private refs the unit owns: the recorded `units.<unit>.pr.number` and each `review/<unit>/pr<n>`
  (none through a linked unit folder)."""
  numbers = {p.name[2:] for p in pr_folders(st, unit)}
  try:
    state = json.loads(st.path("state").read_text(encoding="utf-8"))
    number = ((state.get("units") or {}).get(unit, {}).get("pr") or {}).get("number")
    if isinstance(number, int) and not isinstance(number, bool):
      numbers.add(str(number))
  except (OSError, ValueError, AttributeError):
    pass
  return sorted(numbers)


def private_refs(root, st, unit):
  """The `refs/superegm/pr/<n>` and `refs/superegm/pr-base/<n>` that exist for the unit's pull requests."""
  wanted = [f"refs/superegm/{kind}/{n}" for n in pr_numbers(st, unit) for kind in ("pr", "pr-base")]
  return [ref for ref in wanted if core.run_git(["rev-parse", "--verify", "--quiet", ref], root, check=False).strip()]


def first_line(error):
  return str(error).splitlines()[0] if str(error) else "git failed"


def review_trees(root, st, unit):
  """`{folder: (tree, legacy)}` for each `review/<unit>/pr<n>` folder whose `worktree` child (or, legacy, itself) git has registered."""
  registered, found = set(core.registered_worktrees(root)), {}
  for folder in pr_folders(st, unit):
    if (folder / "worktree").resolve() in registered:
      found[folder] = (folder / "worktree", False)
    elif folder.resolve() in registered:
      found[folder] = (folder, True)
  return found


def builder_trees(root, st, unit):
  """`(trees, recorded, registered)`: the `worktrees/<unit>/r<n>` folders, the worktrees a launch records, those git has registered."""
  recorded = {Path(entry["worktree"]).resolve() for entry in load_launches(st, unit)}
  folder = st.path("worktrees", unit)
  trees = [] if linked(st, unit, folder) else sorted(p for p in folder.glob("r*") if p.is_dir())
  return trees, recorded, set(core.registered_worktrees(root))


def has_remnants(root, st, unit):
  """Something `clean_unit` would remove: a registered review worktree (the `pr<n>/worktree` child or a legacy `pr<n>`), or a builder
  `r<n>` folder that a launch records and git has registered, or a private ref of the unit's pull requests. A folder kept by rule
  (unrecorded, unregistered) is not one."""
  if review_trees(root, st, unit) or private_refs(root, st, unit):
    return True
  trees, recorded, registered = builder_trees(root, st, unit)
  return any(tree.resolve() in recorded and tree.resolve() in registered for tree in trees)


def is_dirty(tree):
  return bool(core.run_git(["status", "--porcelain"], tree, check=False).strip())


def clean_unit(root, st, unit, quiet=False):
  """Remove the unit's registered worktrees and refs. `quiet` (`--auto`) leaves out the routine `kept ...: not a worktree` and
  `no launch records it` lines; a line that warns always prints. `<unit> cleaned` is journalled, and the unit's private refs deleted, only
  when no tree was kept for a reason (a symlink, a process that cannot be listed or signalled or survives SIGKILL, uncommitted changes in a
  legacy tree, a removal git refused, a ref git cannot delete); `not a worktree` and `no launch records it` do not withhold it."""
  problems = terminal_problems(st, unit)
  if problems:
    raise core.HandoffError(problems[0])

  def note(line):
    if not quiet:
      print(line)

  complete = True
  for folder in (review_dir(st, unit), st.path("worktrees", unit)):
    if linked(st, unit, folder):  # a link can reach another unit's folder: nothing is signalled, removed or deleted through it
      print(f"kept {folder}: symlink")
      complete = False
  refs = private_refs(root, st, unit)  # read before any `pr<n>` folder goes: a legacy tree's folder names its number
  registered_review = review_trees(root, st, unit)
  for folder in pr_folders(st, unit):
    if folder not in registered_review:
      note(f"kept {folder}: not a worktree")
      continue
    tree, legacy = registered_review[folder]
    if linked(st, unit, tree):
      print(f"kept {tree}: symlink")
      complete = False
      continue
    if legacy and is_dirty(tree):  # a legacy `pr<n>` may be a person's tree: never forced, never signalled
      print(f"kept {tree}: uncommitted changes")
      complete = False
      continue
    if not stop_leftovers(st, unit, tree):
      complete = False
      continue
    try:
      core.remove_worktree(root, tree, force=not legacy)  # the review child is the store's: its `pr<n>/r<n>` records stay
    except core.HandoffError as error:  # git's own reason: `uncommitted changes` only where the dirty-legacy refusal says so
      print(f"kept {tree}: {first_line(error)}")
      complete = False
  trees, recorded, registered = builder_trees(root, st, unit)
  for tree in trees:
    real = tree.resolve()
    if linked(st, unit, tree):
      print(f"kept {tree}: symlink")
      complete = False
    elif real not in recorded:
      note(f"kept {tree}: no launch records it")
    elif real not in registered:
      note(f"kept {tree}: not a worktree")
    elif stop_leftovers(st, unit, tree):
      try:
        core.run_git(["worktree", "remove", "--force", str(tree)], root)
      except core.HandoffError as error:
        print(f"kept {tree}: {first_line(error)}")
        complete = False
    else:
      complete = False
  core.run_git(["worktree", "prune"], root, check=False)
  try:
    st.path("worktrees", unit).rmdir()  # the unit's folder goes with its last worktree; a kept one stays
  except OSError:
    pass
  if complete:
    for ref in refs:  # the refs go once nothing of the unit was kept, whether or not a review tree existed
      try:
        core.run_git(["update-ref", "-d", ref], root)
      except core.HandoffError as error:  # a ref git cannot delete still counts as left, so the unit is not cleaned
        print(f"kept {ref}: {first_line(error)}")
        complete = False
  if complete:
    core.journal(st, f"{unit} cleaned")
    print(f"{unit} cleaned")


class ListError(Exception):
  """`lsof` could not list the processes; the text is the reason."""


def parse_process_table(text):
  """`(pid, command, cwd)` of each process in `lsof -Fpcn` output (`p<pid>`, `c<command>` and `n<cwd>` lines)."""
  rows, pid, command = [], None, ""
  for line in text.splitlines():
    if line.startswith("p") and line[1:].isdigit():
      pid, command = int(line[1:]), ""
    elif line.startswith("c"):
      command = line[1:]
    elif line.startswith("n") and pid is not None:
      rows.append((pid, command, line[1:]))
  return rows


def process_table():
  """`(pid, command, cwd)` of every process `lsof -a -d cwd` lists; `ListError` when `lsof` is missing, times out or exits non-zero with no records."""
  try:
    result = subprocess.run(["lsof", "+c", "0", "-a", "-d", "cwd", "-Fpcn"], capture_output=True, text=True, timeout=60)
  except FileNotFoundError:
    raise ListError("lsof is missing") from None
  except subprocess.TimeoutExpired:
    raise ListError("lsof timed out") from None
  except (OSError, subprocess.SubprocessError) as error:
    raise ListError(str(error)) from None
  table = parse_process_table(result.stdout)
  if result.returncode != 0 and not table:  # an exit 1 that still lists processes (some not readable) is a usable listing
    raise ListError(f"lsof exited {result.returncode}")
  return table


def signal_process(pid, sig):
  """Send `sig`; a process already gone is no error, a `PermissionError` is the caller's."""
  try:
    os.kill(pid, sig)
  except ProcessLookupError:
    pass


def is_alive(pid):
  try:
    os.kill(pid, 0)
  except ProcessLookupError:
    return False
  except PermissionError:
    return True
  return True


def leftovers(tree):
  """`(pid, command)` of every `node` or `python*` process (any case: macOS reports `Python`) whose cwd lies inside `tree`
  (a path-component test, never a prefix); this process and its parent are left out."""
  inside, found = tree.resolve(), []
  for pid, command, cwd in process_table():
    name = command.lower()
    if pid in (os.getpid(), os.getppid()) or not (name == "node" or name.startswith("python")):
      continue
    try:
      Path(cwd).resolve().relative_to(inside)
    except ValueError:
      continue
    found.append((pid, command))
  return found


def stop_leftovers(st, unit, tree):
  """SIGTERM, after `KILL_WAIT` seconds SIGKILL, each leftover process in `tree`, journalled `<unit> killed <pid> <command>`;
  False, with a `kept` line, when the processes cannot be listed, one cannot be signalled or one outlives SIGKILL (the caller keeps the tree)."""
  try:
    found = leftovers(tree)
  except ListError as error:
    print(f"kept {tree}: cannot list its processes ({error})")
    return False
  blocked = []

  def send(pid, sig):
    try:
      signal_process(pid, sig)
    except PermissionError:
      if pid not in blocked:
        blocked.append(pid)

  for pid, _command in found:
    send(pid, signal.SIGTERM)
  found = [(pid, command) for pid, command in found if pid not in blocked]
  deadline = core.NOW() + KILL_WAIT
  while core.NOW() < deadline and any(is_alive(pid) for pid, _command in found):
    core.SLEEP(1)
  survivors = []
  for pid, command in found:
    if is_alive(pid):
      send(pid, signal.SIGKILL)
      core.SLEEP(1)
    if pid in blocked:
      continue
    if is_alive(pid):
      survivors.append((pid, command))
    else:
      core.journal(st, f"{unit} killed {pid} {command}")
  for pid in blocked:
    print(f"kept {tree}: process {pid} cannot be signalled")
  for pid, command in survivors:
    print(f"kept {tree}: {command} {pid} survives SIGKILL")
  return not survivors and not blocked


def terminal_problems(store, unit):
  """Every launch without its exit file or `interrupted`, every round not `posted` nor
  `collected` with a `not run` outcome (spec section 4)."""
  problems = [f"{unit} launch {entry['round']} is not terminal" for entry in load_launches(store, unit) if not terminal(entry)]
  for entry in core.load_foreman(store, unit)["rounds"]:
    if not (entry.get("phase") == "posted" or (entry.get("phase") == "collected" and str(entry.get("outcome") or "").startswith("not run"))):
      problems.append(f"{unit} round {entry.get('round')} is not terminal ({entry.get('phase')})")
  return problems
