# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# From the elephant-goldfish-model (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_collect` as the collect module, keyed by the dispatch id; it records the foreman's own findings of a round (spec section 11); the lane record's `brief_sha256` (U17); an unreplied external high or medium carried forward (U21); rulings read through `ruling_of` and the record, every folded deviation heading (U22); the DoD re-run and the test delta, two gates before the word (U25).

"""superegm collect: the foreman's findings of a round through one `review record --reviewer foreman`, or a
round that could not complete with `--not-run`."""

import argparse
import contextlib
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import superegm as core
from superegm import body as body_mod, review, tdd_order
from superegm.decision import binding_rulings, recorded_rulings
from superegm.foreman import head_review_id
from superegm.launch_builder import DOD_RESULT_RE, SENTINEL, launched_pairs
from superegm.prepare import HEADER_RE

WRITES = frozenset(['foreman', 'review', 'reviews'])  # the store kinds this subcommand writes
SKILLS = frozenset(['wave'])  # the skills whose card this subcommand accepts
DEVIATION_RE = re.compile(r"^\*\*Deviation \((interface|dod|test|other)\):\*\*")
REPLY_RE = re.compile(r"^\*\*Reply (\S+):\*\* (fixed|contested)(?:\s*[—-]\s*(.*))?", re.S)
COUNTS_RE = re.compile(r"(\d+) passed|(\d+) failed")  # a pytest summary line's pass and fail counts
KILL_WAIT = 5  # seconds waited after `kill_group` at the bound before `exit: none` is recorded


def run_env(gh, worktree) -> dict:
  """The DoD runs' environment, an allow-list (spec section 11.1): `PATH`, `HOME`, `LANG`, `TMPDIR`, the sentinel
  `GH_TOKEN`, the builder's git shut-out pairs, `PIP_REQUIRE_VIRTUALENV=1` and `npm_config_prefix` at the worktree."""
  env = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "TMPDIR") if k in os.environ}
  env.update(launched_pairs(gh, "superegm", "superegm"))
  env.update(GH_TOKEN=SENTINEL, PIP_REQUIRE_VIRTUALENV="1", npm_config_prefix=str(worktree))
  return env


def last_line(text: str) -> str:
  return next((l.strip() for l in reversed(text.splitlines()) if l.strip()), "")


def counts(text) -> tuple | None:
  """`(passed, failed)` from the last line of `text` matching `COUNTS_RE` (an absent word 0), or None: no such line."""
  line = next((l for l in reversed((text or "").splitlines()) if COUNTS_RE.search(l)), None)
  if line is None:
    return None
  found = COUNTS_RE.findall(line)
  return (next((int(p) for p, _ in found if p), 0), next((int(f) for _, f in found if f), 0))


def dod_findings(body: str, runs: dict, ruled: set) -> list:
  """The `dod-<n>` highs of the re-run, in item order, skipping an item number in `ruled`: a run cut by the bound
  `ran red (timeout)`, an item the bound left unreached `not run (timeout)`, a non-zero exit `ran red (<line>)` alone,
  and a green run whose pass or fail counts differ from the builder's paste `paste differs from the run`."""
  found = []
  for n, kind, _ in body_mod.dod_items(body):
    run = runs.get(str(n))
    if kind != "run" or run is None or n in ruled:
      continue
    if run["summary"] is None:
      found.append(("pr_body.md", f"dod-{n}: not run (timeout)"))
    elif run["timed_out"]:
      found.append((f"dod/{n}.txt", f"dod-{n}: ran red (timeout)"))
    elif run["exit"] != 0:
      found.append((f"dod/{n}.txt", f"dod-{n}: ran red ({run['summary']})"))
    elif None not in (ran := counts(run["summary"]), pasted := counts(run["paste_summary"])) and ran != pasted:
      found.append((f"dod/{n}.txt", f"dod-{n}: paste differs from the run"))
  return found


def dod_runs(items, worktree: Path, env: dict, deadline: float, out_dir: Path) -> dict:
  """Run each `(n, command, paste_summary)` through `/bin/sh` in `worktree`, in its own process group, its output
  to `out_dir/<n>.out`; the group is killed on the item's return and at `deadline`, and an item reached after
  the deadline is not run (`exit` and `summary` None, `timed_out` true)."""
  out_dir.mkdir(parents=True, exist_ok=True)
  runs = {}
  for n, command, paste in items:
    left = deadline - time.time()
    if left <= 0:
      runs[str(n)] = {"exit": None, "summary": None, "paste_summary": paste, "timed_out": True}
      continue
    out = out_dir / f"{n}.out"
    with open(out, "wb") as sink:
      p = subprocess.Popen(["/bin/sh", "-c", command], cwd=str(worktree), env=env, stdin=subprocess.DEVNULL,
                           stdout=sink, stderr=subprocess.STDOUT, start_new_session=True)
      try:
        code, timed_out = p.wait(timeout=left), False
        core.kill_group(p.pid)
      except subprocess.TimeoutExpired:
        core.kill_group(p.pid)
        with contextlib.suppress(subprocess.TimeoutExpired):
          p.wait(timeout=KILL_WAIT)
        code, timed_out = None, True
    summary = last_line(out.read_text(encoding="utf-8", errors="replace"))
    runs[str(n)] = {"exit": code, "summary": summary, "paste_summary": paste, "timed_out": timed_out}
  return runs


OPERATORS = ("==", " in ", "raises", "match=")  # a paired head line lacking one of its base line's is weakened
MARKER_RE = re.compile(r"@pytest\.mark\.(?:skip|xfail)\b")


def assertion_lines(lines: list) -> set:
  """The 0-based indexes of `lines` the gate guards: an `assert`, a `pytest.raises`, a `def test_` and a
  `parametrize` row (a line strictly between one holding `@pytest.mark.parametrize(` and the next whose stripped
  text starts with `]`)."""
  out, inside = set(), False
  for i, line in enumerate(lines):
    s = line.strip()
    if inside:
      if s.startswith("]"):
        inside = False
      else:
        out.add(i)
        continue
    if "@pytest.mark.parametrize(" in line:
      inside = True
    elif s.startswith("assert ") or s == "assert" or "pytest.raises" in s or s.startswith("def test_"):
      out.add(i)
  return out


def test_delta(base_files: dict, head_files: dict, named: set) -> list:
  """The removed or weakened assertions of each test file `base_files` maps to `(base_commit, text)`, its head
  text in `head_files` (absent: zero assertions), a file in `named` or not `.py` skipped. Lines pair as git pairs
  them: positionally within each `difflib.SequenceMatcher` `replace` block, the rest unpaired; a pair whose head
  line lacks one of the base line's `OPERATORS` is `weakened` at the head line, an unpaired head skip or xfail
  marker directly above a `def test_` is `weakened`, and an unpaired base assertion whose stripped text is in no
  head line is `removed`."""
  delta = []
  for path, (base_commit, base_text) in sorted(base_files.items()):
    if path in named or not path.endswith(".py"):
      continue
    entry = lambda line, base_line, kind: {"file": path, "line": line, "base_line": base_line, "kind": kind, "base_commit": base_commit}
    base, guarded = base_text.splitlines(), assertion_lines(base_text.splitlines())
    head_text = head_files.get(path)
    if head_text is None:
      delta += [entry(i + 1, i + 1, "removed") for i in sorted(guarded)]
      continue
    head = head_text.splitlines()
    stripped = {line.strip() for line in head}
    ops = difflib.SequenceMatcher(None, base, head, autojunk=False).get_opcodes()
    to_base = {j1 + k: i1 + k for tag, i1, i2, j1, j2 in ops if tag == "equal" for k in range(i2 - i1)}
    for tag, i1, i2, j1, j2 in ops:
      if tag == "equal":
        continue
      paired = min(i2 - i1, j2 - j1) if tag == "replace" else 0
      for k in range(paired):
        i, j = i1 + k, j1 + k
        if i in guarded and any(op in base[i] and op not in head[j] for op in OPERATORS):
          delta.append(entry(j + 1, i + 1, "weakened"))
      for j in range(j1 + paired, j2):
        if MARKER_RE.search(head[j]) and j + 1 < len(head) and head[j + 1].strip().startswith("def test_") and j + 1 in to_base:
          delta.append(entry(j + 1, to_base[j + 1] + 1, "weakened"))
      for i in range(i1 + paired, i2):
        if i in guarded and base[i].strip() not in stripped:
          delta.append(entry(j1 + 1, i + 1, "removed"))
  return delta


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
  deadline = time.time() + 60 * handoff.config["foreman"]["run_timeout_minutes"]  # the whole call's bound, from its entry
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
  prior_dod = {}
  posted = {e["round"]: e.get("posted_at") or "" for e in data["rounds"] if e.get("phase") == "posted"}
  for e in data["rounds"]:  # every posted round: an overruled out-of-Scope finding widens the Scope for good;
    if e.get("phase") == "posted":  # a contest or carried finding names the finding a reply may answer under
      for f in prior_foreman_findings(st, rid, e["round"]):
        if f["claim"] == "changed path outside Scope paths":
          prior_scope[f["id"]] = f["location"]
        if f["claim"].startswith("tdd-order: "):  # a ruled tdd-order failure stays ruled in every later round
          prior_tdd[f["id"]] = f["claim"].removeprefix("tdd-order: ")
        if (m := re.match(r"dod-(\d+): ", f["claim"])):  # a ruled `dod-<n>` finding stays ruled on its item number
          prior_dod[f["id"]] = int(m.group(1))
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
  verdict, pr_body = json.loads(core.read_text(r / "ci.json"))["verdict"], core.read_text(r / "pr_body.md")
  commits = tdd_order.commits_of(worktree, entry["merge_base"])
  items = body_mod.dod_items(text)
  present = {path for _, kind, path in items if kind == "exists" and (worktree / path).exists()}
  # every input is read; the three files a run could edit are held whole, then the DoD `Run` items run
  config = worktree / core.run_git(["rev-parse", "--git-common-dir"], worktree).strip() / "config"
  held = [st.path("foreman", unit), config] + ([st.path("reviews", rid, f"round-{n}.json")] if rid else [])
  held = {path: path.read_bytes() if path.is_file() else None for path in held}
  pastes = {int(m.group(1)): last_line(m.group(2)) for m in DOD_RESULT_RE.finditer(pr_body)}
  runs = dod_runs([(i, cmd, pastes[i]) for i, kind, cmd in items if kind == "run" and i in pastes], worktree,
                  run_env(shutil.which("gh") or "gh", worktree), deadline, r / "dod")
  for path, raw in held.items():  # written back whole: an edit a run made to them is overwritten
    if raw is None:
      path.unlink(missing_ok=True)
    else:
      core.atomic_write(path, raw)
  for i, run in runs.items():
    if run["summary"] is not None:
      core.atomic_write(r / "dod" / f"{i}.txt", f"exit: {'none' if run['exit'] is None else run['exit']}\n"
                        f"summary: {run['summary']}\ntimed_out: {'yes' if run['timed_out'] else 'no'}\n")
  lines, contested = foreman_findings(n, verdict, text, scope, worktree, changed, pr_body, comments, login, prior, prior_ci_fid,
                                      commits, prior_tdd, prior_scope, contest_of,
                                      external, earlier, disposed, posted, handoff.config.get("owners") or [],
                                      recorded_rulings(data), data.get("decisions") or [], recorded_times(data),
                                      handoff.state["units"][unit].get("number"), runs=runs, prior_dod=prior_dod, present=present)
  entry.update(dod_runs=runs, test_delta=[])
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
  """Each recorded ruling's comment id to `(posted_at, unread)`: the entry's time (the comment as recorded) and
  whether it is an `unread` entry, whose `posted_at` is the host's clock, not GitHub's, so the comment's own
  creation time stands while the comment is there and the host's time only once it is gone."""
  return {int(cid): (e.get("posted_at") or "", bool(e.get("unread"))) for e in foreman.get("rulings") or []
          if (cid := str(e.get("posted") or "").removeprefix("comment ")).isdigit()}


def foreman_findings(round_n: int, ci_verdict: str, body: str, scope: list, worktree: Path, changed: list, pr_body: str,
                     comments: list, login: str, prior_round, prior_ci_fid, commits: list = (), prior_tdd: dict = None,
                     prior_scope: dict = None, contest_of: dict = None, external: list = (),
                     earlier: set = frozenset(), disposed: set = frozenset(), posted: dict = None,
                     owners: list = (), recorded: list = (), decisions: list = (), recorded_at: dict = None,
                     issue_number: int = None, runs: dict = None, prior_dod: dict = None, present: set = None) -> tuple:
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
  on the unit's issue (`issue_number`). An `unread` entry's `posted_at` is the host's clock, so its comment's own
  time is the bound, and when that comment is gone the host's time is (a fixed reply before the ruling never
  counts). A reply
  to a carried copy `foreman-<r>-<k>`, `fixed` or `contested`, counts (toward the carry, or as a contest) only
  when it comes after round r was posted (`posted`, each posted round's `posted_at`): before that the copy did
  not exist. The DoD re-run's `dod-<n>` highs (`runs`, `dod_runs`' record) follow the fenced-output check; an item
  number stays ruled by the owner's `dod-<n> allowed` or by an overrule or allowance of a posted `dod-<n>` fid
  (`prior_dod`, fid to item number), a contest's copy followed back to it. `present`, when given, is the `Exists`
  paths found before the runs."""
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
    if kind == "exists" and not (text in present if present is not None else (worktree / text).exists()):
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
  ruled = {int(r.subject[4:]) for r in rulings if r.kind == "allowed" and re.fullmatch(r"dod-\d+", r.subject)}
  found += dod_findings(body, runs or {}, ruled | {item for fid, item in (prior_dod or {}).items() if fid in overruled | allowed})
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
      at, unread = times.get(ruling.comment_id, ("", False))
      if c is None and ruling.comment_id in times:  # a recorded ruling whose comment is gone or no longer a form:
        c = {"kind": "issue", "number": issue_number, "id": ruling.comment_id, "at": at if unread else ""}  # an unread
      if ruling.kind not in ("upheld", "overruled") or c is None:  # one's stand-in takes the host's time, the only one left
        continue
      fid = ruling.subject
      answers = {fid, links.get(fid, fid)} | groups.get(origin(fid), set())  # the ruled finding, or any id of its group
      since = max(c["at"], "" if unread else at)  # from its record's time; an unread one from the comment's
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
