# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_approve` as the approve-spec module (U03); the section 8 form: a converged
# review, the `Units` check, the commit by path, `--void` and `--amend-units` (U04).

"""superegm approve-spec: record the owner's approval of a converged spec (spec section 8)."""

from pathlib import Path
import re

import superegm as core
from superegm.review import evaluate, latest_cycle, review_id

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
  handoff_id = f"{handoff_slug(spec.stem)}-{sha[:6]}"
  commit = commit_by_path(root, [spec.relative_to(root).as_posix(), CONFIG], f"superegm: approve {slug} at review {rid}")
  record = {"path": str(spec), "sha256": sha, "commit": commit, "runcard": args.runcard, "review": rid,
            "approved_at": core.now_iso(), "amended": [], "voided_by": None, "handoff_id": handoff_id}
  path = st.path("approvals", slug)
  core.atomic_write(path, record)
  core.journal(st, f"approve-spec {handoff_id} sha256 {sha[:12]} at review {rid} commit {commit[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0
