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

REPO = Path(__file__).resolve().parents[2]

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
  """A spec cycle reviewing respec R1 on `spec`'s bytes, committed first (a respec round records `HEAD`'s spec), recorded
  clean by its two reviewers when `converged`."""
  world.spec = spec
  cid = world.card("review-spec")
  text = spec.read_text(encoding="utf-8")
  git(["add", "-A"], world.repo)
  git(["commit", "--allow-empty", "-qm", "respec draft"], world.repo)
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


RETRY = BASE[:BASE.index("## 5. Units\n")] + ["## 8. Retry\n", "\n", "Max retries: 3\n", "\n"] \
  + [f"Filler {n}.\n" for n in range(8)] + ["\n", "## 9. Untouched section\n", "\n", "Nothing here.\n", "\n"] \
  + BASE[BASE.index("## 5. Units\n"):]


def test_respec_review_evidence_panel_and_cap(world):
  # a respec cycle reviews the diff from the latest approval's commit to HEAD and the sections it touches
  spec, st = respec_world(world, [(RETRY, None)])
  open_respec(st)
  approved(world, spec, replace(RETRY, "Max retries: 3", "Max retries: 4"), "draft")
  world.spec = spec
  cid = world.card("review-spec")
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", spec, "--reviewers", "design,zoom-out",
                        "--astra", "on", "--respec", "R1", "--runcard", cid)
  assert code == 1 and "zoom-out is not on a respec panel" in out
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", spec, "--reviewers", "design,codebase-details",
                        "--astra", "on", "--respec", "R2", "--runcard", cid)
  assert code == 1 and "respec R2 is not open" in out
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", spec, "--reviewers", "design,codebase-details",
                        "--astra", "on", "--respec", "R1", "--runcard", cid)
  assert code == 0, out
  rid = out.splitlines()[0]
  cycle = json.loads(st.path("reviews", rid, "review.json").read_text(encoding="utf-8"))
  panel = [{"name": name} for name in cycle["reviewers"]]
  code, evidence = world.run("review", "scope", "--review", rid, "--runcard", cid)
  assert code == 0, evidence
  assert [m["name"] for m in panel] == ["design", "codebase-details", "astra"] and cycle["cap"] == 2
  assert "+Max retries: 4" in evidence and "## 9. Untouched section" not in evidence
  assert cycle["respec"] == "R1" and "changed" in evidence and "neighbour" not in evidence


R1_TEXT = replace(BASE, "Delay is 5s.", "Delay is 6s.")
STARTED = "2026-11-13T00:00:00Z"


def commit_at(world, monkeypatch, name, when):
  """A commit of `name` whose committer time is `when`; its sha."""
  monkeypatch.setenv("GIT_COMMITTER_DATE", when)
  (world.repo / name).write_text(name, encoding="utf-8")
  git(["add", name], world.repo)
  git(["commit", "-qm", name], world.repo)
  monkeypatch.delenv("GIT_COMMITTER_DATE")
  return git(["rev-parse", "HEAD"], world.repo).strip()


def launch(status="exited 0", head=None, builder_status=None, respecs=("R1",), started_at=STARTED):
  return {"round": 1, "status": status, "started_at": started_at, "respecs": list(respecs), "reason": "respec",
          **({"head": head} if head else {}), "builder_status": builder_status}


def marks_world(world, monkeypatch, case):
  """Handoff `HID` with respec R1 applied (`R1_TEXT`), touching U2, as `case` sets U2 up."""
  old = commit_at(world, monkeypatch, "old.txt", "2026-11-10T00:00:00Z")
  new = commit_at(world, monkeypatch, "new.txt", "2026-11-14T00:00:00Z")
  units = {u: {"id": u, "design_range": design_range(BASE, h)} for u, h in SECTIONS.items()}
  filed = "unfiled" not in case
  if case == "unfiled, corrected names R1":
    units["U2"] |= {"corrected": ["R1"], "rendered_under": 2}
  elif case == "unfiled, later render without corrected":
    units["U2"] |= {"corrected": [], "rendered_under": 1}
  head = new if case == "saved head committed after a launch naming R1 started" else old
  state_units = {"U0": MERGED_U1["U0"], "U1": {"number": 11}, "U3": {},
                 "U2": {"number": 12, "pr": {"number": 22, "head": head}} if filed else {}}
  spec, st = respec_world(world, [(BASE, None), (R1_TEXT, "R1")], {"R1": ["U2"]}, units=units, state_units=state_units)
  launches = {
    "saved head committed after a launch naming R1 started": [launch("exited 1")],
    "launch naming R1 failed before pushing": [launch("exited 1")],
    "saved head older than every launch naming R1": [launch("exited 1"), launch("running", started_at="2026-11-13T06:00:00Z")],
    "exit-0 DONE launch recorded head == saved head": [launch(head=old, builder_status="DONE")],
    "exit-0 DONE_WITH_CONCERNS launch recorded head == saved head": [launch(head=old, builder_status="DONE_WITH_CONCERNS")],
    "exit-0 BLOCKED launch, same head": [launch(head=old, builder_status="BLOCKED")],
    "exit-0 NEEDS_CONTEXT launch, same head": [launch(head=old, builder_status="NEEDS_CONTEXT")],
  }.get(case)
  if filed:  # filed at R1's approval: the approval wrote U2's comment file
    core.atomic_write(st.path("file", "respec_comment_U2_R1.md"), "**Spec correction R1** for U2\n")
  if launches:
    core.atomic_write(st.path("launches", "U2"), {"unit": "U2", "launches": launches})
  if case == "filed touched, unit stopped":
    core.atomic_write(st.path("foreman", "U2"), {"dispatch_id": None, "rounds": [], "decisions": [], "rulings": [],
                                                 "stopped": {"by": "owner", "reason": "x", "at": STARTED}})
  return spec, st


@pytest.mark.parametrize("case, mark", [
  ("unfiled touched", "replan: R1"), ("unfiled, corrected names R1", None), ("unfiled, later render without corrected", "replan: R1"),
  ("filed touched", "respec: R1"), ("saved head committed after a launch naming R1 started", None),
  ("launch naming R1 failed before pushing", "respec: R1"), ("saved head older than every launch naming R1", "respec: R1"),
  ("exit-0 DONE launch recorded head == saved head", None), ("exit-0 DONE_WITH_CONCERNS launch recorded head == saved head", None), ("exit-0 BLOCKED launch, same head", "respec: R1"),
  ("exit-0 NEEDS_CONTEXT launch, same head", "respec: R1"), ("filed touched, unit stopped", None)])
def test_marks_derived_and_cleared(world, monkeypatch, case, mark):
  # marks are derived on every read; state.json is never written
  from superegm import respec
  spec, st = marks_world(world, monkeypatch, case)
  handoff = HID
  state_bytes_before = st.path("state").read_bytes()
  assert respec.marks(st, handoff).get("U2") == mark and st.path("state").read_bytes() == state_bytes_before
  state_bytes_after = st.path("state").read_bytes()
  assert respec.marks(st, handoff).get("U2") == mark and state_bytes_after == state_bytes_before
  assert "U0" not in respec.marks(st, handoff)


def actionable_world(world, monkeypatch, case):
  """Respec R1, raised by U2 and touching filed U2, as `case` sets it up; `(spec, st, opened)`, `opened` the ids
  `respec.open` returned before R1's approval (an applied respec is no longer open), the store then holding it."""
  old = commit_at(world, monkeypatch, "old.txt", "2026-11-10T00:00:00Z")
  state_units = {"U0": MERGED_U1["U0"], "U1": {"number": 11}, "U3": {}, "U2": {"number": 12, "pr": {"number": 22, "head": old}}}
  spec, st = respec_world(world, [(BASE, None), (R1_TEXT, "R1")], {"R1": ["U2"]}, state_units=state_units)
  open_respec(st)
  core.atomic_write(st.path("file", "respec_comment_U2_R1.md"), "**Spec correction R1** for U2\n")  # filed at R1's approval
  if case == "handoff superseded":
    another_handoff(st, spec)
  if case == "unit stopped":
    core.atomic_write(st.path("foreman", "U2"), {"dispatch_id": None, "rounds": [], "decisions": [], "rulings": [],
                                                 "stopped": {"by": "owner", "reason": "x", "at": STARTED}})
  if case == "pending owner decision":
    core.atomic_write(st.path("foreman", "U2"), {"dispatch_id": None, "rounds": [], "rulings": [], "decisions": [
      {"id": "U2-d1", "point": 2, "question": "respec R1?", "options": ["respec", "stop the unit"]}]})
  if case == "posted, unit's own launch live":
    core.atomic_write(st.path("file", "respec", "R1.U2.posted"), {"comment": 555})
    core.atomic_write(st.path("launches", "U2"), {"unit": "U2", "launches": [launch("running", builder_status=None)]})
  if case.startswith("max_in_flight 1"):
    config = world.repo / ".superegm/config.json"
    config.write_text(json.dumps(dict(json.loads(config.read_text(encoding="utf-8")), max_in_flight=1)), encoding="utf-8")
    core.atomic_write(st.path("launches", "U1"), {"unit": "U1", "launches": [launch("running", respecs=())]})
  from superegm import respec
  path = st.path("approvals", core.spec_slug(spec))
  full = json.loads(path.read_text(encoding="utf-8"))
  core.atomic_write(path, dict(full, entries=[e for e in full["entries"] if e.get("kind") != "respec"]))
  opened = [r["id"] for r in respec.open(st, HID)]
  core.atomic_write(path, full)
  return spec, st, opened


@pytest.mark.parametrize("case, opened, items", [
  ("open, unposted, idle unit", ["R1"], [("post", "R1", "U2"), ("relaunch", "R1", "U2")]),
  ("posted, unit's own launch live", ["R1"], []), ("unit stopped", [], []), ("handoff superseded", [], []),
  ("pending owner decision", ["R1"], []),
  ("max_in_flight 1, U1's builder running, clean U2 touched", ["R1"], [("post", "R1", "U2"), ("relaunch", "R1", "U2")])])
def test_withdrawn_respec_and_actionable(world, monkeypatch, case, opened, items):
  # a withdrawn respec is not open; a relaunch is only queued for launch's ready-again set, never launched here
  from superegm import respec
  spec, st, opened_before_approval = actionable_world(world, monkeypatch, case)
  handoff = HID
  launches_of_U2_before = snapshot(st.path("launches", "U2").parent)
  assert opened_before_approval == opened and respec.actionable(st, handoff) == items
  assert [r["id"] for r in respec.open(st, handoff)] == []  # applied once an approval names it
  launches_of_U2_after = snapshot(st.path("launches", "U2").parent)
  assert launches_of_U2_after == launches_of_U2_before
  if case != "handoff superseded":  # a card on the spec resolves the latest handoff, which holds no R1
    world.spec = spec
    cid = world.card("wave")
    posted_rc, out = world.run("respec", "posted", "--respec", "R1", "--unit", "U2", "--comment", "555", "--runcard", cid)
    respec_dir = st.path("file", "respec")
    assert posted_rc == 0 and (respec_dir / "R1.U2.posted").exists(), out
  if case == "open, unposted, idle unit":
    assert respec.actionable(st, handoff) == [("relaunch", "R1", "U2")]
  skill_text = (REPO / "skills/review-spec/SKILL.md").read_text(encoding="utf-8")
  assert all(p in skill_text for p in ("--respec R<n>", "one question at a time", "suggested answer", "approve-spec --respec R<n> --dry-run"))


# Round 2: the owner's rulings on the round-1 review (issue #169).


def test_unfiled_at_approval_then_filed_keeps_its_correction(world, monkeypatch):
  # filed or unfiled as of the approval naming R1 (its comment file), not state.json's current number
  from superegm import respec
  old = commit_at(world, monkeypatch, "old.txt", "2026-11-10T00:00:00Z")
  units = {u: {"id": u, "design_range": design_range(BASE, h)} for u, h in SECTIONS.items()}
  units["U2"] |= {"corrected": ["R1"], "rendered_under": 2}
  state_units = {"U0": MERGED_U1["U0"], "U1": {"number": 11}, "U3": {}, "U2": {"number": 12, "pr": {"number": 22, "head": old}}}
  spec, st = respec_world(world, [(BASE, None), (R1_TEXT, "R1")], {"R1": ["U2"]}, units=units, state_units=state_units)
  assert "U2" not in respec.marks(st, HID) and respec.actionable(st, HID) == []
  units["U2"]["corrected"] = []  # filed without its correction: the replan mark stands, no comment to post
  core.atomic_write(st.path("units"), {"handoff_id": HID, "units": units})
  assert respec.marks(st, HID).get("U2") == "replan: R1" and respec.actionable(st, HID) == []


def test_replan_mark_stands_after_a_render_without_corrected(world, monkeypatch):
  # rendered_under reaching R1's entry count clears nothing: only `corrected` naming R1 does
  from superegm import respec
  units = {u: {"id": u, "design_range": design_range(BASE, h)} for u, h in SECTIONS.items()}
  units["U2"] |= {"corrected": [], "rendered_under": 2}
  spec, st = respec_world(world, [(BASE, None), (R1_TEXT, "R1")], {"R1": ["U2"]}, units=units)
  assert respec.marks(st, HID).get("U2") == "replan: R1"


def new_handoff(st, spec, hid="x-def456"):
  """A later opening approval of handoff `hid`, naming no respec."""
  path = st.path("approvals", core.spec_slug(spec))
  record = json.loads(path.read_text(encoding="utf-8"))
  last = {k: v for k, v in record["entries"][-1].items() if k not in ("respec", "ranges")}
  record["entries"].append(dict(last, handoff_id=hid, kind="opening"))
  core.atomic_write(path, record)
  core.atomic_write(st.path("handoffs", hid), {"id": hid, "spec": str(spec), "opened_at": None, "closed_at": None})
  return core.handoff_store(st, hid)


def test_respec_ids_are_per_handoff(world):
  # an R1 open in a new handoff, after an older handoff applied its own R1, opens a respec review
  spec, st = respec_world(world, [(BASE, None), (R1_TEXT, "R1")], {"R1": ["U2"]})
  hs = new_handoff(st, spec)
  core.atomic_write(hs.path("file", "respec", "R1.open.json"), {"id": "R1", "unit": "U2", "comment_id": 902, "at": STARTED})
  approved(world, spec, replace(R1_TEXT, "Delay is 6s.", "Delay is 7s."), "draft")
  world.spec = spec
  cid = world.card("review-spec")
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", spec, "--reviewers", "design,codebase-details",
                        "--respec", "R1", "--runcard", cid)
  assert code == 0, out


def hand_cycle(st, spec, cid, rid, respec=None):
  core.atomic_write(st.path("reviews", rid, "review.json"), {
    "kind": "spec", "artifact": str(spec.resolve()), "cycle": int(rid.rsplit("-c", 1)[1]), "handoff_id": HID, "scope": "auto",
    "reviewers": ["design", "codebase-details"], "cap": 2, "runcard": cid, "artifact_sha256": None, "astra_incomplete": 0,
    "converged": "no", "converged_round": None, "rulings": [], **({"respec": respec, "base": "HEAD"} if respec else {})})


@pytest.mark.parametrize("held, asked, expect", [
  ("R1", "R1", "resumed"), ("R1", "R2", "spec-x-c2 is open"), (None, "R1", "spec-x-c2 is open")])
def test_respec_review_resumes_only_its_own_cycle(world, held, asked, expect):
  # --respec is read before the resume branch: the same respec's open cycle resumes, any other spec cycle refuses
  spec, st = respec_world(world, [(BASE, None)])
  open_respec(st, "R1")
  open_respec(st, "R2")
  approved(world, spec, replace(BASE, "Delay is 5s.", "Delay is 6s."), "draft")
  world.spec = spec
  cid = world.card("review-spec")
  hand_cycle(st, spec, cid, "spec-x-c2", held)
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", spec, "--reviewers", "design,codebase-details",
                        "--respec", asked, "--runcard", cid)
  if expect == "resumed":
    assert code == 0 and out.splitlines()[0] == "spec-x-c2", out
  else:
    assert code == 1 and expect in out and not st.path("reviews", "spec-x-c3", "review.json").exists()


def test_respec_round_records_the_committed_spec(world):
  # the evidence is HEAD's diff, so a round refuses a working-tree spec that differs from HEAD
  spec, st = respec_world(world, [(BASE, None)])
  open_respec(st)
  approved(world, spec, replace(BASE, "Delay is 5s.", "Delay is 6s."), "draft")
  world.spec = spec
  cid = world.card("review-spec")
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", spec, "--reviewers", "design,codebase-details",
                        "--respec", "R1", "--runcard", cid)
  assert code == 0, out
  rid = out.splitlines()[0]
  committed = spec.read_text(encoding="utf-8")
  spec.write_text("".join(replace(BASE, "Delay is 5s.", "Delay is 9s.")), encoding="utf-8")  # an uncommitted correction
  findings = world.repo.parent / "clean.txt"
  findings.write_text("", encoding="utf-8")
  argv = ["review", "record", "--review", rid, "--round", "1", "--reviewer", "design", "--runcard", cid,
          "--findings", str(findings), "--isolation", "clean", "--model", "inherit:opus", "--effort", "inherit:high"]
  code, out = world.run(*argv)
  assert code == 1 and "differs from HEAD" in out
  spec.write_text(committed, encoding="utf-8")
  code, out = world.run(*argv)
  assert code == 0, out


PLAN_BODIES = {
  "U1": "### U1: Queue\n\nInterfaces\n- Produces: `retry(job)` returning the delay\n\n## Issue body as posted\n\n````markdown\n"
        "## Interfaces\n- Produces: `other(x)`\n````\n",
  "U2": "### U2: Deliver\n\nInterfaces\n- Consumes: send(job) (U9)\n\n## Issue body as posted\n\n````markdown\n"
        "## Interfaces\n- Consumes: `retry(job)` from U1\n````\n",
  "U3": "### U3: Admin\n\nInterfaces\n- Consumes: retry(job) (U1)\n\n## Issue body as posted\n\n````markdown\n"
        "## Interfaces\n- Consumes: `other(x)` from U9\n````\n",
}


def test_interfaces_read_from_the_plan_section(world):
  # the plan section's Interfaces lines count; the fenced issue body graph writes does not
  from superegm import respec
  spec, st = respec_world(world, [(BASE, None)])
  for uid, body in PLAN_BODIES.items():
    core.atomic_write(st.path("unit", uid), body)
  draft = replace(BASE, "- Produces: `retry(job)` returning the delay", "- Produces: `retry(job)` returning the delay in ms")
  assert respec.touched(st, HID, "".join(draft))["touched"] == ["U1", "U3"]


FOLLOW_ROW = "| U9 | Queue follow-up (Follows: U1) | U1 | S |"


@pytest.mark.parametrize("row, rc", [
  ("new Units row", 0), ("fenced example row", 1), ("existing row edited", 1), ("new row following another unit", 1)])
def test_merged_overlap_follow_up_row(world, row, rc):
  # only a new row of the Units table whose Follows names the merged unit satisfies the refusal
  spec, st = respec_world(world, [(PADDED, None)], state_units=MERGED_U1)
  open_respec(st)
  start = PADDED.index("## 1. Queue\n")
  draft = PADDED[:start] + [line.rstrip("\n") + " v2\n" if line.strip() else "Gap.\n" for line in PADDED[start:start + 5]] \
    + PADDED[start + 5:]
  if row == "new Units row":
    draft = draft + [FOLLOW_ROW + "\n"]
  elif row == "fenced example row":
    draft = replace(draft, "Preamble goal line.", ["```", FOLLOW_ROW, "```"])
  elif row == "existing row edited":
    draft = replace(draft, "| U1 | queue | — | S |", "| U1 | queue (Follows: U1) | — | S |")
  else:
    draft = draft + [FOLLOW_ROW.replace("Follows: U1", "Follows: U0") + "\n"]
  spec.write_text("".join(draft), encoding="utf-8")
  respec_cycle(world, spec, st)
  code, out = world.run("approve-spec", "--spec", spec, "--respec", "R1", "--yes")
  assert code == rc, out
  if rc:
    assert "U1 is merged and overlaps" in out and not st.path("file", "respec", "R1.json").exists()
  else:
    assert "follow_up: U1 overlaps docs/specs/x.md:40-44: row U9" in out


TRIAGE = BASE[:BASE.index("## 5. Units\n")] + ["## Triage\n", "\n", "- defer docs-only findings\n", "\n"] \
  + BASE[BASE.index("## 5. Units\n"):]
FENCED_ROUNDS = ["# X\n", "\n", "```\n", "## Example\n", "```\n", "\n", "Rounds: 3\n", "\n", "## 1. A\n", "\n", "Text.\n"]


@pytest.mark.parametrize("old, new, field", [
  (TRIAGE, replace(TRIAGE, "- defer docs-only findings", "- defer every finding"), "triage"),
  (TRIAGE, replace(TRIAGE, "Delay is 5s.", ["Delay grows."]), None),
  (FENCED_ROUNDS, replace(FENCED_ROUNDS, "Rounds: 3", "Rounds: 4"), "Rounds"),
  (FENCED_ROUNDS, replace(FENCED_ROUNDS, "Text.", "Other text."), None)])
def test_frozen_field_change(old, new, field):
  # the triage section's body alone, not its position; a fenced heading before the Rounds line hides nothing
  from superegm import approve_spec
  assert approve_spec.frozen_change("".join(old), "".join(new)) == field


def test_frozen_triage_refusal(world):
  spec, st = respec_world(world, [(TRIAGE, None)])
  open_respec(st)
  spec.write_text("".join(replace(TRIAGE, "- defer docs-only findings", "- defer every finding")), encoding="utf-8")
  respec_cycle(world, spec, st)
  store_before = snapshot(world.artifacts)
  code, out = world.run("approve-spec", "--spec", spec, "--respec", "R1", "--yes")
  assert code == 1 and "approve-spec: respec R1: changes the frozen triage: void and re-approve" in out
  assert snapshot(world.artifacts) == store_before


@pytest.mark.parametrize("argv, err", [
  (["--respec", "1", "--unit", "U2"], "respec posted: 1 is not R<n>"),
  (["--respec", "R7", "--unit", "U2"], "respec posted: respec R7 is not applied"),
  (["--respec", "R1", "--unit", "U3"], "respec posted: U3 is not touched by R1")])
def test_respec_posted_refusals(world, monkeypatch, argv, err):
  spec, st, _ = actionable_world(world, monkeypatch, "open, unposted, idle unit")
  world.spec = spec
  cid = world.card("wave")
  code, out = world.run("respec", "posted", *argv, "--comment", "555", "--runcard", cid)
  assert code == 1 and err in out and not list(st.path("file", "respec").glob("*.posted"))


def test_respec_approval_honours_the_leavemealone_flag(world):
  # `--leavemealone` approves without `--yes`, as the main approval does
  spec, st = respec_world(world, [(BASE, None)], state_units={"U0": MERGED_U1["U0"], "U1": {"number": 11}, "U2": {}, "U3": {}})
  open_respec(st)
  spec.write_text("".join(replace(BASE, "Delay is 5s.", "Delay is 6s.")), encoding="utf-8")
  respec_cycle(world, spec, st)
  code, out = world.run("approve-spec", "--spec", spec, "--respec", "R1", "--leavemealone")
  entries = json.loads(st.path("approvals", core.spec_slug(spec)).read_text(encoding="utf-8"))["entries"]
  assert code == 0 and entries[-1].get("respec") == "R1", out


def test_skill_respec_dry_run_and_confirmation_text():
  text = (REPO / "skills/review-spec/SKILL.md").read_text(encoding="utf-8")
  assert "each `follow_up:`" in text and "each `follow-up:`" not in text
  step = text[text.index("4. **Approve.**"):text.index("## Data notice")]
  assert "--yes" in step and "writes nothing" in step and "Stop" in step
