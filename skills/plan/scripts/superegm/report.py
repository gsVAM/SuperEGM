# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the report subcommand (spec section 11): the per-batch wave report, the idle rules
# and the end condition, plus the pure functions the wave skill cites.

"""superegm report: rewrite `wave_<n>_report.md` from the store and print the idle, pending and loop lines."""

import sys

WRITES = frozenset()  # the store kinds this subcommand writes
TERMINAL = ("landed", "stopped", "pending", "idle", "clean")  # every state the loop never dispatches


def register(subparsers):
  subparsers.add_parser("report", help="write the wave report").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: report is not built yet", file=sys.stderr)
  return 1


def unit_state(uid: str, view: dict, foreman: dict, card: dict, config: dict, now: float) -> str:
  """One of six: `landed`, `stopped`, `pending` (a decision without its ruling), `idle` (named on the
  card, or a head whose CI is pending or absent for `ci_wait_minutes` since the card first saw it),
  `clean` (the latest round posted clean), else `active`."""
  if view.get("landed"):
    return "landed"
  if foreman.get("stopped"):
    return "stopped"
  if pending_decisions(foreman):
    return "pending"
  if any(entry["unit"] == uid for entry in card.get("idle") or []):
    return "idle"
  seen = ci_seen_at(uid, view, card)
  if seen is not None and now - seen >= config.get("ci_wait_minutes", 30) * 60:
    return "idle"
  latest = max(foreman.get("rounds") or [], key=lambda r: r.get("round") or 0, default={})
  if latest.get("phase") == "posted" and latest.get("outcome") == "clean":
    return "clean"
  return "active"


def pending_decisions(foreman: dict) -> list:
  """`decisions[]` minus `rulings[]` (spec section 7)."""
  ruled = {r.get("decision") for r in foreman.get("rulings") or []}
  return [d for d in foreman.get("decisions") or [] if d["id"] not in ruled]


def ci_seen_at(uid: str, view: dict, card: dict):
  """When the card first saw the unit's current head with pending or absent CI, else None."""
  if view.get("ci") not in (None, "pending") or not view.get("head"):
    return None
  entry = next((h for h in reversed(card.get("heads") or []) if h["unit"] == uid), None)
  return entry["seen_at"] if entry and entry["head"] == view["head"] else None


def loop_ended(states: dict, ready_unlaunched: list, free_slots: int) -> tuple:
  """The end condition: no launched unit active, and no ready unit unlaunched while a slot is free."""
  active = [uid for uid, state in states.items() if state == "active"]
  if active:
    return False, "in flight: " + ", ".join(active)
  if ready_unlaunched and free_slots > 0:
    return False, "ready, unlaunched: " + ", ".join(ready_unlaunched)
  if ready_unlaunched:
    return True, "no free slot for " + ", ".join(ready_unlaunched)
  return True, "every launched unit is clean, landed, stopped, pending or idle"


def word_action(word: str, review_exit: int) -> str:
  """What the elephant does with a foreman's word (spec section 11); `recovered <word>` is the word."""
  word = word.removeprefix("recovered ")
  if word == "clean":
    return "await-merge"
  if word == "revise":
    return "launch-builder"
  if word.startswith("contested"):
    return "decision 1"
  if word == "cap-reached":
    return "decision 2"
  if word == "blocked":
    return "decision 3"
  return "idle: review stalled" if review_exit == 5 else "redispatch"
