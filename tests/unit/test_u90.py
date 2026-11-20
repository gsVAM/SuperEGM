# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U90's tests, spec §7.6 "The units it touches": a respec re-plans an unfiled unit.

"""U90: a `replan: R<n>` unit refused by `gate` and a resumed `apply`, routed to `plan` by `next`; an unfiled unit's
Design range rendered through each later respec's `line_map`; the `Corrected:` row recorded by `graph` alone, clearing
the mark."""

import hashlib
import json
from pathlib import Path

import pytest

import superegm as core
from conftest import UNITS, converge, git, handoff_store

SPEC_REL, HID = "docs/specs/s.md", "2026-11-12-s-abc123"
UNIT_IDS = {"U01": "U07", "U02": "U08", "U03": "U09"}


def spec_lines():
  """A 250-line spec: `## 7. Seven` at :110, `## 8. Eight` at :200, every other line `Line <n>.`; its `## Units` table
  after the numbered lines."""
  lines = [f"Line {n}." for n in range(1, 251)]
  lines[0], lines[109], lines[199] = "# S", "## 7. Seven", "## 8. Eight"
  return lines + ["", "## Units", "", "| Unit | Scope | Blocked by | Size |", "| --- | --- | --- | --- |",
                  *(f"| {u} | thing | — | S |" for u in UNIT_IDS.values())]


def inserted(lines, at, count):
  """`lines` with `count` new lines inserted before line `at` (1-based)."""
  return lines[:at - 1] + [f"Inserted {n}." for n in range(1, count + 1)] + lines[at - 1:]


def units_text(corrected=None):
  """conftest's three units as U07-U09 on `docs/specs/s.md`: U07 at :110-130 with a non-blocking D1, U08 at :200-240;
  `corrected` adds U07's `| Corrected | <value> |` row."""
  text = UNITS
  for old, new in UNIT_IDS.items():
    text = text.replace(old, new)
  text = text.replace("docs/designs/sample.md:13-15 (#### 1. src/webhooks/queue.ts)", f"{SPEC_REL}:110-130 (## 7. Seven)")
  text = text.replace("docs/designs/sample.md:17-19 (#### 2. src/webhooks/deliver.ts)", f"{SPEC_REL}:200-240 (## 8. Eight)")
  text = text.replace("docs/designs/sample.md:21-23 (#### 3. src/webhooks/admin.ts)", f"{SPEC_REL}:241-250 (## 8. Eight)")
  text = text.replace("Decide before build\n- none\n\n### U08",
                      "Decide before build\n- D1 Queue bound? options: (a) none; (b) 1000; owner: the user; default: (a); "
                      "blocking: no\n\n### U08", 1)
  text = text.replace("blocking: yes", "blocking: no")
  if corrected:
    text = text.replace("| Size | S |\n\nInterfaces\n- Produces: enqueue", f"| Size | S |\n| Corrected | {corrected} |\n\n"
                        "Interfaces\n- Produces: enqueue", 1)
  return text


def write_plan(world, corrected=None):
  spec = world.repo / SPEC_REL
  world.plan.write_text(f"# Handoff plan: S\n\nDesign: `{spec}`\n\n## 1. Issue template\n\n(the layout of "
                        f"references/issue_template.md)\n\n## Global constraints\n- TypeScript strict mode, no new "
                        f"dependencies\n\n## 2. Units\n\n{units_text(corrected)}", encoding="utf-8")


def approve(world, lines, kind="opening", respec=None):
  """Commit `lines` as the spec and append its approval entry to the handoff's history."""
  spec = world.repo / SPEC_REL
  spec.parent.mkdir(parents=True, exist_ok=True)
  text = "\n".join(lines) + "\n"
  if not spec.is_file() or spec.read_text(encoding="utf-8") != text:  # the same text keeps the commit, so every body
    spec.write_text(text, encoding="utf-8")
    git(["add", "-A"], world.repo)
    git(["commit", "-qm", f"spec {kind}"], world.repo)
  entry = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "commit": git(["rev-parse", "HEAD"], world.repo).strip(),
           "runcard": None, "review": "spec-s-c1", "approved_at": "2026-11-12T00:00:00Z", "handoff_id": HID, "kind": kind,
           "voided_by": None, "escalated": [], "mode": "normal"} | ({"respec": respec} if respec else {})
  path = world.artifacts / "approvals" / f"{core.spec_slug(spec)}.json"
  record = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"path": str(spec), "entries": []}
  record["entries"].append(entry)
  core.atomic_write(path, record)
  core.atomic_write(world.artifacts / "handoffs" / f"{HID}.json",
                    {"id": HID, "spec": str(spec), "opened_at": "2026-11-12T00:00:00Z", "closed_at": None})
  return entry


def s_world(world):
  """The handoff `HID` of `docs/specs/s.md`, opened and graphed: U07-U09 unfiled."""
  (world.artifacts / "approvals" / "sample.json").unlink()
  world.spec = world.repo / SPEC_REL
  approve(world, spec_lines())
  write_plan(world)
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 0, out
  return world


def units(world):
  return json.loads(handoff_store(world).path("units").read_text(encoding="utf-8"))["units"]


def converge_all(world):
  for uid, unit in units(world).items():
    converge(world.artifacts, HID, uid, unit["body_sha256"], cycle=len(list(handoff_store(world).path("reviews").glob(f"plan-{uid}-c*"))) + 1)


def respec(world, lines, touched, rid="R1"):
  """Respec `rid` applied: `respec/<rid>.json` (its `touched`, the `line_map` from the previous approved text) and the
  `kind: respec` entry; `lines` the corrected spec."""
  from superegm import respec as rs
  previous = (world.repo / SPEC_REL).read_text(encoding="utf-8").splitlines()
  core.atomic_write(handoff_store(world).path("file", "respec", f"{rid}.json"),
                    {"touched": touched, "untouched": [], "follow_ups": [], "line_map": rs.opcodes(previous, lines),
                     "merged_review": []})
  approve(world, lines, "respec", rid)


def marks(world):
  from superegm import respec as rs
  return rs.marks(handoff_store(world), HID)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
  """`~/.superegm` under `tmp_path`: no test reads the owner's registry."""
  monkeypatch.setenv("HOME", str(tmp_path / "home"))


def ticked(world):
  """The tick's fetch record ok and `refs/superegm/tick-base` at HEAD, the root clean on main."""
  core.atomic_write(world.artifacts / "tick" / "fetch.json", {"at": "2026-11-15T00:00:00Z", "ok": True, "stderr": ""})
  git(["update-ref", "refs/superegm/tick-base", "HEAD"], world.repo)


@pytest.mark.parametrize("command", ["gate --pass", "apply --yes"])
def test_gate_refuses_a_replan_unit(world, command):
  # U07 unfiled, its plan review converged on its current body, then respec R1 applied with U07 in `touched`
  s_world(world)
  converge_all(world)
  if command == "apply --yes":  # a resumed apply: the gate passed and the dry run confirmed before the respec
    assert world.run("gate", "--pass", "--spec", world.spec)[0] == 0
    code, out = world.run("dry-run", "--spec", world.spec)
    assert code == 0, out
  respec(world, inserted(spec_lines(), 120, 6), ["U07"])  # a real respec: the spec's sha256 and every body change
  assert marks(world) == {"U07": "replan: R1"}
  argv = ["gate", "--pass"] if command == "gate --pass" else ["apply", "--yes"]
  code, out = world.run(*argv, "--spec", world.spec)
  assert code == 1, out
  assert "gate: U07 needs a re-plan after respec R1" in out


def test_next_routes_a_replan_unit_to_plan(world):
  # every unit has a plan section; U07 unfiled with a converged review on its current body and `replan: R1`
  s_world(world)
  converge_all(world)
  ticked(world)
  code, out = world.run("next", "--handoff", HID)
  assert (code, out.strip()) == (0, "file")  # without the mark the handoff is ready to file
  respec(world, spec_lines(), ["U07"])
  ticked(world)
  result_code, stdout = world.run("next", "--handoff", HID)
  assert stdout.strip() == "plan"
  assert result_code == 0


def unit_file_text(world, uid):
  return next(handoff_store(world).root.rglob(f"unit_{uid}.md")).read_text(encoding="utf-8")


def test_graph_maps_unfiled_ranges_through_line_map(world):
  # U08 unfiled, rendered under approval 1 at :200-240; R1 inserts 6 lines at :120 (line_map shifts +6 below it)
  s_world(world)
  assert "docs/specs/s.md:200-240" in unit_file_text(world, "U08")
  respec(world, inserted(spec_lines(), 120, 6), ["U07"])
  for _ in range(2):  # a second graph run renders :206-246 again, never :212-252
    code, out = world.run("graph", "--plan", world.plan)
    assert code == 0, out
    assert units(world)["U08"]["rendered_under"] == 1  # the plan text still reads in approval-1 lines
    assert "docs/specs/s.md:206-246" in unit_file_text(world, "U08")
    assert "docs/specs/s.md:212-252" not in unit_file_text(world, "U08")
  assert units(world)["U08"]["design_range"]["start"] == 200  # the plan file's own coordinates, never rewritten


@pytest.mark.parametrize("render, corrected, marked", [
  ("graph with Corrected: R1", ["R1"], False),
  ("graph without the line", [], True),
  ("decide", [], True),
])
def test_corrected_line_clears_the_mark(world, render, corrected, marked):
  # U07 carries replan: R1; once cleared, gate still reads "gate: U07 plan review not converged" until a review-plan cycle converges on its new sha
  from superegm import respec as rs
  s_world(world)
  converge_all(world)
  respec(world, inserted(spec_lines(), 120, 6), ["U07"])
  assert marks(world) == {"U07": "replan: R1"}
  store, handoff = handoff_store(world), HID
  if render == "decide":  # a decide render of a section carrying the line records nothing
    write_plan(world, corrected="R1")
    code, out = world.run("decide", "--plan", world.plan, "--unit", "U07", "--decision", "D1", "--default")
  else:
    write_plan(world, corrected="R1" if render == "graph with Corrected: R1" else None)
    code, out = world.run("graph", "--plan", world.plan)
  assert code == 0, out
  assert units(world)["U07"].get("corrected", []) == corrected
  assert ("U07" in rs.marks(store, handoff)) is marked
  assert "Corrected" in core.OPTIONAL_FIELDS
  assert units(world)["U07"]["rendered_under"] == (1 if marked else 2)  # a recorded rewrite reads in R1's lines
  code, out = world.run("gate", "--pass", "--spec", world.spec)
  assert code == 1
  if marked:
    assert "gate: U07 needs a re-plan after respec R1" in out
    return
  assert "gate: U07 " in out and "needs a re-plan" not in out  # cleared, yet its new body is unreviewed
  converge_all(world)  # a review-plan cycle converged on every current body
  code, out = world.run("gate", "--pass", "--spec", world.spec)
  assert code == 0, out


def read(rel):
  return (Path(__file__).resolve().parents[2] / rel).read_text(encoding="utf-8")


def test_skills_name_the_replan():
  # the plan skill rewrites a replan section, the schema names the field, the file skill relays the refusal
  assert "Corrected: R<n>" in read("skills/plan/SKILL.md")
  assert "Corrected" in read("skills/plan/references/handoff_plan.md")
  assert "gate: <U> needs a re-plan after respec R<n>" in read("skills/file/SKILL.md")


def test_corrected_row_names_respec_ids(world):
  s_world(world)
  write_plan(world, corrected="soon")
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1
  assert "U07: Corrected names respec ids `R<n>[, R<m>…]`, not 'soon'" in out


def test_corrected_row_names_an_applied_respec(world):
  s_world(world)
  write_plan(world, corrected="R1")  # no respec applied yet
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1
  assert f"graph: U07: Corrected names R1, no applied respec of handoff {HID}" in out
  respec(world, inserted(spec_lines(), 120, 6), ["U07"])
  write_plan(world, corrected="R1, R2")
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1
  assert f"graph: U07: Corrected names R2, no applied respec of handoff {HID}" in out


def test_graph_maps_through_the_approved_texts_without_a_respec_record(world):
  # a later entry with no `respec/R<n>.json` is carried by the approved texts' opcodes, as `respec.history` reads them
  s_world(world)
  approve(world, inserted(spec_lines(), 120, 6), "respec", "R1")
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 0, out
  assert "docs/specs/s.md:206-246" in unit_file_text(world, "U08")


def test_graph_refuses_an_approval_no_commit_holds(world):
  # an entry between the opening and the latest whose text no commit holds: refused as `respec.history` refuses it
  s_world(world)
  path = world.artifacts / "approvals" / f"{core.spec_slug(world.spec)}.json"
  record = json.loads(path.read_text(encoding="utf-8"))
  ghost = hashlib.sha256(b"never committed\n").hexdigest()
  record["entries"].append({**record["entries"][0], "sha256": ghost, "kind": "respec", "respec": "R1"})
  core.atomic_write(path, record)
  approve(world, inserted(spec_lines(), 120, 6), "respec", "R2")
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1
  assert f"respec: no commit holds approval {ghost[:7]} of s.md" in out


@pytest.mark.parametrize("argv", [["gate", "--pass"], ["next"]])
def test_marks_read_once_per_call(world, monkeypatch, argv):
  from superegm import respec as rs
  s_world(world)
  converge_all(world)
  ticked(world)
  respec(world, spec_lines(), [])  # an applied respec touching nothing: the marks are read
  calls, real = [], rs.marks
  monkeypatch.setattr(rs, "marks", lambda *a: calls.append(a) or real(*a))
  code, out = world.run(*argv, *(["--spec", world.spec] if argv[0] == "gate" else ["--handoff", HID]))
  assert code == 0, out
  assert len(calls) == 1


def test_next_skips_the_marks_without_a_respec_after_the_approving_worktree_is_gone(world, monkeypatch, tmp_path):
  # the handoff's spec recorded in a worktree since removed: `next` neither reads the marks nor runs git there
  from superegm import respec as rs
  s_world(world)
  converge_all(world)
  ticked(world)
  gone = tmp_path / "removed-worktree" / SPEC_REL
  path = world.artifacts / "handoffs" / f"{HID}.json"
  core.atomic_write(path, json.loads(path.read_text(encoding="utf-8")) | {"spec": str(gone)})
  calls, real = [], rs.marks
  monkeypatch.setattr(rs, "marks", lambda *a: calls.append(a) or real(*a))
  code, out = world.run("next", "--handoff", HID)
  assert (code, out.strip()) == (0, "file")
  assert calls == []


def test_a_shifting_respec_invalidates_the_unfiled_reviews(world):
  # every unit unfiled and converged; R1 inserts 6 lines at :120 and touches none: U08's carried range and every
  # body's spec hash change, so the gate and `next` hold the filing until `graph` and review-plan run again
  s_world(world)
  converge_all(world)
  ticked(world)
  respec(world, inserted(spec_lines(), 120, 6), [])
  assert marks(world) == {}
  code, out = world.run("gate", "--pass", "--spec", world.spec)
  assert code == 1
  assert "body differs from its converged round" in out
  ticked(world)
  assert world.run("next", "--handoff", HID)[1].strip() == "plan"
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 0, out
  ticked(world)
  assert world.run("next", "--handoff", HID)[1].strip() == "review-plan"
  converge_all(world)
  code, out = world.run("gate", "--pass", "--spec", world.spec)
  assert code == 0, out


def test_scan_measures_the_carried_range(world):
  # U08 rendered at :206-246 after R1 inserts 6 lines at :199: `scan` measures those spec lines, never :200-240
  s_world(world)
  lines = inserted(spec_lines(), 199, 6)
  respec(world, lines, [])
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 0, out
  assert "docs/specs/s.md:206-246" in unit_file_text(world, "U08")
  world.run("scan", "--plan", world.plan)
  found = json.loads(next(handoff_store(world).root.rglob("scan/U08.json")).read_text(encoding="utf-8"))
  assert found["spec_range_bytes"] == len("".join(f"{line}\n" for line in lines[205:246]).encode("utf-8"))
