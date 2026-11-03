# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the clean subcommand (not built yet).

"""superegm clean: remove a unit's worktree."""

import sys


def register(subparsers):
  subparsers.add_parser("clean", help="remove a unit's worktree").set_defaults(run=run)


def run(args):
  print("superegm: clean is not built yet", file=sys.stderr)
  return 1
