# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U76's tests: the reviewers module, its doctor line, `review open` taking a loaded reviewer and the frozen persona.

"""U76: custom reviewers, the helper."""

import pytest

import superegm  # the harness reloads the package per test: read its names at call time


def write_reviewer(root, name, text):
  """`.superegm/reviewers/<name>` under `root`, written as UTF-8 text."""
  path = root / ".superegm" / "reviewers" / name
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("name, text", [
  ("Bad_id.md", "---\nname: X\nkinds: [spec]\n---\nbody"),
  ("nameless.md", "---\nkinds: [spec]\n---\nbody"),
  ("nokinds.md", "---\nname: X\nkinds: []\n---\nbody"),
  ("big.md", "---\nname: X\nkinds: [spec]\n---\n" + "b" * 8193),
  ("foreman.md", "---\nname: X\nkinds: [head]\n---\nbody")])
def test_a_bad_reviewer_file_is_refused_naming_it(world, name, text):
  """An id outside [a-z][a-z0-9-]{1,31}, no name, empty kinds, a body over 8,192 bytes and a non-reviewer override are each refused naming the file."""
  from superegm import reviewers
  write_reviewer(world.repo, "fine.md", "---\nname: Fine\nkinds: [spec, head]\n---\nA persona.\n")
  write_reviewer(world.repo, name, text)
  with pytest.raises(superegm.HandoffError) as refusal:
    reviewers.load(world.repo)
  assert f".superegm/reviewers/{name}" in str(refusal.value)


def test_doctor_prints_the_reviewers_line_after_mcp(world, monkeypatch, tmp_path):
  """With no reviewer file the line after `mcp:` is `reviewers: none`."""
  from test_doctor import arranged
  arranged(world, monkeypatch, tmp_path, None)
  got, out = world.run("doctor")
  lines = out.splitlines()
  assert got == 0, out
  assert lines[lines.index(next(l for l in lines if l.startswith("mcp:"))) + 1] == "reviewers: none"


@pytest.mark.parametrize("kind, reviewers, code, expect", [
  ("spec", "design,zoom-out,security", 0, "design"),
  ("head", "security", 1, "review open: security does not review head")])
def test_review_open_takes_a_loaded_reviewer_for_its_kinds(world, kind, reviewers, code, expect):
  """A loaded id whose kinds holds the review's kind opens; one that does not is refused; an overridden design keeps its id."""
  from test_review import SKILL_OF, card, rjson, seed_handoff, spec_file
  from test_u37 import commit_file
  commit_file(world, ".superegm/reviewers/security.md", "---\nname: Security\nkinds: [spec]\n---\nHunt for secrets.\n")
  commit_file(world, ".superegm/reviewers/design.md", "---\nname: Design\nkinds: [spec]\n---\nA new design persona.\n")
  spec = spec_file(world)
  seed_handoff(world, spec)
  cid = card(world, spec, SKILL_OF[kind])
  artifact = str(spec) if kind == "spec" else "U07"
  got, out = world.run("review", "open", "--kind", kind, "--artifact", artifact, "--reviewers", reviewers, "--astra", "off", "--runcard", cid)
  assert got == code and (expect in out if code else rjson(world, out.splitlines()[0])["reviewers"][0] == expect), out
