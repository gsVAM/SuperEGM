# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the registry

"""superegm register [--remove] --runcard <id>: `~/.superegm/registry.json`'s entry `{repo, root, artifacts_dir}`
for the current store, added or removed (spec section 11.2). An entry is keyed on `artifacts_dir`: a second
worktree of a listed store updates its `root`, never adds a second entry."""

from pathlib import Path

import superegm as core

WRITES = frozenset()  # the registry lives outside every store
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SKILLS = frozenset({"driver"})


def register(subparsers):
  p = core.add_parser(subparsers, "register", "add (or with --remove remove) this store's registry entry")
  p.add_argument("--remove", action="store_true", help="remove this store's entry")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  try:
    core.require_runcard(args, SKILLS)
    return update(args)
  except core.HandoffError as error:
    raise core.HandoffError(f"register: {error}") from None


def update(args) -> int:
  st = core.STORE
  entries = core.load_registry()
  store_dir, root = str(st.root), str(core.git_toplevel(Path.cwd()))
  mine = [e for e in entries if e.get("artifacts_dir") == store_dir]
  others = [e for e in entries if e.get("artifacts_dir") != store_dir]
  if args.remove:
    if not mine:
      print(f"not registered: {store_dir}")
      return 0
    core.atomic_write(core.registry_path(), others)
    core.journal(st, f"registry: {store_dir} removed")
    print(f"removed: {store_dir}")
    return 0
  entry = {"repo": st.config["repo"], "root": root, "artifacts_dir": store_dir}
  if mine and mine[0].get("root") != root:
    core.journal(st, f"registry: {store_dir} root {mine[0].get('root')} → {root}")
  elif not mine:
    core.journal(st, f"registry: {store_dir} added at {root}")
  core.atomic_write(core.registry_path(), others + [entry])
  print(f"registered: {store_dir} at {root}")
  return 0
