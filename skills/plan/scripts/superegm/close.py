# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the close subcommand (not built yet).

"""superegm close: close the handoff."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("close", help="close the handoff").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: close is not built yet", file=sys.stderr)
  return 1
