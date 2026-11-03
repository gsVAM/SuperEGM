# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the review loop (spec section 8).

"""superegm review open|record|settle|status|rule: the one review loop (spec section 8)."""

import json
from pathlib import Path
import re
import sys

import superegm as core

WRITES = frozenset({"reviews", "foreman", "runcards"})  # the store kinds this subcommand writes
SKILLS = frozenset({"review-spec", "review-plan", "wave", "integrate"})  # the skills whose card this subcommand accepts
KINDS = ("spec", "plan", "head", "integrate")
REVIEWERS = ("design", "zoom-out", "comprehension", "readiness", "structural", "style",
             "codebase-details", "change-review", "set", "proportion")
FIRST = {"spec": "design", "plan": "readiness", "head": "change-review"}  # the kind's fixed first reviewer (section 5)
PANEL_OF = {"spec": "design,zoom-out", "integrate": "design", "plan": "readiness,proportion,set", "head": "change-review"}
LANE_KINDS = ("spec", "plan", "integrate")  # the kinds the Astra lane joins
SEVERITIES = ("high", "medium", "low")
DISPOSITIONS = ("fixed", "contested", "declined", "escalated", "fix-design")
RULINGS = ("continue", "accept", "stop")


def register(subparsers):
  p = subparsers.add_parser("review", help="the review loop")
  action = p.add_subparsers(dest="action", required=True)
  o = core.add_parser(action, "open", "open a review, or resume its open cycle")
  o.add_argument("--kind", choices=KINDS, required=True)
  o.add_argument("--artifact", required=True, help="the spec path, or the unit id")
  o.add_argument("--sha256", help="the bytes under review (a plan body or a head); a spec is hashed by the helper")
  o.add_argument("--reviewers", required=True, help="comma-separated reviewer ids, the kind's first reviewer first")
  o.add_argument("--astra", choices=("on", "off"), help="the Astra lane (default: config.astra.enabled)")
  r = core.add_parser(action, "record", "record one reviewer's round")
  r.add_argument("--review", required=True)
  r.add_argument("--round", type=int, required=True)
  r.add_argument("--sha256")
  r.add_argument("--reviewer", required=True)
  what = r.add_mutually_exclusive_group(required=True)
  what.add_argument("--findings", help="the findings file (empty when the reviewer found nothing)")
  what.add_argument("--not-run", dest="not_run", help="the reason the dispatch did not complete")
  r.add_argument("--isolation", help="clean | exposed:<what>")
  r.add_argument("--model", help="<requested>:<effective>")
  r.add_argument("--effort", help="<requested>:<effective>")
  s = core.add_parser(action, "settle", "write a finding's disposition")
  s.add_argument("--review", required=True)
  s.add_argument("--finding", required=True)
  s.add_argument("--disposition", choices=DISPOSITIONS, required=True)
  by_whom(s, required=False)
  t = core.add_parser(action, "status", "the review's state; the exit code is the verdict")
  t.add_argument("--review", required=True)
  u = core.add_parser(action, "rule", "record a ruling at the cap")
  u.add_argument("--review", required=True)
  u.add_argument("--ruling", choices=RULINGS, required=True)
  by_whom(u, required=True)
  core.add_parser(action, "post", "post a head round's review to its pull request (not built yet: U10)")
  p.set_defaults(run=run, writes=WRITES)


def by_whom(parser, required):
  group = parser.add_mutually_exclusive_group(required=required)
  group.add_argument("--owner", action="store_true", help="the owner ruled")
  group.add_argument("--judges", metavar="ID", help="the judges panel that ruled")


def run(args):
  if args.action == "post":
    print("superegm: review post is not built yet", file=sys.stderr)
    return 1
  return {"open": open_review}[args.action](args)


# ---------------------------------------------------------------- the findings line


def parse_findings(text: str, reviewer: str, rnd: int) -> list[dict]:
  """One finding per non-blank line, `<reviewer>-<round>-<n> | high|medium|low | <location> |
  regression: yes|no | <claim>`; a `set` id carries the set's own round, every other id `rnd`."""
  id_re = re.compile(rf"^{re.escape(reviewer)}-(\d+)-\d+$")
  findings = []
  for lineno, line in enumerate(text.splitlines(), 1):
    if not line.strip():
      continue
    fields = [f.strip() for f in line.split(" | ")]
    if len(fields) != 5:
      raise ValueError(f"{lineno}: expected 5 fields")
    fid, severity, location, regression, claim = fields
    match = id_re.match(fid)
    if not match or (reviewer != "set" and int(match.group(1)) != rnd):
      raise ValueError(f"{lineno}: id must be {reviewer}-{'<k>' if reviewer == 'set' else rnd}-<n>")
    if severity not in SEVERITIES:
      raise ValueError(f"{lineno}: severity must be high|medium|low")
    if regression not in ("regression: yes", "regression: no"):
      raise ValueError(f"{lineno}: regression must be yes|no")
    findings.append({"id": fid, "severity": severity, "location": location, "regression": regression[12:],
                     "claim": claim, "disposition": None, "ruling": None})
  return findings


# ---------------------------------------------------------------- the store


def review_id(st: core.Store, kind: str, artifact: str, cycle: int = 1) -> str:
  """`spec-<slug>-c<n>`, `spec-<slug>-integrate-c<n>`, `<6 hex>-plan-<unit>-c<n>`, `<6 hex>-head-<unit>-c<n>`."""
  if kind in ("spec", "integrate"):
    base = f"spec-{core.spec_slug(artifact)}" + ("-integrate" if kind == "integrate" else "")
  else:
    base = f"{st.handoff_id[-6:]}-{kind}-{artifact}"
  return f"{base}-c{cycle}"


def load_review(st: core.Store, rid: str):
  path = st.path("reviews", rid, "review.json")
  return json.loads(core.read_text(path)) if path.is_file() else None


def save_review(st: core.Store, rid: str, review: dict) -> None:
  core.atomic_write(st.path("reviews", rid, "review.json"), review)


def bind(args, review: dict) -> dict:
  """A by-id subcommand acts on the review's artifact: the card rule reads it from `args`."""
  if review["kind"] in ("spec", "integrate"):
    args.design = review["artifact"]
  else:
    args.unit = review["artifact"]
  return core.require_runcard(args, SKILLS)


# ---------------------------------------------------------------- open


def open_review(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  kind, reviewers = args.kind, args.reviewers.split(",")
  if kind in ("spec", "integrate"):
    args.design = args.artifact
    artifact = str(Path(args.artifact).expanduser().resolve())
  else:
    args.unit = artifact = args.artifact
  core.require_runcard(args, SKILLS)
  unknown = [r for r in reviewers if r not in REVIEWERS]
  if unknown:
    raise core.HandoffError(f"review open: unknown reviewer {unknown[0]}")
  if not 1 <= len(reviewers) <= 6:
    raise core.HandoffError("review open: 1 to 6 reviewers")
  if kind in FIRST and reviewers[0] != FIRST[kind]:
    raise core.HandoffError(f"review open: first reviewer must be {FIRST[kind]}")
  if kind in ("plan", "head") and not st.handoff_id:
    raise core.HandoffError("review open: no handoff_id in state.json")
  rid = review_id(st, kind, artifact)
  astra = args.astra or ("on" if (st.config.get("astra") or {}).get("enabled") else "off")
  review = {"kind": kind, "artifact": artifact, "cycle": 1,
            "reviewers": reviewers + (["astra"] if astra == "on" and kind in LANE_KINDS else []),
            "runcard": args.runcard, "artifact_sha256": args.sha256, "astra_incomplete": 0,
            "converged": "no", "converged_round": None, "rulings": []}
  save_review(st, rid, review)
  core.card_add(st, args.runcard, "produced", rid)
  core.journal(st, f"review open {rid} panel {','.join(review['reviewers'])} under {args.runcard}")
  print(rid)
  return 0
