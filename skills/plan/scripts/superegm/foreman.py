# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the foreman subcommand (not built yet).

"""superegm foreman: foreman dispatch."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("foreman", help="foreman dispatch").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: foreman is not built yet", file=sys.stderr)
  return 1
