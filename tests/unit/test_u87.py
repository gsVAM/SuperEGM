# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U87's tests, spec sections 7.5 and 7.7: the post-mortem's Lessons table, `postmortem --retro` and the retro skill.

"""U87: the Lessons table, `superegm postmortem --retro <file>` and the `/superegm:retro` skill."""

import json

import pytest
from conftest import ROOT
from test_u43 import SLUG, jread, jwrite
from test_u43 import registry  # noqa: F401  (the autouse fixture: no test reads the owner's registry)
from test_u78 import two_units

DEVIATION = ("**Deviation (spec):** the retry delay the spec states cannot hold.\n\n"
             "Evidence: `docs/specs/x.md:12` says 5s; the builder's test needs 6s.\n\n**Builder status:** BLOCKED\n")


def lessons(report):
  """The Lessons section's rows, each as one line of text."""
  body = report.split("## Lessons\n", 1)[1].split("\n## ", 1)[0]
  return [line for line in body.splitlines() if line.startswith("|")][2:]


def respec_world(world, comment):
  """`two_units`' handoff with respec R1 applied (opened for U02 on comment 901, its approval entry ranges `12-14`);
  `comment(args)` answers the one `gh api` read of that comment. U01's second launch is escalated."""
  c, _, _ = two_units(world)
  answer = world.gh.handlers["api"]

  def api(args, cwd, token=None):
    return comment(args) if "issues/comments/901" in args[1] else answer(args, cwd, token=token)
  world.gh.extend("api", api)
  path = c.root / "approvals" / f"{SLUG}.json"
  record = jread(path)
  record["entries"].append({**record["entries"][-1], "kind": "respec", "respec": "R1", "ranges": [[12, 14], [30, 31]]})
  jwrite(path, record)
  jwrite(c.hs.path("file", "respec", "R1.open.json"), {"id": "R1", "unit": "U02", "comment_id": 901, "at": "2026-11-16T00:00:00Z"})
  return c


def test_lessons_rows(world):
  # a store with one respec and one escalated unit gives two Lessons rows, facts with their source record
  c = respec_world(world, lambda args: (0, json.dumps({"id": 901, "body": DEVIATION}), ""))
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  rows = lessons(c.hs.path("file", "postmortem.md").read_text(encoding="utf-8"))
  spec = c.spec.resolve().relative_to(world.repo.resolve()).as_posix()
  assert len(rows) == 2
  assert "R1" in rows[0] and "U02" in rows[0] and f"{spec}:12-14" in rows[0] and "R1.open.json" in rows[0]
  assert "the builder's test needs 6s" in rows[0] and "retry delay" in rows[0] and "30-31" not in rows[0]
  assert "U01" in rows[1] and "escalated" in rows[1]


def test_lessons_respec_evidence_unread(world):
  # a comment read that fails leaves the row and says so
  c = respec_world(world, lambda args: (1, "", "HTTP 404"))
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  rows = lessons(c.hs.path("file", "postmortem.md").read_text(encoding="utf-8"))
  assert len(rows) == 2 and "evidence unread (comment 901)" in rows[0]


def test_retro_copy(world, tmp_path):
  # --retro copies the file in, needs no run card, writes only the store's file kind
  from superegm import postmortem
  from test_u78 import snapshot
  c, _, _ = two_units(world)
  source = tmp_path / "agreed-retro.md"
  source.write_bytes("# Retro\n\n- the reviewer file gains one line\né\n".encode())
  before = snapshot(c.root)
  code, out = world.run("postmortem", "--handoff", c.hid, "--retro", str(source))
  after = snapshot(c.root)
  retro_md = c.hs.path("file", "retro.md")
  assert code == 0, out
  assert retro_md.read_bytes() == source.read_bytes() and set(after) - {retro_md} == set(before)
  assert {p for p in before if after[p] != before[p]} == set()
  assert postmortem.WRITES == frozenset(["file"])


def text(path):
  return (ROOT / path).read_text(encoding="utf-8")


def frontmatter(path):
  import yaml
  return yaml.safe_load(text(path).split("---", 2)[1])


@pytest.mark.parametrize("phrase", ["reference document", "reviewer file", "`.superegm/config.json`", "`.superegm/brainstorm.md`",
                                    "owner's yes", "suggested answer", "one question at a time", "`retro: <handoff>`",
                                    "superegm postmortem --handoff <id> --retro <file>", "never edits the approved spec", "every open handoff"])
def test_retro_skill_text(phrase):
  # the retro skill names its four targets, asks per edit, and never touches an approved spec
  assert phrase in text("skills/retro/SKILL.md") and frontmatter("skills/retro/SKILL.md")["effect_kinds"] == ["state-store"]


@pytest.mark.parametrize("path, phrase", [("skills/integrate/SKILL.md", "/superegm:retro"), ("skills/using-superegm/SKILL.md", "/superegm:retro")])
def test_integrate_offers_retro_and_phase_list(path, phrase):
  # integrate offers the retrospective once after the post-mortem; the phase list ends with it
  assert phrase in text(path)
