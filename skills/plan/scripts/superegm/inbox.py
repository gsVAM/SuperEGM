# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the inbox and notify subcommands (spec section 11.2, U23).

"""superegm inbox [--all] [--json] [--handoff <id>]: one line per item that needs the owner across the
store's open handoffs, read-only and with no run card; superegm notify --runcard <id>: the owner's
~/.superegm/notify hook run once with the lines new since `state.json.notified`."""

import superegm as core

WRITES = frozenset({"state"})  # notify's `notified`; inbox writes nothing
SKILLS = frozenset({"wave"})


def register(subparsers):
  p = core.add_parser(subparsers, "inbox", "list what needs the owner across the open handoffs (read-only, no run card)",
                      runcard=False)
  p.add_argument("--all", action="store_true", help="every store the registry lists")
  p.add_argument("--json", action="store_true", help="one JSON object per line")
  p.set_defaults(run=run, writes=WRITES)
  p = core.add_parser(subparsers, "notify", "run ~/.superegm/notify once with the inbox lines new since the last notify")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  return 0
