# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U109's pins of the plan-and-approval rows (1.3 design section 3.10): path-shaped Step spans, the panel check at load, the whitespace-bounded review location.

"""U109: `step_paths` reads only path-shaped spans; `load_config` checks each `reviewers.<kind>` panel;
`out_of_scope` reads a review location's file name as a whitespace-free token."""

import re

import pytest
import superegm
from superegm import body

from conftest import set_config


@pytest.mark.parametrize("write, implement, test_path, impl_path", [
  ("1. Write the failing test `test_x` in `tests/unit/test_u01.py`:", "   Implement the default `stall_minutes` 60 in `launch_builder.py`, refusing `0`.",
   "tests/unit/test_u01.py", "launch_builder.py"),
  ("1. Write the failing test `test_x` in `tests/unit/test_u01.py`:", "   Implement the skill in `skills/sweep/` with `--max`.",
   "tests/unit/test_u01.py", "skills/sweep/"),
  ("1. Write the failing test `test_x` for `U07` in `tests/unit/test_u01.py`:", "   Implement `--max` capped at `20`.",
   "tests/unit/test_u01.py", None),
  ("1. Write the failing test `test_x`:", "   Implement it in `skills/x.py`.", None, "skills/x.py"),
])
def test_step_paths_reads_only_path_shaped_spans(write, implement, test_path, impl_path):
  # a path-shaped span holds a `/` or ends in a file extension; any other span is no path
  assert body.step_paths(f"## Steps\n{write}\n{implement}\n") == [(1, test_path, impl_path)]


@pytest.mark.parametrize("reviewers, refused", [
  ({"spec": ["zoom-out"]}, "reviewers.spec"),
  ({"plan": ["readiness", "proportion"]}, "reviewers.plan"),
  ({"head": []}, "reviewers.head"),
  ({"integrate": ["style"]}, "reviewers.integrate"),
  ({"spec": ["design", "zoom-out", "style"], "head": ["change-review"]}, None),
  ({}, None),
])
def test_load_config_checks_each_panel(world, reviewers, refused):
  # .superegm/config.json's reviewers; each reviewers.<kind> opens with review.PANEL_OF[<kind>], as CI checks the repository's own
  set_config(world, repo="example-org/webhooks", reviewers=reviewers)
  if refused:
    with pytest.raises(superegm.HandoffError, match=re.escape(refused)):
      superegm.load_config(world.repo)
  else:
    assert superegm.load_config(world.repo)["reviewers"]["plan"][:3] == ["readiness", "proportion", "set"]


SPEC_TEXT = "# Spec\n\n## A\nline\nline\n\n## B\nline\nline\n"
SCOPE = [("changed", "B", 7, 9), ("changed", "docs/reference/domain model.md", 0, 0)]


@pytest.mark.parametrize("location, answer", [
  ("design.md line 8 contradicts docs/reference/domain model.md", None),
  ("design.md line 4 contradicts docs/reference/domain model.md", "## A"),
  ("design.md line 8 contradicts a/b.md:12", None),
  ("docs/specs/design.md line 8 contradicts a/b.md:12", None),
  ("other/domain model.md, line 8", "none"),
  ("docs/reference/domain model.md:500", None),
  ("line 8 of design.md", None),                                     # a token after the first line cite names no file: the spec's line
  ("§2 line 8 contradicts README.md", None),
  ("domain model.md line 12 vs docs/specs/design.md", None),         # a listed document's bare name opens it; the later `/` decides nothing
])
def test_location_stops_at_whitespace_before_a_slash_path(location, answer):
  # spec docs/specs/design.md SPEC_TEXT; rows, spans: the round's scope (## B changed, docs/reference/domain model.md listed)
  # and the spec's sections; a file name stops at whitespace (spec 3.10)
  from superegm import review
  assert review.out_of_scope(SCOPE, review.sections(SPEC_TEXT), location, "docs/specs/design.md") == answer
