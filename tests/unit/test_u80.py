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

