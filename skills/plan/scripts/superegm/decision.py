# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the decision subcommand (spec sections 7, 11 and 13.2): every point-1/2/3
# question and ruling of a unit, the by-hand BLOCKED ruling and the owner's close as `stop`.

"""superegm decision open|rule: record a unit's question (`decisions[]`) and its ruling (`rulings[]`)."""

import os
from pathlib import Path

import superegm as core
from superegm.apply import body_file
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


def stop_unit(store, uid: str, by: str, reason: str, number: int, now_iso: str) -> None:
  """Label the issue `superegm:stopped`, write `foreman["stopped"]`, journal (spec section 11)."""
  core.gh(["issue", "edit", str(number), "-R", store.config["repo"], "--add-label", store.config["labels"]["stopped"]])
  data = core.load_foreman(store, uid)
  data["stopped"] = {"by": by, "reason": reason, "at": now_iso}
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
  if closed:
    posted = f"closed #{closed}"
  elif args.posted:
    verify_posted(st, st.config, decision, args.posted, args.by)
    posted = f"comment {args.posted}"
  else:
    body = ruling_comment(decision["point"], decision["source"], chosen + (f" — {reason}" if reason else ""),
                          decision["question"])
    path = body_file(body, st.root)
    try:
      url = core.gh(["issue", "comment", str(number), "-R", st.config["repo"], "--body-file", path]).strip()
    finally:
      os.unlink(path)
    posted = f"comment {url.rsplit('-', 1)[1]}"
  data["rulings"].append({"decision": args.decision, "ruling": args.ruling, "by": args.by,
                          "reason": reason.strip() or None, "posted": posted, "posted_at": now})
  core.save_foreman(st, unit, data)
  who = f"judges {args.by[7:]}, leavemealone" if args.by.startswith("judges:") else args.by
  core.journal(st, f"Ruling ({who}): {unit} {args.decision} {args.ruling}")
  if chosen.startswith("stop"):
    stop_unit(st, unit, args.by, chosen, number, now)
  print(url if posted.startswith("comment") and not args.posted else f"recorded ({posted})")
  return 0


def check_ruling(point: int, options: list, ruling: str) -> str:
  """The option `ruling` names (its letter, its text, or both; point 1 as `<fid> <option>`), resolved
  to the option's text; refused when it is none of them."""
  fid, _, text = ruling.partition(" ") if point == 1 else ("", "", ruling)
  for option in options:
    letter, _, rest = option.partition(" ") if option.startswith("(") else ("", "", option)
    if text in (option, letter, rest) and (point != 1 or fid):
      return f"{fid} {rest}" if point == 1 else rest
  raise Refusal("decision: ruling is none of the options: " + "; ".join(options))


def ruling_comment(point: int, source: str, ruling: str, question: str) -> str:
  """Spec section 11's `**Ruling:**` line (point 1 `<fid> finding upheld (fix it) | finding overruled — <reason>`,
  point 2 `(cap) <option>`, point 3 `(<comment-id>) <option> — <reason>`), a blank line and the quoted question."""
  if point == 1:
    line = ruling.replace("finding upheld", "finding upheld (fix it)", 1)
  else:
    line = f"({source.removeprefix('comment ') if point == 3 else 'cap'}) {ruling}"
  quoted = "\n".join("> " + l for l in question.rstrip("\n").splitlines())
  return f"**Ruling:** {line}\n\n{quoted}\n"
