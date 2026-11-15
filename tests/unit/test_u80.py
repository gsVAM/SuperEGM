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


@pytest.mark.parametrize("value, recorded", [(1234, 1234), (12.5, 12.5), (True, None), ("1234", None), (None, None)])
def test_duration_ms_present_or_absent(world, monkeypatch, spawn_fake, value, recorded):
  # the result file's duration is kept only as a real number
  s, card, hid, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", tb.UNIT, "--round", 1, "--runcard", card)[0] == 0
  entry = tb.launches_of(s)[0]
  Path(entry["result_file"]).write_text(json.dumps({"duration_ms": value}), encoding="utf-8")
  Path(entry["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", tb.UNIT, "--exit", 0, "--runcard", card)[0] == 0
  latest = tb.launches_of(s)[-1]
  assert latest.get("duration_ms", None) == recorded and (("duration_ms" in latest) is (recorded is not None))


def amendment(unit, name, at, cid):
  return {"unit": unit, "name": name, "text": f"{unit} {name} now reads v{cid}", "comment_id": cid, "at": at}


def test_amendments_and_applies_to_this_head(tmp_path):
  # own unit's and a Consumes line's amendments, by `at`; another unit's left out
  body = "# U03 — Worker\n\n## Interfaces\n- Consumes: g (U01)\n- Produces: f() -> None\n"
  entries = [amendment("U01", "g", "2026-11-02T00:00:00Z", 12), amendment("U09", "h", "2026-11-01T00:00:00Z", 13),
             amendment("U03", "f", "2026-11-01T00:00:00Z", 11)]
  (tmp_path / "state.json").write_text(json.dumps({"amendments": entries}), encoding="utf-8")

  class St:
    def path(self, *parts):
      return tmp_path / "state.json"
  got = launch_builder.amendments_for(St(), "U03", body)
  assert [(a["unit"], a["name"]) for a in got] == [("U03", "f"), ("U01", "g")]
  prompt = launch_builder.prompt_text(124, "U03", body, "orders", "orient", [], [], None, "builder-bot", "audit", amendments=got)
  assert "## U03 f · comment 11 at " in prompt and prompt.index("# Amendments") >= 0
  prepare.write_amendments(tmp_path / "amendments.md", got, "2026-11-01T12:00:00Z")
  amendments_md = (tmp_path / "amendments.md").read_text(encoding="utf-8")
  assert amendments_md.splitlines()[0] == "# Amendments"
  entry_before_launch, entry_after_launch = amendments_md.split("## U01 g")[0], "## U01 g" + amendments_md.split("## U01 g")[1]
  assert "applies to this head: yes" in entry_before_launch and "applies to this head: no" in entry_after_launch
  prepare.write_amendments(tmp_path / "none.md", [], "2026-11-01T12:00:00Z")
  empty_amendments_md = (tmp_path / "none.md").read_text(encoding="utf-8")
  assert empty_amendments_md.split() == ["#", "Amendments", "none"]
