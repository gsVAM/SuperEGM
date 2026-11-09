# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the driver

"""superegm driver tick|install|uninstall|status|reset (spec section 11.2): the owner's timer. `tick` launches one
`wave --leavemealone` session per store when there is something to do; `install` and `uninstall` write and remove
the launchd agent (a systemd user timer on Linux); `status` reads, `reset` is the owner's interrupt."""

import json
import os
import plistlib
import subprocess
from pathlib import Path

import superegm as core

WRITES = frozenset({"driver", "runcards", "launches"})
SKILLS = frozenset({"driver"})
ACTIONS = ("tick", "install", "uninstall", "status", "reset")
LABEL = "com.superegm.driver"


def plist_path() -> Path:
  return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def systemd_dir() -> Path:
  return Path.home() / ".config" / "systemd" / "user"


def plist_helper():
  """The helper the installed timer runs: the plist's `ProgramArguments[1]`, else the systemd unit's `ExecStart`
  second word, whichever file exists; None when neither does (or it names none)."""
  try:
    if plist_path().is_file():
      argv = plistlib.loads(plist_path().read_bytes()).get("ProgramArguments") or []
      return argv[1] if len(argv) > 1 else None
    unit = systemd_dir() / "superegm-driver.service"
    if unit.is_file():
      for line in core.read_text(unit).splitlines():
        if line.startswith("ExecStart="):
          words = line[len("ExecStart="):].split()
          return words[1] if len(words) > 1 else None
  except (OSError, ValueError, plistlib.InvalidFileException):
    return None
  return None


def helper_root(helper) -> str:
  """The plugin root a helper path names (`<root>/skills/plan/scripts/superegm.py`)."""
  parents = Path(helper).parents
  return str(parents[3]) if len(parents) > 3 else str(helper)


def root_ok(root, artifacts_dir) -> bool:
  """The registered `root` is a git worktree whose `.superegm/config.json` names `artifacts_dir` (no remote read)."""
  try:
    if subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True).returncode != 0:
      return False
    config = json.loads(core.read_text(Path(root) / ".superegm" / "config.json"))
  except (OSError, ValueError):
    return False
  named = config.get("artifacts_dir")
  return isinstance(named, str) and Path(os.path.expanduser(named)).resolve() == Path(artifacts_dir).resolve()


def register(subparsers):
  p = core.add_parser(subparsers, "driver", "the owner's timer: tick, install, uninstall, status, reset")
  p.add_argument("action", choices=ACTIONS)
  p.add_argument("--interval", type=int, help="install: minutes between ticks (default 15)")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  raise core.HandoffError(f"driver: {args.action} is not available yet")
