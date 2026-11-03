# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the launch-builder subcommand (not built yet).

"""superegm launch-builder: launch a builder."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("launch-builder", help="launch a builder").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: launch-builder is not built yet", file=sys.stderr)
  return 1
