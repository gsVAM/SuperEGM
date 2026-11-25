# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: `superegm postmortem`, the handoff's report of spec section 7.5 (U78); the Lessons table and `--retro <file>` (U87); a copy's settlement counted on the finding it copies, and a round of only copies quiet (U110, 1.3 design section 3.10).

"""superegm postmortem: one report of a handoff from the store (spec section 7.5), and its retrospective's record (7.7).

`<handoff dir>/postmortem.md` holds six fixed sections, each one table: Header, Units, Reviewers, Owner time, Plan against actual and
Lessons (U87: one fact row per signal, each naming its source record, no proposal). The command reads the store, plus one
`gh api repos/<repo>/issues/comments/<id>` read per respec row (the deviation's quoted evidence; `evidence unread (comment
<id>)` when that read fails), needs no run card and writes that one derived file, as `scan` does; `--retro <file>` writes
`retro.md`, the file's bytes, instead and builds no report. It runs on an open handoff too, the header then saying `in progress`.

What the store does not hold, the report does not invent: launches record no token counts (the Units table has cost
only); a head finding's allowed outcome is the foreman's ruling text `<fid> allowed` read per unit (a unit's several
head cycles share them), its overruled outcome the text `<fid> finding overruled`, or a settled disposition; a
finding of any kind settled `contested` or `declined` counts overruled; a decision's wait has no start but the foreman's `asked_at`, so a `decide`
answer is a row without a waiting time; who answered is a config owner's login as `owner`, the foreman's `superegm`
as `default`, a judged answer as `judges:<panel>`, and a `decide --default` answer, stored by `owner` with `default: true`
(U87), as `owner` in the Owner time table; the Lessons table reads the marker."""

import json
import re
from pathlib import Path

import superegm as core
from superegm import approve_spec, body, decision, inbox, launch, launch_builder, report, respec, review

WRITES = frozenset(['file'])  # the store kinds this subcommand writes: the derived `postmortem.md` and, from `--retro <file>`, `retro.md`
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SECTIONS = ("Header", "Units", "Reviewers", "Owner time", "Plan against actual", "Lessons")
WAIT_RE = re.compile(r"^(\S+) next wait (\S+) (\S+) since (\S+) source (\S+) question (\S+)$")
REASK_RE = re.compile(r"^(\S+) next reask (\S+) (\S+) at (\S+) question (\S+)$")
CLEAR_RE = re.compile(r"^(\S+) next clear (\S+) (\S+) answered by (\S+) at (\S+) answer (\S+)$")
SUPERSEDED_RE = re.compile(r"^(\S+) driver: (\S+) superseded: wait record removed$")
OVERRULED_RE = re.compile(r"^(\S+) finding overruled\b")
ALLOWED_RE = re.compile(r"^(\S+) allowed\b")
COPY_RE = re.compile(r"(?:unreplied|contested) (\S+):")  # a foreman finding's claim that repeats finding `<fid>` (`collect.foreman_findings`)
SEVERITIES = ("high", "medium", "low")


def register(subparsers):
  p = core.add_parser(subparsers, "postmortem", "write the handoff's post-mortem report (spec section 7.5)", runcard=False)
  p.add_argument("--handoff", required=True, help="the handoff reported on")
  p.add_argument("--retro", help="copy this file to the handoff's retro.md (spec section 7.7) instead of writing the report")
  p.set_defaults(run=run, writes=WRITES)


def cell(value) -> str:
  """One table cell: a `|` is escaped as `\\|` (the text stays verbatim in the rendered table) and a newline is a space."""
  return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ").strip()


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


def recorded_rounds(hs: core.Store, uid: str) -> set:
  """The round numbers of the unit's head reviews in which a reviewer's result is recorded: `review.record_round` writes
  them without advancing the foreman's phase, so a `prepared` round holding one is a round in progress."""
  return {n for rid in review.cycle_ids(hs, "head", uid) for n in review.round_numbers(hs, rid)
          if review.load_round(hs, rid, n).get("reviewers")}


def superseded(entry: dict, recorded: set = frozenset()) -> bool:
  """A foreman round that was never run: collected as `not run (...)`, by `foreman.supersede`, a moved target
  (`review`), an owner's interrupt or `collect --not-run`; or only fetched or prepared, with no reviewer's result
  recorded in it yet (`recorded`, the round numbers that hold one). It is no round."""
  return (entry.get("phase") in ("fetched", "prepared") and entry.get("round") not in recorded) or (
      entry.get("phase") == "collected" and str(entry.get("outcome") or "").startswith("not run"))


def unit_facts(hs: core.Store, uid: str, state: dict) -> dict:
  """Everything the Units and Plan tables read of one unit."""
  launches = launch.load_launches(hs, uid)
  foreman = core.load_foreman(hs, uid)
  rounds = foreman.get("rounds") or []
  recorded = recorded_rounds(hs, uid)
  pr = ((state.get("units") or {}).get(uid) or {}).get("pr")  # the whole PR; `status.units[uid].pr` is its number
  pr = pr if isinstance(pr, dict) else {}
  costs = [x["total_cost_usd"] for x in launches if isinstance(x.get("total_cost_usd"), (int, float))
           and not isinstance(x.get("total_cost_usd"), bool)]
  models = []
  for entry in launches:
    used = entry.get("effective_model")
    if not used or used == "requested only":  # an unreadable result file: the requested model is all there is
      used = entry.get("model")
    for model in str(used or "").split(", "):  # a launch that used several models stores them joined
      if model and model not in models:
        models.append(model)
  return {
      "launches": launches, "models": models,
      "rounds": [r for r in rounds if not r.get("merge") and not superseded(r, recorded)],
      # a launch's `merge` is `alone` (a merge round: foreman.py flags the round from it) or `with-fix` (a fix round)
      "merge_rounds": sum(1 for x in launches if x.get("merge") == "alone"),
      "merged_at": pr.get("merged_at"), "cost": round(sum(costs), 6) if costs else None,
      "first": launches[0].get("started_at") if launches else None,
      "subagent_calls": sum((x.get("subagent_calls") or {}).get("count", 0) for x in launches)}


def note_finding(entries: list, latest: dict, scope: tuple, name: str, finding: dict, item) -> str:
  """Count `finding` once: `item` (what the caller tallies it by) joins `entries`, or, for a finding carried into a later
  round, replaces the copy before it. `collect.carry` copies a still-open foreman finding under its own id with
  `carried_from`; `review.carry_externals` copies an external one with the same id and claim; `review settle` and
  triage write a carried finding's outcome on its newest copy (`review.locate_finding`), so the newest copy stands.
  A foreman `unreplied <fid>: ...` or `contested <fid>: ...` high repeats a finding some record holds (`COPY_RE`): it is
  no finding, and a settlement it holds counts on the finding it copies, down the chain to the original (U110). Findings
  of one `scope` (the review kind and artifact) are told apart by reviewer and id.
  Returns `""` for a finding counted as new, else the id of the finding it is a copy of (its own for a carried one)."""
  fid = finding.get("id")
  if m := COPY_RE.match(str(finding.get("claim") or "")):
    root = latest.get(("link", scope, m.group(1)), m.group(1))
    latest[("link", scope, fid)] = root
    if disposition := finding.get("disposition"):
      latest[("settled", scope, root)] = disposition
      original = latest.get(("id", scope, root))
      if original is not None and not original.get("disposition"):
        original["disposition"] = disposition
    return str(root)
  external = name.startswith("external:")
  key = (*scope, name, fid) + ((finding.get("claim"),) if external else ())
  copy = (external or finding.get("carried_from")) and key in latest
  if copy:
    entries[latest[key]] = item
  else:
    latest[key] = len(entries)
    entries.append(item)
  latest[("id", scope, fid)] = finding
  if not finding.get("disposition") and ("settled", scope, fid) in latest:  # a copy settled it before a newer copy of it came
    finding["disposition"] = latest[("settled", scope, fid)]
  return str(fid) if copy else ""


def cycle_order(rid: str) -> tuple:
  """A review's place among its artifact's cycles: `head-U01-c2` before `head-U01-c10`, which the names' order is not."""
  m = re.search(r"-c(\d+)$", rid)
  return (rid[:m.start()], int(m.group(1))) if m else (rid, 0)


def head_findings(hs: core.Store, uid: str) -> dict:
  """The unit's head-review findings counted by severity, over every round of every cycle, each once."""
  found, latest = [], {}
  for rid in sorted(review.cycle_ids(hs, "head", uid), key=cycle_order):
    for rnd in review.rounds_of(hs, rid, review.load_review(hs, rid)):
      for name, entry in (rnd.get("reviewers") or {}).items():
        for finding in entry.get("findings") or []:
          note_finding(found, latest, ("head", uid), name, finding, finding)
  count = dict.fromkeys(SEVERITIES, 0)
  for finding in found:
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
  """The spec-review cycles this handoff owns: after the review cycle of the entry before its first approval entry, up
  to its last entry's (a re-approval after a void, and `amend-units`, keep the id and add entries). Spec reviews sit at
  the store's root, shared by every handoff of the spec; no approval of its own, none."""
  entries = core.load_approvals(hs, spec) if spec else []
  own = [i for i, entry in enumerate(entries) if entry.get("handoff_id") == hs.handoff_id]
  if not own:
    return range(0)
  before = max((approve_spec.cycle_of(e.get("review")) for e in entries[:own[0]]), default=0)
  return range(before + 1, max(approve_spec.cycle_of(entries[i].get("review")) for i in own) + 1)


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


def reviewer_stats(st: core.Store, hs: core.Store, spec) -> dict:
  """Per `(reviewer, kind)`, the counts the Reviewers table shows; the Lessons table reads the same numbers. `overrules` is
  `overruled` plus `allowed`: an allowance is recorded as an overrule (spec 13.2, `decision.py`), and that one sum is what the table,
  the Lessons rows and the integrate summary name a reviewer's overruled findings by."""
  stats, found, latest, ruled = {}, [], {}, {}
  for rid, cycle in sorted(reviews_of(st, hs, spec), key=lambda r: cycle_order(r[0])):
    if not cycle:
      continue
    kind = cycle["kind"]
    head = kind == "head"  # a head's outcomes are the foreman's rulings; any other kind's, `review settle`'s
    overruled, allowed = ruled.setdefault(cycle["artifact"], verdicts(hs, cycle["artifact"])) if head else (set(), set())
    for rnd in review.rounds_of(hs, rid, cycle):
      for name, entry in (rnd.get("reviewers") or {}).items():
        if entry.get("not_run"):  # a reviewer that did not run raised nothing and kept no quiet round
          continue
        row = stats.setdefault((name, kind), {**dict.fromkeys(SEVERITIES, 0), "fixed": 0, "overruled": 0,
                                              "allowed": 0, "overrules": 0, "deferred": 0, "regressions": 0, "quiet": 0})
        findings = entry.get("findings") or []
        new = 0
        for finding in findings:
          copied = note_finding(found, latest, (kind, cycle["artifact"]), name, finding, (name, kind, overruled, allowed, finding))
          new += not copied
          for ruling in (overruled, allowed):  # a ruling on a copy rules the finding it copies
            if copied and finding.get("id") in ruling:
              ruling.add(copied)
        row["quiet"] += 0 if new else 1  # a round of only copies raised nothing new
  for name, kind, overruled, allowed, finding in found:
    row, disposition, fid = stats[(name, kind)], str(finding.get("disposition") or ""), finding.get("id")
    row[finding.get("severity")] = row.get(finding.get("severity"), 0) + 1
    row["fixed"] += disposition == "fixed"
    row["deferred"] += disposition.startswith("deferred")
    row["allowed"] += fid in allowed
    row["overruled"] += fid not in allowed and (fid in overruled or disposition in ("contested", "declined"))
    row["regressions"] += finding.get("regression") == "yes"
  for row in stats.values():
    row["overrules"] = row["overruled"] + row["allowed"]
  return stats


def reviewers_table(st: core.Store, hs: core.Store, uids: list, spec) -> str:
  rows = [[name, kind, *(s[k] for k in (*SEVERITIES, "fixed", "overruled", "allowed", "overrules", "deferred", "regressions", "quiet"))]
          for (name, kind), s in sorted(reviewer_stats(st, hs, spec).items())]
  return render(["reviewer", "kind", "high", "medium", "low", "fixed", "overruled", "allowed", "overrules", "deferred", "regressions",
                 "quiet rounds"], rows)


def wait_episodes(hs: core.Store) -> dict:
  """Per phase, its waits from the journal: `{since, source, by, at}`, in order. A wait ends at its `answer.json`'s `at`;
  else at the `next clear` that removed it; else at the next wait or re-ask, of any phase, that replaced it (the chain record holds one wait); else at the
  journal line where the driver removed a superseded handoff's wait record; else it is still going (`at` None)."""
  journal = hs.path("journal")
  lines = core.read_text(journal).splitlines() if journal.is_file() else []
  phases, hid = {}, hs.handoff_id

  def unanswered(found: list) -> list:
    return [e for e in found if e["at"] is None
            and not hs.path("file", "waits", f"{e['phase']}-{e['since']}.answer.json").is_file()]

  def begin(phase: str, since: str, source: str) -> None:
    for found in phases.values():  # the chain record holds one wait whatever its phase: a new one replaces it
      for episode in unanswered(found):  # replaced before anyone answered it
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
  the foreman's own `superegm`, and a judged `decide` answer its raw `judges:<panel>`; a `decide --default` answer is
  stored by `owner` (decide.py) with `default: true`, so it reads `owner` here (the Lessons table reads the marker)."""
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
  for uid, unit in sorted(((read_json(hs.path("units")) or {}).get("units") or {}).items()):
    for declared in unit.get("decisions") or []:  # declared by the plan, not yet answered: `decide` records an answer
      if f"{uid}/{declared.get('id')}" not in (state.get("decisions") or {}):
        rows.append([f"{uid}/{declared.get('id')}", "decision", "plan", None, "waiting", None])
  reviews = reviews_of(st, hs, spec)
  for rid, found in reviews:
    for ruling in (found or {}).get("rulings") or []:
      if ruling.get("ruling") in ("proceed", "stop"):
        rows.append([f"{rid} {ruling.get('id')}", ruling["ruling"], rid, None, who(ruling.get("by")), ruling.get("at")])
  for uid in uids:
    foreman = core.load_foreman(hs, uid)
    heads = [f for _, f in reviews if f and f.get("kind") == "head" and f.get("artifact") == uid]
    stamps = {(rid, r.get("id")): r.get("at") for rid, f in reviews if f in heads for r in f.get("rulings") or []}
    for decision in foreman.get("decisions") or []:
      # a decision may take several rulings (one per `<fid> allowed` option): the last one ends it, and while
      # `report.pending_decisions` still holds it, it waits
      given = [r for r in foreman.get("rulings") or [] if r.get("decision") == decision.get("id")]
      pending = bool(report.pending_decisions({"decisions": [decision], "rulings": given}))
      ruling = given[-1] if given and not pending else {}
      named = (decision.get("source") or "").split()  # `review <id> cap|round <n>`: the review that ruled it, if a proceed
      end = ruling.get("posted_at") or ruling.get("at") or stamps.get((named[1] if len(named) > 1 else None, ruling.get("review")))
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


DEVIATION_RE = re.compile(r"\*\*Deviation \(spec\):\*\*(.*)")
COMMENT_LABEL_RE = re.compile(r"\*\*(?:Builder status|Ruling|Deviation|Blocked|Status|Reply)(?: \([^)]*\))?:\*\*")  # a whole label of a comment (`**Deviation (spec):**`); other bold text, `**Status mismatch:**` too, is evidence


def deviation_evidence(st: core.Store, comment_id) -> str:
  """The lines under `**Deviation (spec):**` in the comment `gh api repos/<repo>/issues/comments/<id>` returns, up to the
  next comment label (`COMMENT_LABEL_RE`; bold text inside the evidence does not end it, as in `decision.check_respec`) and
  less its option lines (`- (a) ...`); `evidence unread (comment <id>)` when the read fails or the comment holds none."""
  try:
    text = str((core.gh_json(["api", f"repos/{st.config['repo']}/issues/comments/{comment_id}"]) or {}).get("body") or "")
  except (core.GhError, ValueError, OSError):  # OSError: no `gh` binary
    text = ""
  lines, taking = [], False
  for line in text.splitlines():
    if m := DEVIATION_RE.search(line):
      taking, line = True, m.group(1)
    elif taking and COMMENT_LABEL_RE.match(line):
      break
    if taking and line.strip() and not line.startswith("- ("):
      lines.append(line.strip())
  return " ".join(lines) if lines else f"evidence unread (comment {comment_id})"


def finding_evidence(hs: core.Store, uid, fid) -> str:
  """A respec opened on the foreman's spec finding `fid` (it stores `finding`, not `comment_id`): the finding's claim as the
  foreman decision's question holds it (`decision.spec_claims`); `spec finding <fid>` when no decision of the unit holds it."""
  for held in (core.load_foreman(hs, uid).get("decisions") or []) if uid else []:
    if claim := decision.spec_claims(str(held.get("question") or "")).get(fid):
      return f"spec finding {fid}: {claim}"
  return f"spec finding {fid}"


def respec_rows(st: core.Store, hs: core.Store, spec) -> list:
  """One row per respec: its first approved range as `path:a-b`, its unit and the deviation's quoted evidence."""
  folder = respec.respec_path(hs)
  if not folder.is_dir():
    return []
  # `R<n>` restarts in each handoff of the spec: only this handoff's approvals name its respecs
  entries = {e.get("respec"): e for e in respec.entries_of(hs, hs.handoff_id, spec) if e.get("kind") == "respec"} if spec else {}
  try:
    rel = Path(spec).resolve().relative_to(core.git_toplevel(Path.cwd()).resolve()).as_posix()
  except (TypeError, ValueError):
    rel = str(spec)
  rows = []
  for path in sorted(folder.iterdir(), key=lambda p: (len(p.name), p.name)):
    match = respec.OPEN_FILE.match(path.name)
    if not match:
      continue
    record, rid = read_json(path) or {}, match.group(1)
    ranges = (entries.get(rid) or {}).get("ranges") or []
    where = f"{rel}:{ranges[0][0]}-{ranges[0][1]}" if ranges else "not approved"
    evidence = (deviation_evidence(st, record["comment_id"]) if record.get("comment_id")
                else finding_evidence(hs, record.get("unit"), record.get("finding")))
    rows.append(["respec", record.get("unit"), f"respec/{path.name}", f"{rid} {where}: {evidence}"])
  return rows


def amendment_rows(hs: core.Store, uids: list) -> list:
  """One row per interface amendment that took effect, read as the builder's launch reads them (`launch_builder.amendments_for`):
  a file `amendments/<comment id>.json` counts only when a ruling names its comment, and the legacy `state.json` list counts."""
  found = [a for uid in uids for a in launch_builder.amendments_for(hs, uid, "") if a.get("unit") == uid]
  files = sorted((hs.path("state").parent / "amendments").glob("*.json"))

  def source(amendment: dict) -> str:
    """The file is named for the deviation comment; its entries' `comment_id` is the ruling's, so find the file that holds the entry."""
    named = next((f.name for f in files if amendment in (read_json(f) or [])), None)
    return f"amendments/{named}" if named else "state.json amendments"

  return [["interface amendment", a.get("unit"), source(a), f"{a.get('name')}: {a.get('text')}"]
          for a in sorted(found, key=lambda a: str(a.get("at")))]


def fix_design_rows(st: core.Store, hs: core.Store, spec) -> list:
  """One row per `fix-design` finding of any review of the handoff, each counted once."""
  found, latest = [], {}
  for rid, cycle in sorted(reviews_of(st, hs, spec), key=lambda r: cycle_order(r[0])):
    for rnd in review.rounds_of(hs, rid, cycle) if cycle else []:
      for name, entry in (rnd.get("reviewers") or {}).items():
        for finding in entry.get("findings") or []:
          note_finding(found, latest, (cycle["kind"], cycle["artifact"]), name, finding, (cycle, rid, name, finding))
  return [["fix-design finding", cycle["artifact"], f"reviews/{rid}", f"{name} {finding.get('id')}: {finding.get('claim')}"]
          for cycle, rid, name, finding in found if finding.get("disposition") == "fix-design"]


def reviewer_rows(st: core.Store, hs: core.Store, spec) -> list:
  """The reviewers with no finding kept (none raised, or every one overruled or allowed), whatever the others raised, and
  those overruled most, by the Reviewers table's `overrules` column (an allowance counts, spec 13.2); with no finding overruled
  anywhere (`most` 0) no reviewer is most overruled."""
  total = {}
  for (name, _), s in reviewer_stats(st, hs, spec).items():
    t = total.setdefault(name, {"raised": 0, "overruled": 0})
    t["raised"] += sum(s[k] for k in SEVERITIES)
    t["overruled"] += s["overrules"]
  most = max((t["overruled"] for t in total.values()), default=0)
  rows = []
  for name, t in sorted(total.items()):
    if t["raised"] == t["overruled"]:
      rows.append(["reviewer kept nothing", None, "Reviewers table", f"{name}: {t['raised']} raised, {t['overruled']} overruled"])
    elif most and t["overruled"] == most:
      rows.append(["reviewer most overruled", None, "Reviewers table", f"{name}: {t['overruled']} of {t['raised']} overruled"])
  return rows


def unit_rows(hs: core.Store, uids: list) -> list:
  """A unit with an escalated launch, and one row per cap decision whose own ruling was a stop."""
  rows = []
  for uid in uids:
    escalated = [e for e in launch.load_launches(hs, uid) if e.get("escalated")]
    if escalated:
      rows.append(["unit escalated", uid, f"launches/{uid}", f"{len(escalated)} escalated launch(es)"])
    foreman = core.load_foreman(hs, uid)
    for decision in foreman.get("decisions") or []:
      if str(decision.get("source") or "").endswith(" cap"):
        given = [r for r in foreman.get("rulings") or [] if r.get("decision") == decision.get("id")]
        if any(str(r.get("ruling") or "").startswith("stop") for r in given):
          rows.append(["unit stopped at the cap", uid, f"foreman/{uid}.json {decision.get('id')}", str(decision.get("source"))])
  return rows


def lessons_table(st: core.Store, hs: core.Store, uids: list, spec, state: dict) -> str:
  """The Lessons table: facts from the store, one row per signal, each naming its source record; no proposal."""
  rows = respec_rows(st, hs, spec) + fix_design_rows(st, hs, spec) + amendment_rows(hs, uids)
  rows += reviewer_rows(st, hs, spec) + unit_rows(hs, uids)
  # a plan decision answered by `decide --default` carries `default: true`; a foreman decision, answered by `superegm`
  rows += [["decision answered by default", key.split("/")[0], f"state.json decisions {key}", f"{key}: {found.get('answer')}"]
           for key, found in sorted((state.get("decisions") or {}).items()) if found.get("default")]
  rows += [["decision answered by default", row[0].split()[0], f"foreman/{row[0].split()[0]}.json {row[0].split()[1]}", f"{row[0]}: {row[2]}"]
           for row in owner_rows(st, hs, uids, spec) if row[1] == "decision" and row[4] == "default" and " " in row[0]]
  return render(["signal", "unit", "source", "fact"], rows)


def build(st: core.Store, hs: core.Store) -> str:
  units = read_json(hs.path("units")) or {}
  state = core.load_state(hs.root) if hs.path("state").is_file() else {}
  uids = uids_of(hs, units, state)
  row = next((r for r in core.handoffs(st.root) if r.get("id") == hs.handoff_id), {})
  tables = [header_table(st, hs, units, uids), units_table(hs, uids, units, state),
            reviewers_table(st, hs, uids, row.get("spec")),
            render(["item", "kind", "asked by", "waited", "answered by", "answered at"], owner_rows(st, hs, uids, row.get("spec"))),
            plan_table(hs, uids, units, state), lessons_table(st, hs, uids, row.get("spec"), state)]
  return f"# Post-mortem {hs.handoff_id}\n\n" + "\n\n".join(f"## {name}\n\n{t}" for name, t in zip(SECTIONS, tables)) + "\n"


def run(args) -> int:
  st = core.store(core.git_toplevel(Path.cwd()))
  hs = core.handoff_store(st, args.handoff)
  if args.retro:  # the retrospective's record: the agreed file's bytes, no report rebuilt, no run card
    source = Path(args.retro)
    if not source.is_file():
      raise core.HandoffError(f"postmortem: --retro {args.retro} is not a file")
    out = hs.path("file", "retro.md")
    core.atomic_write(out, source.read_bytes())
    print(out)
    return 0
  out = hs.path("file", "postmortem.md")
  core.atomic_write(out, build(st, hs))
  print(out)
  return 0
