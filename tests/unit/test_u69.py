# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U69's tests: `superegm next answer`, the owner's words on an unanswered wait record.

"""U69: `superegm next answer --handoff <id> --answer <text>`."""

import hashlib
import json

import pytest
from conftest import CONFIG, REPO
from test_u43 import Chain, jread
from test_u43 import registry  # noqa: F401  (the autouse fixture: no test reads the owner's registry)

QUESTION = "waiting file: Create these 3 issues and 2 links"


def chain_of(world, login="owner", owners=("owner",), **record):
  """A chained handoff holding a wait record on `file`, `config.owners` as given, and `gh api user` answering `login`."""
  path = world.repo / CONFIG
  config = json.loads(path.read_text(encoding="utf-8"))
  path.write_text(json.dumps({**config, "owners": list(owners)}), encoding="utf-8")
  world.gh.extend("api", lambda args, cwd, token=None: (0, login + "\n", ""))
  c = Chain(world)
  c.save()
  c.wait(**{"phase": "file", "question": QUESTION, **record})
  return c, world.artifacts / "chain" / f"{c.hid}.json"


def answer(world, c, *extra, text="go on with the plan"):
  """`next answer`; a refusal by the parser (a status of 2) counts as a code that is not 0."""
  try:
    return world.run("next", "answer", "--handoff", c.hid, "--answer", text, *extra)
  except SystemExit as stop:
    return stop.code, ""


def test_next_answer_writes_the_answer(world):
  # the login comes from gh itself, never an argument; no run card is opened or required
  c, path = chain_of(world)
  code, out = answer(world, c)
  record = jread(path)
  assert code == 0, out
  assert world.gh.calls[-1] == ["api", "user", "--jq", ".login"]
  assert (record["answer"], record["by"]) == ("go on with the plan", "owner") and record["at"]
  assert (record["phase"], record["question"]) == ("file", QUESTION)
  answer_json_path = c.hs.path("file", "waits", f"file-{record['since']}.answer.json")
  assert answer_json_path.name == f"file-{record['since']}.answer.json"
  assert jread(answer_json_path) == {"by": "owner", "at": record["at"], "sha": hashlib.sha256(b"go on with the plan").hexdigest()}
  assert not list((world.artifacts / c.hid).glob("runcards/*"))


ANSWERED = {"answer": "yes", "by": "owner", "at": "2026-11-15T01:00:00Z"}


@pytest.mark.parametrize("case", ["already answered", "no record", "login not an owner", "--phase given"])
def test_next_answer_refusals(world, case):
  # an answer needs an unanswered record and an owner's login
  c, path = chain_of(world, login="stranger" if case == "login not an owner" else "owner",
                     **(ANSWERED if case == "already answered" else {}))
  if case == "no record":
    path.unlink()
  record_bytes_before = path.read_bytes() if path.exists() else None
  code, out = answer(world, c, *(["--phase", "file"] if case == "--phase given" else []), text="a new answer")
  record_bytes_after = path.read_bytes() if path.exists() else None
  assert code != 0 and record_bytes_after == record_bytes_before
  assert not list((world.artifacts / c.hid).glob("waits/*"))
