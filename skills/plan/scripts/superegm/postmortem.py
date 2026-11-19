# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: `superegm postmortem`, the handoff's report of spec section 7.5 (U78).

"""superegm postmortem: one report of a handoff from the store alone (spec section 7.5).

`<handoff dir>/postmortem.md` holds five fixed sections, each one table of numbers: Header, Units, Reviewers,
Owner time and Plan against actual. The command reads the store, needs no run card and writes that one derived
file, as `scan` does; it runs on an open handoff too, the header then saying `in progress`.

What the store does not hold, the report does not invent: launches record no token counts (the Units table has cost
only); a head finding's overruled and allowed outcomes are the foreman's ruling texts (`<fid> finding overruled`,
`<fid> allowed`) read per unit, and a unit's several head cycles share them; a spec, plan or integrate finding settled
`contested` or `declined` counts overruled; a decision's wait has no start but the foreman's `asked_at`, so a `decide`
answer is a row without a waiting time."""

import json
import re
from pathlib import Path

import superegm as core
from superegm import approve_spec, body, inbox, launch, review

WRITES = frozenset(['file'])  # the store kinds this subcommand writes: the derived `postmortem.md`
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SECTIONS = ("Header", "Units", "Reviewers", "Owner time", "Plan against actual")
WAIT_RE = re.compile(r"^(\S+) next wait (\S+) (\S+) since (\S+) source (\S+) question (\S+)$")
REASK_RE = re.compile(r"^(\S+) next reask (\S+) (\S+) at (\S+) question (\S+)$")
CLEAR_RE = re.compile(r"^(\S+) next clear (\S+) (\S+) answered by (\S+) at (\S+) answer (\S+)$")
SUPERSEDED_RE = re.compile(r"^(\S+) driver: (\S+) superseded: wait record removed$")
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
    return max(0, int(core.epoch(end) - core.epoch(start)))
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


def verdicts(hs: core.Store, uid: str) -> tuple:
  """The finding ids the foreman's rulings on one unit overruled and allowed. Finding ids (`<reviewer>-<round>-<n>`)
  repeat across units, so a head review reads its own unit's rulings alone; a unit's several head cycles share them."""
  overruled, allowed = set(), set()
  for ruling in core.load_foreman(hs, uid).get("rulings") or []:
    text = str(ruling.get("ruling") or "").strip()
    for rx, found in ((OVERRULED_RE, overruled), (ALLOWED_RE, allowed)):
      if m := rx.match(text):
        found.add(m.group(1))
  return overruled, allowed


def spec_cycles(hs: core.Store, spec) -> range:
  """The spec-review cycles this handoff owns: after the previous approval entry's review cycle, up to its own
  approval's. Spec reviews sit at the store's root, shared by every handoff of the spec; no approval of its own, none."""
  entries = core.load_approvals(hs, spec) if spec else []
  for i, entry in enumerate(entries):
    if entry.get("handoff_id") == hs.handoff_id:
      before = max((approve_spec.cycle_of(e.get("review")) for e in entries[:i]), default=0)
      return range(before + 1, approve_spec.cycle_of(entry.get("review")) + 1)
  return range(0)


def reviews_of(st: core.Store, hs: core.Store, spec) -> list:
  """This handoff's reviews: its own (`inbox.review_dirs`, which a legacy flat store's shared folder needs) and the
  spec cycles it owns."""
  owned = spec_cycles(hs, spec)
  found = []
  for path in inbox.review_dirs(hs, spec):
    m = re.fullmatch(r"spec-(?:(?!-integrate-).)+-c(\d+)", path.name)  # an integrate review is no spec cycle
    if m is None or int(m.group(1)) in owned:
      found.append(path.name)
  return [(rid, review.load_review(hs, rid)) for rid in found]


def reviewers_table(st: core.Store, hs: core.Store, uids: list, spec) -> str:
  stats, carried = {}, set()
  for rid, found in reviews_of(st, hs, spec):
    if not found:
      continue
    head = found["kind"] == "head"  # a head's outcomes are the foreman's rulings; any other kind's, `review settle`'s
    overruled, allowed = verdicts(hs, found["artifact"]) if head else (set(), set())
    for rnd in review.rounds_of(hs, rid, found):
      for name, entry in (rnd.get("reviewers") or {}).items():
        if entry.get("not_run"):  # a reviewer that did not run raised nothing and kept no quiet round
          continue
        row = stats.setdefault((name, found["kind"]), {**dict.fromkeys(SEVERITIES, 0), "fixed": 0, "overruled": 0,
                                                       "allowed": 0, "deferred": 0, "regressions": 0, "quiet": 0})
        findings = entry.get("findings") or []
        row["quiet"] += 0 if findings else 1
        for finding in findings:
          if name.startswith("external:"):  # `carry_externals` copies an unsettled one into later rounds: one finding
            key = (found["kind"], found["artifact"], name, finding.get("id"), finding.get("claim"))
            if key in carried:
              continue
            carried.add(key)
          row[finding.get("severity")] = row.get(finding.get("severity"), 0) + 1
          disposition = str(finding.get("disposition") or "")
          fid = finding.get("id")
          row["fixed"] += disposition == "fixed"
          row["deferred"] += disposition.startswith("deferred")
          row["allowed"] += fid in allowed
          row["overruled"] += fid not in allowed and (fid in overruled or disposition in ("contested", "declined"))
          row["regressions"] += finding.get("regression") == "yes"
  rows = [[name, kind, *(s[k] for k in (*SEVERITIES, "fixed", "overruled", "allowed", "deferred", "regressions", "quiet"))]
          for (name, kind), s in sorted(stats.items())]
  return render(["reviewer", "kind", "high", "medium", "low", "fixed", "overruled", "allowed", "deferred", "regressions",
                 "quiet rounds"], rows)


def wait_episodes(hs: core.Store) -> dict:
  """Per phase, its waits from the journal: `{since, source, by, at}`, in order. A wait ends at its `answer.json`'s `at`;
  else at the `next clear` that removed it; else at the next wait or re-ask of its phase that replaced it; else at the
  journal line where the driver removed a superseded handoff's wait record; else it is still going (`at` None)."""
  journal = hs.path("journal")
  lines = core.read_text(journal).splitlines() if journal.is_file() else []
  phases, hid = {}, hs.handoff_id

  def unanswered(found: list) -> list:
    return [e for e in found if e["at"] is None
            and not hs.path("file", "waits", f"{e['phase']}-{e['since']}.answer.json").is_file()]

  def begin(phase: str, since: str, source: str) -> None:
    for episode in unanswered(phases.get(phase, [])):  # replaced before anyone answered it
      episode["by"], episode["at"] = "replaced", since
    phases.setdefault(phase, []).append({"phase": phase, "since": since, "source": source, "by": None, "at": None})

  for line in lines:
    if m := WAIT_RE.match(line):
      if m.group(2) == hid:
        begin(m.group(3), m.group(4), m.group(5))
    elif m := REASK_RE.match(line):
      if m.group(2) == hid:
        begin(m.group(3), m.group(4), "reask")
    elif m := CLEAR_RE.match(line):
      if m.group(2) == hid:
        for episode in unanswered(phases.get(m.group(3), []))[-1:]:
          episode["by"], episode["at"] = m.group(4), m.group(5)
    elif m := SUPERSEDED_RE.match(line):
      if m.group(2) == hid:
        for found in phases.values():
          for episode in unanswered(found):
            episode["by"], episode["at"] = "superseded", m.group(1)
  for phase, found in phases.items():
    for episode in found:
      answer = read_json(hs.path("file", "waits", f"{phase}-{episode['since']}.answer.json"))
      if answer:
        episode["by"], episode["at"] = answer.get("by"), answer.get("at")
  return phases


def owner_rows(st: core.Store, hs: core.Store, uids: list, spec) -> list:
  """The Owner time rows: each phase's waits; each decision (the plan's `decide` answers, the foreman's); each review's
  `proceed` and `stop` rulings; each stopped unit. Who answered reads `owner` for a config owner's login, `default` for
  the foreman's own."""
  owners = set((st.config or {}).get("owners") or [])

  def who(by):
    return "owner" if by in owners else "default" if by == "superegm" else by

  rows = []
  for phase, found in sorted(wait_episodes(hs).items()):
    total = sum(seconds(e["since"], e["at"] or core.now_iso()) or 0 for e in found)
    last = found[-1]
    rows.append([phase, "wait", ",".join(dict.fromkeys(e["source"] for e in found)), total,
                 who(last["by"]) or "waiting", last["at"]])
  state = core.load_state(hs.root) if hs.path("state").is_file() else {}
  for key, found in sorted((state.get("decisions") or {}).items()):
    rows.append([key, "decision", "decide", None, who(found.get("by")), found.get("decided_at")])
  reviews = reviews_of(st, hs, spec)
  for rid, found in reviews:
    for ruling in (found or {}).get("rulings") or []:
      if ruling.get("ruling") in ("proceed", "stop"):
        rows.append([f"{rid} {ruling.get('id')}", ruling["ruling"], rid, None, who(ruling.get("by")), ruling.get("at")])
  for uid in uids:
    foreman = core.load_foreman(hs, uid)
    heads = [f for _, f in reviews if f and f.get("kind") == "head" and f.get("artifact") == uid]
    stamps = {r.get("id"): r.get("at") for f in heads for r in f.get("rulings") or []}
    rulings = {r.get("decision"): r for r in foreman.get("rulings") or [] if r.get("decision")}
    for decision in foreman.get("decisions") or []:
      ruling = rulings.get(decision.get("id")) or {}
      end = ruling.get("posted_at") or ruling.get("at") or stamps.get(ruling.get("review"))  # a proceed's carries none
      rows.append([f"{uid} {decision.get('id')}", "decision", decision.get("source") or decision.get("point"),
                   seconds(decision.get("asked_at"), end or core.now_iso()), who(ruling.get("by")) or "waiting", end])
    if foreman.get("stopped"):
      stopped = foreman["stopped"] or {}
      rows.append([f"{uid} stopped", "stop", stopped.get("reason"), None, who(stopped.get("by")), stopped.get("at")])
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
            render(["item", "kind", "asked by", "waited", "answered by", "answered at"], owner_rows(st, hs, uids, row.get("spec"))),
            plan_table(hs, uids, units, state)]
  return f"# Post-mortem {hs.handoff_id}\n\n" + "\n\n".join(f"## {name}\n\n{t}" for name, t in zip(SECTIONS, tables)) + "\n"


def run(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  hs = core.handoff_store(st, args.handoff)
  out = hs.path("file", "postmortem.md")
  core.atomic_write(out, build(st, hs))
  print(out)
  return 0
