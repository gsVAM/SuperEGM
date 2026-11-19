# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: `superegm postmortem`, the handoff's report of spec section 7.5 (U78).

"""superegm postmortem: one report of a handoff from the store alone (spec section 7.5).

`<handoff dir>/postmortem.md` holds five fixed sections, each one table of numbers: Header, Units, Reviewers,
Owner time and Plan against actual. The command reads the store, needs no run card and writes that one derived
file, as `scan` does; it runs on an open handoff too, the header then saying `in progress`."""

import json
import re
from pathlib import Path

import superegm as core
from superegm import body, launch, review

WRITES = frozenset(['file'])  # the store kinds this subcommand writes: the derived `postmortem.md`
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SECTIONS = ("Header", "Units", "Reviewers", "Owner time", "Plan against actual")
WAIT_RE = re.compile(r"^(\S+) next wait (\S+) (\S+) since (\S+) source (\S+) question (\S+)$")
REASK_RE = re.compile(r"^(\S+) next reask (\S+) (\S+) at (\S+) question (\S+)$")
CLEAR_RE = re.compile(r"^(\S+) next clear (\S+) (\S+) answered by (\S+) at (\S+) answer (\S+)$")
OVERRULED_RE = re.compile(r"^(\S+) finding overruled\b")
ALLOWED_RE = re.compile(r"^(\S+) allowed\b")
SEVERITIES = ("high", "medium", "low")


def register(subparsers):
  p = core.add_parser(subparsers, "postmortem", "write the handoff's post-mortem report (spec section 7.5)", runcard=False)
  p.add_argument("--handoff", required=True, help="the handoff reported on")
  p.set_defaults(run=run, writes=WRITES)


def cell(value) -> str:
  """One table cell: `|` and newlines cannot split it."""
  return "" if value is None else str(value).replace("|", "/").replace("\n", " ").strip()


def render(headers: list, rows: list) -> str:
  lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
  lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
  return "\n".join(lines)


def read_json(path: Path):
  return json.loads(core.read_text(path)) if path.is_file() else None


def seconds(start, end):
  """Whole seconds between two store stamps, or None when either is missing or malformed."""
  try:
    return int(core.epoch(end) - core.epoch(start))
  except (TypeError, ValueError):
    return None


def uids_of(hs: core.Store, units: dict, state: dict) -> list:
  found = list(units.get("order") or []) or sorted(units.get("units") or {})
  return found + [u for u in sorted(state.get("units") or {}) if u not in found]


def superseded(entry: dict) -> bool:
  """A foreman round `foreman.supersede` collected unreviewed: it never ran, so it is no round."""
  return entry.get("phase") == "collected" and str(entry.get("outcome") or "").startswith("not run")


def unit_facts(hs: core.Store, uid: str, state: dict) -> dict:
  """Everything the Units and Plan tables read of one unit."""
  launches = launch.load_launches(hs, uid)
  foreman = core.load_foreman(hs, uid)
  rounds = foreman.get("rounds") or []
  pr = ((state.get("units") or {}).get(uid) or {}).get("pr")  # the whole PR; `status.units[uid].pr` is its number
  pr = pr if isinstance(pr, dict) else {}
  costs = [x["total_cost_usd"] for x in launches if isinstance(x.get("total_cost_usd"), (int, float))
           and not isinstance(x.get("total_cost_usd"), bool)]
  models = []
  for entry in launches:
    model = entry.get("effective_model") or entry.get("model")
    if model and model not in models:
      models.append(model)
  merge_rounds = [r for r in rounds if r.get("merge")]
  return {
      "launches": launches, "models": models,
      "rounds": [r for r in rounds if not r.get("merge") and not superseded(r)],
      "merge_rounds": len(merge_rounds) or len([x for x in launches if x.get("merge")]),
      "merged_at": pr.get("merged_at"), "cost": round(sum(costs), 6) if costs else None,
      "first": launches[0].get("started_at") if launches else None,
      "subagent_calls": sum((x.get("subagent_calls") or {}).get("count", 0) for x in launches)}


def head_findings(hs: core.Store, uid: str) -> dict:
  """The unit's head-review findings counted by severity, over every round of every cycle."""
  count = dict.fromkeys(SEVERITIES, 0)
  for rid in review.cycle_ids(hs, "head", uid):
    for rnd in review.rounds_of(hs, rid, review.load_review(hs, rid)):
      for entry in (rnd.get("reviewers") or {}).values():
        for finding in entry.get("findings") or []:
          if finding.get("severity") in count:
            count[finding["severity"]] += 1
  return count


def header_table(st: core.Store, hs: core.Store, units: dict, uids: list) -> str:
  row = next((r for r in core.handoffs(st.root) if r.get("id") == hs.handoff_id), {})
  approval = core.own_approval(hs, hs.handoff_id) or {}
  waves = units.get("waves") or {}
  state = core.load_state(hs.root) if hs.path("state").is_file() else {}
  facts = [unit_facts(hs, uid, state) for uid in uids]
  firsts = [f["first"] for f in facts if f["first"]]
  lasts = [f["merged_at"] for f in facts if f["merged_at"]]
  total = seconds(min(firsts, key=core.epoch), max(lasts, key=core.epoch)) if firsts and lasts else None
  fields = [("handoff", hs.handoff_id), ("spec", row.get("spec")), ("approval commit", approval.get("commit")),
            ("opened", row.get("opened_at")), ("closed", row.get("closed_at") or "in progress"),
            ("mode", core.run_mode(hs)), ("units", len(uids)), ("waves", len(waves)),
            ("total wall seconds", total)]  # the earliest first launch to the latest merge
  return render(["field", "value"], fields)


def units_table(hs: core.Store, uids: list, units: dict, state: dict) -> str:
  rows = []
  for uid in uids:
    facts, found = unit_facts(hs, uid, state), head_findings(hs, uid)
    launches = facts["launches"]
    wall = seconds(facts["first"], facts["merged_at"]) if facts["merged_at"] else None
    rows.append([uid, ((units.get("units") or {}).get(uid) or {}).get("tier"), ", ".join(facts["models"]), len(launches),
                 sum(1 for x in launches if x.get("fresh")), sum(1 for x in launches if x.get("resumed_from")),
                 sum(1 for x in launches if x.get("failed_resume")), sum(1 for x in launches if x.get("escalated")),
                 facts["merge_rounds"], len(facts["rounds"]), *(found[s] for s in SEVERITIES),
                 facts["subagent_calls"], wall, facts["cost"]])
  return render(["unit", "tier", "models", "launches", "fresh", "resumed", "failed resume", "escalated", "merge rounds",
                 "head rounds", "high", "medium", "low", "subagent calls", "wall seconds", "cost usd"], rows)


def verdicts(hs: core.Store, uids: list) -> tuple:
  """The finding ids the foreman's rulings overruled and allowed, over the handoff's units."""
  overruled, allowed = set(), set()
  for uid in uids:
    for ruling in core.load_foreman(hs, uid).get("rulings") or []:
      text = str(ruling.get("ruling") or "").strip()
      for rx, found in ((OVERRULED_RE, overruled), (ALLOWED_RE, allowed)):
        if m := rx.match(text):
          found.add(m.group(1))
  return overruled, allowed


def reviews_of(st: core.Store, hs: core.Store, spec) -> list:
  folder = hs.path("reviews", "x").parent
  ids = sorted(p.parent.name for p in folder.glob("*/review.json")) if folder.is_dir() else []
  if spec and not hs.legacy:
    ids += [rid for rid in review.cycle_ids(st, "spec", spec) if rid not in ids]
  return [(rid, review.load_review(hs, rid)) for rid in ids]


def reviewers_table(st: core.Store, hs: core.Store, uids: list, spec) -> str:
  overruled, allowed = verdicts(hs, uids)
  stats = {}
  for rid, found in reviews_of(st, hs, spec):
    if not found:
      continue
    for rnd in review.rounds_of(hs, rid, found):
      if rnd.get("what_ran") == "not run":
        continue
      for name, entry in (rnd.get("reviewers") or {}).items():
        row = stats.setdefault((name, found["kind"]), {**dict.fromkeys(SEVERITIES, 0), "fixed": 0, "overruled": 0,
                                                       "allowed": 0, "deferred": 0, "regressions": 0, "quiet": 0})
        findings = entry.get("findings") or []
        row["quiet"] += 0 if findings else 1
        for finding in findings:
          row[finding.get("severity")] = row.get(finding.get("severity"), 0) + 1
          disposition = str(finding.get("disposition") or "")
          row["fixed"] += disposition == "fixed"
          row["deferred"] += disposition.startswith("deferred")
          row["overruled"] += finding.get("id") in overruled
          row["allowed"] += finding.get("id") in allowed
          row["regressions"] += finding.get("regression") == "yes"
  rows = [[name, kind, *(s[k] for k in (*SEVERITIES, "fixed", "overruled", "allowed", "deferred", "regressions", "quiet"))]
          for (name, kind), s in sorted(stats.items())]
  return render(["reviewer", "kind", "high", "medium", "low", "fixed", "overruled", "allowed", "deferred", "regressions",
                 "quiet rounds"], rows)


def wait_episodes(hs: core.Store) -> dict:
  """Per phase, its waits from the journal: `[since, answered_by, answered_at, source]`, in order. A wait ends at its
  `answer.json`'s `at`, else at the first `next clear` after it, else it is still going."""
  journal = hs.path("journal")
  lines = core.read_text(journal).splitlines() if journal.is_file() else []
  phases, hid = {}, hs.handoff_id
  for line in lines:
    if m := WAIT_RE.match(line):
      if m.group(2) == hid:
        phases.setdefault(m.group(3), []).append({"since": m.group(4), "source": m.group(5), "by": None, "at": None})
    elif m := REASK_RE.match(line):
      if m.group(2) == hid:
        phases.setdefault(m.group(3), []).append({"since": m.group(4), "source": "reask", "by": None, "at": None})
    elif m := CLEAR_RE.match(line):
      if m.group(2) == hid and phases.get(m.group(3)):
        open_ = [e for e in phases[m.group(3)] if e["at"] is None]
        if open_ and not (hs.path("file", "waits", f"{m.group(3)}-{open_[-1]['since']}.answer.json")).is_file():
          open_[-1]["by"], open_[-1]["at"] = m.group(4), m.group(5)
  for phase, found in phases.items():
    for episode in found:
      answer = read_json(hs.path("file", "waits", f"{phase}-{episode['since']}.answer.json"))
      if answer:
        episode["by"], episode["at"] = answer.get("by"), answer.get("at")
  return phases


def owner_rows(hs: core.Store, uids: list) -> list:
  rows = []
  for phase, found in sorted(wait_episodes(hs).items()):
    total = 0
    for episode in found:
      total += seconds(episode["since"], episode["at"] or core.now_iso()) or 0
    last = found[-1]
    rows.append([phase, "wait", ",".join(dict.fromkeys(e["source"] for e in found)), total,
                 last["by"] or "waiting", last["at"]])
  for uid in uids:
    foreman = core.load_foreman(hs, uid)
    rulings = {r.get("decision"): r for r in foreman.get("rulings") or [] if r.get("decision")}
    for decision in foreman.get("decisions") or []:
      ruling = rulings.get(decision.get("id")) or {}
      end = ruling.get("posted_at") or ruling.get("at")
      by = "default" if ruling.get("by") == "superegm" else ruling.get("by")
      rows.append([f"{uid} {decision.get('id')}", "decision", decision.get("source") or decision.get("point"),
                   seconds(decision.get("asked_at"), end or core.now_iso()), by or "waiting", end])
    for proceed in foreman.get("proceeds") or []:
      rows.append([f"{uid} proceed {proceed.get('ruling')}", "proceed", proceed.get("review"), None,
                   proceed.get("by"), proceed.get("posted_at")])
    if foreman.get("stopped"):
      rows.append([f"{uid} stopped", "cap stop", None, None, (foreman["stopped"] or {}).get("by"),
                   (foreman["stopped"] or {}).get("at")])
  return rows


def plan_table(hs: core.Store, uids: list, units: dict, state: dict) -> str:
  merged = sorted((u for u in uids if unit_facts(hs, u, state)["merged_at"]), key=lambda u: unit_facts(hs, u, state)["merged_at"])
  critical = set(units.get("critical_path") or [])
  rows = []
  for uid in uids:
    text = core.unit_file_body(hs.path("unit", uid))
    rows.append([uid, ((units.get("units") or {}).get(uid) or {}).get("wave"), "yes" if uid in critical else "no",
                 len(body.steps(text)), merged.index(uid) + 1 if uid in merged else None,
                 len(unit_facts(hs, uid, state)["rounds"])])
  return render(["unit", "wave", "critical path", "planned steps", "merge order", "head rounds"], rows)


def build(st: core.Store, hs: core.Store) -> str:
  units = read_json(hs.path("units")) or {}
  state = core.load_state(hs.root) if hs.path("state").is_file() else {}
  uids = uids_of(hs, units, state)
  row = next((r for r in core.handoffs(st.root) if r.get("id") == hs.handoff_id), {})
  tables = [header_table(st, hs, units, uids), units_table(hs, uids, units, state),
            reviewers_table(st, hs, uids, row.get("spec")),
            render(["item", "kind", "asked by", "waited", "answered by", "answered at"], owner_rows(hs, uids)),
            plan_table(hs, uids, units, state)]
  return f"# Post-mortem {hs.handoff_id}\n\n" + "\n\n".join(f"## {name}\n\n{t}" for name, t in zip(SECTIONS, tables)) + "\n"


def run(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  hs = core.handoff_store(st, args.handoff)
  out = hs.path("file", "postmortem.md")
  core.atomic_write(out, build(st, hs))
  print(out)
  return 0
