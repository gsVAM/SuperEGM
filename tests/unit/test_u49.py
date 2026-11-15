# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U49

"""U49 (spec section 8): an interrupted launch keeps its subagent calls, read through one helper."""

import json, re, uuid
from pathlib import Path

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import ROOT

SCRIPTS = ROOT / "skills/plan/scripts/superegm"


def jsonl(path, items):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")


def agent(tid):
  return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "Agent", "input": {"prompt": "p"}}]}}


def two_calls(profile, sid):
  """A transcript for `sid` under `profile` holding two `Agent` calls."""
  jsonl(Path(profile) / "projects/-wt" / f"{sid}.jsonl", [agent("a1"), agent("a2")])


def test_launch_subagent_calls_reads_the_entry_session(tmp_path, monkeypatch):
  from superegm import traces
  monkeypatch.setenv("HOME", str(tmp_path))
  two_calls(tmp_path / "prof", "s1")
  assert traces.launch_subagent_calls("~/prof", {"session_id": "s1"}) == traces.subagent_calls(Path.home() / "prof", "s1")
  assert traces.launch_subagent_calls("~/prof", {"session_id": "s1"})["count"] == 2
  assert traces.launch_subagent_calls("~/prof", {}) == {"count": 0, "calls": []}
