# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the judges subcommand (not built yet).

"""superegm judges: the judge panel."""

import sys


def register(subparsers):
  subparsers.add_parser("judges", help="the judge panel").set_defaults(run=run)


def run(args):
  print("superegm: judges is not built yet", file=sys.stderr)
  return 1
