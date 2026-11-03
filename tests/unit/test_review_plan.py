# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
"""U06: plan review — the dispatch set, the set reviewer, fix-design, the skill file."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import pytest

from superegm import store
from superegm import approve_spec, graph, init, review, review_plan, runcard, scan

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/review-plan/SKILL.md"
SCENARIOS = ROOT / "skills/review-plan/test_scenarios.yaml"
STANDARD = ROOT / "resources/document_standards/handoff-standard.md"
PROPORTION = ROOT / "skills/review-plan/references/proportion.md"
HANDOFF = "sample-42aff4"
SHA = {"U01": "1" * 64, "U02": "2" * 64, "U03": "3" * 64}
SPEC = ("# Sample\n\n## 1. Intent\nOne line.\n\n## 2. Units\n\n"
        "| Unit | Scope | Blocked by | Size |\n| --- | --- | --- | --- |\n"
        "| U01 | the queue | — | S |\n| U02 | the worker | U01 | S |\n| U03 | the admin | U02 | S |\n")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def body(uid, blocked):
    consumes = f"- Consumes: {blocked.lower()}_fn ({blocked})\n" if blocked else ""
    blocked_by = f"#<{blocked}>" if blocked else "none"
    return (f"<!-- superegm:handoff={HANDOFF} unit={uid} spec={'f' * 64} -->\n# {uid} — Title\n"
            "Spec: `docs/specs/sample.md` @ abc1234 · `docs/specs/sample.md:6-11 (## 2. Units)`\n\n"
            f"## Interfaces\n- Produces: {uid.lower()}_fn(x: int) -> int\n{consumes}\n"
            "## Definition of done\n1. The test for each Step was committed before its implementation "
            "(checked by superegm tdd-order)\n\n"
            "## Steps\n1. Write the failing test `test_x` in `tests/unit/test_x.py`:\n\n"
            "## Scope, order and risk\n"
            f"Scope: `src/{uid.lower()}.py` (create) · Blocked by: {blocked_by} · Shared files: none · "
            f"Risk: low: new · Size: S\nBranch: `superegm/{HANDOFF}/{uid}` · Part of #<tracking>\n")


@pytest.fixture
def planned(world):
    """The store after U05's `graph --plan`: U01 and U02 unfiled, U03 filed as #7."""
    spec = write(world.repo / "docs/specs/sample.md", SPEC)
    # `design.path` is what binds a unit-keyed subcommand to the card on the spec (`require_runcard`).
    write(world.artifacts / "state.json", json.dumps(
        {"handoff_id": HANDOFF, "plan": str(world.repo.parent / "plan.md"), "design": {"path": str(spec)},
         "units": {"U03": {"number": 7}}}))
    st = store(world.repo)                          # reads handoff_id, so unit-keyed kinds resolve
    for uid, blocked in (("U01", None), ("U02", "U01"), ("U03", "U02")):
        write(st.path("unit", uid), f"### {uid}: Title\n\n## Issue body as posted\n\n```markdown\n"
                                    f"{body(uid, blocked)}```\n")
    write(st.path("units"), json.dumps({"handoff_id": HANDOFF, "order": ["U01", "U02", "U03"],
                                        "units": {u: {"body_sha256": SHA[u]} for u in SHA}}))
    world.review_card, world.spec, world.store = world.open_card("review-plan", str(spec)), spec, st
    return world


def open_review(w, uid):
    code, out = w.run("review", "open", "--kind", "plan", "--artifact", uid, "--sha256", SHA[uid],
                      "--reviewers", "readiness,set", "--runcard", w.review_card)
    assert code == 0, out
    return out.split()[-1]


def record(w, rid, rnd, reviewer, lines, sha, not_run=None):
    findings = write(w.repo.parent / f"{rid}_{reviewer}_r{rnd}.txt", "".join(line + "\n" for line in lines))
    argv = ["review", "record", "--review", rid, "--round", str(rnd), "--sha256", sha,
            "--reviewer", reviewer, "--isolation", "clean", "--model", "inherit:inherit",
            "--effort", "inherit:inherit", "--runcard", w.review_card]
    argv += ["--not-run", not_run] if not_run else ["--findings", str(findings)]
    code, out = w.run(*argv)
    assert code == 0, out


def status(w, rid):
    return w.run("review", "status", "--review", rid, "--runcard", w.review_card)[0]


def due(w):
    code, out = w.run("review-plan", "due", "--runcard", w.review_card)
    assert code == 0, out
    return {line.split()[0]: line.split()[1:] for line in out.strip().splitlines()}


def test_due_lists_the_units_a_round_dispatches(planned):
    w = planned
    r2 = open_review(w, "U02")                      # U02 converges on its current bytes
    record(w, r2, 1, "readiness", [], SHA["U02"])
    record(w, r2, 1, "set", [], SHA["U02"])
    assert status(w, r2) == 0
    assert due(w) == {"U01": ["due", "-", "1", SHA["U01"]],
                      "U02": ["converged", r2, "-", SHA["U02"]]}   # U03 is filed: absent
    units = json.loads(w.store.path("units").read_text(encoding="utf-8"))
    units["units"]["U02"]["body_sha256"] = "e" * 64             # re-rendered since it converged
    w.store.path("units").write_text(json.dumps(units), encoding="utf-8")
    assert due(w)["U02"] == ["due", r2, "2", "e" * 64]
    r1 = open_review(w, "U01")                      # two rounds not completed under this card
    record(w, r1, 1, "readiness", [], SHA["U01"], not_run="timeout")
    record(w, r1, 2, "readiness", [], SHA["U01"], not_run="timeout")
    assert status(w, r1) == 5
    assert due(w)["U01"] == ["stalled", r1, "-", SHA["U01"]]
    rc = r2                                        # U02 at its cap: five completed rounds, round 1 and four unclean
    for rnd in range(2, 6):
        record(w, rc, rnd, "readiness", [f"readiness-{rnd}-1 | high | U02 Steps | regression: no | "
                                          "Step 1 names no command"], "e" * 64)
        record(w, rc, rnd, "set", [], "e" * 64)
    assert status(w, rc) == 2
    assert due(w)["U02"] == ["cap", rc, "-", "e" * 64]
    assert w.run("review", "rule", "--review", rc, "--ruling", "accept", "--owner",
                 "--runcard", w.review_card)[0] == 0
    assert due(w)["U02"] == ["converged", rc, "-", "e" * 64]


def test_set_input_carries_the_units_table_and_each_unfiled_body_interfaces_only(planned):
    w = planned
    code, out = w.run("review-plan", "set-input", "--spec", str(w.spec))
    assert code == 0, out
    assert "| U03 | the admin | U02 | S |" in out                      # the spec's `## Units`, whole
    assert "- Produces: u01_fn(x: int) -> int" in out
    assert "- Consumes: u01_fn (U01)" in out
    assert "Scope: `src/u02.py` (create) · Blocked by: #<U01> · Shared files: none" in out
    assert "## U03" not in out and "u03_fn" not in out                 # filed: not in the set
    assert "## Steps" not in out and "test_x" not in out and "Definition of done" not in out
    assert out.index("| U01 | the queue") < out.index("## U01") < out.index("## U02")


def round_text(w, rid, rnd):
    return w.store.path("reviews", rid, f"round-{rnd}.json").read_text(encoding="utf-8")


def test_set_file_splits_per_unit_and_reopens_a_converged_unit(planned):
    w = planned
    r1, r2 = open_review(w, "U01"), open_review(w, "U02")
    record(w, r2, 1, "readiness", [], SHA["U02"])
    record(w, r2, 1, "set", [], SHA["U02"])
    assert due(w)["U02"][0] == "converged"
    the_set = ["set-2-1 | high | U01 Interfaces | regression: no | Produces u01_fn has no consumer",
               "set-2-2 | medium | U02 Consumes | regression: no | u01_fn (U01) consumed with another arity",
               "set-2-3 | high | the cut | regression: no | U03's scope belongs in U02"]
    record(w, r1, 1, "readiness", [], SHA["U01"])
    record(w, r1, 1, "set", the_set, SHA["U01"])        # U01's open round keeps 1 and 3
    record(w, r2, 2, "set", the_set, SHA["U02"])        # U02 converged: the set reopens it
    kept = {rid: {fid for fid in ("set-2-1", "set-2-2", "set-2-3") if fid in round_text(w, rid, n)}
            for rid, n in ((r1, 1), (r2, 2))}
    assert kept == {r1: {"set-2-1", "set-2-3"}, r2: {"set-2-2", "set-2-3"}}
    listing = due(w)
    assert listing["U01"][:3] == ["due", r1, "2"]       # round 1 completed and not clean
    assert listing["U02"][:3] == ["due", r2, "3"]       # round 2 holds the set's record only
