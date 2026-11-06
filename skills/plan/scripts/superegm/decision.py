# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the decision subcommand (spec sections 7, 11 and 13.2): every point-1/2/3
# question and ruling of a unit, the by-hand BLOCKED ruling and the owner's close as `stop`; the redesign ruling
# (spec section 11.1) and the store-only brainstorm brief it writes.

"""superegm decision open|rule: record a unit's question (`decisions[]`) and its ruling (`rulings[]`)."""

import json
import os
import re
from pathlib import Path

import superegm as core
from superegm.apply import body_file
from superegm.launch import app_login
from superegm.report import pending_decisions, unit_view
from superegm.review import Refusal

WRITES = frozenset({"foreman"})  # the store kinds this subcommand writes
SKILLS = frozenset({"wave"})  # the skills whose card this subcommand accepts
RELAUNCH = ["relaunch", "stop the unit"]


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
  r.add_argument("--decision", help="the decision id `open` printed; required unless --posted closed:<n>")
  r.add_argument("--ruling", required=True, help="an option's letter or text, optionally ` — <reason>`")
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
  if not args.decision:
    if not closed:
      raise Refusal("decision: --decision is required unless --posted closed:<n>")
    stop_unit(st, unit, args.by, f"closed #{closed} by {args.by}", number, now)
    print(f"recorded (closed #{closed})")
    return 0
  data = core.load_foreman(st, unit)
  decision = next((d for d in data["decisions"] if d["id"] == args.decision), None)
  if decision is None:
    raise Refusal(f"decision: {unit} has no decision {args.decision}")
  if any(r["decision"] == args.decision for r in data["rulings"]):
    raise Refusal(f"decision: {args.decision} already ruled")
  head, _, reason = args.ruling.partition(" — ")
  chosen = check_ruling(decision["point"], decision["options"], head.strip())
  brief = None
  if chosen == "redesign":
    if not reason.strip():
      raise Refusal("decision: redesign needs — <one sentence why>")
    chosen = f"redesign — {reason.strip()}"
    brief = brief_path(st, unit, args.decision)  # written after the comment is posted: a refusal leaves no brief
  if closed:
    posted = f"closed #{closed}"
  elif args.posted:
    verify_posted(st, st.config, decision, args.posted, args.by)
    posted = f"comment {args.posted}"
  else:
    body = ruling_comment(decision["point"], decision["source"], chosen + (f" — {reason}" if reason and not brief else ""),
                          decision["question"], brief)
    path = body_file(body, st.root)
    try:
      url = core.gh(["issue", "comment", str(number), "-R", st.config["repo"], "--body-file", path]).strip()
    finally:
      os.unlink(path)
    posted = f"comment {url.rsplit('-', 1)[1]}"
  if brief:
    brainstorm_brief(st, unit, args.decision, decision, chosen, (state["units"][unit].get("pr") or {}).get("number"))
  data["rulings"].append({"decision": args.decision, "ruling": args.ruling, "by": args.by,
                          "reason": reason.strip() or None, "posted": posted, "posted_at": now})
  core.save_foreman(st, unit, data)
  who = f"judges {args.by[7:]}, leavemealone" if args.by.startswith("judges:") else args.by
  core.journal(st, f"Ruling ({who}): {unit} {args.decision} {args.ruling}")
  if chosen.startswith("stop") or brief:
    stop_unit(st, unit, args.by, chosen, number, now, brief)
  print(url if posted.startswith("comment") and not args.posted else f"recorded ({posted})")
  return 0


def check_ruling(point: int, options: list, ruling: str) -> str:
  """The option `ruling` names (its letter, its text, or both; point 1 as `<fid> <option>`), resolved
  to the option's text; refused when it is none of them."""
  if ruling == "redesign" and point in (1, 2):  # a head's third ruling: no letter, no finding id
    return "redesign"
  fid, _, text = ruling.partition(" ") if point == 1 else ("", "", ruling)
  for option in options:
    letter, _, rest = option.partition(" ") if option.startswith("(") else ("", "", option)
    if text and text in (option, letter, rest) and (point != 1 or fid):
      return f"{fid} {rest}" if point == 1 else rest
  extra = ["redesign — <one sentence why>"] if point in (1, 2) else []  # a head's third ruling, in no option list
  raise Refusal("decision: ruling is none of the options: " + "; ".join(options + extra))


def ruling_comment(point: int, source: str, ruling: str, question: str, brief=None) -> str:
  """Spec section 11's `**Ruling:**` line (point 1 `<fid> finding upheld (fix it) | finding overruled — <reason>`,
  point 2 `(cap) <option>`, point 3 `(<comment-id>) <option> — <reason>`), a blank line and the quoted question."""
  quoted = "\n".join("> " + l for l in question.rstrip("\n").splitlines())
  if brief:  # a redesign ruling: the unit is stopped, the brief named, the owner closes the issue by hand
    return (f"**Ruling:** {ruling}\n\nStopped for redesign; the brainstorm brief is `{brief}`.\n"
            f"Close this issue by hand once the re-planned unit is filed.\n\n{quoted}\n")
  if point == 1:
    line = ruling.replace("finding upheld", "finding upheld (fix it)", 1)
  else:
    line = f"({source.removeprefix('comment ') if point == 3 else 'cap'}) {ruling}"
  return f"**Ruling:** {line}\n\n{quoted}\n"


DIFF_WHOLE, DIFF_LINES = 40_000, 200  # a diff under 40 KB is copied whole, else its first 200 lines
ENTRY_RE = re.compile(r"^### .+ comment \S+ by ")


def brief_path(store, unit: str, qid: str) -> Path:
  return store.path("foreman", unit).with_name(f"{unit}-{qid}.brainstorm.md")


def brainstorm_brief(store, unit: str, qid: str, decision: dict, ruling: str, pr) -> Path:
  """Write `foreman/<unit>-<qid>.brainstorm.md` (spec section 11): what the owner asked, the findings verbatim,
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


def builder_login(config) -> str:
  """The builder's login: `<slug>[bot]` from the config on the App path, else the machine account's
  under its token (read from GitHub, not from the wave card)."""
  if app_login(config):
    return app_login(config)
  env = config["builder"]["gh_token_env"]
  if not os.environ.get(env):
    raise Refusal(f"decision: {env} is not set")
  return json.loads(core.gh(["api", "user"], token=os.environ[env]))["login"]


def verify_posted(store, config, decision: dict, comment_id: str, by: str) -> None:
  """A by-hand `**Ruling:**` is honoured only from a non-builder author who is `--by`, and only when it
  names the BLOCKED comment the decision came from (anti-goal 10)."""
  comment = core.gh_json(["api", f"repos/{config['repo']}/issues/comments/{comment_id}"]) or {}
  author = (comment.get("user") or {}).get("login")
  if author == builder_login(config):
    raise Refusal(f"decision: comment {comment_id} was written by the builder account {author} and is not honoured")
  source = decision["source"]
  if source.startswith("comment ") and f"({source.split()[1]})" not in (comment.get("body") or ""):
    raise Refusal(f"decision: comment {comment_id} does not name {source}")
  if author != by:
    raise Refusal(f"decision: comment {comment_id} was written by {author}, not {by}")
