# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the respec's touched units, derived marks, open and actionable respecs and `respec posted` (U85).

"""superegm respec: the units a spec correction touches (spec section 7.6), its derived marks and the posts and
relaunches it asks for; every mark is derived on read from `respec/` and the launch records, never `state.json`."""

import difflib
import json
from pathlib import Path
import re

import superegm as core
from superegm.review import approved_text, sections

WRITES = frozenset(["file"])  # `respec/` and the comment files are the store's `file` kind
BACKTICKED =re.compile(r"`([^`]+)`")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
HEADING_MARKER = re.compile(r"^\s*#+\s*$")
FOLLOWS = re.compile(r"Follows:\s*(U\d+)")
ROW_ID = re.compile(r"^\s*\|\s*(U\d+)\s*\|")
GLOBAL = "Global constraints"


def respec_path(store: core.Store, *name: str) -> Path:
  return store.path("file", "respec", *name)


def load_json(path: Path):
  return json.loads(core.read_text(path)) if path.is_file() else None


def spec_of(store: core.Store, handoff: str) -> Path:
  """The handoff's spec: `handoffs/<id>.json`'s `spec`, else the plan's `design.path`, else `state.json`'s."""
  record = load_json(store.path("handoffs", handoff)) or {}
  if record.get("spec"):
    return Path(record["spec"])
  hs = core.handoff_store(store, handoff)
  for kind in ("units", "state"):
    path = ((load_json(hs.path(kind)) or {}).get("design") or {}).get("path")
    if path:
      return Path(path)
  raise core.HandoffError(f"respec: handoff {handoff} names no spec")


def entries_of(store: core.Store, handoff: str, spec: Path) -> list:
  """The handoff's approval entries, voided ones left out, in history order."""
  return [e for e in core.load_approvals(store, spec) if e.get("handoff_id") == handoff and not e.get("voided_by")]


def opcodes(old: list[str], new: list[str]) -> list[list]:
  """The line map from `old` to `new`: `difflib`'s opcodes as `[tag, i1, i2, j1, j2]` (0-based, end exclusive)."""
  return [list(op) for op in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()]


def carry(ops: list, start: int, end: int) -> tuple[int, int]:
  """The 1-based range `start-end` carried through the line map `ops` to the new text's coordinates: a line in an
  equal block moves with it; a start in a changed block goes to the block's first new line, an end to its last."""
  def at(line, first):
    for tag, i1, i2, j1, j2 in ops:
      if i1 <= line - 1 < i2:
        return j1 + (line - 1 - i1) + 1 if tag == "equal" else (j1 + 1 if first else j2)
    return (ops[-1][4] if ops else line) if not first else (ops[-1][4] + 1 if ops else line)
  return at(start, True), at(end, False)


def changed_ranges(ops: list) -> list[tuple[int, int]]:
  """The diff's changed ranges in the old text's coordinates (1-based, inclusive): a replaced or deleted block's old
  lines; an insertion as the line it follows (the first line when it opens the text)."""
  return [(i1 + 1, i2) if i2 > i1 else (max(i1, 1), max(i1, 1)) for tag, i1, i2, _, _ in ops if tag != "equal"]


def added_lines(ops: list, new: list[str]) -> list[str]:
  return [line for tag, _, _, j1, j2 in ops if tag in ("replace", "insert") for line in new[j1:j2]]


def skipped(line: str) -> bool:
  """A shared line too common to name a unit: blank, a fence marker, a table separator row, a heading marker alone,
  or a line with no letter or digit."""
  text = line.strip()
  return (not text or bool(core.FENCE_RE.match(text)) or bool(TABLE_SEPARATOR.match(text))
          or bool(HEADING_MARKER.match(text)) or not any(ch.isalnum() for ch in text))


def section_lines(text: str, heading: str) -> set[str]:
  """The stripped lines under every H2 or H3 whose title is `heading`."""
  lines, found = text.splitlines(), set()
  for title, start, end in sections(text):
    if title.lstrip("#").strip() == heading:
      found |= {line.strip() for line in lines[start:end]}
  return found


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
  return a[0] <= b[1] and b[0] <= a[1]


def is_merged(record: dict) -> bool:
  return bool(record.get("landed") or (record.get("pr") or {}).get("merged_at"))


def history(store: core.Store, handoff: str):
  """`(spec, entries, texts, maps)`: the handoff's entries, each one's approved text as lines, and the line map of
  each consecutive pair (`maps[i]` from entry `i-1` to entry `i`; `maps[0]` empty)."""
  spec = spec_of(store, handoff)
  entries = entries_of(store, handoff, spec)
  if not entries:
    raise core.HandoffError(f"respec: handoff {handoff} has no approval")
  texts = []
  for entry in entries:
    text = approved_text(spec, entry)
    if text is None:
      raise core.HandoffError(f"respec: no commit holds approval {entry['sha256'][:7]} of {spec.name}")
    texts.append(text.splitlines())
  maps = [[]] + [opcodes(texts[i - 1], texts[i]) for i in range(1, len(texts))]
  return spec, entries, texts, maps


def carried_spans(units: dict, entries: list, maps: list) -> dict:
  """Each unit's Design range, read in the coordinates of the approval it was last rendered under (`rendered_under`,
  how many of the handoff's entries existed then; absent reads 1, the opening) and carried through each consecutive
  line map to the latest entry's coordinates."""
  carried = {}
  for u, record in units.items():
    span = record.get("design_range") or {}
    if not span.get("start"):
      continue
    a, b = span["start"], span["end"]
    for i in range(max(record.get("rendered_under") or 1, 1), len(entries)):
      a, b = carry(maps[i], a, b)
    carried[u] = (a, b)
  return carried


def comment_text(store: core.Store, handoff: str, text: str, unit: str, respec: str) -> str:
  """`respec_comment_<unit>_R<n>.md`: the diff hunks from the latest approved text to `text` in the unit's Design
  range (every hunk when the unit was touched by shared text alone)."""
  hs = core.handoff_store(store, handoff)
  _, entries, texts, maps = history(store, handoff)
  prev, new = texts[-1], text.splitlines()
  units = ((load_json(hs.path("units")) or {}).get("units")) or {}
  span = carried_spans(units, entries, maps).get(unit)
  hunks = [op for op in opcodes(prev, new) if op[0] != "equal"]
  own = [op for op in hunks if span and overlaps(span, (op[1] + 1, max(op[2], op[1] + 1)))]
  lines = [f"**Spec correction {respec}** for {unit}: the frozen spec changed; build to the lines below.", ""]
  for _, i1, i2, j1, j2 in own or hunks:
    lines += ["```diff", f"@@ -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1} @@",
              *(f"-{line}" for line in prev[i1:i2]), *(f"+{line}" for line in new[j1:j2]), "```", ""]
  return "\n".join(lines)


def touched(store: core.Store, handoff: str, text: str) -> dict:
  """The units the diff from the handoff's latest approved text to `text` touches (spec section 7.6), as
  `respec/R<n>.json` holds them: `touched`, `untouched`, `follow_ups` (each merged unit the range or Interfaces
  test touches, the range it overlaps and the follow-up row naming it, or None), `line_map` (the opcodes from the
  latest approved text to `text`) and `merged_review` (a merged unit only the shared-text or uncovered-range test
  touches). The draft (`--dry-run`) and the approval run this one function."""
  hs = core.handoff_store(store, handoff)
  spec, entries, texts, maps = history(store, handoff)
  root = core.git_toplevel(spec.parent)
  rel = spec.resolve().relative_to(root.resolve()).as_posix()
  prev, new = texts[-1], text.splitlines()
  ops = opcodes(prev, new)
  ranges = changed_ranges(ops)
  units = ((load_json(hs.path("units")) or {}).get("units")) or {}
  state = ((load_json(hs.path("state")) or {}).get("units")) or {}
  merged = {u for u in units if is_merged(state.get(u) or {})}
  bodies = {u: core.read_text(hs.path("unit", u)) if hs.path("unit", u).is_file() else "" for u in units}
  lines_of = {u: {line.strip() for line in body.splitlines()} for u, body in bodies.items()}
  global_of = {u: section_lines(body, GLOBAL) for u, body in bodies.items()}
  interfaces_of = {u: section_lines(body, "Interfaces") for u, body in bodies.items()}
  for i, entry in enumerate(entries):  # a prior applied respec's added lines are part of each touched unit's body
    if i and entry.get("kind") == "respec" and entry.get("respec"):
      prior = load_json(respec_path(hs, f"{entry['respec']}.json")) or {}
      added = {line.strip() for line in added_lines(maps[i], texts[i])}
      for u in prior.get("touched") or []:
        if u in lines_of:
          lines_of[u] |= added
  carried = carried_spans(units, entries, maps)
  spec_global = set()
  old_text = "\n".join(prev)
  for title, start, end in sections(old_text):
    if title.lstrip("#").strip() == GLOBAL:
      spec_global |= set(range(start, end + 1))
  hit, overlap, review = set(), {}, set()  # range or Interfaces (any unit); shared text or uncovered (merged: review)
  for u, span in carried.items():
    for r in ranges:
      if overlaps(span, r):
        hit.add(u)
        overlap.setdefault(u, r)
  for tag, i1, i2, j1, j2 in ops:
    if tag == "equal":
      continue
    r = (i1 + 1, i2) if i2 > i1 else (max(i1, 1), max(i1, 1))
    quoted = False
    for n in range(i1, i2):
      line = prev[n].strip()
      if not line:
        continue
      for u in units:
        counts = n + 1 in spec_global or line in global_of[u] or not skipped(line)
        if not counts:
          continue
        if line in lines_of[u]:
          quoted = True
          (review if u in merged else hit).add(u)
        if line in interfaces_of[u] and "Produces:" in line:  # the producer, and every unit whose Consumes names it
          names = BACKTICKED.findall(line) or [line]
          for v, held in interfaces_of.items():
            if v == u or any("Consumes:" in l and any(name in l for name in names) for l in held):
              hit.add(v)
              overlap.setdefault(v, r)
    covered = any(overlaps(span, r) for span in carried.values())
    trivial = all(skipped(line) for line in prev[i1:i2] + new[j1:j2])
    if not covered and not quoted and not trivial:
      hit |= set(units) - merged
      review |= merged
  rows = {}
  for line in added_lines(ops, new):
    follows, row = FOLLOWS.search(line), ROW_ID.match(line)
    if follows and row:
      rows.setdefault(follows.group(1), row.group(1))
  follow_ups = [{"unit": u, "overlaps": f"{rel}:{overlap[u][0]}-{overlap[u][1]}", "row": rows.get(u)}
                for u in sorted(hit & merged)]
  return {"touched": sorted(hit), "untouched": sorted(set(units) - hit), "follow_ups": follow_ups,
          "line_map": ops, "merged_review": sorted(review - hit)}


CLEARING = ("DONE", "DONE_WITH_CONCERNS")  # a builder status that clears a mark on an unchanged head


def is_stopped(store: core.Store, unit: str) -> bool:
  return bool(core.load_foreman(store, unit).get("stopped"))


def latest_handoff(store: core.Store, spec: Path) -> str | None:
  latest = core.load_approval(store, spec)
  return (latest or {}).get("handoff_id")


def commit_time(root: Path, sha: str) -> float | None:
  """The committer time of `sha` in `root`, as `status` reads a worktree head's (U31); None when git cannot."""
  try:
    return float(core.run_git(["log", "-1", "--format=%ct", sha], root).strip())
  except (core.HandoffError, ValueError, OSError):
    return None


def cleared(store: core.Store, root: Path, unit: str, respec: str, record: dict) -> bool:
  """A filed unit's `respec: R<n>` is cleared when its saved PR head is a commit made after the `started_at` of a
  launch whose `respecs` name R<n>, or when such a launch exited 0, the saved head equals the `head` it recorded and its
  `builder_status` is `DONE` or `DONE_WITH_CONCERNS`."""
  head = (record.get("pr") or {}).get("head")
  if not head:
    return False
  data = load_json(store.path("launches", unit)) or {}
  naming = [e for e in data.get("launches") or [] if isinstance(e, dict) and respec in (e.get("respecs") or [])]
  if not naming:
    return False
  when = commit_time(root, head)
  for entry in naming:
    try:
      started = core.epoch(entry.get("started_at"))
    except (TypeError, ValueError):
      continue
    if when is not None and when > started:
      return True
  return any(e.get("status") == "exited 0" and e.get("head") == head and e.get("builder_status") in CLEARING
             for e in naming)


def marks(store: core.Store, handoff: str) -> dict:
  """Unit to `replan: R<n>` (unfiled) or `respec: R<n>` (filed, unmerged), derived on every read from the applied
  respecs' `respec/R<n>.json` `touched`, `handoff_units.json`'s `corrected` and `rendered_under`, `state.json`'s saved
  PR heads and the launch records; never written. Stopped and merged units are left out, and a handoff a later approval
  supersedes carries none."""
  spec = spec_of(store, handoff)
  if latest_handoff(store, spec) != handoff:
    return {}
  hs = core.handoff_store(store, handoff)
  units = (load_json(hs.path("units")) or {}).get("units") or {}
  state = (load_json(hs.path("state")) or {}).get("units") or {}
  root = core.git_toplevel(spec if spec.is_absolute() else Path.cwd() / spec)
  out = {}
  for count, entry in enumerate(entries_of(store, handoff, spec), start=1):
    respec = entry.get("respec") if entry.get("kind") == "respec" else None
    applied = load_json(respec_path(hs, f"{respec}.json")) if respec else None
    for unit in (applied or {}).get("touched") or []:
      record = state.get(unit) or {}
      if unit in out or is_merged(record) or is_stopped(hs, unit):
        continue
      if not record.get("number"):
        row = units.get(unit) or {}
        if respec not in (row.get("corrected") or []) and (row.get("rendered_under") or 0) < count:
          out[unit] = f"replan: {respec}"
      elif not cleared(hs, root, unit, respec, record):
        out[unit] = f"respec: {respec}"
  return out


OPEN_FILE = re.compile(r"^(R\d+)\.open\.json$")


def open(store: core.Store, handoff: str) -> list:  # noqa: A001, the interface's name (spec section 7.6)
  """The open respecs of `handoff`, each its `respec/R<n>.open.json` record: the file exists, no approval entry names
  it, its unit (when it has one) is not stopped and `handoff` is the latest approval's. Withdrawn and applied respecs
  are left out."""
  spec = spec_of(store, handoff)
  if latest_handoff(store, spec) != handoff:
    return []
  hs = core.handoff_store(store, handoff)
  folder = respec_path(hs)
  if not folder.is_dir():
    return []
  named = {e.get("respec") for e in core.load_approvals(store, spec) if e.get("handoff_id") == handoff}
  out = []
  for path in sorted(folder.iterdir(), key=lambda p: (len(p.name), p.name)):
    match = OPEN_FILE.match(path.name)
    if not match or match.group(1) in named:
      continue
    record = load_json(path) or {}
    if record.get("unit") and is_stopped(hs, record["unit"]):
      continue
    out.append(record | {"id": match.group(1)})
  return out


def live_launch(store: core.Store, unit: str) -> bool:
  data = load_json(store.path("launches", unit)) or {}
  return any(isinstance(e, dict) and e.get("status") == "running" for e in data.get("launches") or [])


def eligible(store: core.Store, unit: str, record: dict) -> bool:
  """A unit a respec may post to or relaunch: not stopped or merged, no pending owner decision (section 7.2), no live
  launch of its own. Launch slots are not read: a relaunch is queued for `launch`'s ready-again set, which takes one."""
  from superegm.review import open_decisions  # at call time: the review loop is heavy to import
  return not (is_merged(record) or is_stopped(store, unit) or open_decisions(store, unit) or live_launch(store, unit))


def actionable(store: core.Store, handoff: str) -> list:
  """`("post" | "relaunch", "R<n>", "<unit>")` for each applied respec of `handoff`: a post while the unit's comment file
  exists and `respec/R<n>.<unit>.posted` is absent, a relaunch while its `respec: R<n>` mark stands, each on an
  eligible unit only. Nothing is written and nothing launched; a withdrawn handoff has none."""
  spec = spec_of(store, handoff)
  if latest_handoff(store, spec) != handoff:
    return []
  hs = core.handoff_store(store, handoff)
  state = (load_json(hs.path("state")) or {}).get("units") or {}
  standing = marks(store, handoff)
  out = []
  for entry in entries_of(store, handoff, spec):
    respec = entry.get("respec") if entry.get("kind") == "respec" else None
    applied = load_json(respec_path(hs, f"{respec}.json")) if respec else None
    for unit in (applied or {}).get("touched") or []:
      record = state.get(unit) or {}
      if not record.get("number") or not eligible(hs, unit, record):
        continue
      if not respec_path(hs, f"{respec}.{unit}.posted").is_file():
        out.append(("post", respec, unit))
      if standing.get(unit) == f"respec: {respec}":
        out.append(("relaunch", respec, unit))
  return out


SKILLS = frozenset(["wave"])  # the skills whose card `respec posted` accepts: the wave posts the comment
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own


def register(subparsers):
  p = subparsers.add_parser("respec", help="a respec's records (spec section 7.6)")
  action = p.add_subparsers(dest="action", required=True)
  posted = core.add_parser(action, "posted", "record that the wave posted respec R<n>'s comment on a unit's issue")
  posted.add_argument("--respec", required=True, help="R<n>")
  posted.add_argument("--unit", required=True)
  posted.add_argument("--comment", required=True, help="the posted comment's id")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  return {"posted": record_posted}[args.action](args)


def record_posted(args) -> int:
  """`respec posted`: write `respec/R<n>.<unit>.posted` (`{respec, unit, comment, at}`) in the handoff's directory."""
  core.require_runcard(args, SKILLS)
  st = core.store(core.git_toplevel(Path.cwd()))
  if not re.fullmatch(r"R\d+", args.respec):
    raise core.HandoffError(f"respec posted: {args.respec} is not R<n>")
  if not respec_path(st, f"{args.respec}.json").is_file():
    raise core.HandoffError(f"respec posted: respec {args.respec} is not applied")
  if args.unit not in (load_json(respec_path(st, f"{args.respec}.json")) or {}).get("touched", []):
    raise core.HandoffError(f"respec posted: {args.unit} is not touched by {args.respec}")
  path = respec_path(st, f"{args.respec}.{args.unit}.posted")
  core.atomic_write(path, {"respec": args.respec, "unit": args.unit, "comment": args.comment, "at": core.now_iso()})
  core.journal(st, f"{args.unit} respec {args.respec} comment {args.comment} posted")
  print(f"posted: {path.name}")
  return 0
