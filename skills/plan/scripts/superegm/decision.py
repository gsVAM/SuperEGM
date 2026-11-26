# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the decision subcommand (spec sections 7, 11 and 13.2): every point-1/2/3/5
# question and ruling of a unit, the by-hand BLOCKED ruling and the owner's close as `stop`; the redesign ruling
# (spec section 11.1) and the store-only brainstorm brief it writes; the one ruling grammar (`ruling_of`, `ruling_form`,
# `recorded_rulings`) and the by-hand ruling read through it (U22); a judges' redesign needs a high finding behind it (U23); an `owner: <ids>` decision's `<fid> allowed` options, the owner's alone (U25); a head's fifth point, `accept` or `revise` (U35); a launch with no commit of its own spends no `relaunch` and a second is `stop the unit` (U31); the owner's `amend` ruling and the amendment it records (spec §6.5, 1.2.1-pre.1 P5), as the file `amendments/<comment id>.json` written before the ruling is saved (U96); a failed resume is no launch without a commit (U63); `respec`, a `spec` deviation's option, the owner's alone, a spent `relaunch` dropped beside it, and a letter that resolves to it binding nothing unrecorded (spec §7.6, U84); the judges' ruling journalled and posted with `contest` on a normal-mode card (spec §7.8, U88); U103's rulings (1.3 design sections 3.6 and 3.7): a point-1 ruling with no fid refused as `missing <fid>`, a point-1 overrule or allowance settling the finding it rules through `review.apply_settle` after `review settle`'s ruler checks, a failed GitHub read one `gh:` line, a posted ruling comment edited before its first record refused as `ruling comment edited: post a new one`; U104's owner-only spec findings (1.3 design section 3.8): an `owner: <ids>` decision offering a spec fid `<fid> respec` beside `finding upheld` and `finding overruled`, a `## Q<n>` question's spec finding read, a mixed decision's `<fid> allowed` ruled as an `owner: <ids>` decision's.

"""superegm decision open|rule: record a unit's question (`decisions[]`) and its ruling (`rulings[]`)."""

import argparse
import contextlib
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import superegm as core
from superegm.apply import body_file
from superegm.launch import load_launches
from superegm.report import pending_decisions, unit_view
from superegm import review, scan
from superegm.review import Refusal

WRITES = frozenset({"foreman", "reviews", "state", "file"})  # the store kinds this subcommand writes (`reviews`: a fifth point's accept, U35; `state`: the other writers' fields; `file`: `amendments/<comment id>.json`, §6.5, and `respec/R<n>.open.json`, §7.6)
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SKILLS = frozenset({"wave"})  # the skills whose card this subcommand accepts
RELAUNCH = ["relaunch", "stop the unit"]
DEVIATION = re.compile(r"^\*\*Deviation \((?P<kind>[^)]*)\):\*\* ?(?P<rest>.*)$", re.M)
INTERFACE = re.compile(r"(?P<unit>U\d+) (?P<name>[^:]+):")  # an interface heading's `<Uxx> <name>:` (spec §6.5); `heading_name` reads the name


def comment_options(text: str) -> list:
  """A builder comment's point-3 options: its `- (` lines, `amend` when its one deviation heading is an interface
  one (the owner's alone, spec §6.5; `check_amend` refuses any other), `respec` when it is a `spec` one (the owner's
  alone, spec §7.6), then `stop the unit`."""
  kinds = [m["kind"] for m in DEVIATION.finditer(text)]
  extra = ["amend"] if kinds == ["interface"] else ["respec"] if kinds == ["spec"] else []
  return [line[2:].strip() for line in text.splitlines() if line.startswith("- (")] + extra + ["stop the unit"]


def produced_names(st, unit: str) -> list:
  """The names `scan.names_of` reads from the unit's Produces lines (no unit file: none)."""
  path = st.path("unit", unit) if st is not None else None
  lines = core.body.sections(core.read_text(path)).get("Interfaces", []) if path is not None and path.exists() else []
  return [n for line in lines if line.startswith("- Produces: ") for n in scan.names_of(line[len("- Produces: "):])]


def heading_name(raw: str, made: list) -> str:
  """An interface heading's name: kept whole when it is exactly one of the producer's names, else read through
  `scan.names_of` (so `load(path)` reads `load`)."""
  name = raw.replace("`", "").strip()
  if name in made:
    return name
  read = scan.names_of(name)
  return read[0] if read else name


def amendments_of(text: str, chosen: str, reason: str, comment_id: int, now: str, st=None) -> list:
  """The `amendments[]` entries a point-3 ruling on a builder comment writes (spec §6.5): `amend` names the one
  interface deviation, which must be in its unit's Interfaces lines (`rule` checks), text the owner's line; any
  other option settles every interface heading, text the option's; `stop the unit` and a relaunch keep the contract."""
  if chosen in RELAUNCH:
    return []
  heads = [INTERFACE.match(m["rest"]) for m in DEVIATION.finditer(text) if m["kind"] == "interface"]
  # the name as scan.names_of reads it, so launch_builder.amendments_for matches a Consumes line on the same reader
  return [{"unit": h["unit"], "name": heading_name(h["name"], produced_names(st, h["unit"])),
           "text": reason.strip() if chosen == "amend" else chosen, "comment_id": comment_id, "at": now}
          for h in heads if h]


RESPEC_FILE = re.compile(r"R(\d+)\.")


def respec_files(st) -> list:
  """The `respec/` folder's files, sorted."""
  folder = st.path("file", "respec")
  return sorted(folder.iterdir()) if folder.is_dir() else []


def respec_held(st, unit: str, comment_id: int = None, finding: str = None):
  """The `(file, content)` of the open respec file of this unit and this deviation, a comment (`comment_id`) or the
  foreman's finding (`finding`), else None."""
  for file in respec_files(st):
    if file.name.endswith(".open.json"):
      try:
        held = json.loads(file.read_text(encoding="utf-8"))
      except ValueError:
        continue
      if isinstance(held, dict) and held.get("unit") == unit and held.get("comment_id") == comment_id and held.get("finding") == finding:
        return file, held
  return None


def open_respec(st, unit: str, comment_id: int, now: str, finding: str = None) -> str:
  """Spec §7.6: the owner's `respec` on a `spec` deviation writes `respec/R<n>.open.json` (`{id, unit, comment_id,
  at}`, the store's `file` kind, never `state.json`) in the handoff's directory; `R<n>` is the next number no
  `respec/` file uses. On the foreman's spec finding `finding` (its fid) takes `comment_id`'s place: `{id, unit,
  finding, at}`. A rerun after a crash finds the file for the same unit and deviation and keeps it."""
  if held := respec_held(st, unit, comment_id, finding):
    return held[1]["id"]
  used = [int(m.group(1)) for f in respec_files(st) if (m := RESPEC_FILE.match(f.name))]
  rid = f"R{max(used, default=0) + 1}"
  entry = {"id": rid, "unit": unit, "finding": finding} if finding else {"id": rid, "unit": unit, "comment_id": comment_id}
  core.atomic_write(st.path("file", "respec", f"{rid}.open.json"), entry | {"at": now})
  return rid


def drop_respec(st, unit: str, comment_id: int = None, finding: str = None) -> None:
  """Remove the open respec file of this unit and deviation, if any: what a crashed run left when a rerun rules
  another option, so the file is never read as an open respec."""
  if held := respec_held(st, unit, comment_id, finding):
    held[0].unlink()


PATH_LINE = re.compile(r"[\w./-]+\.[A-Za-z]\w*:\d+(?:-\d+)?")  # a `path:line` (or `path:a-b`) reference
BACKTICKED = re.compile(r"`([^`\n]+)`")


def cites(ref: str, spec: str) -> bool:
  """Whether a `path:line` reference names the frozen spec: its path is the spec's, or ends it on a path boundary."""
  path, spec = ref.rpartition(":")[0].removeprefix("./"), spec.removeprefix("./")
  return spec == path or spec.endswith("/" + path)


def check_respec(text: str, spec: str = "") -> None:
  """Refuse a `respec` that is not on one `spec` deviation alone, whose comment does not quote a `path:line` of the
  frozen spec (`spec`, the handoff's spec path; empty when none is known, then any `path:line` counts), or that shows
  no evidence: a command (a backticked span that is not itself a `path:line`) or a `path:line` outside the spec, in
  the base (spec §7.6). The comment is the heading and the lines after it, less its options and cut at the
  `**Builder status:**` line: a `path:line` or a command after it does not count."""
  heads = list(DEVIATION.finditer(text))
  if len(heads) != 1 or heads[0]["kind"] != "spec":
    raise Refusal("decision: respec needs a comment with one spec deviation and no other")
  said = text[heads[0].start("rest"):].split("**Builder status:**")[0]
  said = "\n".join(line for line in said.splitlines() if not line.startswith("- ("))
  refs = list(dict.fromkeys(m.group(0) for m in PATH_LINE.finditer(said)))
  in_spec = [r for r in refs if not spec or cites(r, spec)]
  if not in_spec:
    raise Refusal("decision: respec needs the frozen spec's path:line in the deviation")
  commands = [s for s in BACKTICKED.findall(said) if not PATH_LINE.fullmatch(s.strip())]
  base = [r for r in refs if r not in in_spec] if spec else refs[1:]
  if not commands and not base:
    raise Refusal("decision: respec needs the evidence: a command and its output, or a path:line in the base")


def check_amend(st, text: str, reason: str) -> None:
  """Refuse an `amend` that has no Interfaces line, is not on one interface deviation alone, or names a `<name>`
  its unit's Interfaces lines lack (spec §6.5)."""
  if not reason.strip():
    raise Refusal("decision: amend needs — <the Interfaces line as it now reads>")
  heads = list(DEVIATION.finditer(text))
  h = INTERFACE.match(heads[0]["rest"]) if len(heads) == 1 and heads[0]["kind"] == "interface" else None
  if h is None:
    raise Refusal("decision: amend needs a comment with one interface deviation and no other")
  made = produced_names(st, h["unit"])
  name = heading_name(h["name"], made)
  if name not in made:
    raise Refusal(f"decision: amend names {h['unit']} {name}, not in {h['unit']}'s Interfaces lines")

# The one ruling grammar (spec section 13.2, amendment 5): a comment's first line in one of these forms and no other.
FID = r"[^\s()]+"
REASON = r" — (?P<reason>\S.*)"
FORM_RES = (
  ("upheld", re.compile(rf"(?P<subject>{FID}) finding upheld(?: \(fix it\))?")),
  ("overruled", re.compile(rf"(?P<subject>{FID}) finding overruled{REASON}")),
  ("round", re.compile(r"one more round")),
  ("stop", re.compile(r"stop")),
  ("option", re.compile(rf"\((?P<subject>\d+|q\d+)\) (?P<option>\S.*?){REASON}")),
  ("allowed-file", re.compile(rf"test-delta (?P<subject>\S+) allowed{REASON}")),
  ("redesign", re.compile(rf"redesign{REASON}")),
  ("allowed", re.compile(rf"(?P<subject>{FID}) allowed{REASON}")),
  ("proceed", re.compile(rf"proceed{REASON}")),  # the owner's go-ahead on a head (spec section 4.2): owners alone
)
NO_FID_RE = re.compile(r"(?:finding (?:upheld|overruled)|allowed)\b")  # a point-1 ruling opening with the verdict, no fid in front of it (U103)
LETTER_RE = re.compile(r"\([a-z]\)")  # a rendered option's letter, the bare answer of the judges
FILE_RULING_RE = re.compile(r"test-delta (\S+) allowed")  # a recorded whole-file allowance's text
JUDGES_MARK_RE = re.compile(r"^\(judges \S+, (?:leavemealone|contest)\)$", re.M)


@dataclass(frozen=True)
class Ruling:
  kind: str  # upheld | overruled | round | stop | option | allowed | allowed-file | redesign | proceed
  subject: str  # the fid, the comment or decision id, the `dod-<n>` item, the file, or "" for round, stop and redesign
  option: str | None  # the option text at point 3
  reason: str | None  # the text after the first ` — `, as typed
  login: str
  comment_id: int


def parse_form(body: str):
  """The form a body's first line is in, as (kind, subject, option, reason), or None: the judges' marker is not read here."""
  line = body.split("\n", 1)[0].rstrip("\r")
  if not line.startswith("**Ruling:** "):
    return None
  text = line[len("**Ruling:** "):]
  for kind, form in FORM_RES:
    if m := form.fullmatch(text):
      groups = m.groupdict()
      return kind, groups.get("subject") or "", groups.get("option"), groups.get("reason")
  return None


def ruling_of(comment: dict, owners: list) -> "Ruling | None":
  """The owner's ruling a comment carries, or None: an author outside `owners`, a body matching no form exactly, or the
  judges' post (the `(judges <panel>, leavemealone | contest)` marker on any line, recorded from `rulings[]`, never re-read)."""
  login = (comment.get("user") or {}).get("login") or comment.get("login")
  body = comment.get("body") or ""
  if login not in owners or JUDGES_MARK_RE.search(body.replace("\r", "")):
    return None
  form = parse_form(body)
  return form and Ruling(*form, login=login, comment_id=int(comment["id"]))


def ruling_line(text: str, reason: str | None = None) -> str:
  """The one renderer of the `**Ruling:**` line: the text, then ` — <reason>` only for a non-empty reason."""
  return f"**Ruling:** {text}" + (f" — {reason}" if reason else "")


def ruling_form(point: int, subject: str, option: str | None = None) -> str:
  """The form `ruling_of` reads, as the inbox's action text: point 1 `subject` the fid or `test-delta <file>` and
  `option` the verdict; point 2 `subject` the verdict; `redesign` as `subject` with no option; point 3 `subject` the
  comment or decision id and `option` its text. ` — <reason>` ends every form but `finding upheld`, `one more round`
  and `stop`."""
  if subject == "redesign" and option is None:
    text = "redesign"
  elif point == 3:
    text = f"({subject}) {option}"
  elif point == 2:
    text = subject
  else:
    text = f"{subject} {option}"
  bare = (point == 2 and text in ("one more round", "stop")) or (point == 1 and option == "finding upheld")
  return ruling_line(text, None if bare else "<reason>")


def recorded_rulings(foreman: dict) -> list:
  """One `Ruling` per `rulings[]` entry joined to its decision (the record a session, the judges or a by-hand
  ruling leaves): `redesign` by its text; point 1 the fid and `upheld | overruled`; point 2 `round | stop`;
  point 3 `option` on the source's comment id, else the decision id, the entry's leading token its option."""
  decisions = {d["id"]: d for d in foreman.get("decisions") or []}
  out = []
  for entry in foreman.get("rulings") or []:
    decision = decisions.get(entry.get("decision"))
    posted = entry.get("posted") or ""
    cid = int(posted.split()[1]) if posted.startswith("comment ") and posted.split()[1].isdigit() else 0
    if entry.get("kind") == "undo":  # the owner's undo of a triage deferral (spec section 5.2): an upheld, no decision
      out.append(Ruling("upheld", entry["fid"], None, entry.get("reason"), entry.get("by") or "", cid))
      continue
    if decision is None:
      continue
    text = (entry.get("ruling") or "").partition(" — ")[0].strip()
    option, subject = None, ""
    if text == "redesign" and decision["point"] in (1, 2):  # a head's third ruling; a point-3 option may begin with the word
      kind = "redesign"
    elif decision["point"] == 1 and (m := FILE_RULING_RE.fullmatch(text)):  # `rule_file`'s whole-file entry
      kind, subject = "allowed-file", m.group(1)
    elif decision["point"] == 1:
      kind, subject = ("upheld" if text.endswith("upheld") else "overruled"), text.split(" ")[0]
    elif decision["point"] == 2:
      kind = "round" if text == "one more round" else "stop"
    else:
      kind, subject = "option", option_name(decision)
      option = text.split(" ")[0] or None
    out.append(Ruling(kind, subject, option, entry.get("reason"), entry.get("by") or "", cid))
  return out


GROUPS = {"upheld": "fid", "overruled": "fid", "allowed": "fid", "option": "option"}  # the kinds that rule one subject


def binding_rulings(comments: list, owners: list, recorded: list, decisions=None, pending=None, deferred=None,
                    consumed=frozenset()) -> list:
  """The rulings that bind (spec section 13.2: a recorded ruling is never changed by a later comment): the record's
  (`recorded`, as `recorded_rulings` reads it), then each owner's form comment `ruling_of` reads whose comment id
  the record does not hold and whose fid or option subject the record does not already rule; an option ruling binds
  only when it is one of the options its decision offers (`decisions`, else the named comment's `- (` lines and
  `stop the unit`), as `decision rule` would accept it, with two exceptions `offered` names: an option naming a
  comment id this issue lacks binds unchecked (an interface ruling copied from its producer's issue, which
  `decision rule` drops here as naming no open decision, and which a mistyped id cannot be told apart from), and an
  option on a named comment with no `- (` lines binds whatever its text unless `respec` is among that comment's
  `comment_options` (a comment whose one deviation is `spec`; a `spec` deviation beside another deviation is no
  `spec` comment, so it keeps the exception); an unrecorded
  `respec`, or a letter resolving to it, binds nothing (`offered`: only `rule` writes the open file). Given `pending` (the open decisions, `pending_decisions`),
  an unrecorded `one more round` or `stop` binds only while a point-2 decision is open and a `redesign` only while
  a head's (point 1 or 2) is: otherwise `decision rule` drops it, and at point 3 a redesign is text. Once a point-1
  question exists, an unrecorded `finding upheld` binds only on a fid one asks about (`fid_decisions`, whose
  fallback, the latest point-1 decision with no finding line, asks about any fid), as `decision rule` would record
  it. Before any point-1 question an upheld fid binds as the landed `collect` read it, and a `finding overruled`
  always binds: section 13.2 reads an overrule on a `tdd-order`, `test-delta` or `dod-<n>` fid that no decision asks
  about as an allowance, which `collect` applies without a record. Given `deferred` (the fids of the record's
  `followups[]`, spec section 5.2), an unrecorded `upheld` naming one of them is dropped: an applied undo removes
  its row and binds as recorded, so a live one there is a refused undo, which never blocks. A comment in `consumed`
  (`consumed_comments`) binds nothing, whatever it now reads: an edited recorded proceed rules nothing (spec section 4.2)."""
  recorded = list(recorded)
  deferred = set(deferred or ())
  point3 = [d for d in decisions or [] if d.get("point") in (3, 5)]
  point1 = any(d.get("point") == 1 for d in decisions or [])

  def asked_for(r):
    return r.kind != "upheld" or not point1 or bool(fid_decisions({"decisions": decisions}, r.subject))
  open_points = None if pending is None else {d.get("point") for d in pending}

  def open_for(r):
    if open_points is None or r.kind not in ("round", "stop", "redesign"):
      return True
    return bool(open_points & ({2} if r.kind in ("round", "stop") else {1, 2}))

  def key(r):  # an option names its decision as `option_name` says: the comment id, or the decision id of a commentless one
    if r.kind != "option":
      return GROUPS.get(r.kind), r.subject
    return "option", next((d["id"] for d in point3 if r.subject == option_name(d)), r.subject)
  ids = {r.comment_id for r in recorded if r.comment_id}
  keys = {key(r) for r in recorded if r.kind in GROUPS}
  return recorded + [r for c in comments if (r := ruling_of(c, owners))
                     and r.comment_id not in ids and r.comment_id not in consumed and key(r) not in keys and open_for(r) and asked_for(r)
                     and not (r.kind == "upheld" and r.subject in deferred)
                     and (r.kind != "option" or offered(r, comments, decisions or []))]


def offered(r: "Ruling", comments: list, decisions: list) -> bool:
  """Whether an option ruling names one of its decision's options (`check_ruling` at point 3), except where there
  is nothing to check it against: a numeric id this issue's comments lack (a ruling copied from a producer's
  issue, or a mistyped id: both bind, unchecked) and a named comment with no `- (` lines whose `comment_options`
  do not include `respec` (any option binds; a comment whose one deviation is `spec` is excluded, a `spec`
  deviation beside another deviation is not); a decision id the record lacks binds nothing. A `respec` never binds unrecorded: `rule` writes
  its open file and records it, whether the ruling names it or a letter resolves to it (a `spec` comment with no
  option lines offers `respec` and `stop the unit`, so `(a)` is `respec`)."""
  decision = next((d for d in decisions if d.get("point") in (3, 5) and r.subject == option_name(d)), None)
  if (r.option or "").strip() == "respec":  # a ruling comment alone binds no `respec`: `rule` writes the open file and
    return False  # records it (`recorded_rulings`), so a recorded one needs no check here, an unrecorded one clears no blocker
  if decision is not None:
    options = decision.get("options") or []
  else:
    named = next((c for c in comments if str(c.get("id")) == r.subject), None)
    if named is None:  # a comment id this issue lacks: an interface ruling copied from its producer's issue (spec
      return r.subject.isdigit()  # section 13.2), nothing here to check it against; a decision id it lacks binds nothing
    options = comment_options(named.get("body") or "")
    if "respec" not in options and not any(line.startswith("- (") for line in (named.get("body") or "").splitlines()):
      return True  # a comment with no option lines (a kind-`other` deviation): nothing to check the option against
  try:
    return check_ruling(3, options, r.option or "") != "respec"  # a lettered `(a) respec` resolves to it too
  except Refusal:
    return False


def overridden_comments(comments: list, owners: list, foreman: dict) -> dict:
  """The owners' ruling comments the record overrides, by id: a recorded post edited after its record (`updated_at`
  later than the entry's `posted_at`, the comment's own time when recorded; for an `unread` entry, the session's post
  whose GitHub time was never read back, later than the comment's own `created_at`) maps to the record's text, which the prompt shows in its place, as
  does a recorded comment in no form (a ruling recorded before the one grammar, such as `(77) use Redis`); an
  unedited recorded point-3 ruling whose option is not its decision's full option text maps to its body with the
  line `(recorded on <decision id> as: <option>)` (the frozen question's option, never the named comment's live
  text); an unrecorded form ruling a subject the record already rules, an option the decision does not offer, or a
  bare `one more round`, `stop` or `redesign` no open decision takes, maps to None (dropped)."""
  entries = {r.get("posted"): r for r in foreman.get("rulings") or [] if str(r.get("posted") or "").startswith("comment ")}
  proceeds = {r.get("posted"): r for r in foreman.get("proceeds") or [] if str(r.get("posted") or "").startswith("comment ")}
  decisions = foreman.get("decisions") or []
  bound = {r.comment_id for r in binding_rulings(comments, owners, recorded_rulings(foreman), decisions,
                                                 pending_decisions({"decisions": decisions, "rulings": foreman.get("rulings") or []}),
                                                 [r["fid"] for r in foreman.get("followups") or []], consumed_comments(foreman))}
  out = {}
  for c in comments:
    entry = entries.get(f"comment {c['id']}")
    if proceed := proceeds.get(f"comment {c['id']}"):  # consumed by its record: once edited, the prompt shows the record
      if edited_after_record(c, proceed):
        out[c["id"]] = proceed_text(proceed)
    elif entry:
      if edited_after_record(c, entry):
        out[c["id"]] = record_text(foreman, entry)
      elif parse_form(c.get("body") or "") is None:  # recorded before the one grammar (no reason): the record binds
        out[c["id"]] = record_text(foreman, entry, "the comment is in no ruling form")
      elif (full := recorded_option(foreman, entry)) and (form := parse_form(c.get("body") or "")) and form[0] == "option" and form[2] != full:
        first, sep, rest = (c.get("body") or "").partition("\n")
        out[c["id"]] = f"{first}\n(recorded on {entry['decision']} as: {full}){sep}{rest}"
    elif ruling_of(c, owners) and int(c["id"]) not in bound:
      out[c["id"]] = None
  return out


def edited_after_record(comment: dict, entry: dict) -> bool:
  """Whether a recorded comment was edited after its record: its `updated_at` later than the entry's `posted_at`, or,
  for an `unread` entry (`posted_at` the host's time, GitHub's never read back), later than its own `created_at`.
  The comment's `created_at` is a floor for either: a session ruling recorded before U22 holds the host's time from
  before its post, which an unedited post's GitHub time passes."""
  created = comment.get("created_at") or ""
  since = created if entry.get("unread") else max(entry.get("posted_at") or "", created)
  return (comment.get("updated_at") or "") > since


def deleted_rulings(comments: list, foreman: dict) -> list:
  """A recorded ruling whose comment is gone, as a comment in its place: its id, `by` as the author and the record's
  text, so the prompt still carries what binds (spec section 13.2: a recorded ruling is never changed)."""
  live = {int(c["id"]) for c in comments}
  note = "the comment was deleted after its record"
  out = {}
  for entry in foreman.get("rulings") or []:
    cid = str(entry.get("posted") or "").removeprefix("comment ")
    if str(entry.get("posted") or "").startswith("comment ") and cid.isdigit() and int(cid) not in live and int(cid) not in out:
      out[int(cid)] = {"id": int(cid), "user": {"login": entry.get("by")}, "body": record_text(foreman, entry, note)}
  for entry in foreman.get("proceeds") or []:  # a recorded proceed's comment, gone: the proceed as recorded
    cid = str(entry.get("posted") or "").removeprefix("comment ")
    if str(entry.get("posted") or "").startswith("comment ") and cid.isdigit() and int(cid) not in live and int(cid) not in out:
      out[int(cid)] = {"id": int(cid), "user": {"login": entry.get("by")}, "body": proceed_text(entry, note)}
  return list(out.values())


def recorded_option(foreman: dict, entry: dict):
  """A recorded point-3 ruling's option as its decision's frozen question offered it (letter and text), or None."""
  decision = next((d for d in foreman.get("decisions") or [] if d["id"] == entry.get("decision")), {})
  if decision.get("point") != 3:
    return None
  text = (entry.get("ruling") or "").partition(" — ")[0].strip()
  for option in decision.get("options") or []:
    try:
      check_ruling(3, [option], text)
    except Refusal:
      continue
    return option
  return None


def consumed_comments(foreman: dict) -> set:
  """The comment ids `rulings[]` and `proceeds[]` record as `posted` (a typed proceed's null `posted` names none): the
  comments a record consumed, whose later edit or deletion the record answers (spec section 4.2)."""
  return {int(cid) for entry in (foreman.get("rulings") or []) + (foreman.get("proceeds") or [])
          if (cid := str(entry.get("posted") or "").removeprefix("comment ")).isdigit()}


def proceed_text(entry: dict, note: str = "the comment was edited after its record") -> str:
  """A `proceeds[]` entry as its form, marked as the record: `**Ruling:** proceed — <reason>` by its `by` (what an edited
  or deleted recorded proceed comment is replaced by in the prompt; `record_text` reads `rulings[]`, never `proceeds[]`)."""
  return ruling_line("proceed", entry.get("reason")) + f"\n(as recorded by {entry.get('by')}; {note})"


def record_text(foreman: dict, entry: dict, note: str = "the comment was edited after its record") -> str:
  """A `rulings[]` entry as its form, marked as the record (what an edited or deleted recorded comment is replaced by)."""
  decision = next((d for d in foreman.get("decisions") or [] if d["id"] == entry.get("decision")), {})
  text, reason = (entry.get("ruling") or "").partition(" — ")[0].strip(), entry.get("reason")
  source, point = str(decision.get("source") or ""), decision.get("point")
  if point in (3, 5):
    text = recorded_option(foreman, entry) or text
    text = f"({source.removeprefix('comment ') if source.startswith('comment ') else decision.get('id')}) {text}"
  bare = point == 2 and text != "redesign" or point == 1 and text.endswith(" finding upheld")
  return (ruling_line(text, None if bare else reason)
          + f"\n(as recorded by {entry.get('by')}; {note})")


def register(subparsers):
  p = subparsers.add_parser("decision", help="decision open|rule")
  action = p.add_subparsers(dest="action", required=True)
  o = core.add_parser(action, "open", "record a point-1/2/3/5 question and print its id and options")
  o.add_argument("--unit", required=True)
  o.add_argument("--point", type=int, choices=(1, 2, 3, 5), required=True)
  o.add_argument("--question", required=True, help="the question file (the builder's comment, the contested findings)")
  o.add_argument("--source", required=True,
                 help="comment <id> | launch <n> | closed <n> | review <id> round <n> | review <id> cap")
  r = core.add_parser(action, "rule", "record a ruling and post it as the `**Ruling:**` comment")
  r.add_argument("--unit", required=True)
  r.add_argument("--decision", help="the decision id `open` printed; required unless --posted (a comment the ruling's form names, or closed:<n>)")
  r.add_argument("--ruling", required=True, help="an option's letter or text, optionally ` — <reason>`; or on a head (points 1, 2) `redesign — <one sentence why>`")
  r.add_argument("--by", required=True, help="<login> | judges:<panel-id>")
  r.add_argument("--posted", help="<comment-id> of a by-hand **Ruling:** (nothing is posted) | closed:<n>")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  try:
    return {"open": open_decision, "rule": rule}[args.action](args)
  except Refusal as refusal:
    print(refusal)
    return 1
  except core.GhError as error:  # a failed GitHub read (the settle's too) is one line, nothing recorded (U103)
    print(f"gh: {' '.join(str(error).split())}", file=sys.stderr)
    return 1


def open_decision(args) -> int:
  core.require_runcard(args, SKILLS)
  st = core.store(core.git_toplevel(Path.cwd()))
  state, unit = core.load_state(st.root), args.unit
  if unit not in (state.get("units") or {}):
    raise Refusal(f"decision: {unit} is not a unit of this handoff")
  data = core.load_foreman(st, unit)
  pending = pending_decisions(data)
  if pending:
    raise Refusal(f"decision: {unit} has a pending decision {pending[0]['id']}")
  head, question = unit_view(state, unit)["head"], core.read_text(Path(args.question))
  options = options_for(args.point, args.source, question, data, head)
  qid, now = f"q{len(data['decisions']) + 1}", core.now_iso()
  data["decisions"].append({"id": qid, "point": args.point, "source": args.source, "head": head,
                            "question": question, "asked_at": now, "options": options})
  reason = stop_reason(data, load_launches(st, unit), args.source) if "relaunch" in options else None
  if reason and "respec" in options:  # a spec deviation keeps `respec` (§7.6): the spent relaunch is dropped, the decision is asked
    options.remove("relaunch")
    data["decisions"][-1]["options"] = options
    reason = None
  if reason:
    data["rulings"].append({"decision": qid, "ruling": "stop the unit", "by": "superegm",
                            "reason": reason, "posted": None, "posted_at": now})
  core.save_foreman(st, unit, data)
  core.journal(st, f"Decision {qid} (point {args.point}, {args.source}): {unit}")
  print(qid)
  if reason:
    core.journal(st, f"Ruling (superegm): {unit} {qid} stop the unit — {reason}")
    stop_unit(st, unit, "superegm", "stop the unit", state["units"][unit]["number"], now)
    print(f"ruled: stop the unit ({reason})")
  else:
    print("options: " + "; ".join(options))
  return 0


def no_commit(entry) -> bool:
  """U31: a launch with no commit of its own: an `exited …` or `exited (stalled)` entry whose `last_commit_at` is
  absent or None (an `interrupted` or `running` entry, or none, is not; nor a failed resume, relaunched fresh, U63)."""
  return (bool(entry) and str(entry.get("status") or "").startswith("exited") and not entry.get("last_commit_at")
          and not entry.get("failed_resume"))


def launch_of(launches: list, source):
  """The entry a `launch <n>` source names, else None."""
  words = str(source or "").split()
  if len(words) == 2 and words[0] == "launch" and words[1].isdigit():
    return next((e for e in launches if e.get("round") == int(words[1])), None)
  return None


def stop_reason(foreman: dict, launches: list, source: str):
  """The carve-out (spec section 11.1, U31): a relaunch question stopped without asking when a `relaunch` was
  already used (ruled on a `comment`, a `closed`, or a `launch <n>` whose entry has a commit of its own; a
  host-caused stall spends none), or when the source launch and an earlier one both have no commit of their own."""
  sources = {d["id"]: str(d.get("source") or "") for d in foreman.get("decisions") or []}

  def spends(r) -> bool:
    src = sources.get(r.get("decision"))
    if src is None or src.startswith(("comment", "closed")):
      return True
    return src.startswith("launch") and not no_commit(launch_of(launches, src))

  if any(r["ruling"].partition(" — ")[0].strip() == "relaunch" and spends(r) for r in foreman.get("rulings") or []):
    return "relaunch already used"
  entry = launch_of(launches, source)
  if no_commit(entry) and any(no_commit(e) for e in launches if (e.get("round") or 0) < entry["round"]):
    return "second launch with no commit of its own"
  return None


SPEC_CLAIM = "deviation (spec) unruled: "  # the claim of the foreman's finding of kind `spec` (`collect --spec`, §7.6)


def spec_claims(question: str) -> dict:
  """The foreman's spec findings a point-1 question holds, fid to the finding's text (what follows `SPEC_CLAIM`): a
  `<fid> | … | <claim>` line, or a `## Q<n> <fid> (<severity>, <location>): <claim>` one (U104)."""
  found = {}
  for line in question.splitlines():
    fields = line.split(" | ", 4)
    if len(fields) == 5 and fields[4].startswith(SPEC_CLAIM) and " " not in fields[0]:
      found[fields[0]] = fields[4][len(SPEC_CLAIM):]
    elif (m := Q_LINE_RE.match(line)) and m["claim"].startswith(SPEC_CLAIM):
      found[m["fid"]] = m["claim"][len(SPEC_CLAIM):]
  return found


def owner_options(word: str, question: str) -> list:
  """Point 1 on an `owner: <ids>` word (U25, U104): an id of the word standing in the question as its own word is offered
  `<fid> respec` when the question holds it as a spec finding, else `<fid> allowed`; with a spec fid among them,
  `finding upheld` and `finding overruled` come first; [] when no id of the word stands in the question."""
  specs = spec_claims(question)
  ids = [fid for fid in word[len("owner: "):].split(", ") if re.search(rf"(?<!\S){re.escape(fid)}(?!\S)", question)]
  respecs = [f"{fid} respec" for fid in ids if fid in specs]
  allowed = [f"{fid} allowed" for fid in ids if fid not in specs]
  return (["finding upheld", "finding overruled"] + respecs if respecs else []) + allowed


def options_for(point: int, source: str, question: str, foreman: dict, head: str) -> list:
  """Spec section 13.2's options: point 1 upheld|overruled, and `<fid> respec` (§7.6, the owner's alone) for each of the
  foreman's spec findings the question holds; point 2 one more round|stop; point 3 the
  comment's own `- (a)` lines plus `stop the unit`, or `relaunch; stop the unit` for a launch, a close,
  or a third `blocked` comment on the same head (a `spec` deviation's keeps `respec` between them, §7.6, `open_decision` dropping a `relaunch` already used); point 5 (a head's accept below the cap) accept|revise. Point 1 on
  an `owner: <ids>` word (the latest posted round's outcome) offers `owner_options`: `<fid> allowed` one per id the question
  names (U25), a spec finding's id `<fid> respec` beside `finding upheld` and `finding overruled` (U104)."""
  if point == 5:
    return ["accept", "revise"]
  if point == 1:
    posted = [e for e in foreman.get("rounds") or [] if e.get("phase") == "posted"]
    word = str(posted[-1].get("outcome") or "") if posted else ""
    if word.startswith("owner: ") and (named := owner_options(word, question)):
      return named
    return ["finding upheld", "finding overruled"] + [f"{fid} respec" for fid in spec_claims(question)]
  if point == 2:
    return ["one more round", "stop"]
  if source.startswith("comment"):
    same = [d for d in foreman.get("decisions") or []
            if d.get("point") == 3 and str(d.get("source", "")).startswith("comment") and d.get("head") == head]
    if len(same) < 2:
      return comment_options(question)
    if "respec" in comment_options(question):  # a spec deviation's decision always offers `respec` (§7.6)
      return RELAUNCH[:1] + ["respec"] + RELAUNCH[1:]
  return list(RELAUNCH)


def stop_unit(store, uid: str, by: str, reason: str, number: int, now_iso: str, brief=None) -> None:
  """Label the issue `superegm:stopped`, write `foreman["stopped"]` (with `brief`, the redesign brief's path,
  when there is one), journal (spec section 11)."""
  label_stopped(store, number)
  data = core.load_foreman(store, uid)
  data["stopped"] = stopped_entry(by, reason, now_iso, brief)
  core.save_foreman(store, uid, data)
  core.journal(store, f"{uid} stopped by {by}: {reason}")


def label_stopped(store, number: int) -> None:
  core.gh(["issue", "edit", str(number), "-R", store.config["repo"], "--add-label", store.config["labels"]["stopped"]])


def labelled_stopped(store, number: int) -> bool:
  """The issue carries the stopped label now (`gh issue view --json labels`)."""
  labels = core.gh_json(["issue", "view", str(number), "-R", store.config["repo"], "--json", "labels"]).get("labels") or []
  return any(l.get("name") == store.config["labels"]["stopped"] for l in labels)


def stopped_entry(by: str, reason: str, now_iso: str, brief=None) -> dict:
  return {"by": by, "reason": reason, "at": now_iso} | ({"brief": str(brief)} if brief else {})


def high_behind(st, unit: str, source: str) -> bool:
  """A `high` finding with no disposition in the unit's latest posted round of the review the decision's source
  names (its second word): what a judges' `redesign` needs behind it."""
  words = (source or "").split()
  posted = [e["round"] for e in core.load_foreman(st, unit)["rounds"] if e.get("phase") == "posted"]
  rnd = review.load_round(st, words[1], max(posted)) if len(words) > 1 and posted else None
  return bool(rnd) and any(f["severity"] == "high" and f["disposition"] is None for f in review.findings_of(rnd))


def settle_checks(st, items: list, args, card: dict) -> list:
  """U103: the point-1 ruling's settle, checked before anything is posted or recorded. `items` is each `(decision, fid)` the
  ruling overrules or allows; its fid is settled in the head review's round the decision's source names, with the disposition
  the decision gives (`declined` on an `owner: <ids>` decision, `contested` on a contest's), as the owner or as `judges:<panel>`
  (`args.by`), after `review settle`'s own ruler checks. A review never opened, no head's or another unit's, and in
  leavemealone-mode a ruling typed in the session (no `--posted`: no comment of the owner's for the settle to read) settle
  nothing; a finding the source's round does not hold is refused, and the CI finding refuses any overrule. A refusal is
  `review settle`'s own. The plan: `(review id, checked)` each."""
  judges = args.by[7:] if args.by.startswith("judges:") else None
  posted = args.posted if args.posted and not args.posted.startswith("closed:") else None
  # `unrecorded`: the settle's read of the comment comes before its first record, so an edit it sees is refused (U103)
  ruler = argparse.Namespace(owner=not judges, judges=judges, posted=posted, runcard=args.runcard, unrecorded=True)
  plan = {}
  for decision, fid in items:
    words = str(decision.get("source") or "").split()
    if len(words) != 4 or words[0] != "review" or words[2] != "round" or not words[3].isdigit():
      continue
    rid, source_round = words[1], int(words[3])
    opened = review.load_review(st, rid)
    if opened is None or opened["kind"] != "head" or opened["artifact"] != args.unit:  # never another unit's review
      continue
    try:
      _, _, reviewer, found = review.locate_in_round(st, rid, source_round, fid)
      review.check_ci_finding(reviewer, found)  # whether or not it settles
      if card.get("mode") == "leavemealone" and not posted:
        continue
      disposition = "declined" if f"{fid} allowed" in (decision.get("options") or []) else "contested"
      n = review.check_settle(st, rid, opened, card, ruler, fid, disposition, source_round)
    except core.HandoffError as error:  # a finding the source's round does not hold is refused too, as `review settle` refuses it
      raise Refusal(str(error)) from None
    plan.setdefault(rid, []).append((fid, disposition, None, n))
  return list(plan.items())


def settle_ruled(st, plan: list, args, card: dict):
  """The settle a checked plan makes (`review.apply_settle`, once the ruling is recorded); the round's word it rewrote, if any."""
  judges = args.by[7:] if args.by.startswith("judges:") else None
  ruler = argparse.Namespace(owner=not judges, judges=judges, posted=None, runcard=args.runcard)
  word = None
  for rid, checked in plan:
    word = review.apply_settle(st, rid, review.load_review(st, rid), card, ruler, checked) or word
  return word


def rule(args) -> int:
  card = core.require_runcard(args, SKILLS)
  st = core.store(core.git_toplevel(Path.cwd()))
  state, unit, now = core.load_state(st.root), args.unit, core.now_iso()
  if unit not in (state.get("units") or {}):
    raise Refusal(f"decision: {unit} is not a unit of this handoff")
  number, closed = state["units"][unit]["number"], (args.posted or "").partition("closed:")[2]
  if not args.decision and not (args.posted and not closed):
    if not closed:
      raise Refusal("decision: --decision is required unless --posted <comment id> or closed:<n>")
    stop_unit(st, unit, args.by, f"closed #{closed} by {args.by}", number, now)
    print(f"recorded (closed #{closed})")
    return 0
  data = core.load_foreman(st, unit)
  head, _, reason = args.ruling.partition(" — ")
  found = comment = None
  if args.posted and not closed:  # a by-hand ruling: read through the one grammar (spec section 13.2, U22)
    comment, found, decisions = verify_posted(st, unit, data, args, number, card.get("mode"))
    if decisions is None:
      return undo(st, unit, data, args, comment, found, now)
    if found.kind == "allowed-file":
      return rule_file(st, unit, data, args, comment, found, decisions, card)
  else:
    decision = next((d for d in data["decisions"] if d["id"] == args.decision), None)
    if decision is None:
      raise Refusal(f"decision: {unit} has no decision {args.decision}")
    decisions = [decision]
  # Point 1 takes one ruling per contested finding (`<fid> finding upheld | overruled`, the leavemealone row's
  # "one call per finding"), keyed on the comment's fid on a by-hand ruling; the other points take one ruling.
  fid_of = lambda text: text.partition(" — ")[0].strip().split(" ")[0]
  if decisions[0]["point"] == 1 and NO_FID_RE.match(head.strip()):  # U103: a ruling that opens with the verdict names no finding
    raise Refusal('decision: missing <fid>: write "<fid> finding overruled"')
  fid = found.subject if found and found.kind in ("upheld", "overruled", "allowed") else fid_of(head)
  for d in decisions:
    ruled = [r for r in data["rulings"] if r.get("decision") == d["id"]]
    if ruled and (d["point"] != 1 or any(fid_of(r["ruling"]) == fid for r in ruled)):
      dropped(st, args, f"{d['id']} already ruled")
  decision = decisions[0]
  basis = next((d for d in decisions if d["point"] in (1, 2)), decision) if found and found.kind == "redesign" else decision
  chosen = check_ruling(basis["point"], basis["options"], head.strip(), args.by)
  brief = None
  if found:  # the record is the comment's ruling: a `--ruling` that resolves to another option is refused
    said = {"upheld": f"{found.subject} finding upheld", "overruled": f"{found.subject} finding overruled",
            "round": "one more round", "stop": "stop", "option": found.option, "redesign": "redesign",
            "allowed": f"{found.subject} finding overruled"}.get(found.kind) or ""  # an allowance is recorded as an overrule (§13.2)
    try:
      ruled_by_comment = check_ruling(basis["point"], basis["options"], said, args.by)
    except Refusal:
      ruled_by_comment = None
    if ruled_by_comment != chosen:
      raise Refusal(f"decision: comment {args.posted} rules {said}, not {head.strip()}")
    reason = found.reason or ""
  elif not reason.strip() and chosen != "amend" and (decision["point"] == 3 or chosen.endswith((" finding overruled", " allowed", " respec"))):
    # a ruling typed without the reason its form carries: the session's, or the panel's, named as such
    reason = f"ruled by judges {args.by[7:]}" if args.by.startswith("judges:") else "ruled in the session"
  if chosen == "redesign" and basis["point"] in (1, 2):  # a head's third ruling; a point-3 option named `redesign` is an option
    if not reason.strip():
      raise Refusal("decision: redesign needs — <one sentence why>")
    if args.by.startswith("judges:") and not high_behind(st, unit, decision["source"]):  # spec section 11.2 (U23)
      raise Refusal(f"decision: redesign by {args.by} needs a high finding behind it")
    chosen = f"redesign — {reason.strip()}"
    brief = brief_path(st, unit, decision["id"])  # written after the comment is posted: a refusal leaves no brief
  amends = decision["point"] == 3 and str(decision["source"]).startswith("comment")
  respec_fid = chosen.removesuffix(" respec") if decision["point"] == 1 and chosen.endswith(" respec") else None
  if amends and chosen == "amend":  # refused before anything is posted
    check_amend(st, decision["question"], reason)
  if amends and chosen == "respec":  # the spec line and the evidence, refused before anything is posted
    check_respec(decision["question"], core.handoff_spec(args, st))
  if respec_fid:  # the same two parts on the foreman's spec finding, refused before anything is posted
    check_respec("**Deviation (spec):** " + spec_claims(decision["question"])[respec_fid], core.handoff_spec(args, st))
  if decision["point"] == 5:  # a head's fifth point (U35): the owner's alone, applied before anything is posted
    if args.by.startswith("judges:"):
      raise Refusal("decision: point 5 is the owner's alone")
    fifth_point(st, unit, decision, chosen, args.runcard)
    data = core.load_foreman(st, unit)  # the round's outcome is written: the record is reloaded before the append
  settles = []  # U103: a point-1 overrule or allowance settles the finding it rules; every check runs before the post
  if decision["point"] == 1 and not closed and chosen.endswith((" finding overruled", " allowed")):
    ruled_fid = chosen.split(" ")[0]
    if not found and decision not in fid_decisions(data, ruled_fid):  # as the posted path refuses it: never another finding
      raise Refusal(f"decision: {ruled_fid} is not a finding of {decision['id']}")
    settles = settle_checks(st, [(decision, ruled_fid)], args, card)
  # the effect is the point's, never the option's wording: point 2's `stop`, point 3's `stop the unit`, a redesign.
  # The label goes first, so a failed request records nothing and the same call reruns (round 9); a session post
  # that then fails takes off again only a label this call put on (rounds 10 and 11).
  stops = (decision["point"], chosen) in ((2, "stop"), (3, "stop the unit")) or brief
  label = st.config["labels"]["stopped"]
  had = False
  if stops:
    if not (closed or found):  # a session post can fail after the label: know whether it was already on (the owner's close)
      had = labelled_stopped(st, number)
    label_stopped(st, number)
  posted_at, url = now, None
  if closed:
    posted = f"closed #{closed}"
  elif found:
    # the comment as recorded: its latest edit's time, so only a later edit reads as "edited after record"
    posted, posted_at = f"comment {args.posted}", comment.get("updated_at") or comment.get("created_at") or now
  else:
    bare = chosen.endswith(" finding upheld") if decision["point"] == 1 else decision["point"] == 2  # forms with no reason
    body = ruling_comment(decision["point"], decision["source"], chosen + (f" — {reason}" if reason and not brief and not bare else ""),
                          decision["question"], brief, args.by, decision["id"], card.get("mode"))
    path = body_file(body, st.root)
    try:
      url = core.gh(["issue", "comment", str(number), "-R", st.config["repo"], "--body-file", path]).strip()
    except core.GhError:
      if stops and not had:  # nothing is recorded: the label this call put on comes off, so the call reruns
        try:
          core.gh(["issue", "edit", str(number), "-R", st.config["repo"], "--remove-label", label])
        except core.GhError:  # the post's error is the one raised; the label left on is journaled
          core.journal(st, f"{unit} {decision['id']}: label {label} left on issue #{number}")
      raise
    finally:
      os.unlink(path)
    cid = url.rsplit("-", 1)[1]
    posted = f"comment {cid}"
  if brief:
    brainstorm_brief(st, unit, decision["id"], decision, chosen, (state["units"][unit].get("pr") or {}).get("number"))
  # a point-3 letter resolved by position is stored as the option it resolved to (its ` — <reason>` kept): the readers of
  # `rulings[]` (`stop_reason`, `recorded_option`) compare the option's text, and see no position
  stored = chosen + args.ruling[len(head):] if basis["point"] == 3 and by_position(basis["options"], head.strip(), args.by) else args.ruling
  entries = [{"decision": d["id"], "ruling": stored, "by": args.by,
              "reason": reason.strip() or None, "posted": posted, "posted_at": posted_at}
             | ({"unread": True} if url else {}) for d in decisions]
  data["rulings"] += entries
  if stops:  # the stop is written with the ruling, in one save
    data["stopped"] = stopped_entry(args.by, chosen, now, brief)
  if amends:  # spec §6.5: the contract changes, as the file `amendments/<deviation comment id>.json`, written
    # before the ruling is saved (a crash between the two leaves a file no reader trusts: `amendments_for` reads a file only
    # once a ruling names its comment) and rewritten, or deleted when this ruling records none, by a rerun; a close given
    # with `--decision` (`--posted closed:<n>`) records none, so it deletes a crashed run's file (a close with no `--decision`
    # stops the unit and returns above, leaving the file, which no ruling names and no reader trusts)
    file = st.path("file", "amendments", f"{str(decision['source']).split()[1]}.json")
    added = [] if closed else amendments_of(decision["question"], chosen, reason, int(posted.split()[1]), now, st)
    if added:
      recorded_at = core.now_iso()
      core.atomic_write(file, [entry | {"recorded_at": recorded_at} for entry in added])
    elif file.exists():
      file.unlink()
  # spec §7.6: the open file is written before the ruling is saved, so a crash leaves a file a rerun keeps when it rules
  # `respec` again, and removes when it rules another option, so a stale file is never read as an open respec
  deviation = None
  if amends:
    deviation = {"comment_id": int(str(decision["source"]).split()[1])}
  elif decision["point"] == 1 and chosen.split(" ")[0] in spec_claims(decision["question"]):  # a spec finding's ruling
    deviation = {"finding": chosen.split(" ")[0]}
  if deviation:
    if (chosen == "respec" if amends else bool(respec_fid)) and not closed:
      open_respec(st, unit, deviation.get("comment_id"), now, deviation.get("finding"))
    else:
      drop_respec(st, unit, deviation.get("comment_id"), deviation.get("finding"))
  # recorded before the read-back, the session's post marked `unread` (its GitHub time not yet read), so a
  # `status --wait` pass in between compares its edits with its own `created_at` and skips the unedited post
  core.save_foreman(st, unit, data)
  if url:  # the session's own post: its time is GitHub's creation time, read back, so any edit since (one before the
    # read-back too) reads as an edit after the record; a failed read-back leaves the entry `unread`
    created = read_back(st, cid).get("created_at")
    if created:
      for entry in entries:
        entry.pop("unread", None)
        entry["posted_at"] = created
      core.save_foreman(st, unit, data)
  for d in decisions:
    if found:
      words = " ".join(w for w in (found.kind, found.subject, found.option) if w)
      core.journal(st, f"Ruling ({args.by}, comment {args.posted}): {unit} {d['id']} {words}" + (f" — {found.reason}" if found.reason else ""))
    else:
      who = f"judges {args.by[7:]}, {judges_word(card.get('mode'))}" if args.by.startswith("judges:") else args.by
      typed = args.ruling + (f" — {reason}" if reason and " — " not in args.ruling else "")  # a defaulted reason
      core.journal(st, f"Ruling ({who}): {unit} {d['id']} {typed}")
  if stops:
    core.journal(st, f"{unit} stopped by {args.by}: {chosen}")
  word = settle_ruled(st, settles, args, card)  # the ruling is recorded: the finding it rules is settled (U103)
  print(url or f"recorded ({posted})")
  if word:  # the round's rewritten word, as `review settle` prints it
    print(word)
  return 0


def fifth_point(st, unit: str, decision: dict, chosen: str, runcard: str) -> None:
  """A head's fifth point ruled (U35): `accept` is `review rule --ruling accept --owner --decision <id>` on the
  unit's head review, in-process (its refusal is raised as `review rule`'s own; it writes the round's `clean` with its
  awaiting-merge line), else the round's word `revise` (no point-3 relaunch spent). An accept `review rule` typed
  alone already gave is recorded here, not given twice."""
  rid = review.head_review_id(st, unit)
  if rid is None:
    raise Refusal(f"decision: {unit} has no head review")
  head = review.load_review(st, rid)
  done = review.evaluate(st, head, runcard)
  # a rerun after a failed post, or an accept `review rule` gave: it stands, and is not given twice
  given = done.converged.startswith("by ruling") and str(done.converged_round) == decision["source"].split()[-1]
  if chosen == "accept" and not given:
    with contextlib.redirect_stdout(io.StringIO()):
      review.rule_review(argparse.Namespace(review=rid, ruling="accept", owner=True, judges=None, posted=None,
                                            decision=decision["id"], runcard=runcard, unit=None, design=None, plan=None))
  elif chosen == "accept":
    try:  # the rerun binds the reviewed head as the first call did
      review.refuse_moved_head(st, rid, head, decision["id"])
    except core.HandoffError:  # refused: the accept the failed call gave is withdrawn, the round's word `revise`
      withdraw_accept(st, rid, head, runcard)
      review.write_head_outcome(st, review.load_review(st, rid), runcard, outcome="revise")
      raise
  elif given:  # `revise` after an accept whose post failed: the accept is withdrawn, journaled as a lapse
    withdraw_accept(st, rid, head, runcard)
  outcome = "clean" if chosen == "accept" else "revise"  # an accept's `clean` is `review rule`'s, written once
  posted = [e for e in core.load_foreman(st, unit)["rounds"] if e.get("phase") == "posted"]
  if not (posted and max(posted, key=lambda e: e["round"]).get("outcome") == outcome):
    review.write_head_outcome(st, review.load_review(st, rid), runcard, outcome=outcome)


def withdraw_accept(st, rid: str, head: dict, runcard: str) -> None:
  """The accept a call whose post failed gave, withdrawn: the review's verdict re-derived without it,
  journaled as a lapse, `review <id> R<n> accept lapsed`)."""
  accepted = head["converged"].removeprefix("by ruling ")
  head["converged"], head["converged_round"] = "no", None
  review.store_verdict(st, rid, head, runcard)
  core.journal(st, f"review {rid} {accepted} accept lapsed under {runcard}")


def deferral_of(foreman: dict, fid: str):
  """The latest `followups[]` row of a triage-deferred fid (spec section 5.2), or None."""
  return next((r for r in reversed(foreman.get("followups") or []) if r.get("fid") == fid), None)


def refuse_undo(st, unit: str, data: dict, row: dict, args) -> None:
  """The undo's refusals (spec section 5.2), checked before anything is written, so the follow-up row stays: a
  deferral of an earlier round than the unit's latest posted one, a stopped unit (`foreman.stopped`, or the stopped
  label on its issue), and a pull request merged or closed (its state read now)."""
  posted = [e["round"] for e in data.get("rounds") or [] if e.get("phase") == "posted"]
  why = None
  if row["round"] != max(posted, default=None):
    why = f"{row['fid']} was deferred in round {row['round']}, not the latest posted round"
  elif data.get("stopped"):
    why = f"{unit} is stopped"
  else:
    state = core.load_state(st.root)
    record = state["units"][unit]
    pr = (record.get("pr") or {}).get("number")
    if labelled_stopped(st, record["number"]):
      why = f"{unit} is stopped (issue #{record['number']} labelled {st.config['labels']['stopped']})"
    elif pr and (pr_state := core.gh_json(["pr", "view", str(pr), "-R", st.config["repo"], "--json", "state"]).get("state")) != "OPEN":
      why = f"pull request #{pr} is {pr_state.lower()}"
  if why:
    core.journal(st, f"undo refused ({args.by}, comment {args.posted}): {why}; follow-up {row['fid']} kept")
    raise Refusal(f"decision: undo refused: {why}; the follow-up row stays")


def undo(st, unit: str, data: dict, args, comment: dict, found: "Ruling", now: str) -> int:
  """The owner's `**Ruling:** <fid> finding upheld` on a triage-deferred medium of the unit's latest posted round
  (spec section 5.2), applied with no dispatch and no `collect`: the finding's disposition cleared and `undone_by` its
  comment id, a standalone `kind: undo` ruling (`decision: null`), the follow-up row dropped, the latest posted
  round's outcome rewritten, and triage off for the unit's remaining rounds (`review.triage_undone`)."""
  said = f"{found.subject} finding upheld"
  if args.ruling.partition(" — ")[0].strip() != said:
    raise Refusal(f"decision: comment {args.posted} rules {said}, not {args.ruling.strip()}")
  row = deferral_of(data, found.subject)
  refuse_undo(st, unit, data, row, args)
  rid = review.head_review_id(st, unit)
  rnd = review.load_round(st, rid, row["round"])
  finding = next(f for f in review.findings_of(rnd) if f["id"] == found.subject)
  finding["disposition"], finding["undone_by"] = None, str(args.posted)
  core.atomic_write(st.path("reviews", rid, f"round-{row['round']}.json"), rnd)
  # the outcome rewritten before the ruling is recorded: a stop in between leaves the follow-up row and no record,
  # so the same `decision rule --posted` reruns and completes the undo (both writes are idempotent)
  review.undo_outcome(st, rid, args.runcard)
  data = core.load_foreman(st, unit)
  data["rulings"].append({"kind": "undo", "decision": None, "fid": found.subject, "by": args.by,
                          "posted": f"comment {args.posted}", "ruling": args.ruling,
                          "posted_at": comment.get("updated_at") or comment.get("created_at") or now, "at": now})
  data["followups"] = [r for r in data.get("followups") or [] if r.get("fid") != found.subject]
  core.save_foreman(st, unit, data)
  core.journal(st, f"Ruling ({args.by}, comment {args.posted}): {unit} undo {found.subject} deferred by triage; "
                   f"triage off for {unit}")
  print(f"recorded (comment {args.posted}): undo {found.subject}")
  return 0


KIND_POINTS = {"upheld": (1,), "overruled": (1,), "allowed": (1,), "allowed-file": (1,), "round": (2,), "stop": (2,), "option": (3, 5), "redesign": (1, 2)}


def dropped(store, args, reason: str):
  """Refuse a ruling that names no open decision or a ruled one; a by-hand one is journaled as dropped."""
  if args.posted and not args.posted.startswith("closed:"):
    core.journal(store, f"ruling dropped ({args.by}, comment {args.posted}): {reason}")
  raise Refusal(f"decision: {reason}")


def read_back(store, comment_id) -> dict:
  """The comment by its id (`rule` stores a session post's `created_at` as the record's `posted_at`, and marks the
  entry `unread: true` when it is missing); {} when GitHub does not return it."""
  try:
    return core.gh_json(["api", f"repos/{store.config['repo']}/issues/comments/{comment_id}"]) or {}
  except core.GhError:
    return {}


def rule_file(st, unit: str, data: dict, args, comment: dict, found, decisions: list, card: dict) -> int:
  """The owner's by-hand `**Ruling:** test-delta <file> allowed — <reason>` (spec section 11.1), all on the comment:
  first the whole-file `test-delta <file> allowed` entry itself (which `recorded_rulings`, and `collect`'s allowed
  files through it, keep after the comment is edited or deleted), then one entry per unruled `test-delta:` finding
  of that file each of `decisions` asks about: `<fid> allowed` on an `owner: <ids>` decision, `<copy fid> finding
  overruled` on a decision about a contest copy (options upheld or overruled). `--ruling` must be the comment's own
  `test-delta <file> allowed`."""
  said = f"test-delta {found.subject} allowed"
  if args.ruling.partition(" — ")[0].strip() != said:
    raise Refusal(f"decision: comment {args.posted} rules {said}, not {args.ruling.partition(' — ')[0].strip()}")
  ids = {d["id"] for d in decisions}
  targets = [(d, fid) for d, fid in file_targets(data, found.subject, st) if d["id"] in ids]
  if not targets:
    dropped(st, args, f"comment {args.posted} names no open finding of {found.subject}")
  settles = settle_checks(st, targets, args, card)  # U103: each finding of the file is settled once recorded; the checks come first
  posted_at = comment.get("updated_at") or comment.get("created_at") or core.now_iso()
  entry = lambda d, text: {"decision": d["id"], "ruling": text, "by": args.by, "reason": found.reason or None,
                           "posted": f"comment {args.posted}", "posted_at": posted_at}
  # the whole-file allowance itself first, so `recorded_rulings` keeps it after the comment is edited or deleted
  # a contest copy's decision (options upheld or overruled) takes the allowance as `<fid> finding overruled`, as `rule` does
  allowed = lambda d, fid: f"{fid} allowed" if f"{fid} allowed" in (d.get("options") or []) else f"{fid} finding overruled"
  data["rulings"] += [entry(targets[0][0], said)] + [entry(d, allowed(d, fid)) for d, fid in targets]
  core.save_foreman(st, unit, data)
  for d, fid in targets:
    core.journal(st, f"Ruling ({args.by}, comment {args.posted}): {unit} {d['id']} allowed-file {found.subject} {fid}"
                     + (f" — {found.reason}" if found.reason else ""))
  word = settle_ruled(st, settles, args, card)
  print(f"recorded (comment {args.posted})")
  if word:
    print(word)
  return 0


def by_position(options: list, text: str, by: str) -> bool:
  """Point 3: a bare `(x)` is the letter of its position in the rendered question: always the judges' (they see letters
  by position), the owner's only where no stored option's own prefix carries it (the owner reads the comment's letters)."""
  return bool(LETTER_RE.fullmatch(text)) and (by.startswith("judges:") or not any(o.startswith(text + " ") for o in options))


def check_ruling(point: int, options: list, ruling: str, by: str = "") -> str:
  """The option `ruling` names (its letter, its text, or both; point 1 as `<fid> <option>`), resolved
  to the option's text; refused when it is none of them. At points 1 and 2 the bare word `redesign` (its ` — <why>`
  is checked by `rule`; no letter, no finding id) is the third ruling, in no option list. An `owner: <ids>`
  decision's options are `<fid> allowed`: a `<fid> allowed` ruling, or `<fid> finding overruled` (read as allowed),
  answers the option carrying its fid, and `<fid> finding upheld` rules that fid upheld (spec section 8: the builder
  restores it, or at the cap point 2 asks); either is refused to the judges, the owner's alone (U25); any other text
  is none of its options."""
  if ruling == "redesign" and point in (1, 2):  # a head's third ruling: no letter, no finding id
    return "redesign"
  fid, _, text = ruling.partition(" ") if point == 1 else ("", "", ruling)
  if point == 3 and by_position(options, text, by):
    place = ord(text[1]) - ord("a")
    if place < len(options):
      text = options[place]
  said = text.partition(" — ")[0].strip()
  if point == 1 and f"{fid} allowed" in options:  # an `owner: <ids>` decision's test-delta fid, a mixed decision's too (U104)
    option = f"{fid} allowed" if said in ("allowed", "finding overruled", "finding upheld") else None
    if option and by.startswith("judges:"):
      raise Refusal(f"decision: {fid} {said} is the owner's alone")  # the ruling the panel gave, not the option it matched
    if option:
      return f"{fid} finding upheld" if said == "finding upheld" else option
  if point == 1 and said == "respec" and f"{fid} respec" in options:  # §7.6: the foreman's spec finding
    if by.startswith("judges:"):
      raise Refusal("decision: respec is the owner's alone")
    return f"{fid} respec"
  if point == 1 and f"{fid} respec" in options and by.startswith("judges:"):  # a spec finding is the owner's alone (U104)
    raise Refusal(f"decision: {fid} {said} is the owner's alone")
  for option in options:
    letter, _, rest = option.partition(" ") if option.startswith("(") else ("", "", option)
    if text and text in (option, letter, rest) and (point != 1 or fid):
      if point == 3 and rest in ("amend", "respec") and by.startswith("judges:"):  # on the option the ruling resolves to, its own `(x) ` prefix dropped
        raise Refusal(f"decision: {rest} is the owner's alone")
      return f"{fid} {rest}" if point == 1 else rest
  extra = ["redesign — <one sentence why>"] if point in (1, 2) else []  # a head's third ruling, in no option list
  raise Refusal("decision: ruling is none of the options: " + "; ".join(options + extra))


def judges_word(mode) -> str:
  """The word the judges' ruling carries: `contest` on a normal-mode card (U88), `leavemealone` on a leavemealone-mode card
  and where no card's mode is given (1.2's word)."""
  return "contest" if mode == "normal" else "leavemealone"


def ruling_comment(point: int, source: str, ruling: str, question: str, brief=None, by: str = "", qid: str = "", mode=None) -> str:
  """Spec section 13.2's `**Ruling:**` form (point 1 `<fid> finding upheld (fix it) | finding overruled — <reason>`,
  point 2 `one more round | stop`, point 3 `(<comment-id>) <option> — <reason>`, `(<qid>)` for a decision opened
  on no comment), the judges' `(judges <panel>, leavemealone | contest)` marker line when `by` is `judges:<panel>` (the word
  `judges_word(mode)` gives, U88), a blank
  line and the quoted question. A redesign ruling (`brief` given) takes the form `**Ruling:** redesign — <why>`,
  the stopped-for-redesign line naming the brief, the close-by-hand line, a blank line and the quoted question."""
  quoted = "\n".join("> " + l for l in question.rstrip("\n").splitlines())
  marker = f"\n(judges {by[7:]}, {judges_word(mode)})" if by.startswith("judges:") else ""
  if brief:  # a redesign ruling: the unit is stopped, the brief named, the owner closes the issue by hand
    return (f"{ruling_line(ruling)}{marker}\n\nStopped for redesign; the brainstorm brief is `{brief}`.\n"
            f"Close this issue by hand once the re-planned unit is filed.\n\n{quoted}\n")
  if point == 1:
    line = ruling.replace("finding upheld", "finding upheld (fix it)", 1)
  elif point == 2:
    line = ruling
  else:  # point 3, and a head's fifth point in the point-3 form over its decision id (U35)
    line = f"({source.removeprefix('comment ') if source.startswith('comment ') else qid}) {ruling}"
  return f"{ruling_line(line)}{marker}\n\n{quoted}\n"


DIFF_WHOLE, DIFF_LINES = 40_000, 200  # a diff under 40 KB is copied whole, else its first 200 lines
ENTRY_RE = re.compile(r"^### .+ comment \S+ by ")


def brief_path(store, unit: str, qid: str) -> Path:
  return store.path("foreman", unit).with_name(f"{unit}-{qid}.brainstorm.md")


def brainstorm_brief(store, unit: str, qid: str, decision: dict, ruling: str, pr) -> Path:
  """Write `foreman/<unit>-<qid>.brainstorm.md` (spec section 11): what the owner asked, the decision's question text verbatim (the findings at point 1),
  the unit body, the latest posted round's diff summary and its builder deviations. Store-only, never committed;
  nothing is read from GitHub."""
  posted = [r["round"] for r in core.load_foreman(store, unit)["rounds"] if r.get("phase") == "posted"]
  folder = store.path("review", unit, pr) / f"r{max(posted)}" if posted and pr else None
  diff = folder / "diff" if folder else None
  raw = diff.read_bytes() if diff and diff.is_file() else b""
  text = raw.decode("utf-8", errors="replace")
  lines = text.splitlines()
  paths = [l.rpartition(" b/")[2] for l in lines if l.startswith("diff --git ")]
  shown = lines if len(raw) < DIFF_WHOLE else lines[:DIFF_LINES]
  comments = folder / "comments.md" if folder else None
  entries, current = [], None
  for line in core.read_text(comments).splitlines() if comments and comments.is_file() else []:
    if ENTRY_RE.match(line):
      current = [line]
      entries.append(current)
    elif current is not None:
      current.append(line)
  deviations = ["\n".join(e).rstrip("\n") for e in entries if len(e) > 1 and e[1].startswith("**Deviation")]
  body = core.unit_file_body(store.path("unit", unit)).splitlines()
  out = ["# What the owner asked", "", ruling, "", "# Findings", "", decision["question"].rstrip("\n"), "",
         "# Unit body", ""] + [("  " + l).rstrip() for l in body] + ["", "# Diff", ""] + (paths or ["(none)"]) \
      + ["", "```diff"] + shown + ["```", "", "# Deviations", "", "\n\n".join(deviations) or "(none)", ""]
  path = brief_path(store, unit, qid)
  core.atomic_write(path, "\n".join(out))
  core.journal(store, f"Brainstorm brief: {path}")
  return path


def verify_posted(store, unit: str, foreman: dict, args, number: int, mode=None):
  """A by-hand `**Ruling:**` (spec section 13.2, U22): honoured only on the unit's issue (`number`), only from the
  author who is `--by`, only when `ruling_of` reads it as a `config.owners` login's form, only once (a recorded
  comment edited later is ignored), and only on the decisions its kind and subject name: `--decision`'s, else the
  latest point-1 decision whose question names the fid (else the latest naming no finding) with no ruling on that
  fid (an `allowed` one: only a decision naming it, recorded as `<fid> finding overruled`), the open point-2 one, the point-3 one on its comment or decision id, or for `redesign` every pending
  decision of the unit. In leavemealone-mode (`mode`) an allowance naming a decision is refused before anything is
  recorded: `review settle --owner --posted` there reads only `<fid> finding overruled — <reason>`, except on an
  `owner: <ids>` decision (every option `<fid> allowed`), where verify_owner_ruling reads the allowance. Returns
  (comment, ruling, decisions)."""
  cid = args.posted
  comment = core.gh_json(["api", f"repos/{store.config['repo']}/issues/comments/{cid}"]) or {}
  issue_url = comment.get("issue_url") or ""
  if issue_url and not issue_url.endswith(f"/issues/{number}"):
    raise Refusal(f"decision: comment {cid} is not on issue #{number}")
  author = (comment.get("user") or {}).get("login")
  if author != args.by:
    raise Refusal(f"decision: comment {cid} was written by {author}, not {args.by}")
  found = ruling_of(comment, store.config.get("owners") or [])
  if found is None:
    raise Refusal(f"decision: comment {cid} by {author} is not an owner's ruling")
  if int(cid) in consumed_comments(foreman):
    recorded = next(r for r in foreman["rulings"] + (foreman.get("proceeds") or []) if r.get("posted") == f"comment {cid}")
    core.journal(store, f"Ruling ({args.by}, comment {cid}): {unit} {recorded.get('decision') or recorded.get('ruling')} ruling edited after record, ignored")
    raise Refusal(f"decision: comment {cid} already recorded (ruling edited after record, ignored)")
  if review.edited_comment(comment):  # edited before its first record: never recorded (U103); an edit after the record is ignored above
    raise Refusal("decision: ruling comment edited: post a new one")
  points = KIND_POINTS.get(found.kind, ())
  point2 = {d["id"] for d in foreman["decisions"] if d["point"] == 2}
  if found.kind == "round" and any(r.get("decision") in point2 and r["ruling"].partition(" — ")[0].strip() == "one more round"
                                   for r in foreman["rulings"]):
    # a head's `one more round` is once per unit (spec section 13.2): refused before anything is recorded, where the
    # typed path's `review rule` refuses `continue already ruled this cycle`
    raise Refusal(f"decision: comment {cid} rules one more round, already spent on {unit}")
  if args.decision:
    decision = next((d for d in foreman["decisions"] if d["id"] == args.decision), None)
    if decision is None:
      raise Refusal(f"decision: {unit} has no decision {args.decision}")
    if decision["point"] not in points:
      raise Refusal(f"decision: comment {cid} rules no point-{decision['point']} decision")
    source = decision["source"]
    if found.kind == "option" and found.subject != option_name(decision):
      raise Refusal(f"decision: comment {cid} does not name {source if source.startswith('comment ') else decision['id']}")
    if found.kind in ("upheld", "overruled", "allowed"):  # the fid must be one of this decision's, and ruled nowhere else
      if decision not in fid_decisions(foreman, found.subject, strict=found.kind == "allowed"):
        raise Refusal(f"decision: comment {cid} rules {found.subject}, not a finding of {decision['id']}")
      if fid_ruled(foreman, found.subject, but=decision["id"]):
        dropped(store, args, f"{found.subject} already ruled")
    if found.kind == "redesign" and decision["id"] not in {d["id"] for d in pending_decisions(foreman)}:
      dropped(store, args, f"{decision['id']} already ruled")  # a redesign rules open decisions alone, as without --decision
    refuse_allowance(store, args, found, [decision], cid, mode)
    if found.kind == "redesign":  # every pending decision at once (spec section 13.2), the named one first: its brief
      return comment, found, [decision] + [d for d in pending_decisions(foreman) if d["id"] != decision["id"]]
    return comment, found, [decision]
  if found.kind == "upheld" and deferral_of(foreman, found.subject):  # the undo, checked before `fid_decisions` (5.2)
    return comment, found, None
  pending = pending_decisions(foreman)
  if found.kind == "allowed-file":  # every open decision with an entry of that file, a contest copy's too (`rule` records each fid)
    decisions = list({d["id"]: d for d, _ in file_targets(foreman, found.subject, store)}.values())
  elif found.kind == "redesign":
    decisions = pending if any(d["point"] in points for d in pending) else []
  elif found.kind in ("upheld", "overruled", "allowed"):
    decisions = [d for d in fid_decisions(foreman, found.subject, strict=found.kind == "allowed") if not fid_ruled(foreman, found.subject)][-1:]
  elif found.kind in ("round", "stop"):
    decisions = [d for d in pending if d["point"] == 2][-1:]
  elif found.kind == "option":
    decisions = [d for d in foreman["decisions"] if d["point"] in (3, 5) and found.subject == option_name(d)][-1:]
  else:
    decisions = []
  if not decisions and found.kind in ("allowed", "allowed-file"):  # an allowance no decision asks about: `collect` reads it
    raise Refusal(f"decision: comment {cid} allows {found.subject}; no open decision names it")
  if not decisions:
    dropped(store, args, f"comment {cid} does not name an open decision")
  refuse_allowance(store, args, found, decisions, cid, mode)
  return comment, found, decisions


def option_name(decision: dict) -> str:
  """The parenthesis a point-3 option ruling names its decision by (spec section 13.2): the comment id of one opened
  on a comment, the decision id of one opened on a launch or a close; never the other, with or without `--decision`."""
  source = str(decision.get("source") or "")
  return source.removeprefix("comment ") if source.startswith("comment ") else decision["id"]


def refuse_allowance(store, args, found: "Ruling", decisions: list, cid, mode) -> None:
  """In leavemealone-mode an allowance naming an open point-1 decision is refused, journaled as dropped (the owner's
  notice, the event being spent): the decision's `review settle --owner --posted` reads only the overrule form. An
  `owner: <ids>` decision (every option `<fid> allowed`, U25) asks for the allowance itself and is never refused."""
  options = (decisions[0].get("options") or []) if decisions else []
  owner_only = options and (all(o.endswith(" allowed") for o in options) or f"{found.subject} allowed" in options)  # a mixed decision's too (U104)
  if found.kind == "allowed" and decisions and mode == "leavemealone" and not owner_only:
    dropped(store, args, f"comment {cid} allows {found.subject}; in leavemealone-mode {decisions[0]['id']} takes "
                         f"`**Ruling:** {found.subject} finding overruled — <reason>`")


# A finding id, `<reviewer>-<round>-<n>`, an external one `external:<login>-<round>-<n>` (a login may carry `[bot]`)
FID_PAT = r"[a-z][\w:\[\]-]*-\d+-\d+"
# A finding line of a point-1 question: `<fid> | <severity> | …`, or the question file's `## Q<n> <fid> (<severity>, …`;
# a line merely starting `<fid> (` (a quoted original) is not one
FINDING_LINE_RE = re.compile(rf"^(?:#+\s+Q\d+\s+({FID_PAT})\s+\(|({FID_PAT})\s*\|)", re.M)
Q_LINE_RE = re.compile(rf"^#+\s+Q\d+\s+(?P<fid>{FID_PAT})\s+\([^)]*\):\s*(?P<claim>.*)$")  # a `## Q<n> <fid> (…): <claim>` line


def fid_decisions(foreman: dict, fid: str, strict: bool = False) -> list:
  """The point-1 decisions a finding id belongs to: those with a finding line starting with it (`<fid> |` or
  `## Q<n> <fid> (`; a fid a claim or a reason quotes is not the question's), else (not `strict`) the latest
  point-1 decision with no finding line at all; never one asking about others."""
  point1 = [d for d in foreman["decisions"] if d["point"] == 1]
  asked = lambda d: {a or b for a, b in FINDING_LINE_RE.findall(d.get("question") or "")}
  named = [d for d in point1 if fid in asked(d)]
  return named or ([] if strict else [d for d in point1 if not asked(d)][-1:])


def file_targets(foreman: dict, path: str, st=None) -> list:
  """`(decision, fid)` for every unruled `test-delta:` finding of `path` an open point-1 decision asks about: an
  `owner: <ids>` decision's (each option `<fid> allowed`) by its finding line's claim, and any other's contest copy
  (`contested <fid>: …`) whose original, reached down the chain in the decision's review (`st`'s record,
  `review.delta_claim`), is one: what `**Ruling:** test-delta <path> allowed — <reason>` rules at once (spec
  sections 8 and 11.1: every open decision whose `test_delta` entry is in that file). A point-1 decision takes one
  ruling per finding, so it is open on each fid not yet ruled, whatever `pending_decisions` says once its first
  ruling is recorded; a `redesign` closes it whole."""
  line = re.compile(rf"^({FID_PAT})\s*\|.*\|\s*test-delta: {re.escape(path)}:\d+ ", re.M)
  redesigned = {r.get("decision") for r in foreman.get("rulings") or [] if str(r.get("ruling") or "").startswith("redesign")}
  out = []
  for d in foreman.get("decisions") or []:
    options = d.get("options") or []
    if d["point"] != 1 or not options or d["id"] in redesigned:
      continue
    if any(o.endswith(" allowed") for o in options):  # an `owner: <ids>` decision, a mixed one's `<fid> allowed` too (U104)
      out += [(d, fid) for fid in line.findall(d.get("question") or "")
              if f"{fid} allowed" in options and not fid_ruled(foreman, fid)]
    elif st is not None and str(d.get("source") or "").startswith("review "):
      rid = d["source"].split()[1]
      for fid in dict.fromkeys(a or b for a, b in FINDING_LINE_RE.findall(d.get("question") or "")):
        try:
          claim = review.locate_finding(st, rid, fid)[3]["claim"]
        except core.HandoffError:
          continue
        if (claim != (original := review.delta_claim(st, rid, claim)) and original.startswith(f"test-delta: {path}:")
            and not fid_ruled(foreman, fid)):
          out.append((d, fid))
  return out


def fid_ruled(foreman: dict, fid: str, but: str = "") -> bool:
  """Whether a point-1 ruling on `fid` is recorded on any decision but `but` (the one `rule` checks itself)."""
  point1 = {d["id"] for d in foreman["decisions"] if d["point"] == 1} - {but}
  return any(r.get("decision") in point1 and r["ruling"].partition(" — ")[0].strip().split(" ")[0] == fid
             for r in foreman["rulings"])
