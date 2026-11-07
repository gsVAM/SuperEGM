# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the decision subcommand (spec sections 7, 11 and 13.2): every point-1/2/3
# question and ruling of a unit, the by-hand BLOCKED ruling and the owner's close as `stop`; the redesign ruling
# (spec section 11.1) and the store-only brainstorm brief it writes; the one ruling grammar (`ruling_of`, `ruling_form`,
# `recorded_rulings`) and the by-hand ruling read through it (U22).

"""superegm decision open|rule: record a unit's question (`decisions[]`) and its ruling (`rulings[]`)."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import superegm as core
from superegm.apply import body_file
from superegm.report import pending_decisions, unit_view
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
  bare = text in ("one more round", "stop") or text.endswith(" finding upheld")
  return f"**Ruling:** {text}" + ("" if bare else " — <reason>")


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
  or a third `blocked` comment on the same head."""
  if point == 1:
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
  core.gh(["issue", "edit", str(number), "-R", store.config["repo"], "--add-label", store.config["labels"]["stopped"]])
  data = core.load_foreman(store, uid)
  data["stopped"] = {"by": by, "reason": reason, "at": now_iso} | ({"brief": str(brief)} if brief else {})
  core.save_foreman(store, uid, data)
  core.journal(store, f"{uid} stopped by {by}: {reason}")


def rule(args) -> int:
  core.require_runcard(args, SKILLS)
  st = core.store(core.git_toplevel(Path.cwd()))
  state, unit, now = core.load_state(st.root), args.unit, core.now_iso()
  if unit not in (state.get("units") or {}):
    raise Refusal(f"decision: {unit} is not a unit of this handoff")
  number, closed = state["units"][unit]["number"], (args.posted or "").partition("closed:")[2]
  if not args.decision and not (args.posted and not closed):
    if not closed:
      raise Refusal("decision: --decision is required unless --posted closed:<n>")
    stop_unit(st, unit, args.by, f"closed #{closed} by {args.by}", number, now)
    print(f"recorded (closed #{closed})")
    return 0
  data = core.load_foreman(st, unit)
  head, _, reason = args.ruling.partition(" — ")
  found = comment = None
  if args.posted and not closed:  # a by-hand ruling: read through the one grammar (spec section 13.2, U22)
    comment, found, decisions = verify_posted(st, unit, data, args)
  else:
    decision = next((d for d in data["decisions"] if d["id"] == args.decision), None)
    if decision is None:
      raise Refusal(f"decision: {unit} has no decision {args.decision}")
    decisions = [decision]
  # Point 1 takes one ruling per contested finding (`<fid> finding upheld | overruled`, the leavemealone row's
  # "one call per finding"); the other points take one ruling.
  fid_of = lambda text: text.partition(" — ")[0].strip().split(" ")[0]
  for decision in decisions:
    ruled = [r for r in data["rulings"] if r["decision"] == decision["id"]]
    if ruled and (decision["point"] != 1 or any(fid_of(r["ruling"]) == fid_of(head) for r in ruled)):
      dropped(st, args, f"{decision['id']} already ruled")
  decision = decisions[0]
  chosen = [check_ruling(d["point"], d["options"], head.strip()) for d in decisions][0]
  brief = None
  if found:
    reason = found.reason or ""
  elif not reason.strip() and (decision["point"] == 3 or chosen.endswith(" finding overruled")):
    reason = "ruled in the session"  # a session ruling typed without the reason its form carries
  if chosen == "redesign":
    if not reason.strip():
      raise Refusal("decision: redesign needs — <one sentence why>")
    chosen = f"redesign — {reason.strip()}"
    brief = brief_path(st, unit, decision["id"])  # written after the comment is posted: a refusal leaves no brief
  posted_at, url = now, None
  if closed:
    posted = f"closed #{closed}"
  elif found:
    posted, posted_at = f"comment {args.posted}", comment.get("created_at") or now
  else:
    body = ruling_comment(decision["point"], decision["source"], chosen + (f" — {reason}" if reason and not brief else ""),
                          decision["question"], brief, args.by, decision["id"])
    path = body_file(body, st.root)
    try:
      url = core.gh(["issue", "comment", str(number), "-R", st.config["repo"], "--body-file", path]).strip()
    finally:
      os.unlink(path)
    cid = url.rsplit("-", 1)[1]
    posted, posted_at = f"comment {cid}", read_back(st, cid).get("created_at") or now
  if brief:
    brainstorm_brief(st, unit, decision["id"], decision, chosen, (state["units"][unit].get("pr") or {}).get("number"))
  for d in decisions:
    data["rulings"].append({"decision": d["id"], "ruling": args.ruling, "by": args.by,
                            "reason": reason.strip() or None, "posted": posted, "posted_at": posted_at})
  core.save_foreman(st, unit, data)
  for d in decisions:
    if found:
      words = " ".join(w for w in (found.kind, found.subject, found.option) if w)
      core.journal(st, f"Ruling ({args.by}, comment {args.posted}): {unit} {d['id']} {words}" + (f" — {found.reason}" if found.reason else ""))
    else:
      who = f"judges {args.by[7:]}, leavemealone" if args.by.startswith("judges:") else args.by
      typed = args.ruling + (" — ruled in the session" if reason == "ruled in the session" else "")
      core.journal(st, f"Ruling ({who}): {unit} {d['id']} {typed}")
  if chosen.startswith("stop") or brief:
    stop_unit(st, unit, args.by, chosen, number, now, brief)
  print(url or f"recorded ({posted})")
  return 0


KIND_POINTS = {"upheld": (1,), "overruled": (1,), "round": (2,), "stop": (2,), "option": (3,), "redesign": (1, 2)}


def dropped(store, args, reason: str):
  """Refuse a ruling that names no open decision or a ruled one; a by-hand one is journaled as dropped."""
  if args.posted and not args.posted.startswith("closed:"):
    core.journal(store, f"ruling dropped ({args.by}, comment {args.posted}): {reason}")
  raise Refusal(f"decision: {reason}")


def read_back(store, comment_id) -> dict:
  """The comment by its id (`created_at` is the record's `posted_at`); {} when GitHub does not return it."""
  try:
    return core.gh_json(["api", f"repos/{store.config['repo']}/issues/comments/{comment_id}"]) or {}
  except core.GhError:
    return {}


def check_ruling(point: int, options: list, ruling: str) -> str:
  """The option `ruling` names (its letter, its text, or both; point 1 as `<fid> <option>`), resolved
  to the option's text; refused when it is none of them. At points 1 and 2 the bare word `redesign` (its ` — <why>`
  is checked by `rule`; no letter, no finding id) is the third ruling, in no option list."""
  if ruling == "redesign" and point in (1, 2):  # a head's third ruling: no letter, no finding id
    return "redesign"
  fid, _, text = ruling.partition(" ") if point == 1 else ("", "", ruling)
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


def verify_posted(store, unit: str, foreman: dict, args):
  """A by-hand `**Ruling:**` (spec section 13.2, U22): honoured only from the author who is `--by`, only when
  `ruling_of` reads it as a `config.owners` login's form, only once (a recorded comment edited later is ignored),
  and only on the decisions its kind and subject name: `--decision`'s, else the latest point-1 decision with no
  ruling on its fid, the open point-2 one, the point-3 one on its comment or decision id, or for `redesign` every
  pending decision of the unit. Returns (comment, ruling, decisions)."""
  cid = args.posted
  comment = core.gh_json(["api", f"repos/{store.config['repo']}/issues/comments/{cid}"]) or {}
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
  if args.decision:
    decision = next((d for d in foreman["decisions"] if d["id"] == args.decision), None)
    if decision is None:
      raise Refusal(f"decision: {unit} has no decision {args.decision}")
    if decision["point"] not in points:
      raise Refusal(f"decision: comment {cid} rules no point-{decision['point']} decision")
    source = decision["source"]
    named = source.removeprefix("comment ") if source.startswith("comment ") else decision["id"]
    if found.kind == "option" and found.subject != named:
      raise Refusal(f"decision: comment {cid} does not name {source if source.startswith('comment ') else decision['id']}")
    return comment, found, [decision]
  pending = pending_decisions(foreman)
  fid_of = lambda text: text.partition(" — ")[0].strip().split(" ")[0]
  if found.kind == "redesign":
    decisions = pending if any(d["point"] in points for d in pending) else []
  elif found.kind in ("upheld", "overruled"):
    decisions = [d for d in foreman["decisions"] if d["point"] == 1 and not any(
        r["decision"] == d["id"] and fid_of(r["ruling"]) == found.subject for r in foreman["rulings"])][-1:]
  elif found.kind in ("round", "stop"):
    decisions = [d for d in pending if d["point"] == 2][-1:]
  elif found.kind == "option":
    decisions = [d for d in foreman["decisions"] if d["point"] == 3 and found.subject in (d["id"], d["source"].removeprefix("comment "))][-1:]
  else:
    decisions = []
  if not decisions:
    dropped(store, args, f"comment {cid} does not name an open decision")
  return comment, found, decisions
