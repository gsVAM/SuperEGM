# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the report subcommand (not built yet).

"""superegm report: write the wave report."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("report", help="write the wave report").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: report is not built yet", file=sys.stderr)
  return 1
