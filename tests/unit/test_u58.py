from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("path, start, end", [
    ("skills/review-spec/SKILL.md", "### 5. At the cap", "### 6. Stalled"),
    ("skills/review-spec/SKILL.md", "### 6. Stalled", "### 7. Close"),
    ("skills/review-plan/SKILL.md", "- `cap`:", "\n- "),
    ("skills/review-plan/SKILL.md", "- `stalled`:", "\n- `cap`:"),
])
def test_skills_offer_proceed(path, start, end):
    text = (ROOT / path).read_text()
    i = text.index(start)
    j = text.index(end, i + len(start))
    passage = text[i:j]
    assert "review rule" in passage
    assert ("--ruling proceed --owner" in passage
            or "--ruling 'proceed' --owner" in passage)
    if "stalled" in start.lower():
        assert ("ends the invocation" in passage
                or "End this invocation" in passage)
    else:
        # the judges' cap question keeps its options; proceed is the owner's way past
        for opt in ("continue", "accept", "stop"):
            assert opt in passage
        assert "owner" in passage


def test_review_spec_closing_line():
    text = (ROOT / "skills/review-spec/SKILL.md").read_text()
    i = text.index("Tell the owner, in one line:")
    para = text[i:].split("\n\n", 1)[0]
    a = para.index("origin/<base>")
    b = para.index("check out `<base>` at the pushed commit")
    c = para.index("waiting checkout")
    assert a < b < c
    assert "Nothing chains." not in text
