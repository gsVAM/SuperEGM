# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the orient subcommand's tests (spec section 9.3).

"""Orient: the store kinds, the names rule, the extractor on the fixture tree, the projection on
the fixture graph, the trimming sequence, the export, the graphify build against a fake CLI, the
subcommand's lines and refusals, and the callers' texts. No test runs graphify."""

import hashlib, json, os, shutil
from pathlib import Path
import pytest
from conftest import DESIGN, git

ROOT = Path(__file__).resolve().parents[2]


def test_store_orient_kinds(world):
  import superegm
  root = world.artifacts
  a = superegm.Store(root, handoff_id="sample-111111")
  assert a.path("orient", "map.md") == root / "orient/map.md" and a.path("orient", "export") == root / "orient/export"
  assert superegm.Store(root).path("orient", "graphify-out") == root / "orient/graphify-out"
  assert a.path("orient_unit", "U12.md") == root / "111111/orient/U12.md"
  assert a.kind_of(root / "orient/map.md") == "orient" and a.kind_of(root / "orient/export/x.py") == "orient"
  assert a.kind_of(root / "111111/orient/U12.md") == "orient_unit"
  with pytest.raises(superegm.HandoffError, match="no handoff in this store"):
    superegm.Store(root).path("orient_unit", "U12.md")
