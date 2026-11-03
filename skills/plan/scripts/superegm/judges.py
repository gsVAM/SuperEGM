# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the judges subcommand (spec section 13.1).

"""superegm judges open|record|diff|verdict: the judge panel over a question file."""

import json
import re
from pathlib import Path

import superegm as core

WRITES = frozenset(["judges", "runcards"])  # the store kinds this subcommand writes
SKILLS = frozenset(["judges"])  # the skills whose card this subcommand accepts
PARENT_SKILLS = ("review-spec", "review-plan", "plan", "wave", "integrate")
CAP = 5  # rounds per panel

QUESTION_RE = re.compile(r"^## Q(\d+) (.+)$")
OPTION_RE = re.compile(r"^- \(([a-z])\) (.+)$")
ANSWER_RE = re.compile(r"^Q(\d+): \(([a-z])\)\s*$")
NOTE_KEYS = {"reason": "reason", "would change my mind": "would_change"}
DEFAULT_MEMBERS = {"fable": {"via": "adapter"}, "opus": {"via": "adapter"}, "astra": {"via": "runner"}}
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
    if not line.strip():
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
  members = judges_cfg.get("members") or DEFAULT_MEMBERS
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
                 prior: list[tuple[int, str, str]], diffs: list[str]) -> str:
  lines = [f"JUDGE BRIEF, panel {panel['id']}, round {round_no}.",
           "You are one judge of a panel. Answer each question below by option id, one line per question:",
           "`Q<n>: (<id>)`",
           "After an answer you may add one `reason: <sentence>` line and one `would change my mind: <what>` line.",
           "Close with one line `saw: <none | CLAUDE.md | memory index | hook output | ...>` naming anything",
           "that reached you besides this brief, the question file and the evidence.",
           "Report no findings. Read only the question file and the evidence listed.",
           f"Question file: {panel['question']} (sha256 {panel['question_sha256']})",
           "Evidence: " + (", ".join(e["path"] for e in panel["evidence"]) or "none")]
  if round_no > 1:
    lines += ["", f"Questions still open: {', '.join(open_ids)}",
              "Answer only those. Every prior verdict and every diff follow verbatim; no one adds arguments between rounds:",
              "weigh them and change position only for a reason you can name."]
    for rnd, judge, text in prior:
      lines += ["", f"### Round {rnd}, {judge}", text.rstrip("\n")]
    for diff in diffs:
      lines += ["", diff.rstrip("\n")]
  return "\n".join(lines) + "\n"


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
  rid = args.runcard or core.open_runcard(store, "judges", str(question), parent=args.parent)
  panel = {"id": pid, "question": str(question), "question_sha256": core.sha256_file(question),
           "evidence": evidence, "judges": members, "min_vendors": min_vendors, "runcard": rid,
           "parent": args.parent, "opened_at": core.now_iso(), "rounds": {}}
  core.atomic_write(folder / "question.md", question.read_bytes())
  write_json(folder / "panel.json", panel)
  core.atomic_write(folder / "round-1" / "brief.md",
                    render_brief(panel, questions, 1, [q["id"] for q in questions], [], []))
  core.journal(store, f"judges {pid}: opened ({', '.join(members)}; min_vendors {min_vendors})")
  print(pid)
  return 0


def cmd_record(args, store) -> int:
  panel = load_panel(store, args.panel)
  panel_card(args, store, panel)
  raise core.HandoffError("judges: record is not built yet")


COMMANDS = {"open": cmd_open, "record": cmd_record}
