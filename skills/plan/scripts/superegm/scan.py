# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the section 9.1 body rules, one named rule per line, over the graph module's bodies.

"""superegm scan: the body rules of spec section 9.1, one `<rule>: <unit>: <line>` per problem."""

import re
from pathlib import Path

import superegm as core
from superegm import graph

WRITES = frozenset()  # the store kinds this subcommand writes
BODY_LIMIT = 49_152


def register(subparsers):
  p = core.add_parser(subparsers, "scan", "the section 9.1 body rules, one named rule per line", runcard=False)
  p.add_argument("--comment", help="scan this comment file instead of the bodies")
  p.set_defaults(run=run, writes=WRITES)


def scan_text(text: str, config: dict, kind: str, dod=None, label="body") -> list:
  """EGM's raw, non-code-aware checks: every line as written, fences and spans
  included (a legitimate `@scope/pkg` goes in `allowed_mentions`)."""
  problems = []
  size = len(text.encode("utf-8"))
  if size > BODY_LIMIT:
    problems.append(f"body-size: {label}: {size:,} bytes exceeds {BODY_LIMIT:,}: split it")
  terms = [re.compile(t) for t in config["banned_terms"]]
  mention = config.get("fix_request_mention")
  allowed = set(config.get("allowed_mentions") or [])
  for number, line in enumerate(text.splitlines(), start=1):
    for term in terms:
      if term.search(line):
        problems.append(f"banned-term: {label}:{number}: banned term /{term.pattern}/")
    for found in core.MENTION_RE.findall(line):
      # Exact literal only: `@types` does not cover `@types/node`, `@acme` never the team `@acme/release`.
      if found in allowed or (kind == "comment" and number == 1 and mention and found == mention):
        continue
      problems.append(f"mention: {label}:{number}: bare mention {found} (it would notify that user; "
                      f"reword it, or list it in `allowed_mentions` in .superegm/config.json)")
    if re.match(r"^(<<<<<<<|=======|>>>>>>>)( |$)", line):
      problems.append(f"merge-marker: {label}:{number}: merge marker")
  for item in dod or []:
    if item not in text:
      problems.append(f"dod-missing: {label}: definition-of-done item missing from the body: {item}")
  return problems


def scan_handoff(handoff: graph.Handoff) -> list:
  problems = []
  for item in handoff.writes():
    if item[0] == "issue":
      dod = handoff.plan.units[item[1]].dod if item[1] != "tracking" else []
      problems += scan_text(item[4], handoff.config, "body", dod, label=item[1])
      problems += scan_text(item[2], handoff.config, "body", label=f"{item[1]} title")
  return problems


def run(args):
  plan, st = core.locate(args)
  handoff = graph.Handoff(plan, st, core.load_state(st.root))
  if args.comment:
    path = Path(args.comment).expanduser().resolve()
    problems = scan_text(core.read_text(path), handoff.config, "comment", label=path.name)
  else:
    problems = scan_handoff(handoff)
  for problem in problems:
    print(problem)
  print("scan: clean" if not problems else f"scan: {len(problems)} problem(s)")
  return 1 if problems else 0
