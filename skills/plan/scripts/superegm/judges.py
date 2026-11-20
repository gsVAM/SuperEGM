# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the judges subcommand (spec section 13.1) and `judges question`, the
# leavemealone-mode question renderer of section 13.2 (U11); the cap question names a spec review's scope (U19); the default members read from `DEFAULT_CONFIG` (U28); a `launch <n>` or `closed <n>` question renders its pending decision's options, a stall's heading its facts (U31); its own `judges` config key, moved from `__init__` (U32); the panel's instructions section rendered once at open by its parent card's skill, placed last in each brief and copied to each member's record (U38); `respec`, the owner's alone, left out of the judges' question with every other option keeping its letter, its leavemealone wait read off the options (U84); the Astra member's brief embeds each evidence file's contents, re-checked against its recorded sha256, and an unconverged panel's point 1 question gains the verdict line (U88).

"""superegm judges open|record|diff|verdict|question: the judge panel over a question file, and the
question file rendered from the record at a decision point."""

import json
import re
from pathlib import Path

import superegm as core
from superegm import instructions

WRITES = frozenset(["judges", "runcards", "questions", "instructions", "foreman"])  # the store kinds this subcommand writes (`instructions`: a spec review's reference copies, U74; `foreman`: an unconverged panel's verdict line on the open decision, U88)
CONFIG_DEFAULTS = {"judges": {"min_vendors": 1,  # its own config key (U32)
                              "members": [{"name": "fable", "via": "adapter", "effort": "xhigh"},
                                          {"name": "opus", "via": "adapter", "effort": "max"},
                                          {"name": "astra", "via": "runner", "effort": "xhigh"}]}}
INIT_STEP, DOCTOR_CHECKS = "", None
SKILLS = frozenset(["judges"])  # the skills whose card this subcommand accepts
PARENT_SKILLS = ("review-spec", "review-plan", "plan", "wave", "integrate")
QUESTION_SKILLS = frozenset(["review-spec", "review-plan", "plan", "wave"])  # the cards `judges question` accepts
CAP_OPTIONS = {"head": ["one more round", "stop"], "other": ["continue one bounded round", "accept the remainder", "stop"]}
RELAUNCH = ["relaunch", "stop the unit"]
CAP = 5  # rounds per panel
ISOLATION_RE = re.compile(r"^(clean|exposed:.+)$")

QUESTION_RE = re.compile(r"^## Q(\d+) (.+)$")
OPTION_RE = re.compile(r"^- \(([a-z])\) (.+)$")
ANSWER_RE = re.compile(r"^Q(\d+): \(([a-z])\)\s*$")
SAW_RE = re.compile(r"^saw:\s*(.*)$")  # the judge's isolation report, first or last line of the reply
NOTE_KEYS = {"reason": "reason", "would change my mind": "would_change"}
VENDOR_OF = {"adapter": "anthropic", "runner": "openai"}


def parse_questions(text: str) -> list[dict]:
  """`## Q<n> <question>` then two or more `- (<id>) <option>` lines, in file order."""
  questions, seen = [], set()
  for n, line in enumerate(text.splitlines(), start=1):
    if not line.strip():
      continue
    if match := QUESTION_RE.match(line):
      qid = f"Q{match.group(1)}"
      if qid in seen:
        raise ValueError(f"duplicate question {qid}")
      seen.add(qid)
      questions.append({"id": qid, "text": match.group(2).strip(), "options": {}})
    elif match := OPTION_RE.match(line):
      if not questions:
        raise ValueError(f"line {n}: option before any question")
      oid, options = match.group(1), questions[-1]["options"]
      if oid in options:
        raise ValueError(f"{questions[-1]['id']}: duplicate option ({oid})")
      options[oid] = match.group(2).strip()
    else:
      raise ValueError(f"line {n}: expected `## Q<n> <question>` or `- (<id>) <option>`")
  if not questions:
    raise ValueError("no questions")
  for question in questions:
    if len(question["options"]) < 2:
      raise ValueError(f"{question['id']}: fewer than two options")
  return questions


def parse_verdict(text: str, questions: list[dict]) -> dict[str, dict]:
  """`Q<n>: (<id>)` lines, each with optional `reason:` and `would change my mind:`
  lines; a verdict may answer a subset (coverage is `record`'s check)."""
  options = {q["id"]: q["options"] for q in questions}
  answers = {}
  last = None
  for n, line in enumerate(text.splitlines(), start=1):
    if not line.strip() or SAW_RE.match(line):
      continue
    if match := ANSWER_RE.match(line):
      qid, oid = f"Q{match.group(1)}", match.group(2)
      if qid not in options:
        raise ValueError(f"unknown question {qid}")
      if oid not in options[qid]:
        raise ValueError(f"{qid}: unknown option ({oid})")
      if qid in answers:
        raise ValueError(f"duplicate answer {qid}")
      last = answers[qid] = {"option": oid, "reason": None, "would_change": None}
      continue
    key, sep, value = line.partition(":")
    if sep and key.strip().lower() in NOTE_KEYS and last is not None:
      last[NOTE_KEYS[key.strip().lower()]] = value.strip()
    else:
      raise ValueError(f"line {n}: expected `Q<n>: (<id>)`")
  return answers


def judge_members(config: dict) -> dict[str, dict]:
  """`config.judges.members` as `{id: {via, vendor, model, effort}}`; a list of
  dicts (keyed `id`, or `name` as `init` writes it) or of ids is normalised."""
  judges_cfg = config.get("judges") or {}
  astra = config.get("astra") or {}
  members = judges_cfg.get("members") or core.DEFAULT_CONFIG["judges"]["members"]
  if isinstance(members, list):
    members = {(m if isinstance(m, str) else m.get("id") or m.get("name")): ({} if isinstance(m, str) else m)
               for m in members}
  out = {}
  for jid, spec in members.items():
    via = spec.get("via", "runner" if jid == "astra" else "adapter")
    runner = via == "runner"
    out[jid] = {"via": via, "vendor": VENDOR_OF[via],
                "model": spec.get("model") or (astra.get("model", "gpt-6-astra") if runner else jid),
                "effort": spec.get("effort") or (astra.get("effort", "xhigh") if runner else "max")}
  return out


def register(subparsers):
  p = core.add_parser(subparsers, "judges", "the judge panel: open, record, diff, verdict", runcard=False)
  action = p.add_subparsers(dest="action", required=True)
  o = action.add_parser("open", help="open a panel on a question file and print its id")
  o.add_argument("--question", required=True, help="the question file (`## Q<n>` and `- (<id>)` lines)")
  o.add_argument("--evidence", action="append", default=[], help="a file the judges may read; repeatable")
  card = o.add_mutually_exclusive_group(required=True)
  card.add_argument("--runcard", help="the open judges card on the question file")
  card.add_argument("--parent", help="the open review-spec, review-plan, plan, wave or integrate card to open a child card under")
  r = action.add_parser("record", help="record one judge's verdict, Astra result or not-run reason for a round")
  r.add_argument("--panel", required=True)
  r.add_argument("--round", required=True, type=int)
  r.add_argument("--judge", required=True)
  form = r.add_mutually_exclusive_group(required=True)
  form.add_argument("--verdict", help="a Claude judge's reply in the verdict-file grammar")
  form.add_argument("--result", help="the Astra lane's result.json")
  form.add_argument("--not-run", dest="not_run", help="the reason the judge did not run")
  r.add_argument("--isolation", help="clean | exposed:<what>, from the judge's `saw:` line (with --verdict)")
  r.add_argument("--model", help="<requested>:<effective>; default the configured model twice")
  r.add_argument("--effort", help="<requested>:<effective>; default the configured effort twice")
  r.add_argument("--runcard", required=True, help="the panel's judges card, or its parent")
  d = action.add_parser("diff", help="write the neutral list of where a round's positions differ and the next brief")
  d.add_argument("--panel", required=True)
  d.add_argument("--round", required=True, type=int)
  d.add_argument("--runcard", required=True, help="the panel's judges card, or its parent")
  v = action.add_parser("verdict", help="compute per-question convergence, write verdict.json and print it")
  v.add_argument("--panel", required=True)
  v.add_argument("--runcard", required=True, help="the panel's judges card, or its parent")
  q = action.add_parser("question", help="render a section 13.2 question file from the record and print its path")
  q.add_argument("--review", help="the review id (with --round or --cap)")
  q.add_argument("--round", type=int, help="the round whose findings are questioned")
  q.add_argument("--reason", action="append", default=[], metavar="FID=TEXT", help="a contested or declined finding and the overrule text")
  q.add_argument("--cap", action="store_true", help="the review is at its cap")
  q.add_argument("--unit", help="the unit (with --decision or --blocked)")
  q.add_argument("--decision", help="a `blocking: yes` item, D<n>")
  q.add_argument("--blocked", nargs="+", metavar="WHAT", help="<comment-id> | launch <n> | closed <n>")
  q.add_argument("--runcard", help="the open review-spec, review-plan, plan or wave card")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  st = core.store(core.git_toplevel(Path.cwd()))
  return COMMANDS[args.action](args, st)


def require_card(args, artifact: str) -> dict:
  # U03's require_runcard reads the subcommand's artifact from args.design; a judges card's is the question file.
  args.design = artifact
  return core.require_runcard(args, SKILLS)


def load_panel(store, pid: str) -> dict:
  path = store.path("judges", pid, "panel.json")
  if not path.is_file():
    raise core.HandoffError(f"judges: panel {pid} not found")
  return json.loads(core.read_text(path))


def panel_card(args, store, panel: dict) -> dict:
  """The panel's card: `--runcard` may name the child or its parent; U03 accepts
  the child while the parent is open or interrupted."""
  if args.runcard == panel["parent"]:
    args.runcard = panel["runcard"]
  return require_card(args, panel["question"])


def write_json(path: Path, obj) -> None:
  # atomic_write sorts keys; the panel's judge order is the config's, so serialise first
  core.atomic_write(path, json.dumps(obj, indent=2) + "\n")


def panel_id(question: Path) -> str:
  return f"{question.stem}-{core.sha256_file(question)[:6]}"


def render_brief(panel: dict, questions: list[dict], round_no: int, open_ids: list[str],
                 prior: list[tuple[int, str, str]], diffs: list[str], lane: str = "local") -> str:
  lines = [f"JUDGE BRIEF, panel {panel['id']}, round {round_no}.",
           "You are one judge of a panel. Answer each question below by option id, one line per question:",
           "`Q<n>: (<id>)`",
           "After an answer you may add one `reason: <sentence>` line and one `would change my mind: <what>` line.",
           "Close with one line `saw: <none | CLAUDE.md | memory index | hook output | ...>` naming anything",
           "that reached you besides this brief, the question file and the evidence.",
           "Report no findings. Read only the question file and the evidence listed.",
           f"Question file: {panel['question']} (sha256 {panel['question_sha256']})",
           "Evidence: " + (", ".join(e["path"] for e in panel["evidence"]) or "none")]
  if lane == "astra":  # the Astra lane reads no paths: each evidence file's contents follow, re-checked against the sha256 recorded at open
    for item in panel["evidence"]:
      path = Path(item["path"])
      if not path.is_file() or core.sha256_file(path) != item["sha256"]:
        raise core.HandoffError(f"judges: evidence {item['path']} changed since open")
      body = core.read_text(path).rstrip("\n")
      fence = "`" * max(3, 1 + max((len(run) for run in re.findall(r"`+", body)), default=0))  # one longer than the file's longest run
      lines += ["", f"### Evidence: {item['path']}", fence, body, fence]
  if round_no > 1:
    lines += ["", f"Questions still open: {', '.join(open_ids)}",
              "Answer only those. Every prior verdict and every diff follow verbatim; no one adds arguments between rounds:",
              "weigh them and change position only for a reason you can name."]
    for rnd, judge, text in prior:
      lines += ["", f"### Round {rnd}, {judge}", text.rstrip("\n")]
    for diff in diffs:
      lines += ["", diff.rstrip("\n")]
  section = (panel.get("instructions") or {}).get(lane, {}).get("text", "")
  return "\n".join(lines) + "\n" + (f"\n{section}" if section else "")  # the lane's stored section, last in every round's brief


def write_briefs(folder: Path, round_no: int, panel: dict, *args) -> None:
  """`round-<n>/brief.md` for the local members (the index) and `brief-astra.md` for the Astra member, which cannot read
  the store (the pastes): the same brief, each with its own lane's stored section."""
  for name, text in render_briefs(panel, *args).items():
    core.atomic_write(folder / f"round-{round_no}" / name, text)


def render_briefs(panel: dict, *args) -> dict:
  """Both lanes' briefs by file name, rendered before either is written: a refusal (a changed evidence file) leaves no brief."""
  return {name: render_brief(panel, *args, lane=lane) for name, lane in (("brief.md", "local"), ("brief-astra.md", "astra"))}


def render_panel(store, parent: dict | None) -> dict:
  """The panel's `instructions`: `{lane: {manifest, text}}` for `local` and `astra`, the `judges` section rendered once, by
  the parent card's skill: a `review-spec` parent renders its artifact as the spec at `HEAD` (its card can carry a legacy
  store's handoff id, which is not the spec's); any other parent its card's handoff's frozen list; no parent, or a parent
  with no handoff, nothing."""
  def lane_render(lane: str) -> dict:
    if parent is None:
      manifest, text = [], ""
    elif parent["skill"] == "review-spec":
      manifest, text = instructions.render(store, "judges", root=core.git_toplevel(Path(parent["artifact"])), lane=lane)
    else:
      handoff = parent.get("handoff", store.handoff_id)
      manifest, text = instructions.render(store, "judges", handoff_id=handoff, lane=lane) if handoff else ([], "")
    return {"manifest": manifest, "text": text}
  return {lane: lane_render(lane) for lane in ("local", "astra")}  # the Astra member's pastes, the local members' index


def lane_manifest(panel: dict, judge: str) -> list:
  """The manifest stored on the panel for `judge`'s lane (`astra` for the runner member); `[]` for a panel opened before U38."""
  lane = "astra" if panel["judges"][judge]["via"] == "runner" else "local"
  return ((panel.get("instructions") or {}).get(lane) or {}).get("manifest", [])


def cmd_open(args, store) -> int:
  question = Path(args.question).expanduser().resolve()
  parent = None
  if args.runcard:
    require_card(args, str(question))
  else:
    parent = core.load_card(store, args.parent)
    if parent["skill"] not in PARENT_SKILLS:
      raise core.HandoffError("runcard: parent must be a review-spec, review-plan, plan, wave or integrate card")
    if parent["closed_at"]:
      raise core.HandoffError(f"runcard: parent {args.parent} is closed")
  if not question.is_file():
    raise core.HandoffError(f"judges: question file {question} does not exist")
  try:
    questions = parse_questions(core.read_text(question))
  except ValueError as error:
    raise core.HandoffError(f"judges: question file: {error}")
  evidence = []
  for item in args.evidence:
    path = Path(item).expanduser().resolve()
    if not path.is_file():
      raise core.HandoffError(f"judges: evidence {path} does not exist")
    evidence.append({"path": str(path), "sha256": core.sha256_file(path)})
  pid = panel_id(question)
  folder = store.path("judges", pid)
  if folder.exists():
    raise core.HandoffError(f"judges: panel {pid} exists")
  config = store.config or {}
  members = judge_members(config)
  min_vendors = (config.get("judges") or {}).get("min_vendors", 1)
  rendered = render_panel(store, parent)  # before the card opens: a refused render leaves no open judges card
  rid = args.runcard or core.open_runcard(store, "judges", str(question), parent=args.parent)
  panel = {"id": pid, "question": str(question), "question_sha256": core.sha256_file(question),
           "evidence": evidence, "judges": members, "min_vendors": min_vendors, "runcard": rid,
           "parent": args.parent, "opened_at": core.now_iso(), "rounds": {},
           "instructions": rendered}
  core.atomic_write(folder / "question.md", question.read_bytes())
  write_json(folder / "panel.json", panel)
  write_briefs(folder, 1, panel, questions, 1, [q["id"] for q in questions], [], [])
  core.journal(store, f"judges {pid}: opened ({', '.join(members)}; min_vendors {min_vendors})")
  print(pid)
  return 0


def compute_verdict(panel: dict, questions: list[dict]) -> dict:
  """Per-question convergence over the recorded rounds in order: a question
  converges in the first round where every answering judge chose one option
  and those judges span `min_vendors` vendors; `degraded` when any round had
  fewer than two answering vendors."""
  members, min_vendors = panel["judges"], panel["min_vendors"]
  result = {q["id"]: {"converged": False, "option": None, "round": None, "positions": {}, "vendors": [],
                      "reason": None} for q in questions}
  open_ids = [q["id"] for q in questions]
  degraded = False
  rounds = sorted(panel["rounds"], key=int)
  for key in rounds:
    entries = panel["rounds"][key]
    answered = [j for j in members if "options" in entries.get(j, {})]
    if len({members[j]["vendor"] for j in answered}) < 2:
      degraded = True
    for qid in list(open_ids):
      positions = {}
      for judge in answered:
        option = entries[judge]["options"].get(qid)
        if option:
          positions.setdefault(option, []).append(judge)
      if not positions:
        continue
      vendors = sorted({members[j]["vendor"] for judges in positions.values() for j in judges})
      question = result[qid]
      question.update(positions={k: positions[k] for k in sorted(positions)}, vendors=vendors, reason=None)
      if len(positions) > 1:
        continue
      if len(vendors) < min_vendors:
        question["reason"] = f"vendors {len(vendors)} < min_vendors {min_vendors}"
        continue
      question.update(converged=True, option=next(iter(positions)), round=int(key))
      open_ids.remove(qid)
  return {"questions": result, "open": open_ids, "converged": not open_ids, "degraded": degraded,
          "cap_reached": bool(open_ids) and len(rounds) >= CAP}


def open_questions(panel: dict, questions: list[dict], before_round: int) -> list[str]:
  """The ids not converged by the rounds before `before_round`."""
  earlier = {**panel, "rounds": {k: v for k, v in panel["rounds"].items() if int(k) < before_round}}
  return compute_verdict(earlier, questions)["open"]


def astra_answers(record: dict) -> tuple[str | None, str]:
  """The Astra lane's `result.json` as `(summary, "")`, else `(None, reason)`
  (the claudex-loop runner's record; a changed field is a reason, never an answer)."""
  response = record.get("response") or {}
  if record.get("status") == "failed":
    return None, str(record.get("error") or "failed")
  if record.get("status") != "completed":
    return None, "killed"
  if response.get("verdict") == "BLOCKED":
    return None, f"blocked: {response.get('limitations') or 'no limitations given'}"
  summary = response.get("summary")
  if not isinstance(summary, str) or not summary.strip():
    return None, "no summary in the result"
  return summary, ""


def cmd_record(args, store) -> int:
  panel = load_panel(store, args.panel)
  panel_card(args, store, panel)
  pid, n, judge = panel["id"], args.round, args.judge
  if judge not in panel["judges"]:
    raise core.HandoffError(f"judges: unknown judge {judge}")
  if n > CAP:
    raise core.HandoffError(f"judges: cap of {CAP} rounds reached")
  if n < 1:
    raise core.HandoffError(f"judges: round must be 1..{CAP}")
  folder = store.path("judges", pid)
  if n >= 2 and not (folder / f"round-{n - 1}" / "diff.md").is_file():
    raise core.HandoffError(f"judges: round {n - 1} not diffed")
  rounds = panel["rounds"].setdefault(str(n), {})
  if judge in rounds:
    raise core.HandoffError(f"judges: round {n}: {judge} already recorded")
  questions = parse_questions(core.read_text(folder / "question.md"))
  member = panel["judges"][judge]
  reason, text, saw = None, None, None
  if args.verdict:
    if not args.isolation:
      raise core.HandoffError("judges: --isolation required with --verdict")
    if not ISOLATION_RE.match(args.isolation):
      raise core.HandoffError("judges: isolation must be clean or exposed:<what>")
    path = Path(args.verdict).expanduser()
    if not path.is_file():
      raise core.HandoffError(f"judges: verdict file {path} does not exist")
    text = core.read_text(path)
    saw = next((m.group(1).strip() for line in text.splitlines() if (m := SAW_RE.match(line))), None)
    try:
      answers = parse_verdict(text, questions)
      missing = [q for q in open_questions(panel, questions, n) if q not in answers]
      if missing:
        raise ValueError(f"no answer for {missing[0]}")
    except ValueError as error:
      raise core.HandoffError(f"judges: verdict file: {error}")
    isolation = args.isolation
    model = args.model or f"{member['model']}:{member['model']}"
    effort = args.effort or f"{member['effort']}:{member['effort']}"
  elif args.result:
    path = Path(args.result).expanduser()
    if not path.is_file():
      raise core.HandoffError(f"judges: result {path} does not exist")
    record = json.loads(core.read_text(path))
    text, reason = astra_answers(record)
    if text is not None:
      try:
        answers = parse_verdict(text, questions)
        missing = [q for q in open_questions(panel, questions, n) if q not in answers]
        if missing:
          raise ValueError(f"no answer for {missing[0]}")
      except ValueError as error:
        text, reason = None, str(error)
    isolation = "runner"
    model = f"{member['model']}:{record.get('effective_model') or 'requested only'}"
    effort = f"{member['effort']}:{record.get('effective_effort') or 'requested only'}"
  else:
    reason = args.not_run
  if reason:
    rounds[judge] = {"not_run": reason, "recorded_at": core.now_iso(), "instructions": lane_manifest(panel, judge)}
    core.journal(store, f"judges {pid}: round {n} {judge} not run ({reason})")
    print(f"not run ({reason})")
  else:
    core.atomic_write(folder / f"round-{n}" / f"{judge}.md", text)
    rounds[judge] = {"isolation": isolation, "model": model, "effort": effort,
                     "options": {q: a["option"] for q, a in answers.items()}, "recorded_at": core.now_iso(),
                     "instructions": lane_manifest(panel, judge)}
    if args.verdict:
      rounds[judge]["saw"] = saw
    core.journal(store, f"judges {pid}: round {n} {judge} recorded ({isolation})")
    print("recorded")
  write_json(folder / "panel.json", panel)
  return 0


def neutral_diff(pid: str, round_no: int, questions: list[dict], entries: dict[str, dict],
                 open_ids: list[str]) -> str:
  """Option ids and judge ids only: per open question, who chose what."""
  lines = [f"# Panel {pid}, round {round_no}: where positions differ"]
  for qid in open_ids:
    positions = {}
    for judge, entry in entries.items():
      option = entry.get("options", {}).get(qid)
      if option:
        positions.setdefault(option, []).append(judge)
    if len(positions) == 1:
      lines.append(f"## {qid}: converged on ({next(iter(positions))})")
      continue
    lines.append(f"## {qid}")
    lines += [f"- ({option}): {', '.join(positions[option])}" for option in sorted(positions)]
  lines += [f"Not run: {judge} ({entry['not_run']})" for judge, entry in entries.items() if "not_run" in entry]
  return "\n".join(lines) + "\n"


def cmd_diff(args, store) -> int:
  panel = load_panel(store, args.panel)
  panel_card(args, store, panel)
  pid, n = panel["id"], args.round
  if not 1 <= n <= CAP:
    raise core.HandoffError(f"judges: round must be 1..{CAP}")
  entries = panel["rounds"].get(str(n), {})
  for judge in panel["judges"]:
    if judge not in entries:
      raise core.HandoffError(f"judges: round {n}: {judge} not recorded")
  folder = store.path("judges", pid)
  questions = parse_questions(core.read_text(folder / "question.md"))
  diff = neutral_diff(pid, n, questions, entries, open_questions(panel, questions, n))
  still_open = open_questions(panel, questions, n + 1)
  briefs = {}
  if still_open and n < CAP:  # everything that can refuse comes before the first write: a refusal leaves the round untouched
    prior = [(k, judge, core.read_text(folder / f"round-{k}" / f"{judge}.md"))
             for k in range(1, n + 1) for judge in panel["judges"]
             if "options" in panel["rounds"][str(k)].get(judge, {})]
    diffs = [core.read_text(folder / f"round-{k}" / "diff.md") for k in range(1, n)] + [diff]
    briefs = render_briefs(panel, questions, n + 1, still_open, prior, diffs)
  core.atomic_write(folder / f"round-{n}" / "diff.md", diff)
  for name, text in briefs.items():
    core.atomic_write(folder / f"round-{n + 1}" / name, text)
  core.journal(store, f"judges {pid}: round {n} diff written, open {', '.join(still_open) or 'none'}")
  print(folder / f"round-{n}" / "diff.md")
  return 0


def verdict_line(pid: str, verdict: dict, questions: list[dict]) -> str:
  """The one line an unconverged panel adds to the owner's point 1 question: `judges/<panel>/verdict.json` and, for each
  open question, each judge's last recorded choice, from whichever round it made it, as its option's text (a judge
  that never answered the question reads `no answer`)."""
  options = {q["id"]: q["options"] for q in questions}
  parts = []
  for qid in verdict["open"]:
    last = {}
    for key in sorted(verdict["rounds"], key=int):
      for judge, entry in verdict["rounds"][key].items():
        if entry.get("options", {}).get(qid):
          last[judge] = entry["options"][qid]
    choices = [(judge, options[qid][last[judge]] if judge in last else "no answer") for judge in sorted(verdict["judges"])]
    parts.append(f"{qid} " + "; ".join(f"{judge}: {text}" for judge, text in choices))
  return f"The judges did not converge (judges/{pid}/verdict.json), their last choices: " + " | ".join(parts) + "\n"


def add_to_open_decisions(store, pid: str, question_text: str, line: str) -> None:
  """Append the verdict line, once, to the `question` of each point 1 decision of this panel's review and round (its `source` is
  `review <rid> round <n>`, the panel id being `<rid>-r<n>-<6 hex>`) that still has an unruled finding the panel asks: that record
  is what `inbox` lists and the ruling comment quotes (section 7.8), `owner-question.md` being only a copy. A finding id recurs
  in every unit and cycle, so the id alone never picks a decision; one a `redesign` or a `proceed` closed, or whose asked
  findings all have a ruling, is left as it was."""
  from superegm.decision import FINDING_LINE_RE
  m = re.fullmatch(r"(.+)-r(\d+)-[0-9a-f]{6}", pid)
  if not store.handoff_id or not m:  # a panel outside a wave (a spec review's) has no foreman files
    return
  source = f"review {m.group(1)} round {m.group(2)}"
  fids = lambda text: {a or b for a, b in FINDING_LINE_RE.findall(text or "")}
  asked = fids(question_text)
  for path in sorted(store.path("foreman", "x").parent.glob("*.json")):
    data = json.loads(core.read_text(path))
    changed = False
    for decision in data.get("decisions", []):
      named = {str(r.get("ruling") or "").split(" ")[0] for r in data.get("rulings", []) if r.get("decision") == decision.get("id")}
      unruled = not named & {"redesign", "proceed"} and any(f not in named for f in fids(decision.get("question")) & asked)
      if decision.get("point") == 1 and decision.get("source") == source and unruled and f"judges/{pid}/verdict.json" not in decision["question"]:
        decision["question"] = decision["question"].rstrip("\n") + "\n" + line
        changed = True
    if changed:
      core.save_foreman(store, path.stem, data)


def cmd_verdict(args, store) -> int:
  panel = load_panel(store, args.panel)
  panel_card(args, store, panel)
  pid = panel["id"]
  if not panel["rounds"]:
    raise core.HandoffError("judges: no round recorded")
  latest = max(panel["rounds"], key=int)
  for judge in panel["judges"]:
    if judge not in panel["rounds"][latest]:
      raise core.HandoffError(f"judges: round {latest}: {judge} not recorded")
  folder = store.path("judges", pid)
  questions = parse_questions(core.read_text(folder / "question.md"))
  path = folder / "verdict.json"
  previous = json.loads(core.read_text(path))["questions"] if path.is_file() else {}
  verdict = {"panel": pid, "question_sha256": panel["question_sha256"], "runcard": panel["runcard"],
             "min_vendors": panel["min_vendors"], "judges": panel["judges"], "rounds": panel["rounds"],
             "computed_at": core.now_iso(), **compute_verdict(panel, questions)}
  write_json(path, verdict)
  for qid, question in verdict["questions"].items():
    if question["converged"] and not previous.get(qid, {}).get("converged"):
      core.journal(store, f"judges {pid}: {qid} converged ({question['option']}) round {question['round']}")
  line = "verdict converged" if verdict["converged"] else f"verdict not converged: {', '.join(verdict['open'])}"
  line += " (cap reached)" if verdict["cap_reached"] else ""
  line += " (degraded)" if verdict["degraded"] else ""
  core.journal(store, f"judges {pid}: {line}")
  if verdict["cap_reached"] and not verdict["converged"]:  # section 7.8: the owner keeps the question, with the verdict line
    line = verdict_line(pid, verdict, questions)
    core.atomic_write(folder / "owner-question.md", core.read_text(folder / "question.md") + line)
    add_to_open_decisions(store, pid, core.read_text(folder / "question.md"), line)
  print(json.dumps(verdict, indent=2))
  return 0 if verdict["converged"] else 2


# ---------------------------------------------------------------- question: section 13.2's points 1-3 rendered


def question(args, st) -> int:
  from superegm import review as reviews
  if args.review:  # the card rule reads the review's artifact from args, as review.py's `bind` does
    found = reviews.load_review(st, args.review)
    if found is None:
      raise core.HandoffError(f"question: review {args.review} not opened")
    if found["kind"] in ("spec", "integrate"):
      args.design = found["artifact"]
    else:
      args.unit = found["artifact"]
  card = core.require_runcard(args, QUESTION_SKILLS)
  text, consumers = render(st, args, card.get("mode"))
  path = st.path("questions", question_name(args))
  core.atomic_write(path, text)
  core.journal(st, f"question rendered: {path}")
  print(path)
  if consumers:
    print("consumers: " + " ".join(f"#{n}" for n in consumers))
  return 0


def question_name(args) -> str:
  if args.review:
    return f"{args.review}-cap.md" if args.cap else f"{args.review}-r{args.round}.md"
  if args.decision:
    return f"{args.unit}-{args.decision}.md"
  return f"{args.unit}-blocked-{'-'.join(args.blocked)}.md"


def render(st, args, mode=None) -> tuple[str, list[int]]:
  """The question text of one section 13.2 point and, for an `interface` deviation, the consumers to post on."""
  if args.review and args.cap:
    return cap_question(st, args.review), []
  if args.review and args.round:
    return round_questions(st, args.review, args.round, args.reason), []
  if args.unit and args.decision:
    return decision_question(st, args.unit, args.decision), []
  if args.unit and args.blocked:
    return blocked_question(st, args.unit, args.blocked, mode)
  raise core.HandoffError("question: --review <id> (--round <n> | --cap) or --unit <U> (--decision D<n> | --blocked ...)")


def options_text(options: list) -> str:
  return "".join(f"- ({chr(ord('a') + i)}) {option}\n" for i, option in enumerate(options))


def round_questions(st, rid: str, n: int, reasons: list) -> str:
  from superegm import review as reviews
  rnd = reviews.load_round(st, rid, n)
  if rnd is None:
    raise core.HandoffError(f"question: {rid} has no round {n}")
  findings = {f["id"]: f for record in rnd["reviewers"].values() for f in record["findings"]}
  asked = []
  for item in reasons:
    fid, sep, text = item.partition("=")
    if not sep:
      raise core.HandoffError(f"question: --reason takes <fid>=<text>, got {item}")
    asked.append((fid, text))
  asked += [(entry["fid"], entry["reason"]) for entry in rnd.get("builder_contested") or []]
  head = (reviews.load_review(st, rid) or {}).get("kind") == "head"
  lines = []
  for k, (fid, text) in enumerate(asked, start=1):
    if fid not in findings:
      raise core.HandoffError(f"question: {fid} is not in round {n}")
    finding = findings[fid]
    if finding["location"] == "ci" or finding["claim"].startswith("CI not green"):  # section 8: settled by no one
      raise core.HandoffError(f"question: {fid} is the CI finding")
    if finding["severity"] == "low":
      raise core.HandoffError(f"question: {fid} is low")
    lines.append(f"## Q{k} {fid} ({finding['severity']}, {finding['location']}): {finding['claim']}\n"
                 + options_text(["finding upheld", f"finding overruled — {text}"]
                                + ([f"redesign — {finding['claim']}"] if head else [])))
  if not lines:
    raise core.HandoffError(f"question: nothing to ask in round {n} of {rid}")
  return "".join(lines)


def cap_question(st, rid: str) -> str:
  from superegm import review as reviews
  review = reviews.load_review(st, rid)
  head = review["kind"] == "head"
  options = list(CAP_OPTIONS["head" if head else "other"])
  continued = any(r["ruling"] == "continue" for r in review["rulings"])  # section 5: continue is ruled at most once
  if reviews.evaluate(st, review, None).moved:  # accept is refused on bytes nobody reviewed (a head never moves)
    options.remove("accept the remainder")
    if continued:
      raise core.HandoffError("question: one option: stop")
  if continued:
    options.pop(0)
  if head:
    options.append(redesign_option(st, rid))
  return f"## Q1 {rid} is at its cap{scope_suffix(st, rid, review)}\n" + options_text(options)


def scope_suffix(st, rid: str, review: dict) -> str:
  """On kind `spec`, ` (scope: <the latest round's headings in document order, or whole>)`; empty elsewhere
  and before any round stored a scope."""
  from superegm import review as reviews
  if review["kind"] != "spec":
    return ""
  stored = [rnd["scope"] for n in reviews.round_numbers(st, rid) if "scope" in (rnd := reviews.load_round(st, rid, n))]
  if not stored:
    return ""
  rows = sorted(stored[-1], key=lambda row: row[2])
  return " (scope: " + ("whole" if any(row[0] == "whole" for row in rows) else ", ".join(row[1] for row in rows)) + ")"


def redesign_option(st, rid: str) -> str:
  """`redesign — the head is at its cap after <n> rounds`, then `: <claims>` of the latest round's unsettled
  high and medium findings; the CI finding is settled by no one, so it is never part of the sentence."""
  from superegm import review as reviews
  numbers = reviews.round_numbers(st, rid)
  latest = reviews.load_round(st, rid, numbers[-1]) if numbers else None
  claims = [f["claim"] for f in reviews.findings_of(latest) if reviews.blocking(f) and f["disposition"] is None
            and f["location"] != "ci" and not f["claim"].startswith("CI not green")] if latest else []
  return f"redesign — the head is at its cap after {len(numbers)} rounds" + (": " + "; ".join(claims) if claims else "")


STORED_LETTER_RE = re.compile(r"^\([a-z]\) ")  # a stored option's own letter prefix


def decision_question(st, unit: str, did: str) -> str:
  """A plan-time `D<n>` with its options as stored, `respec` (the owner's alone, §7.6) left out and `amend` kept (a
  plan-time decision's options come from the plan, `tests/unit/test_u96.py` pins `amend` there); a runtime `q<n>` is
  refused (`--blocked` renders it through `stored_options_text`, `amend` and `respec` left out)."""
  if re.fullmatch(r"q\d+", did):
    raise core.HandoffError(f"question: {did} is a runtime decision: use --blocked <comment-id> | launch <n> | closed <n>")
  units = json.loads(core.read_text(st.path("units"))).get("units") or {}
  decision = next((d for d in units.get(unit, {}).get("decisions") or [] if d["id"] == did), None)
  if decision is None:
    raise core.HandoffError(f"question: {unit} has no decision {did}")
  return f"## Q1 {unit} {did}: {decision['question']}\n" + "".join(f"- {o}\n" for o in decision["options"] if STORED_LETTER_RE.sub("", o) != "respec")


def stored_options_text(options: list) -> str:
  """A pending decision's stored options with `amend` (the owner's alone, §6.5) and `respec` (the owner's alone,
  §7.6) left out and the others keeping the letter of their stored position; a stored `(x) ` prefix is dropped so a
  letter prints once."""
  return "".join(f"- ({chr(ord('a') + i)}) {STORED_LETTER_RE.sub('', option)}\n"
                 for i, option in enumerate(options) if STORED_LETTER_RE.sub("", option) not in ("amend", "respec"))


def blocked_question(st, unit: str, what: list, mode=None) -> tuple[str, list[int]]:
  """The question for a blocked comment, launch or close. In leavemealone-mode (`mode`) a `spec` deviation's question
  waits for the owner (§7.6): the judges are given none, since `respec` is the owner's alone."""
  from superegm.launch import load_launches
  if len(what) == 1 and what[0].isdigit():
    body = (core.gh_json(["api", f"repos/{st.config['repo']}/issues/comments/{what[0]}"]) or {}).get("body") or ""
    heading = (body.splitlines() or [""])[0]
    from superegm.decision import comment_options
    from superegm.report import pending_decisions
    pending = next((d for d in pending_decisions(core.load_foreman(st, unit))
                    if d.get("point") == 3 and d.get("source") == f"comment {what[0]}"), None)
    held = pending.get("options") or RELAUNCH if pending is not None else comment_options(body)  # the decision's frozen options, else the comment's
    if mode == "leavemealone" and "respec" in (STORED_LETTER_RE.sub("", o) for o in held):
      raise core.HandoffError(f"question: comment {what[0]} is a spec deviation: in leavemealone-mode it waits for the owner (respec is the owner's alone)")
    plain = [STORED_LETTER_RE.sub("", o) for o in held]
    if pending is None and "respec" not in plain:  # a comment with nothing decided and no `respec`: `amend` left out, the rest lettered afresh as before
      shown = options_text([o for o in plain if o != "amend"])
    else:  # `amend` and `respec` left out, every other option keeping its letter (a later `respec` decision stores these letters)
      shown = stored_options_text(held)
    consumers = []
    if heading.startswith("**Deviation (interface):**"):
      from superegm.decision import INTERFACE
      named = INTERFACE.match(heading[len("**Deviation (interface):**"):].strip())
      consumers = fan_out(st, named["unit"] if named else unit, unit)  # the named producer's; the raising unit's for an old-form heading
    return f"## Q1 {unit} BLOCKED (comment {what[0]}): {heading.strip()}\n" + shown, consumers
  if len(what) == 2 and what[0] == "launch" and what[1].isdigit():
    launches = load_launches(st, unit)
    n = int(what[1])
    if not 1 <= n <= len(launches):
      raise core.HandoffError(f"question: {unit} has no launch {n}")
    entry = launches[n - 1]
    if entry["status"] == "exited (stalled)":  # the stall facts (U31)
      heading = f"{unit} launch {n} stalled (last commit {entry.get('last_commit_at') or 'none'})"
    else:
      heading = f"{unit} launch {n} ({entry['status']}) ended with no pull request"
  elif len(what) == 2 and what[0] == "closed" and what[1].isdigit():
    heading = f"{unit}: #{what[1]} was closed by the builder account"
  else:
    raise core.HandoffError("question: --blocked takes <comment-id> | launch <n> | closed <n>")
  # the options are the pending point-3 decision's, `decision open` having applied the carve-out (U31)
  from superegm.report import pending_decisions
  source = " ".join(what)
  pending = next((d for d in pending_decisions(core.load_foreman(st, unit)) if d.get("point") == 3 and d.get("source") == source), None)
  if pending is None:
    raise core.HandoffError(f"question: {unit} has no pending decision on {source}")
  return f"## Q1 {heading}\n" + options_text(pending.get("options") or RELAUNCH), []


def fan_out(st, producer: str, raising: str) -> list[int]:
  """The issue numbers of every filed unit whose unit file consumes a name of `producer`, the raising unit left out
  (section 13.2, spec section 6.5: keyed on the producer the heading names; an old-form heading passes the raising unit
  as both)."""
  # shortcut: the fan-out targets every filed consumer of any name the producer produces, since the deviation text is
  # free prose; narrow it when the Deviation comment gains a name field
  numbers = []
  for other, record in (core.load_state(st.root).get("units") or {}).items():
    path = st.path("unit", other)
    if other != raising and record.get("number") and path.is_file() \
        and any(made == producer for _, made in core.body.consumes(core.read_text(path))):
      numbers.append(record["number"])
  return sorted(numbers)


COMMANDS = {"open": cmd_open, "record": cmd_record, "diff": cmd_diff, "verdict": cmd_verdict, "question": question}
