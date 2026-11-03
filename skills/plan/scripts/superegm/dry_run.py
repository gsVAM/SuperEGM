# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_dry_run` over the unfiled units of the store's plan copy, under the converged gate; the tracking rewrite announced on a later filing.

"""superegm dry-run: preflight reads and handoff_dryrun.md over the unfiled units; records the confirmed write list."""

from pathlib import Path

import superegm as core
from superegm import apply, gate, scan

WRITES = frozenset(["file", "state"])  # the store kinds this subcommand writes
SKILLS = frozenset(["file"])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "dry-run", "preflight reads and handoff_dryrun.md over the unfiled units; records the confirmed write list")
  p.add_argument("--spec", dest="design", required=True, help="the approved spec the filing is for")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  core.require_runcard(args, SKILLS)
  handoff = gate.open_handoff(Path(args.design))
  state = handoff.state
  gate.require_gate(handoff)
  plan_sha, bodies_sha = core.gate_hashes(handoff)
  if len(handoff.plan.units) > core.MAX_UNITS:
    raise core.HandoffError(f"{len(handoff.plan.units)} units: split the handoff (a parent takes at most {core.MAX_UNITS} sub-issues)")
  problems = scan.scan_handoff(handoff)
  if problems:
    raise core.HandoffError("scan failed:\n" + "\n".join(problems))
  checks = core.preflight(handoff)
  missing_extra = [l for l in handoff.labels["extra"] if l not in checks["labels"]]
  if missing_extra:
    raise core.HandoffError(f"create the label `{missing_extra[0]}` on {handoff.config['repo']} or remove it from `extra`")
  labels = {}
  for name in apply.derived_labels(handoff):
    labels[name] = state.get("labels", {}).get(name) if state.get("labels", {}).get(name) == "done" \
        else ("exists" if name in checks["labels"] else "missing")
  writes = gate.pending_writes(handoff)
  to_create = [n for n, s in labels.items() if s == "missing"]
  issues = [w for w in writes if w[0] == "issue"]
  subs = [w for w in writes if w[0] == "sub_issue"]
  blocked = [w for w in writes if w[0] == "blocked_by"]
  total = len(to_create) + len(issues) + len(subs) + len(blocked)
  confirmed = core.sha256_text(core.canonical(writes))
  tracking = (state.get("tracking") or {}).get("number")
  lines = [f"# Handoff dry run: `{handoff.handoff_id}` on {handoff.config['repo']}", "",
           f"Config: `{handoff.config['_source']}`. Remote: `{handoff.config['remote']}`. "
           f"Template: `{handoff.config['issue_template'] or 'default (built into the helper)'}`.",
           f"Gate: plan `{plan_sha[:12]}`, bodies `{bodies_sha[:12]}` ({state.get('gate', {}).get('passed', 'recorded')}).",
           f"Preflight: gh auth ok; push access ok; {len(checks['labels'])} labels on the repository.", "",
           f"Writes: {len(to_create)} labels, {len(issues)} issues (1 tracking, {len(issues) - 1} units), "
           f"{len(subs)} sub-issue links, {len(blocked)} blocked-by links; {total} content-creating "
           f"writes (GitHub allows 80 per minute and 500 per hour)."]
  if tracking:
    lines.append(f"Tracking issue #{tracking} will be rewritten with the units of every filing.")
  if total > core.WRITE_WARN:
    lines.append(f"WARNING: {total} writes exceed {core.WRITE_WARN}: run `apply --yes --max-writes N` in several calls.")
  lines += ["", f"Confirmed write list sha256: `{confirmed}`", "", "## Labels", ""]
  lines += [f"- `{n}`: {'create' if s == 'missing' else s}" for n, s in labels.items()]
  lines += [f"- `{n}`: extra (exists)" for n in handoff.labels["extra"]]
  lines += ["", "## Writes in order", ""]
  for item in issues:
    lines += [f"### issue {item[1]}", "", f"Title: {item[2]}", f"Labels: {', '.join(item[3])}", "",
              "```markdown", item[4].rstrip("\n"), "```", ""]
  lines += [f"- sub-issue: {w[1]} under the tracking issue" for w in subs]
  lines += [f"- blocked-by: {w[1]} blocked by {w[2]}" for w in blocked]
  report = handoff.store.path("file", "handoff_dryrun.md")
  core.atomic_write(report, "\n".join(lines) + "\n")
  state["labels"] = labels
  state["confirmed_sha256"] = confirmed
  # The confirmed snapshot is the contract the owner approved. Keep the write
  # list itself, not only its hash: verify compares GitHub with what was
  # confirmed, never with a plan re-parsed since.
  state["confirmed"] = {"sha256": confirmed, "repo": handoff.config["repo"],
                        "host": core.GH_HOSTNAME, "handoff_id": handoff.handoff_id,
                        "writes": writes, "labels_config": dict(handoff.labels),
                        "at": core.now_iso()}
  state["dry_run"] = {"labels": len(to_create), "issues": len(issues), "sub_issues": len(subs),
                      "blocked_by": len(blocked), "writes": total, "at": core.now_iso()}
  core.save_state(handoff.artifact_dir, state)
  print(f"dry run written to {report}: {len(issues)} issues, "
        f"{len(subs)} sub-issue links, {len(blocked)} blocked-by links, {len(to_create)} labels to create; "
        f"{total} writes; confirmed_sha256 {confirmed[:12]}")
  return 0
