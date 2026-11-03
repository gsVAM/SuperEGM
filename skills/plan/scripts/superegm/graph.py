# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_graph` as the graph module.

"""superegm graph: parse the plan; write units, bodies and the generated sections."""

import superegm as core


def register(subparsers):
  p = core.add_parser(subparsers, "graph", "parse the plan; write units, bodies and the generated sections")
  p.set_defaults(run=run)


def run(args):
  plan = core.locate(args)
  handoff = core.Handoff(plan)
  handoff.write_graph_files()
  g = handoff.graph
  print(f"handoff {handoff.handoff_id} on {handoff.config['repo']} (remote {handoff.config['remote']}): "
        f"{len(handoff.plan.units)} units, {len(g.waves)} waves, labels ok")
  for wave in sorted(g.waves):
    print(f"wave {wave}: {', '.join(g.waves[wave])}")
  print("critical path: " + " -> ".join(g.critical_path))
  print(f"wrote handoff_units.json, {len(g.order)} unit_*.md, handoff_bodies.md in {handoff.artifact_dir}")
  return 0
