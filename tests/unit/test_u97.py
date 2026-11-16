# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U97's tests: the builder orders, the launch reason, duration_ms, the head's launch, the amendments and the Astra brief (spec section 6.5).

"""U97: spec section 6.5 conformance, the builder's launch and its measurement."""

import json
from pathlib import Path
import pytest
from conftest import ROOT
from superegm import launch_builder, record_launch
import test_builders as tb
from test_builders import spawn_fake, no_graphify, which  # noqa: F401  the fixtures test_builders' launches run under

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
def test_duration_ms_present_or_absent(world, monkeypatch, spawn_fake, tmp_path, value, recorded):
  # the key is present only for a real number, in the filter and in the launch record
  result = tmp_path / "result.json"
  result.write_text(json.dumps({"duration_ms": value}), encoding="utf-8")
  assert record_launch.result_usage(result)[2] == recorded
  s, card, hid, _ = tb.seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", tb.UNIT, "--round", 1, "--runcard", card)[0] == 0
  entry = tb.launches_of(s)[0]
  Path(entry["result_file"]).write_text(json.dumps({"duration_ms": value}), encoding="utf-8")
  Path(entry["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", tb.UNIT, "--exit", 0, "--runcard", card)[0] == 0
  entry = tb.launches_of(s)[0]
  assert ("duration_ms" in entry) is (recorded is not None) and entry.get("duration_ms") == recorded


def _prepare_head(world, tmp_path, monkeypatch, started, amendments=(), extra=None):
  """Prepare round 2 of U01 whose head commit is made now, with launches started at `started` (`extra` maps a launch
  number to more launch keys) and the amendments: an `at`, an `(at, recorded_at)` pair, or `(at, None)` for a legacy entry."""
  import test_foreman as tf
  target, base, head, g = tf.pr_repo(world, tmp_path, monkeypatch)
  launches = [{"round": i + 1, "status": "exited 0", "started_at": at, **(extra or {}).get(i + 1, {})} for i, at in enumerate(started)]
  st, card, child, did, _ = tf.dispatched(world, head=head, rounds=[tf.POSTED_R1], launches=launches)
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  pairs = [a if isinstance(a, tuple) else (a, a) for a in amendments]
  state["amendments"] = [{"unit": "U01", "name": "hook", "text": "hook now reads v1", "comment_id": 61, "at": at,
                          **({"recorded_at": rec} if rec else {})} for at, rec in pairs]
  st.path("state").write_text(json.dumps(state), encoding="utf-8")
  code, out = world.run("prepare", "--unit", tf.UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  record = json.loads(st.path("foreman", tf.UNIT).read_text(encoding="utf-8"))
  text = (st.path("review", tf.UNIT, f"pr{tf.PR}") / "r2/amendments.md").read_text(encoding="utf-8")
  return st, card, record, text


def test_astra_brief_amendments(world, tmp_path, monkeypatch):
  # the Astra lane reviews against the same amendments as the foreman
  import test_foreman as tf
  from superegm import foreman
  monkeypatch.setattr(foreman, "runner_path", lambda: "/x/runner.py")
  (tmp_path / "e").mkdir()
  w = tf.prepared(world, tmp_path / "e", monkeypatch, astra={"enabled": True}, rounds=[tf.POSTED_R1], launches=tf.TWO_LAUNCHES)
  dir_ = w.dir / "r2"
  brief = (dir_ / "astra_brief.md").read_text(encoding="utf-8")
  amendments_md_text = (dir_ / "amendments.md").read_text(encoding="utf-8")
  assert "# Amendments\n" in brief and amendments_md_text in brief


def test_head_attributed_to_own_commit(world, tmp_path, monkeypatch):
  # launch 3 pushed nothing: the head is launch 2's, and an amendment recorded after launch 2 started does not apply
  import test_foreman as tf
  early, mid, late = "2000-01-01T00:00:00Z", "2000-01-02T00:00:00Z", "2099-01-01T00:00:00Z"
  for name in "abcdefghi":
    (tmp_path / name).mkdir()
  st, card, record, amendments_md = _prepare_head(world, tmp_path / "a", monkeypatch, [early, mid, late], ["2000-01-03T00:00:00Z"])
  assert record["rounds"][-1]["head_launch"] == 2 and record["rounds"][-1]["launch"] == 3
  record["rounds"][-1]["phase"] = "posted"
  st.path("foreman", tf.UNIT).write_text(json.dumps(record), encoding="utf-8")
  code, out = world.run("foreman", "dispatch", "--unit", tf.UNIT, "--runcard", card)
  assert "round 2 posted since launch 3" in out  # the round still answers the latest launch
  assert "applies to this head: no" in amendments_md
  _, _, after_push, md_after_push = _prepare_head(world, tmp_path / "b", monkeypatch, [early, mid, late], ["2000-01-01T12:00:00Z"])
  assert after_push["rounds"][-1]["head_launch"] == 2 and "applies to this head: yes" in md_after_push
  _, _, _, md_before = _prepare_head(world, tmp_path / "c", monkeypatch, [early, mid], ["2000-01-03T00:00:00Z"])
  assert "applies to this head: no" in md_before
  # a launch 3 that committed but never pushed is not the head's
  _, _, unpushed, _ = _prepare_head(world, tmp_path / "e", monkeypatch, [early, mid, late], [], {3: {"last_commit_at": "2099-01-01T01:00:00Z"}})
  assert unpushed["rounds"][-1]["head_launch"] == 2
  # launch 3 pushed: the head is its own and the amendment recorded after launch 2 started now applies
  _, _, pushed, md_pushed = _prepare_head(world, tmp_path / "f", monkeypatch, [early, mid, "2000-01-04T00:00:00Z"], ["2000-01-03T00:00:00Z"])
  assert pushed["rounds"][-1]["head_launch"] == 3 and "applies to this head: yes" in md_pushed
  # `recorded_at` decides over `at`; a legacy entry without it falls back to `at`
  _, _, _, md_rec_late = _prepare_head(world, tmp_path / "g", monkeypatch, [early, mid], [("2000-01-01T12:00:00Z", "2000-01-03T00:00:00Z")])
  assert "applies to this head: no" in md_rec_late
  _, _, _, md_rec_early = _prepare_head(world, tmp_path / "h", monkeypatch, [early, mid], [("2000-01-03T00:00:00Z", "2000-01-01T12:00:00Z")])
  assert "applies to this head: yes" in md_rec_early
  _, _, _, md_legacy = _prepare_head(world, tmp_path / "i", monkeypatch, [early, mid], [("2000-01-01T12:00:00Z", None), ("2000-01-03T00:00:00Z", None)])
  assert md_legacy.count("applies to this head: yes") == 1 and md_legacy.count("applies to this head: no") == 1
  _, _, none_record, empty_md = _prepare_head(world, tmp_path / "d", monkeypatch, ["2099-01-01T00:00:00Z", "2099-01-02T00:00:00Z"])
  assert empty_md.split() == ["#", "Amendments", "none"]
  assert none_record["rounds"][-1]["head_launch"] is None
