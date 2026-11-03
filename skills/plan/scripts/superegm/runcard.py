# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the runcard subcommand (not built yet).

"""superegm runcard: open or close a run card."""

import sys

WRITES = frozenset(['runcards'])  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("runcard", help="open or close a run card").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: runcard is not built yet", file=sys.stderr)
  return 1
