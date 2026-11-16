# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U97's tests: the builder orders, the launch reason, duration_ms, the head's launch, the amendments and the Astra brief (spec section 6.5).

"""U97: spec section 6.5 conformance, the builder's launch and its measurement."""

from conftest import ROOT

ORDERS = (ROOT / "skills/wave/references/builder_orders.md").read_text(encoding="utf-8")
BRIEF = (ROOT / "skills/wave/references/foreman_brief.md").read_text(encoding="utf-8")


def test_orders_and_brief_wording():
  # the orders define deviation kinds by effect and keep Scope, test delta and TDD order under `other`
  for kind in ("interface", "dod", "spec", "test", "other"):
    assert f"`{kind}`" in ORDERS
  assert "**Deviation (interface):** <Uxx> <name>:" in ORDERS and "one heading per comment" in ORDERS
  assert "as `scan` reads it" in ORDERS
  assert "never waives a check the helper makes on paths or names" in ORDERS and "r<n>/amendments.md" in BRIEF
