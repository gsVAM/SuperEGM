# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the file skill under the chain, a started filing resumed, a converged review with a later round refused (U56).

"""U56: `gate.converged_review` refuses a review with a round after the converged one; the file skill resumes a
started filing through `apply --yes` and `verify` before the gate, takes the frozen mode, and waits under the driver."""

import json
import re
from pathlib import Path

import pytest

from superegm import gate, store
from test_file import (ROOT, ROWS, applied, close_card, dry_run, gated, hp, open_card, state_of, planned, converge)


def reviews_of(world, uid):
  """The folder of the unit's plan review in the handoff's `reviews/`."""
  return next(p.parent for p in hp(world, "reviews").glob("*/review.json")
              if json.loads(p.read_text(encoding="utf-8"))["artifact"] == uid)


def test_converged_review_refuses_a_later_round(world):
  spec, plan, handoff_id, card = dry_run(world)
  folder = reviews_of(world, "U01")
  # U01's plan review converged at round 2 on the current body
  round_one = json.loads((folder / "round-1.json").read_text(encoding="utf-8"))
  (folder / "round-2.json").write_text(json.dumps(round_one), encoding="utf-8")
  meta = json.loads((folder / "review.json").read_text(encoding="utf-8"))
  meta["converged_round"] = 2
  (folder / "review.json").write_text(json.dumps(meta), encoding="utf-8")
  hp(world, "state")  # resolves the handoff of the spec for `store`
  handoff_store = store(world.repo)
  assert gate.converged_review(handoff_store, "U01") == (True, round_one["artifact_sha256"])
  # a round-3 file then written
  (folder / "round-3.json").write_text(json.dumps(round_one), encoding="utf-8")
  assert gate.converged_review(handoff_store, "U01") == (False, None)
  code, out = world.run("gate", "--pass", "--spec", spec, "--runcard", card)
  assert code == 1 and "gate: U01 plan review not converged" in out, out
  # a resumed apply keeps the hashes of the earlier pass and refuses on its own check
  code, out = world.run("apply", "--yes", "--spec", spec, "--runcard", card)
  assert code == 1 and "apply: U01 body differs from its converged round" in out, out
  # without the round-3 file
  (folder / "round-3.json").unlink()
  assert gate.converged_review(handoff_store, "U01") == (True, round_one["artifact_sha256"])
