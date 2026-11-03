# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the review subcommand (not built yet).

"""superegm review: the review loop."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  subparsers.add_parser("review", help="the review loop").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: review is not built yet", file=sys.stderr)
  return 1
