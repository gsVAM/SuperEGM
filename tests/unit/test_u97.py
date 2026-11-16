# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U97's tests: the builder orders, the launch reason, duration_ms, the head's launch, the amendments and the Astra brief (spec section 6.5).

"""U97: spec section 6.5 conformance, the builder's launch and its measurement."""

import json
import pytest
from conftest import ROOT
from superegm import launch_builder, record_launch

ORDERS = (ROOT / "skills/wave/references/builder_orders.md").read_text(encoding="utf-8")
BRIEF = (ROOT / "skills/wave/references/foreman_brief.md").read_text(encoding="utf-8")
T0, T1 = "2026-11-01T00:00:00Z", "2026-11-02T00:00:00Z"
STATUS = {"BLOCKED": "**Builder status:** BLOCKED\n\nstuck\n- (a) go\n- (b) stop\n",
          "NEEDS_CONTEXT": "**Builder status:** NEEDS_CONTEXT\n\nwhich?\n- (a) this\n- (b) that\n",
          "none": "**Deviation (other):** a fixture differs\n"}


def test_orders_and_brief_wording():
  # the orders define deviation kinds by effect and keep Scope, test delta and TDD order under `other`
  for kind in ("interface", "dod", "spec", "test", "other"):
    assert f"`{kind}`" in ORDERS
  assert "**Deviation (interface):** <Uxx> <name>:" in ORDERS and "one heading per comment" in ORDERS
  assert "as `scan` reads it" in ORDERS
  assert "never waives a check the helper makes on paths or names" in ORDERS and "r<n>/amendments.md" in BRIEF


def foreman_of(event):
  data = {"decisions": [], "rulings": [], "rounds": []}
  if event == "posted round":
    data["rounds"] = [{"round": 1, "launch": 1, "phase": "posted", "outcome": "revise", "posted_at": T1}]
  elif event and event.startswith("ruled"):
    word = event.split()[1] if event.split()[1] in STATUS else "none"
    data["decisions"] = [{"id": "Q1", "point": 3, "source": "comment 55", "question": STATUS[word]}]
    data["rulings"] = [{"decision": "Q1", "ruling": "(a) — go", "posted_at": T1}]
  return data


@pytest.mark.parametrize("event, reason", [(None, "first"), ("posted round", "review"), ("ruled BLOCKED", "blocked"),
                                           ("ruled NEEDS_CONTEXT", "blocked"), ("ruled comment without status", "harness"), ("stall", "harness")])
def test_launch_reason(event, reason):
  # the latest event after the previous launch started decides the reason
  launches = [] if event is None else [{"round": 1, "started_at": T0}]
  assert launch_builder.launch_reason(launches, foreman_of(event)) == reason


@pytest.mark.parametrize("value, recorded", [(1234, 1234), (12.5, 12.5), (True, None), ("1234", None), (None, None)])
def test_duration_ms_present_or_absent(tmp_path, value, recorded):
  # the key is present only for a real number
  result = tmp_path / "result.json"
  result.write_text(json.dumps({"duration_ms": value}), encoding="utf-8")
  assert record_launch.result_usage(result)[2] == recorded
