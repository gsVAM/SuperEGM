# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_status` as the status module; `--wait` returns event lines (U09b); the `ruling` event and a status line after a comment's deviation headings (U22); the board's one write per `wave` pass, `post_board` (U30); the tick's read, `tick_trigger` (U24); the watchdog's `stalled` line, its predicate and `head_time` (U31).

"""superegm status: landed and ready sets, PRs, CI; refuses without a complete receipt.
`--wait <s>` polls, reading only, and prints every unreported event line, or `deadline`. Under a `wave` card
every pass, `--wait` included, also reads the tracking issue once and rewrites its board when the rows changed
(`post_board`, the one GitHub write, its `board_changed_at` save and a failed write's journal line, spec 11.1)."""

import calendar
import json
import re
import time
from pathlib import Path

import superegm as core
from superegm import apply
from superegm.decision import edited_after_record, ruling_of
from superegm.launch import load_launches, terminal
from superegm.report import board_table
from superegm.review import collaborator_role, read_threads, thread_severity  # bound here: a test patches status's names

WRITES = frozenset(['state'])  # the store kinds this subcommand writes
SKILLS = frozenset(['wave', 'integrate'])  # the skills whose card this subcommand accepts
# a status line anywhere in the comment: a deviation's `**Deviation**` headings come before it (the builder orders)
STATUS_RE = re.compile(r"^\*\*Builder status:\*\*\s*(DONE|DONE_WITH_CONCERNS|BLOCKED|NEEDS_CONTEXT)\b", re.M)
# The saved fingerprint of a unit (spec section 11): every `--wait` reports the keys that differ from it.
EMPTY = {"pr": None, "head": None, "ci": None, "exit": None, "builder_status": None, "landed": False,
         "closed": [None, None], "rulings": []}


def register(subparsers):
  p = core.add_parser(subparsers, "status", "landed and ready sets, PRs, CI; refuses without a complete receipt; "
                         "under a wave card, writes the board into the tracking issue")
  p.add_argument("--wait", type=int, help="seconds; print every unreported event line, or deadline")
  p.add_argument("--watch", action="append", help="U03=412 records that PR for the unit")
  p.add_argument("--confirm-landed", action="append", help="unit the user confirmed landed")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  core.require_frozen_units(handoff)
  state = handoff.state
  core.require_receipt(state)
  core.require_repo(handoff)
  state.setdefault("units", {})
  if args.wait and (args.watch or args.confirm_landed):
    raise core.HandoffError(
        "--wait only watches; it does not record a choice. Run `status --watch "
        "<unit>=<pr>` or `--confirm-landed <unit>` on its own first, then "
        "`status --wait`.")
  for item in args.watch or []:
    uid, _, number = item.partition("=")
    if uid not in handoff.plan.units or not number.isdigit():
      raise core.HandoffError(f"--watch takes U<nn>=<pr number>, got {item}")
    pr = core.read_pr(handoff.config["repo"], int(number))
    record = state["units"].setdefault(uid, {})
    # The selection is the user's and is merged on its own terms; `pr` below is
    # only the first observation of it.
    # One write: a selection whose observation describes a different PR would
    # send `prepare` to the old one.
    record["watch"] = {"number": int(number), "at": core.now_iso()}
    record["pr"] = pr
    record["status"] = None
  if args.wait:
    print("\n".join(wait_events(handoff, args.wait, card)))
    return 0
  for uid in args.confirm_landed or []:
    view = unit_view(handoff, uid)
    if view["pr"] or not core.issue_closed_completed(handoff, uid):
      raise core.HandoffError(
          f"--confirm-landed {uid} is only for an issue closed as completed with "
          f"no watched PR; {uid} is {view['status']}")
    target = state["units"].setdefault(uid, {})
    target["landed_confirmed"] = core.now_iso()
    target.pop("landed_confirmation_void", None)
  summary, open_blocking = core.status_pass(handoff)
  if post_board(handoff, card, {**summary, "units": {uid: fingerprint(unit) for uid, unit in summary["units"].items()}}):
    core.save_state(handoff.artifact_dir, handoff.state)
  core.print_status(handoff, summary, open_blocking)
  return 0


def post_board(handoff, card: dict, status: dict) -> bool:
  """The board's one write (spec section 11.1), under a `wave` card only: `board_table` over the pass's
  snapshot spliced into the tracking issue's body, read once; `apply.edit_issue` and `board_changed_at` set
  to the pass time when the rows changed. A failed read or write is journaled and never fails the pass,
  `board_changed_at` kept so the next pass writes again; on equal rows the held board's header time is
  adopted when the state's differs (a landed write whose save was lost). True when `board_changed_at` changed."""
  number = (handoff.state.get("tracking") or {}).get("number")
  if card.get("skill") != "wave" or not number:
    return False
  repo, at = handoff.config["repo"], core.now_iso()
  block = board_table(handoff, {**handoff.state, "status": status, "board_changed_at": at}, card, core.NOW())
  try:
    body = (core.gh_json(["api", f"repos/{repo}/issues/{number}"]) or {}).get("body") or ""
    spliced = apply.splice_board(body, block)
    if spliced == body:
      # Equal rows. A write that landed with its response lost, or before its save, left the issue's time
      # unrecorded: the held board's time is the one copy, so the state takes it.
      held = apply.board_changed_at(body)
      if held and held != handoff.state.get("board_changed_at"):
        handoff.state["board_changed_at"] = held
        return True
      return False
    apply.edit_issue(repo, number, spliced, handoff.artifact_dir)
  except core.GhError as error:
    core.journal(handoff.store, f"board write failed: {error}")
    return False
  handoff.state["board_changed_at"] = at
  return True


def wait_events(handoff, seconds: int, card: dict) -> list:
  """Poll `status_pass` (reading only) until a unit has an unreported event or the deadline
  passes; the event lines, or `deadline`; one state write on return. Before that write, under a
  `wave` `card`, `post_board` reads the tracking issue once and, when the rows changed, rewrites
  its board (`gh issue edit`, `board_changed_at`), a failed read or write journaled `board write failed`."""
  state = handoff.state
  previous = (state.get("status") or {}).get("units") or {}
  deadline = core.NOW() + seconds
  while True:
    summary, _ = core.status_pass(handoff, save=False)
    lines = [line for uid in handoff.graph.order
             for line in unit_events(uid, previous.get(uid), summary["units"][uid])]
    if lines or core.NOW() >= deadline:
      break
    core.SLEEP(min(core.WAIT_INTERVAL, max(1, deadline - core.NOW())))
  # One write, when the wait is over, the only writer of `status.units`: while it waits it only
  # reads, so no other command can be overwritten by a sleeping watcher.
  state["status"] = {**summary, "units": {uid: fingerprint(unit) for uid, unit in summary["units"].items()}}
  post_board(handoff, card, state["status"])
  core.save_state(handoff.artifact_dir, state)
  return lines or ["deadline"]


def ci_word(verdict: str):
  """`ci_verdict`'s word on the `head` line: `green`, `red:<name,…>` or `pending`; None for a merged PR."""
  if verdict == "merged":
    return None
  if verdict == "ci green":
    return "green"
  if verdict.startswith("ci red ("):
    return "red:" + verdict[len("ci red ("):-1].replace(", ", ",")
  return "pending"


def epoch(stamp: str) -> float:
  """The seconds of a `%Y-%m-%dT%H:%M:%SZ` stamp."""
  return float(calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")))


def head_time(worktree) -> float | None:
  """The committer time of the worktree's `HEAD` (`git log -1 --format=%ct`), a local read; None when git fails."""
  try:
    out = core.run_git(["log", "-1", "--format=%ct"], Path(worktree), check=False).strip()
  except (OSError, TypeError):
    return None
  return float(out) if out.isdigit() else None


def own_commit(entry: dict, worktree_head_time: float | None) -> float | None:
  """The launch's own newest commit: the worktree head's time when newer than the entry's `started_at`, else None
  (a base commit older than the launch is none of its own)."""
  if worktree_head_time is None or not entry.get("started_at"):
    return None
  return worktree_head_time if worktree_head_time > epoch(entry["started_at"]) else None


def stalled(entry: dict, worktree_head_time: float | None, now: float, minutes: int) -> int | None:
  """The watchdog's one predicate (spec section 11.1, U31): a `running` launch without the `kill_failed` mark and
  with no exit file, whose newest own commit (or `started_at` when it has none) is `minutes` or more old; the
  whole minutes since then, or None."""
  if entry.get("status") != "running" or entry.get("kill_failed") or not entry.get("started_at"):
    return None
  if Path(entry["result_file"] + ".exit").is_file():
    return None
  since = own_commit(entry, worktree_head_time) or epoch(entry["started_at"])
  waited = int((now - since) // 60)
  return waited if waited >= minutes else None


def builder_facts(st, uid: str, comments: list, config: dict | None = None) -> tuple:
  """From the latest launch by `round`: `[round, <text of its exit file>]` when that file exists,
  and `[id, word, login]` of the last `**Builder status:**` comment (one opening with that line or with its
  `**Deviation**` headings) created at or after its
  `started_at` (every such comment when nothing was launched). The word is masked (None) while
  the launch is not terminal (spec section 4), so it folds into the exit line it belongs to; both are masked for
  an `exited (stalled)` launch, whose stalled line was its exit line (U31). The third value is the watchdog's
  `[minutes, last commit stamp or None, word or None]` when `config` is given and the latest launch is `stalled`
  (the word unmasked: the stall's question carries it), else None."""
  latest = max(load_launches(st, uid), key=lambda entry: entry["round"], default=None)
  exit = None
  if latest:
    exit_file = Path(latest["result_file"] + ".exit")
    exit = [latest["round"], core.read_text(exit_file).strip()] if exit_file.is_file() else None
  since = latest["started_at"] if latest else ""
  status, builders = None, builder_logins(st)
  for comment in comments:
    if builders and (comment.get("user") or {}).get("login") not in builders:
      continue  # a stranger's status line is no builder's (spec section 11.2); a store whose `launch` recorded no login reads all
    body = comment.get("body") or ""
    # a status comment opens with its status line or its `**Deviation**` headings (the orders' shapes); a status
    # line quoted below another comment's first line, such as an owner's ruling, is not one
    match = STATUS_RE.search(body) if body.startswith(("**Builder status:**", "**Deviation")) else None
    if match and (comment.get("created_at") or "") >= since:
      status = [comment["id"], match.group(1), (comment.get("user") or {}).get("login")]
  stall = None
  # the git read only for a launch the predicate can hold of (running, unmarked, a worktree, no exit file); a
  # `started_at` that does not parse is no stall, as record-launch reads it
  if latest and config and latest.get("worktree") and latest.get("status") == "running" and not latest.get("kill_failed") and not exit:
    try:
      head = head_time(latest["worktree"])
      waited = stalled(latest, head, core.NOW(), config["builder"]["stall_minutes"])
      last = own_commit(latest, head) if waited is not None else None
    except (ValueError, TypeError):
      waited = None
    if waited is not None:
      stall = [waited, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last)) if last else None, status[1] if status else None]
  if latest and latest.get("status") == "exited (stalled)":
    return None, None, stall
  return exit, None if latest and not terminal(latest) else status, stall


def closed_facts(repo: str, issue: dict, pr, landed: bool) -> list:
  """`[pr fact, issue fact]`, each `[number, login]`: a PR closed unmerged, an issue closed short of
  a landing; the login from the issue already fetched, the PR's from `gh api repos/<repo>/issues/<pr>`."""
  facts = [None, None]
  if landed:
    return facts
  if pr and not pr.get("merged_at") and (pr.get("state") or "").upper() == "CLOSED":
    who = (core.gh_json(["api", f"repos/{repo}/issues/{pr['number']}"]) or {}).get("closed_by") or {}
    facts[0] = [pr["number"], who.get("login") or "unknown"]
  if issue.get("state") == "closed":
    facts[1] = [issue.get("number"), (issue.get("closed_by") or {}).get("login") or "unknown"]
  return facts


def ruling_facts(store, uid: str, comments: list, owners) -> list:
  """One `Ruling` per comment of an owner `ruling_of` parses (spec section 13.2); a comment the unit's `rulings[]`
  names as `posted` is skipped unless its `updated_at` is later than that entry's `posted_at` (a by-hand `--posted`
  record's: the comment's `updated_at` when recorded, else its `created_at`; a session post's: its `created_at`, read
  back, so any edit of it since its creation is one), so an unedited recorded post is no event and an owner's edit of it is one.
  For an `unread` entry (the session's own post whose GitHub time was never read back, `posted_at` the host's) the edit
  is an `updated_at` later than the comment's own `created_at` (`decision.edited_after_record`)."""
  posted = {}
  for entry in core.load_foreman(store, uid).get("rulings") or []:
    kind, _, cid = (entry.get("posted") or "").partition("comment ")
    if not kind and cid.isdigit():
      posted[int(cid)] = entry
  facts = []
  for comment in comments:
    ruling = ruling_of(comment, owners)
    if ruling and (ruling.comment_id not in posted or edited_after_record(comment, posted[ruling.comment_id])):
      facts.append(ruling)
  return facts


def ruling_entries(facts: list, comments: list) -> list:
  """The saved `rulings` key: `[comment id, kind, subject, option, login, updated_at or created_at]` per fact."""
  stamps = {c.get("id"): c.get("updated_at") or c.get("created_at") for c in comments}
  return [[r.comment_id, r.kind, r.subject, r.option, r.login, stamps.get(r.comment_id)] for r in facts]


def fingerprint(unit: dict) -> dict:
  """The saved keys of a unit (lists, not tuples: the saved one comes back from JSON)."""
  return {key: unit[key] for key in EMPTY}


def unit_events(uid: str, previous, current: dict) -> list:
  """One line per event of the unit since `previous` (`EMPTY` when nothing was saved), kinds in
  the order head, exit, status, stalled, landed, closed, ruling; a builder's exit carries its status word. The
  `stalled` line (U31) is no fingerprint's: it is emitted at every pass while the predicate holds."""
  before = {**EMPTY, **(previous or {})}
  lines = []
  if current["ci"] is not None and any(current[k] != before[k] for k in ("pr", "head", "ci")):
    lines.append(f"{uid} head pr={current['pr']} sha={current['head']} ci={current['ci']}")
  status = current["builder_status"]
  tail = f" comment={status[0]} by={status[2]}" if status else ""
  if current["exit"] is not None and current["exit"] != before["exit"]:
    lines.append(f"{uid} exit code={current['exit'][1]} pr={current['pr'] or 'none'} "
                 f"status={status[1] if status else 'none'}{tail}")
  elif status and status != before["builder_status"]:
    lines.append(f"{uid} status word={status[1]}{tail}")
  if current.get("stalled"):
    waited, last, word = current["stalled"]
    lines.append(f"{uid} stalled ({waited} min; last commit {last or 'none'}) pr={current['pr'] or 'none'} status={word or 'none'}")
  if current["landed"] and not before["landed"]:
    lines.append(f"{uid} landed pr={current['pr'] or 'none'}")
  for what, fact, earlier in zip(("pr", "issue"), current["closed"], before["closed"]):
    if fact and fact != earlier:
      lines.append(f"{uid} closed {what}={fact[0]} by={fact[1]}")
  for entry in current["rulings"]:
    if entry not in before["rulings"]:
      cid, kind, subject, option, login = entry[:5]
      what = " ".join(part for part in (kind, subject, option) if part)
      lines.append(f"{uid} ruling by {login}: {what} (comment {cid})")
  return lines


def builder_logins(st) -> set:
  """The builder logins `launch` recorded on the handoff's cards (`builder[].login`)."""
  folder = (st.root if st.legacy else st.base()) / "runcards"
  logins = set()
  for path in folder.glob("*.json"):
    card = json.loads(core.read_text(path))
    if card.get("handoff", st.handoff_id) == st.handoff_id:
      logins |= {b.get("login") for b in card.get("builder") or [] if isinstance(b, dict)}
  return logins - {None}


def tick_trigger(handoff) -> str | None:
  """What a tick's session would have to do (spec section 11.2), from one `status_pass` that saves nothing, in order:
  the proof the tick applied to the handoff's newest tick launch, backed-off launches dropped first (`reboot <n>` for
  one recorded `interrupted (reboot)`, `exit-file <card>` for one whose exit file exists and whose top-level `wave`
  card is `interrupted`); the first event line against `state.status.units` (a `stalled` line at every tick while its
  predicate holds, no fingerprint saving it away, U31), a `status word=` event by a login no card
  records as a builder skipped; `<uid> ready` for a unit the read finds ready and the saved `ready` lacks; an
  un-ingested thread above `low` on the latest posted round's head, by U21's reader, a stopped unit's threads skipped;
  `first launch` while `state.status` is absent; else None, the nothing-to-do predicate."""
  st, state = handoff.store, handoff.state
  launches = [e for e in core.load_driver(st).get("launches") or [] if not core.backed_off(e)]
  if launches:
    last = launches[-1]
    if last.get("status") == "interrupted (reboot)":
      return f"reboot {last['round']}"
    if Path(last["exit_file"]).is_file():
      mine = [(p.stem, c) for p, c in core.top_wave_cards(st) if c.get("driver_card") == last["card"]]
      if mine and mine[-1][1].get("interrupted_at"):
        return f"exit-file {mine[-1][0]}"
  saved = state.get("status")
  previous = (saved or {}).get("units") or {}
  summary, _ = core.status_pass(handoff, save=False)
  builders = builder_logins(st)
  for uid in handoff.graph.order:
    for line in unit_events(uid, previous.get(uid), summary["units"][uid]):
      if " status word=" in line and line.rsplit(" by=", 1)[-1] not in builders:
        continue  # a `**Builder status:**` comment a stranger wrote buys no session
      return line
  if saved:
    for uid in summary.get("ready") or []:
      if uid not in (saved.get("ready") or []):
        return f"{uid} ready"
  repo, config = handoff.config["repo"], handoff.config
  for uid in handoff.graph.order:
    foreman = core.load_foreman(st, uid)
    if foreman.get("stopped"):
      continue  # the session skips a stopped unit's threads, so they buy no session
    posted = [e for e in foreman.get("rounds") or [] if e.get("phase") == "posted" and e.get("head")]
    pr = ((state.get("units") or {}).get(uid) or {}).get("pr") or {}
    if not posted or not pr.get("number") or summary["units"][uid].get("landed"):
      continue
    head = max(posted, key=lambda e: e["round"])["head"]
    threads = [t for t in read_threads(repo, pr["number"], set(foreman.get("ingested") or []))
               if t.get("commit_id") == head and thread_severity(t, config, collaborator_role(repo, t["login"])) != "low"]
    if threads:
      return f"{uid} threads {len(threads)} un-ingested"
  return None if saved else "first launch"


def unit_view(handoff, uid):
  """EGM's view of one unit (its PR, CI and status word) plus the fingerprint keys."""
  repo, state = handoff.config["repo"], handoff.state
  record = state["units"].get(uid, {})
  number = record.get("number")
  issue = core.gh_json(["api", f"repos/{repo}/issues/{number}"]) or {}
  view = {"unit": uid, "number": number, "issue_state": issue.get("state"),
          "state_reason": issue.get("state_reason"), "launched": record.get("launched"),
          **EMPTY, "status": "waiting-for-pr", "candidates": []}
  chosen = (record.get("watch") or {}).get("number") or (record.get("pr") or {}).get("number")
  if chosen:
    pr = core.read_pr(repo, chosen)
  else:
    matches, candidates = core.discover_pr(handoff, uid, number)
    pr = None
    if len(matches) == 1:
      pr = matches[0]
    elif len(matches) > 1:
      view["status"] = "ambiguous: PRs " + ", ".join(f"#{m['number']}" for m in matches) + " (choose with --watch)"
    view["candidates"] = [c["number"] for c in candidates]
  if pr:
    record["pr"] = pr
    view["pr"], view["head"] = pr["number"], pr["head"]
    view["pr_state"] = "MERGED" if pr.get("merged_at") else (pr.get("state") or "OPEN").upper()
    if pr["merged_at"]:
      view["status"] = "merged"
    else:
      view["status"] = core.ci_verdict(core.read_ci(repo, pr["head"]))
    view["ci"] = ci_word(view["status"])
  closed_done = issue.get("state") == "closed" and issue.get("state_reason") == "completed"
  if pr and not pr.get("merged_at") and (pr.get("state") or "").upper() == "CLOSED":
    # Terminal: the builder abandoned this PR. Never rediscover silently; the
    # user picks the replacement with --watch.
    view["status"] = f"pr #{pr['number']} closed unmerged (choose a replacement with --watch)"
  override = record.get("landed_confirmed")
  if override and record.get("landed_confirmation_void"):
    override = None
  if override and not closed_done:
    # The exception is for an issue closed as completed with no watched PR; it
    # lapses the moment either of those stops being true.
    view["status"] = (f"landed confirmation no longer applies (issue is "
                      f"{issue.get('state')}/{issue.get('state_reason')}): "
                      f"re-confirm or watch a PR")
    # Persist it: closing the issue as completed again must not silently
    # revive a confirmation the user gave for an earlier state.
    record["landed_confirmation_void"] = core.now_iso()
    override = None
  if override and pr:
    view["status"] = (f"landed confirmation no longer applies (pr #{pr['number']} "
                      f"is now visible): re-confirm or let it merge")
    record["landed_confirmation_void"] = core.now_iso()
    override = None
  if override or (closed_done and pr and pr.get("merged_at")):
    view["landed"], view["status"] = True, "landed"
  elif closed_done and not pr:
    view["status"] = "closed (no watched PR)"
  elif view["candidates"] and view["status"] == "waiting-for-pr":
    view["status"] = "candidate: PRs " + ", ".join(f"#{c}" for c in view["candidates"]) + " (confirm with --watch)"
  comments = core.gh_pages(f"repos/{repo}/issues/{number}/comments?per_page=100")
  view["exit"], view["builder_status"], view["stalled"] = builder_facts(handoff.store, uid, comments, handoff.config)
  view["closed"] = closed_facts(repo, issue, pr, view["landed"])
  view["rulings"] = ruling_entries(ruling_facts(handoff.store, uid, comments, handoff.config.get("owners") or []), comments)
  record["status"] = view["status"]
  state["units"][uid] = record
  return view
