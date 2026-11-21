# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the clean subcommand (spec section 11).

"""superegm clean: remove a unit's review and builder worktrees and its private refs once every
launch and round is terminal; keeps what it cannot prove."""

import os
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
  p.add_argument("--unit")
  p.add_argument("--auto", action="store_true", help="clean every landed, merged or stopped unit that is terminal, silently skipping the rest")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  try:
    return clean(args)
  except core.HandoffError as error:
    raise core.HandoffError(f"clean: {error}") from None


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
  passes, one line per unit cleaned; any other unit, and any unit `clean_unit` refuses, is skipped silently, so the caller never stops."""
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  state, card, now = handoff.state, core.load_card(st, args.runcard), core.NOW()
  for uid in handoff.graph.order:
    foreman, entries = core.load_foreman(st, uid), load_launches(st, uid)
    word = unit_state(uid, unit_view(state, uid), foreman, entries, card, st.config, now)
    merged = ((state.get("units") or {}).get(uid, {}).get("pr") or {}).get("merged_at")
    if (word in ("landed", "stopped") or merged) and has_remnants(root, st, uid):
      try:
        clean_unit(root, st, uid)
      except core.HandoffError:
        pass
  return 0


def has_remnants(root, st, unit):
  """A registered review worktree (the `pr<n>/worktree` child or a legacy `pr<n>`) or a builder `r<n>` folder of `unit` is still there."""
  registered = set(core.registered_worktrees(root))
  folders = [p for p in st.path("review", unit, "pr0").parent.glob("pr*") if p.is_dir()]
  return any(p.resolve() in registered or (p / "worktree").resolve() in registered for p in folders) \
      or any(p.is_dir() for p in st.path("worktrees", unit).glob("r*"))


def clean_unit(root, st, unit):
  problems = terminal_problems(st, unit)
  if problems:
    raise core.HandoffError(problems[0])
  registered, complete = set(core.registered_worktrees(root)), True
  for folder in sorted(p for p in st.path("review", unit, "pr0").parent.glob("pr*") if p.is_dir()):
    child = folder / "worktree"
    if child.resolve() in registered:
      if not stop_leftovers(st, unit, child):
        complete = False
        continue
      core.remove_worktree(root, child, force=True)  # the review child is the store's: its `pr<n>/r<n>` records stay
    elif folder.resolve() in registered:
      if not stop_leftovers(st, unit, folder):
        complete = False
        continue
      core.remove_worktree(root, folder)  # a legacy `pr<n>` worktree keeps EGM's dirty refusal
    else:
      print(f"kept {folder}: not a worktree")
      continue
    for ref in (f"refs/superegm/pr/{folder.name[2:]}", f"refs/superegm/pr-base/{folder.name[2:]}"):
      core.run_git(["update-ref", "-d", ref], root, check=False)
  recorded = {Path(entry["worktree"]).resolve() for entry in load_launches(st, unit)}
  for tree in sorted(p for p in st.path("worktrees", unit).glob("r*") if p.is_dir()):
    if tree.resolve() not in recorded:
      print(f"kept {tree}: no launch records it")
    elif stop_leftovers(st, unit, tree):
      core.run_git(["worktree", "remove", "--force", str(tree)], root)
    else:
      complete = False
  core.run_git(["worktree", "prune"], root, check=False)
  if complete:
    try:
      st.path("worktrees", unit).rmdir()  # the unit's folder goes with its last worktree; a kept one stays
    except OSError:
      pass
    core.journal(st, f"{unit} cleaned")
    print(f"{unit} cleaned")


def process_table():
  """`(pid, command, cwd)` of every process `lsof -a -d cwd` lists; nothing when `lsof` is missing."""
  try:
    out = subprocess.run(["lsof", "+c", "0", "-a", "-d", "cwd", "-Fpcn"], capture_output=True, text=True, timeout=60).stdout
  except (OSError, subprocess.SubprocessError):
    return []
  rows, pid, command = [], None, ""
  for line in out.splitlines():
    if line.startswith("p") and line[1:].isdigit():
      pid, command = int(line[1:]), ""
    elif line.startswith("c"):
      command = line[1:]
    elif line.startswith("n") and pid is not None:
      rows.append((pid, command, line[1:]))
  return rows


def signal_process(pid, sig):
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
  """`(pid, command)` of every `node` or `python*` process whose cwd lies inside `tree` (a path-component test, never a prefix)."""
  inside, found = tree.resolve(), []
  for pid, command, cwd in process_table():
    if pid in (os.getpid(), os.getppid()) or not (command == "node" or command.startswith("python")):
      continue
    try:
      Path(cwd).resolve().relative_to(inside)
    except ValueError:
      continue
    found.append((pid, command))
  return found


def stop_leftovers(st, unit, tree):
  """SIGTERM, after `KILL_WAIT` seconds SIGKILL, each leftover process in `tree`, journalled `<unit> killed <pid> <command>`;
  False, with the survivors printed, when one outlives SIGKILL (the caller keeps the worktree)."""
  found = leftovers(tree)
  for pid, _command in found:
    signal_process(pid, signal.SIGTERM)
  deadline = core.NOW() + KILL_WAIT
  while core.NOW() < deadline and any(is_alive(pid) for pid, _command in found):
    core.SLEEP(1)
  survivors = []
  for pid, command in found:
    if is_alive(pid):
      signal_process(pid, signal.SIGKILL)
      core.SLEEP(1)
    if is_alive(pid):
      survivors.append((pid, command))
    else:
      core.journal(st, f"{unit} killed {pid} {command}")
  for pid, command in survivors:
    print(f"kept {tree}: {command} {pid} survives SIGKILL")
  return not survivors


def terminal_problems(store, unit):
  """Every launch without its exit file or `interrupted`, every round not `posted` nor
  `collected` with a `not run` outcome (spec section 4)."""
  problems = [f"{unit} launch {entry['round']} is not terminal" for entry in load_launches(store, unit) if not terminal(entry)]
  for entry in core.load_foreman(store, unit)["rounds"]:
    if not (entry.get("phase") == "posted" or (entry.get("phase") == "collected" and str(entry.get("outcome") or "").startswith("not run"))):
      problems.append(f"{unit} round {entry.get('round')} is not terminal ({entry.get('phase')})")
  return problems
