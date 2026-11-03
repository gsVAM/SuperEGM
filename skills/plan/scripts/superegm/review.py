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
  return {"open": open_review, "record": record_round, "settle": settle_finding}[args.action](args)


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


def keep_for_unit(findings: list[dict], unit: str) -> list[dict]:
  """The set reviewer's findings that name this unit, or no unit at all."""
  return [f for f in findings if unit in f["location"] or not re.search(r"U\d\d", f["location"])]


def derive_what_ran(review: dict, rnd: dict, entry: dict | None) -> str:
  """`completed` when every panel reviewer has a record for the round (an empty findings file counts;
  the Astra lane's `--not-run` counts, and the lane is excused after two incomplete runs) and, on a
  head, the unit's `rounds[]` entry is `posted`; else `not run (<reason>)`, the reason being the
  entry's own `not run` reason, its phase, or the first reviewer without a record."""
  if entry is not None:
    outcome = entry.get("outcome") or ""
    if outcome.startswith("not run"):
      return outcome
    if entry.get("phase") != "posted":
      return f"not run (phase {entry.get('phase')})"
  records = rnd.get("reviewers") or {}
  for reviewer in review["reviewers"]:
    record = records.get(reviewer)
    if reviewer == "astra":
      if record is None and review.get("astra_incomplete", 0) < 2:
        return "not run (astra: no record)"
      continue
    if record is None:
      return f"not run ({reviewer}: no record)"
    if record.get("not_run"):
      return f"not run ({reviewer}: {record['not_run']})"
  return "completed"


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


def load_round(st: core.Store, rid: str, n: int):
  path = st.path("reviews", rid, f"round-{n}.json")
  return json.loads(core.read_text(path)) if path.is_file() else None


def round_numbers(st: core.Store, rid: str) -> list[int]:
  return sorted(int(m.group(1)) for p in st.path("reviews", rid).glob("round-*.json")
                if (m := re.fullmatch(r"round-(\d+)\.json", p.name)))


def head_entry(st: core.Store, unit: str, n: int):
  """The unit's `rounds[]` entry of round `n`, or None."""
  return next((e for e in core.load_foreman(st, unit)["rounds"] if e.get("round") == n), None)


def latest_cycle(st: core.Store, kind: str, artifact: str) -> tuple[dict | None, bool]:
  """The latest cycle's `review.json` of this artifact and whether that cycle is closed: by an
  `accept` or `stop` ruling, or (a spec) by the artifact's bytes moving off the converged round's."""
  base = review_id(st, kind, artifact, 0)[:-3]
  cycles = [int(m.group(1)) for p in st.path("reviews").glob(f"{base}-c*")
            if (m := re.fullmatch(rf"{re.escape(base)}-c(\d+)", p.name)) and (p / "review.json").is_file()]
  if not cycles:
    return None, False
  review = load_review(st, f"{base}-c{max(cycles)}")
  closed = any(r["ruling"] in ("accept", "stop") for r in review["rulings"])
  if not closed and kind in ("spec", "integrate") and review["converged_round"]:
    rnd = load_round(st, f"{base}-c{max(cycles)}", review["converged_round"])
    closed = core.sha256_file(Path(artifact)) != rnd["artifact_sha256"]
  return review, closed


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
  latest, closed = latest_cycle(st, kind, artifact)
  if latest and not closed:  # a re-typed skill resumes the open cycle; the panel cannot change
    rid = review_id(st, kind, artifact, latest["cycle"])
    core.card_add(st, args.runcard, "produced", rid)
    core.journal(st, f"review open {rid} resumed under {args.runcard}")
    print(rid)
    return 0
  cycle = latest["cycle"] + 1 if latest else 1
  rid = review_id(st, kind, artifact, cycle)
  astra = args.astra or ("on" if (st.config.get("astra") or {}).get("enabled") else "off")
  review = {"kind": kind, "artifact": artifact, "cycle": cycle,
            "reviewers": reviewers + (["astra"] if astra == "on" and kind in LANE_KINDS else []),
            "runcard": args.runcard, "artifact_sha256": args.sha256, "astra_incomplete": 0,
            "converged": "no", "converged_round": None, "rulings": []}
  save_review(st, rid, review)
  core.card_add(st, args.runcard, "produced", rid)
  core.journal(st, f"review open {rid} panel {','.join(review['reviewers'])} under {args.runcard}")
  print(rid)
  return 0


# ---------------------------------------------------------------- record


def record_round(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  rid, n, reviewer = args.review, args.round, args.reviewer
  review = load_review(st, rid)
  if review is None:
    raise core.HandoffError(f"review {rid}: not opened")
  card = bind(args, review)
  kind, existing = review["kind"], load_round(st, rid, n)
  if reviewer == "foreman":  # the helper's own findings (section 11), outside the panel
    if kind != "head":
      raise core.HandoffError("review record: foreman is accepted on a head only")
  elif reviewer not in review["reviewers"]:
    raise core.HandoffError(f"review record: {reviewer} is not on the panel")
  if kind in ("spec", "integrate"):
    sha = core.sha256_file(Path(review["artifact"]))
  else:
    sha = args.sha256 or (existing["artifact_sha256"] if existing else review["artifact_sha256"] if n == 1 else None)
    if not sha:
      raise core.HandoffError(f"review record: --sha256 required for kind {kind}")
  if existing and existing["artifact_sha256"] != sha:
    raise core.HandoffError("review record: sha256 differs from the round's")
  entry = None
  if kind == "head":  # a head's rounds are the unit's `rounds[]` entries
    entry = head_entry(st, review["artifact"], n)
    if entry is None:
      raise core.HandoffError(f"review record: no rounds[] entry for round {n}")
  elif not existing and n != (nxt := max(round_numbers(st, rid), default=0) + 1):
    raise core.HandoffError(f"review record: round {nxt} is next")
  if args.not_run:
    record = {"findings": [], "not_run": args.not_run, "isolation": None, "model": None, "effort": None}
  else:
    path = Path(args.findings)
    try:
      findings = parse_findings(core.read_text(path), reviewer, n)
    except ValueError as error:
      raise core.HandoffError(f"review record: {path}:{error}")
    if reviewer == "set":
      findings = keep_for_unit(findings, review["artifact"])
    record = {"findings": findings, "not_run": None, "isolation": args.isolation, "model": args.model,
              "effort": args.effort}
  rnd = existing or {"round": n, "runcard": card.get("parent") or args.runcard, "artifact_sha256": sha,
                     "builder_contested": [], "reviewers": {}}
  rnd["reviewers"][reviewer] = record
  if reviewer == "astra" and args.not_run:
    review["astra_incomplete"] += 1
  rnd["what_ran"] = derive_what_ran(review, rnd, entry)
  core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
  save_review(st, rid, review)
  core.journal(st, f"review record {rid} round {n} {reviewer} what_ran {rnd['what_ran']} under {args.runcard}")
  print(f"round {n} {reviewer} recorded, what_ran {rnd['what_ran']}")
  return 0


# ---------------------------------------------------------------- settle


def blocking(finding: dict) -> bool:
  return finding["severity"] in ("high", "medium")


def locate_finding(st: core.Store, rid: str, fid: str):
  """`(round number, round, reviewer, finding)` of `fid` in any recorded round, completed or not."""
  for n in round_numbers(st, rid):
    rnd = load_round(st, rid, n)
    for reviewer, record in rnd["reviewers"].items():
      for finding in record["findings"]:
        if finding["id"] == fid:
          return n, rnd, reviewer, finding
  raise core.HandoffError(f"review settle: no finding {fid}")


def settle_finding(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  rid, fid, disposition = args.review, args.finding, args.disposition
  review = load_review(st, rid)
  if review is None:
    raise core.HandoffError(f"review {rid}: not opened")
  card = bind(args, review)
  n, rnd, reviewer, finding = locate_finding(st, rid, fid)
  if review["kind"] == "head" and disposition == "fix-design":
    raise core.HandoffError("review settle: fix-design is refused on a head")
  if reviewer == "foreman" and finding["location"] == "ci":  # D2 (a): `collect` records it afresh each round
    raise core.HandoffError("review settle: the CI finding is settled by no one")
  if blocking(finding) and disposition in ("contested", "declined"):
    if card["mode"] == "leavemealone" and not args.judges:
      raise core.HandoffError(f"review settle: {fid} is {finding['severity']}: --judges required in leavemealone-mode")
    if card["mode"] != "leavemealone" and not args.owner:
      raise core.HandoffError(f"review settle: {fid} is {finding['severity']}: --owner required in normal mode")
  finding["disposition"] = disposition
  finding["ruling"] = "owner" if args.owner else f"judges:{args.judges}" if args.judges else None
  core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
  core.journal(st, f"review settle {rid} {fid} {disposition} by {finding['ruling'] or 'the elephant'} under {args.runcard}")
  print(f"{fid} {disposition}")
  return 0
