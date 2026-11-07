# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U22, rulings by GitHub comment (spec §13.2).

"""U22: the one ruling grammar `decision.ruling_of`, its renderer `ruling_form` and the builder prompt's keep rule."""

import pytest

from superegm.decision import ruling_of

FORMS = [
  ("**Ruling:** f-2-1 finding upheld", ("upheld", "f-2-1", None, None)),
  ("**Ruling:** f-2-1 finding upheld (fix it)\n\n> the finding", ("upheld", "f-2-1", None, None)),
  ("**Ruling:** f-2-1 finding overruled — the test covers it", ("overruled", "f-2-1", None, "the test covers it")),
  ("**Ruling:** one more round", ("round", "", None, None)), ("**Ruling:** f-2-1 finding overruled — done.", ("overruled", "f-2-1", None, "done.")),
  ("**Ruling:** stop", ("stop", "", None, None)),
  ("**Ruling:** (77) (b) use Redis — already a dependency", ("option", "77", "(b) use Redis", "already a dependency")),
  ("**Ruling:** dod-3 allowed — a service the worktree lacks", ("allowed", "dod-3", None, "a service the worktree lacks")),
  ("**Ruling:** test-delta tests/unit/test_x.py allowed — by design", ("allowed-file", "tests/unit/test_x.py", None, "by design")),
  ("**Ruling:** redesign — the queue is the wrong shape", ("redesign", "", None, "the queue is the wrong shape")),
  ("**Ruling:** f-2-1 finding upheld now", None), ("**Ruling:** f-2-1 finding overruled", None), ("**Ruling:** (77) use Redis", None),
  ("**Ruling:** (cap) stop", None), ("**Ruling:** (77) use Redis — fine\n(judges p-1, leavemealone)\n\n> q", None)]


@pytest.mark.parametrize("body, expect", FORMS)
def test_ruling_of_is_the_one_grammar(body, expect):
  comment = {"id": 501, "user": {"login": "gsvam"}, "body": body}
  ruling = ruling_of(comment, ["gsvam", "other"])
  assert (ruling and (ruling.kind, ruling.subject, ruling.option, ruling.reason)) == expect
  assert ruling_of(comment, ["other"]) is None and (not expect or (ruling.login, ruling.comment_id) == ("gsvam", 501))
