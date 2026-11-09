# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the review loop (spec section 8); the Astra lane on a head and its not-installed record (U17); the amendment scope of a spec review and the batch settle (U19); `review ingest` and the external reviewer (U21); `review ingest --pr`, the carry and the fixed replies on the spec PR (U26); the gates before the word, `owner: <ids>` and the owner-only settle of a `test-delta` finding (U25).

"""superegm review open|record|settle|status|rule|scope|post|ingest: the one review loop (spec section 8)."""

import argparse
import contextlib
from dataclasses import dataclass
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import superegm as core

WRITES = frozenset({"reviews", "foreman", "runcards", "review"})  # the store kinds this subcommand writes
SKILLS = frozenset({"review-spec", "review-plan", "wave", "integrate"})  # the skills whose card this subcommand accepts
KINDS = ("spec", "plan", "head", "integrate")
REVIEWERS = ("design", "zoom-out", "comprehension", "readiness", "structural", "style",
             "codebase-details", "change-review", "set", "proportion")
FIRST = {"spec": "design", "plan": "readiness", "head": "change-review"}  # the kind's fixed first reviewer (section 5)
PANEL_OF = {"spec": "design,zoom-out", "integrate": "design", "plan": "readiness,proportion,set", "head": "change-review"}
LANE_KINDS = ("spec", "plan", "integrate", "head")  # the kinds the Astra lane joins
ROLES = ("none", "read", "triage", "write", "maintain", "admin")  # a repository role, lowest first; `none` the endpoint's non-collaborator


def seat_lane(kind: str, flag: str | None, astra: dict) -> bool:
  """Whether the Astra lane joins a review: `--astra on|off` decides; without it `astra.enabled`, and on a
  head `astra.heads` too (`spec` and `integrate` as `plan`)."""
  if kind not in LANE_KINDS:
    return False
  if flag is not None:
    return flag == "on"
  return bool(astra.get("enabled")) and (kind != "head" or bool(astra.get("heads", True)))


SEVERITIES = ("high", "medium", "low")
DISPOSITIONS = ("fixed", "contested", "declined", "escalated", "fix-design")
RULINGS = ("continue", "accept", "stop")
CAP = 5  # completed rounds per cycle, plus one per `continue` ruling (section 5)


def register(subparsers):
  p = subparsers.add_parser("review", help="the review loop")
  action = p.add_subparsers(dest="action", required=True)
  o = core.add_parser(action, "open", "open a review, or resume its open cycle")
  o.add_argument("--kind", choices=KINDS, required=True)
  o.add_argument("--artifact", required=True, help="the spec path, or the unit id")
  o.add_argument("--sha256", help="the bytes under review (a plan body or a head); a spec is hashed by the helper")
  o.add_argument("--reviewers", required=True, help="comma-separated reviewer ids, the kind's first reviewer first")
  o.add_argument("--astra", choices=("on", "off"), help="the Astra lane (default: config.astra.enabled)")
  o.add_argument("--scope", help="kind spec: auto (default) | whole | headings separated by `;`")
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
  s.add_argument("--finding")
  s.add_argument("--disposition", choices=DISPOSITIONS)
  s.add_argument("--file", help="one `<fid> | <disposition> | <note>` per line, settled all or nothing (in place of --finding)")
  by_whom(s, required=False)
  t = core.add_parser(action, "status", "the review's state; the exit code is the verdict")
  t.add_argument("--review", required=True)
  c = core.add_parser(action, "scope", "a spec review's scope this round: one line per section, for the brief")
  c.add_argument("--review", required=True)
  u = core.add_parser(action, "rule", "record a ruling at the cap")
  u.add_argument("--review", required=True)
  u.add_argument("--ruling", choices=RULINGS, required=True)
  by_whom(u, required=False)  # `stop` alone needs no ruler once `continue` is spent and the bytes moved
  v = core.add_parser(action, "post", "post a head round's review to its pull request, bound to the reviewed commit")
  v.add_argument("--unit", required=True)
  v.add_argument("--round", type=int, required=True)
  v.add_argument("--dispatch", required=True, help="the dispatch id `foreman dispatch` printed")
  i = core.add_parser(action, "ingest", "record a unit's PR review threads as external findings into its latest posted round (--unit), or the spec PR's into the latest round of the spec's latest cycle (--pr)")
  which = i.add_mutually_exclusive_group(required=True)
  which.add_argument("--unit")
  which.add_argument("--pr", type=int, help="the spec PR: its threads into the latest round of the spec's latest cycle")
  p.set_defaults(run=run, writes=WRITES)


def by_whom(parser, required):
  group = parser.add_mutually_exclusive_group(required=required)
  group.add_argument("--owner", action="store_true", help="the owner ruled")
  group.add_argument("--judges", metavar="ID", help="the judges panel that ruled")
  parser.add_argument("--posted", metavar="COMMENT", help="in leavemealone with --owner: the owner's by-hand `**Ruling:** <fid> finding overruled` comment id")


def run(args):
  try:
    return {"open": open_review, "record": record_round, "settle": settle_finding,
            "status": status_review, "rule": rule_review, "post": post, "scope": scope_review,
            "ingest": ingest}[args.action](args)
  except Refusal as refusal:
    print(refusal)
    return 1


class Refusal(core.HandoffError):
  """A refusal the subcommand prints as is: one line on stdout, exit 1."""


def require_dispatch(unit: str, data: dict, dispatch_id: str) -> dict:
  """The round entry of the unit's current dispatch; a stale or unknown id is refused."""
  if dispatch_id != data.get("dispatch_id"):
    raise Refusal(f"dispatch: {dispatch_id} is not {unit}'s current dispatch ({data.get('dispatch_id')})")
  entry = next((e for e in reversed(data["rounds"]) if e.get("dispatch_id") == dispatch_id), None)
  if entry is None:
    raise Refusal(f"dispatch: {unit} has no round for {dispatch_id}")
  return entry


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


# ---------------------------------------------------------------- the scope of a spec round (U19)


HEADING_RE = re.compile(r"^ {0,3}(#{2,3})[ \t]+\S")  # an H2 or an H3 opens a section


def sections(text: str) -> list[tuple[str, int, int]]:
  """`(heading, start, end)` per section, 1-based and inclusive: the preamble above the first H2 (when it
  holds a line) as `(preamble)`, then every H2 and H3; a heading-like line inside a fenced block (section
  9.1's CommonMark-smallest grammar, `scan_text`'s) opens none."""
  lines, starts, fence = text.splitlines(), [], None
  for number, line in enumerate(lines, 1):
    if fence:
      if re.match(rf"^ {{0,3}}{fence[0]}{{{fence[1]},}}\s*$", line):
        fence = None
    elif (opener := core.FENCE_RE.match(line)) and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
      fence = (opener.group(1)[0], len(opener.group(1)))
    elif HEADING_RE.match(line):
      starts.append((line.strip(), number))
  if not starts or starts[0][1] > 1:
    starts.insert(0, ("(preamble)", 1))
  return [(heading, start, (starts[i + 1][1] - 1) if i + 1 < len(starts) else len(lines))
          for i, (heading, start) in enumerate(starts) if start <= len(lines)]


def section_of(spans: list[tuple[str, int, int]], line: int):
  """The index of the section holding line `line`, or None past the end."""
  return next((i for i, (_, start, end) in enumerate(spans) if start <= line <= end), None)


def scope_sections(old: str, new: str) -> list[tuple[str, str, int, int]]:
  """`(changed|neighbour, heading, start, end)` in the new text's document order: a section holding a line
  the diff from `old` to `new` inserted or replaced, or the line before a deletion, is changed; the one
  section before and after each changed one is its neighbour (for an H3, its sibling H3, else its parent
  H2 before it and the next H2 after it: the adjacent sections either way)."""
  spans, changed = sections(new), set()
  matcher = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False)
  for tag, _, _, j1, j2 in matcher.get_opcodes():
    if tag == "equal":
      continue
    for line in (range(j1 + 1, j2 + 1) if j2 > j1 else [max(j1, 1)]):
      index = section_of(spans, line)
      if index is not None:
        changed.add(index)
  neighbours = {i + d for i in changed for d in (-1, 1)} - changed
  return [("changed" if i in changed else "neighbour", heading, start, end)
          for i, (heading, start, end) in enumerate(spans) if i in changed or i in neighbours]


def cited_line(location: str) -> int | None:
  """The line a finding's location cites: the first integer after `line `, `lines `, `L` or `:`, else None."""
  match = re.search(r"(?:\blines? |\bL|:)(\d+)", location)
  return int(match.group(1)) if match else None


def out_of_scope(rows: list, spans: list, location: str):
  """The heading of the section a finding cites when no scope row holds its line, else None: a location
  naming no line, or a line past the spec's end (another file's), is kept (D1 (a): the goldfish was briefed
  to cite lines, and an unplaceable finding is not lost)."""
  line = cited_line(location)
  index = None if line is None else section_of(spans, line)
  if index is None or any(start <= line <= end for _, _, start, end in rows):
    return None
  return spans[index][0]


def approved_text(spec: Path, approval: dict):
  """The approved bytes as text: the spec at the approval's `commit` (voided or not), else at the first commit
  of the current branch's `git log -- <spec>` whose blob hashes to its `sha256`; None when no commit holds them."""
  root = core.git_toplevel(spec.parent)
  rel = spec.resolve().relative_to(root.resolve()).as_posix()
  show = lambda commit: subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=str(root), capture_output=True)
  if approval.get("commit") and (at := show(approval["commit"])).returncode == 0:
    return at.stdout.decode("utf-8")
  for commit in core.run_git(["log", "--format=%H", "--", rel], root, check=False).split():
    blob = show(commit)
    if blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == approval["sha256"]:
      return blob.stdout.decode("utf-8")
  return None


def scope_of(st: core.Store, review: dict, spec: Path) -> list:
  """The round's scope rows, `(changed|neighbour|whole, heading, start, end)`, from the current bytes: under
  `auto` (a review opened before U19 reads as `auto`) the sections `scope_sections` finds against the
  approved bytes; a section list adds its headings as `changed`, without neighbours (a heading the bytes no
  longer hold is dropped). One `whole` row otherwise, its heading field the reason: `(whole)`, `(no
  approval)`, `(no commit holds <sha7>)`, or `(no change)` when nothing changed and no listed heading stands."""
  text = core.read_text(spec)
  whole = lambda reason: [("whole", f"({reason})", 1, len(text.splitlines()))]
  form = review.get("scope") or "auto"
  if form == "whole":
    return whole("whole")
  approval = core.load_approval(st, spec)
  if not approval:
    return whole("no approval")
  old = approved_text(spec, approval)
  if old is None:
    return whole(f"no commit holds {approval['sha256'][:7]}")
  rows = {row[2]: row for row in scope_sections(old, text)}  # by start line: two sections may share a heading
  if isinstance(form, list):
    for heading, start, end in sections(text):
      if heading in form:
        rows[start] = ("changed", heading, start, end)
  return [rows[start] for start in sorted(rows)] or whole("no change")


# ---------------------------------------------------------------- the store


def review_id(st: core.Store, kind: str, artifact: str, cycle: int = 1) -> str:
  """`spec-<slug>-c<n>`, `spec-<slug>-integrate-c<n>`, `plan-<unit>-c<n>`, `head-<unit>-c<n>` (in the handoff's
  directory, spec section 7; a legacy flat store keeps the `<6 hex>-` prefix that kept its handoffs apart)."""
  if kind in ("spec", "integrate"):
    base = f"spec-{core.spec_slug(artifact)}" + ("-integrate" if kind == "integrate" else "")
  else:
    base = f"{hex_prefix(st)}{kind}-{artifact}"
  return f"{base}-c{cycle}"


def hex_prefix(st: core.Store) -> str:
  """`<6 hex>-` before a plan or head review id in a legacy flat store; nothing in a handoff's directory."""
  return f"{st.handoff_id[-6:]}-" if st.legacy else ""


def frozen(st: core.Store) -> str | None:
  """Why the store's handoff is frozen (an older handoff, spec section 7), or None."""
  try:
    core.require_latest_handoff(st)
  except core.HandoffError as error:
    return str(error)
  return None


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


def head_review_id(st: core.Store, unit: str):
  """The unit's latest `head-<unit>-c<n>` review id, or None before the first dispatch."""
  latest, _ = latest_cycle(st, "head", unit)
  return review_id(st, "head", unit, latest["cycle"]) if latest else None


def head_entry(st: core.Store, unit: str, n: int):
  """The unit's `rounds[]` entry of round `n`, or None."""
  return next((e for e in core.load_foreman(st, unit)["rounds"] if e.get("round") == n), None)


def cycle_ids(st: core.Store, kind: str, artifact: str) -> list[str]:
  """The review ids of every cycle of this artifact holding a `review.json`, oldest first."""
  base = review_id(st, kind, artifact, 0)[:-3]
  folder = st.path("reviews", f"{base}-c0").parent  # where this kind's reviews sit: a spec's at the store's root
  found = sorted(int(m.group(1)) for p in folder.glob(f"{base}-c*")
                 if (m := re.fullmatch(rf"{re.escape(base)}-c(\d+)", p.name)) and (p / "review.json").is_file())
  return [f"{base}-c{c}" for c in found]


def latest_cycle(st: core.Store, kind: str, artifact: str) -> tuple[dict | None, bool]:
  """The latest cycle's `review.json` of this artifact and whether that cycle is closed: by an
  `accept` or `stop` ruling; a spec's by the approval that names it, once the bytes moved off its
  sha; an integrate's by the handoff closing or changing (D1 (a)), or by a `## Units` amendment
  past the bytes its latest completed round reviewed (a cycle with no completed round stays)."""
  cycles = cycle_ids(st, kind, artifact)
  if not cycles:
    return None, False
  rid = cycles[-1]
  review = load_review(st, rid)
  closed = any(r["ruling"] in ("accept", "stop") for r in review["rulings"])
  if not closed and kind == "spec":
    approval = core.load_approval(st, Path(artifact))
    closed = bool(approval) and approval["review"] == rid and approval["sha256"] != current_sha(st, kind, artifact)
  if not closed and kind == "integrate":
    state = core.load_state(st.root)
    amended = [e for e in core.load_approvals(st, Path(artifact))
               if e.get("kind") == "amend-units" and e.get("handoff_id") == review.get("handoff_id")]
    latest_sha = evaluate(st, review, None).latest_sha
    closed = bool(state.get("closed_at")) or ("handoff_id" in review and state.get("handoff_id") != review["handoff_id"]) \
        or bool(amended and latest_sha and amended[-1]["sha256"] != latest_sha)
  return review, closed


def current_sha(st: core.Store, kind: str, artifact: str):
  """The artifact's bytes now: a spec or integrate hashes the file, a plan its stored body (what
  `handoff_units.json`'s `body_sha256` holds); a head has none."""
  if kind in ("spec", "integrate"):
    return core.sha256_file(Path(artifact))
  if kind == "plan":
    path = st.path("unit", artifact)
    if not path.is_file():
      raise core.HandoffError(f"review: no unit_{artifact}.md: run graph first")
    return core.sha256_text(core.unit_file_body(path) + "\n")
  return None


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
  kind, reviewers = args.kind, [r for r in args.reviewers.split(",") if r != "astra"]  # an `astra` entry is informational
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
  if kind == "plan" and frozen(st):  # an older handoff is frozen for review-plan (spec section 7)
    raise core.HandoffError(f"review open: {frozen(st)}")
  if kind == "plan" and args.sha256:
    raise core.HandoffError("review open: --sha256 is refused for kind plan")
  given = getattr(args, "scope", None)  # a caller's own Namespace (the foreman's) may omit it
  if given is not None and kind != "spec":
    raise core.HandoffError(f"review open: --scope is refused for kind {kind}")
  latest, closed = latest_cycle(st, kind, artifact)
  if latest and not closed:  # a re-typed skill resumes the open cycle; the panel cannot change
    rid = review_id(st, kind, artifact, latest["cycle"])
    core.card_add(st, args.runcard, "produced", rid)
    core.journal(st, f"review open {rid} resumed under {args.runcard}")
    print(rid)
    return 0
  scope = scope_form(st, artifact, given) if kind == "spec" else None
  cycle = latest["cycle"] + 1 if latest else 1
  rid = review_id(st, kind, artifact, cycle)
  lane = seat_lane(kind, getattr(args, "astra", None), st.config.get("astra") or {})
  review = {"kind": kind, "artifact": artifact, "cycle": cycle, "handoff_id": st.handoff_id, "scope": scope,
            "reviewers": reviewers + (["astra"] if lane else []),
            "runcard": args.runcard, "artifact_sha256": current_sha(st, kind, artifact) if kind == "plan" else args.sha256,
            "astra_incomplete": 0,
            "converged": "no", "converged_round": None, "rulings": []}
  save_review(st, rid, review)
  core.card_add(st, args.runcard, "produced", rid)
  core.journal(st, f"review open {rid} panel {','.join(review['reviewers'])} under {args.runcard}")
  print(rid)
  return 0


def scope_form(st: core.Store, artifact: str, given) -> str | list:
  """The stored form of a spec review's `--scope`: `auto` (the default), `whole`, or the headings the list
  names, separated by `;` (a heading may hold a comma), each a heading of the spec now; the list needs a
  previous approval to diff against."""
  if given is None or given.strip() in ("auto", "whole"):
    return (given or "auto").strip()
  headings = [h.strip() for h in given.split(";") if h.strip()]
  if not core.load_approval(st, Path(artifact)):
    raise core.HandoffError("review open: --scope <list>: no approval: use whole")
  present = {heading for heading, _, _ in sections(core.read_text(Path(artifact)))}
  missing = [h for h in headings if h not in present]
  if missing or not headings:
    raise core.HandoffError(f"review open: --scope: {missing[0] if missing else given} is not in the spec")
  return headings


# ---------------------------------------------------------------- scope


def scope_review(args) -> int:
  """Prints the round's scope, `<changed|neighbour|whole> <start>-<end> <heading>` per section; writes nothing."""
  st = core.store(core.git_toplevel(Path.cwd()))
  review = load_review(st, args.review)
  if review is None:
    raise core.HandoffError(f"review {args.review}: not opened")
  if review["kind"] != "spec":
    raise core.HandoffError(f"review scope: {args.review} is not a spec review")
  bind(args, review)
  for kind, heading, start, end in scope_of(st, review, Path(review["artifact"])):
    print(f"{kind} {start}-{end} {heading}")
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
  external = reviewer.startswith("external:")
  if reviewer == "foreman":  # the helper's own findings (section 11), outside the panel
    if kind != "head":
      raise core.HandoffError("review record: foreman is accepted on a head only")
  elif external:  # a PR thread's author (`review ingest`), outside the panel
    if kind not in ("head", "spec"):
      raise core.HandoffError(f"review record: {reviewer} is accepted on a head or a spec only")
  elif reviewer not in review["reviewers"]:
    raise core.HandoffError(f"review record: {reviewer} is not on the panel")
  if kind == "plan" and args.sha256:
    raise core.HandoffError("review record: --sha256 is refused for kind plan")
  sha = current_sha(st, kind, review["artifact"])
  if kind == "head":
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
  if not existing and evaluate(st, review, card.get("parent") or args.runcard).code == 2:
    print("review record: review at its cap: rule first", file=sys.stderr)
    return 2
  rnd = existing or {"round": n, "runcard": card.get("parent") or args.runcard, "artifact_sha256": sha,
                     "builder_contested": [], "reviewers": {}}
  if kind == "spec" and "scope" not in rnd:  # the round's scope, stored by its first record, checked by every later one
    rows = [list(row) for row in scope_of(st, review, Path(review["artifact"]))]
    rnd.update({"scope": rows, "out_of_scope": [],
                "note": rows[0][1][1:-1] if rows and rows[0][0] == "whole" else None})
  refused = []
  if args.not_run and external:  # an ingest's record holds findings: a not-run would erase them
    raise core.HandoffError(f"review record: --not-run is refused for an external reviewer ({reviewer})")
  if args.not_run:
    record = {"findings": [], "not_run": args.not_run, "isolation": None, "model": None, "effort": None}
  else:
    path = Path(args.findings)
    text = core.read_text(path)
    try:
      findings = parse_findings(text, reviewer, n)
    except ValueError as error:
      raise core.HandoffError(f"review record: {path}:{error}")
    pairs = list(zip(findings, [line for line in text.splitlines() if line.strip()]))  # one finding per non-blank line
    if reviewer == "set":  # the raw lines filtered alongside, so a kept line stays its own finding's
      kept = [id(finding) for finding in keep_for_unit(findings, review["artifact"])]
      pairs = [(finding, line) for finding, line in pairs if id(finding) in kept]
    findings = [finding for finding, _ in pairs]
    if kind == "spec" and not external:  # a thread's location is a file of the PR, never a spec section
      spans = sections(core.read_text(Path(review["artifact"])))
      verdicts = [(finding, line, out_of_scope(rnd["scope"], spans, finding["location"])) for finding, line in pairs]
      findings = [finding for finding, _, section in verdicts if section is None]
      refused = [(finding["id"], line, section) for finding, line, section in verdicts if section is not None]
      mine = lambda line: line.split(" | ", 1)[0].rsplit("-", 2)[0] == reviewer
      rnd["out_of_scope"] = [line for line in rnd["out_of_scope"] if not mine(line)] + [line for _, line, _ in refused]
    if external:  # an ingest appends: a recorded finding keeps its severity and disposition
      kept = (rnd["reviewers"].get(reviewer) or {}).get("findings") or []
      threads = getattr(args, "threads", None) or {}  # `ingest`'s finding id → root comment id, in this one write
      findings = kept + [{**f, **({"thread": threads[f["id"]]} if f["id"] in threads else {})}
                         for f in findings if f["id"] not in {k["id"] for k in kept}]
    record = {"findings": findings, "not_run": None, "isolation": args.isolation, "model": args.model,
              "effort": args.effort}
  rnd["reviewers"][reviewer] = record
  if reviewer == "astra" and args.not_run and not args.not_run.startswith(("not installed", "stopped")):
    review["astra_incomplete"] += 1
  rnd["what_ran"] = derive_what_ran(review, rnd, entry)
  core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
  store_verdict(st, rid, review, rnd["runcard"])
  for fid, _, section in refused:
    core.journal(st, f"review record {rid} round {n} out of scope: {fid} ({section}) under {args.runcard}")
    print(f"record: {fid} out of scope ({section}): not recorded")
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
  """`--finding` with `--disposition`, or `--file`: every line checked under the per-finding refusals first,
  and a refused line (named) writes nothing."""
  st = core.store(core.git_toplevel(Path.cwd()))
  rid = args.review
  if bool(getattr(args, "file", None)) == bool(args.finding or args.disposition) or (args.finding is None) != (args.disposition is None):
    raise core.HandoffError("review settle: --file, or --finding with --disposition")
  review = load_review(st, rid)
  if review is None:
    raise core.HandoffError(f"review {rid}: not opened")
  card = bind(args, review)
  if not getattr(args, "file", None):
    checked = [(args.finding, args.disposition, None, check_settle(st, rid, review, card, args, args.finding, args.disposition))]
  else:
    checked = []
    for line in core.read_text(Path(args.file)).splitlines():
      if not line.strip():
        continue
      fields = [f.strip() for f in line.split(" | ")]
      if len(fields) != 3 or fields[1] not in DISPOSITIONS or not fields[0]:
        raise core.HandoffError(f"review settle: {line}: not <fid> | <disposition> | <note>: nothing written")
      try:
        checked.append((fields[0], fields[1], fields[2], check_settle(st, rid, review, card, args, fields[0], fields[1])))
      except core.HandoffError as error:
        raise core.HandoffError(f"review settle: {line}: {str(error).removeprefix('review settle: ')}: nothing written")
  runcard = card.get("parent") or args.runcard
  for fid, disposition, note, n in checked:
    rnd = load_round(st, rid, n)
    reviewer, finding = next((r, f) for r, record in rnd["reviewers"].items() for f in record["findings"] if f["id"] == fid)
    finding["disposition"] = disposition
    finding["ruling"] = "owner" if args.owner else f"judges:{args.judges}" if args.judges else None
    if note is not None:
      finding["note"] = note
    core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
    copies = settle_set_copies(st, rnd, finding) if (review["kind"], reviewer, disposition) == ("plan", "set", "fixed") \
        else settle_external_copies(st, review, reviewer, finding) if review["kind"] == "spec" and reviewer.startswith("external:") else []
    core.journal(st, f"review settle {rid} {fid} {disposition} by {finding['ruling'] or 'the elephant'}"
                 + (f" copied to {', '.join(copies)}" if copies else "") + f" under {args.runcard}")
  status = store_verdict(st, rid, review, runcard)
  word = None
  if review["kind"] == "head" and status.code == 0:
    write_head_outcome(st, review, runcard)
  elif review["kind"] == "head":
    word = write_owner_outcome(st, rid, review, runcard, status.code)
  for fid, disposition, _, _ in checked:
    print(f"{fid} {disposition}")
  if word:
    print(word)
  return 0


def check_settle(st: core.Store, rid: str, review: dict, card: dict, args, fid: str, disposition: str) -> int:
  """The per-finding refusals of `review settle`; the round number of `fid` when none applies."""
  n, rnd, reviewer, finding = locate_finding(st, rid, fid)
  if review["kind"] == "head" and disposition == "fix-design":
    raise core.HandoffError("review settle: fix-design is refused on a head")
  if review["kind"] == "integrate" and disposition == "fix-design" and frozen(st):  # its spec is the latest handoff's now
    raise core.HandoffError("review settle: fix-design is refused on a frozen handoff's integrate: settle it escalated")
  if reviewer == "foreman" and finding["location"] == "ci":  # D2 (a): `collect` records it afresh each round
    raise core.HandoffError("review settle: the CI finding is settled by no one")
  if disposition == "fixed" and rnd["artifact_sha256"] == current_sha(st, review["kind"], review["artifact"]):
    raise core.HandoffError("review settle: fixed needs changed bytes")  # a head's current bytes are unknown: never
  if finding["claim"].startswith("test-delta:") and not args.owner:  # U25: the owner's alone, in either mode
    raise core.HandoffError(f"review settle: {fid} is the owner's alone: --owner required")
  if blocking(finding) and disposition in ("contested", "declined"):
    if card["mode"] == "leavemealone" and not args.judges:
      if not (args.owner and getattr(args, "posted", None)):
        raise core.HandoffError(f"review settle: {fid} is {finding['severity']}: --judges required in leavemealone-mode")
      verify_owner_ruling(st.config, finding, args.posted, delta_claim(st, rid, finding["claim"]))
    if card["mode"] != "leavemealone" and not args.owner:
      raise core.HandoffError(f"review settle: {fid} is {finding['severity']}: --owner required in normal mode")
  return n


def delta_claim(st: core.Store, rid: str, claim: str) -> str:
  """The claim a contest's copy (`contested <fid>: …`, `unreplied <fid>: …`) stands for, followed down the chain to
  the original finding of this review (bounded; an id no round holds ends the walk): what the owner's whole-file
  `test-delta <file> allowed` reads on a contested `test-delta:` finding (U25)."""
  for _ in range(32):
    m = re.match(r"(?:contested|unreplied) (\S+):", claim)
    if not m:
      break
    try:
      claim = locate_finding(st, rid, m.group(1))[3]["claim"]
    except core.HandoffError:
      break
  return claim


def verify_owner_ruling(config: dict, finding: dict, comment_id: str, original: str = None) -> None:
  """In leavemealone the owner's word still counts, by hand (1.1.3; U22 reads such comments itself): one GitHub
  read of the comment, by a `config.owners` login, carrying a ruling `ruling_of` reads: `<fid> finding overruled`,
  or `<fid> allowed` on a `test-delta:` finding, or `test-delta <file> allowed` on a `test-delta:` finding of that
  file or on a contest's copy whose `original` claim (`delta_claim`'s) is one (U25)."""
  from superegm.decision import ruling_of  # inside: `decision` imports `review`
  fid, claim = finding["id"], finding["claim"]
  original = claim if original is None else original
  comment = core.gh_json(["api", f"repos/{config['repo']}/issues/comments/{comment_id}"]) or {}
  author = (comment.get("user") or {}).get("login")
  if author not in (config.get("owners") or []):
    raise core.HandoffError(f"review settle: comment {comment_id} is by {author}, not a login in config.owners")
  found = ruling_of({**comment, "id": comment.get("id") or comment_id}, config.get("owners") or [])
  delta = claim.startswith("test-delta:")
  if not (found and ((found.subject == fid and (found.kind == "overruled" or (found.kind == "allowed" and delta)))
                     or (found.kind == "allowed-file" and original.startswith(f"test-delta: {found.subject}:")))):
    raise core.HandoffError(f"review settle: comment {comment_id} does not rule {fid} overruled")


def settle_set_copies(st: core.Store, rnd: dict, finding: dict) -> list:
  """A `set` finding settled `fixed` on one unit settles its copies: every other plan review's round
  under the same run card whose `set` record holds the same id and claim takes the disposition and
  ruling (one already holding them, the settled round included, is left alone); the review ids written."""
  copies = []
  for folder in st.path("reviews").glob(f"{hex_prefix(st)}plan-*-c*"):
    for n in round_numbers(st, folder.name):
      other = load_round(st, folder.name, n)
      twins = [f for f in ((other["reviewers"].get("set") or {}).get("findings") or [])
               if (f["id"], f["claim"]) == (finding["id"], finding["claim"])
               and (f["disposition"], f["ruling"]) != (finding["disposition"], finding["ruling"])]
      if other["runcard"] == rnd["runcard"] and twins:
        for twin in twins:
          twin["disposition"], twin["ruling"] = finding["disposition"], finding["ruling"]
        core.atomic_write(folder / f"round-{n}.json", other)
        copies.append(folder.name)
  return copies


def settle_external_copies(st: core.Store, review: dict, reviewer: str, finding: dict) -> list[str]:
  """An external finding settled on a spec settles its copies: every round of every cycle of the spec holding the
  same `(id, claim)` under `reviewer` takes the disposition, ruling and note (one already holding them, the settled
  round included, is left alone); the review ids written."""
  copies = []
  for other_rid, _ in spec_cycles(st, review["artifact"]):
    for m in round_numbers(st, other_rid):
      other = load_round(st, other_rid, m)
      twins = [f for f in ((other["reviewers"].get(reviewer) or {}).get("findings") or [])
               if (f["id"], f["claim"]) == (finding["id"], finding["claim"])
               and (f["disposition"], f["ruling"], f.get("note")) != (finding["disposition"], finding["ruling"], finding.get("note"))]
      if twins:
        for twin in twins:
          twin["disposition"], twin["ruling"] = finding["disposition"], finding["ruling"]
          if "note" in finding:
            twin["note"] = finding["note"]
        core.atomic_write(st.path("reviews", other_rid, f"round-{m}.json"), other)
        if other_rid not in copies:
          copies.append(other_rid)
  return copies


def write_head_outcome(st: core.Store, review: dict, runcard: str) -> None:
  """`outcome: clean` on the unit's latest posted round and `<unit> awaiting merge` in the journal:
  whichever of `review post` (U10) and `review settle` leaves `review status` at 0 writes it."""
  unit = review["artifact"]
  data = core.load_foreman(st, unit)
  posted = sorted((e for e in data["rounds"] if e.get("phase") == "posted"), key=lambda e: e["round"])
  if not posted:
    return
  posted[-1]["outcome"] = "clean"
  core.save_foreman(st, unit, data)
  core.journal(st, f"{unit} awaiting merge under {runcard}")


def write_owner_outcome(st: core.Store, rid: str, review: dict, runcard: str, code: int = 3) -> str | None:
  """Round 4 (PR #103 review, astra-4-3): a settle that leaves the latest posted round's remainder owner-only
  (`owner_only_fids`, no open contest) rewrites its outcome to `owner: <ids>`, so a contest settled after the post
  routes to the owner row, not to `revise` or the cap; the word, when written. Round 5 (codebase-details-5-1): a
  settle on the owner row itself (the round's word already `owner: <ids>`) leaves that word, its decision still
  open on the ids left, unless every id left is one the owner upheld (a recorded `<fid> finding upheld`): then the
  word is `revise`, or `cap-reached` at the cap (`code`, the status `review status` gives), as an uphold is."""
  unit = review["artifact"]
  data = core.load_foreman(st, unit)
  posted = sorted((e for e in data["rounds"] if e.get("phase") == "posted"), key=lambda e: e["round"])
  rnd = load_round(st, rid, posted[-1]["round"]) if posted else None
  if not rnd or contested_fids(rnd) or not (owner := owner_only_fids(rnd)):
    return None
  upheld = {str(r.get("ruling") or "").split(" ")[0] for r in data.get("rulings") or []  # `--ruling` is stored raw, reason and all
            if str(r.get("ruling") or "").partition(" — ")[0].strip().endswith(" finding upheld")}
  if set(owner) <= upheld:
    word = {3: "revise", 2: "cap-reached"}.get(code)
  elif str(posted[-1].get("outcome") or "").startswith("owner:"):
    return None
  else:
    word = outcome_word(3, [], owner)
  if not word:
    return None
  if posted[-1].get("outcome") != word:
    posted[-1]["outcome"] = word
    core.save_foreman(st, unit, data)
    core.journal(st, f"{unit} round {posted[-1]['round']} outcome {word} under {runcard}")
  return word


# ---------------------------------------------------------------- status: the predicates live here alone


@dataclass
class Status:
  code: int
  line: str
  trend: str
  converged: str
  converged_round: int | None
  sha: str | None
  moved: bool = False          # the latest completed round's bytes are no longer the artifact's (never on a head)
  latest_sha: str | None = None
  fixed: bool = False          # that round would have converged but for the move: re-review on the current bytes


def findings_of(rnd: dict) -> list[dict]:
  return [f for record in rnd["reviewers"].values() for f in record["findings"]]


def regressions_of(rnd: dict) -> int:
  return sum(blocking(f) and f["regression"] == "yes" for f in findings_of(rnd))


def rounds_of(st: core.Store, rid: str, review: dict) -> list[dict]:
  """The review's rounds in order: the round files, or on a head the unit's `rounds[]` entries, each
  with its `what_ran` re-derived from the entry (one without a file is `not run` with the entry's
  reason and carries the entry's `runcard`)."""
  files = {n: load_round(st, rid, n) for n in round_numbers(st, rid)}
  if review["kind"] != "head":
    return list(files.values())
  rounds = []
  for entry in sorted(core.load_foreman(st, review["artifact"])["rounds"], key=lambda e: e["round"]):
    rnd = files.get(entry["round"]) or {"round": entry["round"], "runcard": entry.get("runcard"),
                                        "artifact_sha256": entry.get("head"), "builder_contested": [], "reviewers": {}}
    rounds.append(rnd | {"what_ran": derive_what_ran(review, rnd, entry)})
  return rounds


def evaluate(st: core.Store, review: dict, runcard: str) -> Status:
  """The one convergence rule (section 5), the cap and the stall rule (section 8); exit order 4, 0, 5, 2, 3."""
  rid = review_id(st, review["kind"], review["artifact"], review["cycle"])
  rounds = rounds_of(st, rid, review)
  completed = [r for r in rounds if r["what_ran"] == "completed"]
  latest = completed[-1] if completed else None
  rulings = [r["ruling"] for r in review["rulings"]]
  fix_design = any(f["disposition"] == "fix-design" for r in rounds for f in findings_of(r))
  clean = latest is not None and not any(blocking(f) and f["disposition"] is None for f in findings_of(latest))
  regressions = regressions_of(latest) if latest else 0
  accept = next((r for r in review["rulings"] if r["ruling"] == "accept"), None)
  latest_sha = latest["artifact_sha256"] if latest else None
  moved = latest is not None and review["kind"] != "head" \
      and latest_sha != current_sha(st, review["kind"], review["artifact"])
  converged, converged_round = "no", None
  if fix_design:
    pass
  elif accept:
    converged, converged_round = f"by ruling {accept['id']}", review["converged_round"]
  elif clean and not regressions and not moved:
    converged, converged_round = "yes", latest["round"]
  cap = "stop" in rulings or len(completed) >= CAP + rulings.count("continue")
  stalled = len(rounds) >= 2 and all(r["what_ran"] != "completed" and r.get("runcard") == runcard for r in rounds[-2:])
  sha = next((r["artifact_sha256"] for r in rounds if r["round"] == converged_round), None)
  code = 4 if fix_design else 0 if converged != "no" else 5 if stalled else 2 if cap else 3
  line = (f"round {latest['round'] if latest else 0}: {'clean' if clean else 'not clean'}, regressions {regressions}, "
          f"converged {converged}, cap {'yes' if cap else 'no'}, stalled {'yes' if stalled else 'no'}, sha256 {sha or 'none'}")
  trend = (f"rounds: {' -> '.join(str(len(findings_of(r))) for r in rounds)} "
           f"(regressions {', '.join(str(regressions_of(r)) for r in rounds)})") if rounds else "rounds: none"
  fixed = moved and clean and not regressions and not (fix_design or accept)
  return Status(code, line, trend, converged, converged_round, sha, moved, latest_sha, fixed)


def store_verdict(st: core.Store, rid: str, review: dict, runcard: str) -> Status:
  """Re-derive `converged` and `converged_round` into `review.json` after a record or a settle."""
  status = evaluate(st, review, runcard)
  review["converged"], review["converged_round"] = status.converged, status.converged_round
  save_review(st, rid, review)
  return status


def status_review(args) -> int:
  """Prints the state line and the trend; writes nothing; the exit code is the verdict."""
  st = core.store(core.git_toplevel(Path.cwd()))
  review = load_review(st, args.review)
  if review is None:
    print(f"review {args.review}: not opened")
    return 3
  card = bind(args, review)
  status = evaluate(st, review, card.get("parent") or args.runcard)
  print(status.line)
  print(status.trend)
  if status.fixed:
    print("fixed: re-review on the current bytes")
  return status.code


# ---------------------------------------------------------------- post: a head round on its pull request


def header(round_n: int, head: str) -> str:
  return f"**SuperEGM review round {round_n} (head {head[:7]})**"


POST_HEADER_RE = re.compile(r"^\*\*SuperEGM review round \d+ \(head [0-9a-f]{7}\)\*\*$", re.M)  # `header`'s form


def read_threads(repo: str, number: int, skip: set) -> list[dict]:
  """A PR's review threads (spec section 8, External review): a review comment with no `in_reply_to`, its
  replies its text, and a non-empty review body of a review with no inline comments that is not `APPROVED`;
  a review carrying `review post`'s header is the foreman's, never a thread. `skip` holds root ids left out."""
  comments = core.gh_pages(f"repos/{repo}/pulls/{number}/comments")
  reviews = core.gh_pages(f"repos/{repo}/pulls/{number}/reviews")
  login = lambda item: ((item.get("user") or {}).get("login")) or "ghost"
  replies = {}
  for c in comments:
    if c.get("in_reply_to_id") is not None:
      replies.setdefault(c["in_reply_to_id"], []).append(c.get("body") or "")
  inline = {c.get("pull_request_review_id") for c in comments}
  threads = []
  for c in comments:
    if c.get("in_reply_to_id") is not None or c["id"] in skip:
      continue
    threads.append({"id": c["id"], "login": login(c), "bot": login(c).endswith("[bot]"),
                    "body": "\n\n".join([c.get("body") or "", *replies.get(c["id"], [])]), "path": c.get("path"),
                    "line": c.get("line"), "commit_id": c.get("commit_id"), "review_body": False,
                    "created_at": c.get("created_at")})
  for r in reviews:
    body = r.get("body") or ""
    if POST_HEADER_RE.search(body):
      continue
    if (not body.strip() or r["id"] in inline or r.get("state") == "APPROVED" or r["id"] in skip):
      continue
    threads.append({"id": r["id"], "login": login(r), "bot": login(r).endswith("[bot]"), "body": body, "path": None,
                    "line": None, "commit_id": r.get("commit_id"), "review_body": True, "created_at": r.get("submitted_at")})
  return threads


def mask(text: str, config: dict) -> str:
  """A thread's text made safe to post: `|` written `/`, `@` written `@ `, a `banned_terms` match split the same way."""
  text = text.replace("|", "/").replace("@", "@ ")
  for pattern in config.get("banned_terms") or []:
    term = re.compile(pattern)
    for _ in range(len(text) + 1):
      match = term.search(text)
      if not match or not match.group(0):
        break
      text = text[:match.start() + 1] + " " + text[match.start() + 1:]
  return text


def thread_line(reviewer: str, rnd: int, n: int, thread: dict, severity: str, config: dict) -> str:
  """The thread's finding line: `<reviewer>-<round>-<n> | <severity> | <file:line or PR> at <commit7> |
  regression: no | <the first line, 200 chars, masked>`."""
  where = thread.get("path") or "PR"
  if thread.get("path") and thread.get("line") is not None:
    where += f":{thread['line']}"
  where = f"{mask(where, config)} at {(thread.get('commit_id') or '')[:7]}"
  first = ((thread.get("body") or "").strip().splitlines() or [""])[0].strip()[:200]
  return f"{reviewer}-{rnd}-{n} | {severity} | {where} | regression: no | {mask(first, config)}"


def collaborator_role(repo: str, login: str) -> str:
  """The login's repository role (`collaborators/<login>/permission`): its `role_name`, or its base `permission`
  when the role name is not one of `ROLES` (a custom repository role); `none` when GitHub answers 404 (not a
  collaborator). Any other refusal propagates."""
  try:
    data = core.gh_json(["api", f"repos/{repo}/collaborators/{login}/permission"]) or {}
  except core.GhError as error:
    if error.http_status == 404:
      return "none"
    raise
  return next((r for r in (data.get("role_name"), data.get("permission")) if r in ROLES), "none")


def thread_severity(thread: dict, config: dict, role: str | None) -> str:
  """A thread's severity (spec section 8, External review): a human below `ingest.human_role` is `low`; a bot's
  review body is `low`; a human's review body is `medium` when its first line carries a severity word or a
  mapped word, else `low`; an inline thread is the word its first line starts with or carries in a bold or
  bracketed marker, else `low`. Words match whole and case-folded."""
  ingest = config["ingest"]
  if not thread["bot"] and ROLES.index(role if role in ROLES else "none") < ROLES.index(ingest["human_role"]):
    return "low"
  if thread["review_body"] and thread["bot"]:
    return "low"
  words = {w.casefold(): s for w, s in ingest["severity_words"].items()}
  words.update({s: s for s in SEVERITIES})
  first = ((thread.get("body") or "").strip().splitlines() or [""])[0].casefold()
  found = [m.group(0) for m in re.finditer(r"[^\W_]+(?:[-'][^\W_]+)*", first)]
  if thread["review_body"]:
    return "medium" if any(w in words for w in found) else "low"
  starts = re.match(r"\W*([^\W_]+(?:[-'][^\W_]+)*)", first)  # a compound word (`security-bug`) whole, as the tokenizer's
  marked = [(m.group(1) or m.group(2)).strip(" :") for m in re.finditer(r"\*\*([^*]+?)\*\*|\[([^\]]+?)\]", first)]
  for word in ([starts.group(1)] if starts else []) + marked:
    if word in words:
      return words[word]
  return "low"


def render_comment(round_json: dict, head: str, ci_verdict: str, mention) -> str:
  """The configured mention as line 1 when set, the header, the round's finding lines (section 8's form)
  and `CI: <verdict>`; no run card, no model names."""
  lines = [mention] if mention else []
  lines += [header(round_json["round"], head), ""]
  for record in (round_json.get("reviewers") or {}).values():
    lines += [f"{f['id']} | {f['severity']} | {f['location']} | regression: {f['regression']} | {f['claim']}"
              for f in record["findings"]]
  lines += ["", f"CI: {ci_verdict}"]
  return "\n".join(lines) + "\n"


def post(args) -> int:
  """EGM's posting guard in the helper: the round's review goes to the pull-request reviews API bound to the
  commit it reviewed, as a COMMENT, after the raw-text scan; the response's `commit_id` must be that sha
  for the round to count `posted`."""
  st = core.store(core.git_toplevel(Path.cwd()))
  card = core.require_runcard(args, SKILLS)
  unit, n = args.unit, args.round
  data = core.load_foreman(st, unit)
  require_dispatch(unit, data, args.dispatch)
  entry = next((e for e in data["rounds"] if e.get("round") == n), None)
  if entry is None or not entry.get("head"):
    raise core.HandoffError(f"review post: {unit} has no prepared round {n}")
  rid = head_review_id(st, unit)
  if rid is None:
    raise core.HandoffError(f"review post: {unit} has no head review")
  config, head = st.config, entry["head"]
  repo, number = config["repo"], core.load_state(st.root)["units"][unit]["pr"]["number"]
  runcard = card.get("parent") or args.runcard
  if "dod_runs" not in entry or "test_delta" not in entry:  # U25: the word only after both gates ran (empty is not absent)
    raise Refusal("post: gates not run")
  present = next((r for r in core.gh_pages(f"repos/{repo}/pulls/{number}/reviews")
                  if carries_header(r.get("body"), n, head)), None)
  if present:  # never posted twice: counted when bound to the reviewed sha, refused otherwise
    if present.get("commit_id") != head:
      raise Refusal(f"header present on {(present.get('commit_id') or '')[:7]}")
    print(f"posted {count_posted(st, unit, entry, present['submitted_at'], rid, runcard)} (already on the PR)")
    return 0
  folder = st.path("review", unit, f"pr{number}") / f"r{n}"
  verdict = json.loads(core.read_text(folder / "ci.json"))["verdict"]
  rnd = load_round(st, rid, n) or {"round": n, "reviewers": {}, "builder_contested": []}
  body = render_comment(rnd, head, verdict, config.get("fix_request_mention") or None)
  problems = core.scan_text(body, config, "comment", label="comment")
  if problems:
    raise Refusal(problems[0].split(": ", 1)[1])  # from the label on: `comment:<line>: <reason>`
  root = core.git_toplevel(Path.cwd())
  if merge_base_moved(root, core.load_state(st.root).get("remote") or config["remote"], config["base"], number, entry):
    entry.update({"phase": "collected", "outcome": "not run (target-moved)"})
    core.save_foreman(st, unit, data)
    core.journal(st, f"{unit} round {n} collected (not run (target-moved)) under {runcard}")
    print("target-moved")
    return 3
  core.atomic_write(folder / "comment.md", body)
  _, text = core.gh_post(f"repos/{repo}/pulls/{number}/reviews",
                         {"commit_id": head, "event": "COMMENT", "body": f"@{folder / 'comment.md'}"})
  response = json.loads(text) if text.strip() else {}
  if response.get("commit_id") != head:
    raise Refusal(f"posted on {(response.get('commit_id') or '')[:7]}, not {head[:7]}: round {n} not counted")
  word = count_posted(st, unit, entry, response.get("submitted_at") or core.now_iso(), rid, runcard)
  print(f"posted {word}")
  return 0


COMMENT_LIMIT = 65_536  # GitHub's review comment limit, in bytes: the ingest comment's bound


def carries_header(body, n: int, head: str) -> bool:
  """Whether a PR review body carries `review post`'s header for round `n` on `head` on a line of its own:
  `render_comment` puts `config.fix_request_mention` on line 1 when set, so the header is not always first."""
  return header(n, head) in (body or "").splitlines()


def ingest(args) -> int:
  """`review ingest --pr <n>` routes to `ingest_spec_pr` (U26: the spec PR's threads into the latest round of the
  spec's latest cycle, closed by an `accept` or not). `review ingest --unit` (spec section 8, External review): every review thread of the unit's PR not yet
  ingested, on a head the latest posted round reviewed, recorded as one `external:<login>` finding in that
  round; the ones from a bot or a human at `ingest.human_role` or above posted first as one review comment
  in `review post`'s form. A landed unit is not read. Every read precedes every write: a refused read records
  nothing. A login's new findings are numbered after its highest recorded id. Before the post the ingest writes
  its plan, `r<n>/ingest.json` (each line, each finding id's root comment id, the comment body, and once posted
  the comment's id under `posted`), and a plan not marked `done` on the latest posted round is resumed verbatim
  before any new thread is read into one; one on an earlier round is marked `abandoned` and refused, recording
  nothing, the refusal telling the owner to re-run `review ingest`, which plans those threads afresh on the latest
  round (a plan is never finished into an earlier round). The plan is marked `done` only after every record, the
  foreman file and the journal are saved. A resumed plan's comment is found on the PR
  by its `posted` id, or, when its answer was never saved, as a comment on the round's head under the round's
  header on any line carrying every planned line whole, and not posted again; each finding is recorded against the thread it
  was posted for (`record_round` stamps the root id under `thread` in the same write), and the threads join
  `ingested[]`. With no new thread an ingest still re-reads an edited thread's text into its finding (its
  severity kept), backfills `ingested[]` from a finding's `thread`, and rewrites a `clean` outcome; an ingest
  that finds nothing to change writes nothing. The `ready again` journal line names the login of the round's first
  external finding at the highest severity whose `disposition` is unset (a builder's reply sets none). With no builder App and no builder token the ingest refuses: `gh api user`
  would answer the owner's login. A `cap-reached` it wrote prints `outcome: cap-reached` again on every ingest
  until a Decision point 2 (`source` `review <id> cap`) is opened at or after the round's `posted_at` (`asked_at`
  is the host's clock, `posted_at` GitHub's: a host clock behind GitHub's delays the stop)."""
  from superegm.launch import app_login  # lazily: launch imports this module
  st = core.store(core.git_toplevel(Path.cwd()))
  if getattr(args, "pr", None) is not None:
    return ingest_spec_pr(args, st)
  card = core.require_runcard(args, SKILLS)
  unit, config = args.unit, st.config
  wave = card.get("parent") or args.runcard
  data = core.load_foreman(st, unit)
  state = core.load_state(st.root)
  posted_rounds = sorted((e for e in data["rounds"] if e.get("phase") == "posted" and e.get("head")), key=lambda e: e["round"])
  entry = posted_rounds[-1] if posted_rounds else None
  rid = head_review_id(st, unit)
  landed = (((state.get("status") or {}).get("units") or {}).get(unit) or {}).get("landed")
  if entry is None or rid is None or landed:  # a merged PR's thread returns nothing to flight
    print("0 ingested")
    return 0
  repo, number = config["repo"], state["units"][unit]["pr"]["number"]
  root = core.git_toplevel(Path.cwd())
  plan, latest = None, entry
  for e in posted_rounds:  # an unfinished plan, in whatever posted round it was written, is finished first
    path = st.path("review", unit, f"pr{number}") / f"r{e['round']}" / "ingest.json"
    saved = json.loads(core.read_text(path)) if path.exists() else None
    if (saved and not saved.get("done") and not saved.get("abandoned") and saved.get("round") == e["round"]
        and saved.get("head") == e["head"]):
      plan, entry = saved, e
      break
  n, head = entry["round"], entry["head"]
  folder = st.path("review", unit, f"pr{number}") / f"r{n}"
  plan_path = folder / "ingest.json"
  if plan is not None and n < latest["round"]:  # never finished into an earlier round: the owner's re-run plans afresh
    core.atomic_write(plan_path, {**plan, "abandoned": True})
    raise Refusal(f"review ingest: round {n}'s unfinished ingest is not on the latest posted round ({latest['round']}): "
                  f"nothing recorded; re-run `review ingest` to plan its threads afresh on round {latest['round']}")
  recorded = {f["thread"] for m in round_numbers(st, rid) for name, record in load_round(st, rid, m)["reviewers"].items()
              if name.startswith("external:") for f in record["findings"] if "thread" in f}
  done = set(data.get("ingested") or []) | recorded
  threads = read_threads(repo, number, skip=set())
  read, new = {}, plan is None
  if new:
    env = config["builder"]["gh_token_env"]
    token = os.environ.get(env) if env else None
    if not app_login(config) and not token:  # with no token `gh api user` answers the owner's login, not the builder's
      raise Refusal(f"review ingest: {env} is not set: the builder's login is unknown")
    builder = app_login(config) or core.gh(["api", "user", "-q", ".login"], token=token).strip()
    owners = set(config.get("owners") or [])
    fresh = []
    for thread in threads:
      first = ((thread["body"] or "").strip().splitlines() or [""])[0]
      if thread["id"] in done or thread["login"] == builder:
        continue
      if thread["login"] in owners and first.startswith("**Ruling:**"):
        continue  # a ruling is read on the unit's issue alone
      try:  # a thread on a later head waits for the round that reviews it
        core.run_git(["merge-base", "--is-ancestor", thread["commit_id"] or "", head], root, check=True)
      except core.HandoffError:
        continue
      fresh.append(thread)
    roles = {r["login"]: r["role"] for r in core.load_card(st, wave).get("roles") or []}
    for thread in fresh:
      if thread["bot"] or thread["login"] in roles or thread["login"] in read:
        continue
      try:
        read[thread["login"]] = collaborator_role(repo, thread["login"])
      except core.GhError as error:
        raise Refusal(f"review ingest: {error}")
    roles.update(read)
    rnd = load_round(st, rid, n) or {"reviewers": {}}
    minimum = ROLES.index(config["ingest"]["human_role"])
    lines, postable, thread_of, top = {}, {}, {}, {}
    for thread in fresh:
      ext = f"external:{thread['login']}"
      role = None if thread["bot"] else roles.get(thread["login"], "none")
      if ext not in top:  # after the login's highest recorded id, whatever ids the record took
        top[ext] = max((int(f["id"].rsplit("-", 1)[1]) for f in (rnd["reviewers"].get(ext) or {}).get("findings") or []),
                       default=0)
      top[ext] += 1
      line = thread_line(ext, n, top[ext], thread, thread_severity(thread, config, role), config)
      lines.setdefault(ext, []).append(line)
      thread_of[line.split(" | ", 1)[0]] = thread["id"]
      if thread["bot"] or ROLES.index(role) >= minimum:
        postable.setdefault(ext, []).append(line)
    body = None
    if postable:
      shown = {"round": n, "reviewers": {ext: {"findings": parse_findings("\n".join(ls), ext, n)} for ext, ls in postable.items()}}
      verdict = json.loads(core.read_text(folder / "ci.json"))["verdict"]
      body = render_comment(shown, head, verdict, config.get("fix_request_mention") or None)
      if len(body.encode("utf-8")) > COMMENT_LIMIT:
        raise Refusal(f"review ingest: comment over 65,536 bytes ({sum(map(len, postable.values()))} threads)")
      problems = core.scan_text(body, config, "comment", label="comment", limit=None)
      if problems:
        raise Refusal(f"review ingest: {problems[0].split(': ', 1)[1]}")
    plan = {"round": n, "head": head, "lines": lines, "threads": thread_of, "body": body, "done": False}
  thread_of, lines, body = plan["threads"], plan["lines"], plan["body"]  # a resumed plan's own, verbatim
  present = None
  if body:
    planned = {line for line in body.splitlines() if line.startswith("external:")}  # each line whole, its text too
    reviews = core.gh_pages(f"repos/{repo}/pulls/{number}/reviews")
    if plan.get("posted") is not None:  # the ingest's own comment, by the id its post answered
      present = next((r for r in reviews if r.get("id") == plan["posted"]), None)
    else:  # a post whose answer was never saved: a comment on the round's head carrying every planned line whole
      present = next((r for r in reviews if r.get("commit_id") == head and carries_header(r.get("body"), n, head)
                      and planned <= set(r["body"].splitlines())), None)
    if present and present.get("commit_id") != head:  # an interrupted ingest's comment, bound to another sha
      raise Refusal(f"review ingest: header present on {(present.get('commit_id') or '')[:7]}, not {head[:7]}: nothing recorded")
  for login in read:
    core.card_add(st, wave, "roles", {"login": login, "role": read[login]})
  if new and lines:
    core.atomic_write(plan_path, plan)
  if body and not present:  # never posted twice: an interrupted ingest's comment stands
    core.atomic_write(folder / "ingest.md", body)
    _, text = core.gh_post(f"repos/{repo}/pulls/{number}/reviews",
                           {"commit_id": head, "event": "COMMENT", "body": f"@{folder / 'ingest.md'}"})
    response = json.loads(text) if text.strip() else {}
    if response.get("id") is not None:  # a retry finds this comment by its id, never by its text
      plan = {**plan, "posted": response["id"]}
      core.atomic_write(plan_path, plan)
    if response.get("commit_id") != head:
      raise Refusal(f"review ingest: posted on {(response.get('commit_id') or '')[:7]}, not {head[:7]}: "
                    "the comment stands on the PR, nothing recorded")
  count = len({tid for tid in thread_of.values() if tid not in done})
  for ext, ls in lines.items():
    path = folder / f"external-{ext.split(':', 1)[1]}.findings"
    core.atomic_write(path, "\n".join(ls) + "\n")
    mine = {line.split(" | ", 1)[0]: thread_of[line.split(" | ", 1)[0]] for line in ls}
    with contextlib.redirect_stdout(io.StringIO()):
      code = record_round(argparse.Namespace(review=rid, round=n, sha256=head, reviewer=ext, findings=str(path), not_run=None,
                                             isolation="exposed:ingest", model="none:none", effort="none:none",
                                             runcard=args.runcard, unit=None, design=None, plan=None, threads=mine))
    if code != 0:
      raise Refusal(f"review ingest: {ext} not recorded in round {n} (exit {code})")
    data = core.load_foreman(st, unit)
    have = set(data.get("ingested") or [])
    data.setdefault("ingested", []).extend(tid for tid in mine.values() if tid not in have)
    core.save_foreman(st, unit, data)
  edited = {t["id"]: t for t in threads if t["id"] in done}
  for m in round_numbers(st, rid):  # an edited thread's text re-read, its severity kept
    saved, changed = load_round(st, rid, m), False
    for reviewer, record in saved["reviewers"].items():
      for finding in record["findings"] if reviewer.startswith("external:") else []:
        thread = edited.get(finding.get("thread"))
        if thread is not None:
          claim = thread_line(reviewer, m, 1, thread, finding["severity"], config).split(" | ", 4)[4]
          if claim != finding["claim"]:
            finding["claim"], changed = claim, True
    if changed:
      core.atomic_write(st.path("reviews", rid, f"round-{m}.json"), saved)
  data = core.load_foreman(st, unit)
  missing = sorted(recorded - set(data.get("ingested") or []))
  saved_entry = next(e for e in data["rounds"] if e["round"] == latest["round"])
  word = None
  if saved_entry.get("outcome") == "clean":  # the mirror of `review post`'s `clean` write
    word = {3: "revise", 2: "cap-reached"}.get(status_code(rid, wave))
    if word:
      saved_entry.update({"outcome": word, "rewritten_from": "clean"})
  elif str(saved_entry.get("outcome") or "").startswith("owner:") and not owner_only_fids(load_round(st, rid, latest["round"]) or {"reviewers": {}}):
    # an external high or medium beside the owner's own leaves the remainder mixed: `revise`, or `cap-reached` at the cap
    word = {3: "revise", 2: "cap-reached"}.get(status_code(rid, wave))
    if word:
      saved_entry.update({"outcome": word, "rewritten_from": saved_entry["outcome"]})
  # point 2 opened since the round was posted: `decision open` records the PR's head then, not the round's
  routed = any(d.get("point") == 2 and d.get("source") == f"review {rid} cap" and d.get("asked_at", "") >= saved_entry.get("posted_at", "")
               for d in data.get("decisions") or [])
  again = not word and not routed and (saved_entry.get("outcome"), saved_entry.get("rewritten_from")) == ("cap-reached", "clean")
  if missing or word:
    data.setdefault("ingested", []).extend(missing)
    core.save_foreman(st, unit, data)
  if count:
    core.journal(st, f"{unit} round {n} ingested {count} under {wave}")
  if word:  # the login of the round's first external finding at the highest severity no settlement recorded
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    open_ext = [f for name, record in (load_round(st, rid, n) or {"reviewers": {}})["reviewers"].items()
                if name.startswith("external:") for f in record["findings"] if f["disposition"] is None]
    login = min(open_ext, key=lambda f: rank[f["severity"]])["id"].rsplit("-", 2)[0] if open_ext else "external:?"
    core.journal(st, f"{unit} ready again ({login}) under {wave}")
  if lines:  # done only once every record, the foreman file and the journal are saved
    core.atomic_write(plan_path, {**plan, "done": True})
  print(f"{count} ingested")
  if word:
    print(f"outcome: {word}")
  elif again:  # a rewrite whose routing line was never acted on: printed until point 2 is opened after the post
    print("outcome: cap-reached")
  return 0


def ingest_spec_pr(args, st: core.Store) -> int:
  """`review ingest --pr <n>` (kind spec, U26): the card's artifact is the spec; its latest cycle takes the threads."""
  if args.runcard:
    args.design = core.load_card(st, args.runcard)["artifact"]
  card = core.require_runcard(args, SKILLS)
  review, _ = latest_cycle(st, "spec", args.design)
  if review is None:
    raise Refusal(f"review ingest: no spec review for {core.spec_slug(args.design)}")
  count, _ = ingest_pr(st, review, args.pr, card.get("parent") or args.runcard)
  print(f"{count} ingested")
  return 0


def spec_cycles(st: core.Store, artifact: str) -> list[tuple[str, dict]]:
  """Every cycle of the spec's review, `(review id, review.json)`, oldest first."""
  return [(rid, load_review(st, rid)) for rid in cycle_ids(st, "spec", artifact)]


def external_record(rnd: dict, reviewer: str) -> dict:
  """The round's record of an external reviewer, opened outside the panel when absent."""
  return rnd["reviewers"].setdefault(reviewer, {"findings": [], "not_run": None, "isolation": "exposed:ingest",
                                                "model": "none:none", "effort": "none:none"})


def ingest_pr(st: core.Store, review: dict, number: int, runcard: str) -> tuple[int, list[str]]:
  """The spec PR's threads (spec section 8, External review on the elephant's own PR) recorded as `external:<login>`
  findings into the latest round of `review`'s cycle, closed by an `accept` or not; a thread whose root id is in
  any cycle's `ingested[]`, or on any external finding of any cycle's round (a write the `ingested[]` one never
  followed, backfilled), is skipped by the reader, and an owner's `**Ruling:**` is dropped after it (never a finding, never in `ingested[]`,
  and settling nothing: unlike the `--unit` path, which reads a ruling on the unit's issue, nothing reads one on the
  spec PR; a spec's rulings are made in the session or by the judges). Every unsettled external high or medium of an earlier round is
  carried into the round first, and a new thread's id is numbered after every id of its reviewer and round number
  in any cycle, so no fid is reused. Recorded outside the panel and the round's byte and scope checks, so `what_ran`
  is untouched; each finding keeps its PR's `number` as `pr`. Then the reply pass posts `**Reply <fid>:** fixed` on
  GitHub (`reply_fixed`, whose failures are named and retried, never refused). A gh failure of the read is a
  one-line Refusal. Returns
  the count and that round's unsettled external high and medium fids."""
  rid = review_id(st, "spec", review["artifact"], review["cycle"])
  numbers = round_numbers(st, rid)
  if not numbers:
    raise Refusal(f"review ingest: {rid} has no round")
  n, config = numbers[-1], st.config
  rnd = load_round(st, rid, n)
  cycles = spec_cycles(st, review["artifact"])
  listed = {tid for _, other in cycles for tid in (other.get("ingested") or [])}
  recorded = [f["thread"] for other_rid, _ in cycles for m in round_numbers(st, other_rid)
              for name, record in load_round(st, other_rid, m)["reviewers"].items() if name.startswith("external:")
              for f in record["findings"] if f.get("thread") is not None]
  backfill = sorted({tid for tid in recorded if tid not in listed})
  carried = carry_externals(st, review["artifact"], rid, rnd)
  owners = set(config.get("owners") or [])
  try:  # an owner's `**Ruling:**` is dropped, never a finding; nothing reads it here (the `--unit` path reads its issue's)
    threads = [t for t in read_threads(config["repo"], number, listed | set(recorded))
               if not (t["login"] in owners and ((t["body"] or "").strip().splitlines() or [""])[0].startswith("**Ruling:**"))]
    roles = {}
    for thread in threads:
      if not thread["bot"] and thread["login"] not in roles:
        roles[thread["login"]] = collaborator_role(config["repo"], thread["login"])
  except core.GhError as error:
    raise Refusal(f"review ingest: {error}")
  # a new id is numbered after every `<ext>-<n>-k` any round of any cycle holds (round numbers restart per cycle),
  # so no fid is ever reused, carried or settled
  held = [f["id"] for r in [rnd] + [load_round(st, other_rid, m) for other_rid, _ in cycles
                                     for m in round_numbers(st, other_rid) if (other_rid, m) != (rid, n)]
          for f in findings_of(r)]
  added = []
  for thread in threads:
    ext = f"external:{thread['login']}"
    record = external_record(rnd, ext)
    top = max((int(m.group(1)) for fid in held + [f["id"] for f in record["findings"]]
               if (m := re.fullmatch(rf"{re.escape(ext)}-{n}-(\d+)", fid))), default=0)
    severity = thread_severity(thread, config, None if thread["bot"] else roles[thread["login"]])
    [finding] = parse_findings(thread_line(ext, n, top + 1, thread, severity, config), ext, n)
    record["findings"].append({**finding, "thread": thread["id"], "review_body": thread["review_body"], "pr": number})
    added.append(thread["id"])
  if added or carried:
    core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
  if added or backfill:
    review["ingested"] = (review.get("ingested") or []) + backfill + added
  if added or carried or backfill:
    store_verdict(st, rid, review, runcard)
  if carried:
    core.journal(st, f"review ingest {rid} round {n} carried {', '.join(carried)} under {runcard}")
  if added:
    core.journal(st, f"review ingest {rid} round {n} PR {number} ingested {len(added)} under {runcard}")
  unsettled = [f["id"] for name, record in rnd["reviewers"].items() if name.startswith("external:")
               for f in record["findings"] if blocking(f) and f["disposition"] is None]
  reply_fixed(st, review["artifact"], number, runcard)
  return len(added), unsettled


def reply_fixed(st: core.Store, artifact: str, number: int, runcard: str) -> list[int]:
  """One `**Reply <fid>:** fixed` on each thread of the spec PR settled `fixed` and not yet replied to, in any round
  of any cycle of the spec, under the session's own token, on the PR the thread came from (`pr`, else `number`); a
  review body has no replies endpoint, so its reply is a PR comment. Before posting, the PR's comments are read once:
  a reply already there (a post whose answer was lost) is recorded, never posted again, when it is the session's own
  login's and sits where this reply would (a PR comment for a review body, an inline reply to the thread's root else). The reply's id is written as
  `replied` on every copy of the finding right after its post, so a later failed post never repeats it. A failed read
  or post is named on stderr (`review ingest: reply <fid> not posted: <error>`) and retried on the next run, never a
  refusal: the reply is a courtesy of the ingest, not a condition of the approval. The thread ids replied to."""
  rounds_ = [(other_rid, m, load_round(st, other_rid, m)) for other_rid, _ in spec_cycles(st, artifact)
             for m in round_numbers(st, other_rid)]
  copies = {}
  for _, _, rnd in rounds_:
    for name, record in rnd["reviewers"].items():
      for f in record["findings"] if name.startswith("external:") else []:
        if f.get("thread") is not None:
          copies.setdefault(f["thread"], []).append(f)
  replied, posted_on, me = [], {}, None
  repo = st.config["repo"]
  for thread, found in sorted(copies.items()):
    if any(f.get("replied") for f in found) or not any(f["disposition"] == "fixed" for f in found):
      continue
    fixed = next(f for f in found if f["disposition"] == "fixed")
    pr, text = fixed.get("pr") or number, f"**Reply {fixed['id']}:** fixed"
    try:
      if pr not in posted_on:  # the PR's comments, read once: a reply posted but never recorded
        posted_on[pr] = ([("inline", c) for c in core.gh_pages(f"repos/{repo}/pulls/{pr}/comments")]
                         + [("pr", c) for c in core.gh_pages(f"repos/{repo}/issues/{pr}/comments")])
      # where this reply would sit: a review body's as a PR comment, a thread's as an inline reply to its root
      candidates = [c for where, c in posted_on[pr] if (c.get("body") or "").strip() == text
                    and (where == "pr" if fixed.get("review_body") else where == "inline" and c.get("in_reply_to_id") == thread)]
      if candidates and me is None:  # read only when a candidate exists: the session's own login, once
        me = (core.gh_json(["api", "user"]) or {}).get("login") or ""
      there = next((c for c in candidates if (c.get("user") or {}).get("login") == me), None)
      if there is not None:
        reply_id = there.get("id") or True
      else:
        endpoint = (f"repos/{repo}/issues/{pr}/comments" if fixed.get("review_body")
                    else f"repos/{repo}/pulls/{pr}/comments/{thread}/replies")
        _, body = core.gh_post(endpoint, {"body": text})
        try:
          reply_id = json.loads(body)["id"]
        except (ValueError, KeyError, TypeError):
          reply_id = True  # posted; its id unread
    except core.GhError as error:
      print(f"review ingest: reply {fixed['id']} not posted: {error}", file=sys.stderr)
      continue
    for f in found:
      f["replied"] = reply_id
    for other_rid, m, rnd in rounds_:
      if any(f.get("thread") == thread for f in findings_of(rnd)):
        core.atomic_write(st.path("reviews", other_rid, f"round-{m}.json"), rnd)
    core.journal(st, f"review ingest PR {pr} replied fixed on {thread} under {runcard}")
    replied.append(thread)
  return replied


def carry_externals(st: core.Store, artifact: str, rid: str, rnd: dict) -> list[str]:
  """Every unsettled external high or medium of an earlier round of the spec's cycles (this cycle's earlier rounds
  included) copied into `rnd` (the latest round, in memory) when no finding there holds its `(id, claim)`, as `collect`
  carries one on a head: the copy and the original are one finding. The fids carried."""
  held = {(f["id"], f["claim"]) for f in findings_of(rnd)}
  carried = []
  for other_rid, _ in spec_cycles(st, artifact):
    for m in round_numbers(st, other_rid):
      if (other_rid, m) == (rid, rnd["round"]):
        continue
      for reviewer, record in load_round(st, other_rid, m)["reviewers"].items():
        for finding in record["findings"] if reviewer.startswith("external:") else []:
          if blocking(finding) and finding["disposition"] is None and (finding["id"], finding["claim"]) not in held:
            external_record(rnd, reviewer)["findings"].append(dict(finding))
            held.add((finding["id"], finding["claim"]))
            carried.append(finding["id"])
  return carried


def outcome_word(status_exit: int, contested: list, owner=()) -> str:
  """The posted round's return word (section 11), in this order: an owner-only remainder (`owner_only_fids`)
  comes after a contest and before `revise` and `cap-reached` (U25)."""
  if contested:
    return "contested: " + ", ".join(contested)
  if owner:
    return "owner: " + ", ".join(owner)
  return {0: "clean", 2: "cap-reached"}.get(status_exit, "revise")


def contested_fids(round_json: dict) -> list:
  """The `builder_contested[].fid` whose `foreman` finding in the round has no disposition."""
  open_fids = {f["id"] for f in ((round_json.get("reviewers") or {}).get("foreman") or {}).get("findings") or []
               if f["disposition"] is None}
  return [c["fid"] for c in round_json.get("builder_contested") or [] if c["fid"] in open_fids]


def owner_only_fids(round_json: dict) -> list:
  """The unsettled `test-delta:` fids of the round when every unsettled high or medium of it is one of them, else
  []: a remainder the owner alone can settle (U25)."""
  open_blocking = [f for record in (round_json.get("reviewers") or {}).values() for f in record.get("findings") or []
                   if f["disposition"] is None and blocking(f)]
  owner = [f["id"] for f in open_blocking if f["claim"].startswith("test-delta:")]
  return owner if owner and len(owner) == len(open_blocking) else []


def count_posted(st: core.Store, unit: str, entry: dict, posted_at: str, review_id: str, runcard: str) -> str:
  """The round is `posted` at `posted_at`; its `what_ran` is re-derived, its `outcome` is the word `review
  status` and `builder_contested[]` imply, and `clean` journals `<unit> awaiting merge`."""
  data = core.load_foreman(st, unit)
  saved = next(e for e in data["rounds"] if e["round"] == entry["round"])
  saved.update({"phase": "posted", "posted_at": posted_at})
  core.save_foreman(st, unit, data)
  review, rnd = load_review(st, review_id), load_round(st, review_id, entry["round"])
  if rnd:
    rnd["what_ran"] = derive_what_ran(review, rnd, saved)
    core.atomic_write(st.path("reviews", review_id, f"round-{entry['round']}.json"), rnd)
  word = outcome_word(status_code(review_id, runcard), contested_fids(rnd or {}), owner_only_fids(rnd or {}))
  saved["outcome"] = word
  entry.update(saved)
  core.save_foreman(st, unit, data)
  core.journal(st, f"{unit} round {entry['round']} posted {word} under {runcard}")
  if word == "clean":
    core.journal(st, f"{unit} awaiting merge under {runcard}")
  return word


def merge_base_moved(root: Path, remote: str, base: str, pr: int, entry: dict) -> bool:
  """Fetch the base tip and compare the merge base of the fetched refs, at the repository root (never
  inside the worktree), with the one `prepare` recorded: an unrelated base commit leaves it unchanged."""
  core.run_git(["fetch", "--no-write-fetch-head", remote, f"+refs/heads/{base}:refs/superegm/pr-base/{pr}"], root)
  now = core.run_git(["merge-base", f"refs/superegm/pr-base/{pr}", f"refs/superegm/pr/{pr}"], root).strip()
  return now != entry.get("merge_base")


def status_code(review_id: str, runcard: str) -> int:
  """`review status` in-process with its stdout captured: the exit code alone (0 converged, 2 cap, 3 open or
  not clean, 4 fix-design, 5 stalled)."""
  with contextlib.redirect_stdout(io.StringIO()):
    return status_review(argparse.Namespace(review=review_id, runcard=runcard, unit=None, design=None, plan=None))


# ---------------------------------------------------------------- rule


def rule_review(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  rid = args.review
  review = load_review(st, rid)
  if review is None:
    raise core.HandoffError(f"review {rid}: not opened")
  card = bind(args, review)
  rulings = [r["ruling"] for r in review["rulings"]]
  if "stop" in rulings:
    raise core.HandoffError("review rule: cycle stopped")
  if args.ruling == "continue" and "continue" in rulings:
    raise core.HandoffError("review rule: continue already ruled this cycle")
  if args.ruling == "accept" and review["kind"] == "head":
    raise core.HandoffError("review rule: accept is refused on a head")
  status = evaluate(st, review, card.get("parent") or args.runcard)
  if status.code != 2:
    raise core.HandoffError("review rule: not at the cap")
  if args.ruling == "accept" and status.moved:
    raise core.HandoffError("review rule: the reviewed bytes moved: continue or stop")
  if args.owner:
    by = "owner"
  elif args.judges:
    by = f"judges:{args.judges}"
  elif args.ruling == "stop" and "continue" in rulings and status.moved:
    by = "helper"
  else:
    raise core.HandoffError("review rule: --owner or --judges required")
  ruling = {"id": f"R{len(rulings) + 1}", "ruling": args.ruling, "by": by, "at": core.now_iso()}
  review["rulings"].append(ruling)
  if args.ruling == "accept":
    completed = [r for r in rounds_of(st, rid, review) if r["what_ran"] == "completed"]
    review["converged"], review["converged_round"] = f"by ruling {ruling['id']}", completed[-1]["round"]
  save_review(st, rid, review)
  core.journal(st, f"review rule {rid} {ruling['id']} stop: the one option under {args.runcard}" if by == "helper"
               else f"review rule {rid} {ruling['id']} {args.ruling} by {by} under {args.runcard}")
  print(f"ruling {ruling['id']} {args.ruling}")
  return 0
