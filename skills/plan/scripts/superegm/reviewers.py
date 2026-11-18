# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the reviewers module: `.superegm/reviewers/*.md` loaded and checked (spec 1.2.1 section 3.6, U76).

"""superegm reviewers: the repository's custom review goldfish, `.superegm/reviewers/<id>.md` (spec 1.2.1 section 3.6)."""

import json
from pathlib import Path
import re
import subprocess

import superegm as core

WRITES = frozenset(["reviews"])  # the store kinds this subcommand writes: a spec cycle's `persona-<n>-<id>.json`
SKILLS = frozenset(["review-spec", "review-plan", "integrate", "wave"])  # the skills whose card `--brief` accepts (the foreman's card is a child of the wave card)
CONFIG_DEFAULTS = {}  # no config key of its own: a file under `.superegm/reviewers/` is the setting
INIT_STEP, DOCTOR_CHECKS = "", None  # no init line of its own; its doctor line is `doctor`'s
DIR = ".superegm/reviewers"
KINDS = ("spec", "plan", "head", "integrate")
LIMIT = 8192  # the most bytes of persona a file may hold
ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
NOT_REVIEWERS = ("foreman", "judge", "cartographer", "triage", "astra")  # roles that are not reviewers (the Astra lane is no goldfish): no file may take their id


def blob_sha(data: bytes) -> str:
  """git's blob sha of `data`, 12 hex."""
  from superegm import instructions
  return instructions.blob_sha(data)


def refuse(rel: str, reason: str) -> core.HandoffError:
  """The refusal for the file `rel`, naming it."""
  return core.HandoffError(f"{rel}: {reason}")


def frontmatter(rel: str, text: str) -> tuple[dict, str]:
  """`text`'s frontmatter as `{key: value}` (a `[a, b]` or block-list value a list) and the body after it; refused when it
  does not open with one, repeats a key or holds a line that is none of the forms below.
  shortcut: only `key: value` lines, `[a, b]` lists, `- item` block lists and `#` comment lines; not the whole of YAML."""
  lines = text.split("\n")
  if not lines or lines[0].rstrip() != "---":
    raise refuse(rel, "does not open with a frontmatter block")
  try:
    end = next(i for i in range(1, len(lines)) if lines[i].rstrip() == "---")
  except StopIteration:
    raise refuse(rel, "the frontmatter is not closed by ---") from None
  fields, listing = {}, None  # `listing`: the key whose block list is open
  for line in lines[1:end]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
      continue
    if stripped == "-" or stripped.startswith("- "):
      if listing is None:
        raise refuse(rel, f"the frontmatter line {line!r} is not `key: value`")
      fields[listing].append(stripped[1:].strip().strip("'\""))
      continue
    key, sep, value = line.partition(":")
    key, value = key.strip(), value.strip()
    if not sep or not key or line[0] in " \t":
      raise refuse(rel, f"the frontmatter line {line!r} is not `key: value`")
    if key in fields:
      raise refuse(rel, f"the frontmatter key {key!r} appears twice")
    listing = None
    if value.startswith("[") and value.endswith("]"):
      fields[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
    elif not value:
      fields[key], listing = [], key  # `key:` alone opens a block list
    else:
      fields[key] = value.strip("'\"")
  return fields, "\n".join(lines[end + 1:])


def parse(rel: str, data: bytes) -> dict:
  """The reviewer the file `rel` holds, `{id, name, kinds, model, effort, text, sha, source}` (`source` the file's text, which
  the store copy keeps so that its sha can be re-derived); refused naming `rel` and the reason.
  The size limit counts the body as written, less the file's last newlines; the persona is the body without its leading
  blank lines and trailing whitespace, so the first line keeps its indentation."""
  stem = Path(rel).stem
  if not ID_RE.match(stem):
    raise refuse(rel, f"the id {stem!r} does not match [a-z][a-z0-9-]{{1,31}}")
  if stem in NOT_REVIEWERS:
    raise refuse(rel, f"{stem} is not a reviewer and cannot be overridden")
  try:
    text = data.decode("utf-8")
  except UnicodeDecodeError:
    raise refuse(rel, "is not UTF-8") from None
  fields, body = frontmatter(rel, text)
  name = fields.get("name")
  if not isinstance(name, str) or not name:
    raise refuse(rel, "name is required")
  kinds = fields.get("kinds")
  if not isinstance(kinds, list) or not kinds or not set(kinds) <= set(KINDS) or len(set(kinds)) != len(kinds):
    raise refuse(rel, f"kinds must be a non-empty list of distinct kinds from {', '.join(KINDS)}")
  model, effort = fields.get("model"), fields.get("effort")
  if model is not None and (not isinstance(model, str) or not core.MODEL_RE.match(model)):
    raise refuse(rel, f"model {model!r} is not a model alias")
  efforts = (*core.EFFORTS, "max")  # the forms `config.reviewers.effort` takes
  if effort is not None and effort not in efforts:
    raise refuse(rel, f"effort {effort!r} is not one of {', '.join(efforts)}")
  size = len(body.rstrip("\n").encode("utf-8"))
  if size > LIMIT:
    raise refuse(rel, f"the body is {size} bytes, over {LIMIT}")
  persona = re.sub(r"\A(?:[ \t]*\n)+", "", body).rstrip()
  return {"id": stem, "name": name, "kinds": kinds, "model": model, "effort": effort, "text": persona, "sha": blob_sha(data), "source": text}


def load(root: Path, ref: str | None = None) -> dict[str, dict]:
  """`{id: {name, kinds, model, effort, text, sha, source}}` from `.superegm/reviewers/*.md` under `root` (the working tree, which
  follows a symlink and sees an uncommitted file: what `doctor` shows), or at `ref` when given (what `approve-spec` and a
  spec review read); the first bad file is refused, naming it and the reason, and so is a ref or a blob git cannot read."""
  found = {}
  if ref is None:
    for path in sorted((root / DIR).glob("*.md")):
      rel = f"{DIR}/{path.name}"
      if path.is_file():
        try:
          data = path.read_bytes()
        except OSError as error:
          raise refuse(rel, f"cannot be read: {error.strerror or error}") from None
        found[path.stem] = {k: v for k, v in parse(rel, data).items() if k != "id"}
    return found
  from superegm import instructions
  with core.hook_free() as pairs:
    listed = subprocess.run(["git", *pairs, "ls-tree", "-z", "--name-only", ref, f"{DIR}/"], cwd=str(root), capture_output=True)
  if listed.returncode != 0:
    raise core.HandoffError(f"{DIR}: cannot list it at {ref}: {listed.stderr.decode('utf-8', 'replace').strip()}")
  for rel in sorted(n for n in listed.stdout.decode("utf-8", "replace").split("\0") if n.endswith(".md")):
    data = instructions.blob(root, ref, rel)
    if data is None:
      raise refuse(rel, f"cannot be read at {ref}")
    found[Path(rel).stem] = {k: v for k, v in parse(rel, data).items() if k != "id"}
  return found


def copy_of(st: core.Store, item: dict) -> dict:
  """The reviewer the store copy of the approval entry's `item` ({id, sha}) holds: its `source` (the file's text) must hash
  to the sha and parse as the file `<id>.md`, and every field is read from that source, the return being
  `{name, kinds, model, effort, text, sha, source}`. The copy is named by the sha alone,
  so files of one content (two of one list, or one renamed between approvals) share it, whichever `id` wrote it."""
  rel = f"{DIR}/{item['id']}.md"
  path = st.path("reviewers", item["sha"])
  try:
    copy = json.loads(core.read_text(path))
  except (OSError, ValueError):
    raise core.HandoffError(f"{rel}: the store copy {path.name} is missing or unreadable") from None
  source = copy.get("source") if isinstance(copy, dict) else None
  if not isinstance(source, str) or blob_sha(source.encode("utf-8")) != item["sha"]:
    raise core.HandoffError(f"{rel}: the store copy {path.name} does not match the approval entry")
  return {k: v for k, v in parse(rel, source.encode("utf-8")).items() if k != "id"}


def frozen(st: core.Store, handoff_id: str | None, only=None) -> dict[str, dict] | None:
  """`{id: {name, kinds, model, effort, text, sha, source}}` the approval entry of `handoff_id` froze, each read from its verified
  store copy (`{}` for an entry freezing none: an absent field reads `[]`), or None with no such entry; with `only` (ids),
  just those are read, so one missing copy refuses no other reviewer."""
  from superegm import instructions
  entry = instructions.handoff_entry(st, handoff_id) if handoff_id else None
  if entry is None:
    return None
  return {item["id"]: copy_of(st, item) for item in entry.get("reviewers") or [] if only is None or item["id"] in only}


def available(st: core.Store, root: Path, kind: str, handoff_id: str | None = None, only=None) -> dict[str, dict]:
  """The reviewers a review of `kind` reads: a spec review's at `HEAD`; any other kind's the handoff's frozen copies, and
  none when the handoff has no approval entry (a file at `HEAD` was never frozen: a builder's branch changes no reviewer).
  A file's `kinds` is the kinds a repository reviewer may open on; an override of a built-in replaces its persona wherever
  that built-in reviews, so `review open` consults `kinds` for the ids that are not built-ins only."""
  if kind == "spec":
    return load(root, "HEAD")
  return frozen(st, handoff_id, only) or {}


def stored_read(path: Path) -> dict:
  """`{id, sha, text}` the spec cycle's stored read `path` (`persona-<n>-<id>.json`) holds; refused naming the file when it
  is damaged (not JSON, not an object, or short of a string `id`, `sha` or `text`)."""
  try:
    read = json.loads(core.read_text(path))
  except (OSError, ValueError):
    read = None
  if not isinstance(read, dict) or not all(isinstance(read.get(k), str) for k in ("id", "sha", "text")):
    raise core.HandoffError(f"{path.name}: the stored persona read is damaged; remove it and run `reviewers --brief` again")
  return read


def persona_of(st: core.Store, review: dict, rid: str, n: int, reviewer: str) -> dict | None:
  """`{id, sha}` the round's record of `reviewer` carries, the persona it read: a spec review's stored read
  (`persona-<n>-<id>.json`, which a `--brief` stores; none stored, none recorded, so HEAD is never inferred at record
  time), any other kind's the handoff's frozen copy of that one reviewer; None for a built-in with no file and for any
  name that is not a reviewer. A repository reviewer (not a built-in) of a spec round with no stored read is refused:
  its record would carry no evidence of the persona it read."""
  from superegm import review as reviews
  if reviewer == "astra" or reviewer == "foreman" or reviewer.startswith("external:"):
    return None
  if review["kind"] == "spec":
    path = st.path("reviews", rid, f"persona-{n}-{reviewer}.json")
    if path.is_file():
      read = stored_read(path)
      return {"id": read["id"], "sha": read["sha"]}
    if reviewer not in reviews.REVIEWERS:
      raise core.HandoffError(f"{reviewer} has no stored persona read for round {n}; run `reviewers --brief {reviewer} --spec ... --review {rid} --round {n}` first")
    return None
  found = (frozen(st, review.get("handoff_id"), {reviewer}) or {}).get(reviewer)
  return {"id": reviewer, "sha": found["sha"]} if found else None


def brief(args, st: core.Store) -> str:
  """The persona text `--brief` prints: the handoff's frozen copy, or a spec review's `HEAD` read, stored once for the round."""
  from superegm import instructions
  if args.handoff:
    record = core.load_card(st, args.runcard)
    opened = record.get("handoff", st.handoff_id)  # a card without the key: the store's handoff
    if opened != args.handoff:
      raise core.HandoffError(f"--handoff {args.handoff}: {args.runcard} was opened under handoff {opened}")
    held = frozen(st, args.handoff, {args.brief})
    if held is None:
      raise core.HandoffError(f"--handoff {args.handoff}: no approval entry")
    if args.brief not in held:
      raise core.HandoffError(f"{args.brief} is not frozen in handoff {args.handoff}")
    return held[args.brief]["text"]
  if not args.review or args.round is None:
    raise core.HandoffError("--spec requires --review and --round")
  if args.round < 1:
    raise core.HandoffError(f"--round {args.round}: a round is 1 or more")
  design = Path(args.design).expanduser().resolve()
  instructions.require_review(st, args.review, design)
  path = st.path("reviews", args.review, f"persona-{args.round}-{args.brief}.json")
  if path.is_file():
    return stored_read(path)["text"]
  found = load(core.git_toplevel(design), "HEAD").get(args.brief)
  if found is None:
    raise core.HandoffError(f"unknown reviewer {args.brief}")
  core.atomic_write(path, {"id": args.brief, "sha": found["sha"], "text": found["text"]})
  return found["text"]


def register(subparsers):
  p = core.add_parser(subparsers, "reviewers", "print a repository reviewer's persona, frozen or at HEAD")
  p.add_argument("--brief", required=True, metavar="ID", help="the reviewer id")
  p.add_argument("--handoff", help="the handoff whose frozen copy to print")
  p.add_argument("--spec", dest="design", help="a spec review's: the file at HEAD")
  p.add_argument("--review", help="with --spec: the review id")
  p.add_argument("--round", type=int, help="with --spec: the round")
  p.add_argument("--unit", help="with --handoff: the unit whose card (the foreman's child card) this runs under")
  p.set_defaults(run=run, writes=WRITES)


def run(args) -> int:
  if args.unit and args.design:  # --unit lets a unit's card pass for --handoff; with --spec it would pass any spec
    raise core.HandoffError("reviewers: --unit goes with --handoff, not --spec")
  core.require_runcard(args, SKILLS)
  if bool(args.handoff) == bool(args.design):
    raise core.HandoffError("reviewers: exactly one of --handoff and --spec is required")
  if args.handoff and (args.review or args.round is not None):
    raise core.HandoffError("reviewers: --review and --round go with --spec, not --handoff")
  st = core.STORE or core.store(core.git_toplevel(Path.cwd()), args)
  try:
    text = brief(args, st)
  except core.HandoffError as error:
    message = str(error)
    raise core.HandoffError(message if message.startswith("reviewers: ") else f"reviewers: {message}") from None
  print(text)
  return 0
