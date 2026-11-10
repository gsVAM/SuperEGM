# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
"""U06: plan review — the dispatch set, the set reviewer, fix-design, the skill file."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import pytest

from superegm import store
from superegm import approve_spec, graph, init, judges, review, review_plan, runcard, scan

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/review-plan/SKILL.md"
SCENARIOS = ROOT / "skills/review-plan/test_scenarios.yaml"
STANDARD = ROOT / "resources/document_standards/handoff-standard.md"
PROPORTION = ROOT / "skills/review-plan/references/proportion.md"
HANDOFF = "sample-42aff4"
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


SHA = {u: hashlib.sha256(body(u, b).encode("utf-8")).hexdigest() for u, b in (("U01", None), ("U02", "U01"), ("U03", "U02"))}


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
    code, out = w.run("review", "open", "--kind", "plan", "--artifact", uid,
                      "--reviewers", "readiness,set", "--runcard", w.review_card)
    assert code == 0, out
    return out.split()[-1]


def record(w, rid, rnd, reviewer, lines, not_run=None):
    findings = write(w.repo.parent / f"{rid}_{reviewer}_r{rnd}.txt", "".join(line + "\n" for line in lines))
    argv = ["review", "record", "--review", rid, "--round", str(rnd),
            "--reviewer", reviewer, "--isolation", "clean", "--model", "inherit:inherit",
            "--effort", "inherit:inherit", "--runcard", w.review_card]
    argv += ["--not-run", not_run] if not_run else ["--findings", str(findings)]
    code, out = w.run(*argv)
    assert code == 0, out


def rerender(w, uid, text):
    """The unit's body re-rendered: `unit_<id>.md` and `handoff_units.json`'s `body_sha256` take `text`; its hash."""
    write(w.store.path("unit", uid), f"### {uid}: Title\n\n## Issue body as posted\n\n```markdown\n{text}```\n")
    units = json.loads(w.store.path("units").read_text(encoding="utf-8"))
    units["units"][uid]["body_sha256"] = sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    w.store.path("units").write_text(json.dumps(units), encoding="utf-8")
    return sha


def status(w, rid):
    return w.run("review", "status", "--review", rid, "--runcard", w.review_card)[0]


def due(w):
    code, out = w.run("review-plan", "due", "--runcard", w.review_card)
    assert code == 0, out
    return {line.split()[0]: line.split()[1:] for line in out.strip().splitlines()}


def test_due_lists_the_units_a_round_dispatches(planned):
    w = planned
    r2 = open_review(w, "U02")                      # U02 converges on its current bytes
    record(w, r2, 1, "readiness", [])
    record(w, r2, 1, "set", [])
    assert status(w, r2) == 0
    assert due(w) == {"U01": ["due", "-", "1", SHA["U01"]],
                      "U02": ["converged", r2, "-", SHA["U02"]]}   # U03 is filed: absent
    moved = rerender(w, "U02", body("U02", "U01") + "re-rendered\n")   # re-rendered since it converged
    assert due(w)["U02"] == ["due", r2, "2", moved]
    r1 = open_review(w, "U01")                      # two rounds not completed under this card
    record(w, r1, 1, "readiness", [], not_run="timeout")
    record(w, r1, 2, "readiness", [], not_run="timeout")
    assert status(w, r1) == 5
    assert due(w)["U01"] == ["stalled", r1, "-", SHA["U01"]]
    rc = r2                                        # U02 at its cap: five completed rounds, round 1 and four unclean
    for rnd in range(2, 6):
        record(w, rc, rnd, "readiness", [f"readiness-{rnd}-1 | high | U02 Steps | regression: no | "
                                          "Step 1 names no command"])
        record(w, rc, rnd, "set", [])
    assert status(w, rc) == 2
    assert due(w)["U02"] == ["cap", rc, "-", moved]
    assert w.run("review", "rule", "--review", rc, "--ruling", "accept", "--owner",
                 "--runcard", w.review_card)[0] == 0
    assert due(w)["U02"] == ["converged", rc, "-", moved]


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
    record(w, r2, 1, "readiness", [])
    record(w, r2, 1, "set", [])
    assert due(w)["U02"][0] == "converged"
    the_set = ["set-2-1 | high | U01 Interfaces | regression: no | Produces u01_fn has no consumer",
               "set-2-2 | medium | U02 Consumes | regression: no | u01_fn (U01) consumed with another arity",
               "set-2-3 | high | the cut | regression: no | U03's scope belongs in U02"]
    record(w, r1, 1, "readiness", [])
    record(w, r1, 1, "set", the_set)        # U01's open round keeps 1 and 3
    record(w, r2, 2, "set", the_set)        # U02 converged: the set reopens it
    kept = {rid: {fid for fid in ("set-2-1", "set-2-2", "set-2-3") if fid in round_text(w, rid, n)}
            for rid, n in ((r1, 1), (r2, 2))}
    assert kept == {r1: {"set-2-1", "set-2-3"}, r2: {"set-2-2", "set-2-3"}}
    listing = due(w)
    assert listing["U01"][:3] == ["due", r1, "2"]       # round 1 completed and not clean
    assert listing["U02"][:3] == ["due", r2, "3"]       # round 2 holds the set's record only


def test_fix_design_voids_the_approval(planned):
    w = planned
    approval = write(w.store.path("approvals", "sample"), json.dumps(
        {"path": str(w.spec), "sha256": hashlib.sha256(SPEC.encode("utf-8")).hexdigest(),
         "commit": "abc1234", "runcard": "rc-spec", "review": "spec-sample-c1",
         "approved_at": "2026-11-03T00:00:00Z", "amended": [], "handoff_id": HANDOFF}))
    rid = open_review(w, "U01")
    record(w, rid, 1, "readiness", ["readiness-1-1 | high | U01 Design range | regression: no | "
                                     "the spec gives no exit code for this refusal"])
    record(w, rid, 1, "set", [])
    code, out = w.run("review", "settle", "--review", rid, "--finding", "readiness-1-1",
                      "--disposition", "fix-design", "--runcard", w.review_card)
    assert code == 0, out
    assert status(w, rid) == 4
    assert due(w)["U01"] == ["fix-design", rid, "-", SHA["U01"]]
    # `approve-spec` requires `--spec` (U04's form): the void names the spec whose approval it voids.
    code, out = w.run("approve-spec", "--void", "--review", rid, "--spec", str(w.spec), "--runcard", w.review_card)
    assert code == 0, out
    assert json.loads(approval.read_text(encoding="utf-8"))["voided_by"] == rid


HELPER_CALL = re.compile(r"<HELPER>' ([a-z][a-z0-9-]*)(?: ([a-z][a-z0-9-]*))?"
                         r"((?: --[a-z0-9-]+(?: '[^']*'| <[^>]*>| [\w./,-]+)?)*)")


def flags_of(sub, verb):
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="sub")
    for module in (approve_spec, graph, init, judges, review, review_plan, runcard, scan):  # judges: U11's wiring
        module.register(subs)
    target = subs.choices[sub]
    if verb:
        target = next(a for a in target._actions
                      if isinstance(a, argparse._SubParsersAction)).choices[verb]
    return {flag for a in target._actions for flag in a.option_strings}


def test_skill_body_form_and_helper_calls():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\nname: review-plan\n")
    body = text.split("---", 2)[2]
    assert len(body.encode("utf-8")) <= 24_000
    assert "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first." in body
    assert "`${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`" in body
    calls = HELPER_CALL.findall(body)
    assert {(s, v) for s, v, _ in calls} >= {
        ("init", ""), ("runcard", "open"), ("runcard", "close"), ("review-plan", "due"),
        ("review-plan", "set-input"), ("review-plan", "proportion-input"), ("review", "open"),
        ("review", "record"), ("review", "settle"), ("review", "status"), ("review", "rule"),
        ("approve-spec", ""), ("graph", ""), ("scan", "")}
    for sub, verb, rest in calls:
        missing = set(re.findall(r"--[a-z0-9-]+", rest)) - flags_of(sub, verb or None)
        assert not missing, (sub, verb, missing)
    for needle in ("--reviewer set", "once per round", "superegm:readiness", "concurrently",
                   "skills/review-spec/references/review_loop.md",
                   "resources/document_standards/handoff-standard.md", "plan-<unit>-c<n>",
                   "ends the invocation for that unit", "--void", "/superegm:review-spec",
                   "/superegm:file", "pauses the owner", "readiness,proportion,set", "superegm:zoom-out",
                   "references/proportion.md", "proportion-input", "plan/scan/<unit>.json", "question 11"):
        assert needle in body, needle
    assert "merge" not in body.lower() and "gh issue create" not in body


Q11 = ("Is the body no longer than the decisions the builder cannot make alone: no fenced test the signature and "
       "assertions already determine, no Implement line that restates the test, no Step a parametrized sibling "
       "covers, no prose table that should be test data?")
PAIR = "resolved in favour of the shorter form that keeps the test honest"
CASES = [
    (STANDARD, "Modified by SuperEGM (gsVAM), 2026: questions 8–11, severities high|medium|low, the fix-design path.", True),
    (STANDARD, "The Eleven Questions", True),
    (STANDARD, "8.  **Interfaces present and consistent.**", True),
    (STANDARD, "9.  **Steps complete, DoD item 1 present.**", True),
    (STANDARD, "10. **Global constraints and review focus present.**", True),
    (STANDARD, "11. **Proportion.** " + Q11, True),
    (STANDARD, "high: the body cannot be filed as written", True),
    (STANDARD, "`approve-spec --void`", True),
    (STANDARD, "returns to `review-spec`", True),
    (STANDARD, "the spec's `## Units`", True),
    (STANDARD, PAIR, True),
    (STANDARD, "Stage 10", False), (STANDARD, "Stage 9", False), (STANDARD, "egm-review", False),
    (STANDARD, "egm-handoff", False), (STANDARD, "Blocker", False), (STANDARD, "Major", False),
    (STANDARD, "Nit", False), (STANDARD, "Detailed Implementation Plan", False),
    (SKILL, "readiness test", False), (SKILL, "gate --accept", False), (SKILL, "Stage 10", False),
    (SKILL, "two consecutive clean", False), (SKILL, "synthesizer", False), (SKILL, "Codex", False),
    (SKILL, "egm-review-loop", False), (SKILL, "egm-resolve", False), (SKILL, "Blocker", False),
    (SCENARIOS, 'skill: "review-plan"', True),
    (SCENARIOS, 'scenario_id: "set_runs_once_per_round"', True),
    (SCENARIOS, 'scenario_id: "stalled_unit_ends_the_invocation"', True),
    (SCENARIOS, 'scenario_id: "fix_design_voids_the_approval"', True),
    (SCENARIOS, "Stage 10", False),
    (PROPORTION, Q11, True), (PROPORTION, "plan/scan/<unit>.json", True),
    (PROPORTION, "names the Step and the bytes it would remove", True),
    (PROPORTION, "`medium` at most", True), (PROPORTION, "never block alone", True), (PROPORTION, PAIR, True),
]


@pytest.mark.parametrize("path,needle,present", CASES, ids=[f"{p.name}:{n[:40]}" for p, n, _ in CASES])
def test_files_name_the_new_forms_and_not_the_retired_ones(path, needle, present):
    assert (needle in path.read_text(encoding="utf-8")) is present, needle


def test_proportion_input(planned):
    w = planned
    write(w.store.path("unit", "U02").parent / "plan/scan/U02.json", json.dumps(
        {"bytes": 900, "fenced_share": 0.1, "steps": 1, "spec_range_bytes": 300, "ratio": 3.0, "warnings": []}))
    code, out = w.run("review-plan", "proportion-input", "--unit", "U02", "--spec", str(w.spec))
    assert code == 0, out
    assert out.index(body("U02", "U01")) < out.index('"spec_range_bytes": 300') < out.index("| U02 | the worker | U01 | S |")
    assert "## 1. Intent" not in out and "| U03 | the admin | U02 | S |" not in out


TIER_CHECK = ["## The tier", "the `Tier:` word on the body's `Scope:` line", "a body without it reads doable",
              "whose open choices contradict its tier", "| U<nn> Scope | regression: no | tier: <reason>",
              "an `easy` or `doable` body with a `D<n>` item or an Implement line leaving a design choice",
              "a `difficult` body whose Steps are all mechanical with pinned signatures", "`medium` at most, never blocking alone",
              "`difficult` when the Steps leave a design choice open, the unit holds a novel algorithm or an unverified platform behaviour, or it consumes the interfaces of more than one subsystem",
              "`easy` when the Steps are mechanical with pinned signatures and no open choice"]


@pytest.mark.parametrize("needle", TIER_CHECK)
def test_the_proportion_brief_names_the_tier_check(needle):
    assert needle in PROPORTION.read_text(encoding="utf-8"), needle
