# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U11's tests: `judges question`, the leavemealone routing, `close`, the
# integrate skill, the docs, the README and the removed-mechanism sweep.

"""U11: leavemealone routing and finish (design sections 12, 13.2 and 15)."""

import json
import re
from pathlib import Path

import pytest

from conftest import REPO
from superegm import atomic_write, store

ROOT = Path(__file__).resolve().parents[2]
HEAD = "a" * 64
FINDING = "change-review-1-1 | high | src/x.py:3 | regression: no | the retry loop never backs off"
LOW = "change-review-1-2 | low | src/x.py:9 | regression: no | a stray print"
CI = "foreman-1-1 | high | ci | regression: no | CI not green on this head"
INTERFACE_COMMENT = ("**Deviation (interface):** `deliver(job)` needs a `retries` argument\n"
                     "**Builder status:** BLOCKED\n- (a) add `retries: int = 5` to `deliver`\n"
                     "- (b) read the ceiling from config\n")


def put(world, obj, *key):
  path = store(world.repo).path(*key)
  if isinstance(obj, str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(obj, encoding="utf-8")
  else:
    atomic_write(path, obj)
  return path


def seed(world):
  """One handoff: U07 filed as #410, U08 (#412) consumes a U07 name, U09 (#415) does not."""
  put(world, {"handoff_id": "sample-design-abc123",
              "design": {"path": str(world.spec.resolve())},  # require_runcard matches a --unit call against it
              "units": {"U07": {"number": 410}, "U08": {"number": 412}, "U09": {"number": 415}}}, "state")
  put(world, {"units": {"U07": {"decisions": [{"id": "D1", "question": "Retry ceiling?", "owner": "gsVAM",
                                                "options": ["(a) 5 attempts", "(b) 10 attempts"],
                                                "default": "a", "blocking": True}]}}}, "units")
  put(world, "### U08: Admin\n\n## Interfaces\n- Consumes: deliver (U07)\n", "unit", "U08")
  put(world, "### U09: Queue\n\n## Interfaces\n- Consumes: enqueue (U01)\n", "unit", "U09")


def comment(world, cid, body):
  """A builder comment served at `gh api repos/<repo>/issues/comments/<id>`; every other route stays `do_api`'s."""
  world.gh.comments[cid] = {"id": cid, "user": {"login": "builder-bot"}, "body": body}

  def api(args, cwd, token=None):
    match = re.fullmatch(rf"repos/{REPO}/issues/comments/(\d+)", world.gh.endpoint_of(args))
    return world.gh.ok(world.gh.comments[int(match.group(1))]) if match else world.gh.do_api(args)
  world.gh.extend("api", api)


def record(world, review, reviewer, lines, runcard, tmp_path):
  path = tmp_path / f"{reviewer}.txt"
  path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
  code, out = world.run("review", "record", "--review", review, "--round", "1", "--sha256", HEAD,
                        "--reviewer", reviewer, "--findings", str(path), "--isolation", "clean",
                        "--model", "inherit:opus", "--effort", "max:max", "--runcard", runcard)
  assert code == 0, out


def head_review(world, runcard, tmp_path):
  code, out = world.run("review", "open", "--kind", "head", "--artifact", "U07", "--sha256", HEAD,
                        "--reviewers", "change-review", "--runcard", runcard)
  assert code == 0, out
  review = out.strip()
  # A head's rounds are the unit's `rounds[]` entries (U04): `review record` needs round 1's.
  put(world, {"dispatch_id": "d1", "decisions": [], "rulings": [],
              "rounds": [{"round": 1, "runcard": runcard, "launch": 1, "head": HEAD, "phase": "collected",
                          "dispatch_id": "d1", "outcome": None, "posted_at": None}]}, "foreman", "U07")
  record(world, review, "change-review", [FINDING, LOW], runcard, tmp_path)
  record(world, review, "foreman", [CI], runcard, tmp_path)
  return review


@pytest.mark.parametrize("form", ["round", "cap", "decision", "blocked-comment", "blocked-launch", "blocked-closed"])
def test_judges_question_forms(world, tmp_path, form):
  seed(world)
  runcard = world.card("wave")
  review = head_review(world, runcard, tmp_path)
  comment(world, 123, INTERFACE_COMMENT)
  put(world, {"launches": [{"round": 1, "status": "exited 0"}]}, "launches", "U07")
  args, expected = {
      "round": (["--review", review, "--round", "1", "--reason", "change-review-1-1=the test covers it"],
                "## Q1 change-review-1-1 (high, src/x.py:3): the retry loop never backs off\n"
                "- (a) finding upheld\n- (b) finding overruled — the test covers it\n"),
      "cap": (["--review", review, "--cap"], f"## Q1 {review} is at its cap\n- (a) one more round\n- (b) stop\n"),
      "decision": (["--unit", "U07", "--decision", "D1"],
                   "## Q1 U07 D1: Retry ceiling?\n- (a) 5 attempts\n- (b) 10 attempts\n"),
      "blocked-comment": (["--unit", "U07", "--blocked", "123"],
                          "## Q1 U07 BLOCKED (comment 123): **Deviation (interface):** `deliver(job)` needs a `retries` argument\n"
                          "- (a) add `retries: int = 5` to `deliver`\n- (b) read the ceiling from config\n- (c) stop the unit\n"),
      "blocked-launch": (["--unit", "U07", "--blocked", "launch", "1"],
                         "## Q1 U07 launch 1 (exited 0) ended with no pull request\n- (a) relaunch\n- (b) stop the unit\n"),
      "blocked-closed": (["--unit", "U07", "--blocked", "closed", "41"],
                         "## Q1 U07: #41 was closed by the builder account\n- (a) relaunch\n- (b) stop the unit\n"),
  }[form]
  code, out = world.run("judges", "question", *args, "--runcard", runcard)
  assert code == 0, out
  path = Path(out.splitlines()[0])
  assert path.is_file() and path.read_text(encoding="utf-8") == expected
  assert f"question rendered: {path}" in (world.artifacts / "journal.md").read_text(encoding="utf-8")
  code, out = world.run("judges", "open", "--question", str(path), "--evidence", str(world.spec), "--parent", runcard)
  assert code == 0, out
  code, out = world.run("judges", "question", *args, card=None)
  assert code == 1 and "runcard: --runcard is required" in out, out


@pytest.mark.parametrize("case, args, message", [
    ("ci", ["--review", "{review}", "--round", "1", "--reason", "foreman-1-1=flaky"],
     "question: foreman-1-1 is the CI finding"),
    ("low", ["--review", "{review}", "--round", "1", "--reason", "change-review-1-2=cosmetic"],
     "question: change-review-1-2 is low"),
    ("unknown", ["--review", "{review}", "--round", "1", "--reason", "design-1-9=x"],
     "question: design-1-9 is not in round 1"),
    ("continue-used", ["--review", "{review}", "--cap"],
     "question: continue already ruled on {review}; stop is the only option"),
    ("relaunch-used", ["--unit", "U07", "--blocked", "launch", "1"],
     "question: relaunch already used on U07"),
])
def test_judges_question_refusals(world, tmp_path, case, args, message):
  seed(world)
  runcard = world.card("wave")
  review = head_review(world, runcard, tmp_path)
  put(world, {"launches": [{"round": 1, "status": "exited 1"}]}, "launches", "U07")
  if case == "continue-used":
    # `review rule` refuses `not at the cap` after one round: the ruling it would write is seeded.
    record = json.loads(store(world.repo).path("reviews", review, "review.json").read_text(encoding="utf-8"))
    record["rulings"].append({"id": "R1", "ruling": "continue", "by": "owner", "at": "2026-11-03T00:00:00Z"})
    put(world, record, "reviews", review, "review.json")
  if case == "relaunch-used":
    put(world, {"dispatch_id": None, "rounds": [], "decisions": [{"id": "d1", "point": 3}],
                "rulings": [{"decision": "d1", "ruling": "relaunch", "by": "judges:p1"}]}, "foreman", "U07")
  before = sorted(str(p) for p in world.artifacts.rglob("*.md"))
  code, out = world.run("judges", "question", *[a.format(review=review) for a in args], "--runcard", runcard)
  assert code == 1 and message.format(review=review) in out, out
  assert sorted(str(p) for p in world.artifacts.rglob("*.md")) == before


def test_interface_deviation_fan_out(world):
  seed(world)
  runcard = world.card("wave")
  comment(world, 123, INTERFACE_COMMENT)
  comment(world, 124, "**Deviation (dod):** item 2 cannot run offline\n**Builder status:** BLOCKED\n- (a) mark item 2 CI-only\n")
  code, out = world.run("judges", "question", "--unit", "U07", "--blocked", "123", "--runcard", runcard)
  assert code == 0 and out.splitlines()[1] == "consumers: #412", out
  code, out = world.run("judges", "question", "--unit", "U07", "--blocked", "124", "--runcard", runcard)
  assert code == 0 and len(out.splitlines()) == 1, out


REFERENCE = ROOT / "skills/judges/references/leavemealone.md"
ROWS = [
    ("--review <id> --round <n>", "finding upheld",
     'superegm decision rule --unit <U> --decision <did> --ruling "<fid> finding upheld" --by judges:<panel> --runcard <card>'),
    ("--review <id> --round <n>", "finding overruled",
     "superegm review settle --review <id> --finding <fid> --disposition contested --judges <panel> --runcard <card>"),
    ("--review <id> --cap", "continue one bounded round",
     "superegm review rule --review <id> --ruling continue --judges <panel> --runcard <card>"),
    ("--review <id> --cap", "one more round",
     "superegm review rule --review <id> --ruling continue --judges <panel> --runcard <card>"),
    ("--review <id> --cap", "accept the remainder",
     "superegm review rule --review <id> --ruling accept --judges <panel> --runcard <card>"),
    ("--review <id> --cap", "stop",
     "superegm review rule --review <id> --ruling stop --judges <panel> --runcard <card>"),
    ("--unit <U> --decision D<n>", "(x)",
     'superegm decide --unit <U> --decision D<n> --answer "(x)" --judges <panel> --runcard <card>'),
    ("--unit <U> --blocked", "<option>",
     'superegm decision rule --unit <U> --decision <did> --ruling "<option>" --by judges:<panel> --runcard <card>'),
]


@pytest.mark.parametrize("form, option, command", ROWS)
def test_routing_table_row(world, form, option, command):
  rows = [l for l in REFERENCE.read_text(encoding="utf-8").splitlines() if l.startswith("| `")]
  row = next(l for l in rows if l.startswith(f"| `{form}` | `{option}` |"))
  assert f"`{command}`" in row
  assert not re.search(r"--approve|--request-changes|gh pr merge|merge locally", REFERENCE.read_text(encoding="utf-8"))
  tokens = command.split()[1:]
  sub = [t for t in tokens[:2] if not t.startswith("-")]
  code, usage = world.run(*sub, "--help")  # the harness returns `--help`'s exit 0 and its text
  assert code == 0
  missing = [f for f in tokens if f.startswith("--") and f not in usage]
  assert not missing, (sub, missing)


WIRING = {
    "review-spec": ["judges question --review <id> --round <n> --reason <fid>=<text> --runcard <card>",
                    "judges question --review <id> --cap --runcard <card>"],
    "review-plan": ["judges question --review <id> --round <n> --reason <fid>=<text> --runcard <card>",
                    "judges question --review <id> --cap --runcard <card>"],
    "plan": ["judges question --unit <U> --decision D<n> --runcard <card>",
             'decide --unit <U> --decision D<n> --answer "(<id>)" --judges <panel> --runcard <card>'],
    "wave": ["judges question --review <id> --round <n> --runcard <card>",
             "judges question --review <id> --cap --runcard <card>",
             "judges question --unit <U> --blocked <comment-id> --runcard <card>",
             "judges question --unit <U> --blocked launch <n> --runcard <card>",
             "judges question --unit <U> --blocked closed <n> --runcard <card>",
             "decision open --unit <U> --point <1|2|3> --question <path> --source <source> --runcard <card>",
             "consumers:"],
}
# `judges open` takes `--runcard | --parent` as an exclusive pair (U08); under a skill's card the panel opens with `--parent`.
COMMON = ["judges open --question <path> --evidence <paths> --parent <card>",
          "judges verdict --panel <id>", "${CLAUDE_PLUGIN_ROOT}/skills/judges/references/leavemealone.md",
          "`--leavemealone`", "`config.mode`", "unconverged"]


@pytest.mark.parametrize("skill", sorted(WIRING))
def test_leavemealone_wiring(skill):
  text = (ROOT / f"skills/{skill}/SKILL.md").read_text(encoding="utf-8")
  body = text.split("---", 2)[2]
  section = body[body.index("## Leavemealone-mode"):]
  for snippet in WIRING[skill] + COMMON:
    assert snippet in section, (skill, snippet)
  assert "merge" not in section.lower().replace("awaiting merge", "")
  assert "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first." in body
  assert len(body.encode("utf-8")) <= 24_000


def test_close_writes_closed_at_and_journals_unlanded(world):
  seed(world)
  state = json.loads(store(world.repo).path("state").read_text(encoding="utf-8"))
  state["status"] = {"units": {"U07": {"landed": True}, "U08": {"landed": False}, "U09": {"landed": False}}}
  put(world, state, "state")
  assert world.run("close", "--runcard", world.card("wave"))[0] == 1
  runcard = world.card("integrate")
  code, out = world.run("close", "--runcard", runcard)
  assert code == 0 and out.strip() == "closed sample-design-abc123; unlanded: U08, U09", out
  state = json.loads(store(world.repo).path("state").read_text(encoding="utf-8"))
  closed_at = state["closed_at"]
  assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)", closed_at)
  journal = (world.artifacts / "journal.md").read_text(encoding="utf-8")
  assert "close: U08 unlanded\n" in journal and "close: U09 unlanded\n" in journal
  assert f"closed sample-design-abc123 at {closed_at}\n" in journal
  code, out = world.run("close", "--runcard", runcard)
  assert code == 1 and f"close: already closed at {closed_at}" in out
  assert json.loads(store(world.repo).path("state").read_text(encoding="utf-8"))["closed_at"] == closed_at


def test_integrate_skill_body():
  text = (ROOT / "skills/integrate/SKILL.md").read_text(encoding="utf-8")
  front, body = text.split("---", 2)[1:]
  assert "disable-model-invocation: true" in front and "effect_kinds: [state-store, start-session]" in front
  for snippet in [
      "runcard open --skill integrate --artifact <spec-path>",
      # `status` serves the integrate card (I-4): no wave card, so `wave_number` never counts one.
      "status --wait 1 --runcard <card>",
      "review open --kind integrate --artifact <spec-path> --reviewers <config.reviewers.integrate> --runcard <card>",
      "git diff <base_at_start>..<base>",
      "review record --review <id> --round 1",
      "review status --review <id> --runcard <card>",
      "review settle --review <id> --finding <fid> --disposition escalated --runcard <card>",
      "(from integrate, review <id>)",
      "approve-spec --spec <spec-path> --amend-units --runcard <card>",
      "close --runcard <card>",
      "runcard close <card>",
      "`--close`", "nothing to escalate", "every unlanded unit",
      "`plan` → `review-plan` → `file` → `wave`",
      "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.",
  ]:
    assert snippet in body, snippet
  assert not re.search(r"--approve|--request-changes|gh pr merge|merge locally", body)
  assert len(body.encode("utf-8")) <= 24_000


DOCS = {
    "docs/index.md": ["SuperEGM", "](getting_started.md)", "](claude.md)", "](faq.md)", "](privacy.md)", "](releases.md)"],
    "docs/getting_started.md": ["/superegm:brainstorming", "/superegm:review-spec", "/superegm:plan", "/superegm:review-plan",
                                "/superegm:file", "/superegm:wave", "/superegm:integrate", "/superegm:judges",
                                ".superegm/config.json", "--leavemealone", "merge", "builder account"],
    "docs/claude.md": ["omitClaudeMd", "SubagentStart", "SUPEREGM_ROLE", "SUPEREGM_GOLDFISH_MODEL", "claude -p",
                       "config.builder.profile_dir", "GH_TOKEN", "superegm:judge", "superegm:foreman", "git worktree add"],
    "docs/faq.md": ["leavemealone-mode", "builder account", "Nothing is merged by a machine"],
    "docs/privacy.md": ["claudex-loop", "question file", "SUPEREGM_BUILDER_TOKEN", "config.astra", "artifacts_dir", "banned_terms"],
    "docs/releases.md": ["python3 scripts/prepare_release.py --tag v1.0.0", "superegm-1.0.0.zip", "SHA256SUMS",
                         "`plugin.json`", "`.claude-plugin/plugin.json`"],
}


@pytest.mark.parametrize("path", sorted(DOCS))
def test_docs_content(path):
  text = (ROOT / path).read_text(encoding="utf-8")
  for snippet in DOCS[path]:
    assert snippet in text, (path, snippet)
  assert re.search(r"Modified by SuperEGM \(gsVAM\), 2026: ", text), path


NOTICE = re.compile(r"Modified by SuperEGM \(gsVAM\), 2026: |From superpowers 7\.0\.0 \(MIT\); modified by SuperEGM \(gsVAM\), 2026: ")
SKIP = (".git", ".pytest_cache", "__pycache__", "tests")


def test_readme_install_and_licence():
  readme = (ROOT / "README.md").read_text(encoding="utf-8")
  for snippet in [
      "claude plugin disable egm@egm-astra", "claude plugin disable superpowers@claude-plugins-official",
      "```sh\nclaude plugin marketplace add gsVAM/superegm\nclaude plugin install superegm@superegm\n```",
      "builder account", "SUPEREGM_BUILDER_TOKEN", "config.builder.profile_dir", "no plugins and no `CLAUDE.md`",
      "restrict", "`superegm/**`", "force-push", "`pull_request`", "SubagentStart", "`LICENSE-MIT`",
  ]:
    assert snippet in readme, snippet
  paragraph = next(p for p in readme.split("\n\n") if p.startswith("**Licence.**"))
  listed = set(re.findall(r"`([^`]+)`", paragraph)) - {"LICENSE", "LICENSE-MIT"}
  assert all((ROOT / p).is_file() for p in listed), sorted(p for p in listed if not (ROOT / p).is_file())
  carrying = set()
  for path in ROOT.rglob("*"):
    rel = path.relative_to(ROOT)
    if not path.is_file() or any(part in SKIP for part in rel.parts) or rel.parts[:2] == ("docs", "specs"):
      continue  # docs/specs quotes the notice form
    try:
      text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
      continue
    if NOTICE.search(text):
      carrying.add(rel.as_posix())
  assert "README.md" in carrying
  # shortcut: tests/ are compared by existence only, since test files quote the notice text; drop the exclusion
  # when the notice tests stop quoting it
  assert {p for p in listed if not p.startswith("tests/")} == carrying, sorted(listed ^ carrying)


REMOVED = ["egm-bootstrap", "synthesizer", "bootstrap_orchestrator", "distributions/claude", "EGM_PANEL", "EGM_ASTRA",
           "EGM_GOLDFISH", ".egm/handoff.json", "egm-review-loop", "egm-resolve", "egm-handoff", "egm-wave",
           "egm_handoff.py", "handoff_state.json", "--published", "gate --accept", "merge locally", "Merge back locally",
           "visual companion", "/egm:", "codex plugin", "docs/codex.md", "docs/harnesses.md", "ChatGPT", "Antigravity",
           ".codex-plugin", "egm-openai", "egm-claude", "attestation", "foreman_<unit-id>_state.json", "--defer", "defer ",
           "head-moved", "rebase-only", "concepts_brief.md", "design_draft.md", "Stage 7", "Stage 9"]
MINE = ["README.md", "docs/index.md", "docs/getting_started.md", "docs/claude.md", "docs/faq.md", "docs/privacy.md",
        "docs/releases.md", "scripts/prepare_release.py", "tests/unit/test_releases.py", "skills/review-spec/SKILL.md",
        "skills/review-plan/SKILL.md", "skills/plan/SKILL.md", "skills/wave/SKILL.md", "skills/integrate/SKILL.md",
        "skills/judges/references/leavemealone.md", "skills/plan/scripts/superegm/judges.py",
        "skills/plan/scripts/superegm/close.py"]


@pytest.mark.parametrize("path", MINE)
def test_no_removed_mechanism_named(path):
  text = (ROOT / path).read_text(encoding="utf-8")
  hits = [term for term in REMOVED if re.search(r"(?<!SUPER)" + re.escape(term), text)]  # SUPEREGM_* stays
  assert not hits, (path, hits)
