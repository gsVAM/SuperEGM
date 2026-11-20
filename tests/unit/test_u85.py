# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U85's tests, spec §7.6 "The correction", "The review", "The approval" and "The units it touches": the respec review, approval and touched units.

"""U85: `respec.touched` (the range, shared-text, uncovered-range, Interfaces and prior-respec rules), the
`approve-spec --respec` refusals, entry and dry run, the respec review's evidence, panel and cap, the derived
marks, the open and actionable respecs and `respec posted`."""

import argparse
import hashlib
import json
from pathlib import Path

import pytest

import superegm as core
from conftest import git

SPEC_REL, HID = "docs/specs/x.md", "x-abc123"

BASE = """# X

Preamble goal line.

## Global constraints

- No new deps ok
- Shared rule here

## 0. Old

Old text.

## 1. Queue

Queue keeps jobs.
assert result is None
- Log every retry

## 2. Deliver

Deliver sends jobs.
Delay is 5s.

## 3. Admin

Admin lists jobs.

## 4. Limits

- Max retries: 3
assert timeout == 3
- Produces: `retry(job)` returning the delay

```
call(
  x
)
```

## 5. Units

| Unit | Scope | Blocked by | Size |
| --- | --- | --- | --- |
| U1 | queue | — | S |
""".splitlines(keepends=True)

CODE = "## Steps\n\n```\ncall(\n  x\n)\n```\n"
BODIES = {
  "U0": "### U0: Old\n\nOld body.\n",
  "U1": "### U1: Queue\n\n## Global constraints\n- No new deps ok\n- Log every retry\n\n## Interfaces\n"
        "- Produces: `retry(job)` returning the delay\n\n" + CODE,
  "U2": "### U2: Deliver\n\n## Global constraints\n- Log every retry\n- Max retries: 3\n\n" + CODE,
  "U3": "### U3: Admin\n\n## Global constraints\n- No new deps ok\n- Log every retry\n\n## Interfaces\n"
        "- Consumes: `retry(job)` from U1\n\nassert timeout == 3\nassert result is None\n\n" + CODE,
}
SECTIONS = {"U0": "## 0. Old", "U1": "## 1. Queue", "U2": "## 2. Deliver", "U3": "## 3. Admin"}


def design_range(lines, heading):
  """The section's lines, its heading to the line before the next H2 (1-based, inclusive)."""
  start = lines.index(heading + "\n") + 1
  end = next((n for n in range(start + 1, len(lines) + 1) if lines[n - 1].startswith("## ")), len(lines) + 1) - 1
  return {"path": SPEC_REL, "start": start, "end": end, "heading": heading}


def replace(lines, old, new):
  """`lines` with the line `old` replaced by `new` (None deletes it), or `new` lines inserted after `old`."""
  out = list(lines)
  at = out.index(old + "\n")
  if new is None:
    del out[at]
  elif isinstance(new, list):
    out[at + 1:at + 1] = [n + "\n" for n in new]
  else:
    out[at] = new + "\n"
  return out


def store_of(world, spec):
  core.CURRENT_ARGS = argparse.Namespace(design=str(spec))
  return core.store(world.repo)


def approved(world, spec, lines, kind="opening", respec=None, review="spec-x-c1"):
  """Commit `lines` as the spec and return its approval entry."""
  text = "".join(lines)
  spec.write_text(text, encoding="utf-8")
  git(["add", "-A"], world.repo)
  git(["commit", "-qm", f"spec {kind}"], world.repo)
  entry = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "commit": git(["rev-parse", "HEAD"], world.repo).strip(),
           "runcard": None, "review": review, "approved_at": "2026-11-12T00:00:00Z", "handoff_id": HID, "kind": kind,
           "voided_by": None, "escalated": [], "rounds": 3, "triage": None, "mode": "normal"}
  return entry | ({"respec": respec} if respec else {})


def respec_world(world, history, touched_of=None, units=None, state_units=None):
  """A handoff `HID` of `docs/specs/x.md` whose approval history is `history` (`[(lines, respec or None)]`, the first the
  opening), the four units' ranges in the opening's coordinates, their bodies, U0 merged and U1 filed; each prior
  respec's `respec/R<k>.json` with `touched_of[R<k>]`."""
  spec = world.repo / SPEC_REL
  spec.parent.mkdir(parents=True, exist_ok=True)
  entries = [approved(world, spec, lines, "respec" if rid else "opening", rid) for lines, rid in history]
  st0 = store_of(world, spec)
  core.atomic_write(st0.path("approvals", core.spec_slug(spec)), {"path": str(spec), "entries": entries})
  core.atomic_write(st0.path("handoffs", HID), {"id": HID, "spec": str(spec), "opened_at": "2026-11-12T00:00:00Z", "closed_at": None})
  st = store_of(world, spec)
  assert st.handoff_id == HID
  opening = history[0][0]
  records = units or {u: {"id": u, "design_range": design_range(opening, h)} for u, h in SECTIONS.items()}
  core.atomic_write(st.path("units"), {"handoff_id": HID, "units": records})
  core.atomic_write(st.path("state"), {"handoff_id": HID, "units": state_units or {
    "U0": {"number": 10, "pr": {"number": 20, "head": "e" * 40, "merged_at": "2026-11-11T00:00:00Z"}},
    "U1": {"number": 11}, "U2": {}, "U3": {}}})
  for uid, body in BODIES.items():
    core.atomic_write(st.path("unit", uid), body)
  for rid, touched in (touched_of or {}).items():
    core.atomic_write(st.path("file", "respec", f"{rid}.json"), {"touched": touched, "untouched": [], "follow_ups": [],
                                                                "line_map": [], "merged_review": []})
  return spec, st


R1_MOVED = replace(BASE, "Preamble goal line.", ["Inserted one.", "Inserted two.", "Inserted three.", "Inserted four.", "Inserted five."])
R1_ADDED = replace(BASE, "- Max retries: 3", ["Backoff doubles."])

CHANGES = {
  "one of three units' Design ranges": ([BASE], {}, lambda: replace(BASE, "Delay is 5s.", "Delay is 6s.")),
  "U2's range after a first respec moved it": ([BASE, R1_MOVED], {"R1": []}, lambda: replace(R1_MOVED, "Delay is 5s.", "Delay is 6s.")),
  "the preamble": ([BASE], {}, lambda: replace(BASE, "Preamble goal line.", "Preamble goal line, revised.")),
  "a Global constraints line inside U1's range": ([BASE], {}, lambda: replace(BASE, "- Log every retry", "- Log every retry twice")),
  "a blank line": ([BASE], {}, lambda: BASE[:BASE.index("- Max retries: 3\n") - 1] + BASE[BASE.index("- Max retries: 3\n"):]),
  "a fence marker": ([BASE], {}, lambda: replace(BASE, "```", "```text")),
  "a `)` line": ([BASE], {}, lambda: replace(BASE, ")", "])")),
  "a 16-character `## Global constraints` line": ([BASE], {}, lambda: replace(BASE, "- No new deps ok", "- No new deps at all")),
  "`- Max retries: 3` under U2's Global constraints": ([BASE], {}, lambda: replace(BASE, "- Max retries: 3", "- Max retries: 4")),
  "`assert timeout == 3` quoted by U3": ([BASE], {}, lambda: replace(BASE, "assert timeout == 3", "assert timeout == 4")),
  "`assert result is None` in U1's range, quoted by U3": ([BASE], {}, lambda: replace(BASE, "assert result is None", "assert result == []")),
  "a line R1 added, changed by R2": ([BASE, R1_ADDED], {"R1": ["U2"]}, lambda: replace(R1_ADDED, "Backoff doubles.", "Backoff triples.")),
  "an Interfaces line U1 produces, U3 consumes": ([BASE], {}, lambda: replace(BASE, "- Produces: `retry(job)` returning the delay",
                                                                              "- Produces: `retry(job)` returning the delay in ms")),
}


@pytest.mark.parametrize("change, touched, merged_review", [
  ("one of three units' Design ranges", ["U2"], []), ("U2's range after a first respec moved it", ["U2"], []),
  ("the preamble", ["U1", "U2", "U3"], ["U0"]), ("a Global constraints line inside U1's range", ["U1", "U2", "U3"], []),
  ("a blank line", [], []), ("a fence marker", [], []), ("a `)` line", [], []),
  ("a 16-character `## Global constraints` line", ["U1", "U3"], []), ("`- Max retries: 3` under U2's Global constraints", ["U2"], []),
  ("`assert timeout == 3` quoted by U3", ["U3"], []), ("`assert result is None` in U1's range, quoted by U3", ["U1", "U3"], []),
  ("a line R1 added, changed by R2", ["U2"], []), ("an Interfaces line U1 produces, U3 consumes", ["U1", "U3"], [])])
def test_touched_units(world, change, touched, merged_review):
  # range ∩ diff in the previous approval's coordinates, plus shared text, uncovered ranges, Interfaces and prior respecs' lines
  from superegm import respec
  texts, touched_of, draft = CHANGES[change]
  assert len("- No new deps ok") == 16
  spec, st = respec_world(world, [(t, f"R{n}" if n else None) for n, t in enumerate(texts)], touched_of)
  result = respec.touched(st, HID, "".join(draft()))
  assert (sorted(result["touched"]), result["merged_review"]) == (touched, merged_review)
  assert set(result) == {"touched", "untouched", "follow_ups", "line_map", "merged_review"}
  assert sorted(result["untouched"]) == sorted(set(SECTIONS) - set(touched))


def snapshot(root):
  return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}


def respec_cycle(world, spec, st, converged=True, rid="spec-x-c2"):
  """A spec cycle reviewing respec R1 on `spec`'s working bytes, recorded clean by its two reviewers when `converged`."""
  world.spec = spec
  cid = world.card("review-spec")
  text = spec.read_text(encoding="utf-8")
  core.atomic_write(st.path("reviews", rid, "review.json"), {
    "kind": "spec", "artifact": str(spec), "cycle": int(rid.rsplit("-c", 1)[1]), "handoff_id": None, "scope": "auto",
    "reviewers": ["design", "codebase-details"], "cap": 2, "runcard": cid, "respec": "R1",
    "artifact_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "astra_incomplete": 0, "converged": "no",
    "converged_round": None, "rulings": []})
  if converged:
    for reviewer in ("design", "codebase-details"):
      path = world.repo.parent / f"{rid}-1-{reviewer}.txt"
      path.write_text("", encoding="utf-8")
      code, out = world.run("review", "record", "--review", rid, "--round", "1", "--reviewer", reviewer, "--runcard", cid,
                            "--findings", str(path), "--isolation", "clean", "--model", "inherit:opus", "--effort", "inherit:high")
      assert code == 0, out
  return cid


def open_respec(st, rid="R1", unit="U2"):
  core.atomic_write(st.path("file", "respec", f"{rid}.open.json"),
                    {"id": rid, "unit": unit, "comment_id": 901, "at": "2026-11-13T00:00:00Z"})


PADDED = BASE[:3] + [f"Pad {n}.\n" for n in range(26)] + BASE[3:]
ROUNDS = BASE[:3] + ["Rounds: 3\n"] + BASE[3:]
MERGED_U1 = {"U0": {"number": 10, "pr": {"number": 20, "head": "e" * 40, "merged_at": "2026-11-11T00:00:00Z"}},
             "U1": {"number": 11, "pr": {"number": 21, "head": "d" * 40, "merged_at": "2026-11-11T00:00:00Z"}}, "U2": {}, "U3": {}}


def another_handoff(st, spec):
  """A later opening approval of handoff `x-def456`: `HID` is no longer the latest approval's."""
  path = st.path("approvals", core.spec_slug(spec))
  record = json.loads(path.read_text(encoding="utf-8"))
  record["entries"].append(dict(record["entries"][-1], handoff_id="x-def456", kind="opening"))
  core.atomic_write(path, record)
  core.atomic_write(st.path("handoffs", "x-def456"), {"id": "x-def456", "spec": str(spec), "opened_at": None, "closed_at": None})


@pytest.mark.parametrize("case, err", [
  ("unconverged", "approve-spec: respec R1: review spec-x-c2 not converged"),
  ("merged U1 overlaps, no follow-up row", "approve-spec: respec R1: U1 is merged and overlaps docs/specs/x.md:40-44: add a follow-up row"),
  ("Rounds: line changed", "approve-spec: respec R1: changes the frozen Rounds: void and re-approve"),
  ("latest approval of another handoff", "approve-spec: respec R1:")])
def test_approve_respec_refusals(world, case, err):
  # each refusal writes nothing: no entry, no respec/R1.json
  opening = {"merged U1 overlaps, no follow-up row": PADDED, "Rounds: line changed": ROUNDS}.get(case, BASE)
  spec, st = respec_world(world, [(opening, None)], state_units=MERGED_U1 if "merged" in case else None)
  open_respec(st)
  if case == "merged U1 overlaps, no follow-up row":
    start = PADDED.index("## 1. Queue\n")
    assert start + 1 == 40
    draft = PADDED[:start] + [line.rstrip("\n") + " v2\n" if line.strip() else "Gap.\n" for line in PADDED[start:start + 5]] \
      + PADDED[start + 5:]
  elif case == "Rounds: line changed":
    draft = replace(ROUNDS, "Rounds: 3", "Rounds: 4")
  else:
    draft = replace(BASE, "Delay is 5s.", "Delay is 6s.")
  spec.write_text("".join(draft), encoding="utf-8")
  respec_cycle(world, spec, st, converged=case != "unconverged")
  extra = []
  if case == "latest approval of another handoff":
    another_handoff(st, spec)
    extra = ["--handoff", HID]
  store_before = snapshot(world.artifacts)
  rc, stderr = world.run("approve-spec", "--spec", spec, "--respec", "R1", "--yes", *extra)
  store_after = snapshot(world.artifacts)
  assert rc == 1 and err in stderr and store_after == store_before
  assert not st.path("file", "respec", "R1.json").exists()


FROZEN = ["rounds", "triage", "mode"]


def test_approve_respec_writes_entry_and_touched(world, monkeypatch):
  # the entry copies every frozen field as --amend-units; R1.json and the comment files land in the same command
  from superegm import approve_spec
  state_units = {"U0": MERGED_U1["U0"], "U1": {"number": 11}, "U2": {"number": 12}, "U3": {}}
  spec, st = respec_world(world, [(BASE, None)], state_units=state_units)
  open_respec(st)
  spec.write_text("".join(replace(BASE, "Delay is 5s.", "Delay is 6s.")), encoding="utf-8")
  world.spec = spec
  world.card("review-spec")
  store_before = snapshot(world.artifacts)
  dry_rc, dry_out = world.run("approve-spec", "--spec", spec, "--respec", "R1", "--dry-run")
  store_after_dry = snapshot(world.artifacts)
  assert dry_rc == 0 and "touched: U2" in dry_out and "merged_review:" in dry_out and store_after_dry == store_before
  respec_cycle(world, spec, st)
  prev = json.loads(st.path("approvals", core.spec_slug(spec)).read_text(encoding="utf-8"))["entries"][-1]
  real = approve_spec.append_entry
  monkeypatch.setattr(approve_spec, "append_entry", lambda *a: (_ for _ in ()).throw(RuntimeError("crash")))
  with pytest.raises(RuntimeError):
    world.run("approve-spec", "--spec", spec, "--respec", "R1", "--yes")
  r1 = st.path("file", "respec", "R1.json")
  assert r1.exists() and len(json.loads(st.path("approvals", core.spec_slug(spec)).read_text(encoding="utf-8"))["entries"]) == 1
  monkeypatch.setattr(approve_spec, "append_entry", real)
  rc, out = world.run("approve-spec", "--spec", spec, "--respec", "R1", "--yes")
  assert rc == 0, out
  entries = json.loads(st.path("approvals", core.spec_slug(spec)).read_text(encoding="utf-8"))["entries"]
  entry, rerun_after_crash_entries = entries[-1], sum(e.get("kind") == "respec" for e in entries)
  r1_json = r1.read_text(encoding="utf-8")
  comment_file, = st.path("file", "x").parent.glob("respec_comment_*.md")
  assert entry["kind"] == "respec" and entry["respec"] == "R1" and {k: entry[k] for k in FROZEN} == {k: prev[k] for k in FROZEN}
  assert entry["review"] == "spec-x-c2" and entry["ranges"] == [[23, 23]] and entry["handoff_id"] == HID
  assert set(json.loads(r1_json)) == {"touched", "untouched", "follow_ups", "line_map", "merged_review"}
  assert comment_file.name == "respec_comment_U2_R1.md" and rerun_after_crash_entries == 1 and "file" in approve_spec.WRITES
  assert "-Delay is 5s." in comment_file.read_text(encoding="utf-8") and "+Delay is 6s." in comment_file.read_text(encoding="utf-8")
