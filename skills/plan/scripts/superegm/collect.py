# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# From the elephant-goldfish-model (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_collect` as the collect module, keyed by the dispatch id; it records the foreman's own findings of a round (spec section 11); the lane record's `brief_sha256` (U17); an unreplied external high or medium carried forward (U21).

"""superegm collect: the foreman's findings of a round through one `review record --reviewer foreman`, or a
round that could not complete with `--not-run`."""

import argparse
import contextlib
import io
import json
import re
from pathlib import Path

import superegm as core
from superegm import body as body_mod, review, tdd_order
from superegm.foreman import head_review_id
from superegm.launch_builder import DOD_RESULT_RE
from superegm.prepare import HEADER_RE

WRITES = frozenset(['foreman', 'review', 'reviews'])  # the store kinds this subcommand writes
SKILLS = frozenset(['wave'])  # the skills whose card this subcommand accepts
DEVIATION_RE = re.compile(r"^\*\*Deviation \((interface|dod|test|other)\):\*\*")
RULED_RE = re.compile(r"^\*\*Ruling:\*\* \((\d+)\)")  # a ruling on a deviation comment, by its id (section 10)
RULING_RE = re.compile(r"^\*\*Ruling:\*\* (\S+) finding (upheld|overruled)")
REPLY_RE = re.compile(r"^\*\*Reply (\S+):\*\* (fixed|contested)(?:\s*[—-]\s*(.*))?", re.S)


def register(subparsers):
  p = core.add_parser(subparsers, "collect", "record the foreman's findings of a round, or a round that did not run")
  p.add_argument("--unit", required=True)
  p.add_argument("--dispatch", required=True, help="the dispatch id `foreman dispatch` printed")
  p.add_argument("--not-run", dest="not_run", help="the round could not complete, with this reason")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  try:
    return collect(args, core.require_runcard(args, SKILLS))
  except review.Refusal as refusal:
    print(refusal)
    return 1


def collect(args, card):
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  unit = args.unit
  data = core.load_foreman(st, unit)
  entry = review.require_dispatch(unit, data, args.dispatch)
  n = entry["round"]
  if args.not_run:
    require_non_terminal(unit, entry)
    entry.update({"phase": "collected", "outcome": f"not run ({args.not_run})"})
    core.save_foreman(st, unit, data)
    core.journal(st, f"{unit} round {n} collected (not run ({args.not_run})) under {args.runcard}")
    print(f"{unit} round {n}: collected (not run ({args.not_run}))")
    return 0
  if entry.get("phase") != "prepared":
    raise core.HandoffError(f"{unit} round {n} is `{entry.get('phase')}`, not `prepared`")
  number = handoff.state["units"][unit]["pr"]["number"]
  r = st.path("review", unit, f"pr{number}") / f"r{n}"
  worktree = Path(entry["worktree"])
  text = core.unit_file_body(st.path("unit", unit))
  scope = [path for path, _ in handoff.plan.units[unit].scope]
  changed = core.run_git(["diff", "--name-only", entry["merge_base"], "HEAD"], worktree).split()
  login, comments = parse_comments(core.read_text(r / "comments.md"))
  rid = head_review_id(st, unit)
  prior = max((e["round"] for e in data["rounds"] if e.get("phase") == "posted"), default=None)
  prior_ci_fid, prior_tdd, prior_scope, contest_of, external, earlier = None, [], {}, {}, [], set()
  for e in data["rounds"]:  # every posted round: an overruled out-of-Scope finding widens the Scope for good;
    if e.get("phase") == "posted":  # a contest or carried finding names the finding a reply may answer under
      for f in prior_foreman_findings(st, rid, e["round"]):
        if f["claim"] == "changed path outside Scope paths":
          prior_scope[f["id"]] = f["location"]
        if (m := re.match(r"(?:contested|unreplied) (\S+):", f["claim"])):
          contest_of[f["id"]] = m.group(1)
      external += external_findings(st, rid, e["round"])
      seen = st.path("review", unit, f"pr{number}") / f"r{e['round']}" / "comments.md"
      if seen.is_file():  # a reply in an earlier round's window still answers its finding
        who, said = parse_comments(core.read_text(seen))
        earlier |= {m.group(1) for c in said if c["login"] == who and (m := REPLY_RE.match(c["body"]))}
  for f in prior_foreman_findings(st, rid, prior):
    if f["location"] == "ci":
      prior_ci_fid = f["id"]
    if f["claim"].startswith("tdd-order:"):
      prior_tdd.append(f["id"])
  lines, contested = foreman_findings(n, json.loads(core.read_text(r / "ci.json"))["verdict"], text, scope, worktree, changed,
                                      core.read_text(r / "pr_body.md"), comments, login, prior, prior_ci_fid,
                                      tdd_order.commits_of(worktree, entry["merge_base"]), prior_tdd, prior_scope, contest_of,
                                      external, earlier)
  findings = r / "foreman.findings"
  core.atomic_write(findings, "".join(line + "\n" for line in lines))
  with contextlib.redirect_stdout(io.StringIO()):
    code = review.record_round(argparse.Namespace(
        review=rid, round=n, sha256=entry["head"], reviewer="foreman", findings=str(findings), not_run=None,
        isolation="clean", model="-:-", effort="-:-", runcard=args.runcard, unit=None, design=None, plan=None))
  if code != 0:
    raise core.HandoffError(f"review record exited {code}")
  entry["phase"] = "collected"
  core.save_foreman(st, unit, data)
  rnd = review.load_round(st, rid, n)
  rnd["builder_contested"] = contested
  brief = r / "astra_brief.md"
  if "astra" in rnd["reviewers"] and brief.is_file():  # the lane's record names the brief the runner read
    rnd["reviewers"]["astra"]["brief_sha256"] = core.sha256_file(brief)
  rnd["what_ran"] = review.derive_what_ran(review.load_review(st, rid), rnd, entry)
  core.atomic_write(st.path("reviews", rid, f"round-{n}.json"), rnd)
  core.journal(st, f"{unit} round {n} collected: {len(lines)} foreman findings under {args.runcard}")
  print(f"collected: {len(lines)} foreman findings")
  return 0


def require_non_terminal(unit: str, entry: dict) -> None:
  """A round is terminal in phase `posted`, or `collected` with a `not run` outcome (spec section 7)."""
  phase = entry.get("phase")
  if phase == "posted" or (phase == "collected" and (entry.get("outcome") or "").startswith("not run")):
    raise core.HandoffError(f"{unit} round {entry['round']} is terminal (`{phase}`)")


def prior_foreman_findings(st, rid, prior) -> list:
  """The `foreman` findings of the last posted round's file, or []."""
  if not prior or not rid:
    return []
  rnd = review.load_round(st, rid, prior) or {}
  return ((rnd.get("reviewers") or {}).get("foreman") or {}).get("findings") or []


def external_findings(st, rid, rnd_n) -> list:
  """The `external:<login>` findings `review ingest` recorded in a posted round's file, or []."""
  if not rnd_n or not rid:
    return []
  rnd = review.load_round(st, rid, rnd_n) or {}
  return [f for name, record in (rnd.get("reviewers") or {}).items() if name.startswith("external:")
          for f in record.get("findings") or []]


def parse_comments(text: str) -> tuple:
  """`comments.md` back: the builder login and `{kind, number, id, login, at, body}` per entry."""
  lines = text.splitlines()
  login = lines[0][len("builder: "):] if lines and lines[0].startswith("builder: ") else ""
  comments, current = [], None
  for line in lines[1:]:
    match = HEADER_RE.match(line)
    if match:
      current = {"kind": match.group(1), "number": int(match.group(2)), "id": int(match.group(3)), "login": match.group(4),
                 "at": match.group(5), "body": []}
      comments.append(current)
    elif current is not None:
      current["body"].append(line)
  for comment in comments:
    comment["body"] = "\n".join(comment["body"]).rstrip("\n")
  return login, comments


def foreman_findings(round_n: int, ci_verdict: str, body: str, scope: list, worktree: Path, changed: list, pr_body: str,
                     comments: list, login: str, prior_round, prior_ci_fid, commits: list = (), prior_tdd_fids: list = (),
                     prior_scope: dict = None, contest_of: dict = None, external: list = (),
                     earlier: set = frozenset()) -> tuple:
  """The foreman's high findings of spec section 11 in this order: CI, the DoD items, scope, tdd-order,
  deviations, contested, upheld, unreplied external; and `builder_contested[]` for the contested ones. Rulings
  and replies count only from the right author: rulings from anyone but the builder, replies from the builder.
  An external high or medium with no disposition is carried until a reply names it, or names a posted carried
  copy of it, in this round's comments or an earlier round's (`earlier`, the builder's reply ids there); a
  `contested` reply to such a finding is recorded in the round it comes in, a round late included, when no
  earlier round's comments hold a builder reply to it or its carried copy (`late`) and no ruling already
  names it: a contest is recorded once (spec section 8, External review)."""
  found, contested = [], []
  open_ext = {f["id"] for f in external if f["disposition"] is None and f["severity"] in ("high", "medium")}
  open_ext |= {cid for cid, original in (contest_of or {}).items() if original in open_ext}
  late = {fid for fid in open_ext if not {fid, (contest_of or {}).get(fid, fid)} & set(earlier)}
  if ci_verdict != "ci green":
    found.append(("ci", f"CI not green on this head: {ci_verdict}"))
  results = {int(m.group(1)) for m in DOD_RESULT_RE.finditer(pr_body)}
  for n, kind, text in body_mod.dod_items(body):
    if kind == "exists" and not (worktree / text).exists():
      found.append((text, f"Exists item {n}: path absent"))
    elif kind == "run" and n not in results:
      found.append(("pr_body.md", f"Run item {n}: no fenced output"))
  others = [c for c in comments if c["login"] != login]
  rulings = [(c, m) for c in others if (m := RULING_RE.match(c["body"]))]
  overruled = {m.group(1) for _, m in rulings if m.group(2) == "overruled"}
  widened = {path for fid, path in (prior_scope or {}).items() if fid in overruled}  # an owner's overrule widens the Scope
  found += [(path, "changed path outside Scope paths") for path in changed if path not in scope and path not in widened]
  if not set(prior_tdd_fids) & overruled:
    tests = {n: t for n, t, _ in body_mod.step_paths(body)}
    for failure in tdd_order.check(body, list(commits)):
      step = re.match(r"S(\d+):", failure) or re.search(r"test\(S(\d+)\)", failure)
      found.append((tests.get(int(step.group(1)), "tests/") if step else "tests/", f"tdd-order: {failure}"))
  ruled = {int(m.group(1)) for c in others if (m := RULED_RE.match(c["body"]))}
  for c in comments:
    kind = DEVIATION_RE.match(c["body"])
    if kind and kind.group(1) != "other" and c["id"] not in ruled:
      found.append((where(c), f"deviation ({kind.group(1)}) unruled"))
  if prior_round:
    settled = {m.group(1) for _, m in rulings}
    for c in comments:
      reply = REPLY_RE.match(c["body"])
      if not reply or c["login"] != login or reply.group(2) != "contested":
        continue
      fid = reply.group(1)
      if fid == prior_ci_fid or fid in settled or (fid.split("-")[-2] != str(prior_round) and fid not in late):
        continue
      reason = (reply.group(3) or "").strip()
      found.append((where(c), f"contested {fid}: {reason}"))
      contested.append({"fid": f"foreman-{round_n}-{len(found)}", "reason": reason})
    for c, ruling in rulings:
      fid = ruling.group(1)
      answers = {fid, (contest_of or {}).get(fid, fid)}  # the ruled contest finding, or the goldfish finding it names
      fixed = any(o["login"] == login and o["at"] > c["at"] and (m := REPLY_RE.match(o["body"]))
                  and m.group(1) in answers and m.group(2) == "fixed" for o in comments)
      if ruling.group(2) == "upheld" and not fixed:
        found.append((where(c), f"upheld {fid}: no `fixed` reply"))
  replied = {m.group(1) for c in comments if c["login"] == login and (m := REPLY_RE.match(c["body"]))} | set(earlier)
  for f in external:
    if f["disposition"] is not None or f["severity"] not in ("high", "medium"):
      continue
    copies = {cid for cid, original in (contest_of or {}).items() if original == f["id"]}
    if not ({f["id"]} | copies) & replied:
      found.append((f["location"], f"unreplied {f['id']}: {f['claim']}"))
  lines = [f"foreman-{round_n}-{i} | high | {location} | regression: no | {claim}" for i, (location, claim) in enumerate(found, 1)]
  return lines, contested


def where(comment: dict) -> str:
  return f"{comment['kind']} #{comment['number']} comment {comment['id']}"
