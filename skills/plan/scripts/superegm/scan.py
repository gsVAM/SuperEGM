# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the section 9.1 body rules, one named rule per line, over the graph module's bodies; amendment 9's warning values (U29).

"""superegm scan: the body rules of spec section 9.1, one `<rule>: <unit>: <line>` per problem."""

import re
from pathlib import Path

import superegm as core
from superegm import graph

WRITES = frozenset(['file'])  # the store kinds this subcommand writes: the derived `plan/scan/<unit>.json`
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
scan_text, BODY_LIMIT = core.scan_text, core.BODY_LIMIT  # the one raw-text scan, the package's
WARN = {"bytes": (24_576, "24,576"), "steps": (10, "10"), "fenced_share": (0.40, "0.40")}  # limit, as printed
FENCE_LINE = re.compile(r"^\s*`{3,}")
NAME_RE = re.compile(r"^[A-Za-z_][\w.]*")
CHECKBOX_RE = re.compile(r"^\s*- \[[ xX]\]")
FOCUS_RE = re.compile(r"^- (U\d{2,}): .+; pinned by `([^`]+)`$")
PLACEHOLDERS = ("TBD", "handle edge cases", "add appropriate validation", "write tests for the above")


def register(subparsers):
  p = core.add_parser(subparsers, "scan", "the section 9.1 body rules, one named rule per line", runcard=False)
  p.add_argument("--comment", help="scan this comment file instead of the bodies")
  p.set_defaults(run=run, writes=WRITES)


def names_of(item: str) -> list:
  """What an interface item is matched on: a store line's key paths, a
  subcommand's words, else the leading identifier."""
  if " key " in item:
    keys = item.split(" key ", 1)[1].split(" (", 1)[0]
    return [k.strip() for k in keys.split(", ")]
  if item.startswith("superegm "):
    words = ["superegm"]
    for word in item.split()[1:]:
      if word[0] in "-<[→;":
        break
      words.append(word)
    return [" ".join(words)]
  match = NAME_RE.match(item)
  return [match.group(0)] if match else []


def produced(handoff) -> dict:
  """Unit id -> the names its Produces lines define."""
  return {unit.id: {n for line in unit.interfaces if line.startswith("- Produces: ") for n in names_of(line[12:])}
          for unit in handoff.plan.units.values()}


def blockers_of(handoff, uid: str) -> set:
  """The unit's direct and transitive `Blocked by`."""
  seen, todo = set(), list(handoff.plan.units[uid].blockers)
  while todo:
    other = todo.pop()
    if other not in seen and other in handoff.plan.units:
      seen.add(other)
      todo += handoff.plan.units[other].blockers
  return seen


def rule_checkbox(uid, body, handoff):
  return [f"checkbox: {uid}: {line.strip()}" for line in body.splitlines() if CHECKBOX_RE.match(line)]


def rule_placeholder(uid, body, handoff):
  return [f"placeholder: {uid}: {line.strip()}" for line in body.splitlines() if any(p in line for p in PLACEHOLDERS)]


def rule_consumes_undefined(uid, body, handoff):
  every = set().union(*produced(handoff).values())
  return [f"consumes-undefined: {uid}: {name} ({unit})" for name, unit in core.body.consumes(body)
          if any(n not in every for n in names_of(name))]


def rule_consumes_producer(uid, body, handoff):
  made, chain = produced(handoff), blockers_of(handoff, uid)
  every = set().union(*made.values())
  return [f"consumes-producer: {uid}: {name} ({unit})" for name, unit in core.body.consumes(body)
          if all(n in every for n in names_of(name))
          and (unit not in chain or any(n not in made.get(unit, ()) for n in names_of(name)))]


def rule_global_constraints(uid, body, handoff):
  lines = core.body.sections(body).get("Global constraints", [])
  return [] if any(l.strip() for l in lines) else [f"global-constraints: {uid}: no global constraints in the body"]


def rule_review_focus(uid, body, handoff):
  lines = core.body.sections(body).get("Review focus (this unit)", [])
  return [] if any(l.startswith("- ") for l in lines) else [f"review-focus: {uid}: no review-focus line in the body"]


def rule_review_focus_test(uid, body, handoff):
  problems = []
  for line in core.body.sections(body).get("Review focus (this unit)", []):
    match = FOCUS_RE.match(line.rstrip())
    if not line.strip():
      continue
    owner = handoff.plan.units.get(match.group(1)) if match else None
    commands = core.body.run_commands(handoff.render_unit(owner.id)) if owner else []
    if not match or not any(match.group(2).split("[", 1)[0] in c for c in commands):
      problems.append(f"review-focus-test: {uid}: {line.strip()}")
  return problems


def rule_step_group(uid, body, handoff):
  paths = core.body.step_paths(body)
  problems = [f"step-group: {uid}: Step {n} lacks a test path or an implementation path" for n, t, i in paths if not t or not i]
  runs = sum(1 for _, kind, _ in core.body.dod_items(body) if kind == "run")
  if len(core.body.run_commands(body)) < len(paths) + runs:
    problems.append(f"step-group: {uid}: a Step has no command")
  return problems


def rule_step_scope(uid, body, handoff):
  scope = [p for p, _ in handoff.plan.units[uid].scope]
  under = lambda path: any(path == s or path.startswith(s.rstrip("/") + "/") for s in scope)
  return [f"step-scope: {uid}: Step {n}: `{p}` is not under a Scope path"
          for n, t, i in core.body.step_paths(body) for p in (t, i) if p and not under(p)]


def rule_decision_blocking(uid, body, handoff):
  answered = handoff.state.get("decisions") or {}
  problems = [f"decision-blocking: {uid}: {d['id']} {d['question']}" for d in handoff.plan.units[uid].decisions
              if d["blocking"] and not d.get("answer") and f"{uid}/{d['id']}" not in answered]
  if handoff.config["mode"] == "leavemealone":  # an escalated pair's decision is the judges' (section 13.2)
    for d in handoff.plan.units[uid].decisions:
      by = (answered.get(f"{uid}/{d['id']}") or {}).get("by")
      if by and not by.startswith("judges:") and any(pair in d["question"] for pair in handoff.escalated):
        problems.append(f"decision-ruler: {uid}: {d['id']} answered by {by} in leavemealone-mode: decide --judges <panel>")
  return problems


# The code-aware body rules, one problem `<rule>: <unit>: <line or reason>` each;
# `body-size`, `banned-term`, `mention`, `merge-marker` and `dod-missing` are `scan_text`'s raw rules.
RULES = {"checkbox": rule_checkbox, "placeholder": rule_placeholder,
         "consumes-undefined": rule_consumes_undefined, "consumes-producer": rule_consumes_producer,
         "global-constraints": rule_global_constraints, "review-focus": rule_review_focus,
         "review-focus-test": rule_review_focus_test, "step-group": rule_step_group,
         "step-scope": rule_step_scope, "decision-blocking": rule_decision_blocking}


def scan_body(uid: str, body: str, handoff: graph.Handoff) -> list:
  return [problem for rule in RULES.values() for problem in rule(uid, body, handoff)]


def numbers(uid: str, body: str, handoff: graph.Handoff) -> dict:
  """The proportion reviewer's evidence: bytes, the share inside fences (fence
  lines included), Steps, the Design range's bytes in the spec, and the ratio."""
  size, fenced, inside = len(body.encode("utf-8")), 0, False
  for line in body.splitlines(keepends=True):
    fence = bool(FENCE_LINE.match(line))
    inside = inside != fence
    fenced += len(line.encode("utf-8")) if inside or fence else 0
  _, start, end, _ = handoff.plan.units[uid].design_range
  spec_lines = core.read_text(handoff.design_path).splitlines(keepends=True)
  spec_bytes = len("".join(spec_lines[start - 1:end]).encode("utf-8"))
  found = {"bytes": size, "fenced_share": round(fenced / size, 2) if size else 0.0,
           "steps": len(core.body.step_paths(body)), "spec_range_bytes": spec_bytes,
           "ratio": round(size / spec_bytes, 2) if spec_bytes else 0.0}
  found["warnings"] = [f"{key} {found[key]:,} > {text}" for key, (limit, text) in WARN.items() if found[key] > limit]
  return found


def scan_handoff(handoff: graph.Handoff) -> list:
  problems = []
  for item in handoff.writes():
    if item[0] == "issue":
      dod = handoff.plan.units[item[1]].dod if item[1] != "tracking" else []
      problems += scan_text(item[4], handoff.config, "body", dod, label=item[1])
      problems += scan_text(item[2], handoff.config, "body", label=f"{item[1]} title")
      if item[1] != "tracking":
        problems += scan_body(item[1], item[4], handoff)
  return problems


def run(args):
  handoff = graph.load(core.store(core.git_toplevel(Path.cwd())), args.plan)
  if args.comment:
    path = Path(args.comment).expanduser().resolve()
    problems = scan_text(core.read_text(path), handoff.config, "comment", label=path.name)
  else:
    rows = []
    for uid in handoff.graph.order:
      found = numbers(uid, handoff.render_unit(uid), handoff)
      core.atomic_write(handoff.unit_file(uid).parent / "plan" / "scan" / f"{uid}.json", found)
      rows.append([uid] + [f"{found[k]:,}" for k in ("bytes", "fenced_share", "steps", "spec_range_bytes", "ratio")]
                  + ["; ".join(found["warnings"])])
    widths = [max(len(r[i]) for r in [["unit", "bytes", "fenced_share", "steps", "spec_range_bytes", "ratio", "warnings"]] + rows)
              for i in range(7)]
    for row in [["unit", "bytes", "fenced_share", "steps", "spec_range_bytes", "ratio", "warnings"]] + rows:
      print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    problems = scan_handoff(handoff)
  for problem in problems:
    print(problem)
  print("scan: clean" if not problems else f"scan: {len(problems)} problem(s)")
  return 1 if problems else 0
