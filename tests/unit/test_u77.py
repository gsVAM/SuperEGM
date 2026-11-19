from pathlib import Path

import pytest


@pytest.mark.parametrize("path", ["skills/review-spec/references/review_loop.md", "skills/review-plan/SKILL.md",
                                  "skills/integrate/SKILL.md", "skills/wave/references/foreman_brief.md"])
@pytest.mark.parametrize("phrase", ["superegm:repo-reviewer", "superegm reviewers --brief", "# Reviewer persona",
                                    "overridden built-in", "the file's `model` and `effort`", "config.reviewers.model", "SUPEREGM_GOLDFISH_"])
def test_each_dispatch_text_names_the_repo_reviewer_path(path, phrase):
    # a repository or overridden reviewer goes through the one adapter with its frozen persona and its own model first
    assert phrase in Path(path).read_text(encoding="utf-8")
