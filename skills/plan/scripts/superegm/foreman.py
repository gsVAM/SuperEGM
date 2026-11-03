# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the foreman subcommand (spec section 11).

"""superegm foreman dispatch: one evaluation of the dispatch predicate, the supersede of a non-terminal
round, the head review and the child card of a round."""

import argparse
import contextlib
import io
import re
from pathlib import Path

import superegm as core
from superegm import review

WRITES = frozenset({"foreman", "reviews", "runcards"})  # the store kinds this subcommand writes
SKILLS = frozenset({"wave"})  # the skills whose card this subcommand accepts


def register(subparsers):
  p = subparsers.add_parser("foreman", help="foreman dispatch")
  action = p.add_subparsers(dest="action", required=True)
  d = core.add_parser(action, "dispatch", "write a round entry and its dispatch id when the predicate holds")
  d.add_argument("--unit", required=True)
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  st = core.store(core.git_toplevel(Path.cwd()))
  unit, data = args.unit, core.load_foreman(st, args.unit)
  rounds = data["rounds"]
  supersede(rounds)
  rid = head_review_id(st, unit)
  if rid is None:
    with contextlib.redirect_stdout(io.StringIO()):
      code = review.run(argparse.Namespace(action="open", kind="head", artifact=unit, sha256=None,
                                           reviewers=",".join(st.config["reviewers"]["head"]), astra=None,
                                           runcard=args.runcard, unit=None, design=None, plan=None))
    if code != 0:
      raise core.HandoffError("review open failed")
  child = core.open_runcard(st, "wave", unit, parent=args.runcard)
  n = len(rounds) + 1
  did = f"d{n}"
  rounds.append({"round": n, "runcard": args.runcard, "launch": 1, "head": None, "phase": "fetched", "dispatch_id": did})
  data["dispatch_id"] = did
  core.save_foreman(st, unit, data)
  core.journal(st, f"{unit} round {n} dispatched {did} under {args.runcard}")
  print(f"{did} {child}")
  return 0


def head_review_id(st, unit: str):
  """The unit's latest `reviews/*head-<unit>-c<n>` directory name, or None before the first dispatch."""
  folder = st.path("reviews")
  found = [(int(m.group(1)), p.name) for p in folder.iterdir()
           if (m := re.search(rf"(^|-)head-{re.escape(unit)}-c(\d+)$", p.name))] if folder.is_dir() else []
  return max(found)[1] if found else None


def supersede(rounds: list) -> None:
  """Every entry neither `posted` nor `collected` with a `not run` outcome is `collected (not run (superseded))`."""
  for entry in rounds:
    terminal = entry.get("phase") == "posted" or (
        entry.get("phase") == "collected" and (entry.get("outcome") or "").startswith("not run"))
    if not terminal:
      entry.update({"phase": "collected", "outcome": "not run (superseded)"})
