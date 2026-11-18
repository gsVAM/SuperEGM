# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U66

"""U66 (spec sections 6.1 and 4.2): the foreman round of a launch with `merge: "alone"` carries `merge: true` and is
left out of the review round cap's count, and after a proceed the merge launch's head is refused dispatch so the
owner proceeds again. Fixtures: conftest's `world` and test_foreman's `seed`."""

import json

import pytest

from test_foreman import UNIT, dispatched


@pytest.mark.parametrize("launch_merge, has_key", [("alone", True), ("with-fix", False), (None, False)])
def test_round_carries_merge(world, launch_merge, has_key):
  # the dispatched rounds[] entry is marked only when its launch merged alone
  launch = {"round": 1, "status": "exited 0"} | ({"merge": launch_merge} if launch_merge else {})
  st, card, child, did, _ = dispatched(world, launches=[launch])
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  entry = data["rounds"][-1]
  assert entry["dispatch_id"] == did and entry["launch"] == 1
  assert ("merge" in entry, entry.get("merge")) == (has_key, True if has_key else None)
