# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the tdd-order subcommand (not built yet).

"""superegm tdd-order: check that each Step's test commit precedes its implementation."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("tdd-order", help="check that each Step's test commit precedes its implementation").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: tdd-order is not built yet", file=sys.stderr)
  return 1
