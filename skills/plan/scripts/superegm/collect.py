# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_collect` as the collect module.

"""superegm collect: record a round as collected once its run folder has finished."""

import calendar
import json
import time
from pathlib import Path

import superegm as core


def register(subparsers):
  p = core.add_parser(subparsers, "collect", "record a round as collected once its run folder has finished")
  p.add_argument("--unit", required=True)
  p.add_argument("--round", type=int, default=1)
  p.add_argument("--verdict", help="clean | revise, as the round report concluded")
  p.add_argument("--not-run", dest="not_run", help="the lane did not run, with this reason")
  p.set_defaults(run=run)


def run(args):
  """Record a round as collected, after its run folder really finished.

  Cleanup guards read the saved round state, not the run folder, so a round
  that is reported in chat but never recorded stays `launched` and blocks
  `prepare --remove` for ever."""
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  data = core.load_foreman(handoff.store, args.unit)
  record = (data.get("rounds") or {}).get(str(args.round))
  if not record:
    raise core.HandoffError(f"{args.unit} has no round {args.round} to collect")
  allowed = ("prepared", "launched", "collected") if args.not_run else ("launched", "collected")
  if record.get("phase") not in allowed:
    raise core.HandoffError(
        f"{args.unit} round {args.round} is `{record.get('phase')}`, not "
        f"{' or '.join(f'`{p}`' for p in allowed)}"
        + ("" if args.not_run else ". If the lane never ran (it was unavailable, "
           "denied, or the launch failed), collect it with --not-run <reason>."))
  folder = record.get("run_folder")
  if folder and args.not_run:
    # A launched runner that the user chose to skip keeps running and keeps
    # reading its worktree. Recording the round as not run is fine; letting
    # cleanup remove that worktree while the process is alive is not. Require
    # a terminal result before a launched round can be collected at all.
    result = Path(folder) / "result.json"
    status = (json.loads(core.read_text(result)) or {}).get("status") if result.is_file() else None
    if status in (None, "running"):
      # Termination cannot be established from here (file inactivity proves
      # nothing - R12-01), so nothing is inferred: the round is recorded as
      # interrupted, the folder is kept, and NOTHING that could remove the
      # worktree follows from this state - landing refuses while any round is
      # non-terminal and tells the human to remove the worktree by hand.
      record["run_status"] = f"not run (interrupted: {args.not_run})"
      record.update({"phase": "collected", "collected_at": core.now_iso(), "verdict": None})
      data["phase"] = "collected"
      core.save_foreman(handoff.store, args.unit, data)
      print(f"{args.unit} round {args.round}: collected ({record['run_status']}; run folder "
            f"kept; the worktree stays until a human removes it or the unit lands)")
      return 0
  if folder and not args.not_run:
    result = Path(folder) / "result.json"
    if not result.is_file():
      raise core.HandoffError(f"{result} does not exist: the run has not finished, or record it "
                         f"with --not-run <reason>")
    payload = json.loads(core.read_text(result)) or {}
    status = payload.get("status")
    if status != "completed":
      raise core.HandoffError(f"{result} reports status `{status}`, not `completed`: wait for it, "
                         f"or record it with --not-run <reason>")
    # The result must be THIS round's: same unit file as --plan, same merge
    # base as --base. An older run's folder recorded by mistake is refused.
    # Identity is required, not optional (R12-02): a result that merely says
    # `completed`, or an older run of the same unit, must not be attributed to
    # this round's head.
    missing = [k for k in ("plan", "plan_sha256", "base", "repo", "started_at") if k not in payload]
    if missing:
      raise core.HandoffError(f"{result} lacks {', '.join(missing)}: not an inspect result this helper "
                         f"can attribute to round {args.round}")
    unit_file = handoff.unit_file(args.unit)
    checks = [("plan", str(payload["plan"]), str(unit_file)),
              ("plan_sha256", payload["plan_sha256"], core.sha256_file(unit_file)),
              ("base", payload["base"], record.get("merge_base")),
              ("repo", str(payload["repo"]), record.get("worktree"))]
    for name, got, want in checks:
      if want is not None and got != want:
        raise core.HandoffError(f"{result} {name} is {got}, this round's is {want}: it belongs to a "
                           f"different review")
    launched_at = calendar.timegm(time.strptime(record["at"], "%Y-%m-%dT%H:%M:%SZ")) \
        if record.get("at") else None
    if launched_at is not None and float(payload["started_at"]) < launched_at - 60:
      raise core.HandoffError(f"{result} started before this round's launch was recorded: it is an "
                         f"older run, not round {args.round}")
    record["run_status"] = "completed"
  else:
    record["run_status"] = f"not run ({args.not_run})" if args.not_run else "not run"
  record.update({"phase": "collected", "collected_at": core.now_iso(),
                 "verdict": args.verdict, "head": record.get("head")})
  data["phase"] = "collected"
  core.save_foreman(handoff.store, args.unit, data)
  print(f"{args.unit} round {args.round}: collected ({record['run_status']}"
        + (f", verdict {args.verdict}" if args.verdict else "") + ")")
  return 0
