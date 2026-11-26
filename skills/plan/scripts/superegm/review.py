# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the review loop (spec section 8); the Astra lane on a head and its not-installed record (U17); the amendment scope of a spec review and the batch settle (U19); `review ingest` and the external reviewer (U21); `review ingest --pr`, the carry and the fixed replies on the spec PR (U26); the gates before the word, `owner: <ids>` and the owner-only settle of a `test-delta` finding (U25); the accept below the cap, its `acceptable:` line and the head's `--decision` (U35); the stall read across a tick's `wave` cards (U24); a scoped round's lineless finding out of scope and `approved_text` reading `spec_blob` (U32); an external comment read whole from its root (U73); `review.rounds` for the cap, stored at a cycle's open, and a spec resume's narrowed panel (`panels`) with its printed line, `derive_what_ran` and `review record` reading the round's panel (U36); `review settle --judges` for a head's contested or declined high or medium on a normal-mode card, journalled `Ruling (judges <panel>, contest)` (U88); `review triage` on a head, the deferral by a frozen pattern, its follow-up row and the owner's undo (U40); each reviewer's record copying its stored instructions manifest (U38); with `driver.chain` on, the stall read across the top-level cards of every chain phase (U44); the owner's proceed, its settlement, its `foreman.proceeds[]` entry and the convergence it gives first (U57); a merge round left out of the cap's count (U66); `review open` taking a loaded repository reviewer for its kinds, and a round record carrying its `persona` (U76); a spec cycle's changed reference documents as whole-file `changed <path>` scope lines, their `refs` manifest on each round, in the scope filter, the settle check and the proceed ruling (U75); `review open --respec R<n>`: the diff and its sections as evidence, the `design`, `codebase-details` and Astra panel, cap 2 (U85); a plan or integrate cycle a respec approval closed by its `source_review` (U91); `review record --sha256` on a head takes the full 40-hex commit sha alone (U101, 1.3 design section 3.4); the settle's writes in `apply_settle`, which `decision rule` calls on a point-1 ruling, the CI finding's refusal in `check_ci_finding` and a posted proceed comment edited before its record refused in `posted_comment` (U103, 1.3 design sections 3.6 and 3.7); a location's file name is its first whitespace-free token ending in a file extension that starts before the first line cite (U109, 1.3 design section 3.10).

"""superegm review open|record|settle|status|rule|scope|post|ingest|triage: the one review loop (spec section 8)."""

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
import sys

import superegm as core

WRITES = frozenset({"reviews", "foreman", "runcards", "review"})  # the store kinds this subcommand writes
CONFIG_DEFAULTS = {  # its own config keys and init lines (U32)
    "astra": {"enabled": False, "model": "gpt-6-astra", "effort": "xhigh", "heads": True, "heads_effort": "high"},
    "review": {"rounds": 3},  # completed rounds per cycle before the cap (U36)
    "ingest": {"severity_words": {"bug": "high", "issue": "medium", "nit": "low", "suggestion": "low"},
               "human_role": "write"},  # `review ingest`: a thread's word map and the role a human's thread counts from
}
INIT_STEP = ("The Astra lane is off until you set astra.enabled to true; astra.heads (default true) then seats it on every head review.\n"
             "`review ingest` reads PR review threads with ingest.severity_words (Devin's words by default) and counts a human's "
             "thread from ingest.human_role (default write) up.")
DOCTOR_CHECKS = None
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
RULINGS = ("continue", "accept", "stop", "proceed")
LEGACY_CAP = 5  # the cap of a cycle or an approval entry that stores none (opened under 1.2.0)
ROUNDS = range(1, 11)  # the bound of `review.rounds`, and of a spec's `Rounds:` line (`approve-spec` reads it by `valid_rounds`)


def valid_rounds(value) -> bool:
  """Whether `value` is an integer 1-10 (a bool is not)."""
  return isinstance(value, int) and not isinstance(value, bool) and value in ROUNDS


def live_rounds(st: core.Store) -> int:
  """`review.rounds` now; a value outside 1-10, or a `review` key that is no object, is refused, naming the key."""
  review = st.config.get("review")
  if not isinstance(review, dict):
    raise core.HandoffError(f"review.rounds: review must be an object, not {review!r}")
  value = review.get("rounds", CONFIG_DEFAULTS["review"]["rounds"])
  if not valid_rounds(value):
    raise core.HandoffError(f"review.rounds must be an integer 1-10, not {value!r}")
  return value


def cap_at_open(args, st: core.Store, kind: str, artifact: str) -> int:
  """The cap a new cycle stores, completed rounds plus one per `continue` ruling (section 5): a spec's review runs
  under the live `review.rounds`; the others under the `rounds` of the handoff's latest approval entry (5 without
  one: a 1.2.0 entry, an entry whose `rounds` is outside 1-10, or no approval entry of its own, as a legacy flat
  store's)."""
  if kind == "spec":
    return live_rounds(st)
  spec = artifact if kind == "integrate" else core.handoff_spec(args, st)
  entries = core.load_approvals(st, Path(spec)) if spec else []
  own = [e for e in entries if st.handoff_id and e.get("handoff_id") == st.handoff_id]  # another handoff's entry does not govern
  rounds = own[-1].get("rounds") if own else None
  return rounds if valid_rounds(rounds) else LEGACY_CAP


def cap_of(review: dict) -> int:
  """The cycle's cap: the one stored at open; a record opened under 1.2.0 has none and reads 5."""
  return review.get("cap", LEGACY_CAP)


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
  o.add_argument("--respec", help="kind spec: R<n>, review only the correcting diff of open respec R<n> (design, "
                                  "codebase-details and the Astra lane; cap 2)")
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
  u = core.add_parser(action, "rule", "record a ruling at the cap, or the owner's accept below it on an acceptable round")
  u.add_argument("--review", required=True)
  u.add_argument("--ruling", choices=RULINGS, required=True)
  u.add_argument("--decision", metavar="ID", help="on a head below the cap: the unit's pending point-5 decision naming this review")
  u.add_argument("--reason", help="proceed: the owner's reason, typed (else --posted names the owner's comment on a head)")
  by_whom(u, required=False)  # `stop` alone needs no ruler once `continue` is spent and the bytes moved
  v = core.add_parser(action, "post", "post a head round's review to its pull request, bound to the reviewed commit")
  v.add_argument("--unit", required=True)
  v.add_argument("--round", type=int, required=True)
  v.add_argument("--dispatch", required=True, help="the dispatch id `foreman dispatch` printed")
  i = core.add_parser(action, "ingest", "record a unit's PR review threads as external findings into its latest posted round (--unit), or the spec PR's into the latest round of the spec's latest cycle (--pr)")
  which = i.add_mutually_exclusive_group(required=True)
  which.add_argument("--unit")
  which.add_argument("--pr", type=int, help="the spec PR: its threads into the latest round of the spec's latest cycle")
  g = core.add_parser(action, "triage", "a head round's triage: its eligible mediums (--eligible), or the triage goldfish's reply recorded (--file)")
  g.add_argument("--review", required=True)
  g.add_argument("--round", type=int, required=True)
  which = g.add_mutually_exclusive_group(required=True)
  which.add_argument("--eligible", action="store_true", help="print the round's eligible mediums, one fid per line")
  which.add_argument("--file", help="the triage goldfish's reply, one line per eligible medium, recorded verbatim or refused whole")
  g.add_argument("--isolation", help="clean | exposed:<what>")
  g.add_argument("--model", help="<requested>:<effective>")
  g.add_argument("--effort", help="<requested>:<effective>")
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
            "ingest": ingest, "triage": triage}[args.action](args)
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
  """`completed` when every reviewer of the round's panel (`panel_at`) has a record for the round (an empty findings file counts;
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
  for reviewer in panel_at(review, rnd.get("round", 1)):  # a round dict built bare (a test's) reads round 1's panel
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


CITE_RE = re.compile(r"(?:\blines? |\bL|:)(\d+)")
FILE_TOKEN_RE = re.compile(r"[^\s:#,]+\.[A-Za-z][A-Za-z0-9]*(?=[:\s#,]|$)")  # a whitespace-free token ending in a file extension


def cited_line(location: str) -> int | None:
  """The line a finding's location cites: the first integer after `line `, `lines `, `L` or `:`, else None."""
  match = CITE_RE.search(location)
  return int(match.group(1)) if match else None


def out_of_scope(rows: list, spans: list, location: str, spec_name: str = "", root: str = "", respec: bool = False):
  """The heading of the section a finding cites when no scope row holds its line, else None; in a scoped
  round a location naming no line, or a line the spec does not hold, answers `none` (U32); a `whole` round
  exempts every finding. A round that lists reference documents (`("changed", <path>, 0, 0)` rows, U75) reads a
  location's path first: a listed document is in scope whatever its line, any other file but the spec (`spec_name`,
  its repository-relative path) answers `none`, and only a spec location goes on through `cited_line` and the
  sections. A file name is the location's first whitespace-free token that ends in a file extension (an extension
  that starts with a letter, the token ending at whitespace, `:`, `#`, `,` or the end) and starts before the
  location's first line cite (the span `cited_line` reads; any such token when the location cites no line), so a
  token after that cite names no file (`line 8 of design.md` and `§2 line 8 contradicts README.md` cite the spec's
  line 8), and a section cite such as `§3.5 line 4` or `3.5:4` names no file. The spec is named by its full path or
  its bare file name only, never with a directory in front of its path. A listed document is named by its full
  repository-relative path after one leading `./` or the repository root (`root`, an absolute path) is taken off,
  or by its bare file name (the spec's own name wins a tie), opening the location and ending at whitespace, `:`,
  `#`, `,` or the end, whatever follows it (it may hold spaces: `domain model.md line 12 vs docs/specs/design.md`
  names the listed document, and so does `domain model.md:500` when the spec is `docs/specs/model.md`); a directory
  in front of the path names another file. Two limits come with the token rule: a name that holds a space is matched
  whole only as a listed document opening the location, never as the spec (a spec `docs/specs/my design.md` is read
  from the token `design.md`, so `other/my design.md:8` reads as the spec's line 8 and `docs/specs/my design.md:8`
  names no spec file), and a dotted code symbol before the spec's name (`see body.steps in design.md line 4`) ends
  in an extension-shaped tail and reads as a file. A respec cycle (`respec`) lists no reference document and its
  remit is the spec's correction alone: a location naming any other file answers `none`."""
  listed = {row[1] for row in rows if row[0] == "changed" and row[2] == row[3] == 0}
  loc, ends = location.removeprefix("./"), ": \t,#"
  for prefix in {root.rstrip("/"), str(Path(root).resolve()).rstrip("/")} - {"", "."}:
    loc = loc.removeprefix(prefix + "/")
  cite = CITE_RE.search(loc)
  # shortcut: a dotted symbol such as body.steps before the spec's name ends in an extension-shaped tail and reads as a file
  named =next((m for m in FILE_TOKEN_RE.finditer(loc) if cite is None or m.start() < cite.start()), None)
  spec_named = bool(named) and bool(spec_name) and (named.group(0) == spec_name or ("/" not in named.group(0) and spec_name.rsplit("/", 1)[-1] == named.group(0)))
  if respec and named and not spec_named:
    return "none"
  if listed:
    named_as = lambda name: loc.startswith(name) and (len(loc) == len(name) or loc[len(name)] in ends)
    if any(named_as(path) for path in listed):
      return None
    spec_bare = spec_name.rsplit("/", 1)[-1]
    if any(named_as(bare) for bare in (path.rsplit("/", 1)[-1] for path in listed) if bare != spec_bare):
      return None  # a listed document by its bare file name opening the location, even when its last word is the spec's own name
    if not spec_named and named:
      return "none"
    rows = [row for row in rows if not (row[0] == "changed" and row[2] == row[3] == 0)]
  if rows and rows[0][0] == "whole":
    return None
  line = cited_line(location)
  index = None if line is None else section_of(spans, line)
  if index is None:
    return "none"
  if any(start <= line <= end for _, _, start, end in rows):
    return None
  return spans[index][0]


def approved_text(spec: Path, approval: dict):
  """The approved bytes as text, through `core.spec_blob`: searched first from the approval's `commit` (voided
  or not) when set, then from the current branch's `HEAD`; None when no commit holds them."""
  root = core.git_toplevel(spec.parent)
  rel = spec.resolve().relative_to(root.resolve()).as_posix()
  if approval.get("commit") and (text := core.spec_blob(root, rel, approval["sha256"], ref=approval["commit"])) is not None:
    return text
  return core.spec_blob(root, rel, approval["sha256"])


def reference_manifest(st: core.Store, root: Path) -> list[dict]:
  """`[{file, sha}]` (U75) of the `*.md` files under a configured `instructions` `dir` that changed between the merge
  base with `<base>` and `HEAD` (committed bytes only, as the approval freezes them), in path order, each with the
  12-hex blob sha of its bytes at `HEAD`; a file `HEAD` no longer holds (a deletion is a change) has `sha` None.
  `[]` with no `dir` entry; a git failure (no merge base, no `HEAD`, a failed diff) raises with git's own error."""
  from superegm import instructions  # at call time: that module's import chain reaches this one
  folders = [e["dir"].rstrip("/") for e in st.config.get("instructions") or [] if isinstance(e, dict) and isinstance(e.get("dir"), str)]
  if not folders:
    return []
  base = core.run_git(["merge-base", st.config["base"], "HEAD"], root).strip()
  head = core.run_git(["rev-parse", "HEAD"], root).strip()
  names = core.run_git(["diff", "--name-only", "--no-renames", "-z", base, head, "--", *[f + "/" for f in folders]], root)  # a rename lists both paths: its old one is a deletion
  found = []
  for name in sorted({n for n in names.split("\0") if n.endswith(".md")}):
    data = instructions.blob(root, head, name)
    found.append({"file": name, "sha": None if data is None else instructions.blob_sha(data)})
  return found


def refs_moved(st: core.Store, review: dict, rnd: dict) -> bool:
  """Whether a spec round's `refs` differ from the manifest at `HEAD` now (U75); a round with no `refs` key, one
  written before U75, never does."""
  if review["kind"] != "spec" or "refs" not in rnd:
    return False
  return reference_manifest(st, core.git_toplevel(Path(review["artifact"]).parent)) != rnd["refs"]


def scope_of(st: core.Store, review: dict, spec: Path) -> list:
  """The spec's scope rows (`spec_scope`), then one `("changed", <path>, 0, 0)` row per changed reference document
  (`reference_manifest`): a whole file, which has no lines (U75); a respec cycle's scope is its correction diff
  alone, with no reference document row (spec section 7.6)."""
  root = core.git_toplevel(spec.parent)
  if review.get("respec"):
    return spec_scope(st, review, spec)
  return spec_scope(st, review, spec) + [("changed", row["file"], 0, 0) for row in reference_manifest(st, root)]


def spec_scope(st: core.Store, review: dict, spec: Path) -> list:
  """The round's scope rows, `(changed|neighbour|whole, heading, start, end)`, from the current bytes: under
  `auto` (a review opened before U19 reads as `auto`) the sections `scope_sections` finds against the
  approved bytes; under `respec` (a `review open --respec R<n>` cycle) only the `changed` sections
  `scope_sections` finds against the latest approved bytes, without neighbours; a section list adds its
  headings as `changed`, without neighbours (a heading the bytes no longer hold is dropped). One `whole` row
  otherwise, its heading field the reason: `(whole)`, `(no
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
  rows = {row[2]: row for row in scope_sections(old, text)  # by start line: two sections may share a heading
          if form != "respec" or row[0] == "changed"}  # a respec cycle's remit: the diff's sections, no neighbours
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
  sha, and a respec cycle's once its R<n> is not open (applied, or withdrawn by a stopped unit); an integrate's by the handoff closing or changing (D1 (a)), or by a `## Units` amendment
  past the bytes its latest completed round reviewed (a cycle with no completed round stays); a plan or integrate
  cycle by a respec approval (U91, `respec_closed`): an approval entry whose `source_review` is the cycle's id and
  whose `handoff_id` is the cycle's, its `fix-design` finding resolved by the respec."""
  cycles = cycle_ids(st, kind, artifact)
  if not cycles:
    return None, False
  rid = cycles[-1]
  review = load_review(st, rid)
  closed = any(r["ruling"] in ("accept", "stop", "proceed") for r in review["rulings"]) or respec_closed(st, review, rid)
  if not closed and kind == "spec":
    approval = core.load_approval(st, Path(artifact))
    closed = bool(approval) and approval["review"] == rid and approval["sha256"] != current_sha(st, kind, artifact)
    if not closed and review.get("respec"):  # a respec cycle closes once its R<n> is no longer open: applied or withdrawn
      from superegm import respec as respecs
      handoff = (approval or {}).get("handoff_id")
      closed = not handoff or review["respec"] not in [r["id"] for r in respecs.open(st, handoff)]
  if not closed and kind == "integrate":
    state = core.load_state(st.root)
    amended = [e for e in core.load_approvals(st, Path(artifact))
               if e.get("kind") == "amend-units" and e.get("handoff_id") == review.get("handoff_id")]
    latest_sha = evaluate(st, review, None).latest_sha
    closed = bool(state.get("closed_at")) or ("handoff_id" in review and state.get("handoff_id") != review["handoff_id"]) \
        or bool(amended and latest_sha and amended[-1]["sha256"] != latest_sha)
  return review, closed


def respec_closed(st: core.Store, review: dict, rid: str) -> bool:
  """Whether a respec approval closed this plan or integrate cycle (U91): an approval entry of the cycle's own handoff
  (`handoff_id` equal: review ids are handoff-local) whose `source_review` is `rid`. Its `fix-design` finding is then
  resolved by the respec and the next review of the artifact opens a new cycle."""
  if review.get("kind") not in ("plan", "integrate"):
    return False
  from superegm import respec as respecs
  handoff = review.get("handoff_id") or st.handoff_id
  try:
    spec = Path(review["artifact"]) if review["kind"] == "integrate" else respecs.spec_of(st, handoff)
  except core.HandoffError:  # a handoff naming no spec has no approval to close it
    return False
  return any(e.get("source_review") == rid and e.get("handoff_id") == handoff for e in core.load_approvals(st, spec))


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


RESPEC_CAP = 2  # a respec cycle's cap, below `review.rounds` (spec section 7.6)
RESPEC_PANEL = ("design", "codebase-details")  # a respec cycle's panel, besides the Astra lane, narrowed by section 4.1


def respec_base(st: core.Store, kind: str, artifact: str, respec: str, reviewers: list, given) -> str:
  """`review open --respec R<n>`'s checks; returns the commit of the latest approval, the diff's base. Refused: a
  kind other than spec, a `--scope`, a reviewer outside `RESPEC_PANEL`, no approval, a voided latest approval, or
  R<n> not open in the latest approval's handoff."""
  if kind != "spec":
    raise core.HandoffError(f"review open: --respec is refused for kind {kind}")
  if given is not None:
    raise core.HandoffError("review open: --scope is refused with --respec")
  outside = [r for r in reviewers if r not in RESPEC_PANEL]
  if outside:
    raise core.HandoffError(f"review open: respec {respec}: {outside[0]} is not on a respec panel ({', '.join(RESPEC_PANEL)})")
  approval = core.load_approval(st, Path(artifact))
  if not approval:
    raise core.HandoffError(f"review open: respec {respec}: no approval")
  if approval.get("voided_by"):  # the line approve-spec --respec refuses with: no cycle runs against a voided handoff
    raise core.HandoffError(f"review open: respec {respec}: {approval.get('handoff_id')}: not the latest approval: "
                            "plan the rows in the latest handoff")
  from superegm import respec as respecs  # R ids are per handoff: open in the latest approval's handoff alone
  if respec not in [r["id"] for r in respecs.open(st, approval.get("handoff_id"))]:
    raise core.HandoffError(f"review open: respec {respec} is not open")
  return approval["commit"]


def respec_evidence(st: core.Store, review: dict) -> str:
  """A respec cycle's evidence: the diff from the latest approval's commit (`base`) to `HEAD`, then the text at `HEAD`
  of each section the diff changes; nothing else of the spec."""
  spec = Path(review["artifact"])
  root = core.git_toplevel(spec.parent)
  rel = spec.resolve().relative_to(root.resolve()).as_posix()
  old = core.run_git(["show", f"{review['base']}:{rel}"], root)
  new = core.run_git(["show", f"HEAD:{rel}"], root)
  out = [core.run_git(["diff", review["base"], "HEAD", "--", rel], root).rstrip("\n"), ""]
  lines = new.splitlines()
  for kind, heading, start, end in scope_sections(old, new):
    if kind == "changed":
      out += [f"--- {heading} ({start}-{end})", *lines[start - 1:end], ""]
  return "\n".join(out)


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
  if unknown:  # a repository reviewer: a loaded file whose kinds holds this review's kind (spec section 3.6)
    from superegm import reviewers as repository  # at call time: that module's import chain reaches this one
    try:
      loaded = repository.available(st, core.git_toplevel(Path.cwd()), kind, st.handoff_id, set(unknown))
    except core.HandoffError as error:
      raise core.HandoffError(f"review open: {error}") from None
    for rid in unknown:
      if rid not in loaded:
        raise core.HandoffError(f"review open: unknown reviewer {rid}")
      if kind not in loaded[rid]["kinds"]:
        raise core.HandoffError(f"review open: {rid} does not review {kind}")
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
  respec = getattr(args, "respec", None)  # read and checked before the resume, which resumes only its own cycle
  base = respec_base(st, kind, artifact, respec, reviewers, given) if respec else None
  latest, closed = latest_cycle(st, kind, artifact)
  if respec and latest and not closed and latest.get("respec") != respec:
    raise core.HandoffError(f"review open: respec {respec}: {review_id(st, kind, artifact, latest['cycle'])} is open")
  if not respec and latest and not closed and latest.get("respec"):  # resumed by `--respec R<n>` alone
    raise core.HandoffError(f"review open: {review_id(st, kind, artifact, latest['cycle'])} is a respec {latest['respec']} "
                            f"cycle: use --respec {latest['respec']}")
  if latest and not closed:  # a re-typed skill resumes the open cycle; a spec's panel may narrow, from the next round
    rid = review_id(st, kind, artifact, latest["cycle"])
    core.card_add(st, args.runcard, "produced", rid)
    core.journal(st, f"review open {rid} resumed under {args.runcard}")
    print(rid)
    if kind == "spec":
      nxt = max(round_numbers(st, rid), default=0) + 1
      narrowed, refused = narrow_panel(latest, nxt, reviewers)
      if narrowed:
        save_review(st, rid, latest)
        core.journal(st, f"review open {rid} panel {','.join(panel_at(latest, nxt))} from round {nxt} under {args.runcard}")
      print(f"panel {','.join(panel_at(latest, nxt))} from round {nxt}" + (f" (unchanged: {refused})" if refused else ""))
    return 0
  cap = RESPEC_CAP if respec else cap_at_open(args, st, kind, artifact)
  scope = ("respec" if respec else scope_form(st, artifact, given)) if kind == "spec" else None
  cycle = latest["cycle"] + 1 if latest else 1
  rid = review_id(st, kind, artifact, cycle)
  lane = seat_lane(kind, getattr(args, "astra", None), st.config.get("astra") or {})
  review = {"kind": kind, "artifact": artifact, "cycle": cycle, "handoff_id": st.handoff_id, "scope": scope,
            "reviewers": reviewers + (["astra"] if lane else []), "cap": cap,
            "runcard": args.runcard, "artifact_sha256": current_sha(st, kind, artifact) if kind == "plan" else args.sha256,
            "astra_incomplete": 0,
            "converged": "no", "converged_round": None, "rulings": [], **({"respec": respec, "base": base} if respec else {})}
  save_review(st, rid, review)
  core.card_add(st, args.runcard, "produced", rid)
  core.journal(st, f"review open {rid} panel {','.join(review['reviewers'])} under {args.runcard}")
  print(rid)
  return 0


def panel_at(review: dict, n: int) -> list[str]:
  """Round `n`'s panel: the last `panels` entry from a round at most `n`, else the cycle's `reviewers`."""
  entries = [p for p in review.get("panels") or [] if p["from_round"] <= n]
  return entries[-1]["reviewers"] if entries else review["reviewers"]


def narrow_panel(review: dict, nxt: int, given: list[str]) -> tuple[bool, str | None]:
  """A resume's `given` panel against round `nxt`'s: a proper subset (`design` first, checked by the caller)
  becomes a `panels` entry from `nxt`, the Astra lane kept when the panel has it. Returns `(narrowed, reason)`:
  an equal panel changes nothing and needs no reason; a given reviewer off the panel (wider or overlapping)
  changes nothing and names it. `review` is changed in memory only."""
  current = panel_at(review, nxt)
  names = [r for r in current if r != "astra"]
  off = [r for r in given if r not in names]
  if off:
    return False, f"{off[0]} is not on the panel"
  if set(given) == set(names):
    return False, None
  given = list(dict.fromkeys(given))  # a reviewer named twice is dispatched once
  entry = {"from_round": nxt, "reviewers": given + (["astra"] if "astra" in current else [])}
  panels = review.setdefault("panels", [])
  if panels and panels[-1]["from_round"] == nxt:  # narrowed twice before the round: the later wins
    panels.pop()
  panels.append(entry)
  return True, None


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
  """Prints the round's scope, `<changed|neighbour|whole> <start>-<end> <heading>` per spec section and
  `changed <path>` per changed reference document (U75); writes nothing."""
  st = core.store(core.git_toplevel(Path.cwd()))
  review = load_review(st, args.review)
  if review is None:
    raise core.HandoffError(f"review {args.review}: not opened")
  if review["kind"] != "spec":
    raise core.HandoffError(f"review scope: {args.review} is not a spec review")
  bind(args, review)
  for kind, heading, start, end in scope_of(st, review, Path(review["artifact"])):
    print(f"{kind} {heading}" if start == end == 0 else f"{kind} {start}-{end} {heading}")  # a reference document is a whole file
  if review.get("respec"):  # a respec cycle reviews its diff and the sections it touches alone (spec section 7.6)
    print(respec_evidence(st, review))
  return 0


# ---------------------------------------------------------------- record


def stored_manifest(st, rid: str, review: dict, n: int, reviewer: str, card: dict) -> list:
  """The `[{file, sha}]` stored for this record's reviewer lane, copied and never re-resolved: a spec review's from the
  round's `instructions-<n>-reviewers-<lane>.json`, any other kind's from the recording card; `[]` with no stored render
  and for the foreman's own and a thread's findings, which no section reached."""
  if reviewer == "foreman" or reviewer.startswith("external:"):
    return []
  lane = "astra" if reviewer == "astra" else "local"
  if review["kind"] == "spec":
    path = st.path("reviews", rid, f"instructions-{n}-reviewers-{lane}.json")
    return (json.loads(core.read_text(path)).get("manifest") or []) if path.exists() else []
  stored = ((card.get("instructions") or {}).get("reviewers") or {}).get(lane) or {}
  return list(stored.get("manifest") or [])


def stored_brief_exists(st, rid: str, n: int, reviewer: str) -> bool:
  """Whether a spec round holds a stored brief for this reviewer's lane; the foreman's and a thread's findings have none."""
  if reviewer == "foreman" or reviewer.startswith("external:"):
    return False
  return st.path("reviews", rid, f"instructions-{n}-reviewers-{'astra' if reviewer == 'astra' else 'local'}.json").exists()


def record_round(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  rid, n, reviewer = args.review, args.round, args.reviewer
  review = load_review(st, rid)
  if review is None:
    raise core.HandoffError(f"review {rid}: not opened")
  card = bind(args, review)
  proceed = last_proceed(review)
  if proceed and getattr(args, "threads", None) is None:  # head ingest's own call passes `threads`: it records still
    raise core.HandoffError(f"review {rid} proceeded by {proceed['id']}")
  kind, existing = review["kind"], load_round(st, rid, n)
  external = reviewer.startswith("external:")
  if reviewer == "foreman":  # the helper's own findings (section 11), outside the panel
    if kind != "head":
      raise core.HandoffError("review record: foreman is accepted on a head only")
  elif external:  # a PR thread's author (`review ingest`), outside the panel
    if kind not in ("head", "spec"):
      raise core.HandoffError(f"review record: {reviewer} is accepted on a head or a spec only")
  elif reviewer not in panel_at(review, n):  # the round's own panel: a narrowed one drops a reviewer from its round on
    raise core.HandoffError(f"review record: {reviewer} is not on the panel")
  if kind == "plan" and args.sha256:
    raise core.HandoffError("review record: --sha256 is refused for kind plan")
  sha = current_sha(st, kind, review["artifact"])
  if review.get("respec"):  # its evidence is HEAD's diff: the recorded sha must be of the same bytes
    spec = Path(review["artifact"])
    root = core.git_toplevel(spec.parent)
    from superegm import instructions  # at call time, as `reviewers` is: the raw blob, hashed as `current_sha` hashes
    head = instructions.blob(root, "HEAD", spec.resolve().relative_to(root.resolve()).as_posix())
    if head is None or hashlib.sha256(head).hexdigest() != sha:
      raise core.HandoffError(f"review record: respec {review['respec']}: {spec} differs from HEAD: commit the correction")
  if kind == "head" and args.sha256 is not None and not re.fullmatch(r"[0-9a-f]{40}", args.sha256):  # a head's bytes are its commit: the full sha, never a prefix or a digest
    raise core.HandoffError(f"review record: --sha256 on a head takes the full 40-hex commit sha, not {args.sha256!r}")
  if kind == "head":
    sha = args.sha256 or (existing["artifact_sha256"] if existing else review["artifact_sha256"] if n == 1 else None)
    if not sha:
      raise core.HandoffError(f"review record: --sha256 required for kind {kind}")
  if existing and existing["artifact_sha256"] != sha:
    raise core.HandoffError("review record: sha256 differs from the round's")
  if kind == "spec" and existing and refs_moved(st, review, existing):  # one round, one reference snapshot (U75)
    raise core.HandoffError("review record: reference documents differ from the round's")
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
  if kind == "spec" and not existing:  # the reference documents the round reviewed (U75): beside the spec's own sha, never in it
    rnd["refs"] = reference_manifest(st, core.git_toplevel(Path(review["artifact"]).parent))
  if kind == "spec" and "scope" not in rnd:  # the round's scope, stored by its first record, checked by every later one
    rows = [list(row) for row in scope_of(st, review, Path(review["artifact"]))]
    rnd.update({"scope": rows, "out_of_scope": [],
                "note": rows[0][1][1:-1] if rows and rows[0][0] == "whole" else None})
  refused = []
  if args.not_run and external:  # an ingest's record holds findings: a not-run would erase them
    raise core.HandoffError(f"review record: --not-run is refused for an external reviewer ({reviewer})")
  manifest = stored_manifest(st, rid, review, n, reviewer, card)
  lane = "astra" if reviewer == "astra" else "local"
  dropped = st.path("reviews", rid, f"instructions-{n}-reviewers-{lane}.dropped")  # marks a stale brief the check dropped (U75): no record follows until a render
  render = (f"render it again with `superegm instructions --spec {review['artifact']} --review {rid} --round {n} "
            f"--role reviewers --lane {lane} --runcard {args.runcard}`")
  if kind == "spec" and reviewer != "foreman" and not external and dropped.exists():
    if not stored_brief_exists(st, rid, n, reviewer):  # a retry or the lane's next reviewer would otherwise skip the check below
      raise core.HandoffError(f"review record: the reviewers' {lane} brief for round {n} was dropped as stale: {render}, the reviewers read it, then record")
    dropped.unlink()  # rendered again: the check below reads the new brief
  if kind == "spec" and rnd.get("refs") is not None and stored_brief_exists(st, rid, n, reviewer):  # U75: the panel read the reference bytes its stored brief listed; the round's `refs` are those
    read = {item["file"]: item.get("sha") for item in manifest}
    moved = [ref["file"] for ref in rnd["refs"] if ref["file"] in read and read[ref["file"]] != ref["sha"]]
    folders = tuple(e["dir"].rstrip("/") + "/" for e in st.config.get("instructions") or []
                    if isinstance(e, dict) and isinstance(e.get("dir"), str) and "reviewers" in (e.get("to") or []))  # the folders the brief lists: the entries addressed to the reviewers, never a builder-only folder
    unseen = [ref["file"] for ref in rnd["refs"] if ref["sha"] is not None and ref["file"] not in read and ref["file"].startswith(folders)]  # added after the render
    if moved or unseen:  # the stored brief is stale: drop it, so `instructions --spec` renders it again from HEAD and this round can still be recorded
      st.path("reviews", rid, f"instructions-{n}-reviewers-{lane}.json").unlink(missing_ok=True)
      core.atomic_write(dropped, "dropped\n")
      raise core.HandoffError("; ".join([f"review record: {path}: differs from the reviewers' brief" for path in moved]
                                        + [f"review record: {path}: not in the reviewers' brief" for path in unseen])
                              + f" (the stored brief is dropped: {render}, the reviewers read it, then record; a `dir` entry is listed once committed)")
  from superegm import reviewers as repository  # at call time: that module's import chain reaches this one
  try:  # a repository or overridden reviewer's record carries the persona it read; a built-in with no file's has none, and a not-run read none (U76)
    persona = None if args.not_run else repository.persona_of(st, review, rid, n, reviewer)
  except core.HandoffError as error:
    raise core.HandoffError(f"review record: {error}") from None
  if args.not_run:
    record = {"findings": [], "not_run": args.not_run, "isolation": None, "model": None, "effort": None,
              "instructions": manifest}
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
      artifact = Path(review["artifact"])
      spec_rel = artifact.resolve().relative_to(core.git_toplevel(artifact.parent).resolve()).as_posix()
      verdicts = [(finding, line, out_of_scope(rnd["scope"], spans, finding["location"], spec_rel, str(core.git_toplevel(artifact.parent)),
                                              respec=bool(review.get("respec")))) for finding, line in pairs]
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
              "effort": args.effort, "instructions": manifest}
  rnd["reviewers"][reviewer] = {**record, **({"persona": persona} if persona else {})}
  if reviewer == "astra" and args.not_run and not args.not_run.startswith(("not installed", "stopped")):
    review["astra_incomplete"] += 1
  rnd["what_ran"] = derive_what_ran(review, rnd, entry)
  core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
  prior = review.get("converged") or ""
  status = store_verdict(st, rid, review, rnd["runcard"])
  if kind == "head" and prior.startswith("by ruling ") and review["converged"] != prior \
      and getattr(args, "threads", None) is None:  # a lapsed accept's `clean` rewritten (`review ingest` rewrites its own)
    data = core.load_foreman(st, review["artifact"])
    posted = sorted((e for e in data["rounds"] if e.get("phase") == "posted"), key=lambda e: e["round"])
    if posted and rewrite_posted(posted[-1], lambda: status.code):
      core.save_foreman(st, review["artifact"], data)
  for fid, _, section in refused:
    where = ": no line number" if section == "none" else f" ({section})"
    core.journal(st, f"review record {rid} round {n} out of scope: {fid}{where} under {args.runcard}")
    print(f"record: {fid} out of scope ({section}): not recorded")
  core.journal(st, f"review record {rid} round {n} {reviewer} what_ran {rnd['what_ran']} under {args.runcard}")
  print(f"round {n} {reviewer} recorded, what_ran {rnd['what_ran']}")
  return 0


# ---------------------------------------------------------------- triage


def triage_undone(foreman: dict) -> bool:
  """The owner turned triage off for the unit: a recorded undo (`kind: undo`) in its `rulings[]`."""
  return any(r.get("kind") == "undo" for r in foreman.get("rulings") or [])


def owner_named(foreman: dict) -> set:
  """The fids an `owner: <ids>` outcome of any `rounds[]` entry names."""
  return {fid for e in foreman.get("rounds") or [] if str(e.get("outcome") or "").startswith("owner: ")
          for fid in e["outcome"][len("owner: "):].split(", ")}


def eligible_fids(st: core.Store, review: dict, rnd: dict) -> list[str]:
  """A head round's eligible mediums (section 5.2): a panel reviewer's unsettled medium that is not a regression,
  not a `test-delta:` finding and not named in an `owner:` line, in a unit whose triage no undo turned off."""
  foreman = core.load_foreman(st, review["artifact"])
  if review["kind"] != "head" or triage_undone(foreman):
    return []
  panel, named = panel_at(review, rnd["round"]), owner_named(foreman)
  return [f["id"] for reviewer in panel for f in (rnd["reviewers"].get(reviewer) or {}).get("findings") or []
          if f["severity"] == "medium" and f["regression"] == "no" and f["disposition"] is None
          and not f["claim"].startswith("test-delta:") and f["id"] not in named]


def triage(args) -> int:
  match = re.search(r"(?:^|-)head-(U\d+)-c\d+$", args.review)
  if match and not args.runcard:  # `--eligible` runs without a card: the handoff is the one filing the review's unit
    args.unit = match.group(1)
  st = core.store(core.git_toplevel(Path.cwd()), args)
  review = load_review(st, args.review)
  if review is None:
    raise core.HandoffError(f"review {args.review}: not opened")
  rnd = load_round(st, args.review, args.round)
  if rnd is None:
    raise Refusal(f"triage: round {args.round} not recorded")
  if args.eligible:
    for fid in eligible_fids(st, review, rnd):
      print(fid)
    return 0
  bind(args, review)
  patterns = frozen_triage(args, st)
  if patterns is None or triage_undone(core.load_foreman(st, review["artifact"])):
    raise Refusal("triage: triage is off for this unit")
  if rnd.get("triage"):
    raise Refusal(f"triage: round {args.round} already triaged")
  eligible = eligible_fids(st, review, rnd)
  root = core.git_toplevel(Path.cwd())
  lines = [line for line in core.read_text(Path(args.file)).splitlines() if line.strip()]
  fields = {}
  for line in lines:
    fid, values = triage_line(line, root, rnd["artifact_sha256"])
    if fid not in eligible:
      raise Refusal(f"triage: {fid} is not an eligible medium of round {args.round}: {line}")
    if fid in fields:
      raise Refusal(f"triage: a second line for {fid}: {line}")
    fields[fid] = values
  if missing := [fid for fid in eligible if fid not in fields]:
    raise Refusal(f"triage: no line for {', '.join(missing)}")
  deferred = {}
  for fid, values in fields.items():
    n = next((i for i, pattern in enumerate(patterns, 1) if pattern_matches(pattern, values)), None)
    if n is not None:
      deferred[fid] = n
  for reviewer in rnd["reviewers"].values():
    for finding in reviewer.get("findings") or []:
      if finding["id"] in deferred:
        finding["disposition"] = f"deferred: triage {deferred[finding['id']]}"
  rnd["triage"] = {"runcard": args.runcard, "isolation": args.isolation, "model": args.model, "effort": args.effort,
                   "lines": lines, "findings": fields}
  core.atomic_write(st.path("reviews", args.review, f"round-{args.round}.json"), rnd)
  store_verdict(st, args.review, review, rnd["runcard"])
  for fid, n in deferred.items():
    core.journal(st, f"review triage {args.review} round {args.round} {fid} deferred: triage {n} under {args.runcard}")
    print(f"{fid} deferred: triage {n}")
  return 0


def rewrite_posted(entry: dict, code, rnd: dict | None = None) -> str | None:
  """A posted `rounds[]` entry whose outcome no longer holds, rewritten in place: a `clean` outcome, or (given its
  round `rnd`) an `owner:` word whose remainder is no longer owner-only, becomes `revise`, or `cap-reached` at the cap
  (`code()`, the review's status exit, read only then), with `rewritten_from` the old outcome. Returns the new word."""
  outcome = str(entry.get("outcome") or "")
  if outcome != "clean" and not (rnd is not None and outcome.startswith("owner:") and not owner_only_fids(rnd)):
    return None
  word = {3: "revise", 2: "cap-reached"}.get(code())
  if word:
    entry.update({"outcome": word, "rewritten_from": outcome})
  return word


def undo_outcome(st: core.Store, rid: str, runcard: str) -> None:
  """After the owner's undo (section 5.2): the verdict re-derived (an accept on the round lapses), and the unit's
  latest posted entry rewritten as ingest rewrites it (`rewrite_posted`): `clean`, or an `owner:` word whose remainder
  is no longer owner-only, becomes `revise` or `cap-reached` at the cap."""
  review = load_review(st, rid)
  status = store_verdict(st, rid, review, runcard)
  unit = review["artifact"]
  data = core.load_foreman(st, unit)
  posted = sorted((e for e in data["rounds"] if e.get("phase") == "posted"), key=lambda e: e["round"])
  if not posted:
    return
  was = posted[-1].get("outcome")
  if word := rewrite_posted(posted[-1], lambda: status.code, load_round(st, rid, posted[-1]["round"]) or {"reviewers": {}}):
    core.save_foreman(st, unit, data)
    core.journal(st, f"{unit} round {posted[-1]['round']} {was} rewritten {word} by the undo under {runcard}")


def deferred_of(rnd: dict) -> list[dict]:
  """The round's findings deferred by triage, in record order."""
  return [f for f in findings_of(rnd) if str(f.get("disposition") or "").startswith("deferred: triage ")]


def write_followups(st: core.Store, unit: str, rnd: dict) -> None:
  """A posted round's deferred mediums as `followups[]` rows (section 5.2): once per fid and round, so a recovery's
  second count writes none."""
  rows = [{"fid": f["id"], "round": rnd["round"], "claim": f["claim"], "triage": rnd["triage"]["findings"][f["id"]],
           "pattern": int(f["disposition"].rsplit(" ", 1)[1])} for f in deferred_of(rnd)]
  if not rows:
    return
  data = core.load_foreman(st, unit)
  have = {(r["fid"], r["round"]) for r in data.get("followups") or []}
  new = [r for r in rows if (r["fid"], r["round"]) not in have]
  if new:
    data["followups"] = (data.get("followups") or []) + new
    core.save_foreman(st, unit, data)


TRIAGE_LINE = re.compile(r"^(?P<fid>\S+) \| reach: (?P<reach>\S+) \| later: (?P<later>\S+) \| critical: (?P<critical>\S+)"
                         r" \| verified: (?P<verified>(?P<word>\S+)(?: (?P<rest>.+))?)$")


def triage_line(line: str, root: Path, head: str) -> tuple[str, dict]:
  """One reply line `<fid> | reach: <v> | later: <v> | critical: <v> | verified: confirmed <file:line>|refuted <reason>`:
  its fid and the four fields, `verified` the text from its first word to the end of the line. Refused: a missing or
  misplaced field, an unknown value, a `confirmed` whose `<file:line>` does not exist at the round's head."""
  from superegm.approve_spec import TRIAGE_FIELDS  # approve_spec imports this module
  match = TRIAGE_LINE.match(line.strip())
  if not match:
    raise Refusal(f"triage: expected `<fid> | reach: <v> | later: <v> | critical: <v> | verified: <v>`: {line}")
  values = {key: match.group(key) for key in ("reach", "later", "critical")}
  for key, value in [*values.items(), ("verified", match.group("word"))]:
    if value not in TRIAGE_FIELDS[key]:
      raise Refusal(f"triage: unknown value {value} for {key}: {line}")
  rest = match.group("rest") or ""
  if not rest:
    raise Refusal(f"triage: verified: {match.group('word')} without its {'file:line' if match.group('word') == 'confirmed' else 'reason'}: {line}")
  if match.group("word") == "confirmed":
    cite = re.fullmatch(r"(?P<path>\S+):(?P<n>\d+)", rest)
    text = core.run_git(["cat-file", "-p", f"{head}:{cite.group('path')}"], root, check=False) if cite else ""
    if not cite or not 1 <= int(cite.group("n")) <= len(text.splitlines()):
      raise Refusal(f"triage: {rest} does not exist at the round's head {head[:7]}: {line}")
  return match.group("fid"), {**values, "verified": match.group("verified")}


def pattern_matches(pattern: dict, values: dict) -> bool:
  """A frozen pattern matches a triage when every field it names holds its value (`verified` by its first word); a
  `refuted` triage matches only a pattern naming `verified: refuted` (section 5.2)."""
  if values["verified"].split(" ", 1)[0] == "refuted" and pattern.get("verified") != "refuted":
    return False
  return all((values[key].split(" ", 1)[0] if key == "verified" else values[key]) == value for key, value in pattern.items())


def frozen_triage(args, st: core.Store):
  """The triage patterns frozen in the handoff's latest approval entry (section 5.1), or None: triage off."""
  spec = core.handoff_spec(args, st)
  entries = core.load_approvals(st, Path(spec)) if spec else []
  own = [e for e in entries if st.handoff_id and e.get("handoff_id") == st.handoff_id]
  return own[-1].get("triage") if own else None


# ---------------------------------------------------------------- settle


def blocking(finding: dict) -> bool:
  return finding["severity"] in ("high", "medium")


def locate_finding(st: core.Store, rid: str, fid: str):
  """`(round number, round, reviewer, finding)` of `fid` in the newest recorded round holding it (a carried copy),
  completed or not."""
  for n in reversed(round_numbers(st, rid)):
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
  word = apply_settle(st, rid, review, card, args, checked)
  for fid, disposition, _, _ in checked:
    print(f"{fid} {disposition}")
  if word:
    print(word)
  return 0


def apply_settle(st: core.Store, rid: str, review: dict, card: dict, args, checked: list) -> str | None:
  """The settle `review settle` runs once its checks pass, and `decision rule` runs on a point-1 ruling (U103): each
  `(fid, disposition, note, round)` of `checked` takes its disposition and its `ruling` (`owner`, `judges:<panel>`, or none),
  the verdict is stored, a head's clean outcome is written, or the `owner:`/`revise`/`cap-reached` word of a remainder
  that is not clean; the word rewritten, if any. `args` carries `owner`, `judges` and `runcard`."""
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
    if review["kind"] == "head" and args.judges and card["mode"] != "leavemealone" and blocking(finding) and disposition in ("contested", "declined"):
      core.journal(st, f"Ruling (judges {args.judges}, contest): {review['artifact']} {fid} {disposition}")  # U88
      continue
    core.journal(st, f"review settle {rid} {fid} {disposition} by {finding['ruling'] or 'the elephant'}"
                 + (f" copied to {', '.join(copies)}" if copies else "") + f" under {args.runcard}")
  status = store_verdict(st, rid, review, runcard)
  word = None
  if review["kind"] == "head" and status.code == 0:
    write_head_outcome(st, review, runcard)
  elif review["kind"] == "head":
    word = write_owner_outcome(st, rid, review, runcard, status.code)
  return word


def check_ci_finding(reviewer: str, finding: dict) -> None:
  """D2 (a): `collect` records the CI finding afresh each round, so no one settles it (`check_settle`, and `decision rule` on
  an overrule of it, U103)."""
  if reviewer == "foreman" and finding["location"] == "ci":
    raise core.HandoffError("review settle: the CI finding is settled by no one")


def locate_in_round(st: core.Store, rid: str, n: int, fid: str):
  """`(n, round, reviewer, finding)` of `fid` in round `n` alone (a finding id carries across rounds: U103's `decision rule`
  settles in the round its decision's source names)."""
  rnd = load_round(st, rid, n)
  for reviewer, record in ((rnd or {}).get("reviewers") or {}).items():
    for finding in record["findings"]:
      if finding["id"] == fid:
        return n, rnd, reviewer, finding
  raise core.HandoffError(f"review settle: no finding {fid} in round {n}")


def check_settle(st: core.Store, rid: str, review: dict, card: dict, args, fid: str, disposition: str, source_round: int | None = None) -> int:
  """The per-finding refusals of `review settle`; the round number of `fid` when none applies: the newest round holding it,
  or `source_round`, the round a `decision rule` ruling's source names, when given."""
  n, rnd, reviewer, finding = locate_finding(st, rid, fid) if source_round is None else locate_in_round(st, rid, source_round, fid)
  if review["kind"] == "head" and disposition == "fix-design":
    raise core.HandoffError("review settle: fix-design is refused on a head")
  if review["kind"] == "integrate" and disposition == "fix-design" and frozen(st):  # its spec is the latest handoff's now
    raise core.HandoffError("review settle: fix-design is refused on a frozen handoff's integrate: settle it escalated")
  check_ci_finding(reviewer, finding)
  if disposition == "fixed" and rnd["artifact_sha256"] == current_sha(st, review["kind"], review["artifact"]) \
      and not refs_moved(st, review, rnd):  # a spec round's changed reference document counts as changed bytes (U75)
    raise core.HandoffError("review settle: fixed needs changed bytes")  # a head's current bytes are unknown: never
  if finding["claim"].startswith("test-delta:") and not args.owner:  # U25: the owner's alone, in either mode
    raise core.HandoffError(f"review settle: {fid} is the owner's alone: --owner required")
  if blocking(finding) and disposition in ("contested", "declined"):
    if card["mode"] == "leavemealone" and not args.judges:
      if not (args.owner and getattr(args, "posted", None)):
        raise core.HandoffError(f"review settle: {fid} is {finding['severity']}: --judges required in leavemealone-mode")
      verify_owner_ruling(st.config, finding, args.posted, delta_claim(st, rid, finding["claim"]),
                          unrecorded=getattr(args, "unrecorded", False))
    if card["mode"] != "leavemealone" and not args.owner and not (args.judges and review["kind"] == "head"):  # U88: a head's contest goes to the panel first
      raise core.HandoffError(f"review settle: {fid} is {finding['severity']}: --owner required in normal mode")
    if args.judges and review["kind"] == "head":  # either mode: a contest settles by a panel that overruled it
      check_panel_overrules(st, args.judges, fid, rid, n)
  return n


def check_panel_overrules(st: core.Store, panel: str, fid: str, rid: str, n: int) -> None:
  """U88: a head contest settles by `--judges <panel>` only when `judges/<panel>/` was opened for this review and round (its id
  is `<rid>-r<n>-<6 hex>`, as `judges.panel_id` makes it from `question_name`) and its `verdict.json` converged on `finding
  overruled` for the question that asks `fid` (the panel's `question.md` names the finding at the head of its `## Q<n>` line);
  the other questions of the panel, converged or not, do not matter."""
  from superegm import judges
  if not re.fullmatch(re.escape(f"{rid}-r{n}-") + "[0-9a-f]{6}", panel):
    raise core.HandoffError(f"review settle: {fid}: judges {panel} was not opened for {rid} round {n}")
  folder = st.path("judges", panel, "verdict.json").parent
  if not (folder / "verdict.json").is_file():
    raise core.HandoffError(f"review settle: {fid}: judges {panel} has no verdict")
  verdict = json.loads(core.read_text(folder / "verdict.json"))
  asked = next((q for q in judges.parse_questions(core.read_text(folder / "question.md")) if q["text"].split(" ")[0] == fid), None)
  answer = (verdict["questions"].get(asked["id"]) if asked else None) or {}
  if asked and not answer.get("converged"):
    raise core.HandoffError(f"review settle: {fid}: judges {panel} has not converged")
  if not (asked and asked["options"].get(answer.get("option"), "").startswith("finding overruled")):
    raise core.HandoffError(f"review settle: {fid}: judges {panel} did not overrule {fid}")


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


def verify_owner_ruling(config: dict, finding: dict, comment_id: str, original: str = None, unrecorded: bool = False) -> None:
  """In leavemealone the owner's word still counts, by hand (1.1.3; U22 reads such comments itself): one GitHub
  read of the comment, by a `config.owners` login, carrying a ruling `ruling_of` reads: `<fid> finding overruled`,
  or `<fid> allowed` on a `test-delta:` finding, or `test-delta <file> allowed` on a `test-delta:` finding of that
  file or on a contest's copy whose `original` claim (`delta_claim`'s) is one (U25). `unrecorded` (`decision rule`'s
  read before the comment's first record, U103): an edited comment is refused, as on `decision rule`'s own read."""
  from superegm.decision import ruling_of  # inside: `decision` imports `review`
  fid, claim = finding["id"], finding["claim"]
  original = claim if original is None else original
  comment = core.gh_json(["api", f"repos/{config['repo']}/issues/comments/{comment_id}"]) or {}
  if unrecorded and edited_comment(comment):
    raise core.HandoffError("review settle: ruling comment edited: post a new one")
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
          if "by" in finding:  # a proceed's settlement (`by: owner`, `ruling: R<n>`)
            twin["by"] = finding["by"]
          if "note" in finding:
            twin["note"] = finding["note"]
        core.atomic_write(st.path("reviews", other_rid, f"round-{m}.json"), other)
        if other_rid not in copies:
          copies.append(other_rid)
  return copies


def write_head_outcome(st: core.Store, review: dict, runcard: str, outcome: str = "clean") -> None:
  """`outcome: clean` on the unit's latest posted round and `<unit> awaiting merge` in the journal:
  whichever of `review post` (U10), `review settle` and a head's accept below the cap (`review rule`, which a head's
  fifth point runs, U35) leaves `review status` at 0 writes it. A head's fifth point writes `revise` as the round's
  word instead (its `revise`, or a rerun accept refused on a moved head), with no journal line."""
  unit = review["artifact"]
  data = core.load_foreman(st, unit)
  posted = sorted((e for e in data["rounds"] if e.get("phase") == "posted"), key=lambda e: e["round"])
  if not posted:
    return
  posted[-1]["outcome"] = outcome
  core.save_foreman(st, unit, data)
  if outcome == "clean":
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
  moved: bool = False          # the latest completed round's bytes are no longer the artifact's, or a spec round's `refs` are no longer HEAD's reference manifest (never on a head)
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
    rounds.append(rnd | {"what_ran": derive_what_ran(review, rnd, entry)} | ({"merge": True} if entry.get("merge") else {}))
  return rounds


def stall_cards(st: core.Store, review: dict, runcard: str) -> set:
  """The card set the stall rule reads (spec section 11.2): the given card alone when it records no `driver_card`;
  a tick's session's card reads every `wave` card of the handoff (with `driver.chain` on, also every top-level card
  of the other chain phases, U44), typed included, opened at or after the last posted round's `posted_at` (every
  one when none is posted), every card that ran a round after that post (an earlier session's rounds since its own
  post), and itself, so a tick's session is no fresh retry."""
  path = st.path("runcards", runcard) if runcard else None
  card = json.loads(core.read_text(path)) if path and path.is_file() else {}
  if not card.get("driver_card"):
    return {runcard}
  rounds = core.load_foreman(st, review["artifact"])["rounds"] if review["kind"] == "head" else []
  last = max((i for i, r in enumerate(rounds) if r.get("phase") == "posted" and r.get("posted_at")), default=None)
  since = rounds[last]["posted_at"] if last is not None else None
  cards = {runcard} | {r["runcard"] for r in (rounds[last + 1:] if last is not None else []) if r.get("runcard")}
  chain = core.chain_on(st.config)
  for other in sorted(st.card_dir(runcard).glob("*.json" if chain else "wave-*.json")):  # by the chain (U44)
    data = json.loads(core.read_text(other))
    top = data.get("skill") == "wave" or (chain and data.get("skill") in core.CHAIN_PHASES and not data.get("parent"))
    if top and (since is None or (data.get("opened_at") or "") >= since):
      cards.add(other.stem)
  return cards


def evaluate(st: core.Store, review: dict, runcard: str) -> Status:
  """The one convergence rule (section 5), the cap and the stall rule (section 8); exit order 4, 0, 5, 2, 3."""
  rid = review_id(st, review["kind"], review["artifact"], review["cycle"])
  rounds = rounds_of(st, rid, review)
  completed = [r for r in rounds if r["what_ran"] == "completed"]
  latest = completed[-1] if completed else None
  rulings = [r["ruling"] for r in review["rulings"]]
  fix_design = any(f["disposition"] == "fix-design" for r in rounds for f in findings_of(r)) \
      and not respec_closed(st, review, rid)  # a respec approval resolved the finding: its exit 4 ends (U91)
  clean = latest is not None and not any(blocking(f) and f["disposition"] is None for f in findings_of(latest))
  regressions = regressions_of(latest) if latest else 0
  accept = next((r for r in reversed(review["rulings"]) if r["ruling"] == "accept"), None)
  if accept and early_accept_lapsed(review, accept, rounds, rulings):
    accept = None
  latest_sha = latest["artifact_sha256"] if latest else None
  moved = latest is not None and review["kind"] != "head" \
      and (latest_sha != current_sha(st, review["kind"], review["artifact"]) or refs_moved(st, review, latest))
  converged, converged_round = "no", None
  if fix_design:
    pass
  elif accept:
    converged, converged_round = f"by ruling {accept['id']}", review["converged_round"]
  elif clean and not regressions and not moved:
    converged, converged_round = "yes", latest["round"]
  counted = [r for r in completed if not r.get("merge")]  # a merge round is not counted toward the cap (spec section 6.1)
  cap = "stop" in rulings or len(counted) >= cap_of(review) + rulings.count("continue")
  cards = stall_cards(st, review, runcard)
  stalled = len(rounds) >= 2 and all(r["what_ran"] != "completed" and r.get("runcard") in cards for r in rounds[-2:])
  sha = next((r["artifact_sha256"] for r in rounds if r["round"] == converged_round), None)
  code = 4 if fix_design else 0 if converged != "no" else 5 if stalled else 2 if cap else 3
  proceed = last_proceed(review)
  if proceed:  # the owner's go-ahead is checked first (spec section 4.2): at the latest recorded round, its pinned sha
    converged, converged_round = f"by proceed {proceed['id']}", max((r["round"] for r in rounds), default=0)
    sha, code = proceed.get("sha256"), 0
  line = (f"round {latest['round'] if latest else 0}: {'clean' if clean else 'not clean'}, regressions {regressions}, "
          f"converged {converged}, cap {'yes' if cap else 'no'}, stalled {'yes' if stalled else 'no'}, sha256 {sha or 'none'}")
  trend = (f"rounds: {' -> '.join(str(len(findings_of(r))) for r in rounds)} "
           f"(regressions {', '.join(str(regressions_of(r)) for r in rounds)})") if rounds else "rounds: none"
  fixed = moved and clean and not regressions and not (fix_design or accept or proceed)
  return Status(code, line, trend, converged, converged_round, sha, moved, latest_sha, fixed)


def acceptable(st: core.Store, review: dict, runcard: str) -> tuple[list[str], int, int]:
  """The accept below the cap's predicate, beside the cap's: what blocks it on the latest completed round
  (`kind integrate`, then each unsettled `high <fid>`, `regression <fid>`, `external <fid>`, `undone <fid>` (a
  medium the owner's undo returned to the round, section 5.2), then each pending
  `decision <id>` of a head's unit naming this review at any point but 5), with that round's unsettled medium
  and low counts. A later round, complete or not, holding an unsettled high or medium (a set finding review-plan
  records into a unit's next round) bars it as `early_accept_lapsed` lapses one: its `high`, `regression` and
  `external` fids, then each other unsettled `medium <fid>`."""
  blockers = ["kind integrate"] if review["kind"] == "integrate" else []
  rid = review_id(st, review["kind"], review["artifact"], review["cycle"])
  rounds = rounds_of(st, rid, review)
  completed = [r for r in rounds if r["what_ran"] == "completed"]
  unsettled = [f for f in findings_of(completed[-1]) if f["disposition"] is None] if completed else []
  blockers += finding_blockers(completed[-1]) if completed else []
  for rnd in (r for r in rounds if completed and r["round"] > completed[-1]["round"]):
    named = finding_blockers(rnd)
    blockers += named + [f"medium {f['id']}" for f in findings_of(rnd) if f["severity"] == "medium"
                         and f["disposition"] is None and not any(b.endswith(f" {f['id']}") for b in named)]
  if review["kind"] == "head":
    blockers += [f"decision {d['id']}" for d in open_decisions(st, review["artifact"])
                 if d.get("point") != 5 and names_review(d, rid)]
  return blockers, sum(f["severity"] == "medium" for f in unsettled), sum(f["severity"] == "low" for f in unsettled)


def finding_blockers(rnd: dict) -> list[str]:
  """A round's findings that bar an accept below the cap: each unsettled `high <fid>`, each `regression <fid>` the
  landed `regressions_of` counts (a blocking `regression: yes` whatever its disposition, an unsettled high listed
  under `high` alone), each unsettled `external <fid>` medium, then each unsettled `undone <fid>`: a finding the
  owner's undo returned to the round (section 5.2), which lapses an accept given on it and bars a new one."""
  found = findings_of(rnd)
  high = [f for f in found if f["severity"] == "high" and f["disposition"] is None]
  regression = [f for f in found if blocking(f) and f["regression"] == "yes" and f not in high]
  external = [f for f in found if f["severity"] == "medium" and f["disposition"] is None
              and f not in regression and f["id"].startswith("external:")]
  # a medium the owner's undo returned to the round (section 5.2) lapses an accept given on it, as a new blocker does
  undone = [f for f in found if f.get("undone_by") and blocking(f) and f["disposition"] is None
            and f not in high + regression + external]
  return ([f"high {f['id']}" for f in high] + [f"regression {f['id']}" for f in regression]
          + [f"external {f['id']}" for f in external] + [f"undone {f['id']}" for f in undone])


def early_accept_lapsed(review: dict, accept: dict, rounds: list[dict], rulings: list[str]) -> bool:
  """An accept given below the cap holds its round alone: it lapses once a later round completes, once a later
  round, complete or not, holds an unsettled high or medium (a set finding review-plan records into an accepted
  unit's next round), or once a finding recorded into its round since (an ingested external one, a set finding)
  bars the accept; the cap's accept stands.
  The stored `converged: by ruling <id>` is the accept's mark: once a verdict overwrote it (the lapse, `store_verdict`)
  the accept never comes back, neither at the cap nor as the verdict of a later clean round."""
  if review.get("converged") != f"by ruling {accept['id']}":
    return True
  accepted = review.get("converged_round")
  if accepted is None:
    return False
  completed = [r for r in rounds if r["what_ran"] == "completed"]
  upto = [r for r in completed if r["round"] <= accepted and not r.get("merge")]
  if len(upto) >= cap_of(review) + rulings.count("continue"):
    return False
  rnd = next((r for r in completed if r["round"] == accepted), None)
  later = [f for r in rounds if r["round"] > accepted for f in findings_of(r)]
  return rnd is None or any(r["round"] > accepted for r in completed) or bool(finding_blockers(rnd)) \
      or any(blocking(f) and f["disposition"] is None for f in later)


def open_decisions(st: core.Store, unit: str) -> list[dict]:
  """The unit's pending decisions (`report.pending_decisions`), and a point-1 decision while a contested finding of
  its round has no ruling yet (point 1 takes one ruling per finding, `decision rule`)."""
  from superegm.report import pending_decisions
  data = core.load_foreman(st, unit)
  pending = pending_decisions(data)
  return pending + [d for d in data.get("decisions") or [] if d.get("point") == 1 and d not in pending
                    and point_one_open(st, data, d)]


def point_one_open(st: core.Store, foreman: dict, decision: dict) -> bool:
  """A point-1 decision some contested fid of its `review <id> round <n>` round names no ruling of."""
  words = (decision.get("source") or "").split()
  if len(words) != 4 or words[0] != "review" or words[2] != "round" or not words[3].isdigit():
    return False
  if any(r.get("decision") == decision["id"] and r.get("ruling") == "proceed" for r in foreman.get("rulings") or []):
    return False  # a proceed closes the whole decision, as `redesign` does
  rnd = load_round(st, words[1], int(words[3])) or {}
  fids = contested_fids(rnd) or [c["fid"] for c in rnd.get("builder_contested") or []]
  ruled = {r["ruling"].partition(" — ")[0].strip().split(" ")[0]
           for r in foreman.get("rulings") or [] if r.get("decision") == decision["id"]}
  return any(fid not in ruled for fid in fids)


def names_review(decision: dict, rid: str) -> bool:
  """A decision whose `source` is `review <id> round <n>` or `review <id> cap`, this review's."""
  words = (decision.get("source") or "").split()
  return len(words) >= 3 and words[:2] == ["review", rid] and words[2] in ("round", "cap")


def store_verdict(st: core.Store, rid: str, review: dict, runcard: str) -> Status:
  """Re-derive `converged` and `converged_round` into `review.json` after a record, a settle or a head round's post.
  A verdict replacing an accept's mark (a later round, a `fix-design`) is the accept's lapse, journaled
  `review <id> R<n> accept lapsed` (integrate quotes no lapsed accept)."""
  status = evaluate(st, review, runcard)
  prior = review.get("converged") or ""
  review["converged"], review["converged_round"] = status.converged, status.converged_round
  save_review(st, rid, review)
  if prior.startswith("by ruling ") and review["converged"] != prior:
    core.journal(st, f"review {rid} {prior.removeprefix('by ruling ')} accept lapsed under {runcard}")
  return status


def status_review(args) -> int:
  """Prints the state line, the trend and, on an acceptable round, its `acceptable:` line; writes nothing; the exit code is the verdict."""
  st = core.store(core.git_toplevel(Path.cwd()))
  review = load_review(st, args.review)
  if review is None:
    print(f"review {args.review}: not opened")
    return 3
  card = bind(args, review)
  status = evaluate(st, review, card.get("parent") or args.runcard)
  print(status.line)
  print(status.trend)
  if status.code in (3, 5) and not status.moved and not head_moved(st, review, status.latest_sha):  # at the reviewed bytes
    blockers, mediums, lows = acceptable(st, review, args.runcard)
    if not blockers and mediums:
      print(f"acceptable: yes ({mediums} medium, {lows} low)")
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
                    "root": c.get("body") or "", "body": "\n\n".join([c.get("body") or "", *replies.get(c["id"], [])]), "path": c.get("path"),
                    "line": c.get("line"), "commit_id": c.get("commit_id"), "review_body": False,
                    "created_at": c.get("created_at")})
  for r in reviews:
    body = r.get("body") or ""
    if POST_HEADER_RE.search(body):
      continue
    if (not body.strip() or r["id"] in inline or r.get("state") == "APPROVED" or r["id"] in skip):
      continue
    threads.append({"id": r["id"], "login": login(r), "bot": login(r).endswith("[bot]"), "root": body, "body": body, "path": None,
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


CLAIM_LIMIT = 1_000  # characters of a thread's root kept in its claim (a longer one keeps 999 and `…`)
NO_TEXT = "(no text outside hidden markup)"  # the claim of a root with nothing left after its HTML comments go
CUT_LIMIT = 200  # characters of a claim when its ingest comment would pass `COMMENT_LIMIT` (a longer one keeps 199 and `…`)


def cut_claim(claim: str) -> str:
  """The claim cut to `CUT_LIMIT` characters (199 and `…`) when it is longer, else whole."""
  return claim[:CUT_LIMIT - 1] + "…" if len(claim) > CUT_LIMIT else claim


def root_text(thread: dict) -> str:
  """The thread's root comment without its HTML comments: `<!--` to the next `-->`, across lines, or to the
  end of the text when none follows (GitHub hides that too). A thread built by hand reads its `body`."""
  return re.sub(r"<!--.*?(?:-->|\Z)", "", thread.get("root", thread.get("body")) or "", flags=re.S)


def thread_line(reviewer: str, rnd: int, n: int, thread: dict, severity: str, config: dict) -> str:
  """The thread's finding line: `<reviewer>-<round>-<n> | <severity> | <file:line or PR> at <commit7> |
  regression: no | <the root comment on one line, masked, 1,000 chars>`."""
  where = thread.get("path") or "PR"
  if thread.get("path") and thread.get("line") is not None:
    where += f":{thread['line']}"
  where = f"{mask(where, config)} at {(thread.get('commit_id') or '')[:7]}"
  claim = mask(" ".join(root_text(thread).split()), config) or NO_TEXT
  if len(claim) > CLAIM_LIMIT:
    claim = claim[:CLAIM_LIMIT - 1] + "…"
  return f"{reviewer}-{rnd}-{n} | {severity} | {where} | regression: no | {claim}"


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
  first = next((line for line in root_text(thread).splitlines() if line.strip()), "").strip().casefold()
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
  and `CI: <verdict>`, a carried finding (`carried_from`, posted once already) left out; no run card, no model names."""
  lines = [mention] if mention else []
  lines += [header(round_json["round"], head), ""]
  for record in (round_json.get("reviewers") or {}).values():
    lines += [f"{f['id']} | {f['severity']} | {f['location']} | regression: {f['regression']} | {f['claim']}"
              for f in record["findings"] if "carried_from" not in f]
  deferred = deferred_of(round_json) if round_json.get("reviewers") else []
  if deferred:  # section 5.2: a deferred medium no longer blocks; the builder may still fix it
    lines += ["", "**Deferred by triage**"] + [f"{f['id']} | {f['disposition']}" for f in deferred]
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
      verdict = json.loads(core.read_text(folder / "ci.json"))["verdict"]
      render = lambda: render_comment(
        {"round": n, "reviewers": {ext: {"findings": parse_findings("\n".join(ls), ext, n)} for ext, ls in postable.items()}},
        head, verdict, config.get("fix_request_mention") or None)
      body = render()
      if len(body.encode("utf-8")) > COMMENT_LIMIT:  # every claim of the ingest cut to 200 characters, stored and posted alike
        cut = lambda line: " | ".join([*line.split(" | ", 4)[:4], cut_claim(line.split(" | ", 4)[4])])
        lines = {ext: [cut(line) for line in ls] for ext, ls in lines.items()}
        postable = {ext: [cut(line) for line in ls] for ext, ls in postable.items()}
        body = render()
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
          if claim != finding["claim"] and finding["claim"] != cut_claim(claim):  # a stored 200-character cut stays cut
            finding["claim"], changed = claim, True
    if changed:
      core.atomic_write(st.path("reviews", rid, f"round-{m}.json"), saved)
  data = core.load_foreman(st, unit)
  missing = sorted(recorded - set(data.get("ingested") or []))
  saved_entry = next(e for e in data["rounds"] if e["round"] == latest["round"])
  # the mirror of `review post`'s `clean` write; an external high or medium beside the owner's own leaves an
  # `owner:` remainder mixed: `revise`, or `cap-reached` at the cap
  word = rewrite_posted(saved_entry, lambda: status_code(rid, wave),
                        load_round(st, rid, latest["round"]) or {"reviewers": {}})
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
  store_verdict(st, review_id, review, runcard)  # the round now completed: an early accept it lapses is journaled
  word = outcome_word(status_code(review_id, runcard), contested_fids(rnd or {}), owner_only_fids(rnd or {}))
  saved["outcome"] = word
  entry.update(saved)
  core.save_foreman(st, unit, data)
  if rnd and rnd.get("triage"):  # the round posts: its deferrals become follow-up rows, once per fid and round
    write_followups(st, unit, rnd)
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
  if args.ruling == "proceed":  # the owner's go-ahead ends the review whatever its state (spec section 4.2)
    return rule_proceed(st, rid, review, card, args)
  rulings = [r["ruling"] for r in review["rulings"]]
  if "stop" in rulings:
    raise core.HandoffError("review rule: cycle stopped")
  if args.ruling == "continue" and "continue" in rulings:
    raise core.HandoffError("review rule: continue already ruled this cycle")
  status = evaluate(st, review, card.get("parent") or args.runcard)
  early = args.ruling == "accept" and status.code != 2
  if early:
    counts = refuse_early_accept(st, rid, review, status, args)
  elif args.ruling == "accept" and review["kind"] == "head":
    raise core.HandoffError("review rule: accept is refused on a head")
  elif status.code != 2:
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
  if early:
    core.journal(st, f"review {rid} accepted before the cap by the owner ({counts[0]} medium, {counts[1]} low)")
    if review["kind"] == "head":  # the round's `clean` and its awaiting-merge line, however the accept was typed
      write_head_outcome(st, review, args.runcard)
  print(f"ruling {ruling['id']} {args.ruling}")
  return 0


def rule_proceed(st: core.Store, rid: str, review: dict, card: dict, args) -> int:
  """`review rule --ruling proceed --owner` (spec section 4.2): the owner's alone, typed with `--reason`, or on a head
  `--posted <comment id>`, the owner's `**Ruling:** proceed — <reason>` on the unit's issue, consumed once."""
  reason, posted = getattr(args, "reason", None), getattr(args, "posted", None)
  if getattr(args, "judges", None) or not args.owner:
    raise core.HandoffError("review rule: proceed is the owner's")
  if bool(reason) == bool(posted):
    raise core.HandoffError("review rule: proceed takes --reason or --posted")
  head = review["kind"] == "head"
  if posted and not head:
    raise core.HandoffError("review rule: --posted proceeds a head alone")
  ruling = {"id": f"R{len(review['rulings']) + 1}", "ruling": "proceed", "by": "owner", "at": core.now_iso(),
            "reason": reason}
  if not head:
    ruling["sha256"] = current_sha(st, review["kind"], review["artifact"])
    if review["kind"] == "spec":  # U75: the reference manifest the proceed pins, `approve-spec` compares against it
      ruling["refs"] = reference_manifest(st, core.git_toplevel(Path(review["artifact"]).parent))
    review["rulings"].append(ruling)
    save_review(st, rid, review)
    return proceeded(st, rid, review, ruling, card, args)
  unit = review["artifact"]
  foreman = core.load_foreman(st, unit)
  if foreman.get("stopped"):
    raise core.HandoffError(f"review rule: {unit} is stopped")
  state = core.load_state(st.root)
  number = state["units"][unit]["number"]
  pinned = pinned_head(st, rid, review, state)
  comment, by = None, "owner"
  if posted:
    recorded = next((e for e in foreman.get("proceeds") or [] if e.get("posted") == f"comment {posted}"), None)
    if recorded and (recorded.get("review"), recorded.get("head")) == (rid, pinned):
      print(json.dumps(recorded, sort_keys=True))  # the same comment, review and head: the recorded entry, nothing written
      return 0
    if recorded or posted_anywhere(st, f"comment {posted}"):
      raise core.HandoffError(f"review rule: comment {posted} already ruled")
    comment, found = posted_comment(st, posted, number)
    ruling["reason"], by = found.reason, found.login
  ruling["sha256"] = pinned
  launches = st.path("launches", unit)
  launched = json.loads(core.read_text(launches))["launches"] if launches.is_file() else []
  foreman.setdefault("proceeds", []).append(
    {"ruling": ruling["id"], "review": rid, "posted": f"comment {posted}" if posted else None,
     "posted_at": comment.get("updated_at") if comment else None, "issue": number, "head": pinned,
     "launch": max((e.get("round") or 0 for e in launched), default=None), "by": by, "reason": ruling["reason"]})
  for decision in [d for d in open_decisions(st, unit) if names_review(d, rid)]:  # a cap or point-5 question, answered
    foreman["rulings"].append({"decision": decision["id"], "ruling": "proceed", "by": "owner",
                               "reason": ruling["reason"], "review": ruling["id"]})
  review["rulings"].append(ruling)
  save_review(st, rid, review)
  core.save_foreman(st, unit, foreman)
  return proceeded(st, rid, review, ruling, card, args)


def last_proceed(review: dict):
  """The cycle's latest `proceed` ruling, or None."""
  return next((r for r in reversed(review.get("rulings") or []) if r["ruling"] == "proceed"), None)


def proceeded(st: core.Store, rid: str, review: dict, ruling: dict, card: dict, args) -> int:
  """Once the ruling is recorded: every unsettled finding of every round settled `declined` by the owner under the
  ruling (a spec's external copies too), the verdict re-derived, a head's clean outcome, the journal lines."""
  runcard = card.get("parent") or args.runcard
  k = h = 0
  for n in round_numbers(st, rid):
    rnd = load_round(st, rid, n)
    settled = []
    for reviewer, record in rnd["reviewers"].items():
      for finding in record["findings"]:
        if finding["disposition"] is None:
          finding.update(disposition="declined", by="owner", ruling=ruling["id"])
          k, h = k + 1, h + (finding["severity"] == "high")
          settled.append((reviewer, finding))
    if settled:
      core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
    for reviewer, finding in settled:
      if review["kind"] == "spec" and reviewer.startswith("external:"):
        settle_external_copies(st, review, reviewer, finding)
  status = store_verdict(st, rid, review, runcard)
  if review["kind"] == "head" and status.code == 0:
    write_head_outcome(st, review, runcard)
  core.journal(st, f"review rule {rid} {ruling['id']} proceed by owner under {runcard}")
  core.journal(st, f"review {rid} proceeded by the owner: {k} findings accepted ({h} high)")
  print(f"ruling {ruling['id']} proceed")
  return 0


def pinned_head(st: core.Store, rid: str, review: dict, state: dict):
  """A head's bytes at a proceed: the pull request's saved head (`status --wait`'s snapshot), else the latest round's."""
  from superegm.report import unit_view
  saved = unit_view(state, review["artifact"]).get("head")
  rounds = rounds_of(st, rid, review)
  return saved or (rounds[-1]["artifact_sha256"] if rounds else None)


def posted_anywhere(st: core.Store, posted: str) -> bool:
  """A `proceeds[]` or `rulings[]` entry of any unit's foreman file names the comment (`posted: "comment <id>"`)."""
  for path in sorted(st.path("foreman", "U00").parent.glob("*.json")):
    data = json.loads(core.read_text(path))
    if any(e.get("posted") == posted for e in (data.get("proceeds") or []) + (data.get("rulings") or [])):
      return True
  return False


def edited_comment(comment: dict) -> bool:
  """A comment whose `updated_at` and `created_at` are both present and differ: edited since it was posted, so a ruling
  never read from it (an edited ruling comment is never recorded, `docs/reference/invariants.md`; U103). One carrying no
  `created_at` is not read as edited."""
  return bool(comment.get("updated_at") and comment.get("created_at") and comment["updated_at"] != comment["created_at"])


def posted_comment(st: core.Store, comment_id, number: int):
  """The owner's proceed comment as `review settle` checks a posted ruling: one GitHub read, refused when edited (U103), its author in
  `config.owners`, `ruling_of` of kind `proceed`, on the unit's issue (`issue_url`, as `decision.verify_posted`)."""
  from superegm.decision import ruling_of  # inside: `decision` imports `review`
  owners = st.config.get("owners") or []
  comment = core.gh_json(["api", f"repos/{st.config['repo']}/issues/comments/{comment_id}"]) or {}
  if edited_comment(comment):
    raise core.HandoffError("review rule: ruling comment edited: post a new one")
  author = (comment.get("user") or {}).get("login")
  if author not in owners:
    raise core.HandoffError(f"review rule: comment {comment_id} is by {author}, not a login in config.owners")
  found = ruling_of({**comment, "id": comment.get("id") or comment_id}, owners)
  if found is None or found.kind != "proceed":
    raise core.HandoffError(f"review rule: comment {comment_id} does not rule proceed")
  if not (comment.get("issue_url") or "").endswith(f"/issues/{number}"):
    raise core.HandoffError(f"review rule: comment {comment_id} is not on issue #{number}")
  return comment, found


def refuse_early_accept(st: core.Store, rid: str, review: dict, status: Status, args) -> tuple[int, int]:
  """An accept below the cap is the owner's alone, on an acceptable round with a medium unsettled, and on a head
  it names the unit's pending point-5 decision; the round's unsettled medium and low counts when honoured."""
  if args.judges:
    raise core.HandoffError("review rule: accept refused: judges")
  if status.code in (0, 4):
    raise core.HandoffError("review rule: not at the cap")
  blockers, mediums, lows = acceptable(st, review, args.runcard)
  if blockers:
    raise core.HandoffError("review rule: accept refused: " + ", ".join(blockers))
  if not mediums:
    raise core.HandoffError("review rule: accept refused: no medium to accept")
  if review["kind"] == "head":
    fifth = [d["id"] for d in open_decisions(st, review["artifact"]) if d.get("point") == 5 and names_review(d, rid)]
    if not getattr(args, "decision", None):
      raise core.HandoffError(f"review rule: accept on a head needs --decision {fifth[0] if fifth else 'none'}")
    if args.decision not in fifth:
      raise core.HandoffError(f"review rule: --decision {args.decision} names no pending point-5 decision of {review['artifact']}")
    refuse_moved_head(st, rid, review, args.decision)
  return mediums, lows


def refuse_moved_head(st: core.Store, rid: str, review: dict, qid: str) -> None:
  """A head's accept binds the round its point-5 decision names, at the head that round reviewed: the decision's
  round is the latest completed one, and the decision's `head`, the pull request's saved head and its head read
  afresh from GitHub are its bytes."""
  decision = next(d for d in core.load_foreman(st, review["artifact"])["decisions"] if d["id"] == qid)
  completed = [r for r in rounds_of(st, rid, review) if r["what_ran"] == "completed"]
  words = (decision.get("source") or "").split()
  reviewed = completed[-1]["artifact_sha256"] if completed else None
  if (len(words) != 4 or words[2] != "round" or not completed or words[3] != str(completed[-1]["round"])
      or decision.get("head") != reviewed or head_moved(st, review, reviewed, fresh=True)):
    raise core.HandoffError("review rule: the reviewed head moved: revise")


def head_moved(st: core.Store, review: dict, reviewed: str | None, fresh: bool = False) -> bool:
  """A head review whose pull request's saved head (`status --wait`'s snapshot) is not the reviewed one, or with
  `fresh`, whose head read from GitHub now is not; never on another kind."""
  from superegm.report import unit_view
  if review["kind"] != "head":
    return False
  saved = unit_view(core.load_state(st.root), review["artifact"])
  if saved["head"] != reviewed:
    return True
  if not fresh:
    return False
  number = saved["pr"]["number"] if isinstance(saved["pr"], dict) else saved["pr"]
  return number is None or core.read_pr(st.config["repo"], int(number))["head"] != reviewed
