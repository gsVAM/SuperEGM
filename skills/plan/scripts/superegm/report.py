# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the report subcommand (spec section 11): the per-batch wave report, the idle rules
# and the end condition, plus the pure functions the wave skill cites.

"""superegm report: rewrite `wave_<n>_report.md` from the store and print the idle, pending and loop lines."""

import json
from pathlib import Path

import superegm as core
from superegm.launch import load_launches

WRITES = frozenset({"report"})  # the store kinds this subcommand writes
SKILLS = frozenset({"wave"})  # the skills whose card this subcommand accepts
TERMINAL = ("landed", "stopped", "pending", "idle", "clean")  # every state the loop never dispatches


def register(subparsers):
  p = core.add_parser(subparsers, "report", "rewrite the wave report; print the idle, pending and loop lines")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  st = core.store(core.git_toplevel(Path.cwd()))
  state, config, now = core.load_state(st.root), st.config, core.NOW()
  units = state.get("units") or {}
  views = {uid: unit_view(state, uid) for uid in units}
  launched = [uid for uid in units if units[uid].get("launched")]
  foremen = {uid: core.load_foreman(st, uid) for uid in launched}
  states = {uid: unit_state(uid, views[uid], foremen[uid], card, config, now) for uid in launched}
  free = config["max_in_flight"] - sum(states[uid] in ("active", "pending") for uid in launched)
  ready = [uid for uid in (state.get("status") or {}).get("ready") or [] if uid not in launched]
  ended, why = loop_ended(states, ready, free)
  n = wave_number(st, args.runcard, card)
  path = st.path("wave_report", n)
  lines = [f"# Wave {n} report", f"Run card: {args.runcard}", f"Loop: {'ended' if ended else 'continuing'} ({why})", "",
           "## Units"]
  for uid in units:
    lines.append(unit_line(uid, units[uid], views[uid], states.get(uid, "unlaunched"), foremen.get(uid, {}),
                           load_launches(st, uid)))
  idle = [uid for uid in launched if states[uid] == "idle"]
  lines += section("Non-terminal launches", [f"{uid} launch {e['round']} {e['status']}" for uid in launched
                                              for e in load_launches(st, uid) if not e["status"].startswith("exited")
                                              and e["status"] != "interrupted"])
  lines += section("Heads with pending or absent CI", [f"{uid} {views[uid]['head'][:7]} waiting-for-ci" for uid in launched
                                                       if views[uid]["head"] and views[uid]["ci"] in (None, "pending")])
  lines += section("Idle", [f"{uid}: {reason}" for uid, reason in idle_reasons(card, states, views, config, now)])
  lines += section("Ready, unlaunched", [f"{uid} ({'slot free' if free > 0 else 'no free slot'})" for uid in ready])
  lines += section("Pending decisions", [])
  lines += section("Stopped", [])
  core.atomic_write(path, "\n".join(lines) + "\n")
  print(path)
  print("idle: " + (",".join(idle) or "none"))
  print("pending: none")
  print(f"loop: {'ended' if ended else 'continuing'} ({why})")
  return 0


def unit_view(state: dict, uid: str) -> dict:
  """The one reader of `status.units[<id>]` (what `status --wait` saves): `pr, head, ci, landed`."""
  saved = ((state.get("status") or {}).get("units") or {}).get(uid) or {}
  return {key: saved.get(key) for key in ("pr", "head", "ci")} | {"landed": bool(saved.get("landed"))}


def wave_number(st, rid: str, card: dict) -> int:
  """The card's ordinal by `opened_at` among the store's top-level `wave` cards on the same artifact."""
  folder = st.path("runcards", "x").parent
  cards = []
  for other in folder.glob("*.json"):
    data = json.loads(core.read_text(other))
    if data["skill"] == "wave" and data["artifact"] == card["artifact"] and not data["parent"]:
      cards.append((data["opened_at"], other.stem))
  return sorted(cards).index((card["opened_at"], rid)) + 1


def unit_line(uid: str, record: dict, view: dict, state: str, foreman: dict, launches: list) -> str:
  rounds = foreman.get("rounds") or []
  detail = ", ".join(f"r{r.get('round')} {r.get('phase')}" + (f" {r['outcome']}" if r.get("outcome") else "") for r in rounds)
  latest = launches[-1] if launches else None
  return (f"- {uid} #{record.get('number')}: {state} · pr {'#%s' % view['pr'] if view['pr'] else 'none'} "
          f"head {view['head'][:7] if view['head'] else 'none'} · ci {view['ci'] or 'none'} · rounds {len(rounds)}"
          f"{' (' + detail + ')' if rounds else ''} · launch {'%s %s' % (latest['round'], latest['status']) if latest else 'none'}")


def section(title: str, items: list) -> list:
  return ["", f"## {title}"] + [f"- {item}" for item in items or ["none"]]


def idle_reasons(card: dict, states: dict, views: dict, config: dict, now: float) -> list:
  """`(unit, reason)` per idle unit: the card's `idle[]` reasons, then the CI bound with its minutes."""
  reasons = [(entry["unit"], entry["reason"]) for entry in card.get("idle") or [] if entry["unit"] in states]
  for uid, state in states.items():
    seen = ci_seen_at(uid, views[uid], card)
    if state == "idle" and seen is not None and not any(u == uid for u, _ in reasons):
      reasons.append((uid, f"ci {views[uid]['ci'] or 'absent'} for {int((now - seen) // 60)} min "
                           f"(ci_wait_minutes {config.get('ci_wait_minutes', 30)})"))
  return reasons



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
