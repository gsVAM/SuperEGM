# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: `superegm next`, a handoff's next phase by the first-match table of spec section 7.1 (U43).

"""superegm next: print a handoff's next phase, the first row of spec section 7.1's table that matches.

The module is `phase`, not `next`: `discover()` imports every submodule onto the package, where
`superegm.next` would shadow the builtin `next`. `next` only reads: `tick/fetch.json` and
`refs/superegm/tick-base` as the tick left them."""

import argparse
import json
import re
import subprocess
from pathlib import Path

import superegm as core
from superegm import gate, graph, launch, report, review, runcard
from superegm.approve_spec import units_section

WRITES = frozenset({"chain", "runcards", "file"})  # the store kinds this subcommand writes
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SKILLS = frozenset({"plan", "review-plan", "file"})  # the skills whose card `next wait` and `next clear` accept
TICK_BASE = "refs/superegm/tick-base"
ROW_RE = re.compile(r"^\|\s*(U\d{2,})\s*\|", re.M)  # a unit row of the spec's `## Units` table
LANDED_RE = re.compile(r"^Landed:\s*([^(\n]*)", re.M)  # the comma-separated ids before any parenthetical
ORDER = ("plan", "review-plan", "file", "wave", "integrate", "none")  # the phases, earliest first: `next clear`'s progress


def register(subparsers):
  p = core.add_parser(subparsers, "next", "print the handoff's next phase (spec section 7.1); writes nothing", runcard=False)
  p.add_argument("--handoff", help="the handoff whose next phase is printed")
  p.set_defaults(run=run, writes=WRITES, action=None)
  sub = p.add_subparsers(dest="action")
  w = core.add_parser(sub, "wait", "write the handoff's wait record, keep its question under waits/ and journal it, close the card (spec sections 7.2, 7.5)")
  w.add_argument("--handoff", default=argparse.SUPPRESS, help="the handoff that waits")
  w.add_argument("--phase", required=True, choices=sorted(SKILLS), help="the phase that waits")
  w.add_argument("--question", required=True, help="what the owner is asked")
  w.add_argument("--review", help="the review whose `proceed` ruling answers it (kept on a re-ask without it)")
  c = core.add_parser(sub, "clear", "remove the wait record on confirmed progress, else keep it or ask again (spec section 7.2)")
  c.add_argument("--handoff", default=argparse.SUPPRESS, help="the handoff whose wait record is cleared")
  a = core.add_parser(sub, "answer", "record the owner's words on the handoff's unanswered wait record (spec section 7.3)", runcard=False)
  a.add_argument("--handoff", default=argparse.SUPPRESS, help="the handoff whose wait is answered")
  a.add_argument("--answer", required=True, help="the owner's words")


def read_json(path: Path):
  return json.loads(core.read_text(path)) if path.is_file() else None


def registered_root(st: core.Store) -> Path:
  """The `root` of the `~/.superegm/registry.json` entry whose `artifacts_dir` is the store (`superegm register`),
  the checkout the plan, review-plan and file skills read; an unregistered store falls back to the checkout its
  config was read from."""
  store_root = st.root.resolve()
  for entry in core.load_registry():
    if entry.get("root") and Path(entry.get("artifacts_dir") or "").expanduser().resolve() == store_root:
      return Path(entry["root"])
  source = Path(str((st.config or {}).get("_source", "")))
  return core.git_toplevel(source.parents[1] if source.is_file() else Path.cwd())


def first_line(text) -> str:
  return (str(text or "").strip().splitlines() or [""])[0]


def merged(view: dict) -> bool:
  """Integrate's own test: the saved snapshot has the pull request set and no CI."""
  return bool(view.get("pr")) and view.get("ci") is None


def unit_open(hs: core.Store, state: dict, uid: str) -> bool:
  """Neither landed, stopped nor merged."""
  view = report.unit_view(state, uid)
  return not (view["landed"] or merged(view) or core.load_foreman(hs, uid).get("stopped"))


def proceeded(hs: core.Store, rid, since) -> bool:
  """The review `rid` has a `proceed` ruling recorded after `since`."""
  data = review.load_review(hs, rid) if rid else None
  return any(r.get("ruling") == "proceed" and str(r.get("at") or "") > str(since or "")
             for r in (data or {}).get("rulings") or [])


def checkout_problem(root: Path, base: str, tick: str):
  """Why the registered root is not `<base>` at the tick-base commit with a clean tree, else None."""
  if core.run_git(["symbolic-ref", "-q", "HEAD"], root, check=False).strip() != f"refs/heads/{base}":
    return f"not on {base}"
  head = core.run_git(["rev-parse", "HEAD"], root).strip()
  if head != tick:
    behind = subprocess.run(["git", "merge-base", "--is-ancestor", head, tick], cwd=str(root), capture_output=True)
    return "behind" if behind.returncode == 0 else "diverged"
  if core.run_git(["--no-optional-locks", "status", "--porcelain", "--untracked-files=no"], root, check=False).strip():
    return "dirty"
  return None


def plan_review_stopped(hs: core.Store, uid: str):
  """The id of the unit's latest plan review when it is stopped with no `proceed` after its `stop`, else None."""
  latest, _ = review.latest_cycle(hs, "plan", uid)
  if latest is None:
    return None
  stops = [r for r in latest.get("rulings") or [] if r.get("ruling") == "stop"]
  rid = review.review_id(hs, "plan", uid, latest["cycle"])
  return rid if stops and not proceeded(hs, rid, stops[-1].get("at")) else None


def plan_review_due(hs: core.Store, uid: str, sha: str, marks: dict | None = None) -> bool:
  """Absent, not converged, converged on other body bytes, or a round recorded after the converged one; `marks`
  the caller's one read of `respec.marks` (U90)."""
  converged, converged_sha = gate.converged_review(hs, uid, marks)  # the gate's two tests
  if not converged or converged_sha != sha:
    return True
  latest, _ = review.latest_cycle(hs, "plan", uid)
  rid = review.review_id(hs, "plan", uid, latest["cycle"])
  return max(review.round_numbers(hs, rid), default=0) > latest["converged_round"]


def spec_under(root: Path, spec: Path):
  """The handoff's spec under the registered root: `spec` when it lies there, else root joined with the longest
  suffix of the recorded path that `refs/superegm/tick-base` holds (a spec approved in another worktree that the
  root has not pulled); None when the tick-base holds no suffix of it."""
  if spec.resolve().is_relative_to(root.resolve()):
    return spec
  for i in range(1, len(spec.parts)):
    rel = Path(*spec.parts[i:]).as_posix()
    if not subprocess.run(["git", "cat-file", "-e", f"{TICK_BASE}:{rel}"], cwd=str(root), capture_output=True).returncode:
      return root / rel
  return None


def approved_text(root: Path, spec: Path, entry) -> str:
  """The spec text of the latest approval `entry`: its bytes as `refs/superegm/tick-base`'s history holds them,
  else (no entry, or bytes not reachable there) the registered root's working copy."""
  try:
    rel = spec.resolve().relative_to(root.resolve()).as_posix()
  except ValueError:
    rel = None
  text = core.spec_blob(root, rel, entry["sha256"], ref=TICK_BASE) if entry and rel else None
  return text if text is not None else (core.read_text(spec) if spec.is_file() else "")


def planning_line(hs: core.Store, state: dict, spec: Path, text: str) -> str:
  """The rows from `waiting plan` down: what the handoff's plan, reviews, filing and units ask for next; `text` is
  the latest approval's spec, whose `## Units` rows the plan must cover."""
  section = units_section(text)
  landed = LANDED_RE.search(section)
  done = set(re.findall(r"U\d{2,}", landed.group(1))) if landed else set()
  done |= set(graph.filed_in(hs, spec))
  rows = ROW_RE.findall(section)
  units = read_json(hs.path("units"))
  if units is None:
    return "waiting plan: no unit left to plan: superegm approve-spec --void --spec " + str(spec) \
        if rows and all(u in done for u in rows) else "plan"
  if any(u not in units["order"] and u not in done for u in rows):
    return "plan"
  numbers = {u: (r or {}).get("number") for u, r in (state.get("units") or {}).items()}
  unfiled = [u for u in units["order"] if not numbers.get(u)]
  marks = gate.handoff_marks(hs)
  if any((marks.get(u) or "").startswith("replan: ") for u in unfiled):
    return "plan"  # a respec touched an unfiled unit: its section is rewritten from the corrected spec (U90)
  for uid in unfiled:
    rid = plan_review_stopped(hs, uid)
    if rid:
      return f"waiting review-plan: {rid} stopped"
  if any(plan_review_due(hs, u, units["units"][u]["body_sha256"], marks) for u in unfiled):
    return "review-plan"
  if unfiled or not core.receipt_ok(state):
    return "file"
  return "wave" if any(unit_open(hs, state, u) for u in units["order"]) else "integrate"


def next_line(st: core.Store, hid: str, read_wait: bool = True) -> str:
  """The line `next` prints for handoff `hid`: the first row of spec section 7.1's table that matches;
  `read_wait=False` reads the table as if the handoff had no wait record (`next clear`)."""
  record = next((r for r in core.handoffs(st.root) if r["id"] == hid), None)
  if record is None:
    raise core.HandoffError(f"next: {hid}: no such handoff")
  hs = core.handoff_store(st, hid)
  config = st.config or {}
  root = registered_root(st)
  state = read_json(hs.path("state")) or {}
  spec = core.rebased(record.get("spec") or (state.get("design") or {}).get("path") or "", root)
  entries = core.load_approvals(st, spec)
  own = [i for i, e in enumerate(entries) if e.get("handoff_id") == hid]
  if record.get("closed_at") or state.get("closed_at") or (own and entries[own[-1]].get("voided_by")):
    return "none"
  fetch = read_json(st.path("tick", "fetch"))
  tick = core.run_git(["rev-parse", "-q", "--verify", f"{TICK_BASE}^{{commit}}"], root, check=False).strip()
  if fetch is not None and not fetch.get("ok"):
    return f"waiting fetch: {config.get('remote')}: {first_line(fetch.get('stderr')) or 'fetch failed'}"
  if not tick:
    return f"waiting fetch: {config.get('remote')}: {TICK_BASE} absent"
  try:
    core.require_latest_handoff(hs)
  except core.HandoffError:
    filed = [u for u, r in (state.get("units") or {}).items() if (r or {}).get("number")]
    if not filed:
      return "none"
    return "wave" if any(unit_open(hs, state, u) for u in filed) else "integrate"
  wait = read_json(st.path("chain", hid)) if read_wait else None
  if wait and not wait.get("answer") and not proceeded(hs, wait.get("review"), wait.get("since")):
    return f"waiting {wait['phase']}: {' '.join(str(wait.get('question') or '').splitlines())}"
  if own:
    spec = spec_under(root, spec)
    if spec is None or launch.origin_problems(root, config.get("base", "main"), {**entries[own[-1]], "path": str(spec)},
                                              entries[own[-1] + 1:], ref=TICK_BASE, spec_only=True):
      return "waiting push"
  answered = bool(wait and wait.get("answer"))
  text = approved_text(root, spec, entries[-1] if entries else None)
  below = wait["phase"] if answered else planning_line(hs, state, spec, text)
  if answered or below in ("plan", "review-plan", "file"):
    problem = checkout_problem(root, config.get("base", "main"), tick)
    if problem:
      return f"waiting checkout: {root}: {problem}"
  return below


def wait(args, st: core.Store, hid: str) -> int:
  """Write `chain/<handoff>.json` (`review` kept from the stored record on a re-ask without one) and close the card.
  The question is kept as `waits/<phase>-<at>.md` and journaled as `next wait` or, on a phase whose record holds an
  answer, `next reask` (`keep_question`)."""
  card_id = args.runcard
  path = st.path("chain", hid)
  stored = read_json(path) or {}
  hs = core.handoff_store(st, hid)
  at = fresh_at(hs, args.phase, core.now_iso())
  keep_question(hs, args.phase, at, args.question, card_id,
                reask=bool(stored.get("answer")) and stored.get("phase") == args.phase)
  core.atomic_write(path, {"phase": args.phase, "question": args.question, "since": at,
                           "review": args.review or stored.get("review")})
  runcard.close_card(st, card_id)
  return 0


def fresh_at(hs: core.Store, phase: str, at: str) -> str:
  """`at`, or the next second no wait of `phase` has kept a question under: the store's stamps have one-second
  precision and a wait's files are keyed by its stamp, so a wait in the second of an earlier one would overwrite it."""
  while hs.path("file", "waits", f"{phase}-{at}.md").is_file():
    at = core.iso(core.epoch(at) + 1)
  return at


def keep_question(hs: core.Store, phase: str, at: str, question: str, source: str, reask: bool = False) -> None:
  """Keep a wait's question as `waits/<phase>-<at>.md` in the handoff's directory and journal it: `next wait
  <handoff> <phase> since <at> source <source> question <sha>`, or `next reask <handoff> <phase> at <at> question
  <sha>` for a re-ask (a `next wait` on a phase whose record holds an answer). The history of a wait lives in these
  lines and files: the record itself is rewritten and removed (spec section 7.5)."""
  core.atomic_write(hs.path("file", "waits", f"{phase}-{at}.md"), question)
  sha = core.sha256_text(question)
  core.journal(hs, f"next reask {hs.handoff_id} {phase} at {at} question {sha}" if reask
               else f"next wait {hs.handoff_id} {phase} since {at} source {source} question {sha}")


def clear(args, st: core.Store, hid: str) -> int:
  """Remove the wait record on confirmed progress (`next` without it prints a later phase, or a `proceed` ruling
  resolves it); a `waiting` row keeps it as it is, answered or not; otherwise an unanswered record stays and an
  answered one is asked again (a Stop: the record is rewritten with a new `since`, its question kept as
  `waits/<phase>-<since>.md` and journaled `next wait ... source clear`). Each removal or rewrite journals `next
  clear` (`journal_clear`). The card closes.
  Section 7.2's third removal, `next` showing "the unit withdrawn", is not read: section 7.1's table prints no
  such line and no unit of this build defines withdrawal, so a withdrawn unit's record clears only through a later
  phase."""
  path = st.path("chain", hid)
  record = read_json(path)
  if record:
    line = next_line(st, hid, read_wait=False)
    later = line in ORDER and ORDER.index(line) > ORDER.index(record["phase"])
    hs = core.handoff_store(st, hid)
    if later or proceeded(hs, record.get("review"), record.get("since")):
      journal_clear(hs, record)
      path.unlink()
    elif record.get("answer") and not line.startswith("waiting "):
      journal_clear(hs, record)
      at = fresh_at(hs, record["phase"], core.now_iso())
      question = f"stopped at {record['phase']} by {record.get('by')}: answer to go on"
      keep_question(hs, record["phase"], at, question, "clear")
      core.atomic_write(path, {"phase": record["phase"], "since": at, "review": record.get("review"), "question": question})
  runcard.close_card(st, args.runcard)
  return 0


def journal_clear(hs: core.Store, record: dict) -> None:
  """Journal the end of a wait record `next clear` removes or rewrites: `next clear <handoff> <phase> answered by
  <by> at <at> answer <sha>`, the answer's sha256. Every `waits/` file stays where it is. A record a `proceed` ruling
  resolves holds no answer: its `by` and `at` are the ruling's, else `progress` and now, the answer's text empty."""
  if record.get("answer") is not None:
    by, at, text = record.get("by"), record.get("at"), record["answer"]
  else:
    data = review.load_review(hs, record.get("review")) if record.get("review") else None
    ruling = next((r for r in reversed((data or {}).get("rulings") or [])
                   if r.get("ruling") == "proceed" and str(r.get("at") or "") > str(record.get("since") or "")), {})
    by, at, text = ruling.get("by") or "progress", ruling.get("at") or core.now_iso(), ""
  core.journal(hs, f"next clear {hs.handoff_id} {record['phase']} answered by {by} at {at} "
                   f"answer {core.sha256_text(text)}")


def answer(args, st: core.Store, hid: str) -> int:
  """Record `--answer` on the handoff's wait record as the login `gh api user` reports: `answer`, `by` and `at` on
  `chain/<handoff>.json`, the words as `waits/<phase>-<since>.answer.md` and `{by, at, sha}` (the answer's sha256) as
  `waits/<phase>-<since>.answer.json` in the handoff's directory, both keyed by the wait's `since`, never rewritten. No run card: the phase session that runs next holds the card."""
  path = st.path("chain", hid)
  record = read_json(path)
  if not record:
    raise core.HandoffError(f"next answer: {hid}: no wait record to answer")
  if record.get("answer"):
    raise core.HandoffError(f"next answer: {hid}: the wait record already holds an answer")
  login = core.gh(["api", "user", "--jq", ".login"]).strip()
  if login not in ((st.config or {}).get("owners") or []):
    raise core.HandoffError(f"next answer: {login or 'no login'} is not in config.owners")
  at = core.now_iso()
  sha = core.sha256_text(args.answer)
  waits = core.handoff_store(st, hid).path("file", "waits")
  core.atomic_write(waits / f"{record['phase']}-{record['since']}.answer.md", args.answer)  # keyed by `since`: it pairs with its question
  core.atomic_write(waits / f"{record['phase']}-{record['since']}.answer.json", {"by": login, "at": at, "sha": sha})
  core.atomic_write(path, {**record, "answer": args.answer, "by": login, "at": at})
  return 0


def run(args):
  action = getattr(args, "action", None)
  if action and action != "answer":  # `answer` is the owner's, read before any card: the owner opens none
    core.require_runcard(args, SKILLS)
  if not getattr(args, "handoff", None):
    raise core.HandoffError("next: --handoff is required")
  st = core.store(core.git_toplevel(Path.cwd()))
  if action == "answer":
    return answer(args, st, args.handoff)
  if args.action == "wait":
    return wait(args, st, args.handoff)
  if args.action == "clear":
    return clear(args, st, args.handoff)
  print(next_line(st, args.handoff))
  return 0
