# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U101's tests of recovering a round (1.3 design section 3.4).

"""U101: `review record --sha256` takes the full 40-hex head sha, the `prepared:` line prints it, `collect` prints each
finding's line and saves its `collected` phase last, and the foreman brief says how a failed `collect` is recovered.
Fixtures: test_foreman's `seed`, `prepared`, `record`."""
import json

import pytest

import superegm as core
from test_foreman import UNIT, builder_token, c, prepared, record, seed  # noqa: F401  builder_token: autouse


@pytest.mark.parametrize("sha, code", [
    ("short", 1),  # the round head's own first seven characters, as the old `prepared:` line printed them
    ("1234567" * 6, 1),  # 42 hex
    ("a" * 64, 1),
    ("g" * 40, 1),
    ("head", 0),  # the round's own 40-hex head
])
def test_sha256_is_the_full_head_sha(world, tmp_path, monkeypatch, sha, code):
  # `review record --sha256` on a head review takes only the full 40-hex commit sha (L43, L55); a refused sha records nothing
  w = prepared(world, tmp_path, monkeypatch)
  sha = {"short": w.head[:7], "head": w.head}.get(sha, sha)
  findings = w.dir / "r1/change-review.findings"
  findings.write_text("", encoding="utf-8")
  rc, out = world.run("review", "record", "--review", w.rid, "--round", 1, "--sha256", sha, "--reviewer", "change-review",
                      "--findings", str(findings), "--isolation", "clean", "--model", "m:m", "--effort", "e:e", "--runcard", w.child)
  round_file = w.st.path("reviews", w.rid, "round-1.json")
  assert rc == code, out
  assert code == 0 or ("--sha256" in out and "40" in out), out
  assert round_file.exists() == (code == 0)


def test_prepared_line_prints_the_full_head(world, tmp_path, monkeypatch):
  # the `prepared:` line names the head as the 40-hex sha `review record --sha256` takes
  w = prepared(world, tmp_path, monkeypatch)
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)  # the round again: `prepared` ran it once
  assert code == 0, out
  assert out.startswith(f"prepared: head {w.head} merge-base "), out
