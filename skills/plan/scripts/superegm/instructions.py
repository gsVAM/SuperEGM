# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the `instructions` key and the instructions subcommand (spec 1.2.1 section 3.1, U37).

"""superegm instructions: the `# Repository instructions` section of a role's brief (spec 1.2.1 section 3.1)."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

import superegm as core
from superegm import review

WRITES = frozenset(["runcards", "reviews"])  # the store kinds this subcommand writes: the card's render, a round's
CONFIG_DEFAULTS = {"instructions": []}  # [{file: <repo-relative path>, to: [<role>, ...]}], frozen at approval
INIT_STEP, DOCTOR_CHECKS = "", None  # no init line or doctor line of its own
SKILLS = frozenset(["review-spec", "review-plan", "wave", "integrate", "judges"])  # the skills whose card this subcommand accepts
ROLES = ("builder", "foreman", "reviewers", "judges")
LANES = ("local", "astra")
CONFIG = ".superegm/config.json"
LIMIT = 8192  # the most bytes a file may hold
SHAPE = "instructions must be a list of {file: <repo-relative path>, to: [non-empty list from builder, foreman, reviewers, judges]}"


def register(subparsers):
  p = core.add_parser(subparsers, "instructions", "print a role's # Repository instructions section")
  p.add_argument("--role", required=True, choices=ROLES)
  p.add_argument("--lane", choices=LANES, default="local")
  p.add_argument("--spec", dest="design", help="a spec review's: the config and the files at HEAD")
  p.add_argument("--review", help="with --spec: the review id")
  p.add_argument("--round", type=int, help="with --spec: the round")
  p.add_argument("--unit", help="with --handoff: the unit whose card (the foreman's child card) this runs under")
  p.set_defaults(run=run, writes=WRITES)


def check(value) -> list:
  """`value` when it is a well-formed `instructions` list; else refused, naming the key."""
  def good(entry):
    return (isinstance(entry, dict) and set(entry) == {"file", "to"} and isinstance(entry["file"], str) and entry["file"]
            and "\0" not in entry["file"] and not Path(entry["file"]).is_absolute() and ".." not in Path(entry["file"]).parts
            and isinstance(entry["to"], list) and entry["to"] and all(r in ROLES for r in entry["to"]))
  if not isinstance(value, list) or not all(good(e) for e in value):
    raise core.HandoffError(f"{SHAPE}, not {json.dumps(value)}")
  return value


def blob_sha(data: bytes) -> str:
  """git's blob sha of `data`, 12 hex: the name of its store copy."""
  return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()[:12]


def blob(root: Path, ref: str, rel: str) -> bytes | None:
  """The bytes of `rel` at `ref`, or None when `ref` lacks it (hook-free)."""
  with core.hook_free() as pairs:
    shown = subprocess.run(["git", *pairs, "cat-file", "blob", f"{ref}:{rel}"], cwd=str(root), capture_output=True)
  return shown.stdout if shown.returncode == 0 else None


def head_list(root: Path, ref: str = "HEAD") -> list:
  """The `instructions` list of the config committed at `ref` (`[]` when it lacks the config or the key)."""
  data = blob(root, ref, CONFIG)
  if data is None:
    return []
  try:
    config = json.loads(data.decode("utf-8"))
  except ValueError:
    config = None
  if not isinstance(config, dict):
    raise core.HandoffError(f"instructions: the {CONFIG} committed at HEAD is not a JSON object")
  return check(config.get("instructions", []))


def handoff_list(st: core.Store, handoff_id: str) -> list:
  """The frozen `instructions` of the last approval entry whose `handoff_id` is `handoff_id`, across
  `approvals/*.json` (`[]` with no such entry; an entry without the key reads `[]`)."""
  return list((handoff_entry(st, handoff_id) or {}).get("instructions") or [])


def handoff_entry(st: core.Store, handoff_id: str) -> dict | None:
  """The last approval entry whose `handoff_id` is `handoff_id`, across `approvals/*.json`, or None."""
  found = None
  for path in sorted(st.path("approvals", "x").parent.glob("*.json")):
    for entry in core.load_approvals(st, path):
      if entry.get("handoff_id") == handoff_id:
        found = entry
  return found


def section(files: list) -> str:
  """`# Repository instructions`, then each `(file, text)` under `## <file>`, its text verbatim in a fence of backticks
  one longer than its longest backtick run (at least three); `""` with no file."""
  if not files:
    return ""
  parts = ["# Repository instructions\n"]
  for file, text in files:
    fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))
    parts.append(f"\n## {file}\n{fence}\n{text if text.endswith(chr(10)) or not text else text + chr(10)}{fence}\n")
  return "".join(parts)


def render(st: core.Store, role: str, handoff_id: str | None = None, root: Path | None = None) -> tuple[list[dict], str]:
  """`(manifest [{file, sha}], text)` of `role`'s section: with `handoff_id` that handoff's frozen list, each file read
  from its verified store copy; else the config and the files at `HEAD` under `root` (the checkout this runs in when
  `root` is None), both read from the one commit `HEAD` names when the render begins, a file absent there, over `LIMIT`
  bytes or not UTF-8 refused, naming it. Stores nothing."""
  manifest, text, _ = rendered(st, role, handoff_id, root)
  return manifest, text


def rendered(st: core.Store, role: str, handoff_id: str | None, root: Path | None) -> tuple[list[dict], str, dict | None]:
  """`render`'s pair and the approval entry it read (None on the `HEAD` path or with no entry)."""
  from superegm import approve_spec  # approve_spec imports this module
  if handoff_id is not None:
    entry = handoff_entry(st, handoff_id)
    files = [(i["file"], i["sha"], approve_spec.read_copy(st, i["file"], i["sha"]))
             for i in (entry or {}).get("instructions") or [] if role in i["to"]]
  else:  # HEAD resolved once, so a commit landing mid-render never mixes one commit's list with another's files
    entry, root = None, root if root is not None else core.git_toplevel(Path.cwd())
    commit = core.run_git(["rev-parse", "--verify", "-q", "HEAD^{commit}"], root, check=False).strip()
    listed = [i for i in head_list(root, commit) if role in i["to"]] if commit else []
    files = [(i["file"], i["sha"], i["text"]) for i in approve_spec.freeze(root, commit, listed, at="HEAD")]
  return [{"file": f, "sha": s} for f, s, _ in files], section([(f, t) for f, _, t in files]), entry


def render_stored(st: core.Store, role: str, lane: str = "local", *, card: str | None = None, review: str | None = None,
                  round: int | None = None, handoff_id: str | None = None, root: Path | None = None) -> tuple[list[dict], str]:
  """The store-once path: the render stored for that card (or that review's round), role and lane when one exists,
  else `render`'s, stored there first: on the card as `instructions.<role>.<lane>` (`{approved_at, manifest, text}`,
  `approved_at` the approval entry read, null with none), or as `reviews/<id>/instructions-<n>-<role>-<lane>.json`
  (`{manifest, text}`). A later call returns the stored one whatever `HEAD` or the latest approval is then."""
  if card is not None:  # a card renders its handoff's frozen list, nothing with no handoff id (a flat 1.0 store), never HEAD
    record = core.load_card(st, card)
    opened = record.get("handoff", st.handoff_id)  # a card without the key: the store's handoff
    if handoff_id is not None and opened != handoff_id:
      raise core.HandoffError(f"--handoff {handoff_id}: {card} was opened under handoff {opened}")
    stored = ((record.get("instructions") or {}).get(role) or {}).get(lane)
    if stored is not None:
      return stored["manifest"], stored["text"]
    manifest, text, entry = rendered(st, role, handoff_id, root) if handoff_id is not None else ([], "", None)
    record.setdefault("instructions", {}).setdefault(role, {})[lane] = {
      "approved_at": (entry or {}).get("approved_at"), "manifest": manifest, "text": text}
    core.atomic_write(st.path("runcards", card), record)
    return manifest, text
  path = st.path("reviews", review, f"instructions-{round}-{role}-{lane}.json")
  if path.is_file():
    stored = json.loads(core.read_text(path))
    return stored["manifest"], stored["text"]
  manifest, text = render(st, role, handoff_id=handoff_id, root=root)
  core.atomic_write(path, {"manifest": manifest, "text": text})
  return manifest, text


def require_review(st: core.Store, rid: str, design: Path) -> None:
  """`rid` is one of the spec review cycles of `design`, so a card for one spec never stores a round's render under
  another spec's review, an integrate review or a path outside `reviews/`."""
  if rid not in review.cycle_ids(st, "spec", str(design)):
    raise core.HandoffError(f"--review {rid}: not a spec review of {design}")


def run(args):
  if args.unit and args.design:  # --unit lets a unit's card pass for --handoff; with --spec it would pass any spec
    raise core.HandoffError("instructions: --unit goes with --handoff, not --spec")
  core.require_runcard(args, SKILLS)
  if bool(args.handoff) == bool(args.design):
    raise core.HandoffError("instructions: exactly one of --handoff and --spec is required")
  if args.handoff and (args.review or args.round is not None):
    raise core.HandoffError("instructions: --review and --round go with --spec, not --handoff")
  st = core.STORE or core.store(core.git_toplevel(Path.cwd()), args)
  try:
    if args.design:
      if not args.review or args.round is None:
        raise core.HandoffError("--spec requires --review and --round")
      if args.round < 1:
        raise core.HandoffError(f"--round {args.round}: a round is 1 or more")
      design = Path(args.design).expanduser().resolve()
      require_review(st, args.review, design)
      _, text = render_stored(st, args.role, args.lane, review=args.review, round=args.round,
                              root=core.git_toplevel(design))
    else:  # render_stored refuses a card opened under another handoff
      _, text = render_stored(st, args.role, args.lane, card=args.runcard, handoff_id=args.handoff)
  except core.HandoffError as error:
    message = str(error)
    raise core.HandoffError(message if message.startswith("instructions: ") else f"instructions: {message}") from None
  print(text, end="")
  return 0
