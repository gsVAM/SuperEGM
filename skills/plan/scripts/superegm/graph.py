# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the section 9.1 unit schema and issue body; the handoff id comes from the approval record; the plan is copied into the store; the optional `Issue` field checked against the spec's `## Units` section (U13); every escalated pair needs a `## Units` row or a blocking decision (U16); `filed_elsewhere[]`, an older handoff frozen, one store of many handoffs (U20).

"""superegm graph: parse the plan under its approval; write the store's plan copy,
units, unit files and bodies."""

import json
import re
from pathlib import Path

import superegm as core
from superegm import review
from superegm.approve_spec import units_section

WRITES = frozenset(['bodies', 'plan', 'state', 'unit', 'units'])  # the store kinds this subcommand writes
SKILLS = frozenset(['plan', 'review-plan'])  # the skills whose card this subcommand accepts (D1 (a): a re-render between review-plan rounds)

DECIDE_RE = re.compile(r"^- (D\d+) (.+?) options: (.+?); owner: (.+?); default: \((\w)\); blocking: (yes|no)"
                       r"(?:; answer: \((\w)\))?$")
GLOBAL_RE = re.compile(r"^## Global constraints[ \t]*\n(.*?)(?=^## |\Z)", re.S | re.M)
INTERFACE_RE = re.compile(r"^- (?:Consumes: .+ \(U\d{2,}\)|Produces: .+)$")
FIXED_DOD_1 = "The test for each Step was committed before its implementation (checked by superegm tdd-order)"
DOD_ITEM_RE = re.compile(r"^(?:Run `[^`]+` — .+|Exists `[^`]+`|CI green on the head)$")
OPTION_RE = re.compile(r"^\((\w)\) .+$")
MARKER_LINE = "<!-- superegm:handoff={{handoff_id}} unit={{unit_id}} spec={{spec_sha256}} -->"
BODY_TEMPLATE = MARKER_LINE + """
# {{unit_id}} — {{title}}
Spec: `{{spec}}` @ {{sha7}} · `{{design}}`

## Objective
{{objective}}

## Interfaces
{{interfaces}}

## Definition of done
{{dod}}

## Global constraints
{{global_constraints}}

## Review focus (this unit)
{{review_focus}}

## Steps
{{steps}}

## Decide before build
{{decisions}}

## Scope, order and risk
Scope: {{scope}} · Blocked by: {{blocked_by}} · Shared files: {{shared}} · Risk: {{risk}} · Size: {{size}}
Branch: `{{branch}}` · Part of #{{tracking}}
"""
PLACEHOLDERS = sorted(set(re.findall(r"\{\{\w+\}\}", BODY_TEMPLATE)))


def register(subparsers):
  p = core.add_parser(subparsers, "graph", "parse the plan under its approval; write the store's plan copy, units and bodies")
  p.set_defaults(run=run, writes=WRITES)


def check_template(template: str) -> None:
  """A body template starts with the marker line and uses every placeholder."""
  if (template.splitlines() or [""])[0] != MARKER_LINE:
    raise core.HandoffError(f"issue template must start with the marker line `{MARKER_LINE}`")
  missing = [name for name in PLACEHOLDERS if name not in template]
  if missing:
    raise core.HandoffError(f"issue template lacks {', '.join(missing)}")


class Unit(core.Unit):

  def __init__(self, uid, title, line):
    super().__init__(uid, title, line)
    self.interfaces = []     # the raw `- Consumes: …` / `- Produces: …` lines
    self.review_focus = []   # the raw `- U<nn>: …` lines
    self.steps = ""          # the Steps text, verbatim
    self.decide = []         # the raw `Decide before build` lines

  def to_json(self, wave, preds):
    return {**super().to_json(wave, preds), "interfaces": self.interfaces, "review_focus": self.review_focus}


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
    unknown = set(fields) - set(core.FIELDS) - set(core.OPTIONAL_FIELDS)
    if unknown:
      self._fail(unit.line - 1, f"{uid}: unknown fields {sorted(unknown)}")
    self._parse_fields(unit, fields)
    i = self._heading(lines, i, uid, "Interfaces")
    while i < len(lines) and lines[i].startswith("- "):
      if not INTERFACE_RE.match(lines[i].rstrip()):
        self._fail(i, f"{uid}: interfaces line must read `- Consumes: <name> (U<nn>)` or `- Produces: <name>`")
      unit.interfaces.append(lines[i].rstrip())
      i += 1
    i = self._heading(lines, i, uid, "Definition of done")
    while i < len(lines) and core.DOD_RE.match(lines[i]):
      number, item = int(core.DOD_RE.match(lines[i]).group(1)), core.DOD_RE.match(lines[i]).group(2).strip()
      if number != len(unit.dod) + 1:
        self._fail(i, f"{uid}: definition-of-done items must be numbered 1, 2, …")
      if number == 1 and item != FIXED_DOD_1:
        self._fail(i, f"{uid}: definition-of-done item 1 must read `{FIXED_DOD_1}`")
      if number > 1 and not DOD_ITEM_RE.match(item):
        self._fail(i, f"{uid}: definition-of-done item {number} is not `Run `, `Exists ` or `CI green on the head`")
      unit.dod.append(item)
      i += 1
    if len(unit.dod) < 2:
      self._fail(i, f"{uid}: definition of done needs item 1 and a `Run`, `Exists` or CI item")
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
        did, options, default, answer = decide.group(1), decide.group(3).split("; "), decide.group(5), decide.group(7)
        ids = [OPTION_RE.match(o).group(1) if OPTION_RE.match(o) else
               self._fail(i, f"{uid}: decide-before-build item {did} option `{o}` must read `(a) <option>`")
               for o in options]
        if len(options) < 2:
          self._fail(i, f"{uid}: decide-before-build item {did} needs two or more options")
        if default not in ids:
          self._fail(i, f"{uid}: decide-before-build item {did} default ({default}) is not one of its options")
        if answer and answer not in ids:
          self._fail(i, f"{uid}: decide-before-build item {did} answer ({answer}) is not one of its options")
        unit.decisions.append({"id": did, "question": decide.group(2), "options": options, "owner": decide.group(4),
                               "default": f"({decide.group(5)})", "blocking": decide.group(6) == "yes",
                               "answer": f"({decide.group(7)})" if decide.group(7) else None, "line": i + 1})
      i += 1
    self._check_decision_ids(unit)
    self.units[uid] = unit
    self.order.append(uid)
    return i


def filed_in(store: core.Store, spec: Path) -> dict:
  """`{unit: handoff id}` of the units the spec's other handoffs (every id its approval history names but
  the store's own) file in their `state.json`, each read in its own place (a legacy handoff's at the root)."""
  filed = {}
  for hid in dict.fromkeys(e.get("handoff_id") for e in core.load_approvals(store, spec)):
    path = core.handoff_store(store, hid).path("state") if hid and hid != store.handoff_id else None
    if path and path.is_file():
      for uid, record in (json.loads(core.read_text(path)).get("units") or {}).items():
        if (record or {}).get("number"):
          filed.setdefault(uid, hid)
  return filed


def filed_elsewhere(store: core.Store, spec: Path) -> list:
  """The units filed in another handoff of the spec (the plan's `Landed:` rows, `handoff_units.json`'s
  `filed_elsewhere[]`)."""
  return sorted(filed_in(store, spec))


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
    # The handoff's own approval: the last entry carrying the resolved handoff's id, else (no handoff resolved, or
    # a legacy store's) the history's last; an older handoff's spec may stand at a later link of the chain (spec
    # section 7). A 1.2 handoff no entry of this spec names is another spec's: refused, never rebound.
    entries = core.load_approvals(store, self.design_path)
    own = [i for i, e in enumerate(entries) if store.handoff_id and e.get("handoff_id") == store.handoff_id]
    if store.handoff_id and not store.legacy and entries and not own:
      raise core.HandoffError(f"graph: {store.handoff_id} is not a handoff of {self.design_path.name}")
    own = own or ([len(entries) - 1] if entries else [])
    approval = entries[own[-1]] if own else None
    later = {e["sha256"] for e in entries[own[-1] + 1:]} if own else set()
    if not approval or approval.get("voided_by") or (approval["sha256"] != self.design_sha and self.design_sha not in later):
      raise core.HandoffError(f"graph: no approval matches {self.design_path.name} at its current sha256 "
                              f"{self.design_sha[:12]}: run /superegm:review-spec (approve-spec) first")
    self.handoff_id, self.spec_sha = approval["handoff_id"], approval["sha256"]
    self.design_commit = approval.get("commit") or ""
    spec_text = core.read_text(self.design_path)
    named = units_section(spec_text)
    for uid, unit in self.plan.units.items():
      if unit.issue is not None and not re.search(rf"#{unit.issue}(?!\d)", named):
        raise core.HandoffError(f"graph: {uid}: Issue #{unit.issue} is not named in the spec's `## Units` section")
    self.escalated = approval.get("escalated") or []  # the pairs `scan` holds to the judges in leavemealone-mode
    for pair in self.escalated:
      if pair in named:
        continue
      rid, fid = pair.split(":", 1)
      claims = [f["claim"] for n in review.round_numbers(store, rid)
                for f in review.findings_of(review.load_round(store, rid, n)) if f["id"] == fid]
      if not claims:
        raise core.HandoffError(f"graph: {pair}: no such finding in the store")
      if not any(d["blocking"] and pair in d["question"] and claims[0] in d["question"]
                 for unit in self.plan.units.values() for d in unit.decisions):
        raise core.HandoffError(f"graph: {pair} needs a `## Units` row or a `blocking: yes` D<n> line naming it "
                                "with the finding's claim verbatim")
    self.design_title = next((l[2:].strip() for l in spec_text.splitlines() if l.startswith("# ")), self.design_path.stem)
    self.config = core.load_config(self.repo_root)
    self.template = self.config["_template"] if self.config["issue_template"] else BODY_TEMPLATE
    check_template(self.template)
    self.graph = core.Graph(self.plan)
    self.state = state
    store.handoff_id = self.handoff_id
    elsewhere = filed_in(store, self.design_path)
    for uid in self.plan.units:
      if uid in elsewhere:
        raise core.HandoffError(f"graph: {uid} is filed in {elsewhere[uid]}: no section for it")
    self.filed_elsewhere = sorted(elsewhere)
    self.check_labels()
    self.check_frozen()

  def filed(self, uid: str):
    """The unit's issue number once filed, else None."""
    return ((self.state.get("units") or {}).get(uid) or {}).get("number")

  def check_frozen(self) -> None:
    """A filed unit's section in the plan file equals the stored handoff_plan.md's (spec section 7)."""
    stored_path = self.store.path("plan")
    stored = Plan(stored_path) if stored_path.is_file() else None
    for uid, record in (self.state.get("units") or {}).items():
      if not record.get("number"):
        continue
      if stored is None or uid not in stored.units or uid not in self.plan.units \
          or core.unit_section_text(self.plan, uid) != core.unit_section_text(stored, uid):
        raise core.HandoffError(f"graph: {uid} is filed (#{record['number']}) and its section differs "
                                "from the stored handoff_plan.md")

  def render_unit(self, uid: str) -> str:
    if self.filed(uid) is not None:
      return core.unit_file_body(self.unit_file(uid)) + "\n"
    unit = self.plan.units[uid]
    shared = "; ".join(f"`{path}`: " + ", ".join(f"after {self.ref(o)}" if k == "after" else f"before {self.forward_ref(o)}"
                                                 for k, o in orders) for path, orders in unit.shared)
    values = {
        "handoff_id": self.handoff_id, "unit_id": uid, "title": unit.title, "spec_sha256": self.spec_sha,
        "sha7": self.spec_sha[:7], "spec": self.design_path.relative_to(self.repo_root).as_posix(),
        "design": f"{unit.design_range[0]}:{unit.design_range[1]}-{unit.design_range[2]} ({unit.design_range[3]})",
        "objective": unit.objective, "interfaces": "\n".join(unit.interfaces) or "- none",
        "dod": "\n".join(f"{n}. {item}" for n, item in enumerate(unit.dod, 1)),
        "global_constraints": "\n".join(self.plan.global_constraints),
        "review_focus": "\n".join(unit.review_focus), "steps": unit.steps, "decisions": "\n".join(unit.decide),
        "scope": ", ".join(f"`{p}` ({a})" for p, a in unit.scope),
        "blocked_by": ", ".join(self.ref(b) for b in unit.blockers) or "none", "shared": shared or "none",
        "risk": f"{unit.risk[0]}: {unit.risk[1]}", "size": unit.size, "branch": self.branch(uid), "tracking": "<tracking>",
    }
    return core.substitute(self.template, values)

  def bodies_text(self):
    parts = [f"## {item[1]}\n\nTitle: {item[2]}\nLabels: {', '.join(item[3])}\n\n````markdown\n{item[4]}````\n"
             for item in self.writes() if item[0] == "issue"]
    return "# Rendered issue bodies (creation order)\n\n" + "\n".join(parts)

  def unit_file_text(self, uid):
    return (f"{core.unit_section_text(self.plan, uid)}\n\n## Issue body as posted\n\n"
            f"````markdown\n{self.render_unit(uid)}````\n")

  def write_graph_files(self) -> None:
    g = self.graph
    hashes = {uid: core.sha256_text(self.render_unit(uid)) for uid in g.order}
    core.atomic_write(self.store.path("plan"), self.plan.text)
    units = {u: {**self.plan.units[u].to_json(g.wave[u], g.preds[u]), "body_sha256": hashes[u]} for u in g.order}
    data = {"handoff_id": self.handoff_id, "repo": self.config["repo"],
            "design": {"path": str(self.design_path), "sha256": self.design_sha,
                       "commit": self.design_commit, "title": self.design_title},
            "order": g.order, "waves": {str(w): us for w, us in sorted(g.waves.items())},
            "critical_path": g.critical_path,
            "edges": [{"from": a, "to": b, "kind": k} for a, b, k in g.edges],
            "units": units, "filed_elsewhere": self.filed_elsewhere}
    core.atomic_write(self.store.path("units"), data)
    for uid in g.order:
      if self.filed(uid) is None:
        core.atomic_write(self.unit_file(uid), self.unit_file_text(uid))
    core.atomic_write(self.store.path("bodies"), self.bodies_text())
    self.state.update({"handoff_id": self.handoff_id, "repo": self.config["repo"],
                       "remote": self.config["remote"], "repo_root": str(self.repo_root),
                       "plan": str(self.plan_path),
                       "design": {"path": str(self.design_path), "sha256": self.design_sha,
                                  "commit": self.design_commit}})
    records = self.state.setdefault("units", {})
    for uid in g.order:
      records.setdefault(uid, {})["body_sha256"] = hashes[uid]
    core.save_state(self.artifact_dir, self.state)
    core.journal(self.store, f"graph {self.handoff_id}: {len(g.order)} units, {len(g.waves)} waves")


def load(store: core.Store, plan) -> Handoff:
  """The handoff of `--plan`, or of the plan `state.json` recorded."""
  if plan is None:
    plan = core.load_state(store.root).get("plan")
    if not plan:
      raise core.HandoffError("graph: no plan recorded: pass --plan on the first graph")
  plan = Path(plan).expanduser().resolve()
  if not plan.is_file():
    raise core.HandoffError(f"graph: plan {plan} does not exist")
  return Handoff(plan, store, core.load_state(store.root))


def run(args):
  st = core.store(core.git_toplevel(Path.cwd()))
  try:  # an older handoff is frozen (spec section 7)
    core.require_latest_handoff(st)
  except core.HandoffError as error:
    raise core.HandoffError(f"graph: {error}") from None
  handoff = load(st, args.plan)
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
