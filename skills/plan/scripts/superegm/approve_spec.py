# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_approve` as the approve-spec module (U03); the section 8 form: a converged
# review, the `Units` check, the commit by path, `--void` and `--amend-units` (U04).

"""superegm approve-spec: record the owner's approval of a converged spec (spec section 8)."""

from pathlib import Path
import re

import superegm as core
from superegm.review import evaluate, findings_of, latest_cycle, load_review, load_round, review_id, round_numbers

WRITES = frozenset(["approvals"])  # the store kinds this subcommand writes
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


def handoff_id_for(st: core.Store, sha: str, stem: str) -> str:
  """`state.json`'s id while the handoff is open (a `handoff_id` and no `closed_at`), else a fresh one."""
  state = core.load_state(st.root)
  if state.get("handoff_id") and not state.get("closed_at"):
    return state["handoff_id"]
  return f"{handoff_slug(stem)}-{sha[:6]}"


def before_units(text: str) -> str:
  """The text up to and including the last `## … Units` line (the whole text when there is none)."""
  lines = text.splitlines(keepends=True)
  last = max((i for i, line in enumerate(lines) if UNITS_H2.match(line)), default=len(lines))
  return "".join(lines[:last + 1])


def commit_by_path(repo_root: Path, paths: list[str], message: str) -> str:
  """Add and commit `paths` alone, ignoring other changes in the tree; the commit may be empty."""
  core.run_git(["add", "--", *paths], repo_root)
  core.run_git(["commit", "--allow-empty", "-q", "-m", message, "--", *paths], repo_root)
  return core.run_git(["rev-parse", "HEAD"], repo_root).strip()


def run(args):
  card = core.require_runcard(args, SKILLS)
  spec = Path(args.design).expanduser().resolve()
  if not spec.is_file():
    raise core.HandoffError(f"approve-spec: spec {spec} does not exist")
  root = core.git_toplevel(spec)
  st = core.store(root)
  slug = core.spec_slug(spec)
  if args.void:
    return void_approval(args, st, spec)
  if args.amend_units:
    return amend_units(args, st, spec, root)
  review, _ = latest_cycle(st, "spec", str(spec))
  if review is None:
    raise core.HandoffError(f"approve-spec: no spec review for {slug}")
  rid = review_id(st, "spec", str(spec), review["cycle"])
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
  if not (args.yes or args.leavemealone or card["mode"] == "leavemealone"):
    print(f"Approve `{spec}` (sha256 `{sha[:12]}`) at review {rid}?")
    print("Options: Approve | Stop. Run again with --yes after the owner chose Approve.")
    return 0
  handoff_id = handoff_id_for(st, sha, spec.stem)
  commit = commit_by_path(root, [spec.relative_to(root).as_posix(), CONFIG], f"superegm: approve {slug} at review {rid}")
  record = {"path": str(spec), "sha256": sha, "commit": commit, "runcard": args.runcard, "review": rid,
            "approved_at": core.now_iso(), "amended": [], "voided_by": None, "handoff_id": handoff_id}
  path = st.path("approvals", slug)
  core.atomic_write(path, record)
  core.journal(st, f"approve-spec {handoff_id} sha256 {sha[:12]} at review {rid} commit {commit[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0


def void_approval(args, st: core.Store, spec: Path) -> int:
  """`--void --review <id>`: the approval is void once that review records a `fix-design` finding."""
  if not args.review:
    raise core.HandoffError("approve-spec: --void requires --review")
  slug, rid = core.spec_slug(spec), args.review
  approval = core.load_approval(st, spec)
  if approval is None:
    raise core.HandoffError(f"approve-spec: no approval for {slug}")
  if load_review(st, rid) is None:
    raise core.HandoffError(f"approve-spec: review {rid}: not opened")
  if not any(f["disposition"] == "fix-design" for n in round_numbers(st, rid) for f in findings_of(load_round(st, rid, n))):
    raise core.HandoffError(f"approve-spec: review {rid} has no fix-design finding")
  approval["voided_by"] = rid
  core.atomic_write(st.path("approvals", slug), approval)
  core.journal(st, f"approve-spec void {slug} by review {rid} under {args.runcard}")
  print(f"approval of {slug} voided by review {rid}")
  return 0


def amend_units(args, st: core.Store, spec: Path, root: Path) -> int:
  """`--amend-units` (section 12): rows appended to `## Units` are re-approved without a review round;
  any change to a line before that heading refuses."""
  slug = core.spec_slug(spec)
  approval = core.load_approval(st, spec)
  if approval is None:
    raise core.HandoffError("approve-spec: no approval to amend")
  rel = spec.relative_to(root).as_posix()
  approved = core.run_git(["show", f"{approval['commit']}:{rel}"], root)
  if before_units(approved) != before_units(core.read_text(spec)):
    raise core.HandoffError("approve-spec: a line outside ## Units changed")
  sha = core.sha256_file(spec)
  commit = commit_by_path(root, [rel, CONFIG], f"superegm: approve {slug} at review {approval['review']}")
  approval.update({"sha256": sha, "commit": commit})
  approval["amended"].append({"sha256": sha, "commit": commit, "at": core.now_iso()})
  path = st.path("approvals", slug)
  core.atomic_write(path, approval)
  core.journal(st, f"approve-spec amend-units {approval['handoff_id']} sha256 {sha[:12]} commit {commit[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0
