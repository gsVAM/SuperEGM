# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the close subcommand (spec section 12): `closed_at`, every unlanded unit journaled;
# it refuses while a redesign-stopped unit's issue is open (one GitHub read per such unit); `write_closed`, `closed_at` in the state and handoffs/<id>.json (U20).

"""superegm close: close the handoff under an integrate card; writes `closed_at` once."""

import json
from pathlib import Path

import superegm as core

WRITES = frozenset({"state", "handoffs"})  # the store kinds this subcommand writes
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
  # A unit stopped for redesign keeps its issue open until the owner closes it by hand: one read each, all
  # journaled, then the refusal, before any write.
  refusals = []
  for uid, record in sorted((state.get("units") or {}).items()):
    if not (core.load_foreman(st, uid).get("stopped") or {}).get("brief"):
      continue
    number = record["number"]
    issue = core.gh_json(["api", f"repos/{st.config['repo']}/issues/{number}"]) or {}
    core.journal(st, f"close: {uid} stopped for redesign: #{number} {issue.get('state')}")
    if issue.get("state") == "open":
      refusals.append(f"close: {uid} is stopped for redesign and #{number} is open: "
                      "close it by hand once the re-planned unit is filed")
  if refusals:
    print("\n".join(refusals))
    return 1
  # The landed set is `status --wait`'s last snapshot (the integrate skill refreshes it first); no GitHub read here.
  saved = (state.get("status") or {}).get("units") or {}
  unlanded = sorted(uid for uid in state.get("units") or {} if not (saved.get(uid) or {}).get("landed"))
  for uid in unlanded:
    core.journal(st, f"close: {uid} unlanded")
  write_closed(st, state, None)
  print(f"closed {state['handoff_id']}; unlanded: {', '.join(unlanded) or 'none'}")
  return 0


def write_closed(store: core.Store, state: dict, reason: str | None) -> None:
  """`close`'s write (spec section 7): `closed_at` into the handoff's `state.json` and its
  `handoffs/<id>.json` (written for a legacy handoff the first time), journaled; `reason` names a close
  other than `close`'s own (`voided`: `approve-spec --void` on a handoff with no filed unit)."""
  hid = state.get("handoff_id") or store.handoff_id
  state["closed_at"] = core.now_iso()
  core.atomic_write(store.path("state"), state)
  path = store.path("handoffs", hid)
  record = json.loads(core.read_text(path)) if path.is_file() else \
      {"id": hid, "spec": (state.get("design") or {}).get("path"), "opened_at": None, "closed_at": None}
  core.atomic_write(path, record | {"closed_at": state["closed_at"]})
  core.journal(store, f"closed {hid} at {state['closed_at']}" + (f" (closed: {reason})" if reason else ""))
