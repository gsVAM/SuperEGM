# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_record_launch` as the record-launch module.

"""superegm record-launch: record `launched` and the run folder for a round."""

from pathlib import Path

import superegm as core

WRITES = frozenset(['foreman'])  # the store kinds this subcommand writes


def register(subparsers):
  p = core.add_parser(subparsers, "record-launch", "record `launched` and the run folder for a round")
  p.add_argument("--unit", required=True)
  p.add_argument("--round", type=int, default=1)
  p.add_argument("--run-folder", dest="run_folder")
  p.add_argument("--not-run", dest="not_run", help="record the lane as not run, with this reason")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  """Record `launched` and the run folder for a round.

  The elephant runs this the moment the runner prints its folder. Without it
  nothing persists between `prepared` and `collected` on the no-teams path:
  the prepare subagent has already returned and the collect subagent is not
  spawned until the run completes, so a session that ends in between restarts
  the round and abandons a finished Astra run."""
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  data = core.load_foreman(handoff.store, args.unit)
  rounds = data.setdefault("rounds", {})
  record = rounds.setdefault(str(args.round), {})
  if args.not_run:
    if record.get("run_folder"):
      # A launch was recorded: the runner may still be reading its worktree.
      # Erasing the folder here would hide that from every cleanup guard
      # (R10-01). Skipping the result is `collect --not-run`, after the
      # runner has terminated; recording "not run" is only for a round that
      # never launched.
      raise core.HandoffError(
          f"{args.unit} round {args.round} already recorded a launch "
          f"({record['run_folder']}); `record-launch --not-run` is for a round "
          f"that never launched. Wait for the completion notice, then "
          f"`collect --unit {args.unit} --round {args.round} --not-run <reason>`.")
    status = f"not run ({args.not_run})"
    record.update({"phase": "launched", "run_folder": None,
                   "status": status, "run_status": status, "at": core.now_iso()})
  else:
    folder = Path(args.run_folder).expanduser()
    existing = record.get("run_folder")
    if existing and Path(existing) != folder:
      # One round, one launch. Re-pointing a live round at another folder lets
      # an old completed result be collected in its place (R11-02); a new
      # launch is a new round.
      raise core.HandoffError(
          f"{args.unit} round {args.round} already recorded launch {existing}; a "
          f"different folder ({folder}) means a new launch, which is a new round.")
    if existing:
      print(f"{args.unit} round {args.round}: launch already recorded ({existing})")
      return 0
    record.update({"phase": "launched", "run_folder": str(folder),
                   "status": "running", "run_status": "running", "at": core.now_iso()})
  core.save_foreman(handoff.store, args.unit, data)
  print(f"{args.unit} round {args.round}: {record['status']} "
        f"({record['run_folder'] or 'no run folder'})")
  return 0
