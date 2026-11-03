# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: U05's tests of graph, scan, decide and the plan skill; EGM's moved tests re-pointed at the spec-section-9.1 plan.

"""U05's tests: `graph --plan`, `scan`, `decide`, the body parsers' Step defaults and
the `plan` skill's prose; EGM's graph/scan tests, moved here by U03, re-pointed."""

import hashlib, json, re, subprocess
from pathlib import Path
import pytest
from superegm import atomic_write, open_runcard, store
from superegm.body import MARKER_RE, fill_numbers
from superegm.scan import scan_text

from conftest import REPO, set_config

ROOT = Path(__file__).resolve().parents[2]
FENCE = chr(96) * 3
SPEC = ("# Webhooks\n\nDelivery.\n\n## Units\n\n| Unit | Scope | Blocked by | Size |\n| --- | --- | --- | --- |\n"
        "| U01 | The queue | — | S |\n| U02 | The worker | U01 | S |\n| U03 | The admin endpoint | U02 | S |\n")
D1 = "- D1 Retry ceiling? options: (a) 5 attempts; (b) 10 attempts; owner: the owner; default: (a); blocking: no"


def section(uid, title, blocked="none", consumes=(), decide="- none"):
  n = uid.lower()
  interfaces = "\n".join([f"- Consumes: {c}" for c in consumes] + [f"- Produces: {n}_fn(x: int) -> int"])
  return f"""### {uid}: {title}
| Field | Value |
| --- | --- |
| Objective | {title} exists. |
| Scope paths | `src/{n}.ts` (create), `tests/test_{n}.py` (create) |
| Design range | `docs/specs/2026-11-03-webhooks-design.md:5-10 (## Units)` |
| Blocked by | {blocked} |
| Shared files | none |
| Risk | low: new module |
| Size | S |

Interfaces
{interfaces}

Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `pytest tests/test_{n}.py -q` — the module's cases pass
3. Exists `src/{n}.ts`
4. CI green on the head

Review focus (this unit)
- {uid}: an empty input — returns 0; pinned by `test_{n}_empty`

Steps
1. Write the failing test `test_{n}_empty` in `tests/test_{n}.py`:
   {FENCE}python
   def test_{n}_empty(): assert {n}_fn(0) == 0
   {FENCE}
   Run `pytest tests/test_{n}.py::test_{n}_empty -q`; expected: FAIL (`NameError`).
   Implement `{n}_fn(x: int) -> int` in `src/{n}.ts`.
   Run the same command; expected: PASS. Commit `test(S1): {n} empty` then `feat(S1): {n} empty`.

Decide before build
{decide}
"""


UNITS = (section("U01", "Queue"),
         section("U02", "Worker", "U01", ["u01_fn(x: int) -> int (U01)"], D1),
         section("U03", "Admin", "U02", ["u01_fn(x: int) -> int (U01)"]))


def plan_text(spec, units=UNITS, constraints="- Python 3.11, standard library only"):
  return (f"# Handoff plan: Webhooks\n\nDesign: `{spec}`\n\n## 1. Issue template\n\n(the layout of "
          f"references/issue_template.md)\n\n## Global constraints\n{constraints}\n\n## 2. Units\n\n" + "\n".join(units))


def git(args, cwd):
  return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def store_root(world):
  return Path(json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["artifacts_dir"])


def approve(world, text=SPEC, handoff_id=None, name="2026-11-03-webhooks-design.md"):
  spec = world.repo / "docs/specs" / name
  spec.parent.mkdir(parents=True, exist_ok=True)
  spec.write_text(text, encoding="utf-8")
  git(["add", "-A"], world.repo)
  git(["commit", "-qm", "spec"], world.repo)
  sha = hashlib.sha256(spec.read_bytes()).hexdigest()
  path = store_root(world) / "approvals" / f"{spec.stem}.json"
  path.parent.mkdir(parents=True, exist_ok=True)
  atomic_write(path, {"path": str(spec), "sha256": sha, "commit": git(["rev-parse", "--short", "HEAD"], world.repo).strip(),
                      "runcard": "rc-spec", "review": f"spec-{spec.stem}-c1", "approved_at": "2026-11-03T00:00:00Z",
                      "amended": [], "voided_by": None, "handoff_id": handoff_id or f"2026-11-03-webhooks-{sha[:6]}"})
  return spec, sha


def planned(world, units=UNITS):
  spec, sha = approve(world)
  plan = world.repo.parent / "plan.md"
  plan.write_text(plan_text(spec, units), encoding="utf-8")
  return spec, sha, plan, open_runcard(store(world.repo), "plan", str(spec))


def graph(world, plan, card):
  return world.run("graph", "--plan", plan, "--runcard", card)


def find(world, name):
  return next(store_root(world).rglob(name))


def state(world):
  return json.loads((store_root(world) / "state.json").read_text(encoding="utf-8"))


def body_of(world, uid):
  text = find(world, f"unit_{uid}.md").read_text(encoding="utf-8")
  return re.search(r"^````markdown\n(.*?)^````$", text, re.S | re.M).group(1)


def test_graph_requires_a_matching_approval(world):
  spec, sha, plan, card = planned(world)
  spec.write_text(SPEC + "\nchanged\n", encoding="utf-8")
  code, out = graph(world, plan, card)
  assert code == 1 and "graph: no approval matches" in out and spec.name in out and "review-spec" in out
  spec.write_text(SPEC, encoding="utf-8")
  code, out = graph(world, plan, card)
  assert code == 0 and f"handoff 2026-11-03-webhooks-{sha[:6]} on" in out and "wave 1: U01" in out, out
  assert state(world)["handoff_id"] == f"2026-11-03-webhooks-{sha[:6]}"
  assert f"<!-- superegm:handoff=2026-11-03-webhooks-{sha[:6]} unit=U01 spec={sha} -->" in body_of(world, "U01")


# ---------------------------------------------- EGM's tests, re-pointed at the section 9.1 plan


def test_graph_unknown_reference_cycle_and_contradiction(world):
  spec, sha, plan, card = planned(world)
  text = plan_text(spec)
  plan.write_text(text.replace("| Blocked by | U02 |", "| Blocked by | U09 |"), encoding="utf-8")
  code, out = graph(world, plan, card)
  assert code == 1 and "unknown unit U09" in out
  plan.write_text(text.replace("| Blocked by | none |", "| Blocked by | U03 |"), encoding="utf-8")
  code, out = graph(world, plan, card)
  assert code == 1 and "blocked-by cycle" in out and "U01" in out and "U03" in out
  plan.write_text(text.replace("| Shared files | none |", "| Shared files | `src/u01.ts`: after U02 |", 1), encoding="utf-8")
  code, out = graph(world, plan, card)
  assert code == 1 and "shared-file chain contradicts the blockers" in out


def test_scan_banned_terms_mentions_and_size():
  config = {"banned_terms": ["(?i)secret-codename"], "fix_request_mention": "@copilot"}
  # The scan is not code-aware (0.2.1): a banned term inside a code span is
  # still refused, and the author rewords.
  assert any("banned term" in p for p in scan_text("plain `secret-codename` in code", config, "body"))
  assert any("banned term" in p for p in scan_text("the secret-codename leaks", config, "body"))
  assert any("bare mention" in p for p in scan_text("ask @alice please", config, "body"))
  assert scan_text("email a@b.example only", config, "body") == []
  assert any("bare mention" in p for p in scan_text("email a@b.example and `@alice`", config, "body"))
  assert scan_text("@copilot\n**EGM review round 1**", config, "comment") == []
  assert any("bare mention" in p for p in scan_text("hello\n@copilot", config, "comment"))
  assert any("bare mention" in p for p in scan_text("@copilot first", config, "body"))
  big = "é" * 40_000
  assert any("split it" in p for p in scan_text(big, config, "body"))
  assert any("merge marker" in p for p in scan_text("a\n<<<<<<< HEAD\nb", config, "body"))
  assert any("missing from the body" in p for p in scan_text("x", config, "body", dod=["`npm test`"]))


def test_scan_command_over_rendered_bodies(world):
  spec, sha, plan, card = planned(world)
  text = plan_text(spec)
  plan.write_text(text.replace("Worker exists.", "Worker exists; see secret-codename."), encoding="utf-8")
  assert graph(world, plan, card)[0] == 0
  code, out = world.run("scan", "--plan", plan)
  assert code == 1 and "banned term" in out and "U02" in out
  plan.write_text(text, encoding="utf-8")
  code, out = world.run("scan", "--plan", plan)
  assert code == 0 and "scan: clean" in out


def test_scan_is_not_code_aware(world):
  """Seven review rounds each found a defect in a Markdown-aware scanner; it
  could both hide a mention behind a fence shape it misread and refuse an
  ordinary comment. The code-awareness was deleted. Every line is scanned as
  written, fences and spans included."""
  config = {"banned_terms": ["(?i)secret-codename"], "fix_request_mention": None,
            "allowed_mentions": []}
  for body in ("```\n@alice secret-codename\n```\n",
               "`@alice` and `secret-codename`\n",
               "- ```\n  safe\n  ```\n\n@alice secret-codename\n```\n",
               "<div></div>\n```\n\n@alice secret-codename\n\n```\n",
               "    ```\n\n@alice secret-codename\n\n    ```\n"):
    problems = scan_text(body, config, "comment")
    assert any("bare mention @alice" in p for p in problems), (body, problems)
    assert any("banned term" in p for p in problems), (body, problems)
  assert "strip_code" not in world.ns and "FENCE_RE" not in world.ns


def test_an_ordinary_body_with_a_fence_and_no_mention_passes():
  config = {"banned_terms": ["(?i)secret-codename"], "fix_request_mention": None,
            "allowed_mentions": []}
  assert scan_text("Do this:\n\n```sh\nnpm test\n```\n\nThen ship.\n", config, "body") == []
  assert scan_text("```diff\n- ```sh\n+ ```bash\n```\n", config, "comment") == []


def test_allowed_mentions_are_explicit_and_validated(world):
  config = {"banned_terms": [], "fix_request_mention": None,
            "allowed_mentions": ["@types/node"]}
  assert scan_text("import from @types/node\n", config, "body") == []
  problems = scan_text("ping @alice and @types/node\n", config, "body")
  assert [p for p in problems if "@alice" in p] and not [p for p in problems if "@types" in p]
  assert any("allowed_mentions" in p for p in problems), problems
  # R8-01: the allowlist is exact-literal over the whole token GitHub resolves.
  # `@acme` must not cover the team `@acme/release`, and `@types` must not
  # cover `@types/node`.
  team = {"banned_terms": [], "fix_request_mention": None, "allowed_mentions": ["@acme"]}
  assert any("@acme/release" in p for p in scan_text("@acme/release please look\n", team, "body"))
  bare = {"banned_terms": [], "fix_request_mention": None, "allowed_mentions": ["@types"]}
  assert any("@types/node" in p for p in scan_text("uses @types/node\n", bare, "body"))
  # the config refuses anything that is not an @name (the card is opened while it still loads)
  spec, sha, plan, card = planned(world)
  set_config(world, repo=REPO, allowed_mentions=["types"])
  code, out = graph(world, plan, card)
  assert code == 1 and "allowed_mentions must be a list of `@name` strings" in out


def test_fix_request_mention_still_passes_only_on_a_comment_first_line():
  config = {"banned_terms": [], "fix_request_mention": "@devin", "allowed_mentions": []}
  assert scan_text("@devin please fix\n", config, "comment") == []
  assert scan_text("note\n@devin please fix\n", config, "comment") != []
  assert scan_text("@devin please fix\n", config, "body") != []


def test_graph_keeps_the_handoff_id_across_a_reapproval(world):
  spec, sha, plan, card = planned(world)
  assert graph(world, plan, card)[0] == 0
  hid = f"2026-11-03-webhooks-{sha[:6]}"
  # comprehension-c2r5-1: a fix-design re-approval with nothing filed keeps the id though the bytes changed
  spec2, sha2 = approve(world, SPEC.replace("Delivery.", "Delivery, retried."), handoff_id=hid)
  assert sha2 != sha and graph(world, plan, card)[0] == 0
  assert state(world)["handoff_id"] == hid and f"spec={sha2} -->" in body_of(world, "U01")
  # one handoff per store: another id is refused until closed_at is written
  spec3, sha3 = approve(world, SPEC.replace("Webhooks", "Payments"), handoff_id="2026-11-04-payments-abcdef",
                        name="2026-11-04-payments-design.md")
  plan3 = world.repo.parent / "plan3.md"
  plan3.write_text(plan_text(spec3), encoding="utf-8")
  card3 = open_runcard(store(world.repo), "plan", str(spec3))
  code, out = graph(world, plan3, card3)
  assert code == 1 and f"graph: the store holds handoff {hid}, not closed" in out and "integrate --close" in out
  s = state(world)
  s["closed_at"] = "2026-11-04T00:00:00Z"
  atomic_write(store_root(world) / "state.json", s)
  assert graph(world, plan3, card3)[0] == 0
  assert state(world)["handoff_id"] == "2026-11-04-payments-abcdef" and "closed_at" not in state(world)


def test_graph_records_the_plan_path_and_copies_the_plan(world):
  spec, sha, plan, card = planned(world)
  code, out = world.run("graph", "--runcard", card)
  assert code == 1 and "graph: no plan recorded: pass --plan on the first graph" in out
  assert graph(world, plan, card)[0] == 0
  assert state(world)["plan"] == str(plan)
  assert find(world, "handoff_plan.md").read_text(encoding="utf-8") == plan.read_text(encoding="utf-8")
  plan.write_text(plan.read_text(encoding="utf-8").replace("Worker exists.", "A worker exists."), encoding="utf-8")
  assert world.run("graph", "--runcard", card)[0] == 0
  assert "A worker exists." in find(world, "handoff_plan.md").read_text(encoding="utf-8")
  assert plan.read_text(encoding="utf-8") == plan_text(spec).replace("Worker exists.", "A worker exists.")
  assert world.run("scan")[0] == 0


FIXED_DOD_1 = "1. The test for each Step was committed before its implementation (checked by superegm tdd-order)"
GRAMMAR = [
  pytest.param("Interfaces\n- Consumes: u01_fn(x: int) -> int (U01)\n- Produces: u02_fn(x: int) -> int\n\n", "",
               "U02: expected `Interfaces`", id="no-interfaces"),
  pytest.param("- Produces: u02_fn(x: int) -> int", "- Gives: u02_fn(x: int) -> int",
               "U02: interfaces line must read `- Consumes: <name> (U<nn>)` or `- Produces: <name>`", id="interfaces-line"),
  pytest.param(FIXED_DOD_1 + "\n2. Run `pytest tests/test_u01.py -q`", "1. Run `pytest tests/test_u01.py -q`",
               "U01: definition-of-done item 1 must read `The test for each Step", id="dod-1"),
  pytest.param("3. Exists `src/u02.ts`", "3. `src/u02.ts` is documented",
               "U02: definition-of-done item 3 is not `Run `, `Exists ` or `CI green on the head`", id="dod-kind"),
  pytest.param("Review focus (this unit)\n- U02:", "- U02:", "U02: expected `Review focus (this unit)`", id="no-review-focus"),
  pytest.param("Steps\n1. Write the failing test `test_u02_empty`", "1. Write the failing test `test_u02_empty`",
               "U02: expected `Steps`", id="no-steps"),
  pytest.param("options: (a) 5 attempts; (b) 10 attempts; owner", "options: (a) 5 attempts; owner",
               "U02: decide-before-build item D1 needs two or more options", id="decide-one-option"),
  pytest.param("default: (a); blocking: no", "default: (c); blocking: no",
               "U02: decide-before-build item D1 default (c) is not one of its options", id="decide-default"),
  pytest.param(D1, "- D1 Retry ceiling? owner: the owner; default: 5; blocking: no",
               "U02: decide-before-build item must read `- D<n> <question> options: (a) <option>; (b) <option>", id="decide-egm-form"),
  pytest.param("## Global constraints\n- Python 3.11, standard library only\n\n", "",
               "no `## Global constraints` section", id="no-global-constraints"),
]


@pytest.mark.parametrize("old,new,message", GRAMMAR)
def test_graph_section_grammar(world, old, new, message):
  spec, sha, plan, card = planned(world)
  text = plan_text(spec)
  assert old in text
  plan.write_text(text.replace(old, new, 1), encoding="utf-8")
  code, out = graph(world, plan, card)
  assert code == 1 and f"{plan}:" in out and message in out, out


def test_body_layout_markers_and_placeholders(world):
  spec, sha, plan, card = planned(world)
  assert graph(world, plan, card)[0] == 0
  body = body_of(world, "U02")
  lines = body.splitlines()
  assert MARKER_RE.match(lines[0]).groups() == (f"2026-11-03-webhooks-{sha[:6]}", "U02", sha)
  assert lines[1] == "# U02 — Worker"
  assert lines[2] == (f"Spec: `docs/specs/2026-11-03-webhooks-design.md` @ {sha[:7]} · "
                      "`docs/specs/2026-11-03-webhooks-design.md:5-10 (## Units)`")
  assert [l for l in lines if l.startswith("## ")] == [
      "## Objective", "## Interfaces", "## Definition of done", "## Global constraints",
      "## Review focus (this unit)", "## Steps", "## Decide before build", "## Scope, order and risk"]
  assert "\n- Python 3.11, standard library only\n" in body and "- [ ]" not in body
  assert "\n" + FIXED_DOD_1 + "\n2. Run `pytest tests/test_u02.py -q` — the module's cases pass\n" in body
  assert "- Consumes: u01_fn(x: int) -> int (U01)\n- Produces: u02_fn(x: int) -> int\n" in body
  assert "- U02: an empty input — returns 0; pinned by `test_u02_empty`\n" in body
  assert "1. Write the failing test `test_u02_empty` in `tests/test_u02.py`:\n   " + FENCE + "python\n" in body
  assert "\n" + D1 + "\n" in body
  assert ("Scope: `src/u02.ts` (create), `tests/test_u02.py` (create) · Blocked by: #<U01> · "
          "Shared files: none · Risk: low: new module · Size: S\n") in body
  assert body.endswith(f"Branch: `superegm/2026-11-03-webhooks-{sha[:6]}/U02` · Part of #<tracking>\n")
  filled = fill_numbers(body, {"U01": 11}, tracking=10)
  assert "Blocked by: #11 ·" in filled and "Part of #10" in filled
  bodies = find(world, "handoff_bodies.md").read_text(encoding="utf-8")
  assert f"<!-- superegm:handoff=2026-11-03-webhooks-{sha[:6]} unit=tracking spec={sha} -->" in bodies
  assert "Blocked by: none ·" in body_of(world, "U01")


def test_graph_hashes_unfiled_bodies(world):
  spec, sha, plan, card = planned(world)
  assert graph(world, plan, card)[0] == 0
  units = json.loads(find(world, "handoff_units.json").read_text(encoding="utf-8"))
  for uid in ("U01", "U02", "U03"):
    digest = hashlib.sha256(body_of(world, uid).encode("utf-8")).hexdigest()
    assert units["units"][uid]["body_sha256"] == digest == state(world)["units"][uid]["body_sha256"]
  assert units["handoff_id"] == f"2026-11-03-webhooks-{sha[:6]}" and units["waves"] == {"1": ["U01"], "2": ["U02"], "3": ["U03"]}
  assert units["units"]["U02"]["blockers"] == ["U01"] and units["order"] == ["U01", "U02", "U03"]
  assert units["units"]["U02"]["interfaces"] == ["- Consumes: u01_fn(x: int) -> int (U01)", "- Produces: u02_fn(x: int) -> int"]
  assert units["units"]["U02"]["decisions"][0]["options"] == ["(a) 5 attempts", "(b) 10 attempts"]
  before = find(world, "handoff_units.json").read_bytes()
  assert graph(world, plan, card)[0] == 0 and find(world, "handoff_units.json").read_bytes() == before
  assert "unit_U02.md" in find(world, "unit_U02.md").name and find(world, "handoff_bodies.md").is_file()


def file_unit(world, uid, number):
  s = state(world)
  s["units"][uid]["number"] = number
  atomic_write(store_root(world) / "state.json", s)


def test_graph_refuses_an_edited_filed_section(world):
  spec, sha, plan, card = planned(world)
  assert graph(world, plan, card)[0] == 0
  file_unit(world, "U01", 7)
  filed_body, filed_hash = body_of(world, "U01"), state(world)["units"]["U01"]["body_sha256"]
  edited = plan.read_text(encoding="utf-8").replace("| Objective | Queue exists. |", "| Objective | A queue exists. |")
  edited = edited.replace("| Objective | Worker exists. |", "| Objective | A worker exists. |")
  plan.write_text(edited, encoding="utf-8")
  code, out = graph(world, plan, card)
  assert code == 1 and "graph: U01 is filed (#7) and its section differs from the stored handoff_plan.md" in out
  plan.write_text(edited.replace("| Objective | A queue exists. |", "| Objective | Queue exists. |"), encoding="utf-8")
  assert graph(world, plan, card)[0] == 0
  assert body_of(world, "U01") == filed_body and state(world)["units"]["U01"]["body_sha256"] == filed_hash
  assert "A worker exists." in body_of(world, "U02")


@pytest.mark.parametrize("item,names", [
  ("require_runcard(args, skills) -> dict", ["require_runcard"]),
  ("MARKER_RE", ["MARKER_RE"]),
  ("superegm runcard open --skill <s> --artifact <a> [--parent <id>] → <id>", ["superegm runcard open"]),
  ("superegm scan [--plan <file>] → `scan: clean`; exit 0 / 1", ["superegm scan"]),
  ("handoff_units.json key units[<id>].body_sha256", ["units[<id>].body_sha256"]),
  ("approvals/<spec-slug>.json key path, sha256, amended[], voided_by", ["path", "sha256", "amended[]", "voided_by"]),
  ("state.json key closed_at (written by U11's `close`, absent until then)", ["closed_at"]),
])
def test_interface_names(item, names):
  from superegm.scan import names_of
  assert names_of(item) == names


U02_DOD2 = "tests/test_u02.py -q` — the module's cases pass"
CLOSE = "Commit `test(S1): u02 empty` then `feat(S1): u02 empty`.\n"
SCAN = [
  pytest.param("body-size", "| Objective | Worker exists. |", "| Objective | Worker " + "x" * 49_152 + " exists. |", id="body-size"),
  pytest.param("checkbox", CLOSE, CLOSE + "   - [ ] later\n", id="checkbox"),
  pytest.param("placeholder", U02_DOD2, "tests/test_u02.py -q` — TBD", id="placeholder-tbd"),
  pytest.param("placeholder", U02_DOD2, "tests/test_u02.py -q` — handle edge cases", id="placeholder-edge"),
  pytest.param("placeholder", U02_DOD2, "tests/test_u02.py -q` — add appropriate validation", id="placeholder-validation"),
  pytest.param("placeholder", U02_DOD2, "tests/test_u02.py -q` — write tests for the above", id="placeholder-tests"),
  pytest.param("consumes-undefined", "- Consumes: u01_fn(x: int) -> int (U01)\n- Produces: u02_fn",
               "- Consumes: nothing_fn(x: int) -> int (U01)\n- Produces: u02_fn", id="consumes-undefined"),
  pytest.param("consumes-producer", "- Consumes: u01_fn(x: int) -> int (U01)\n- Produces: u02_fn",
               "- Consumes: u03_fn(x: int) -> int (U03)\n- Produces: u02_fn", id="consumes-producer"),
  pytest.param("global-constraints", "- Python 3.11, standard library only\n", "", id="global-constraints"),
  pytest.param("review-focus", "- U02: an empty input — returns 0; pinned by `test_u02_empty`\n", "", id="review-focus"),
  pytest.param("review-focus-test", "pinned by `test_u02_empty`", "pinned by `test_u02_other`", id="review-focus-test"),
  pytest.param("step-group", "   Implement `u02_fn(x: int) -> int` in `src/u02.ts`.\n", "", id="step-group"),
  pytest.param("step-scope", "`test_u02_empty` in `tests/test_u02.py`", "`test_u02_empty` in `tests/other/test_u02.py`", id="step-scope"),
  pytest.param("decision-blocking", "default: (a); blocking: no", "default: (a); blocking: yes", id="decision-blocking"),
  pytest.param("mention", "| Objective | Worker exists. |", "| Objective | Worker exists, ask @alice. |", id="mention"),
]


@pytest.mark.parametrize("rule,old,new", SCAN)
def test_scan_rules(world, rule, old, new):
  spec, sha, plan, card = planned(world)
  text = plan_text(spec)
  assert old in text
  plan.write_text(text.replace(old, new, 1), encoding="utf-8")
  assert graph(world, plan, card)[0] == 0
  code, out = world.run("scan")
  assert code == 1 and f"{rule}: U02" in out and out.rstrip().endswith("problem(s)"), out
  if rule == "body-size":
    assert "exceeds 49,152: split it" in out
  plan.write_text(text, encoding="utf-8")
  assert graph(world, plan, card)[0] == 0
  code, out = world.run("scan")
  assert code == 0 and out.rstrip().endswith("scan: clean"), out


D1_YES = D1.replace("blocking: no", "blocking: yes")
BLOCKED = (UNITS[0], section("U02", "Worker", "U01", ["u01_fn(x: int) -> int (U01)"], D1_YES), UNITS[2])


def test_decide_rewrites_the_plan_line_and_rerenders(world):
  spec, sha, plan, card = planned(world, BLOCKED)
  assert graph(world, plan, card)[0] == 0
  code, out = world.run("scan")
  assert code == 1 and "decision-blocking: U02" in out
  before = state(world)["units"]["U02"]["body_sha256"]
  code, out = world.run("decide", "--unit", "U02", "--decision", "D1", "--answer", "(b)", "--runcard", card)
  assert code == 0 and "recorded U02/D1 (b); re-rendered unit_U02.md" in out, out
  assert D1_YES + "; answer: (b)" in plan.read_text(encoding="utf-8")
  assert D1_YES + "; answer: (b)" in body_of(world, "U02") and state(world)["units"]["U02"]["body_sha256"] != before
  d = state(world)["decisions"]["U02/D1"]
  assert d["answer"] == "(b)" and d["by"] == "owner" and d["decided_at"] and "published" not in d
  assert not list(store_root(world).rglob("decision_comment_U02_D1.md"))
  assert world.run("scan")[0] == 0


def test_decide_refuses_an_answer_outside_the_options(world):
  spec, sha, plan, card = planned(world, BLOCKED)
  assert graph(world, plan, card)[0] == 0
  code, out = world.run("decide", "--unit", "U02", "--decision", "D1", "--answer", "(c)", "--runcard", card)
  assert code == 1 and "decide: (c) is not an option of U02/D1" in out
  assert "answer:" not in plan.read_text(encoding="utf-8") and "decisions" not in state(world)
  code, out = world.run("decide", "--unit", "U02", "--decision", "D9", "--default", "--runcard", card)
  assert code == 1 and "decide: U02 has no decision D9" in out
  code, out = world.run("decide", "--unit", "U02", "--decision", "D1", "--default", "--judges", "judges-7", "--runcard", card)
  assert code == 0 and D1_YES + "; answer: (a)" in plan.read_text(encoding="utf-8")
  assert state(world)["decisions"]["U02/D1"]["by"] == "judges:judges-7"
