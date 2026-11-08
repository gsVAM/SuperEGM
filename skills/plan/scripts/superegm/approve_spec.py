# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_approve` as the approve-spec module (U03); the section 8 form: a converged
# review, the `Units` check, the commit by path, `--void` and `--amend-units` (U04); the escalated pairs recorded (U16);
# the approval history, one handoff per opening, the latest-entry rule and the branch check (U20); the spec PR's
# ingest once before the refusals and the refusal of an unsettled external finding (U26).

"""superegm approve-spec: record the owner's approval of a converged spec (spec section 8)."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

import superegm as core
from superegm import close
from superegm.review import evaluate, findings_of, ingest_pr, latest_cycle, load_review, load_round, review_id, round_numbers

WRITES = frozenset(["approvals", "handoffs", "state", "reviews"])  # the store kinds this subcommand writes
SKILLS = frozenset(["review-spec", "review-plan", "integrate"])  # the skills whose card this subcommand accepts
CONFIG = ".superegm/config.json"
UNITS_H2 = re.compile(r"^## (?:\d+\.?\s+)?Units\s*$")


def register(subparsers):
  p = core.add_parser(subparsers, "approve-spec", "record the owner's approval of a converged spec")
  p.add_argument("--spec", dest="design", required=True)
  p.add_argument("--yes", action="store_true", help="the owner answered Approve")
  p.add_argument("--leavemealone", action="store_true", help="the converged record is the approval")
  p.add_argument("--void", action="store_true", help="void the approval after a fix-design finding")
  p.add_argument("--review", help="with --void: the review holding the fix-design finding")
  p.add_argument("--amend-units", dest="amend_units", action="store_true",
                 help="re-approve rows appended to ## Units without a review round")
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


def entry_of(sha, commit, runcard, review, handoff_id, kind, escalated) -> dict:
  return {"sha256": sha, "commit": commit, "runcard": runcard, "review": review, "approved_at": core.now_iso(),
          "handoff_id": handoff_id, "kind": kind, "voided_by": None, "escalated": escalated}


def units_section(text: str) -> str:
  """The spec from its last `## Units` heading to the end; empty without one."""
  lines = text.splitlines(keepends=True)
  starts = [i for i, line in enumerate(lines) if UNITS_H2.match(line)]
  return "".join(lines[starts[-1]:]) if starts else ""


def escalated_pairs(st: core.Store, spec: Path, since: int) -> list:
  """Every `escalated` finding of the spec's review cycles above `since`, as `<review id>:<finding id>`
  in round order, less the pairs the spec's `## Units` section names (D2 (a))."""
  named, pairs, cycle = units_section(core.read_text(spec)), [], since + 1
  while load_review(st, rid := review_id(st, "spec", str(spec), cycle)) is not None:
    pairs += [f"{rid}:{f['id']}" for n in round_numbers(st, rid) for f in findings_of(load_round(st, rid, n))
              if f["disposition"] == "escalated"]
    cycle += 1
  return [pair for pair in pairs if pair not in named]


def before_units(text: str) -> str:
  """The text up to and including the last `## … Units` line (the whole text when there is none)."""
  lines = text.splitlines(keepends=True)
  last = max((i for i, line in enumerate(lines) if UNITS_H2.match(line)), default=len(lines))
  return "".join(lines[:last + 1])


def branch_holds(repo_root: Path, rel: str, sha256: str) -> bool:
  """Whether a commit of the current branch's `git log -- <rel>` holds a blob of `rel` hashing to `sha256`."""
  for commit in core.run_git(["log", "--format=%H", "--", rel], repo_root, check=False).split():
    blob = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=str(repo_root), capture_output=True)
    if blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == sha256:
      return True
  return False


def require_branch_holds(st: core.Store, repo_root: Path, rel: str, entry: dict) -> None:
  """Refuse a branch that never folded the history's last entry: no commit of it holds that entry's bytes."""
  if not branch_holds(repo_root, rel, entry["sha256"]):
    raise core.HandoffError(f"approve-spec: fold {st.config['base']} first: approval {entry['sha256'][:7]} is not in this branch")


def commit_by_path(repo_root: Path, paths: list[str], message: str, trailer: str) -> str:
  """Add and commit `paths` alone, ignoring other changes in the tree, `trailer` (when set) after a
  blank line; the commit may be empty."""
  core.run_git(["add", "--", *paths], repo_root)
  core.run_git(["commit", "--allow-empty", "-q", "-m", message, *(["-m", trailer] if trailer else []), "--", *paths], repo_root)
  return core.run_git(["rev-parse", "HEAD"], repo_root).strip()


def spec_pr(repo: str, branch: str) -> int | None:
  """The open PR whose head is `branch` (the elephant's spec PR, spec section 8), or None: none means nothing to read."""
  try:
    prs = json.loads(core.gh(["pr", "list", "-R", repo, "--head", branch, "--state", "open", "--limit", "1000",
                              "--json", "number,headRefOid"]) or "[]")
  except core.GhError as error:
    raise core.HandoffError(f"approve-spec: {error}") from None
  return prs[0]["number"] if prs else None


def run(args):
  card = core.require_runcard(args, SKILLS)
  spec = Path(args.design).expanduser().resolve()
  if not spec.is_file():
    raise core.HandoffError(f"approve-spec: spec {spec} does not exist")
  root = core.git_toplevel(spec)
  st = core.store(root)
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
  review, _ = latest_cycle(st, "spec", str(spec))
  if review is None:
    raise core.HandoffError(f"approve-spec: no spec review for {slug}")
  rid = review_id(st, "spec", str(spec), review["cycle"])
  number = spec_pr(st.config["repo"], core.run_git(["rev-parse", "--abbrev-ref", "HEAD"], root).strip())
  # U26: one `review ingest --pr` before the refusals: it reads the spec PR's threads, writes them, and the carried
  # findings, into the latest round and posts the fixed replies; no open PR, or a cycle with no round yet to take
  # the threads, reads nothing (the latter is refused below as not converged); a gh failure refuses in one line.
  if number is not None and round_numbers(st, rid):
    _, unsettled = ingest_pr(st, review, number, card.get("parent") or args.runcard)
    if unsettled:
      fid = unsettled[0]
      raise core.HandoffError(f"approve-spec: {fid.rsplit('-', 2)[0]} {fid} unsettled on PR {number}")
  status = evaluate(st, review, card.get("parent") or args.runcard)
  if status.code != 0:
    raise core.HandoffError(f"approve-spec: review {rid} is not converged (review status exit {status.code})")
  sha = core.sha256_file(spec)
  if sha != status.sha:
    raise core.HandoffError("approve-spec: spec bytes differ from the converged round's")
  if not units_is_last_h2(core.read_text(spec)):
    raise core.HandoffError("approve-spec: last H2 must be `Units`")
  if not (root / CONFIG).is_file():
    raise core.HandoffError(f"approve-spec: {CONFIG} missing: run superegm init")
  last = core.load_approval(st, spec)
  if last:
    require_branch_holds(st, root, spec.relative_to(root).as_posix(), last)
  escalated =escalated_pairs(st, spec, int(last["review"].rsplit("-c", 1)[1]) if last and last.get("review") else 0)
  if escalated:
    print(f"approve-spec: {len(escalated)} escalated finding(s) await the owner: {', '.join(escalated)}")
  if not (args.yes or args.leavemealone or card["mode"] == "leavemealone"):
    print(f"Approve `{spec}` (sha256 `{sha[:12]}`) at review {rid}?")
    print("Options: Approve | Stop. Run again with --yes after the owner chose Approve.")
    return 0
  handoff_id, kind = handoff_id_for(st, sha, spec.stem, core.load_approvals(st, spec))
  commit = commit_by_path(root, [spec.relative_to(root).as_posix(), CONFIG], f"superegm: approve {slug} at review {rid}",
                          st.config["commit_trailer"])
  entry = entry_of(sha, commit, args.runcard, rid, handoff_id, kind, escalated)
  path = append_entry(st, spec, entry)
  write_handoff_file(st, handoff_id, spec, entry["approved_at"] if kind == "opening" else None)
  core.journal(st, f"approve-spec {kind} {handoff_id} sha256 {sha[:12]} at review {rid} commit {commit[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0


def void_approval(args, st: core.Store, spec: Path) -> int:
  """`--void --review <id>`: the latest approval (the history's last entry) is void once that review records
  a `fix-design` finding; its handoff, when its `state.json` files no unit, closes through `close`'s write."""
  if not args.review:
    raise core.HandoffError("approve-spec: --void requires --review")
  slug, rid = core.spec_slug(spec), args.review
  entries = core.load_approvals(st, spec)
  if not entries:
    raise core.HandoffError(f"approve-spec: no approval for {slug}")
  if load_review(st, rid) is None:
    raise core.HandoffError(f"approve-spec: review {rid}: not opened")
  if not any(f["disposition"] == "fix-design" for n in round_numbers(st, rid) for f in findings_of(load_round(st, rid, n))):
    raise core.HandoffError(f"approve-spec: review {rid} has no fix-design finding")
  path = st.path("approvals", slug)
  record = json.loads(core.read_text(path))
  if "entries" in record:
    entries[-1]["voided_by"] = rid
    write_entries(st, spec, entries)
  else:  # a 1.1 record is its one entry: `voided_by` written in place, nothing migrated
    entries[-1]["voided_by"] = record["voided_by"] = rid
    core.atomic_write(path, record)
  core.journal(st, f"approve-spec void {slug} by review {rid} under {args.runcard}")
  hid = entries[-1].get("handoff_id")
  voided = core.handoff_store(st, hid)
  state = handoff_state(st, hid) or {"handoff_id": hid}  # a handoff never planned: a minimal state.json
  if hid and not files_a_unit(state) and not state.get("closed_at"):
    close.write_closed(voided, state, "voided")
  print(f"approval of {slug} voided by review {rid}")
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
                                         list(approval.get("escalated") or [])))
  write_handoff_file(st, approval["handoff_id"], spec, None)
  core.journal(st, f"approve-spec amend-units {approval['handoff_id']} sha256 {sha[:12]} commit {commit[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0
