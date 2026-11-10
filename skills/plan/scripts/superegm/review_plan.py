# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: plan review's dispatch set and the set and proportion inputs (spec section 9.2).

"""superegm review-plan due|set-input|proportion-input: what a plan-review round dispatches, and
the texts the `set` and `proportion` reviewers read (spec section 9.2). Writes nothing."""

import argparse
import contextlib
import io
import json
from pathlib import Path
import re

import superegm as core
from superegm import body, graph, review
from superegm.approve_spec import UNITS_H2

WRITES = frozenset()  # the store kinds this subcommand writes: none
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SKILLS = frozenset({"review-plan"})  # the skills whose card this subcommand accepts
SPEC_LINE_RE = re.compile(r"^Spec: `[^`]+` @ \S+ · `([^`:]+):(\d+)-(\d+) \((.+)\)`$", re.M)  # the body's Design range


def register(subparsers):
  p = subparsers.add_parser("review-plan", help="plan review: the dispatch set and the set and proportion inputs")
  action = p.add_subparsers(dest="action", required=True)
  core.add_parser(action, "due", "one line per unfiled unit: what this round dispatches")
  s = core.add_parser(action, "set-input", "the set reviewer's text: the width: line, the plan header, the spec's Units and every unfiled Interfaces block",
                      runcard=False)
  s.add_argument("--spec", required=True)
  q = core.add_parser(action, "proportion-input", "the proportion reviewer's text for one unit", runcard=False)
  q.add_argument("--unit", required=True)
  q.add_argument("--spec", required=True)
  p.set_defaults(run=run, writes=WRITES)


def run(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  if args.action == "due":
    core.require_runcard(args, SKILLS)
    for row in due_rows(st, args.runcard):
      print(" ".join(row))
    return 0
  spec = Path(args.spec).expanduser().resolve()
  print(set_input(st, spec) if args.action == "set-input" else proportion_input(st, args.unit, spec), end="")
  return 0


def unfiled(st: core.Store) -> list[tuple[str, str]]:
  """(unit, body_sha256) per unit of `handoff_units.json.order` without an issue number in `state.json`."""
  units = json.loads(core.read_text(st.path("units")))
  filed = core.load_state(st.root).get("units") or {}
  return [(u, units["units"][u]["body_sha256"]) for u in units["order"] if not (filed.get(u) or {}).get("number")]


def status_of(review_id: str, runcard: str) -> int:
  """`review status` run in-process through U04's `register`/`run`: the cap and stall predicates live there alone."""
  parser = argparse.ArgumentParser()
  review.register(parser.add_subparsers(dest="command"))
  args = parser.parse_args(["review", "status", "--review", review_id, "--runcard", runcard])
  with contextlib.redirect_stdout(io.StringIO()):
    return args.run(args)


def due_rows(st: core.Store, runcard: str) -> list[tuple[str, str, str, str, str]]:
  """One row per unfiled unit: `(unit, due|converged|stalled|cap|fix-design, review id or -, next round or -,
  body_sha256)`. `converged` needs the converged round's bytes to be the unit's current bytes and no round
  file above it; any other exit 0 or 3 is `due` at the highest round file plus one."""
  rows = []
  for uid, sha in unfiled(st):
    latest, _ = review.latest_cycle(st, "plan", uid)
    if latest is None:
      rows.append((uid, "due", "-", "1", sha))
      continue
    rid = review.review_id(st, "plan", uid, latest["cycle"])
    code = status_of(rid, runcard)
    last = max(review.round_numbers(st, rid), default=0)
    word = {4: "fix-design", 5: "stalled", 2: "cap"}.get(code)
    if code == 0:
      converged = latest["converged_round"] or last
      rnd = review.load_round(st, rid, converged)
      if last <= converged and rnd and rnd["artifact_sha256"] == sha:
        word = "converged"
    rows.append((uid, word, rid, "-", sha) if word else (uid, "due", rid, str(last + 1), sha))
  return rows


def interfaces_and_scope(text: str) -> str:
  """The `## Interfaces` lines and the `Scope:` line of a rendered body (section 9.1's fixed layout)."""
  found = body.sections(text)
  lines = [l for l in found.get("Interfaces", []) if l.strip()]
  lines += [l for l in found.get("Scope, order and risk", []) if l.startswith("Scope: ")]
  return "\n".join(lines) + "\n"


def set_input(st: core.Store, spec_path: Path) -> str:
  """`# Plan review: the set`, the `width:` line over `handoff_units.json`, `## Plan header` with the plan's
  `Waves:` line(s) (`none` without one), the spec from its last `## … Units` H2 to the end, then per unfiled unit
  `## <id>` and its Interfaces block and Scope line: what every sibling reviewer also receives."""
  lines = core.read_text(spec_path).splitlines()
  start = max((i for i, line in enumerate(lines) if UNITS_H2.match(line)), default=0)
  width = graph.width_line(json.loads(core.read_text(st.path("units"))))
  plan = st.path("plan")
  waves = [l for l in core.read_text(plan).splitlines() if l.startswith("Waves:")] if plan.is_file() else []
  parts = ["# Plan review: the set", "", width, "", "## Plan header", "", *(waves or ["none"]), "", *lines[start:], ""]
  for uid, _ in unfiled(st):
    parts += [f"## {uid}", "", interfaces_and_scope(core.unit_file_body(st.path("unit", uid)))]
  return "\n".join(parts)


def proportion_input(st: core.Store, uid: str, spec_path: Path) -> str:
  """The unit's rendered body, its `plan/scan/<unit>.json` and the spec lines of the body's Design range,
  each under a `# ` heading naming its source."""
  text = core.unit_file_body(st.path("unit", uid))
  scan_path = st.path("unit", uid).parent / "plan" / "scan" / f"{uid}.json"
  if not scan_path.is_file():
    raise core.HandoffError(f"review-plan: no plan/scan/{uid}.json: run scan first")
  match = SPEC_LINE_RE.search(text)
  if not match:
    raise core.HandoffError(f"review-plan: {uid}: no `Spec:` line with a Design range in the body")
  start, end = int(match.group(2)), int(match.group(3))
  spec_lines = core.read_text(spec_path).splitlines()
  return (f"# {uid}: the rendered body\n\n{text}\n\n# plan/scan/{uid}.json\n\n{core.read_text(scan_path)}\n\n"
          f"# {match.group(1)}:{start}-{end} ({match.group(4)})\n\n" + "\n".join(spec_lines[start - 1:end]) + "\n")
