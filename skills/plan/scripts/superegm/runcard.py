# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the runcard subcommand; open's boot-id proof writes (U24);
# `runcard close --note` (U32).

"""superegm runcard open|close: the run card every effect runs under (spec section 6)."""

from pathlib import Path

import superegm as core

WRITES = frozenset(["runcards", "launches", "driver"])  # the store kinds this subcommand writes; the boot-id proof's (U24)


def register(subparsers):
  p = core.add_parser(subparsers, "runcard", "open or close a run card", runcard=False)
  action = p.add_subparsers(dest="action", required=True)
  o = action.add_parser("open", help="open a card and print its id")
  o.add_argument("--skill", required=True)
  o.add_argument("--artifact", required=True, help="the spec path, unit id, question file or branch")
  o.add_argument("--parent", help="the open or interrupted card this child belongs to")
  o.add_argument("--mode", choices=("normal", "leavemealone"), help="default: the config's mode")
  c = action.add_parser("close", help="close a card")
  c.add_argument("id")
  c.add_argument("--note", help="a note journaled with the close")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  st = core.store(core.git_toplevel(Path.cwd()))
  if args.action == "open":
    print(core.open_runcard(st, args.skill, args.artifact, parent=args.parent, mode=args.mode))
    return 0
  card = core.load_card(st, args.id)
  if card["closed_at"]:
    raise core.HandoffError(f"runcard: {args.id} is closed")
  card["closed_at"] = core.now_iso()
  core.atomic_write(st.path("runcards", args.id), card)
  core.journal(st, f"runcard close {args.id}" + (f" note {args.note}" if getattr(args, "note", None) else ""))
  print(f"closed {args.id}")
  return 0
