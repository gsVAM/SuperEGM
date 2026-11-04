# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the close subcommand (spec section 12): `closed_at`, every unlanded unit journaled.

"""superegm close: close the handoff under an integrate card; writes `closed_at` once."""

from pathlib import Path

import superegm as core

WRITES = frozenset({"state"})  # the store kinds this subcommand writes
SKILLS = frozenset({"integrate"})  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "close", "close the handoff: write closed_at and journal every unlanded unit")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  st = core.store(core.git_toplevel(Path.cwd()))
  state = core.load_state(st.root)
  if state.get("closed_at"):
    raise core.HandoffError(f"close: already closed at {state['closed_at']}")
  if not state.get("handoff_id"):
    raise core.HandoffError("close: no handoff in this store")
  # The landed set is `status --wait`'s last snapshot (the integrate skill refreshes it first); no GitHub read here.
  saved = (state.get("status") or {}).get("units") or {}
  unlanded = sorted(uid for uid in state.get("units") or {} if not (saved.get(uid) or {}).get("landed"))
  for uid in unlanded:
    core.journal(st, f"close: {uid} unlanded")
  state["closed_at"] = core.now_iso()
  core.save_state(st.root, state)
  core.journal(st, f"closed {state['handoff_id']} at {state['closed_at']}")
  print(f"closed {state['handoff_id']}; unlanded: {', '.join(unlanded) or 'none'}")
  return 0
