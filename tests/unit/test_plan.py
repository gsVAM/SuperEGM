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
