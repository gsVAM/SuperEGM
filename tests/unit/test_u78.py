# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U78's tests: a wait's journaled and kept history, and `superegm postmortem` (spec section 7.5).

"""U78: the post-mortem, and the wait history it reads."""

import hashlib
import json

import pytest
from conftest import CONFIG
from test_u43 import Chain, jread
from test_u43 import registry  # noqa: F401  (the autouse fixture: no test reads the owner's registry)
import superegm


def sha(text):
  return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stamp(world):
  """The store's stamp of the world's clock."""
  return superegm.iso(world.clock)


def chain_world(world):
  """A chained handoff whose owner is `owner` and whose `gh api user` answers `owner`."""
  path = world.repo / CONFIG
  config = json.loads(path.read_text(encoding="utf-8"))
  path.write_text(json.dumps({**config, "owners": ["owner"]}), encoding="utf-8")
  world.gh.extend("api", lambda args, cwd, token=None: (0, "owner\n", ""))
  return Chain(world)


def wait(world, c, phase, question):
  """`next wait` on a fresh card of `phase`'s skill; the `at` it is stamped with."""
  at = stamp(world)
  card = world.open_card(phase, c.spec)
  code, out = world.run("next", "wait", "--handoff", c.hid, "--phase", phase, "--question", question, "--runcard", card)
  assert code == 0, out
  return at


def answer(world, c, text):
  code, out = world.run("next", "answer", "--handoff", c.hid, "--answer", text)
  assert code == 0, out
  return stamp(world)


def journal_of(c):
  """The handoff journal's `next ...` lines, each without its leading timestamp."""
  path = c.hs.path("journal")
  lines = [line.split(" ", 1)[1] for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []
  return [line for line in lines if line.startswith("next ")]


def test_reask_keeps_the_first_answer(world):
  c = chain_world(world)
  waits = c.hs.path("file", "waits")
  q1, q2 = "split U02?", "split U02 and U03?"
  since1 = wait(world, c, "plan", q1)
  assert journal_of(c)[-1].startswith(f"next wait {c.hid} plan since {since1} source ")
  assert journal_of(c)[-1].endswith(f" question {sha(q1)}")
  assert (waits / f"plan-{since1}.md").read_text(encoding="utf-8") == q1
  world.advance(60)
  answer(world, c, "first answer")
  # a re-ask: the skill's `next wait` on a phase whose record holds an answer
  world.advance(60)
  at2 = wait(world, c, "plan", q2)
  record = jread(c.root / "chain" / f"{c.hid}.json")
  assert (waits / f"plan-{since1}.answer.md").read_text(encoding="utf-8") == "first answer"
  assert journal_of(c)[-1] == f"next reask {c.hid} plan at {at2} question {sha(q2)}"
  assert record["since"] == at2 and (waits / f"plan-{at2}.md").read_text(encoding="utf-8") == q2
  assert (waits / f"plan-{since1}.md").read_text(encoding="utf-8") == q1
  world.advance(60)
  answer(world, c, "second answer")
  assert (waits / f"plan-{at2}.answer.md").read_text(encoding="utf-8") == "second answer"
  assert (waits / f"plan-{since1}.answer.md").read_text(encoding="utf-8") == "first answer"


@pytest.mark.parametrize("event", ["reask", "stop then next clear then a second answer"])
def test_answer_json_is_never_rewritten(world, event):
  c = chain_world(world)
  c.save()
  waits = c.hs.path("file", "waits")
  since1 = wait(world, c, "plan", "split U02?")
  world.advance(60)
  at1 = answer(world, c, "first answer")
  first_bytes = (waits / f"plan-{since1}.answer.json").read_bytes()
  world.advance(60)
  if event == "reask":
    since2 = wait(world, c, "plan", "split U02 and U03?")
  else:
    since2 = stamp(world)
    card = world.open_card("plan", c.spec)
    code, out = world.run("next", "clear", "--handoff", c.hid, "--runcard", card)
    assert code == 0, out
    # the stopped record is a new wait: its own since, its question kept, the answered one's line journaled
    assert jread(c.root / "chain" / f"{c.hid}.json")["since"] == since2
    assert f"next clear {c.hid} plan answered by owner at {at1} answer {sha('first answer')}" in journal_of(c)
    assert (waits / f"plan-{since2}.md").is_file()
  assert (waits / f"plan-{since1}.answer.json").read_bytes() == first_bytes
  assert (waits / f"plan-{since1}.answer.md").read_text(encoding="utf-8") == "first answer"
  assert (waits / f"plan-{since1}.md").read_text(encoding="utf-8") == "split U02?"
  world.advance(60)
  at2 = answer(world, c, "second answer")
  assert (waits / f"plan-{since1}.answer.json").read_bytes() == first_bytes
  second = json.loads((waits / f"plan-{since2}.answer.json").read_text(encoding="utf-8"))
  assert second == {"by": "owner", "at": at2, "sha": sha("second answer")}
  assert set(second) == {"by", "at", "sha"}
