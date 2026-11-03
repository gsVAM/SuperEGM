# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: renamed from EGM's handoff helper; reduced to main(), the subcommands live in the superegm package.

"""SuperEGM helper entry point: `python3 '<absolute path>' <subcommand> ...`.

The subcommands live in the `superegm` package beside this file (one module
each, found through `superegm.SUBCOMMANDS`); the `plan`, `file`, `wave`,
`integrate` and `judges` skills run them under an open run card. The store
is the config's `artifacts_dir`; tests inject `GH`, `SLEEP` and `NOW` on the package.
"""

import sys

import superegm


# One command at a time. `superegm.py` is a single-writer tool: run one command,
# let it finish, run the next. Nothing here coordinates concurrent writers, and
# nothing needs to - every command is short except `status --wait`, which only
# reads while it waits and saves once when it returns.


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
