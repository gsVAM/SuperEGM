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
from superegm.launch import load_launches

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
  rounds, repo = data["rounds"], st.config["repo"]
  number = ((core.load_state(st.root).get("units") or {}).get(unit) or {}).get("pr", {}).get("number")
  if not number:
    raise core.HandoffError(f"{unit} has no watched PR: run `status` first")
  pr = core.gh_json(["pr", "view", str(number), "-R", repo, "--json", "number,headRefOid,baseRefName,body"])
  launches = load_launches(st, unit)
  rid = head_review_id(st, unit)
  recovered = recover_posted(st, unit, data, core.gh_pages(f"repos/{repo}/pulls/{number}/reviews"), args.runcard)
  if recovered:
    print(f"recovered {recovered}")
    return 1
  status_exit = review.status_code(rid, args.runcard) if rid else 0
  reason = dispatch_refusal(pr, core.read_ci(repo, pr["headRefOid"]), launches, rounds, data["decisions"],
                            data["rulings"], status_exit)
  if reason:
    print(f"dispatch refused: {reason}")
    return 1
  supersede(rounds)
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
  rounds.append({"round": n, "runcard": args.runcard, "launch": launches[-1]["round"], "head": None, "phase": "fetched",
                 "dispatch_id": did})
  data["dispatch_id"] = did
  core.save_foreman(st, unit, data)
  core.journal(st, f"{unit} round {n} dispatched {did} under {args.runcard}")
  print(f"{did} {child}")
  return 0


def recover_posted(st, unit: str, data: dict, reviews: list, runcard: str):
  """A `collected` round without an outcome whose review the PR already carries at the reviewed sha is
  counted `posted` (section 11); returns its outcome word, or None."""
  for entry in data["rounds"]:
    if entry.get("phase") != "collected" or entry.get("outcome") or not entry.get("head"):
      continue
    header = review.header(entry["round"], entry["head"])
    for posted in reviews:
      if (posted.get("body") or "").startswith(header) and posted.get("commit_id") == entry["head"]:
        return review.count_posted(st, unit, entry, posted["submitted_at"], head_review_id(st, unit), runcard)
  return None


def dispatch_refusal(pr: dict, ci: dict, launches: list, rounds: list, decisions: list, rulings: list,
                     status_exit: int):
  """Spec section 11's predicate, its first failing clause: CI concluded on the head, the latest launch
  terminal, no round posted since it, no decision pending, the review not stalled."""
  if not ci["check_runs"] and not ci["statuses"]:
    return "ci absent"
  if core.ci_verdict(ci) == "waiting-for-ci":
    return "ci pending"
  if not launches:
    return "no launch"
  latest = launches[-1]
  if not (latest["status"].startswith("exited") or latest["status"] == "interrupted"):
    return f"launch {latest['round']} not terminal"
  for entry in rounds:
    if entry.get("phase") == "posted" and entry.get("launch") == latest["round"]:
      return f"round {entry['round']} posted since launch {latest['round']}"
  ruled = {r.get("decision") for r in rulings}
  for decision in decisions:
    if decision["id"] not in ruled:
      return f"decision {decision['id']} pending"
  if status_exit == 5:
    return "review stalled"
  return None


def head_review_id(st, unit: str):
  """The unit's latest `reviews/*head-<unit>-c<n>` directory name, or None before the first dispatch."""
  folder = st.path("reviews")
  found = [(int(m.group(2)), p.name) for p in folder.iterdir()
           if (m := re.search(rf"(^|-)head-{re.escape(unit)}-c(\d+)$", p.name))] if folder.is_dir() else []
  return max(found)[1] if found else None


def supersede(rounds: list) -> None:
  """Every entry neither `posted` nor `collected` with a `not run` outcome is `collected (not run (superseded))`."""
  for entry in rounds:
    terminal = entry.get("phase") == "posted" or (
        entry.get("phase") == "collected" and (entry.get("outcome") or "").startswith("not run"))
    if not terminal:
      entry.update({"phase": "collected", "outcome": "not run (superseded)"})
