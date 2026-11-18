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
