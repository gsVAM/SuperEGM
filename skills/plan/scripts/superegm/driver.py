# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the driver

"""superegm driver tick|install|uninstall|status|reset (spec section 11.2): the owner's timer. `tick` launches one
`wave --leavemealone` session per store when there is something to do; `install` and `uninstall` write and remove
the launchd agent (a systemd user timer on Linux); `status` reads, `reset` is the owner's interrupt."""

import superegm as core

WRITES = frozenset({"driver", "runcards", "launches"})
SKILLS = frozenset({"driver"})
ACTIONS = ("tick", "install", "uninstall", "status", "reset")


def register(subparsers):
  p = core.add_parser(subparsers, "driver", "the owner's timer: tick, install, uninstall, status, reset")
  p.add_argument("action", choices=ACTIONS)
  p.add_argument("--interval", type=int, help="install: minutes between ticks (default 15)")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  raise core.HandoffError(f"driver: {args.action} is not available yet")
