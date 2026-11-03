# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the interrupt subcommand (not built yet).

"""superegm interrupt: interrupt a launch or a round."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("interrupt", help="interrupt a launch or a round").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: interrupt is not built yet", file=sys.stderr)
  return 1
