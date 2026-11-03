# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_scan` as the scan module.

"""superegm scan: banned terms, bare mentions, merge markers, size, DoD presence."""

from pathlib import Path

import superegm as core

WRITES = frozenset()  # the store kinds this subcommand writes


def register(subparsers):
  p = core.add_parser(subparsers, "scan", "banned terms, bare mentions, merge markers, size, DoD presence", runcard=False)
  p.add_argument("--comment", help="scan this comment file instead of the bodies")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  if args.comment:
    path = Path(args.comment).expanduser().resolve()
    problems = core.scan_text(core.read_text(path), handoff.config, "comment", label=path.name)
  else:
    problems = core.scan_handoff(handoff)
  for problem in problems:
    print(problem)
  print("scan: clean" if not problems else f"scan: {len(problems)} problem(s)")
  return 1 if problems else 0
