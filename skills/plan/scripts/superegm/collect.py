# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# From the elephant-goldfish-model (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_collect` as the collect module, keyed by the dispatch id; it records the foreman's own findings of a round (spec section 11); the lane record's `brief_sha256` (U17); an unreplied external high or medium carried forward (U21); rulings read through `ruling_of` and the record, every folded deviation heading (U22).

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
from superegm.decision import binding_rulings, recorded_rulings
from superegm.foreman import head_review_id
from superegm.launch_builder import DOD_RESULT_RE
from superegm.prepare import HEADER_RE

WRITES = frozenset(['foreman', 'review', 'reviews'])  # the store kinds this subcommand writes
SKILLS = frozenset(['wave'])  # the skills whose card this subcommand accepts
DEVIATION_RE = re.compile(r"^\*\*Deviation \((interface|dod|test|other)\):\*\*")
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
  prior_ci_fid, prior_tdd, prior_scope, contest_of, external, earlier, disposed = None, {}, {}, {}, [], set(), set()
  posted = {e["round"]: e.get("posted_at") or "" for e in data["rounds"] if e.get("phase") == "posted"}
  for e in data["rounds"]:  # every posted round: an overruled out-of-Scope finding widens the Scope for good;
    if e.get("phase") == "posted":  # a contest or carried finding names the finding a reply may answer under
      for f in prior_foreman_findings(st, rid, e["round"]):
        if f["claim"] == "changed path outside Scope paths":
          prior_scope[f["id"]] = f["location"]
        if f["claim"].startswith("tdd-order: "):  # a ruled tdd-order failure stays ruled in every later round
          prior_tdd[f["id"]] = f["claim"].removeprefix("tdd-order: ")
        if (m := re.match(r"(?:contested|unreplied) (\S+):", f["claim"])):
          contest_of[f["id"]] = m.group(1)
          if f.get("disposition") is not None:  # a settled copy settles what it carries
            disposed.add(f["id"])
      external += external_findings(st, rid, e["round"])
      seen = st.path("review", unit, f"pr{number}") / f"r{e['round']}" / "comments.md"
      if seen.is_file():  # a reply in an earlier round's window still answers its finding
        who, said = parse_comments(core.read_text(seen))
        earlier |= {m.group(1) for c in said if c["login"] == who and (m := REPLY_RE.match(c["body"])) and timely(m.group(1), c["at"], posted)}
  for f in prior_foreman_findings(st, rid, prior):
    if f["location"] == "ci":
      prior_ci_fid = f["id"]
  lines, contested = foreman_findings(n, json.loads(core.read_text(r / "ci.json"))["verdict"], text, scope, worktree, changed,
                                      core.read_text(r / "pr_body.md"), comments, login, prior, prior_ci_fid,
                                      tdd_order.commits_of(worktree, entry["merge_base"]), prior_tdd, prior_scope, contest_of,
                                      external, earlier, disposed, posted, handoff.config.get("owners") or [],
                                      recorded_rulings(data), data.get("decisions") or [], recorded_times(data),
                                      handoff.state["units"][unit].get("number"))
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


def recorded_times(foreman: dict) -> dict:
  """Each recorded ruling's comment id to its entry's `posted_at` (the comment as recorded)."""
  return {int(cid): e.get("posted_at") or "" for e in foreman.get("rulings") or []
          if (cid := str(e.get("posted") or "").removeprefix("comment ")).isdigit()}


def foreman_findings(round_n: int, ci_verdict: str, body: str, scope: list, worktree: Path, changed: list, pr_body: str,
                     comments: list, login: str, prior_round, prior_ci_fid, commits: list = (), prior_tdd: dict = None,
                     prior_scope: dict = None, contest_of: dict = None, external: list = (),
                     earlier: set = frozenset(), disposed: set = frozenset(), posted: dict = None,
                     owners: list = (), recorded: list = (), decisions: list = (), recorded_at: dict = None,
                     issue_number: int = None) -> tuple:
  """The foreman's high findings of spec section 11 in this order: CI, the DoD items, scope, tdd-order,
  deviations, contested, upheld, unreplied external; and `builder_contested[]` for the contested ones. Rulings
  and replies count only from the right author: a ruling is a `config.owners` login's comment `ruling_of` reads
  (spec section 13.2's one grammar) on the unit's issue, never the PR, or an entry of the record (`recorded`,
  `recorded_rulings`), replies come from the builder. Every `**Deviation**` line of a comment is one deviation; an `allowed` ruling on a posted
  round's tdd-order fid (`prior_tdd`, fid to failure) skips that failure as an overrule does, and no other.
  An external high or medium with no disposition is carried until a reply names it, or names a posted carried
  copy of it, in this round's comments or an earlier round's (`earlier`, the builder's reply ids there), or
  until one of its copies is settled (`disposed`, the copies whose disposition is set). Its group is the
  finding and every copy of it, a recorded contest of a copy included (`contest_of` followed back to the
  external id). A `contested` reply to such a finding is recorded in the round it comes in, a round late
  included, when no earlier round's comments hold a builder reply to any id of its group (`late`) and no
  ruling in this round's comments names it: a contest is recorded once (spec section 8, External review). An
  upheld ruling is answered by a `fixed` reply later than it (than its record's `posted_at`, `recorded_at`, when recorded) under the ruled id or under any id of its group;
  a recorded one binds whether or not its comment is still in `comments` (edited into prose or deleted), located
  on the unit's issue (`issue_number`). A reply
  to a carried copy `foreman-<r>-<k>`, `fixed` or `contested`, counts (toward the carry, or as a contest) only
  when it comes after round r was posted (`posted`, each posted round's `posted_at`): before that the copy did
  not exist."""
  found, contested = [], []
  links = contest_of or {}

  def origin(fid):
    seen = set()
    while fid in links and fid not in seen:
      seen.add(fid)
      fid = links[fid]
    return fid

  groups = {}
  for fid in set(links) | {f["id"] for f in external}:
    groups.setdefault(origin(fid), set()).add(fid)
  open_ext = {f["id"] for f in external if f["disposition"] is None and f["severity"] in ("high", "medium")
              and not groups[f["id"]] & set(disposed)}
  open_ext |= {cid for cid in links if origin(cid) in open_ext}
  late = {fid for fid in open_ext if not groups[origin(fid)] & set(earlier)}
  if ci_verdict != "ci green":
    found.append(("ci", f"CI not green on this head: {ci_verdict}"))
  results = {int(m.group(1)) for m in DOD_RESULT_RE.finditer(pr_body)}
  for n, kind, text in body_mod.dod_items(body):
    if kind == "exists" and not (worktree / text).exists():
      found.append((text, f"Exists item {n}: path absent"))
    elif kind == "run" and n not in results:
      found.append(("pr_body.md", f"Run item {n}: no fenced output"))
  # The rulings: an owner's form comment read by `ruling_of`, and the record (`rulings[]`, the judges' post included)
  # (spec section 13.2: a recorded ruling is never changed by a later comment, so the record wins on its comment ids and subjects)
  rulings = binding_rulings([c for c in comments if c["kind"] == "issue"], owners, recorded, decisions)  # an issue comment alone rules
  by_id = {c["id"]: c for c in comments}
  # a ruling on a contest's copy (`contested <fid>: …`) rules the finding it contests, down the chain to the original
  def chain(fid):
    out = {fid}
    while fid in links and links[fid] not in out:
      fid = links[fid]
      out.add(fid)
    return out
  overruled = set().union(*(chain(r.subject) for r in rulings if r.kind == "overruled"))
  allowed = set().union(*(chain(r.subject) for r in rulings if r.kind == "allowed"))
  widened = {path for fid, path in (prior_scope or {}).items() if fid in overruled}  # an owner's overrule widens the Scope
  in_scope = lambda path: any(path == s or path.startswith(s.rstrip("/") + "/") for s in scope)  # a directory covers its files
  found += [(path, "changed path outside Scope paths") for path in changed if not in_scope(path) and path not in widened]
  # a tdd-order failure a posted round raised and a ruling overruled or allowed is skipped; any other failure is raised
  skipped = {text for fid, text in (prior_tdd or {}).items() if fid in overruled | allowed}
  tests = {n: t for n, t, _ in body_mod.step_paths(body)}
  for failure in tdd_order.check(body, list(commits)):
    if failure in skipped:
      continue
    step = re.match(r"S(\d+):", failure) or re.search(r"test\(S(\d+)\)", failure)
    found.append((tests.get(int(step.group(1)), "tests/") if step else "tests/", f"tdd-order: {failure}"))
  ruled = {int(r.subject) for r in rulings if r.kind == "option" and r.subject.isdigit()}
  for c in comments:  # every `**Deviation**` heading a comment folds; one ruling naming the comment rules them all
    for line in c["body"].splitlines():
      kind = DEVIATION_RE.match(line)
      if kind and kind.group(1) != "other" and c["id"] not in ruled:
        found.append((where(c), f"deviation ({kind.group(1)}) unruled"))
  if prior_round:
    settled = {r.subject for r in rulings if r.kind in ("upheld", "overruled", "allowed")}
    for c in comments:
      reply = REPLY_RE.match(c["body"])
      if not reply or c["login"] != login or reply.group(2) != "contested":
        continue
      fid = reply.group(1)
      if fid == prior_ci_fid or fid in settled or (fid.split("-")[-2] != str(prior_round) and fid not in late):
        continue
      if posted is not None and not timely(fid, c["at"], posted):  # a contest of a copy not yet posted contests nothing
        continue
      reason = (reply.group(3) or "").strip()
      found.append((where(c), f"contested {fid}: {reason}"))
      contested.append({"fid": f"foreman-{round_n}-{len(found)}", "reason": reason})
    times = recorded_at or {}
    for ruling in rulings:
      c = by_id.get(ruling.comment_id)  # the comment the ruling names: its time bounds the `fixed` reply
      if c is None and ruling.comment_id in times:  # a recorded ruling whose comment is gone or no longer a form
        c = {"kind": "issue", "number": issue_number, "id": ruling.comment_id, "at": ""}
      if ruling.kind not in ("upheld", "overruled") or c is None:
        continue
      fid = ruling.subject
      answers = {fid, links.get(fid, fid)} | groups.get(origin(fid), set())  # the ruled finding, or any id of its group
      since = max(c["at"], times.get(ruling.comment_id) or "")  # a recorded ruling binds from its record's time
      fixed = any(o["login"] == login and o["at"] > since and (m := REPLY_RE.match(o["body"]))
                  and m.group(1) in answers and m.group(2) == "fixed" for o in comments)
      if ruling.kind == "upheld" and not fixed:
        found.append((where(c), f"upheld {fid}: no `fixed` reply"))
  replied = {m.group(1) for c in comments if c["login"] == login and (m := REPLY_RE.match(c["body"]))
             and (posted is None or timely(m.group(1), c["at"], posted))} | set(earlier)
  for f in external:
    if f["id"] not in open_ext:
      continue
    if not groups[f["id"]] & replied:
      found.append((f["location"], f"unreplied {f['id']}: {f['claim']}"))
  lines = [f"foreman-{round_n}-{i} | high | {location} | regression: no | {claim}" for i, (location, claim) in enumerate(found, 1)]
  return lines, contested


def timely(fid: str, at: str, posted: dict) -> bool:
  """A reply to `foreman-<r>-<k>` counts only after round r was posted (`posted`: round → `posted_at`); any other id always."""
  m = re.fullmatch(r"foreman-(\d+)-\d+", fid)
  return m is None or (int(m.group(1)) in posted and at > posted[int(m.group(1))])


def where(comment: dict) -> str:
  return f"{comment['kind']} #{comment['number']} comment {comment['id']}"
