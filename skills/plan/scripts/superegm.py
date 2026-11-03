# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: renamed from EGM's handoff helper; reduced to main(), the subcommands live in the superegm package.

"""SuperEGM helper entry point: `python3 '<absolute path>' <subcommand> ...`; see the superegm package."""

import sys

import superegm


def main(argv=None):
  args = superegm.build_parser().parse_args(argv)
  superegm.CURRENT_WRITES, superegm.CURRENT_SUBCOMMAND = args.writes, args.command
  try:
    return args.run(args)
  except superegm.HandoffError as error:
    print(f"superegm: {error}", file=sys.stderr)
    return 1
  finally:
    superegm.CURRENT_WRITES = superegm.CURRENT_SUBCOMMAND = None


if __name__ == "__main__":
  sys.exit(main())
