# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U101's tests of recovering a round (1.3 design section 3.4).

"""U101: `review record --sha256` takes the full 40-hex head sha, the `prepared:` line prints it, `collect` prints each
finding's line and saves its `collected` phase last, and the foreman brief says how a failed `collect` is recovered.
Fixtures: test_foreman's `seed`, `prepared`, `record`."""
import json
from pathlib import Path

import pytest

import superegm as core
from test_foreman import UNIT, builder_token, prepared  # noqa: F401  builder_token: autouse

ROOT = Path(__file__).resolve().parents[2]


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


OTHER = [("test(S1): hook", "tests/unit/test_hooks.py"), ("feat(S1): hook", "src/hooks.py"), ("feat(S1): more", "src/other.py")]


def collect(world, w):
  return world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)


def test_collect_prints_each_finding_line(world, tmp_path, monkeypatch):
  # collect prints the count and every foreman finding's line it recorded (L8): CI not green, and a path outside Scope
  w = prepared(world, tmp_path, monkeypatch, ci="failure", commits=OTHER)
  code, out = collect(world, w)
  findings = (w.dir / "r1/foreman.findings").read_text(encoding="utf-8").splitlines()
  assert code == 0 and len(findings) >= 2, out
  assert f"collected: {len(findings)} foreman findings" in out.splitlines()
  assert all(line in out.splitlines() for line in findings)


def test_failed_collect_leaves_the_round_prepared(world, tmp_path, monkeypatch):
  # a collect that fails after recording the foreman's findings (the round file's last write raises) leaves the round
  # `prepared` in foreman/<unit>.json; the same command run again on that round completes it, each finding once (L19)
  w = prepared(world, tmp_path, monkeypatch, ci="failure", commits=OTHER)
  round_file = w.st.path("reviews", w.rid, "round-1.json")
  phase = lambda: json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]["phase"]
  real, writes = core.atomic_write, []

  def failing(path, obj):
    if str(path) == str(round_file):
      writes.append(path)
      if len(writes) == 2:  # `review record`'s write is the first, `collect`'s own last one the second
        raise core.HandoffError("disk full")
    return real(path, obj)
  monkeypatch.setattr(core, "atomic_write", failing)
  first_code, _ = collect(world, w)
  phase_after_first = phase()
  monkeypatch.setattr(core, "atomic_write", real)
  second_code, out = collect(world, w)
  phase_after_second = phase()
  assert first_code != 0 and phase_after_first == "prepared"
  assert second_code == 0 and phase_after_second == "collected", out
  round_record = json.loads(round_file.read_text(encoding="utf-8"))
  assert {"builder_contested", "what_ran"} <= set(round_record)
  foreman_ids = [f["id"] for f in round_record["reviewers"]["foreman"]["findings"]]
  assert len(foreman_ids) == len(set(foreman_ids)) >= 2


def test_brief_recovers_and_dispatches_with_the_pair():
  # the brief: rerun a failed collect once, `--not-run` only for a panel that did not run, the pair on every Agent call,
  # and the deviation evidence `decision.py`'s check counts (L7, L19, #240 codebase-details-5-1)
  brief = " ".join((ROOT / "skills/wave/references/foreman_brief.md").read_text(encoding="utf-8").split())
  assert "run again once on the same prepared round; failing again, return `error`" in brief
  assert "a `collect` refused for its `--spec` text writes nothing and is not that rerun" in brief
  assert "whose panel did not run" in brief
  assert "pass `model` and `effort` on every Agent call" in brief
  assert "The evidence is exactly what `collect` counts: a command on one line in inline backticks, then its output" not in brief
  assert "a backticked span that is not itself a `path:line`, or a `path:line` outside the spec" in brief
