# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the judges subcommand (spec section 13.1).

"""superegm judges open|record|diff|verdict: the judge panel over a question file."""

import re
import sys

WRITES = frozenset()  # the store kinds this subcommand writes

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
  subparsers.add_parser("judges", help="the judge panel").set_defaults(run=run, writes=WRITES)


def run(args):
  print("superegm: judges is not built yet", file=sys.stderr)
  return 1
