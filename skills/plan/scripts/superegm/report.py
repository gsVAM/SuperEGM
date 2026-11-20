# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the report subcommand (spec section 11): the per-batch wave report, the idle rules
# and the end condition, plus the pure functions the wave skill cites; the heading names its handoff, the wave counted among its handoff's cards (U20); `ready` and `waiting`, the board's `## Units` table (U30); an `owner: <ids>` decision pending until each id is ruled (U25); a pending unit holds no slot and a launch `interrupted (reboot)` is terminal (U24); a `kill_failed` launch still `running` reads `idle`, the interrupt its action (U31); its own `ci_wait_minutes` config key, moved from `__init__` (U32); the board's tier column (U33); `waiting proceed` and a proceed closing a point-1 decision (U92); the `conflict` view and its board action (U62); a unit waiting on an open respec is not active (U86).

"""superegm report: rewrite `wave_<n>_report.md` from the store, the plan and the spec and print its path, the
board and the idle, pending and loop lines. It opens the card's handoff as `status` does (`core.locate`,
`core.Handoff`), so it refuses as `status` does: `state holds no plan path`, `design file ... does not exist`,
`spec changed since the approval: run approve-spec again`. It reads GitHub never."""

import json
from pathlib import Path

import superegm as core
from superegm.launch import authorizing, conflict_again, latest_clean, load_launches, waiting_proceed

WRITES = frozenset({"report", "runcards"})  # the store kinds this subcommand writes
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {"ci_wait_minutes": 30}, "", None  # its own config key (U32)
SKILLS = frozenset({"wave"})  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "report", "rewrite the wave report; print its path, the board and the idle, pending and loop lines")
  p.add_argument("--idle", action="append", default=[], metavar="U=<reason>",
                 help="name a unit idle for this invocation (it holds no slot), with why")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  state, config, now = handoff.state, st.config, core.NOW()
  units = state.get("units") or {}
  views = {uid: unit_view(state, uid) for uid in units}
  launched = [uid for uid in units if units[uid].get("launched")]
  for item in args.idle:
    uid, _, reason = item.partition("=")
    if uid not in units:
      raise core.HandoffError(f"report: --idle names no unit of this handoff: {uid}")
    core.card_add(st, args.runcard, "idle", {"unit": uid, "reason": reason, "at": core.now_iso()})
  card = record_heads(st, args.runcard, {uid: views[uid] for uid in launched}, now)
  foremen = {uid: core.load_foreman(st, uid) for uid in launched}
  entries = {uid: load_launches(st, uid) for uid in launched}
  states = {uid: unit_state(uid, views[uid], foremen[uid], entries[uid], card, config, now) for uid in launched}
  for uid in respec_waiting(st, [uid for uid in launched if states[uid] == "active"]):
    states[uid] = "waiting respec"  # spec section 7.6: the raising unit waits, holding no slot, so the wave can end
  free = config["max_in_flight"] - sum(states[uid] == "active" for uid in launched)  # a pending unit holds no slot (amendment 5)
  named_idle = {entry["unit"] for entry in card.get("idle") or []}  # holds no slot, launched or not
  ready = [uid for uid in (state.get("status") or {}).get("ready") or [] if uid not in launched and uid not in named_idle]
  # U62 (spec section 6.1): a clean conflicting unit `launch`'s `again` set takes is pending work, not an end
  # an idle unit, named or on its CI wait, is passed to `launch --idle`, which marks none of them
  merge_rounds = [uid for uid in launched if uid not in named_idle and states[uid] != "idle" and conflict_again(
      {**views[uid], "conflict": conflicting(state, uid)}, foremen[uid], entries[uid], handoff.graph.parallel)]
  ended, why = loop_ended(states, ready, free, merge_rounds)
  n = wave_number(st, args.runcard, card)
  path = st.path("wave_report", n)
  lines = [f"# Wave {n} report (handoff {st.handoff_id})", f"Run card: {args.runcard}", f"Loop: {'ended' if ended else 'continuing'} ({why})", "",
           "## Units"]
  board = board_table(handoff, state, card, now)
  lines.append(board)
  idle = [uid for uid in units if uid in named_idle or states.get(uid) == "idle"]
  pending = [(uid, d) for uid in launched for d in pending_decisions(foremen[uid])]
  lines += section("Non-terminal launches", [f"{uid} launch {e['round']} {e['status']}" for uid in launched
                                              for e in load_launches(st, uid) if not e["status"].startswith(("exited", "interrupted"))])
  lines += section("Heads with pending or absent CI", [f"{uid} {views[uid]['head'][:7]} waiting-for-ci" for uid in launched
                                                       if views[uid]["head"] and views[uid]["ci"] in (None, "pending")])
  lines += section("Idle", [f"{uid}: {reason}" for uid, reason in idle_reasons(card, states, views, config, now, entries)])
  lines += section("Ready, unlaunched", [f"{uid} ({'slot free' if free > 0 else 'no free slot'})" for uid in ready])
  lines += section("Pending decisions", [f"{uid} {d['id']} (point {d['point']}, {d['source']}): {question_line(d['question'])}"
                                         for uid, d in pending])
  lines += section("Stopped", [stopped_line(st, uid, foremen[uid]["stopped"], views) for uid in launched
                               if states[uid] == "stopped"])
  core.atomic_write(path, "\n".join(lines) + "\n")
  print(path)
  print(board)
  print("idle: " + (",".join(idle) or "none"))
  print("pending: " + ("; ".join(f"{uid} {d['id']} (point {d['point']}, {d['source']})" for uid, d in pending) or "none"))
  print(f"loop: {'ended' if ended else 'continuing'} ({why})")
  return 0


def record_heads(store, card_id: str, views: dict, now: float) -> dict:
  """Append `{unit, head, seen_at}` to the card's `heads` for every launched unit whose head differs from the
  card's last entry for it (the CI-wait clock starts at the first report that saw the head); the card after."""
  card = core.load_card(store, card_id)
  for uid, view in views.items():
    last = next((h for h in reversed(card.get("heads") or []) if h["unit"] == uid), None)
    if view["head"] and (last is None or last["head"] != view["head"]):
      core.card_add(store, card_id, "heads", {"unit": uid, "head": view["head"], "seen_at": now})
  return core.load_card(store, card_id)


def unit_view(state: dict, uid: str) -> dict:
  """The one reader of `status.units[<id>]` (what `status --wait` saves): `pr, head, ci, landed`, plus
  `launched` (`units[<id>].launched` truthy) and `ready` (`<id>` in the saved `status.ready`)."""
  status = state.get("status") or {}
  saved = (status.get("units") or {}).get(uid) or {}
  return ({key: saved.get(key) for key in ("pr", "head", "ci")} | {"landed": bool(saved.get("landed"))}
          | {"launched": bool(((state.get("units") or {}).get(uid) or {}).get("launched")),
             "ready": uid in (status.get("ready") or [])})


def conflicting(state: dict, uid: str) -> bool:
  """U62: the saved `status.units[<id>].conflict`, its pull request read `CONFLICTING` by the last `status` pass."""
  return bool((((state.get("status") or {}).get("units") or {}).get(uid) or {}).get("conflict"))


def wave_number(st, rid: str, card: dict) -> int:
  """The card's ordinal by `opened_at` among its handoff's top-level `wave` cards on the same artifact, one spec
  being one artifact in every worktree of the repository (`core.here`, as `require_runcard` reads it, U24)."""
  folder = st.path("runcards", rid).parent  # the card's own `runcards/`: its handoff's (spec section 7)
  try:  # the checkout resolved once, as `open_runcard` does, not once per card
    top = core.git_toplevel(Path.cwd())
  except core.HandoffError:
    top = None
  same = (lambda p: str(core.rebased(p, top))) if top else (lambda p: str(Path(p)))
  cards, mine = [], same(card["artifact"])
  for other in folder.glob("*.json"):
    data = json.loads(core.read_text(other))
    if data["skill"] == "wave" and same(data["artifact"]) == mine and not data["parent"]:
      cards.append((data["opened_at"], other.stem))
  return sorted(cards).index((card["opened_at"], rid)) + 1


BOARD_COLUMNS = ("unit", "state", "round", "launch", "head", "PR", "waits on", "next action", "cost", "tier")  # tier last (U33)


def board_table(handoff, state: dict, card: dict, now: float) -> str:
  """The board (spec section 11.1): a header line (handoff, base, spec sha, waves, `board_changed_at`)
  and one row per unit of the graph's order, the same table in the report, on stdout and in the issue."""
  st, config, units = handoff.store, handoff.config, state.get("units") or {}
  views = {uid: unit_view(state, uid) for uid in handoff.graph.order}
  foremen = {uid: core.load_foreman(st, uid) for uid in handoff.graph.order}
  launches = {uid: load_launches(st, uid) for uid in handoff.graph.order}
  states = {uid: unit_state(uid, views[uid], foremen[uid], launches[uid], card, config, now) for uid in handoff.graph.order}
  # The card's latest reason for the unit (a later `--idle` replaces the cell; `## Idle` lists them all), else the
  # CI bound without its growing minute count, so an idle row stays equal across passes.
  reasons = dict((e["unit"], e["reason"]) for e in card.get("idle") or [] if e["unit"] in views)
  for uid in handoff.graph.order:
    if kill_failed(launches[uid]) and uid not in reasons:  # U31: the interrupt for a `kill_failed` one
      reasons[uid] = kill_failed_reason(uid, kill_failed(launches[uid]))
    reasons.setdefault(uid, f"ci {views[uid]['ci'] or 'absent'} (ci_wait_minutes {config.get('ci_wait_minutes', 30)})")
  open_blocking = (state.get("status") or {}).get("open_blocking") or {}
  waves = " → ".join("{" + ", ".join(handoff.graph.waves[w]) + "}" for w in sorted(handoff.graph.waves))
  lines = [f"handoff {handoff.handoff_id} · base {config.get('base', 'main')} · spec {handoff.design_sha[:12]} · waves {waves}"
           f" · changed {state.get('board_changed_at') or 'none'}",
           "| " + " | ".join(BOARD_COLUMNS) + " |", "| " + " | ".join("---" for _ in BOARD_COLUMNS) + " |"]
  for uid in handoff.graph.order:
    view, foreman, entries, word = views[uid], foremen[uid], launches[uid], states[uid]
    rounds = foreman.get("rounds") or []
    latest = max(rounds, key=lambda r: r.get("round") or 0, default=None)
    launch = entries[-1] if entries else None
    decisions = pending_decisions(foreman)
    waits = [d["id"] for d in decisions]
    if not view["landed"] and view["head"] and view["ci"] in (None, "pending"):
      waits.append("ci")
    # Every predecessor `status_pass` holds readiness on: `preds`, the blockers (the shared-file order too only for an entry without `rounds`), then the plan's open blocking decisions.
    waits += [p for p in handoff.graph.order if p in handoff.graph.preds[uid] and not views[p]["landed"]]
    waits += [f"{uid}/{d}" for d in open_blocking.get(uid) or []]
    # spec section 4.2: a head made clean by a proceed reads its proceed, never its latest posted round alone
    auth = authorizing(foreman) or {}
    action = next_action(word, latest, launch, decisions, reasons.get(uid),
                         proceeded=bool(auth.get("ruling")), pinned=bool(auth.get("head")))
    # U61: a clean head whose shared-file merge order is not all landed waits for those merges; `waits on` keeps the blockers.
    unmerged = [p for p in handoff.graph.order if p in handoff.graph.merge_after[uid] and not views[p]["landed"]]
    if word == "clean" and action == "await-merge" and unmerged:
      action = "await-merge after " + ", ".join(unmerged)
    conflict = conflicting(state, uid)
    again = conflict and conflict_again({**view, "conflict": True}, foreman, entries, handoff.graph.parallel)
    action = conflict_action(conflict, view, word, action, handoff.graph.parallel, again)
    cells = [f"{uid} #{(units.get(uid) or {}).get('number')}", word, round_cell(latest),
             f"{launch['round']} {launch['status']}" if launch else "none", view["head"][:7] if view["head"] else "none",
             f"#{view['pr']}" if view["pr"] else "none", ", ".join(waits) or "none",
             action, cost_cell(entries), core.unit_tier(st, uid)]
    lines.append("| " + " | ".join(map(board_cell, cells)) + " |")
  return "\n".join(lines)


def conflict_action(conflict: bool, view: dict, word: str, action: str, parallel: bool, again: bool = False) -> str:
  """U62 (spec section 6.1): a unit whose pull request GitHub reads `CONFLICTING` shows `conflict` beside its
  action. A clean head awaits no merge: its merge round (an approval with `rounds`) when `launch` would mark it
  (`again`, `launch.conflict_again`), else once the launch running on it ends, or the owner's hand (an approval
  without `rounds`, 1.2's rule); any other state, a stopped unit's included, keeps its action, the rule applied
  once it ends."""
  if not conflict or view.get("landed") or word == "landed":
    return action
  if word == "clean":
    if not parallel:
      return "conflict: the owner resolves it"
    return "conflict: merge round" if again else "conflict: a merge round once the launch ends"
  return f"conflict; {action}"


def board_cell(text: str) -> str:
  """A cell kept inside its row and its block: `|` escaped, line breaks folded, `<!--` written `&lt;!--` so no
  cell text (an `--idle` reason) ends the table or reads as a board marker."""
  return " ".join(str(text).replace("|", "\\|").replace("<!--", "&lt;!--").split())


def round_cell(latest) -> str:
  if not latest:
    return "none"
  return f"r{latest.get('round')} {latest.get('phase')}" + (f" {latest['outcome']}" if latest.get("outcome") else "")


def next_action(word: str, latest, launch, decisions: list, reason, proceeded: bool = False,
                pinned: bool = True) -> str:
  """The board's `next action` by state: `launch-builder` for `ready`, the decision for `pending`, the idle
  reason for `idle`, `proceed again` for `waiting proceed` (spec section 4.2), none for `waiting`, `landed` and
  `stopped`; for a `clean` unit whose authorizing outcome is a proceed (`proceeded`, spec section 4.2: its latest
  posted round, if any, is not what authorizes it), `await-merge` when the proceed pinned a head and `proceed
  again` when it did not (`pinned` False: `inbox` offers no merge without a head for `--match-head-commit`, and
  lists `proceed again` on the pull request's head once the pull request has one; while it has none, the inbox
  lists nothing for the unit and the owner's proceed waits for the builder's push); otherwise an `active` or `clean` unit's from
  the word of a posted round not older than the latest launch, else none while a launch runs, `foreman dispatch`
  once it is terminal or when there is none."""
  if word == "ready":
    return "launch-builder"
  if word == "pending":
    return f"decision {decisions[0]['point']}"
  if word == "idle":
    return reason or "none"
  if word == "waiting proceed":  # spec section 4.2: the owner's second proceed, naming the later launch
    return "proceed again"
  if word not in ("active", "clean"):
    return "none"
  if word == "clean" and proceeded:
    return "await-merge" if pinned else "proceed again"
  if (latest and latest.get("phase") == "posted" and latest.get("outcome")
      and not (launch and launch["round"] > (latest.get("launch") or 0))):
    return word_action(latest["outcome"], 0)
  if launch and not launch["status"].startswith(("exited", "interrupted")):
    return "none"
  return "foreman dispatch"


def cost_cell(entries: list) -> str:
  """The launches' `total_cost_usd` summed; `(partial)` when an entry holds `unrecorded`; none until one has it."""
  costs = [e.get("total_cost_usd") for e in entries if e.get("total_cost_usd") is not None]
  if not costs:
    return "none"
  total = sum(c for c in costs if isinstance(c, (int, float)))
  return f"{total:.2f}" + (" (partial)" if any(c == "unrecorded" for c in costs) else "")


def section(title: str, items: list) -> list:
  return ["", f"## {title}"] + [f"- {item}" for item in items or ["none"]]


def kill_failed(launches: list):
  """U31: the latest launch when it is `running` with the `kill_failed` mark and no exit file, else None (a late exit
  file makes it terminal, `launch.terminal`'s reading, and the interrupt would refuse it)."""
  latest = launches[-1] if launches else None
  if not (latest and latest.get("status") == "running" and latest.get("kill_failed")):
    return None
  return None if Path(str(latest.get("result_file")) + ".exit").is_file() else latest


def kill_failed_reason(uid: str, entry: dict) -> str:
  """U31: a `kill_failed` launch's idle reason, its action the owner's interrupt."""
  return f"kill_failed ({entry['kill_failed']}): /superegm:interrupt --unit {uid} --launch {entry['round']}"


def idle_reasons(card: dict, states: dict, views: dict, config: dict, now: float, launches: dict | None = None) -> list:
  """`(unit, reason)` per idle unit: the card's `idle[]` reasons, a `kill_failed` launch's (U31), then the CI bound
  with its minutes."""
  reasons = [(entry["unit"], entry["reason"]) for entry in card.get("idle") or [] if entry["unit"] in views]
  for uid, state in states.items():
    entry = kill_failed((launches or {}).get(uid) or [])
    if state == "idle" and entry and not any(u == uid for u, _ in reasons):
      reasons.append((uid, kill_failed_reason(uid, entry)))
  for uid, state in states.items():
    seen = ci_seen_at(uid, views[uid], card)
    if state == "idle" and seen is not None and not any(u == uid for u, _ in reasons):
      reasons.append((uid, f"ci {views[uid]['ci'] or 'absent'} for {int((now - seen) // 60)} min "
                           f"(ci_wait_minutes {config.get('ci_wait_minutes', 30)})"))
  return reasons


def question_line(question: str) -> str:
  """The first line of a question that is not blank, not a `**…**` heading and not a `- (` option."""
  return next((line for line in question.splitlines()
               if line.strip() and not line.startswith("**") and not line.startswith("- (")), "")


def dependants(units_json, uid: str) -> list:
  """The transitive closure of the units whose `blockers` name `uid`, sorted; `[]` when the file is absent."""
  found, frontier = set(), {uid}
  while frontier and units_json:
    frontier = {u for u, unit in units_json["units"].items() if set(unit.get("blockers") or []) & frontier} - found
    found |= frontier
  return sorted(found)


def stopped_line(st, uid: str, stopped: dict, views: dict) -> str:
  path = st.path("handoff_units")
  units_json = json.loads(core.read_text(path)) if path.is_file() else None
  unlanded = [u for u in dependants(units_json, uid) if not views.get(u, {}).get("landed")]
  note = " (handoff_units.json absent)" if units_json is None else ""
  brief = f"; brief {stopped['brief']}" if stopped.get("brief") else ""
  return f"{uid} ({stopped['by']}: {stopped['reason']}): unlanded dependants {', '.join(unlanded) or 'none'}{note}{brief}"


def unit_state(uid: str, view: dict, foreman: dict, launches: list, card: dict, config: dict, now: float) -> str:
  """One of nine, read in this order: `landed` (a merged view, `pr` set and `ci` null, included: it holds no
  slot, U55), `stopped`, `pending` (a decision without its ruling), `idle` (named on the card, or a `running`
  latest launch with the `kill_failed` mark, U31), `waiting proceed` (spec section 4.2: a proceeded head with a
  later finished launch or a moved head; no slot, U92; read before the CI wait, so a proceeded unit's new head
  with CI pending reads `waiting proceed`), `idle` (a head whose CI is pending or absent for `ci_wait_minutes`
  since the card first saw it),
  `clean` (`launch.latest_clean`: spec section 4.2's authorizing outcome, the newer by launch of the latest round
  posted clean and the newest proceed, with no launch recorded after it and, when both carry one, the pull
  request's head equal to its head), else `active`; an unlaunched
  unit not named idle is `ready` (in the saved `status.ready`) or `waiting` (a view without
  `launched` reads as launched)."""
  if view.get("landed") or (view.get("pr") and view.get("ci") is None):  # a merged view (`pr` set, `ci` null) has landed
    return "landed"
  if foreman.get("stopped"):
    return "stopped"
  if pending_decisions(foreman):
    return "pending"
  if any(entry["unit"] == uid for entry in card.get("idle") or []):
    return "idle"
  if kill_failed(launches):  # U31: a `kill_failed` launch still `running` holds no slot until the owner's interrupt
    return "idle"
  if not view.get("launched", True):
    return "ready" if view.get("ready") else "waiting"
  if waiting_proceed(foreman, launches, view.get("head")):
    return "waiting proceed"
  seen = ci_seen_at(uid, view, card)
  if seen is not None and now - seen >= config.get("ci_wait_minutes", 30) * 60:
    return "idle"
  return "clean" if latest_clean(foreman, launches, view.get("head")) else "active"


def pending_decisions(foreman: dict) -> list:
  """`decisions[]` minus `rulings[]` (spec section 7); a point-1 decision whose options end ` allowed` (an
  `owner: <ids>` decision, U25) stays pending until every option's fid has a ruling or a `redesign` or a `proceed` rules it whole."""
  rulings = foreman.get("rulings") or []
  ruled = {r.get("decision") for r in rulings}

  def pending(d):
    options = d.get("options") or []
    if d.get("point") == 1 and options and all(o.endswith(" allowed") for o in options):
      fids = {str(r.get("ruling") or "").split(" ")[0] for r in rulings if r.get("decision") == d["id"]}
      if fids & {"redesign", "proceed"}:  # spec section 4.2: a proceed closes the whole decision, as `redesign` does
        return False
      return any(o.split(" ")[0] not in fids for o in options)
    return d["id"] not in ruled

  return [d for d in foreman.get("decisions") or [] if pending(d)]


def ci_seen_at(uid: str, view: dict, card: dict):
  """When the card first saw the unit's current head with pending or absent CI, else None."""
  if view.get("ci") not in (None, "pending") or not view.get("head"):
    return None
  entry = next((h for h in reversed(card.get("heads") or []) if h["unit"] == uid), None)
  return entry["seen_at"] if entry and entry["head"] == view["head"] else None


def loop_ended(states: dict, ready_unlaunched: list, free_slots: int, merge_rounds=()) -> tuple:
  """The end condition: no launched unit active, and no ready unit unlaunched, nor a merge round `launch` would
  mark (U62), while a slot is free."""
  active = [uid for uid, state in states.items() if state == "active"]
  if active:
    return False, "in flight: " + ", ".join(active)
  if merge_rounds and free_slots > 0:
    return False, "merge round: " + ", ".join(merge_rounds)
  if ready_unlaunched and free_slots > 0:
    return False, "ready, unlaunched: " + ", ".join(ready_unlaunched)
  if ready_unlaunched:
    return True, "no free slot for " + ", ".join(ready_unlaunched)
  # spec sections 4.2 and 7.6: a `waiting proceed` or `waiting respec` unit holds no slot, so the wave ends; the
  # reason names the units the owner proceeds on or corrects the spec for
  kinds = [(k, [uid for uid, state in states.items() if state == f"waiting {k}"]) for k in ("proceed", "respec")]
  kinds = [(k, uids) for k, uids in kinds if uids]
  if kinds:
    return True, (f"every launched unit is clean, landed, stopped, pending, idle or {' or '.join(f'waiting {k}' for k, _ in kinds)}"
                  f" ({'; '.join(f'waiting {k}: ' + ', '.join(uids) for k, uids in kinds)})")
  return True, "every launched unit is clean, landed, stopped, pending or idle"


def respec_waiting(st, active: list) -> list:
  """Spec section 7.6: the active units that raised an open respec (`respec.open`) and have no live launch: each waits
  for the owner's correction and is not active. A failed read finds none (the unit stays active: the loop continues)."""
  if not active or not st.handoff_id:
    return []
  from superegm import respec  # at call time: `respec` reads `launch`'s records
  try:
    opened = {r.get("unit") for r in respec.open(st, st.handoff_id)}
    return [uid for uid in active if uid in opened and not respec.live_launch(st, uid)]
  except (core.HandoffError, ValueError, OSError):
    return []


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
  if word.startswith("owner: "):
    return "decision open"
  return "idle: review stalled" if review_exit == 5 else "redispatch"
