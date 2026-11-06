# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the review loop (spec section 8); the Astra lane on a head and its not-installed record (U17); the amendment scope of a spec review and the batch settle (U19).

"""superegm review open|record|settle|status|rule: the one review loop (spec section 8)."""

import argparse
import contextlib
from dataclasses import dataclass
import difflib
import hashlib
import io
import json
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
  s.add_argument("--finding", required=True)
  s.add_argument("--disposition", choices=DISPOSITIONS, required=True)
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
  p.set_defaults(run=run, writes=WRITES)


def by_whom(parser, required):
  group = parser.add_mutually_exclusive_group(required=required)
  group.add_argument("--owner", action="store_true", help="the owner ruled")
  group.add_argument("--judges", metavar="ID", help="the judges panel that ruled")
  parser.add_argument("--posted", metavar="COMMENT", help="in leavemealone with --owner: the owner's by-hand `**Ruling:** <fid> finding overruled` comment id")


def run(args):
  try:
    return {"open": open_review, "record": record_round, "settle": settle_finding,
            "status": status_review, "rule": rule_review, "post": post, "scope": scope_review}[args.action](args)
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
  naming no line is kept (D1 (a): the goldfish was briefed to cite lines, and an unplaceable finding is not lost)."""
  line = cited_line(location)
  if line is None or any(start <= line <= end for _, _, start, end in rows):
    return None
  index = section_of(spans, line)
  return spans[index][0] if index is not None else f"line {line} past the end"


def approved_text(spec: Path, approval: dict):
  """The approved bytes as text: the spec at the approval's `commit` (voided or not), else at the first commit
  of the current branch's `git log -- <spec>` whose blob hashes to its `sha256`; None when no commit holds them."""
  root = core.git_toplevel(spec.parent)
  rel = spec.resolve().relative_to(root.resolve()).as_posix()
  show = lambda commit: subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=str(root), capture_output=True)
  at = show(approval.get("commit") or "")
  if approval.get("commit") and at.returncode == 0:
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


def head_review_id(st: core.Store, unit: str):
  """The unit's latest `head-<unit>-c<n>` review id, or None before the first dispatch."""
  latest, _ = latest_cycle(st, "head", unit)
  return review_id(st, "head", unit, latest["cycle"]) if latest else None


def head_entry(st: core.Store, unit: str, n: int):
  """The unit's `rounds[]` entry of round `n`, or None."""
  return next((e for e in core.load_foreman(st, unit)["rounds"] if e.get("round") == n), None)


def latest_cycle(st: core.Store, kind: str, artifact: str) -> tuple[dict | None, bool]:
  """The latest cycle's `review.json` of this artifact and whether that cycle is closed: by an
  `accept` or `stop` ruling; a spec's by the approval that names it, once the bytes moved off its
  sha; an integrate's by the handoff closing or changing (D1 (a)), or by a `## Units` amendment
  past the bytes its latest completed round reviewed (a cycle with no completed round stays)."""
  base = review_id(st, kind, artifact, 0)[:-3]
  cycles = [int(m.group(1)) for p in st.path("reviews").glob(f"{base}-c*")
            if (m := re.fullmatch(rf"{re.escape(base)}-c(\d+)", p.name)) and (p / "review.json").is_file()]
  if not cycles:
    return None, False
  rid = f"{base}-c{max(cycles)}"
  review = load_review(st, rid)
  closed = any(r["ruling"] in ("accept", "stop") for r in review["rulings"])
  if not closed and kind == "spec":
    approval = core.load_approval(st, Path(artifact))
    closed = bool(approval) and approval["review"] == rid and approval["sha256"] != current_sha(st, kind, artifact)
  if not closed and kind == "integrate":
    state = core.load_state(st.root)
    amended = (core.load_approval(st, Path(artifact)) or {}).get("amended") or []
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
  if reviewer == "foreman":  # the helper's own findings (section 11), outside the panel
    if kind != "head":
      raise core.HandoffError("review record: foreman is accepted on a head only")
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
  if args.not_run:
    record = {"findings": [], "not_run": args.not_run, "isolation": None, "model": None, "effort": None}
  else:
    path = Path(args.findings)
    text = core.read_text(path)
    try:
      findings = parse_findings(text, reviewer, n)
    except ValueError as error:
      raise core.HandoffError(f"review record: {path}:{error}")
    if reviewer == "set":
      findings = keep_for_unit(findings, review["artifact"])
    if kind == "spec":
      spans = sections(core.read_text(Path(review["artifact"])))
      raw = [line for line in text.splitlines() if line.strip()]  # one finding per non-blank line, in order
      verdicts = [(finding, line, out_of_scope(rnd["scope"], spans, finding["location"])) for finding, line in zip(findings, raw)]
      findings = [finding for finding, _, section in verdicts if section is None]
      refused = [(finding["id"], line, section) for finding, line, section in verdicts if section is not None]
      mine = lambda line: line.split(" | ", 1)[0].rsplit("-", 2)[0] == reviewer
      rnd["out_of_scope"] = [line for line in rnd["out_of_scope"] if not mine(line)] + [line for _, line, _ in refused]
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
  if disposition == "fixed" and rnd["artifact_sha256"] == current_sha(st, review["kind"], review["artifact"]):
    raise core.HandoffError("review settle: fixed needs changed bytes")  # a head's current bytes are unknown: never
  if blocking(finding) and disposition in ("contested", "declined"):
    if card["mode"] == "leavemealone" and not args.judges:
      if not (args.owner and getattr(args, "posted", None)):
        raise core.HandoffError(f"review settle: {fid} is {finding['severity']}: --judges required in leavemealone-mode")
      verify_owner_ruling(st.config, fid, args.posted)
    if card["mode"] != "leavemealone" and not args.owner:
      raise core.HandoffError(f"review settle: {fid} is {finding['severity']}: --owner required in normal mode")
  finding["disposition"] = disposition
  finding["ruling"] = "owner" if args.owner else f"judges:{args.judges}" if args.judges else None
  core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
  copies = settle_set_copies(st, rnd, finding) if (review["kind"], reviewer, disposition) == ("plan", "set", "fixed") else []
  status = store_verdict(st, rid, review, card.get("parent") or args.runcard)
  if review["kind"] == "head" and status.code == 0:
    write_head_outcome(st, review, card.get("parent") or args.runcard)
  core.journal(st, f"review settle {rid} {fid} {disposition} by {finding['ruling'] or 'the elephant'}"
               + (f" copied to {', '.join(copies)}" if copies else "") + f" under {args.runcard}")
  print(f"{fid} {disposition}")
  return 0


def verify_owner_ruling(config: dict, fid: str, comment_id: str) -> None:
  """In leavemealone the owner's word still counts, by hand (1.1.3; U22 reads such comments itself): one GitHub
  read of the comment, by a `config.owners` login, starting `**Ruling:** <fid> finding overruled`."""
  comment = core.gh_json(["api", f"repos/{config['repo']}/issues/comments/{comment_id}"]) or {}
  author = (comment.get("user") or {}).get("login")
  if author not in (config.get("owners") or []):
    raise core.HandoffError(f"review settle: comment {comment_id} is by {author}, not a login in config.owners")
  if not (comment.get("body") or "").startswith(f"**Ruling:** {fid} finding overruled"):
    raise core.HandoffError(f"review settle: comment {comment_id} does not rule {fid} overruled")


def settle_set_copies(st: core.Store, rnd: dict, finding: dict) -> list:
  """A `set` finding settled `fixed` on one unit settles its copies: every other plan review's round
  under the same run card whose `set` record holds the same id and claim takes the disposition and
  ruling (one already holding them, the settled round included, is left alone); the review ids written."""
  copies = []
  for folder in st.path("reviews").glob(f"{st.handoff_id[-6:]}-plan-*-c*"):
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
  present = next((r for r in core.gh_pages(f"repos/{repo}/pulls/{number}/reviews")
                  if (r.get("body") or "").startswith(header(n, head))), None)
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


def outcome_word(status_exit: int, contested: list) -> str:
  """The posted round's return word (section 11), in this order."""
  if contested:
    return "contested: " + ", ".join(contested)
  return {0: "clean", 2: "cap-reached"}.get(status_exit, "revise")


def contested_fids(round_json: dict) -> list:
  """The `builder_contested[].fid` whose `foreman` finding in the round has no disposition."""
  open_fids = {f["id"] for f in ((round_json.get("reviewers") or {}).get("foreman") or {}).get("findings") or []
               if f["disposition"] is None}
  return [c["fid"] for c in round_json.get("builder_contested") or [] if c["fid"] in open_fids]


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
  word = outcome_word(status_code(review_id, runcard), contested_fids(rnd or {}))
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
