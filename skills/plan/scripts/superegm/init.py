# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the init subcommand (not built yet).

"""superegm init: write .superegm/config.json and print the owner's by-hand steps."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("init", help="write .superegm/config.json and print the owner's by-hand steps").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: init is not built yet", file=sys.stderr)
  return 1
