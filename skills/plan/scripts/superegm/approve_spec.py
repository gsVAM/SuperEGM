# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_approve` as the approve-spec module.

"""superegm approve-spec: check the design and record the user's approval."""

import re
import time
from pathlib import Path

import superegm as core


def register(subparsers):
  p = core.add_parser(subparsers, "approve-spec", "check the design and record the user's approval")
  p.add_argument("--design", required=True)
  p.add_argument("--artifacts", required=True, help="the artifact directory")
  p.add_argument("--evidence")
  p.add_argument("--yes", action="store_true", help="the user answered Approve")
  p.set_defaults(run=run)


def run(args):
  design = Path(args.design).expanduser().resolve()
  artifacts = Path(args.artifacts).expanduser().resolve()
  artifacts.mkdir(parents=True, exist_ok=True)
  core.ARTIFACT_DIR = artifacts
  if not design.is_file():
    raise core.HandoffError(f"design {design} does not exist")
  root = core.git_toplevel(design)
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
  evidence = None
  if args.evidence:
    evidence = Path(args.evidence).expanduser().resolve()
    if not evidence.is_file():
      raise core.HandoffError(f"evidence {evidence} does not exist")
    if design.name not in core.read_text(evidence):
      raise core.HandoffError(f"{evidence} does not name {design.name}")
  sha = core.sha256_file(design)
  commit = core.run_git(["rev-parse", "--short", "HEAD"], root).strip()
  rel = design.relative_to(root).as_posix()
  if not core.run_git(["cat-file", "-t", f"{commit}:{rel}"], root, check=False).strip():
    raise core.HandoffError(f"{rel} does not exist at commit {commit}: commit it first (Phase 4)")
  stamp = time.strftime("%Y-%m-%d", time.gmtime(evidence.stat().st_mtime)) if evidence else None
  question = (f"Approve `{design}` (sha256 `{sha[:12]}`, commit `{commit}`) for handoff? "
              f"Evidence: {f'`{evidence}` (modified {stamp})' if evidence else 'none given'}.")
  if not args.yes:
    state = core.load_state(artifacts)
    state["pending_approval"] = {"design": str(design), "design_sha256": sha,
                                 "commit": commit, "asked_at": core.now_iso()}
    core.save_state(artifacts, state)
    print(question)
    print("Options: Approve | Stop. Run again with --yes after the user chose Approve.")
    return 0
  state = core.load_state(artifacts)
  slug = re.sub(r"[^a-z0-9]+", "-", design.stem.lower()).strip("-")[:20].rstrip("-")
  core.require_binding(artifacts, f"{slug}-{sha[:6]}")
  pending = state.get("pending_approval") or {}
  if pending.get("design_sha256") and pending["design_sha256"] != sha:
    raise core.HandoffError(
        f"the design changed since the question was asked (approved "
        f"{pending['design_sha256'][:12]}, now {sha[:12]}): ask again before "
        f"recording an approval")
  state.pop("pending_approval", None)
  state["approval"] = {"design": str(design), "design_sha256": sha, "commit": commit,
                       "evidence": str(evidence) if evidence else None,
                       "answer": "Approve", "approved_at": core.now_iso()}
  state["design"] = {"path": str(design), "sha256": sha, "commit": commit}
  core.save_state(artifacts, state)
  print(f"approval recorded in {core.state_path(artifacts)}")
  return 0
