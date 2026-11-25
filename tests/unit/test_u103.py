# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U103's tests: rulings (1.3 design sections 3.6, 3.7 and 3.10): the missing-fid refusal of a point-1 ruling.

"""U103: `decision rule` refuses a point-1 ruling with no fid, settles the finding a point-1 ruling rules, and refuses an
edited ruling comment."""

import pytest

from test_wave import foreman_of, open_wave_card, question, wave_store

FINDING = "foreman-1-1 | high | src/x.py:3 | regression: no | the retry loop never backs off\n"


@pytest.mark.parametrize("ruling", ["finding overruled — the test moved", "finding overruled", "finding upheld"])
def test_a_ruling_without_a_fid_says_so(world, ruling):
  """A point-1 ruling that opens with the verdict is refused, `<fid>` written as the spec writes it, nothing recorded."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  qid = world.run("decision", "open", "--unit", "U01", "--point", 1, "--question", question(world, FINDING),
                  "--source", "review head-U01-c1 round 1", "--runcard", card)[1].splitlines()[0]
  rulings_before = foreman_of(s, "U01")["rulings"]
  code, err = world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", ruling, "--by", "owner",
                        "--runcard", card)
  rulings_after = foreman_of(s, "U01")["rulings"]
  assert code == 1 and 'missing <fid>: write "<fid> finding overruled"' in err
  assert rulings_after == rulings_before
  assert not world.gh.comments, "a refused ruling posts nothing"
