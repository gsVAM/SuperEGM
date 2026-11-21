# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the respec's touched units, derived marks, open and actionable respecs and `respec posted` (U85); `respec open` from a review's design finding (U91).

"""superegm respec: the units a spec correction touches (spec section 7.6), its derived marks and the posts and
relaunches it asks for; every mark is derived on read from `respec/` and the launch records, never `state.json`."""

import difflib
import json
import os
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
UNITS_H2 = re.compile(r"^## (?:\d+\.?\s+)?Units\s*$")  # as approve_spec reads the Units heading
INTERFACE = ("- Produces:", "- Consumes:")
GLOBAL = "Global constraints"


def respec_path(store: core.Store, *name: str) -> Path:
  return store.path("file", "respec", *name)


def load_json(path: Path):
  return json.loads(core.read_text(path)) if path.is_file() else None


def spec_of(store: core.Store, handoff: str, root: Path | None = None) -> Path:
  """The handoff's spec: `handoffs/<id>.json`'s `spec`, else the plan's `design.path`, else `state.json`'s; with `root`,
  rebased onto that checkout (`core.rebased`), so a spec approved in a worktree since removed is read where it lives."""
  record = load_json(store.path("handoffs", handoff)) or {}
  found = record.get("spec")
  if not found:
    hs = core.handoff_store(store, handoff)
    for kind in ("units", "state"):
      found = ((load_json(hs.path(kind)) or {}).get("design") or {}).get("path")
      if found:
        break
  if found:
    return core.rebased(Path(found), root) if root is not None else Path(found)
  raise core.HandoffError(f"respec: handoff {handoff} names no spec")


def entries_of(store: core.Store, handoff: str, spec: Path) -> list:
  """The handoff's approval entries in history order, voided ones included: an after-void approval's text is mapped
  from the voided one's, and `rendered_under` counts every entry (the latest is chosen apart, `core.load_approval`)."""
  return [e for e in core.load_approvals(store, spec) if e.get("handoff_id") == handoff]


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
  return [span_of(op) for op in ops if op[0] != "equal"]


def span_of(op: list) -> tuple[int, int]:
  """One opcode's place in the old text (1-based, inclusive): its old lines, or for an insertion the line it follows."""
  _, i1, i2, _, _ = op
  return (i1 + 1, i2) if i2 > i1 else (max(i1, 1), max(i1, 1))


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


def unfenced(lines: list[str]) -> list[tuple[int, str]]:
  """`(index, line)` for each line outside a fenced block, a fence's own lines left out (as `review.sections` reads
  a fence)."""
  out, fence = [], None
  for number, line in enumerate(lines):
    if fence:
      if re.match(rf"^ {{0,3}}{fence[0]}{{{fence[1]},}}\s*$", line):
        fence = None
    elif (opener := core.FENCE_RE.match(line)) and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
      fence = (opener.group(1)[0], len(opener.group(1)))
    else:
      out.append((number, line))
  return out


def interface_lines(body: str) -> set[str]:
  """A unit file's `- Produces:` and `- Consumes:` lines outside fences: its plan section's Interfaces, never the
  fenced issue body `graph` appends."""
  return {line.strip() for _, line in unfenced(body.splitlines()) if line.strip().startswith(INTERFACE)}


def interface_name(line: str) -> str:
  """The one name an Interfaces line declares, compared whole: its first backticked span, else its text after the
  colon less a trailing `(U<n>)`; any later backticked word (`None`, `file`) is prose, never a name."""
  found = BACKTICKED.search(line)
  return found.group(1).strip() if found else re.sub(r"\s*\(U\d+\)\s*$", "", line.split(":", 1)[1]).strip()


def units_span(text: str) -> tuple[int, int] | None:
  """The 1-based inclusive line range of the spec's last `## Units` section, or None."""
  spans = [(start, end) for title, start, end in sections(text) if UNITS_H2.match(title)]
  return spans[-1] if spans else None


def units_rows(text: str) -> dict:
  """Row id to row line of the spec's last `## Units` table, fenced lines left out."""
  span = units_span(text)
  if not span:
    return {}
  return {m.group(1): line for n, line in unfenced(text.splitlines())
          if span[0] <= n + 1 <= span[1] and (m := ROW_ID.match(line))}


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
  return a[0] <= b[1] and b[0] <= a[1]


def is_merged(record: dict) -> bool:
  return bool(record.get("landed") or (record.get("pr") or {}).get("merged_at"))


def history(store: core.Store, handoff: str, root: Path | None = None):
  """`(spec, entries, texts, maps)`: the handoff's entries, each one's approved text as lines, and the line map of
  each consecutive pair (`maps[i]` from entry `i-1` to entry `i`; `maps[0]` empty); `root` as in `spec_of`."""
  spec = spec_of(store, handoff, root)
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
  """`respec_comment_<unit>_R<n>.md`: every diff hunk from the latest approved text to `text` that `hunk_units`, the
  rule `touched` runs, selects the unit for (its Design range, a shared line its body or a prior respec's added lines
  quote, an Interfaces line it produces or consumes, an uncovered line), in diff order."""
  ctx = context(store, handoff, text)
  prev, new = ctx["prev"], ctx["new"]
  lines = [f"**Spec correction {respec}** for {unit}: the frozen spec changed; build to the lines below.", ""]
  picked = [op for op in ctx["ops"] if op[0] != "equal" and unit in set().union(*hunk_units(ctx, op)[:2])]
  for _, i1, i2, j1, j2 in picked:  # a zero-length side starts at the line before the gap, as unified diff prints it
    old_at, new_at = i1 + 1 if i2 > i1 else i1, j1 + 1 if j2 > j1 else j1
    lines += ["```diff", f"@@ -{old_at},{i2 - i1} +{new_at},{j2 - j1} @@",
              *(f"-{line}" for line in prev[i1:i2]), *(f"+{line}" for line in new[j1:j2]), "```", ""]
  return "\n".join(lines)


def touched(store: core.Store, handoff: str, text: str) -> dict:
  """The units the diff from the handoff's latest approved text to `text` touches (spec section 7.6), as
  `respec/R<n>.json` holds them: `touched`, `untouched`, `follow_ups` (each merged unit the range or Interfaces
  test touches, the range it overlaps and the follow-up row naming it, or None), `line_map` (the opcodes from the
  latest approved text to `text`) and `merged_review` (a merged unit only the shared-text or uncovered-range test
  touches). The draft (`--dry-run`) and the approval run this one function."""
  ctx = context(store, handoff, text)
  units, merged, ops = ctx["units"], ctx["merged"], ctx["ops"]
  hit, overlap, review = set(), {}, set()  # range or Interfaces (any unit); shared text or uncovered (merged: review)
  selected = [(op, hunk_units(ctx, op)) for op in ops if op[0] != "equal"]
  for op, (op_hit, op_review, _, _) in selected:
    hit |= op_hit
    review |= op_review
  for which in (2, 3):  # a merged unit's overlap: its first range hunk, else its first Interfaces hunk
    for op, picked in selected:
      for u in picked[which]:
        overlap.setdefault(u, span_of(op))
  rows, held = {}, units_rows("\n".join(ctx["prev"]))  # a new row of the Units table, its Follows naming the merged unit
  for rid, line in units_rows(text).items():
    follows = FOLLOWS.search(line)
    if rid not in held and follows:
      rows.setdefault(follows.group(1), rid)
  follow_ups = [{"unit": u, "overlaps": f"{ctx['rel']}:{overlap[u][0]}-{overlap[u][1]}", "row": rows.get(u)}
                for u in sorted(hit & merged)]
  return {"touched": sorted(hit), "untouched": sorted(set(units) - hit), "follow_ups": follow_ups,
          "line_map": ops, "merged_review": sorted(review - hit)}


def context(store: core.Store, handoff: str, text: str) -> dict:
  """What `hunk_units` reads for the diff from the handoff's latest approved text to `text`: the units, their carried
  Design ranges, quoted lines (prior applied respecs' added lines included), Global constraints and Interfaces lines,
  the merged units and the spec's own Global constraints line numbers."""
  hs = core.handoff_store(store, handoff)
  spec, entries, texts, maps = history(store, handoff)
  root = core.git_toplevel(spec.parent)
  rel = spec.resolve().relative_to(root.resolve()).as_posix()
  prev, new = texts[-1], text.splitlines()
  ops = opcodes(prev, new)
  units = ((load_json(hs.path("units")) or {}).get("units")) or {}
  state = ((load_json(hs.path("state")) or {}).get("units")) or {}
  merged = {u for u in units if is_merged(state.get(u) or {})}
  bodies = {u: core.read_text(hs.path("unit", u)) if hs.path("unit", u).is_file() else "" for u in units}
  lines_of = {u: {line.strip() for line in body.splitlines()} for u, body in bodies.items()}
  global_of = {u: section_lines(body, GLOBAL) for u, body in bodies.items()}
  interfaces_of = {u: interface_lines(body) for u, body in bodies.items()}
  for i, entry in enumerate(entries):  # a prior applied respec's added lines are part of each touched unit's body
    if i and entry.get("kind") == "respec" and entry.get("respec"):
      prior = load_json(respec_path(hs, f"{entry['respec']}.json")) or {}
      added = {line.strip() for line in added_lines(maps[i], texts[i])}
      for u in prior.get("touched") or []:
        if u in lines_of:
          lines_of[u] |= added
  spec_global = set()
  for title, start, end in sections("\n".join(prev)):
    if title.lstrip("#").strip() == GLOBAL:
      spec_global |= set(range(start, end + 1))
  table = lambda lines: (lambda s: set(range(s[0] - 1, s[1])) if s else set())(units_span("\n".join(lines)))
  return {"rel": rel, "prev": prev, "new": new, "ops": ops, "units": units, "merged": merged, "lines_of": lines_of,
          "global_of": global_of, "names_of": {u: {interface_name(l) for l in held} for u, held in interfaces_of.items()},
          "spec_global": spec_global, "carried": carried_spans(units, entries, maps),
          "table_old": table(prev), "table_new": table(new), "rows_old": set(units_rows("\n".join(prev)))}


def hunk_units(ctx: dict, op: list) -> tuple[set, set, set, set]:
  """`(hit, review, ranged, interfaced)` for one changed hunk, the rule `touched` and `comment_text` share: a unit whose
  carried Design range the hunk overlaps (`ranged`); a unit whose body quotes a line the hunk removes or changes, a
  `## Global constraints` line always counting and any other line unless `skipped` (merged: `review`); every unit whose
  Interfaces declare the name of a `- Produces:` or `- Consumes:` line the hunk removes or inserts, its producer and
  every consumer, names compared whole (`interfaced`); a `## Units` table line, the unit its row names and none for a
  new follow-up row (`Follows: U<n>`), never the uncovered rule (merged: `review`); and, for each other changed line no
  Design range covers, no body quotes and `skipped` passes, every unmerged unit (merged: `review`). A replace's new
  line past the old block's length has no old counterpart: it is judged as an insertion, never as quoted."""
  _, i1, i2, j1, j2 = op
  prev, new, units, merged = ctx["prev"], ctx["new"], ctx["units"], ctx["merged"]
  carried = ctx["carried"].values()
  hit, review, interfaced = set(), set(), set()
  for line, is_new in [(prev[n], False) for n in range(i1, i2) if n in ctx["table_old"]] + \
                      [(new[n], True) for n in range(j1, j2) if n in ctx["table_new"]]:
    row = ROW_ID.match(line)
    if not row or row.group(1) not in units or (is_new and row.group(1) not in ctx["rows_old"] and FOLLOWS.search(line)):
      continue
    (review if row.group(1) in merged else hit).add(row.group(1))
  ranged = {u for u, span in ctx["carried"].items() if overlaps(span, span_of(op))}
  covered = lambda n: any(span[0] <= n <= span[1] for span in carried)  # n is 1-based in the old text
  quoted_old = set()
  for n in range(i1, i2):
    line = prev[n].strip()
    if not line:
      continue
    for u in units:
      if (n + 1 in ctx["spec_global"] or line in ctx["global_of"][u] or not skipped(line)) and line in ctx["lines_of"][u]:
        quoted_old.add(n)
        (review if u in merged else hit).add(u)
  for line in [prev[n].strip() for n in range(i1, i2)] + [new[n].strip() for n in range(j1, j2)]:
    if line.startswith(INTERFACE):  # removed or inserted: the producer and every consumer of the name it declares
      name = interface_name(line)
      interfaced |= {v for v, names in ctx["names_of"].items() if name and name in names}
  uncovered = any(not skipped(prev[n]) and n not in quoted_old and not covered(n + 1)
                  for n in range(i1, i2) if n not in ctx["table_old"])
  for k in range(j2 - j1):  # a new line stands at the old line it replaces; one past their count, or inserted, after the block
    n = i1 + k if k < i2 - i1 else None
    at = n + 1 if n is not None else max(i2, 1)
    if j1 + k in ctx["table_new"]:
      continue
    if not skipped(new[j1 + k]) and (n is None or n not in quoted_old) and not covered(at):
      uncovered = True
  if uncovered:
    hit |= set(units) - merged
    review |= merged
  return hit | ranged | interfaced, review, ranged, interfaced


CLEARING = ("DONE", "DONE_WITH_CONCERNS")  # a builder status that clears a mark on an unchanged head


def is_stopped(store: core.Store, unit: str) -> bool:
  return bool(core.load_foreman(store, unit).get("stopped"))


def latest_handoff(store: core.Store, spec: Path) -> str | None:
  latest = core.load_approval(store, spec)
  return (latest or {}).get("handoff_id")


def commit_time(root: Path, sha: str) -> float | None:
  """The committer time of `sha` in `root`; None when git cannot."""
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
  for entry in naming:
    try:
      started = core.epoch(entry.get("started_at"))
    except (TypeError, ValueError):
      continue
    # read inside the launch's worktree, as `own_commit` reads it (U31); the spec repository only when no worktree exists
    worktree = Path(entry["worktree"]) if entry.get("worktree") else None
    when = commit_time(worktree, head) if worktree and worktree.is_dir() else commit_time(root, head)
    if when is not None and when > started:
      return True
  return any(e.get("status") == "exited 0" and e.get("head") == head and e.get("builder_status") in CLEARING
             for e in naming)


def filed_at(store: core.Store, unit: str, respec: str) -> bool:
  """Whether `unit` was filed and unmerged when R<n> was approved: the approval wrote its comment file then
  (`respec_comment_<unit>_R<n>.md`), and for no other unit, so a unit filed later is still an unfiled one to R<n>."""
  return store.path("file", f"respec_comment_{unit}_{respec}.md").is_file()


def marks(store: core.Store, handoff: str, root: Path | None = None) -> dict:
  """Unit to `replan: R<n>` (unfiled at R<n>'s approval, until `handoff_units.json`'s `corrected` names R<n>) or
  `respec: R<n>` (filed and unmerged then), derived on every read from the applied respecs' `respec/R<n>.json` `touched`,
  their comment files, `corrected`, `state.json`'s saved PR heads and the launch records; never written. Stopped and
  merged units are left out, and a handoff a later approval supersedes carries none; `root` as in `spec_of`."""
  spec = spec_of(store, handoff, root)
  if latest_handoff(store, spec) != handoff:
    return {}
  hs = core.handoff_store(store, handoff)
  units = (load_json(hs.path("units")) or {}).get("units") or {}
  state = (load_json(hs.path("state")) or {}).get("units") or {}
  root = core.git_toplevel(spec if spec.is_absolute() else Path.cwd() / spec)
  out = {}
  for entry in entries_of(store, handoff, spec):
    respec = entry.get("respec") if entry.get("kind") == "respec" else None
    applied = load_json(respec_path(hs, f"{respec}.json")) if respec else None
    for unit in (applied or {}).get("touched") or []:
      record = state.get(unit) or {}
      if unit in out or is_merged(record) or is_stopped(hs, unit):
        continue
      if not filed_at(hs, unit, respec):  # unfiled at the approval: only `corrected` naming R<n> clears it
        if respec not in ((units.get(unit) or {}).get("corrected") or []):
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
      if not filed_at(hs, unit, respec) or not eligible(hs, unit, record):  # an unfiled unit's replan posts nothing
        continue
      if not respec_path(hs, f"{respec}.{unit}.posted").is_file():
        out.append(("post", respec, unit))
      if standing.get(unit) == f"respec: {respec}":
        out.append(("relaunch", respec, unit))
  return out


SKILLS = frozenset(["wave"])  # the skills whose card `respec posted` accepts: the wave posts the comment
OPEN_SKILLS = frozenset(["review-plan", "integrate"])  # the skills whose card `respec open` accepts (U91)
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own


def register(subparsers):
  p = subparsers.add_parser("respec", help="a respec's records (spec section 7.6)")
  action = p.add_subparsers(dest="action", required=True)
  posted = core.add_parser(action, "posted", "record that the wave posted respec R<n>'s comment on a unit's issue")
  posted.add_argument("--respec", required=True, help="R<n>")
  posted.add_argument("--unit", required=True)
  posted.add_argument("--comment", required=True, help="the posted comment's id")
  opened = core.add_parser(action, "open", "the owner opens a respec from a plan or integrate review's fix-design finding")
  opened.add_argument("--review", required=True, help="the plan or integrate review's id")
  opened.add_argument("--finding", required=True, help="its fix-design finding's id")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  return {"posted": record_posted, "open": record_open}[args.action](args)


def review_open(store: core.Store, handoff: str) -> list:
  """The open respecs of `handoff` raised from a review's design finding (`unit: null`, U91): what `file`, `integrate`
  and `next` wait on."""
  return [r for r in open(store, handoff) if r.get("unit") is None]


def record_open(args) -> int:
  """`respec open` (U91): write `respec/R<n>.open.json` (`{id, unit: null, review, finding, at}`) in the handoff's
  directory, `R<n>` the next number no `respec/` file uses. Refused, nothing written: under `SUPEREGM_ROLE` or a
  leavemealone card (`respec open: owner only`); a review never opened; a head review's finding; a review neither plan
  nor integrate; a finding the review does not hold (`respec open: no finding <fid>`); a finding not settled
  `fix-design`. A rerun on the same review and finding prints the R<n> it wrote while that respec is open, and is
  refused once an approval applied it or it was withdrawn."""
  from superegm import review as review_mod  # at call time, as `eligible` imports it
  card = core.require_runcard(args, OPEN_SKILLS)
  if os.environ.get("SUPEREGM_ROLE") or card.get("mode") == "leavemealone":
    raise core.HandoffError("respec open: owner only")
  st = core.store(core.git_toplevel(Path.cwd()))
  found = review_mod.load_review(st, args.review)
  if found is None:
    raise core.HandoffError(f"respec open: review {args.review} not opened")
  if found["kind"] == "head":
    raise core.HandoffError(f"respec open: {args.review} is a head review: its findings open no respec")
  if found["kind"] not in ("plan", "integrate"):
    raise core.HandoffError(f"respec open: {args.review} is a {found['kind']} review, not plan or integrate")
  try:
    disposition = review_mod.locate_finding(st, args.review, args.finding)[3].get("disposition")
  except core.HandoffError:  # `review settle: no finding <fid>`, review's own wording
    raise core.HandoffError(f"respec open: no finding {args.finding}") from None
  if disposition != "fix-design":
    raise core.HandoffError(f"respec open: {args.finding} is {disposition or 'unsettled'}, not fix-design")
  folder = respec_path(st)
  files = sorted(folder.iterdir()) if folder.is_dir() else []
  for path in files:
    held = load_json(path) if OPEN_FILE.match(path.name) else None
    if isinstance(held, dict) and held.get("unit") is None and (held.get("review"), held.get("finding")) == (args.review, args.finding):
      if held.get("id") not in {r["id"] for r in (review_open(st, st.handoff_id) if st.handoff_id else [])}:
        raise core.HandoffError(f"respec open: {held.get('id')} from {args.review} {args.finding} is applied or withdrawn")
      print(f"respec {held['id']} open: {path.name}")
      return 0
  used = [int(m.group(1)) for p in files if (m := re.match(r"R(\d+)\.", p.name))]
  rid = f"R{max(used, default=0) + 1}"
  path = respec_path(st, f"{rid}.open.json")
  core.atomic_write(path, {"id": rid, "unit": None, "review": args.review, "finding": args.finding, "at": core.now_iso()})
  core.journal(st, f"respec {rid} opened from {args.review} {args.finding} under {args.runcard}")
  print(f"respec {rid} open: {path.name}")
  return 0


def record_posted(args) -> int:
  """`respec posted`: write `respec/R<n>.<unit>.posted` (`{respec, unit, comment, at}`) in the handoff's directory;
  refused unless an approval entry of the handoff names R<n> (an `R<n>.json` without one is a crash before the entry)."""
  core.require_runcard(args, SKILLS)
  st = core.store(core.git_toplevel(Path.cwd()))
  if not re.fullmatch(r"R\d+", args.respec):
    raise core.HandoffError(f"respec posted: {args.respec} is not R<n>")
  applied = any(e.get("respec") == args.respec for e in entries_of(st, st.handoff_id, spec_of(st, st.handoff_id)))
  if not applied or not respec_path(st, f"{args.respec}.json").is_file():  # the file alone is the crash window's
    raise core.HandoffError(f"respec posted: respec {args.respec} is not applied")
  if args.unit not in (load_json(respec_path(st, f"{args.respec}.json")) or {}).get("touched", []):
    raise core.HandoffError(f"respec posted: {args.unit} is not touched by {args.respec}")
  path = respec_path(st, f"{args.respec}.{args.unit}.posted")
  core.atomic_write(path, {"respec": args.respec, "unit": args.unit, "comment": args.comment, "at": core.now_iso()})
  core.journal(st, f"{args.unit} respec {args.respec} comment {args.comment} posted")
  print(f"posted: {path.name}")
  return 0
