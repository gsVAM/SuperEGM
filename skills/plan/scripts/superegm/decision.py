# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the decision subcommand (not built yet).

"""superegm decision: decision open|rule."""

import sys


def register(subparsers):
  subparsers.add_parser("decision", help="decision open|rule").set_defaults(run=run)


def run(args):
  print("superegm: decision is not built yet", file=sys.stderr)
  return 1
