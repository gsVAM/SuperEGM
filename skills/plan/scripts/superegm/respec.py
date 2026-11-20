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

BACKTICKED = re.compile(r"`([^`]+)`")
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
  # each unit's Design range, in the coordinates of the approval it was last rendered under, carried to `prev`'s
  carried = {}
  for u, record in units.items():
    span = record.get("design_range") or {}
    if not span.get("start"):
      continue
    a, b = span["start"], span["end"]
    for i in range(max(record.get("rendered_under") or 1, 1), len(entries)):
      a, b = carry(maps[i], a, b)
    carried[u] = (a, b)
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
