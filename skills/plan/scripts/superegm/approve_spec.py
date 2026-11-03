# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_approve` as the approve-spec module; the approval is `approvals/<spec-slug>.json`, not state.

"""superegm approve-spec: check the spec and record the owner's approval."""

import re
from pathlib import Path

import superegm as core

WRITES = frozenset(['approvals', 'state'])  # the store kinds this subcommand writes
SKILLS = frozenset(['review-spec'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "approve-spec", "check the spec and record the owner's approval")
  p.add_argument("--design", required=True)
  p.add_argument("--yes", action="store_true", help="the owner answered Approve")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  design = Path(args.design).expanduser().resolve()
  if not design.is_file():
    raise core.HandoffError(f"design {design} does not exist")
  root = core.git_toplevel(design)
  st = core.store(root)
  if not core.run_git(["ls-files", "--error-unmatch", "--", str(design)], root, check=False).strip():
    raise core.HandoffError(f"{design} is not tracked by git (an ignored or untracked "
                            f"file passes a clean `status`): commit it first (Phase 4)")
  if core.run_git(["status", "--porcelain", "--", str(design)], root).strip():
    raise core.HandoffError(f"{design} is tracked but not clean: commit it first (Phase 4)")
  text = core.read_text(design)
  for heading in ("## Detailed Implementation Plan", "### Target Files to Create/Modify",
                  "### Verification Plan"):
    if heading not in text:
      raise core.HandoffError(f"{design} has no `{heading}`: run egm-draft and egm-review "
                              "(Stage 9) first; a design without an implementation plan "
                              "cannot be handed off")
  sha = core.sha256_file(design)
  commit = core.run_git(["rev-parse", "--short", "HEAD"], root).strip()
  rel = design.relative_to(root).as_posix()
  if not core.run_git(["cat-file", "-t", f"{commit}:{rel}"], root, check=False).strip():
    raise core.HandoffError(f"{rel} does not exist at commit {commit}: commit it first (Phase 4)")
  if not args.yes:
    print(f"Approve `{design}` (sha256 `{sha[:12]}`, commit `{commit}`) for handoff?")
    print("Options: Approve | Stop. Run again with --yes after the user chose Approve.")
    return 0
  slug = re.sub(r"[^a-z0-9]+", "-", design.stem.lower()).strip("-")[:20].rstrip("-")
  handoff_id = f"{slug}-{sha[:6]}"
  core.require_binding(st.root, handoff_id)
  record = {"path": str(design), "sha256": sha, "commit": commit, "runcard": args.runcard,
            "review": None, "approved_at": core.now_iso(), "amended": [], "voided_by": None,
            "handoff_id": handoff_id}
  path = st.path("approvals", core.spec_slug(design))
  core.atomic_write(path, record)
  state = core.load_state(st.root)
  state["design"] = {"path": str(design), "sha256": sha, "commit": commit}
  core.save_state(st.root, state)
  core.journal(st, f"approve-spec {handoff_id} sha256 {sha[:12]} under {args.runcard}")
  print(f"approval recorded in {path}")
  return 0
