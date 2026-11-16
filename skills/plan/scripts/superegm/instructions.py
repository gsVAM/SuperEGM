# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the `instructions` key and the instructions subcommand (spec 1.2.1 section 3.1, U37); the dir entry's validation (section 3.5, U74).

"""superegm instructions: the `# Repository instructions` section of a role's brief (spec 1.2.1 section 3.1)."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

import superegm as core
from superegm import review

WRITES = frozenset(["runcards", "reviews", "instructions"])  # the store kinds this subcommand writes: the card's render, a round's, the `HEAD` path's reference copies
CONFIG_DEFAULTS = {"instructions": []}  # [{file: <repo-relative path>, to: [<role>, ...]}], frozen at approval
INIT_STEP, DOCTOR_CHECKS = "", None  # no init line or doctor line of its own
SKILLS = frozenset(["review-spec", "review-plan", "wave", "integrate"])  # the skills whose card this subcommand accepts (a judge panel renders through `render`)
ROLES = ("builder", "foreman", "reviewers", "judges")
LANES = ("local", "astra")
CONFIG = ".superegm/config.json"
LIMIT = 8192  # the most bytes a file may hold
DOC_LIMIT = 65_536  # the most bytes a reference document may hold
DOC_COUNT = 50  # the most reference documents one `dir` entry may name
INDEX_LINE = 120  # the most characters of a document's first line its index line keeps
BUDGET = 262_144  # the most bytes of reference documents the Astra lane's brief pastes, all together
INDEX_SENTENCE = ("Read a reference document when your task touches what its first line names; "
                  "cite it by file when a finding rests on it.")
SHAPE = ("instructions must be a list of {file: <repo-relative path> or dir: <repo-relative folder>, "
         "to: [non-empty list from builder, foreman, reviewers, judges]}, exactly one of file and dir")


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
    if not (isinstance(entry, dict) and set(entry) in ({"file", "to"}, {"dir", "to"})):
      return False
    path = entry.get("file", entry.get("dir"))
    return (isinstance(path, str) and path and "\0" not in path and not Path(path).is_absolute()
            and ".." not in Path(path).parts
            and isinstance(entry["to"], list) and entry["to"] and all(r in ROLES for r in entry["to"]))
  for entry in value if isinstance(value, list) else []:
    if isinstance(entry, dict) and "file" in entry and "dir" in entry:
      raise core.HandoffError(f"instructions entry {json.dumps(entry)}: exactly one of file and dir")
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


def mode(root: Path, ref: str, rel: str) -> str | None:
  """The tree mode of `rel` at `ref` (`100644`, `100755`, `120000` for a symlink, ...), or None when `ref` lacks it."""
  with core.hook_free() as pairs:
    shown = subprocess.run(["git", *pairs, "ls-tree", "-z", ref, "--", rel], cwd=str(root), capture_output=True)
  entry = shown.stdout.split(b"\0", 1)[0] if shown.returncode == 0 else b""
  return entry.split(b" ", 1)[0].decode() if entry else None


def documents(root: Path, ref: str, entry: dict, at: str | None = None) -> list[tuple[str, bytes]]:
  """`[(file, bytes)]` of the `*.md` files under `entry["dir"]` at `ref` (named `at`, else `ref`), recursively, in path
  order; a folder absent or holding none, more than `DOC_COUNT` files, a file over `DOC_LIMIT` bytes, not UTF-8 or not a
  regular file is refused, naming the folder or the file."""
  folder, where = entry["dir"].rstrip("/"), at or ref
  with core.hook_free() as pairs:
    shown = subprocess.run(["git", *pairs, "ls-tree", "-r", "-z", ref, "--", folder + "/"], cwd=str(root), capture_output=True)
  listed = {}
  for line in (shown.stdout.split(b"\0") if shown.returncode == 0 else []):
    meta, _, name = line.decode("utf-8", "surrogateescape").partition("\t")
    if name.startswith(folder + "/") and name.endswith(".md"):
      listed[name] = meta.split(" ", 1)[0]
  paths = sorted(listed)
  if not paths:
    raise core.HandoffError(f"instructions: {folder} is absent or holds no .md file at {where}")
  if len(paths) > DOC_COUNT:
    raise core.HandoffError(f"instructions: {paths[DOC_COUNT]} is file {DOC_COUNT + 1} of {folder}, over {DOC_COUNT}")
  found = []
  for name in paths:
    if listed[name] not in ("100644", "100755"):  # a symlink's blob is its target path
      raise core.HandoffError(f"instructions: {name} is not a regular file at {where}")
    data = blob(root, ref, name)
    if data is None:
      raise core.HandoffError(f"instructions: {name} is absent at {where}")
    if len(data) > DOC_LIMIT:
      raise core.HandoffError(f"instructions: {name} is {len(data)} bytes, over {DOC_LIMIT}")
    try:
      data.decode("utf-8")
    except UnicodeDecodeError:
      raise core.HandoffError(f"instructions: {name} is not UTF-8") from None
    found.append((name, data))
  return found


def flat(items: list) -> list[dict]:
  """The files of `items` (frozen or approved): a `file` item as it is, a `dir` item as one `{dir, to, file, sha, ...}`
  per document, in order."""
  out = []
  for item in items:
    if "dir" in item:
      out += [{**f, "dir": item["dir"], "to": item["to"]} for f in item["files"]]
    else:
      out.append(item)
  return out


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


def handoff_entry(st: core.Store, handoff_id: str) -> dict | None:
  """The last approval entry whose `handoff_id` is `handoff_id`, across `approvals/*.json`, or None."""
  found = None
  for path in sorted(st.path("approvals", "x").parent.glob("*.json")):
    for entry in core.load_approvals(st, path):
      if entry.get("handoff_id") == handoff_id:
        found = entry
  return found


def fenced(text: str) -> str:
  """`text` verbatim in a fence of backticks one longer than its longest backtick run (at least three)."""
  fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", text)), default=0))
  return f"{fence}\n{text if text.endswith(chr(10)) or not text else text + chr(10)}{fence}\n"


def section(files: list, index: str = "") -> str:
  """`# Repository instructions`, then each `(file, text)` under `## <file>` fenced, then `index` (the reference
  documents' section); `""` with neither."""
  if not files and not index:
    return ""
  parts = ["# Repository instructions\n"]
  for file, text in files:
    parts.append(f"\n## {file}\n{fenced(text)}")
  return "".join(parts) + index


def first_line(data: bytes) -> str:
  """The first non-empty line of a document, stripped, at most `INDEX_LINE` characters."""
  for line in data.decode("utf-8").splitlines():
    if line.strip():
      return line.strip()[:INDEX_LINE]
  return ""


def reference_index(st: core.Store, docs: list, lane: str) -> tuple[list[dict], str]:
  """`(manifest, text)` of the `## Reference documents` section for `docs` (`[(file, sha)]`, in index order); `([], "")` with none. Each line is read from the document's verified store copy `instructions/<sha>.md`. On the `local` lane
  it ends with the path to read; on the `astra` lane, which cannot read the store, the verified copy is pasted under
  its line, up to `BUDGET` bytes for all together, a document past it (and each after) keeping its line with a note and
  recorded `pasted: false`."""
  from superegm import approve_spec  # approve_spec imports this module
  if not docs:
    return [], ""
  manifest, parts, used, over = [], ["\n## Reference documents\n\n"], 0, False
  for file, sha in docs:
    data = approve_spec.read_raw(st, file, sha)
    line = f"- {file} ({sha}): {first_line(data)}"
    over = over or (lane == "astra" and used + len(data) > BUDGET)
    if lane != "astra":
      parts.append(f"{line} — read {approve_spec.raw_path(st, sha)}\n")
    elif over:
      parts.append(f"{line} (not pasted: over the {BUDGET:,}-byte brief budget)\n")
    else:
      used += len(data)
      parts.append(f"{line}\n{fenced(data.decode('utf-8'))}")
    manifest.append({"file": file, "sha": sha, **({"pasted": False} if over else {})})
  parts.append(f"\n{INDEX_SENTENCE}\n")
  return manifest, "".join(parts)


def render(st: core.Store, role: str, handoff_id: str | None = None, root: Path | None = None,
           lane: str = "local") -> tuple[list[dict], str]:
  """`(manifest [{file, sha}], text)` of `role`'s section for `lane`: with `handoff_id` that handoff's frozen list, each
  file read from its verified store copy; else the config and the files at `HEAD` under `root` (the checkout this runs
  in when `root` is None), both read from the one commit `HEAD` names when the render begins, a file absent there, over
  `LIMIT` bytes or not UTF-8 refused, naming it. The `HEAD` path writes each reference document's store copies, which
  the index (and the Astra lane's pastes) read; nothing else is stored."""
  manifest, text, _ = rendered(st, role, handoff_id, root, lane)
  return manifest, text


def rendered(st: core.Store, role: str, handoff_id: str | None, root: Path | None,
             lane: str = "local") -> tuple[list[dict], str, dict | None]:
  """`render`'s pair and the approval entry it read (None on the `HEAD` path or with no entry)."""
  from superegm import approve_spec  # approve_spec imports this module
  if handoff_id is not None:
    entry = handoff_entry(st, handoff_id)
    items = [i for i in (entry or {}).get("instructions") or [] if role in i["to"]]
    files = [(i["file"], i["sha"], approve_spec.read_copy(st, i["file"], i["sha"])) for i in items if "dir" not in i]
  else:  # HEAD resolved once, so a commit landing mid-render never mixes one commit's list with another's files
    entry, root = None, root if root is not None else core.git_toplevel(Path.cwd())
    commit = core.run_git(["rev-parse", "--verify", "-q", "HEAD^{commit}"], root, check=False).strip()
    listed = [i for i in head_list(root, commit) if role in i["to"]] if commit else []
    items = approve_spec.freeze(root, commit, listed, at="HEAD")
    files = [(i["file"], i["sha"], i["text"]) for i in items if "dir" not in i]
    for doc in flat([i for i in items if "dir" in i]):
      approve_spec.write_copy(st, doc, raw=True)
  docs = [(d["file"], d["sha"]) for d in flat([i for i in items if "dir" in i])]
  index_manifest, index = reference_index(st, docs, lane)
  manifest = [{"file": f, "sha": s} for f, s, _ in files] + index_manifest
  return manifest, section([(f, t) for f, _, t in files], index), entry


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
    manifest, text, entry = rendered(st, role, handoff_id, root, lane) if handoff_id is not None else ([], "", None)
    record.setdefault("instructions", {}).setdefault(role, {})[lane] = {
      "approved_at": (entry or {}).get("approved_at"), "manifest": manifest, "text": text}
    core.atomic_write(st.path("runcards", card), record)
    return manifest, text
  path = st.path("reviews", review, f"instructions-{round}-{role}-{lane}.json")
  if path.is_file():
    stored = json.loads(core.read_text(path))
    return stored["manifest"], stored["text"]
  manifest, text = render(st, role, handoff_id=handoff_id, root=root, lane=lane)
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
