# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the section 9.1 unit schema and issue body; the handoff id comes from the approval record; the plan is copied into the store.

"""superegm graph: parse the plan under its approval; write the store's plan copy,
units, unit files and bodies."""

import re
from pathlib import Path

import superegm as core

WRITES = frozenset(['bodies', 'plan', 'state', 'unit', 'units'])  # the store kinds this subcommand writes
SKILLS = frozenset(['plan'])  # the skills whose card this subcommand accepts

DECIDE_RE = re.compile(r"^- (D\d+) (.+?) options: (.+?); owner: (.+?); default: \((\w)\); blocking: (yes|no)"
                       r"(?:; answer: \((\w)\))?$")
GLOBAL_RE = re.compile(r"^## Global constraints[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)


def register(subparsers):
  p = core.add_parser(subparsers, "graph", "parse the plan under its approval; write the store's plan copy, units and bodies")
  p.set_defaults(run=run, writes=WRITES)


class Unit(core.Unit):

  def __init__(self, uid, title, line):
    super().__init__(uid, title, line)
    self.interfaces = []     # the raw `- Consumes: …` / `- Produces: …` lines
    self.review_focus = []   # the raw `- U<nn>: …` lines
    self.steps = ""          # the Steps text, verbatim
    self.decide = []         # the raw `Decide before build` lines


class Plan(core.Plan):
  """EGM's plan with the section 9.1 blocks after each unit's table and the
  `## Global constraints` H2."""

  def __init__(self, path: Path):
    super().__init__(path)
    match = GLOBAL_RE.search(self.text)
    if not match:
      raise core.HandoffError(f"{self.path}: no `## Global constraints` section")
    self.global_constraints = [l.rstrip() for l in match.group(1).splitlines() if l.strip()]

  def _heading(self, lines, i, uid, name):
    while i < len(lines) and not lines[i].strip():
      i += 1
    if i >= len(lines) or lines[i].strip() != name:
      self._fail(min(i, len(lines) - 1), f"{uid}: expected `{name}`")
    return i + 1

  def _parse_unit(self, lines, i):
    match = core.UNIT_RE.match(lines[i])
    uid, title = match.group(1), match.group(2)
    if uid in self.units:
      self._fail(i, f"duplicate unit {uid}")
    unit = Unit(uid, title, i + 1)
    i += 1
    if i + 1 >= len(lines) or lines[i].strip() != "| Field | Value |" or lines[i + 1].strip() != "| --- | --- |":
      self._fail(i, f"{uid}: expected the `| Field | Value |` table")
    i += 2
    fields = {}
    while i < len(lines) and lines[i].startswith("|"):
      row = re.match(r"^\| ([^|]+?) \| (.*?) \|$", lines[i])
      if not row:
        self._fail(i, f"{uid}: malformed table row")
      fields[row.group(1)] = (row.group(2).strip(), i)
      i += 1
    for name in core.FIELDS:
      if name not in fields:
        self._fail(unit.line - 1, f"{uid}: missing field `{name}`")
    unknown = set(fields) - set(core.FIELDS)
    if unknown:
      self._fail(unit.line - 1, f"{uid}: unknown fields {sorted(unknown)}")
    self._parse_fields(unit, fields)
    i = self._heading(lines, i, uid, "Interfaces")
    while i < len(lines) and lines[i].startswith("- "):
      unit.interfaces.append(lines[i].rstrip())
      i += 1
    i = self._heading(lines, i, uid, "Definition of done")
    while i < len(lines) and core.DOD_RE.match(lines[i]):
      unit.dod.append(core.DOD_RE.match(lines[i]).group(2).strip())
      i += 1
    if not unit.dod:
      self._fail(i, f"{uid}: empty definition of done")
    i = self._heading(lines, i, uid, "Review focus (this unit)")
    while i < len(lines) and lines[i].startswith("- "):
      unit.review_focus.append(lines[i].rstrip())
      i += 1
    i = self._heading(lines, i, uid, "Steps")
    start = i
    while i < len(lines) and lines[i] != "Decide before build" and not core.UNIT_RE.match(lines[i]) \
        and not lines[i].startswith("## "):
      i += 1
    unit.steps = "\n".join(lines[start:i]).strip("\n")
    if not unit.steps:
      self._fail(start, f"{uid}: empty Steps")
    i = self._heading(lines, i, uid, "Decide before build")
    while i < len(lines) and lines[i].startswith("- "):
      unit.decide.append(lines[i].rstrip())
      if lines[i].strip() != "- none":
        decide = DECIDE_RE.match(lines[i])
        if not decide:
          self._fail(i, f"{uid}: decide-before-build item must read `- D<n> <question> options: (a) <option>; "
                        "(b) <option>[; …]; owner: <owner>; default: (a); blocking: yes|no`")
        unit.decisions.append({"id": decide.group(1), "question": decide.group(2),
                               "options": decide.group(3).split("; "), "owner": decide.group(4),
                               "default": f"({decide.group(5)})", "blocking": decide.group(6) == "yes",
                               "answer": f"({decide.group(7)})" if decide.group(7) else None, "line": i + 1})
      i += 1
    self._check_decision_ids(unit)
    self.units[uid] = unit
    self.order.append(uid)
    return i


class Handoff(core.Handoff):
  """EGM's handoff under an approval record: the handoff id and the spec sha
  are the approval's, the plan file is never written."""

  def __init__(self, plan_path: Path, store: core.Store, state: dict) -> None:
    self.plan_path = Path(plan_path).resolve()
    self.store, self.artifact_dir = store, store.root
    self.plan = Plan(self.plan_path)
    design = Path(self.plan.design).expanduser()
    if not design.is_absolute():
      design = self.plan_path.parent / design
    if not design.is_file():
      raise core.HandoffError(f"graph: design file {design} does not exist")
    self.design_path = design.resolve()
    self.design_sha = core.sha256_file(self.design_path)
    self.repo_root = core.git_toplevel(self.design_path)
    approval = core.load_approval(store, self.design_path)
    if not approval or approval.get("voided_by") or approval["sha256"] != self.design_sha:
      raise core.HandoffError(f"graph: no approval matches {self.design_path.name} at its current sha256 "
                              f"{self.design_sha[:12]}: run /superegm:review-spec (approve-spec) first")
    self.handoff_id, self.spec_sha = approval["handoff_id"], approval["sha256"]
    self.design_commit = approval.get("commit") or ""
    self.design_title = next((l[2:].strip() for l in core.read_text(self.design_path).splitlines()
                              if l.startswith("# ")), self.design_path.stem)
    self.config = core.load_config(self.repo_root)
    self.graph = core.Graph(self.plan)
    self.state = state
    store.handoff_id = self.handoff_id
    self.check_labels()

  def bodies_text(self):
    parts = [f"## {item[1]}\n\nTitle: {item[2]}\nLabels: {', '.join(item[3])}\n\n````markdown\n{item[4]}````\n"
             for item in self.writes() if item[0] == "issue"]
    return "# Rendered issue bodies (creation order)\n\n" + "\n".join(parts)

  def unit_file_text(self, uid):
    return (f"{core.unit_section_text(self.plan, uid)}\n\n## Issue body as posted\n\n"
            f"````markdown\n{self.render_unit(uid)}````\n")

  def write_graph_files(self) -> None:
    g = self.graph
    core.atomic_write(self.store.path("plan"), self.plan.text)
    units = {u: self.plan.units[u].to_json(g.wave[u], g.preds[u]) for u in g.order}
    data = {"handoff_id": self.handoff_id, "repo": self.config["repo"],
            "design": {"path": str(self.design_path), "sha256": self.design_sha,
                       "commit": self.design_commit, "title": self.design_title},
            "order": g.order, "waves": {str(w): us for w, us in sorted(g.waves.items())},
            "critical_path": g.critical_path,
            "edges": [{"from": a, "to": b, "kind": k} for a, b, k in g.edges],
            "units": units}
    core.atomic_write(self.store.path("units"), data)
    for uid in g.order:
      core.atomic_write(self.unit_file(uid), self.unit_file_text(uid))
    core.atomic_write(self.store.path("bodies"), self.bodies_text())
    self.state.update({"handoff_id": self.handoff_id, "repo": self.config["repo"],
                       "remote": self.config["remote"], "repo_root": str(self.repo_root),
                       "plan": str(self.plan_path),
                       "design": {"path": str(self.design_path), "sha256": self.design_sha,
                                  "commit": self.design_commit}})
    core.save_state(self.artifact_dir, self.state)


def run(args):
  plan, st = core.locate(args)
  handoff = Handoff(plan, st, core.load_state(st.root))
  # The card is on the spec the plan names: `require_runcard` reads it from `design`.
  args.design = str(handoff.design_path)
  core.require_runcard(args, SKILLS)
  handoff.write_graph_files()
  g = handoff.graph
  print(f"handoff {handoff.handoff_id} on {handoff.config['repo']}: {len(g.order)} units, {len(g.waves)} waves")
  for wave in sorted(g.waves):
    print(f"wave {wave}: {', '.join(g.waves[wave])}")
  print("critical path: " + " -> ".join(g.critical_path))
  print(f"wrote handoff_plan.md, handoff_units.json, {len(g.order)} unit_*.md, handoff_bodies.md in {handoff.artifact_dir}")
  return 0
