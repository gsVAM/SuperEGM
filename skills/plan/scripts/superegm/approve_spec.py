# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_approve` as the approve-spec module (U03); the section 8 form: a converged
# review, the `Units` check, the commit by path, `--void` and `--amend-units` (U04); the escalated pairs recorded (U16);
# the approval history, one handoff per opening, the latest-entry rule and the branch check (U20); the spec PR's
# ingest once before the refusals, the refusal of an unsettled external finding, an external finding's carried copies
# as one escalated pair discharged by its latest copy alone, and a re-approval of the same cycle reading that cycle
# again and keeping the replaced entry's unnamed pairs (U26); `--amend-units` typed by hand opens and closes its own
# card, the branch check reading `spec_blob` (U32); the `Rounds:` line or the live `review.rounds` frozen as the entry's `rounds`, and `FROZEN_FIELDS` copied by `--amend-units`, and a hand-written prior approval read as `since` 0 (U36); the triage section parsed, refused with its line and frozen as `triage` (U39); the run mode frozen as the entry's `mode` (U43); the `instructions` list frozen with each file's blob sha and its verified store copy, and the changed files printed (U37); an opening approval refused over a partly filed handoff, and the last filing restored over an unapplied dry run, and `--void` without `--review` on a handoff with no `state.json` (U53); a `dir` entry's documents validated, frozen by blob sha with their raw copies (U74); a proceeded cycle's unsettled external findings no refusal, its bytes checked against the proceed's pinned sha (U57); the reviewer files frozen as the entry's `reviewers` with their store copies and the changed ones printed (U76); the reference-document manifest at `HEAD` (merge base to `HEAD`, never the working tree) refused when it differs from the converged round's, or the proceed ruling's (U75); `--respec R<n>` and its `--dry-run`: the refusals (no approval to correct, not the latest approval, not in this branch, not open, not converged, a merged overlap without a follow-up row, a changed frozen field), `respec/R<n>.json` and the comment files, then the `respec` entry copying the frozen fields (U85).

"""superegm approve-spec: record the owner's approval of a converged spec (spec section 8)."""

import argparse
import json
from pathlib import Path
import re

import superegm as core
from superegm import close, instructions, reviewers, runcard
from superegm.review import Refusal, evaluate, findings_of, ingest_pr, last_proceed, latest_cycle, live_rounds, load_review, load_round, reference_manifest, review_id, round_numbers, rounds_of, valid_rounds

WRITES = frozenset(["approvals", "handoffs", "state", "reviews", "runcards", "instructions", "reviewers", "file"])  # the store kinds this subcommand writes
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SKILLS = frozenset(["review-spec", "review-plan", "integrate", "approve-spec"])  # the skills whose card this subcommand accepts
CONFIG = ".superegm/config.json"
FROZEN_FIELDS = ["rounds", "triage", "mode", "instructions", "reviewers"]  # the entry fields frozen at an approval, which `--amend-units` copies where the extended entry has them (U36, U37, U39, U43, U76)
ANY_H2 = re.compile(r"^ {0,3}##[ \t]+\S")  # an H2 as review.py reads one: up to three spaces of indent, outside a fence
TRIAGE_FIELDS = {"reach": ("external", "agent", "config", "forged"), "later": ("easy", "migration", "version"),
                 "critical": ("yes", "no"), "verified": ("confirmed", "refuted")}  # a pattern's fields and their values (section 5.1)
UNITS_H2 = re.compile(r"^## (?:\d+\.?\s+)?Units\s*$")


def register(subparsers):
  p = core.add_parser(subparsers, "approve-spec", "record the owner's approval of a converged spec")
  p.add_argument("--spec", dest="design", required=True)
  p.add_argument("--yes", action="store_true", help="the owner answered Approve")
  p.add_argument("--leavemealone", action="store_true", help="the converged record is the approval")
  p.add_argument("--void", action="store_true",
                 help="void the approval after a fix-design finding (--review), or, with no --review, the owner's void "
                      "of an approval whose handoff has no state.json; typed without --runcard it opens and closes "
                      "its own approve-spec-<6 hex>-<n> card")
  p.add_argument("--review", help="with --void: the review holding the fix-design finding")
  p.add_argument("--amend-units", dest="amend_units", action="store_true",
                 help="re-approve rows appended to ## Units without a review round; typed without "
                      "--runcard it opens and closes its own approve-spec-<6 hex>-<n> card")
  p.add_argument("--respec", help="R<n>: approve the converged correction of respec R<n> (spec section 7.6)")
  p.add_argument("--dry-run", dest="dry_run", action="store_true",
                 help="with --respec: print the touched units and merged_review of the working tree, write nothing")
  p.set_defaults(run=run, writes=WRITES)


def handoff_slug(stem: str) -> str:
  return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")[:20].rstrip("-")


def units_is_last_h2(text: str) -> bool:
  """The spec's last H2, after any numeric prefix, is `Units` (section 5)."""
  h2s = [line for line in text.splitlines() if line.startswith("## ")]
  return bool(h2s) and bool(UNITS_H2.match(h2s[-1]))


def handoff_state(st: core.Store, hid: str) -> dict:
  """The `state.json` of handoff `hid`: its directory's, or the flat one in a legacy store."""
  path = core.handoff_store(st, hid).path("state")
  return json.loads(core.read_text(path)) if path.is_file() else {}


def files_a_unit(state: dict) -> bool:
  return any((record or {}).get("number") for record in (state.get("units") or {}).values())


def incomplete_filing(state: dict) -> bool:
  """A handoff with a `filings[]` entry is partly filed (U53) when its last entry has no complete, problem-free `verify`
  receipt for its own `sha256` (not `confirmed_sha256`: a later dry run never applied is no partial filing), or a unit
  in `state.units` has no issue `number`; one with no `filings[]` entry is never partly filed."""
  filings = state.get("filings") or []
  if not filings:
    return False
  receipt = state.get("verify") or {}
  if not (receipt.get("complete") and receipt.get("sha256") == filings[-1].get("sha256") and not receipt.get("problems")):
    return True
  return any(not (record or {}).get("number") for record in (state.get("units") or {}).values())


def discard_unapplied_dry_run(st: core.Store, hid: str) -> None:
  """U53: an approval opening a new handoff over a filed one restores the older handoff's `confirmed.sha256`,
  `confirmed.writes` and `confirmed_sha256` from its last `filings[]` entry (its `repo` and the rest of `confirmed`
  kept), so a later dry run never applied cannot leave its receipt failing `require_receipt`; a handoff with a
  `confirmed` list and no `filings[]` entry is left untouched."""
  state = handoff_state(st, hid)
  filings = state.get("filings") or []
  if not filings or state.get("confirmed_sha256") == filings[-1].get("sha256"):
    return
  discarded, last = state.get("confirmed_sha256") or "", filings[-1]
  state["confirmed"] = {**(state.get("confirmed") or {}), "sha256": last["sha256"], "writes": last["writes"]}
  state["confirmed_sha256"] = last["sha256"]
  older = core.handoff_store(st, hid)
  core.atomic_write(older.path("state"), state)
  core.journal(older, f"dry run {discarded[:12]} discarded")


def unplanned_latest(st: core.Store, spec: Path) -> bool:
  """U53: the spec has an approval whose handoff has no `state.json`, nothing planned or filed: the one handoff the
  owner voids without a review."""
  entries = core.load_approvals(st, spec)
  hid = entries[-1].get("handoff_id") if entries else None
  return bool(hid) and not core.handoff_store(st, hid).path("state").is_file()


def handoff_id_for(st: core.Store, sha: str, stem: str, entries: list) -> tuple:
  """(handoff id, kind) of a new approval (spec section 7): the last entry's id, `after-void`, when that
  entry is voided and its handoff's `state.json` files a unit; else a fresh `opening`."""
  last = entries[-1] if entries else None
  if last and last.get("voided_by") and last.get("handoff_id") and files_a_unit(handoff_state(st, last["handoff_id"])):
    return last["handoff_id"], "after-void"
  return f"{handoff_slug(stem)}-{sha[:6]}", "opening"


def append_entry(st: core.Store, spec: Path, entry: dict) -> Path:
  """Append `entry` to the spec's approval history (a 1.1 record read as its first entry)."""
  path = st.path("approvals", core.spec_slug(spec))
  core.atomic_write(path, {"path": str(spec), "entries": core.load_approvals(st, spec) + [entry]})
  return path


def write_handoff_file(st: core.Store, handoff_id: str, spec: Path, opened_at) -> None:
  """`handoffs/<id>.json` at an opening, or the first time an approval touches a legacy handoff (its
  `opened_at` unknown, null); an existing file is left as it is (spec section 7)."""
  path = st.path("handoffs", handoff_id)
  if not path.is_file():
    core.atomic_write(path, {"id": handoff_id, "spec": str(spec), "opened_at": opened_at, "closed_at": None})


def write_entries(st: core.Store, spec: Path, entries: list) -> None:
  core.atomic_write(st.path("approvals", core.spec_slug(spec)), {"path": str(spec), "entries": entries})


def entry_of(sha, commit, runcard, review, handoff_id, kind, escalated, frozen=None) -> dict:
  """An approval entry; `frozen` holds the frozen fields (`FROZEN_FIELDS`) it carries, none for a field it lacks."""
  return {"sha256": sha, "commit": commit, "runcard": runcard, "review": review, "approved_at": core.now_iso(),
          "handoff_id": handoff_id, "kind": kind, "voided_by": None, "escalated": escalated, **(frozen or {})}


def cycle_of(review_id: str | None) -> int:
  """The cycle a review id ends in (`-c<n>`); 0 for a hand-written approval's reference, which has no such suffix."""
  match = re.search(r"-c([0-9]+)$", review_id or "", re.ASCII)
  return int(match.group(1)) if match else 0


def rounds_line(text: str) -> int | None:
  """The value of the one `Rounds: <n>` line before the spec's first H2, `n` 1-10; None without one. A second such
  line, or a value that is not 1-10, is refused with the line; a `Rounds:` line after the first H2 is prose (§4). A
  line inside a fenced block is neither: it is no `Rounds:` line, and a fenced `## ` is no H2. The line starts at
  column 0; an indented ` Rounds:` is prose."""
  found, fence = None, None  # the open fence's (character, run length), as review.py's `sections` reads one
  for line in text.splitlines():
    if fence:
      if re.match(rf"^ {{0,3}}{fence[0]}{{{fence[1]},}}\s*$", line):
        fence = None
      continue
    if (opener := core.FENCE_RE.match(line)) and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
      fence = (opener.group(1)[0], len(opener.group(1)))
      continue
    if ANY_H2.match(line):
      break
    if line.startswith("Rounds:"):
      if found is not None:
        raise core.HandoffError(f"approve-spec: a second Rounds line before the first H2: {line}")
      value = line.removeprefix("Rounds:").strip()
      if not (value.isascii() and value.isdigit() and valid_rounds(int(value))):
        raise core.HandoffError(f"approve-spec: {line} is not an integer 1-10")
      found = int(value)
  return found


def triage_section(lines: list[str]) -> tuple[int, list[tuple[str, bool]]] | None:
  """The triage section of a spec's `lines` (section 5.1): the index of its heading and its lines to the next H2 as
  `(line, fenced)`, a fence's own lines and the lines inside it `fenced`; None when no H2 outside a fenced
  block is exactly `Triage`."""
  fence, start, body = None, None, []  # the open fence's (character, run length), as `rounds_line` reads one
  for number, line in enumerate(lines):
    fenced = fence is not None
    if fence:
      if re.match(rf"^ {{0,3}}{fence[0]}{{{fence[1]},}}\s*$", line):
        fence = None
    elif (opener := core.FENCE_RE.match(line)) and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
      fence, fenced = (opener.group(1)[0], len(opener.group(1))), True
    elif ANY_H2.match(line):
      if start is not None:
        break
      if line.strip().removeprefix("##").strip() == "Triage":
        start = number
      continue
    if start is not None:
      body.append((line, fenced))
  return None if start is None else (start, body)


def triage_refusal(line: str, reason: str) -> core.HandoffError:
  return core.HandoffError(f"approve-spec: {line}: {reason}")


def triage_pattern(line: str) -> dict:
  """The `{field: value}` pairs of one `- ` line of the triage run; the line at fault refuses an empty pattern, a pair
  that is no `field: value`, an unknown field or value, and a field named twice."""
  pattern = {}
  if not line[2:].strip():
    raise triage_refusal(line, "an empty pattern")
  for pair in line[2:].split(", "):
    field, sep, value = pair.strip().partition(": ")
    if not sep:
      raise triage_refusal(line, f"`{pair.strip()}` is not `field: value`")
    if field not in TRIAGE_FIELDS:
      raise triage_refusal(line, f"unknown field {field}: one of {', '.join(TRIAGE_FIELDS)}")
    if field in pattern:
      raise triage_refusal(line, f"field {field} repeated in one pattern")
    if value not in TRIAGE_FIELDS[field]:
      raise triage_refusal(line, f"unknown value {value} for {field}: one of {', '.join(TRIAGE_FIELDS[field])}")
    pattern[field] = value
  return pattern


def triage_patterns(text: str) -> list[dict] | None:
  """The patterns of the spec's triage section (section 5.1), in section order; None without the section (the first
  H2 outside a fenced block whose text is exactly `Triage`, wherever it stands). The section holds one `Unblock:` line and the run of `- ` lines
  directly after it, each `field: value` pairs separated by `, `; any other line is prose. Refused with the line at
  fault: a bad pattern (`triage_pattern`), a second `Unblock:` line, a section with no `Unblock:` line (the heading is
  the line) or an `Unblock:` line with no pattern."""
  lines = text.splitlines()
  section = triage_section(lines)
  if section is None:
    return None
  patterns, state, unblock = [], "before", ""  # before the `Unblock:` line, in the run after it, past the run's end
  for line, fenced in section[1]:
    if not fenced and line.rstrip() == "Unblock:":
      if state != "before":
        raise triage_refusal(line, "a second Unblock: line")
      state, unblock = "run", line
    elif state == "run":
      if fenced or not line.startswith("- "):
        state = "past"
      else:
        patterns.append(triage_pattern(line))
  if state == "before":
    raise triage_refusal(lines[section[0]], "no Unblock: line")
  if not patterns:
    raise triage_refusal(unblock, "no pattern after Unblock:")
  return patterns


def units_section(text: str) -> str:
  """The spec from its last `## Units` heading to the end; empty without one."""
  lines = text.splitlines(keepends=True)
  starts = [i for i, line in enumerate(lines) if UNITS_H2.match(line)]
  return "".join(lines[starts[-1]:]) if starts else ""


def escalated_pairs(st: core.Store, spec: Path, since: int) -> list:
  """Every `escalated` finding of the spec's review cycles above `since`, as `<review id>:<finding id>`
  in round order, less the pairs the spec's `## Units` section names (D2 (a)). One finding is one pair: an
  external finding's carried copies (U26: the same reviewer, id and claim in later rounds or cycles) are one
  finding, named by its latest copy and discharged by a Units mention of that copy alone (the pair recorded and
  the one `graph` discharges)."""
  named, found, cycle = units_section(core.read_text(spec)), {}, since + 1
  while load_review(st, rid := review_id(st, "spec", str(spec), cycle)) is not None:
    for n in round_numbers(st, rid):
      for reviewer, record in load_round(st, rid, n)["reviewers"].items():
        for f in record["findings"]:
          if f["disposition"] == "escalated":
            pair = f"{rid}:{f['id']}"
            key = (reviewer, f["id"], f["claim"]) if reviewer.startswith("external:") else pair
            found[key] = found.pop(key, []) + [pair]
    cycle += 1
  return [pairs[-1] for pairs in found.values() if pairs[-1] not in named]


def before_units(text: str) -> str:
  """The text up to and including the last `## … Units` line (the whole text when there is none)."""
  lines = text.splitlines(keepends=True)
  last = max((i for i, line in enumerate(lines) if UNITS_H2.match(line)), default=len(lines))
  return "".join(lines[:last + 1])


def require_branch_holds(st: core.Store, repo_root: Path, rel: str, entry: dict) -> None:
  """Refuse a branch that never folded the history's last entry: no commit of it holds that entry's bytes."""
  if core.spec_blob(repo_root, rel, entry["sha256"]) is None:
    raise core.HandoffError(f"approve-spec: fold {st.config['base']} first: approval {entry['sha256'][:7]} is not in this branch")


def commit_by_path(repo_root: Path, paths: list[str], message: str, trailer: str) -> str:
  """Add and commit `paths` alone, ignoring other changes in the tree, `trailer` (when set) after a
  blank line; the commit may be empty."""
  core.run_git(["add", "--", *paths], repo_root)
  core.run_git(["commit", "--allow-empty", "-q", "-m", message, *(["-m", trailer] if trailer else []), "--", *paths], repo_root)
  return core.run_git(["rev-parse", "HEAD"], repo_root).strip()


def freeze(root: Path, ref: str, listed: list, at: str | None = None) -> list:
  """`listed` with each file's 12-hex blob sha and text at `ref`: `[{file, to, sha, text}]`, and for a `dir` entry
  `{dir, to, files: [{file, sha, text}]}`; a file absent there (named `at`, else `ref`), over `instructions.LIMIT` bytes
  or not UTF-8 is refused, naming it (a folder's documents by `instructions.documents`)."""
  frozen = []
  for item in listed:
    if "dir" in item:  # a folder's documents, each frozen as a file is, under the entry
      files = [{"file": name, "sha": instructions.blob_sha(data), "text": data.decode("utf-8")}
               for name, data in instructions.documents(root, ref, item, at)]
      frozen.append({"dir": item["dir"], "to": list(item["to"]), "files": files})
      continue
    data = instructions.blob(root, ref, item["file"])
    if data is None:
      raise core.HandoffError(f"instructions: {item['file']} is absent at {at or ref}")
    if instructions.mode(root, ref, item["file"]) not in ("100644", "100755"):  # a symlink's blob is its target path
      raise core.HandoffError(f"instructions: {item['file']} is not a regular file at {at or ref}")
    if len(data) > instructions.LIMIT:
      raise core.HandoffError(f"instructions: {item['file']} is {len(data)} bytes, over {instructions.LIMIT}")
    try:
      text = data.decode("utf-8")
    except UnicodeDecodeError:
      raise core.HandoffError(f"instructions: {item['file']} is not UTF-8") from None
    frozen.append({"file": item["file"], "to": list(item["to"]), "sha": instructions.blob_sha(data), "text": text})
  return frozen


def write_copy(st: core.Store, item: dict, raw: bool = False) -> None:
  """`instructions/<sha>.json` (`file`, `sha`, `text`), the frozen bytes that outlive the approval commit; a copy
  already there that does not verify is rewritten. With `raw` (a reference document), the bytes themselves also as
  `instructions/<sha>.md`, the copy an agent reads, rewritten likewise."""
  try:
    read_copy(st, item["file"], item["sha"])
  except core.HandoffError:
    core.atomic_write(st.path("instructions", item["sha"]), {k: item[k] for k in ("file", "sha", "text")})
  if raw:
    try:
      read_raw(st, item["file"], item["sha"])
    except core.HandoffError:
      core.atomic_write(raw_path(st, item["sha"]), item["text"].encode("utf-8"))


def raw_path(st: core.Store, sha: str) -> Path:
  """The raw copy of a reference document: `instructions/<sha>.md`, beside its `.json`."""
  return st.path("instructions", sha).with_suffix(".md")


def read_raw(st: core.Store, file: str, sha: str) -> bytes:
  """The raw bytes of reference document `file` frozen at `sha`, from `instructions/<sha>.md`; a copy missing, or whose
  blob sha differs, is refused, naming the file."""
  path = raw_path(st, sha)
  try:
    data = path.read_bytes()
  except OSError:
    data = None
  if data is None or instructions.blob_sha(data) != sha:
    raise core.HandoffError(f"instructions: {file}: the store copy {path.name} does not verify against blob sha {sha}")
  return data


def read_copy(st: core.Store, file: str, sha: str) -> str:
  """The text of `file` frozen at `sha`, from its store copy; a copy missing, or whose blob sha differs (edited
  after approval), is refused, naming the file. The copy is named by its bytes alone, so files of the same bytes
  (two of one list, or one renamed between approvals) share it, whichever `file` it records."""
  path = st.path("instructions", sha)
  try:
    copy = json.loads(core.read_text(path))
    text = copy["text"]
    good = instructions.blob_sha(text.encode("utf-8")) == sha
  except (OSError, ValueError, KeyError, TypeError, AttributeError):
    good = False
  if not good:
    raise core.HandoffError(f"instructions: {file}: the store copy {path.name} does not verify against blob sha {sha}")
  return text


def entry_item(item: dict) -> dict:
  """A frozen item as the approval entry holds it: `{file, to, sha}`, or `{dir, to, files: [{file, sha}]}` for a folder."""
  if "dir" in item:
    return {"dir": item["dir"], "to": item["to"], "files": [{k: f[k] for k in ("file", "sha")} for f in item["files"]]}
  return {k: item[k] for k in ("file", "to", "sha")}


def spec_pr(repo: str, branch: str) -> int | None:
  """The open PR whose head is `branch` (the elephant's spec PR, spec section 8), or None: none means nothing to read."""
  try:
    prs = json.loads(core.gh(["pr", "list", "-R", repo, "--head", branch, "--state", "open", "--limit", "1000",
                              "--json", "number,headRefOid"]) or "[]")
  except core.GhError as error:
    raise core.HandoffError(f"approve-spec: {error}") from None
  return prs[0]["number"] if prs else None


def run(args):
  spec = Path(args.design).expanduser().resolve()
  if not spec.is_file():
    raise core.HandoffError(f"approve-spec: spec {spec} does not exist")
  # a dry run writes nothing only on the respec route, and a respec is no void or amendment: each refused by name
  if args.dry_run and not args.respec:
    raise core.HandoffError("approve-spec: --dry-run needs --respec R<n>")
  for flag, given in (("--void", args.void), ("--amend-units", args.amend_units)):
    if args.respec and given:
      raise core.HandoffError(f"approve-spec: --respec is refused with {flag}")
  root = core.git_toplevel(spec)
  st = core.store(root)
  owner_void = args.void and not args.review
  if owner_void and not unplanned_latest(st, spec):  # U53: before any card
    raise core.HandoffError("approve-spec: --void requires --review")
  if not ((args.amend_units or owner_void) and not args.runcard):
    return approve(args, st, spec, root, core.require_runcard(args, SKILLS))
  # U32, U53: `--amend-units`, and the owner's `--void`, typed outside a skill open and close their own card (spec section 12)
  args.runcard = core.open_runcard(st, "approve-spec", str(spec))
  try:
    return approve(args, st, spec, root, core.require_runcard(args, SKILLS))
  finally:
    runcard.run(argparse.Namespace(action="close", id=args.runcard, note=None))


def reviewed_manifest(st: core.Store, rid: str, review: dict, status) -> list | None:
  """The reference manifest the approval must match (U75): the latest `proceed` ruling's `refs` on a proceeded cycle
  (round 0 included), else the converged round's; None when the record has no `refs` (written before U75)."""
  proceed = last_proceed(review)
  if proceed is not None:
    return proceed.get("refs")
  if status.converged_round is None:
    return None
  return load_round(st, rid, status.converged_round).get("refs")


def refs_differing(reviewed: list, now: list) -> list[str]:
  """The paths, sorted, whose `(file, sha)` pair is in one manifest and not the other; pairs, so a deletion (sha
  None) and an absent path are different."""
  pairs = lambda manifest: {(r["file"], r["sha"]) for r in manifest}
  return sorted({file for file, _ in pairs(reviewed) ^ pairs(now)})


def approve(args, st: core.Store, spec: Path, root: Path, card: dict) -> int:
  slug = core.spec_slug(spec)
  if args.void or args.amend_units:  # an older handoff is frozen (spec section 7)
    try:
      core.require_latest_handoff(st)
    except core.HandoffError as error:
      raise core.HandoffError(f"approve-spec: {error}") from None
  if args.void:
    return void_approval(args, st, spec)
  if args.amend_units:
    return amend_units(args, st, spec, root)
  if getattr(args, "respec", None):
    return approve_respec(args, st, spec, root, card)
  review, _ = latest_cycle(st, "spec", str(spec))
  if review is None:
    raise core.HandoffError(f"approve-spec: no spec review for {slug}")
  rid = review_id(st, "spec", str(spec), review["cycle"])
  if review.get("respec"):  # a respec cycle is approved by `--respec R<n>` alone, which writes its touched units
    raise core.HandoffError(f"approve-spec: review {rid} is a respec {review['respec']} cycle: use --respec {review['respec']}")
  if not (root / CONFIG).is_file():  # before any GitHub call: the config names the repository
    raise core.HandoffError(f"approve-spec: {CONFIG} missing: run superegm init")
  # U39: a malformed triage section refuses before the PR ingest (which writes) and before the prompt and the commit
  triage = triage_patterns(core.read_text(spec))
  number = spec_pr(st.config["repo"], core.run_git(["rev-parse", "--abbrev-ref", "HEAD"], root).strip())
  # U26: one `review ingest --pr` before the refusals: it reads the spec PR's threads, writes them, and the carried
  # findings, into the latest round and posts the fixed replies (a failed reply is named and retried next time, never
  # a refusal); no open PR, or a cycle with no round yet to take the threads, reads nothing (the latter is refused
  # below as not converged); a gh failure of the read refuses in one line, as `approve-spec:`.
  if number is not None and round_numbers(st, rid):
    try:
      _, unsettled = ingest_pr(st, review, number, card.get("parent") or args.runcard)
    except Refusal as error:
      raise core.HandoffError(f"approve-spec: {str(error).removeprefix('review ingest: ')}") from None
    if unsettled and not last_proceed(review):  # U57: a proceeded cycle's are the owner's accepted risk
      # named on the PR its thread came from: a carried finding's may be an earlier PR's
      fid = unsettled[0]
      latest = load_round(st, rid, round_numbers(st, rid)[-1])
      pr = next((f.get("pr") for f in findings_of(latest) if f["id"] == fid and f.get("pr")), number)
      raise core.HandoffError(f"approve-spec: {fid.rsplit('-', 2)[0]} {fid} unsettled on PR {pr}")
  status = evaluate(st, review, card.get("parent") or args.runcard)
  if status.code != 0 and status.fixed and status.latest_sha == core.sha256_file(spec):
    # U75: the spec bytes are the round's and only a reference document moved: say which one, not just "not converged"
    completed = [r for r in rounds_of(st, rid, review) if r["what_ran"] == "completed"]  # the round `evaluate` read, not a later partial one
    held = completed[-1].get("refs") if completed else None
    if held is not None:
      differing = refs_differing(held, reference_manifest(st, root))
      if differing:
        raise core.HandoffError(f"approve-spec: {differing[0]}: differs from the reviewed round")
  if status.code != 0:
    raise core.HandoffError(f"approve-spec: review {rid} is not converged (review status exit {status.code})")
  sha = core.sha256_file(spec)
  if sha != status.sha:
    raise core.HandoffError("approve-spec: spec bytes differ from the converged round's")
  reviewed_refs = reviewed_manifest(st, rid, review, status)
  if reviewed_refs is not None:  # U75: the reference documents the review read, unchanged since
    differing = refs_differing(reviewed_refs, reference_manifest(st, root))
    if differing:
      raise core.HandoffError(f"approve-spec: {differing[0]}: differs from the reviewed round")
  if not units_is_last_h2(core.read_text(spec)):
    raise core.HandoffError("approve-spec: last H2 must be `Units`")
  rounds = rounds_line(core.read_text(spec))
  if rounds is None:  # no `Rounds:` line: the live value, which `review.rounds` refuses outside 1-10
    rounds = live_rounds(st)
  try:  # the live `instructions` list, the one the approval commit carries, each file read before the prompt (U37)
    listed = instructions.check(st.config["instructions"])
    freeze(root, "HEAD", listed)
    reviewers.load(root, "HEAD")  # a bad reviewer file is refused before the prompt, naming it (U76)
  except core.HandoffError as error:
    raise core.HandoffError(f"approve-spec: {error}") from None
  last = core.load_approval(st, spec)
  if last:
    require_branch_holds(st, root, spec.relative_to(root).as_posix(), last)
  # the cycles past the last approval's; a re-approval of that same cycle (its bytes unmoved, U26: a thread ingested
  # and escalated after the approval) reads that cycle again and keeps the replaced entry's pairs the `## Units`
  # section does not name (that entry may cover earlier cycles too), since `graph` reads the latest entry's list alone
  since = cycle_of(last.get("review") if last else None)
  if last and last.get("review") == rid:
    named = units_section(core.read_text(spec))
    kept = [pair for pair in last.get("escalated") or [] if pair not in named]
    escalated = kept + [pair for pair in escalated_pairs(st, spec, since - 1) if pair not in kept]
  else:
    escalated = escalated_pairs(st, spec, since)
  if escalated:
    print(f"approve-spec: {len(escalated)} escalated finding(s) await the owner: {', '.join(escalated)}")
  # the mode this approval freezes, also the ask gate's: the card's default mode is the frozen mode of the spec's
  # previous handoff, which an approval opening a new handoff must not read (U43)
  mode = "leavemealone" if args.leavemealone or st.config.get("mode") == "leavemealone" else "normal"
  if not (args.yes or mode == "leavemealone"):
    print(f"Approve `{spec}` (sha256 `{sha[:12]}`) at review {rid}?")
    print("Options: Approve | Stop. Run again with --yes after the owner chose Approve.")
    return 0
  entries = core.load_approvals(st, spec)
  handoff_id, kind = handoff_id_for(st, sha, spec.stem, entries)
  superseded = entries[-1] if entries and kind == "opening" and handoff_id != entries[-1].get("handoff_id") else None
  if superseded and superseded.get("handoff_id") and not superseded.get("voided_by") \
      and incomplete_filing(handoff_state(st, superseded["handoff_id"])):  # U53: before any write
    raise core.HandoffError(f"approve-spec: handoff {superseded['handoff_id']} has an incomplete filing: finish /superegm:file first")
  if superseded and superseded.get("handoff_id"):  # U53: first, so a restore that fails leaves no approval recorded
    discard_unapplied_dry_run(st, superseded["handoff_id"])
  commit = commit_by_path(root, [spec.relative_to(root).as_posix(), CONFIG], f"superegm: approve {slug} at review {rid}",
                          st.config["commit_trailer"])
  try:  # the files at the approval commit itself, each copied to the store before the entry names it
    frozen = freeze(root, commit, listed, at="the approval commit")
  except core.HandoffError as error:
    raise core.HandoffError(f"approve-spec: {error}") from None
  try:  # the reviewer files at the approval commit, each copied to the store before the entry names it (U76)
    personas = reviewers.load(root, commit)
  except core.HandoffError as error:
    raise core.HandoffError(f"approve-spec: {error}") from None
  for item in instructions.flat(frozen):
    write_copy(st, item, raw="dir" in item)
  for pid, persona in personas.items():
    core.atomic_write(st.path("reviewers", persona["sha"]), {"id": pid, **persona})
  held = {r["id"]: r["sha"] for r in (last or {}).get("reviewers") or []}
  for pid, persona in personas.items():  # each reviewer whose sha the spec's previous entry does not hold
    if held.get(pid) != persona["sha"]:
      print(f"approve-spec: reviewers {reviewers.DIR}/{pid}.md {persona['sha']}")
  previous = {i["file"]: i["sha"] for i in instructions.flat((last or {}).get("instructions") or [])}
  for item in instructions.flat(frozen):  # each file whose sha the spec's previous entry, whatever its handoff, does not hold
    if previous.get(item["file"]) != item["sha"]:
      print(f"approve-spec: instructions {item['file']} {item['sha']}")
  entry = entry_of(sha, commit, args.runcard, rid, handoff_id, kind, escalated,  # an empty list stays absent: absent reads []
                   {"rounds": rounds, "triage": triage, "mode": mode, **({"instructions": [entry_item(i) for i in frozen]} if frozen else {}),
                    **({"reviewers": [{"id": pid, "sha": p["sha"]} for pid, p in personas.items()]} if personas else {})})
  path = append_entry(st, spec, entry)
  write_handoff_file(st, handoff_id, spec, entry["approved_at"] if kind == "opening" else None)
  core.journal(st, f"approve-spec {kind} {handoff_id} sha256 {sha[:12]} at review {rid} commit {commit[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0


def frozen_change(old: str, new: str) -> str | None:
  """The frozen field a respec's diff from `old` to `new` changes a line of: `Rounds` (the `Rounds:` lines before the
  first H2) or `triage` (the triage section); None when neither moved."""
  def rounds_lines(text):  # fenced lines are no Rounds lines and a fenced H2 ends nothing, as `rounds_line` reads
    found, fence = [], None
    for line in text.splitlines():
      if fence:
        if re.match(rf"^ {{0,3}}{fence[0]}{{{fence[1]},}}\s*$", line):
          fence = None
        continue
      if (opener := core.FENCE_RE.match(line)) and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
        fence = (opener.group(1)[0], len(opener.group(1)))
        continue
      if ANY_H2.match(line):
        break
      if line.startswith("Rounds:"):
        found.append(line)
    return found
  def triage_body(text):  # the section's lines alone: a heading moved by a line above it changes nothing
    section = triage_section(text.splitlines())
    return None if section is None else section[1]
  if rounds_lines(old) != rounds_lines(new):
    return "Rounds"
  if triage_body(old) != triage_body(new):
    return "triage"
  return None


def respec_checks(args, st: core.Store, spec: Path, root: Path, card: dict):
  """`--respec R<n>`'s refusals, before any write, each `approve-spec: respec R<n>: ...` unless named whole:
  `no approval to correct`; `<handoff>: not the latest approval: plan the rows in the latest handoff` (a voided latest
  approval included); `approve-spec: fold <base> first: approval <sha7> is not in this branch` (`require_branch_holds`);
  `not open`; `review <id> not converged`; `<U> is merged and overlaps <path:a-b>: add a follow-up row`; and
  `changes the frozen <field>: void and re-approve`. Returns `(handoff id, the latest approval, the review id, the spec text, respec.touched's result)`."""
  from superegm import respec
  rid_n = args.respec
  fail = lambda reason: core.HandoffError(f"approve-spec: respec {rid_n}: {reason}")
  latest = core.load_approval(st, spec)
  if latest is None:
    raise fail("no approval to correct")
  # the handoff `core.resolve_handoff` resolved (`--handoff`, else the card's), the latest only when neither names one
  hid = getattr(args, "handoff", None) or st.handoff_id or latest.get("handoff_id")
  if latest.get("handoff_id") != hid or latest.get("voided_by"):
    raise fail(f"{hid}: not the latest approval: plan the rows in the latest handoff")
  require_branch_holds(st, root, spec.relative_to(root).as_posix(), latest)  # as ordinary approvals and --amend-units
  if rid_n not in [r["id"] for r in respec.open(st, hid)]:  # applied, withdrawn or never opened
    raise fail("not open")
  if args.dry_run:  # the draft, before its commit and its review: the touched units alone
    return hid, latest, None, core.read_text(spec), respec.touched(st, hid, core.read_text(spec))
  review, _ = latest_cycle(st, "spec", str(spec))
  rid = review_id(st, "spec", str(spec), review["cycle"]) if review else "none"
  if review is None or review.get("respec") != rid_n:
    raise fail(f"review {rid} not converged")
  status = evaluate(st, review, card.get("parent") or args.runcard)
  text = core.read_text(spec)
  if status.code != 0 or core.sha256_file(spec) != status.sha:  # the raw bytes, as `current_sha` hashes them
    raise fail(f"review {rid} not converged")
  result = respec.touched(st, hid, text)
  for follow in result["follow_ups"]:
    if not follow["row"]:
      raise fail(f"{follow['unit']} is merged and overlaps {follow['overlaps']}: add a follow-up row")
  rel = spec.relative_to(root).as_posix()
  changed = frozen_change(core.run_git(["show", f"{latest['commit']}:{rel}"], root), text)
  if changed:
    raise fail(f"changes the frozen {changed}: void and re-approve")
  return hid, latest, rid, text, result


def approve_respec(args, st: core.Store, spec: Path, root: Path, card: dict) -> int:
  """`--respec R<n>` (spec section 7.6): `respec_checks`' refusals, then `respec/R<n>.json` and the comment files, then the
  entry, copying every frozen field as `--amend-units` does; a crash between them leaves the file without an entry,
  which a re-run rewrites and completes. `--dry-run` prints the touched units of the working tree and writes nothing."""
  from superegm import respec
  hid, latest, rid, text, result = respec_checks(args, st, spec, root, card)
  for key in ("touched", "untouched", "merged_review"):
    print(f"{key}: {', '.join(result[key])}")
  for follow in result["follow_ups"]:
    print(f"follow_up: {follow['unit']} overlaps {follow['overlaps']}: row {follow['row']}")
  if args.dry_run:
    return 0
  if not (args.yes or args.leavemealone or st.config.get("mode") == "leavemealone"):
    print(f"Approve respec {args.respec} of `{spec}` at review {rid}?")
    print("Options: Approve | Stop. Run again with --yes after the owner chose Approve.")
    return 0
  hs = core.handoff_store(st, hid)
  rel = spec.relative_to(root).as_posix()
  core.atomic_write(respec.respec_path(hs, f"{args.respec}.json"), result)
  state = (handoff_state(st, hid) or {}).get("units") or {}
  for unit in result["touched"]:  # a filed, unmerged unit: the comment the wave posts beside its filed body
    record = state.get(unit) or {}
    if record.get("number") and not respec.is_merged(record):
      core.atomic_write(hs.path("file", f"respec_comment_{unit}_{args.respec}.md"),
                        respec.comment_text(st, hid, text, unit, args.respec))
  commit = commit_by_path(root, [rel, CONFIG], f"superegm: approve {core.spec_slug(spec)} respec {args.respec} at review {rid}",
                          st.config["commit_trailer"])
  # the previous entry's escalated pairs the Units section does not name, then this respec cycle's own, as an ordinary
  # approval carries them (`graph` reads the latest entry's list alone)
  named = units_section(text)
  escalated = [pair for pair in latest.get("escalated") or [] if pair not in named]
  escalated += [pair for pair in escalated_pairs(st, spec, cycle_of(latest.get("review"))) if pair not in escalated]
  if escalated:
    print(f"approve-spec: {len(escalated)} escalated finding(s) await the owner: {', '.join(escalated)}")
  entry = entry_of(core.sha256_file(spec), commit, args.runcard, rid, hid, "respec", escalated,
                   {f: latest[f] for f in FROZEN_FIELDS if f in latest})
  entry |= {"respec": args.respec, "ranges": [list(r) for r in respec.changed_ranges(result["line_map"])]}
  path = append_entry(st, spec, entry)
  core.journal(st, f"approve-spec respec {args.respec} {hid} sha256 {entry['sha256'][:12]} at review {rid} commit {commit[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0


def void_approval(args, st: core.Store, spec: Path) -> int:
  """`--void --review <id>`: the latest approval (the history's last entry) is void once that review records
  a `fix-design` finding; its handoff, when its `state.json` files no unit, closes through `close`'s write.
  `--void` with no `--review` (U53) is the owner's void of an unplanned latest handoff, which `run` has checked:
  `voided_by` is `"owner"`."""
  slug, rid = core.spec_slug(spec), args.review or "owner"
  entries = core.load_approvals(st, spec)
  if not entries:
    raise core.HandoffError(f"approve-spec: no approval for {slug}")
  if args.review and load_review(st, rid) is None:
    raise core.HandoffError(f"approve-spec: review {rid}: not opened")
  if args.review and not any(f["disposition"] == "fix-design" for n in round_numbers(st, rid) for f in findings_of(load_round(st, rid, n))):
    raise core.HandoffError(f"approve-spec: review {rid} has no fix-design finding")
  path = st.path("approvals", slug)
  record = json.loads(core.read_text(path))
  if "entries" in record:
    entries[-1]["voided_by"] = rid
    write_entries(st, spec, entries)
  else:  # a 1.1 record is its one entry: `voided_by` written in place, nothing migrated
    entries[-1]["voided_by"] = record["voided_by"] = rid
    core.atomic_write(path, record)
  hid = entries[-1].get("handoff_id")
  if args.review:
    core.journal(st, f"approve-spec void {slug} by review {rid} under {args.runcard}")
  else:
    core.journal(st, f"approval {slug} voided by the owner: no unit left to plan")
  voided = core.handoff_store(st, hid)
  state = handoff_state(st, hid) or {"handoff_id": hid}  # a handoff never planned: a minimal state.json
  if hid and not files_a_unit(state) and not state.get("closed_at"):
    close.write_closed(voided, state, "voided")
  print(f"approval of {slug} voided by " + (f"review {rid}" if args.review else "the owner"))
  return 0


def amend_units(args, st: core.Store, spec: Path, root: Path) -> int:
  """`--amend-units` (section 12): rows appended to `## Units` are re-approved without a review round, a
  later entry of the latest approval's handoff; any change to a line before that heading refuses."""
  slug = core.spec_slug(spec)
  approval = core.load_approval(st, spec)
  if approval is None:
    raise core.HandoffError("approve-spec: no approval to amend")
  rel = spec.relative_to(root).as_posix()
  require_branch_holds(st, root, rel, approval)
  approved = core.run_git(["show", f"{approval['commit']}:{rel}"], root)
  if before_units(approved) != before_units(core.read_text(spec)):
    raise core.HandoffError("approve-spec: a line outside ## Units changed")
  sha = core.sha256_file(spec)
  commit = commit_by_path(root, [rel, CONFIG], f"superegm: approve {slug} at review {approval['review']}",
                          st.config["commit_trailer"])
  path = append_entry(st, spec, entry_of(sha, commit, args.runcard, approval["review"], approval["handoff_id"], "amend-units",
                                         list(approval.get("escalated") or []),
                                         {f: approval[f] for f in FROZEN_FIELDS if f in approval}))
  write_handoff_file(st, approval["handoff_id"], spec, None)
  core.journal(st, f"approve-spec amend-units {approval['handoff_id']} sha256 {sha[:12]} commit {commit[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0
