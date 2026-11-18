# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U62

"""U62 (spec sections 6.1 and 4.2): a pull request GitHub reads `CONFLICTING` gives its unit the view status
`conflict`; a clean or proceeded head with no launch since its authorizing outcome's launch is relaunched once for a
merge round, a revising unit's next fix round carries the merge orders `with-fix`, and every such launch fetches and
pins the current base, briefs the builder from `git merge-tree --write-tree` and admits `Bash(git merge:*)` alone."""

import json
from pathlib import Path

import pytest

import superegm
from superegm import status
from test_events import seed as status_seed, pr as status_pr


@pytest.mark.parametrize("mergeable, status_word, ci, changed", [
  ("CONFLICTING", "conflict", "green", True),
  ("MERGEABLE", "ci green", "green", False),
  ("UNKNOWN", "ci green", "green", False),
])
def test_conflict_view(world, monkeypatch, mergeable, status_word, ci, changed):
  # §6.1: conflict is set after the CI column is read, so ci keeps its value; UNKNOWN is read again next pass
  gh, st, card = status_seed(world, monkeypatch)
  node = status_pr(gh, "green")
  node["mergeable"] = "MERGEABLE"
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  handoff = superegm.Handoff(Path(state["plan"]), st, state)
  saved_view = status.fingerprint(status.unit_view(handoff, "U01"))
  node["mergeable"] = mergeable
  fresh = status.unit_view(handoff, "U01")
  view = status.fingerprint(fresh)
  assert fresh["status"] == status_word and view["ci"] == ci
  assert (view != saved_view) == changed
  assert bool(status.unit_events("U01", saved_view, view)) == changed  # the view change `tick_trigger` and `wait_events` read
  assert handoff.state["units"]["U01"]["pr"]["mergeable"] == mergeable  # the saved pull request `launch-builder` reads
