# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the decision subcommand (spec sections 7, 11 and 13.2): every point-1/2/3
# question and ruling of a unit, the by-hand BLOCKED ruling and the owner's close as `stop`; the redesign ruling
# (spec section 11.1) and the store-only brainstorm brief it writes; the one ruling grammar (`ruling_of`, `ruling_form`,
# `recorded_rulings`) and the by-hand ruling read through it (U22); a judges' redesign needs a high finding behind it (U23); an `owner: <ids>` decision's `<fid> allowed` options, the owner's alone (U25).

"""superegm decision open|rule: record a unit's question (`decisions[]`) and its ruling (`rulings[]`)."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import superegm as core
from superegm.apply import body_file
from superegm.report import pending_decisions, unit_view
from superegm import review
from superegm.review import Refusal

WRITES = frozenset({"foreman"})  # the store kinds this subcommand writes
SKILLS = frozenset({"wave"})  # the skills whose card this subcommand accepts
RELAUNCH = ["relaunch", "stop the unit"]

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
)
JUDGES_MARK_RE = re.compile(r"^\(judges \S+, leavemealone\)$", re.M)


@dataclass(frozen=True)
class Ruling:
  kind: str  # upheld | overruled | round | stop | option | allowed | allowed-file | redesign
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
  judges' post (the `(judges <panel>, leavemealone)` marker on any line, recorded from `rulings[]`, never re-read)."""
  login = (comment.get("user") or {}).get("login") or comment.get("login")
  body = comment.get("body") or ""
  if login not in owners or JUDGES_MARK_RE.search(body.replace("\r", "")):
    return None
  form = parse_form(body)
  return form and Ruling(*form, login=login, comment_id=int(comment["id"]))


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
  return f"**Ruling:** {text}" + ("" if bare else " — <reason>")


def recorded_rulings(foreman: dict) -> list:
  """One `Ruling` per `rulings[]` entry joined to its decision (the record a session, the judges or a by-hand
  ruling leaves): `redesign` by its text; point 1 the fid and `upheld | overruled`; point 2 `round | stop`;
  point 3 `option` on the source's comment id, else the decision id, the entry's leading token its option."""
  decisions = {d["id"]: d for d in foreman.get("decisions") or []}
  out = []
  for entry in foreman.get("rulings") or []:
    decision = decisions.get(entry.get("decision"))
    if decision is None:
      continue
    text = (entry.get("ruling") or "").partition(" — ")[0].strip()
    posted = entry.get("posted") or ""
    cid = int(posted.split()[1]) if posted.startswith("comment ") and posted.split()[1].isdigit() else 0
    option, subject = None, ""
    if text == "redesign" and decision["point"] in (1, 2):  # a head's third ruling; a point-3 option may begin with the word
      kind = "redesign"
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


def binding_rulings(comments: list, owners: list, recorded: list, decisions=None, pending=None) -> list:
  """The rulings that bind (spec section 13.2: a recorded ruling is never changed by a later comment): the record's
  (`recorded`, as `recorded_rulings` reads it), then each owner's form comment `ruling_of` reads whose comment id
  the record does not hold and whose fid or option subject the record does not already rule; an option ruling binds
  only when it is one of the options its decision offers (`decisions`, else the named comment's `- (` lines and
  `stop the unit`), as `decision rule` would accept it, with two exceptions `offered` names: an option naming a
  comment id this issue lacks binds unchecked (an interface ruling copied from its producer's issue, which
  `decision rule` drops here as naming no open decision, and which a mistyped id cannot be told apart from), and an
  option on a named comment with no `- (` lines binds whatever its text. Given `pending` (the open decisions, `pending_decisions`),
  an unrecorded `one more round` or `stop` binds only while a point-2 decision is open and a `redesign` only while
  a head's (point 1 or 2) is: otherwise `decision rule` drops it, and at point 3 a redesign is text. Once a point-1
  question exists, an unrecorded `finding upheld` binds only on a fid one asks about (`fid_decisions`, whose
  fallback, the latest point-1 decision with no finding line, asks about any fid), as `decision rule` would record
  it. Before any point-1 question an upheld fid binds as the landed `collect` read it, and a `finding overruled`
  always binds: section 13.2 reads an overrule on a `tdd-order`, `test-delta` or `dod-<n>` fid that no decision asks
  about as an allowance, which `collect` applies without a record."""
  recorded = list(recorded)
  point3 = [d for d in decisions or [] if d.get("point") == 3]
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
                     and r.comment_id not in ids and key(r) not in keys and open_for(r) and asked_for(r)
                     and (r.kind != "option" or offered(r, comments, decisions or []))]


def offered(r: "Ruling", comments: list, decisions: list) -> bool:
  """Whether an option ruling names one of its decision's options (`check_ruling` at point 3), except where there
  is nothing to check it against: a numeric id this issue's comments lack (a ruling copied from a producer's
  issue, or a mistyped id: both bind, unchecked) and a named comment with no `- (` lines (any option binds); a
  decision id the record lacks binds nothing."""
  decision = next((d for d in decisions if d.get("point") == 3 and r.subject == option_name(d)), None)
  if decision is not None:
    options = decision.get("options") or []
  else:
    named = next((c for c in comments if str(c.get("id")) == r.subject), None)
    if named is None:  # a comment id this issue lacks: an interface ruling copied from its producer's issue (spec
      return r.subject.isdigit()  # section 13.2), nothing here to check it against; a decision id it lacks binds nothing
    lines = [line[2:].strip() for line in (named.get("body") or "").splitlines() if line.startswith("- (")]
    if not lines:  # a comment with no option lines (a kind-`other` deviation): nothing to check the option against
      return True
    options = lines + ["stop the unit"]
  try:
    check_ruling(3, options, r.option or "")
  except Refusal:
    return False
  return True


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
  decisions = foreman.get("decisions") or []
  bound = {r.comment_id for r in binding_rulings(comments, owners, recorded_rulings(foreman), decisions,
                                                 pending_decisions({"decisions": decisions, "rulings": foreman.get("rulings") or []}))}
  out = {}
  for c in comments:
    entry = entries.get(f"comment {c['id']}")
    if entry:
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
  out = {}
  for entry in foreman.get("rulings") or []:
    cid = str(entry.get("posted") or "").removeprefix("comment ")
    if str(entry.get("posted") or "").startswith("comment ") and cid.isdigit() and int(cid) not in live and int(cid) not in out:
      out[int(cid)] = {"id": int(cid), "user": {"login": entry.get("by")},
                       "body": record_text(foreman, entry, "the comment was deleted after its record")}
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


def record_text(foreman: dict, entry: dict, note: str = "the comment was edited after its record") -> str:
  """A `rulings[]` entry as its form, marked as the record (what an edited or deleted recorded comment is replaced by)."""
  decision = next((d for d in foreman.get("decisions") or [] if d["id"] == entry.get("decision")), {})
  text, reason = (entry.get("ruling") or "").partition(" — ")[0].strip(), entry.get("reason")
  source, point = str(decision.get("source") or ""), decision.get("point")
  if point == 3:
    text = recorded_option(foreman, entry) or text
    text = f"({source.removeprefix('comment ') if source.startswith('comment ') else decision.get('id')}) {text}"
  bare = point == 2 and text != "redesign" or point == 1 and text.endswith(" finding upheld")
  return (f"**Ruling:** {text}" + (f" — {reason}" if reason and not bare else "")
          + f"\n(as recorded by {entry.get('by')}; {note})")


def register(subparsers):
  p = subparsers.add_parser("decision", help="decision open|rule")
  action = p.add_subparsers(dest="action", required=True)
  o = core.add_parser(action, "open", "record a point-1/2/3 question and print its id and options")
  o.add_argument("--unit", required=True)
  o.add_argument("--point", type=int, choices=(1, 2, 3), required=True)
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
  used = any(r["ruling"].partition(" — ")[0].strip() == "relaunch" for r in data["rulings"])
  ruled = options == RELAUNCH and used
  if ruled:
    data["rulings"].append({"decision": qid, "ruling": "stop the unit", "by": "superegm",
                            "reason": "relaunch already used", "posted": None, "posted_at": now})
  core.save_foreman(st, unit, data)
  core.journal(st, f"Decision {qid} (point {args.point}, {args.source}): {unit}")
  print(qid)
  if ruled:
    core.journal(st, f"Ruling (superegm): {unit} {qid} stop the unit — relaunch already used")
    stop_unit(st, unit, "superegm", "stop the unit", state["units"][unit]["number"], now)
    print("ruled: stop the unit (relaunch already used)")
  else:
    print("options: " + "; ".join(options))
  return 0


def options_for(point: int, source: str, question: str, foreman: dict, head: str) -> list:
  """Spec section 13.2's options: point 1 upheld|overruled; point 2 one more round|stop; point 3 the
  comment's own `- (a)` lines plus `stop the unit`, or `relaunch; stop the unit` for a launch, a close,
  or a third `blocked` comment on the same head. Point 1 on an `owner: <ids>` word (the latest posted round's
  outcome) offers `<fid> allowed`, one per id the question names (U25)."""
  if point == 1:
    posted = [e for e in foreman.get("rounds") or [] if e.get("phase") == "posted"]
    word = str(posted[-1].get("outcome") or "") if posted else ""
    if word.startswith("owner: "):
      named = [f"{fid} allowed" for fid in word[len("owner: "):].split(", ") if re.search(rf"(?<!\S){re.escape(fid)}(?!\S)", question)]
      if named:
        return named
    return ["finding upheld", "finding overruled"]
  if point == 2:
    return ["one more round", "stop"]
  if source.startswith("comment"):
    same = [d for d in foreman.get("decisions") or []
            if d.get("point") == 3 and str(d.get("source", "")).startswith("comment") and d.get("head") == head]
    if len(same) < 2:
      return [line[2:].strip() for line in question.splitlines() if line.startswith("- (")] + ["stop the unit"]
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


def stopped_entry(by: str, reason: str, now_iso: str, brief=None) -> dict:
  return {"by": by, "reason": reason, "at": now_iso} | ({"brief": str(brief)} if brief else {})


def high_behind(st, unit: str, source: str) -> bool:
  """A `high` finding with no disposition in the unit's latest posted round of the review the decision's source
  names (its second word): what a judges' `redesign` needs behind it."""
  words = (source or "").split()
  posted = [e["round"] for e in core.load_foreman(st, unit)["rounds"] if e.get("phase") == "posted"]
  rnd = review.load_round(st, words[1], max(posted)) if len(words) > 1 and posted else None
  return bool(rnd) and any(f["severity"] == "high" and f["disposition"] is None for f in review.findings_of(rnd))


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
  else:
    decision = next((d for d in data["decisions"] if d["id"] == args.decision), None)
    if decision is None:
      raise Refusal(f"decision: {unit} has no decision {args.decision}")
    decisions = [decision]
  # Point 1 takes one ruling per contested finding (`<fid> finding upheld | overruled`, the leavemealone row's
  # "one call per finding"), keyed on the comment's fid on a by-hand ruling; the other points take one ruling.
  fid_of = lambda text: text.partition(" — ")[0].strip().split(" ")[0]
  fid = found.subject if found and found.kind in ("upheld", "overruled", "allowed") else fid_of(head)
  for d in decisions:
    ruled = [r for r in data["rulings"] if r["decision"] == d["id"]]
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
  elif not reason.strip() and (decision["point"] == 3 or chosen.endswith((" finding overruled", " allowed"))):
    # a ruling typed without the reason its form carries: the session's, or the panel's, named as such
    reason = f"ruled by judges {args.by[7:]}" if args.by.startswith("judges:") else "ruled in the session"
  if chosen == "redesign" and basis["point"] in (1, 2):  # a head's third ruling; a point-3 option named `redesign` is an option
    if not reason.strip():
      raise Refusal("decision: redesign needs — <one sentence why>")
    if args.by.startswith("judges:") and not high_behind(st, unit, decision["source"]):  # spec section 11.2 (U23)
      raise Refusal(f"decision: redesign by {args.by} needs a high finding behind it")
    chosen = f"redesign — {reason.strip()}"
    brief = brief_path(st, unit, decision["id"])  # written after the comment is posted: a refusal leaves no brief
  # the effect is the point's, never the option's wording: point 2's `stop`, point 3's `stop the unit`, a redesign.
  # The label goes first, so a failed request records nothing and the same call reruns (round 9); a session post
  # that then fails takes off again only a label this call put on (rounds 10 and 11).
  stops = (decision["point"], chosen) in ((2, "stop"), (3, "stop the unit")) or brief
  label = st.config["labels"]["stopped"]
  had = False
  if stops:
    if not (closed or found):  # a session post can fail after the label: know whether it was already on (the owner's close)
      labels = core.gh_json(["issue", "view", str(number), "-R", st.config["repo"], "--json", "labels"]).get("labels") or []
      had = any(l.get("name") == label for l in labels)
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
                          decision["question"], brief, args.by, decision["id"])
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
  entries = [{"decision": d["id"], "ruling": args.ruling, "by": args.by,
              "reason": reason.strip() or None, "posted": posted, "posted_at": posted_at}
             | ({"unread": True} if url else {}) for d in decisions]
  data["rulings"] += entries
  if stops:  # the stop is written with the ruling, in one save
    data["stopped"] = stopped_entry(args.by, chosen, now, brief)
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
      who = f"judges {args.by[7:]}, leavemealone" if args.by.startswith("judges:") else args.by
      typed = args.ruling + (f" — {reason}" if reason and " — " not in args.ruling else "")  # a defaulted reason
      core.journal(st, f"Ruling ({who}): {unit} {d['id']} {typed}")
  if stops:
    core.journal(st, f"{unit} stopped by {args.by}: {chosen}")
  print(url or f"recorded ({posted})")
  return 0


KIND_POINTS = {"upheld": (1,), "overruled": (1,), "allowed": (1,), "round": (2,), "stop": (2,), "option": (3,), "redesign": (1, 2)}


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


def check_ruling(point: int, options: list, ruling: str, by: str = "") -> str:
  """The option `ruling` names (its letter, its text, or both; point 1 as `<fid> <option>`), resolved
  to the option's text; refused when it is none of them. At points 1 and 2 the bare word `redesign` (its ` — <why>`
  is checked by `rule`; no letter, no finding id) is the third ruling, in no option list. An `owner: <ids>`
  decision's options are `<fid> allowed`: any `<fid> <text>` ruling answers the option carrying its fid, and is
  refused to the judges, the owner's alone (U25)."""
  if ruling == "redesign" and point in (1, 2):  # a head's third ruling: no letter, no finding id
    return "redesign"
  fid, _, text = ruling.partition(" ") if point == 1 else ("", "", ruling)
  if point == 1 and options and all(o.endswith(" allowed") for o in options):
    option = next((o for o in options if o.split(" ")[0] == fid and text), None)
    if option and by.startswith("judges:"):
      raise Refusal(f"decision: {option} is the owner's alone")
    if option:
      return option
  for option in options:
    letter, _, rest = option.partition(" ") if option.startswith("(") else ("", "", option)
    if text and text in (option, letter, rest) and (point != 1 or fid):
      return f"{fid} {rest}" if point == 1 else rest
  extra = ["redesign — <one sentence why>"] if point in (1, 2) else []  # a head's third ruling, in no option list
  raise Refusal("decision: ruling is none of the options: " + "; ".join(options + extra))


def ruling_comment(point: int, source: str, ruling: str, question: str, brief=None, by: str = "", qid: str = "") -> str:
  """Spec section 13.2's `**Ruling:**` form (point 1 `<fid> finding upheld (fix it) | finding overruled — <reason>`,
  point 2 `one more round | stop`, point 3 `(<comment-id>) <option> — <reason>`, `(<qid>)` for a decision opened
  on no comment), the judges' `(judges <panel>, leavemealone)` marker line when `by` is `judges:<panel>`, a blank
  line and the quoted question. A redesign ruling (`brief` given) takes the form `**Ruling:** redesign — <why>`,
  the stopped-for-redesign line naming the brief, the close-by-hand line, a blank line and the quoted question."""
  quoted = "\n".join("> " + l for l in question.rstrip("\n").splitlines())
  marker = f"\n(judges {by[7:]}, leavemealone)" if by.startswith("judges:") else ""
  if brief:  # a redesign ruling: the unit is stopped, the brief named, the owner closes the issue by hand
    return (f"**Ruling:** {ruling}{marker}\n\nStopped for redesign; the brainstorm brief is `{brief}`.\n"
            f"Close this issue by hand once the re-planned unit is filed.\n\n{quoted}\n")
  if point == 1:
    line = ruling.replace("finding upheld", "finding upheld (fix it)", 1)
  elif point == 2:
    line = ruling
  else:
    line = f"({source.removeprefix('comment ') if source.startswith('comment ') else qid}) {ruling}"
  return f"**Ruling:** {line}{marker}\n\n{quoted}\n"


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
  recorded: `review settle --owner --posted` there reads only `<fid> finding overruled — <reason>`. Returns
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
  recorded = next((r for r in foreman["rulings"] if r.get("posted") == f"comment {cid}"), None)
  if recorded:
    core.journal(store, f"Ruling ({args.by}, comment {cid}): {unit} {recorded['decision']} ruling edited after record, ignored")
    raise Refusal(f"decision: comment {cid} already recorded (ruling edited after record, ignored)")
  points = KIND_POINTS.get(found.kind, ())
  point2 = {d["id"] for d in foreman["decisions"] if d["point"] == 2}
  if found.kind == "round" and any(r["decision"] in point2 and r["ruling"].partition(" — ")[0].strip() == "one more round"
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
  pending = pending_decisions(foreman)
  if found.kind == "redesign":
    decisions = pending if any(d["point"] in points for d in pending) else []
  elif found.kind in ("upheld", "overruled", "allowed"):
    decisions = [d for d in fid_decisions(foreman, found.subject, strict=found.kind == "allowed") if not fid_ruled(foreman, found.subject)][-1:]
  elif found.kind in ("round", "stop"):
    decisions = [d for d in pending if d["point"] == 2][-1:]
  elif found.kind == "option":
    decisions = [d for d in foreman["decisions"] if d["point"] == 3 and found.subject == option_name(d)][-1:]
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
  notice, the event being spent): the decision's `review settle --owner --posted` reads only the overrule form."""
  if found.kind == "allowed" and decisions and mode == "leavemealone":
    dropped(store, args, f"comment {cid} allows {found.subject}; in leavemealone-mode {decisions[0]['id']} takes "
                         f"`**Ruling:** {found.subject} finding overruled — <reason>`")


# A finding id, `<reviewer>-<round>-<n>`, an external one `external:<login>-<round>-<n>` (a login may carry `[bot]`)
FID_PAT = r"[a-z][\w:\[\]-]*-\d+-\d+"
# A finding line of a point-1 question: `<fid> | <severity> | …`, or the question file's `## Q<n> <fid> (<severity>, …`;
# a line merely starting `<fid> (` (a quoted original) is not one
FINDING_LINE_RE = re.compile(rf"^(?:#+\s+Q\d+\s+({FID_PAT})\s+\(|({FID_PAT})\s*\|)", re.M)


def fid_decisions(foreman: dict, fid: str, strict: bool = False) -> list:
  """The point-1 decisions a finding id belongs to: those with a finding line starting with it (`<fid> |` or
  `## Q<n> <fid> (`; a fid a claim or a reason quotes is not the question's), else (not `strict`) the latest
  point-1 decision with no finding line at all; never one asking about others."""
  point1 = [d for d in foreman["decisions"] if d["point"] == 1]
  asked = lambda d: {a or b for a, b in FINDING_LINE_RE.findall(d.get("question") or "")}
  named = [d for d in point1 if fid in asked(d)]
  return named or ([] if strict else [d for d in point1 if not asked(d)][-1:])


def fid_ruled(foreman: dict, fid: str, but: str = "") -> bool:
  """Whether a point-1 ruling on `fid` is recorded on any decision but `but` (the one `rule` checks itself)."""
  point1 = {d["id"] for d in foreman["decisions"] if d["point"] == 1} - {but}
  return any(r["decision"] in point1 and r["ruling"].partition(" — ")[0].strip().split(" ")[0] == fid
             for r in foreman["rulings"])
