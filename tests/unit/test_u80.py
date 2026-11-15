# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0

"""U80 (spec section 6.5): the builder orders and foreman brief wording, the launch reason, `duration_ms` and the
amendments list, as the section states them."""

import json
from pathlib import Path

import pytest

from superegm import launch_builder, prepare
import test_builders as tb
from test_builders import spawn_fake, no_graphify, which  # noqa: F401  the fixtures test_builders' launches run under

ROOT = Path(__file__).resolve().parents[2]
LATER, EARLIER = "2099-01-01T00:00:00Z", "2000-01-01T00:00:00Z"


def test_orders_and_brief_wording():
  # the orders define deviation kinds by effect and keep Scope, test delta and TDD order under `other`
  orders = (ROOT / "skills/wave/references/builder_orders.md").read_text()
  assert "An `other` deviation never waives a check the helper makes on paths or names: Scope, the test delta and TDD order still hold" in orders
  assert all(f"`{k}`" in orders for k in ("interface", "dod", "test", "other")) and "one heading per comment" in orders
  assert "r<n>/amendments.md" in (ROOT / "skills/wave/references/foreman_brief.md").read_text()


BLOCKED = "**Builder status:** BLOCKED\nWhich?\n- (a) keep\n- (b) change\n"
NEEDS = "**Builder status:** NEEDS_CONTEXT\nWhich?\n- (a) keep\n- (b) change\n"
INTERFACE = "**Deviation (interface):** U03 store: takes the root\n"


@pytest.mark.parametrize("since_last_launch, reason", [
  ("no launch before", "first"),
  ("a round posted", "review"),
  ("a ruling on a **Builder status:** BLOCKED comment", "blocked"),
  ("a ruling on a **Builder status:** NEEDS_CONTEXT comment", "blocked"),
  ("a ruling on a **Deviation (interface):** comment with no status", "harness"),
  ("nothing", "harness"),
])
def test_launch_reason(since_last_launch, reason):
  # the latest event after the previous launch started decides the reason
  launches = [] if since_last_launch == "no launch before" else [{"round": 1, "started_at": "2026-11-01T00:00:00Z"}]
  question = {"a ruling on a **Builder status:** BLOCKED comment": BLOCKED,
              "a ruling on a **Builder status:** NEEDS_CONTEXT comment": NEEDS,
              "a ruling on a **Deviation (interface):** comment with no status": INTERFACE}.get(since_last_launch)
  foreman = {"rounds": [], "decisions": [], "rulings": []}
  if since_last_launch == "a round posted":
    foreman["rounds"].append({"round": 1, "phase": "posted", "outcome": "revise", "posted_at": LATER})
  if question:
    foreman["decisions"].append({"id": "q1", "point": 3, "source": "comment 55", "question": question})
    foreman["rulings"].append({"decision": "q1", "ruling": "(a) — go", "posted_at": LATER})
  assert launch_builder.launch_reason(launches, foreman) == reason

