# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_status` as the status module; `--wait` returns event lines (U09b).

"""superegm status: landed and ready sets, PRs, CI; refuses without a complete receipt.
`--wait <s>` polls, reading only, and prints every unreported event line, or `deadline`."""

import superegm as core

WRITES = frozenset(['state'])  # the store kinds this subcommand writes
SKILLS = frozenset(['wave'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "status", "landed and ready sets, PRs, CI; refuses without a complete receipt")
  p.add_argument("--wait", type=int, help="seconds; exit when a unit changes or the deadline passes")
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
    pr["head_seen_at"] = core.NOW()
    record = state["units"].setdefault(uid, {})
    # The selection is the user's and is merged on its own terms; `pr` below is
    # only the first observation of it.
    # One write: a selection whose observation describes a different PR would
    # send `prepare` to the old one.
    record["watch"] = {"number": int(number), "at": core.now_iso()}
    record["pr"] = pr
    record["status"] = None
  if args.wait:
    print("\n".join(wait_events(handoff, args.wait)))
    return 0
  for uid in args.confirm_landed or []:
    view = core.unit_view(handoff, uid)
    if view["pr"] or not core.issue_closed_completed(handoff, uid):
      raise core.HandoffError(
          f"--confirm-landed {uid} is only for an issue closed as completed with "
          f"no watched PR; {uid} is {view['status']}")
    target = state["units"].setdefault(uid, {})
    target["landed_confirmed"] = core.now_iso()
    target.pop("landed_confirmation_void", None)
  summary, open_blocking = core.status_pass(handoff)
  core.print_status(handoff, summary, open_blocking)
  return 0


def wait_events(handoff, seconds: int) -> list:
  """Poll `status_pass` (reading only) until a unit changes or the deadline passes; one
  state write on return. Until the event lines land (S2) the wake line is EGM's `changed: <units>`."""
  state = handoff.state
  fingerprint = lambda s: {u: (v["pr"], v["head"], v["status"], v["landed"],
                              v.get("issue_state"), v.get("pr_state"),
                              v.get("base_ref"), v.get("base_sha"))
                           for u, v in s["units"].items()}
  previous = fingerprint(state["status"]) if state.get("status") else None
  deadline = core.NOW() + seconds
  while True:
    summary, _ = core.status_pass(handoff, save=False)
    current = fingerprint(summary)
    previous = current if previous is None else previous
    changed = sorted(u for u in current if current[u] != previous.get(u))
    if changed:
      lines = ["changed: " + ", ".join(changed)]
      break
    if core.NOW() >= deadline:
      lines = ["deadline"]
      break
    core.SLEEP(min(core.WAIT_INTERVAL, max(1, deadline - core.NOW())))
  # One write, when the wait is over: while it waits it only reads, so no
  # other command can be overwritten by a sleeping watcher.
  core.save_state(handoff.artifact_dir, state)
  return lines
