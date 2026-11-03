# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `run_verify` and `cmd_verify` over the union of every filing's list, the receipt keyed to the latest.

"""superegm verify: read every write of every filing back and record the receipt."""

from pathlib import Path

import superegm as core
from superegm import gate

WRITES = frozenset(["state"])  # the store kinds this subcommand writes
SKILLS = frozenset(["file"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "verify", "read every write of every filing back and record the receipt")
  p.add_argument("--spec", dest="design", required=True, help="the approved spec the filing is for")
  p.set_defaults(run=run, writes=WRITES)


def checkable_union(state, writes) -> list:
  """The latest list first, then from every other filing its unit issues and links, de-duplicated
  by (kind, unit, blocker); `repo` and `gate` items dropped. Earlier filings are compared on their
  unit issues: the tracking issue belongs to the latest list (spec section 7)."""
  latest = state["confirmed"]["sha256"]
  earlier = [w for f in state.get("filings") or [] if f.get("sha256") != latest
             for w in f["writes"] if w[0] in ("issue", "sub_issue", "blocked_by") and w[1] != "tracking"]
  seen, union = set(), []
  for item in [w for w in writes if w[0] not in ("repo", "gate")] + earlier:
    key = (item[0], item[1], item[2] if item[0] == "blocked_by" else None)
    if key not in seen:
      seen.add(key)
      union.append(item)
  return union


def run_verify(handoff, writes=None):
  state, repo = handoff.state, core.require_repo(handoff)
  confirmed = state.get("confirmed") or {}
  if not confirmed.get("sha256"):
    raise core.HandoffError("no confirmed write list in the state: run dry-run first")
  if writes is None:
    # Verify what the owner confirmed, not what the plan says now: an edited
    # local plan must not be able to make a stale receipt look clean.
    writes = confirmed.get("writes") or []
  if core.sha256_text(core.canonical(writes)) != confirmed["sha256"]:
    raise core.HandoffError("the write list no longer matches the confirmed snapshot: "
                            "run dry-run again and re-confirm before verifying")
  checkable = checkable_union(state, writes)
  problems, checked = [], 0
  units, tracking = state.get("units", {}), state.get("tracking", {})
  existing_labels = None
  subs = None
  for item in checkable:
    kind = item[0]
    try:
      if kind == "label":
        if existing_labels is None:
          existing_labels = {l["name"] for l in core.gh_pages(f"repos/{repo}/labels")}
        if item[1] not in existing_labels:
          problems.append(f"MISMATCH label `{item[1]}` is missing on {repo}")
        checked += 1
      elif kind == "issue":
        target = tracking if item[1] == "tracking" else units.get(item[1], {})
        if not target.get("number"):
          continue
        live = core.gh_json(["issue", "view", str(target["number"]), "-R", repo, "--json", "body,labels"])
        numbers = {u: d["number"] for u, d in units.items() if d.get("number")}
        expected = core.body.fill_numbers(item[4], numbers, tracking.get("number"))
        if core.body.normalise(live.get("body") or "") != core.body.normalise(expected):
          problems.append(f"MISMATCH body of #{target['number']} ({item[1]}) differs from the rendered body")
        live_labels = {l["name"] for l in live.get("labels", [])}
        expected_labels = set(item[3])
        if not expected_labels <= live_labels:
          problems.append(f"MISMATCH labels of #{target['number']} ({item[1]}): missing {sorted(expected_labels - live_labels)}")
        checked += 1
      elif kind == "sub_issue":
        if not tracking.get("number") or not units.get(item[1], {}).get("id"):
          continue
        if subs is None:
          subs = {s["id"] for s in core.gh_pages(f"repos/{repo}/issues/{tracking['number']}/sub_issues")}
        if units[item[1]]["id"] not in subs:
          problems.append(f"MISMATCH sub-issue link missing for {item[1]}")
        checked += 1
      elif kind == "blocked_by":
        blocked, blocker = units.get(item[1], {}), units.get(item[2], {})
        if not blocked.get("number") or not blocker.get("id"):
          continue
        ids = {b["id"] for b in core.gh_pages(f"repos/{repo}/issues/{blocked['number']}/dependencies/blocked_by")}
        if blocker["id"] not in ids:
          problems.append(f"MISMATCH blocked-by link missing: {item[1]} blocked by {item[2]}")
        checked += 1
    except core.GhError as error:
      problems.append(f"MISMATCH read failed for {item[:2]}: {error}")
  # Expected-only checking cannot see a link the handoff no longer wants: after
  # an amendment removes a blocker, apply leaves the old link on GitHub and a
  # clean receipt would let status treat the unit as ready.
  if tracking.get("number"):
    expected_subs = {units[w[1]]["id"] for w in checkable
                     if w[0] == "sub_issue" and units.get(w[1], {}).get("id")}
    try:
      if subs is None:
        subs = {s["id"] for s in core.gh_pages(f"repos/{repo}/issues/{tracking['number']}/sub_issues")}
      for extra in sorted(subs - expected_subs):
        problems.append(f"MISMATCH obsolete sub-issue link on #{tracking['number']}: issue id {extra}")
    except core.GhError as error:
      problems.append(f"MISMATCH read failed for obsolete sub-issue check: {error}")
  for uid, record in units.items():
    if not record.get("number"):
      continue
    expected_blockers = {units[w[2]]["id"] for w in checkable
                         if w[0] == "blocked_by" and w[1] == uid
                         and units.get(w[2], {}).get("id")}
    try:
      live_blockers = {b["id"] for b in
                       core.gh_pages(f"repos/{repo}/issues/{record['number']}/dependencies/blocked_by")}
    except core.GhError as error:
      problems.append(f"MISMATCH read failed for obsolete blocked-by check on {uid}: {error}")
      continue
    for extra in sorted(live_blockers - expected_blockers):
      problems.append(f"MISMATCH obsolete blocked-by link on #{record['number']} ({uid}): "
                      f"issue id {extra}; remove it by hand")
  complete = checked == len(checkable) and not any(p.startswith("MISMATCH read failed") for p in problems)
  state["verify"] = {"sha256": confirmed.get("sha256") or state.get("confirmed_sha256"),
                     "complete": complete,
                     "checked": f"{checked} of {len(checkable)}", "problems": problems,
                     "verified_at": core.now_iso()}
  core.save_state(handoff.artifact_dir, state)
  print(f"verify: {'complete' if complete else 'incomplete'}, {checked} of {len(checkable)} checked, "
        f"{len(problems)} problem(s)")
  for problem in problems:
    print(problem)
  return 0 if complete and not problems else 1


def run(args):
  core.require_runcard(args, SKILLS)
  return run_verify(gate.open_handoff(Path(args.design)))
