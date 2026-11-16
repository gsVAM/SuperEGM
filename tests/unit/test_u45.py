# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U45's tests: the skills' wait, resume and frozen-mode wording under the driver, and the inbox's chained lines.

"""U45 (spec sections 7.1, 7.2): the plan, review-plan and wave skills wait, resume and take the frozen mode under the
driver; the inbox reads the frozen mode and shows a chained handoff's `waiting …` and `ready to integrate` lines."""

import importlib
import json

import pytest

from conftest import ROOT
from test_u43 import Chain, SLUG, jread, jwrite


@pytest.mark.parametrize("path,phase", [("skills/plan/SKILL.md", "plan"), ("skills/review-plan/SKILL.md", "review-plan")])
def test_skills_wait_and_resume(path, phase):
  # under the driver an owner question becomes next wait and exit; typed on a wait record: ask, record, run on, next clear
  text = " ".join((ROOT / path).read_text(encoding="utf-8").split())
  assert "SUPEREGM_ROLE=driver" in text and "next wait" in text and f"--phase {phase}" in text
  assert "runcard open --mode normal" in text and "next clear" in text


@pytest.mark.parametrize("path", ["skills/wave/SKILL.md", "skills/wave/references/leavemealone_mode.md",
                                  "skills/review-plan/SKILL.md", "skills/plan/SKILL.md"])
def test_skills_frozen_mode(path):
  # --mode leavemealone only when the invocation says --leavemealone, else runcard open's frozen default; config.mode kept as fallback
  text = " ".join((ROOT / path).read_text(encoding="utf-8").split())
  assert "frozen" in text and "`config.mode`" in text
  assert "or the config's `mode` is `leavemealone`" not in text and "--mode '<normal|leavemealone>'" not in text


def test_wave_batch_decision_and_exit():
  # driven normal mode opens points 1, 2, 3 and 5 as decision open records, holds that unit, handles every other event of the batch
  text = " ".join((ROOT / "skills/wave/SKILL.md").read_text(encoding="utf-8").split())
  assert "always `--leavemealone`" not in text
  assert "normal mode" in text and "points 1, 2, 3 and 5" in text and "every event of the batch" in text


@pytest.fixture
def home(tmp_path, monkeypatch):
  """`~/.superegm` under `tmp_path`: no test reads the owner's registry."""
  monkeypatch.setenv("HOME", str(tmp_path / "home"))


def edit_config(world, **keys):
  path = world.repo / ".superegm" / "config.json"
  path.write_text(json.dumps({**json.loads(path.read_text(encoding="utf-8")), **keys}), encoding="utf-8")


def freeze(chain, mode):
  """The approval entry's frozen `mode`; None leaves a 1.2.0 entry, which has none."""
  path = chain.root / "approvals" / f"{SLUG}.json"
  record = jread(path)
  record["entries"][-1].pop("mode", None)
  if mode:
    record["entries"][-1]["mode"] = mode
  jwrite(path, record)


def driver_lines(world, hid):
  code, out = world.run("inbox", "--json", "--handoff", hid)
  assert code == 0, out
  items = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
  return [i["action"] for i in items if i["kind"] == "driver"]


@pytest.mark.parametrize("chain,mode,line,shown", [
  (True, "leavemealone", "waiting push", "waiting push"),
  (True, "normal", "waiting checkout: {root}: dirty", "waiting checkout: {root}: dirty"),
  (True, None, "waiting fetch: origin: x", None), (False, "leavemealone", "waiting push", None),
  (True, "leavemealone", "integrate", "ready to integrate"),
  (True, "leavemealone", "integrate, U03 stopped issue open",
   "ready to integrate: close the issues of U03, or type /superegm:integrate --close")])
def test_inbox_chain_lines(world, home, monkeypatch, chain, mode, line, shown):
  # chained = driver.chain true and a frozen mode; only then is next's line an inbox line; mode None is a 1.2.0 entry
  c = Chain(world)
  c.all_filed("U03" if "stopped" in line else None)
  if "stopped" in line:
    c.stopped("U03")
  c.save()
  freeze(c, mode)
  edit_config(world, driver={"chain": chain}, mode="normal")
  printed = line.split(",")[0].format(root=world.repo)
  monkeypatch.setattr(importlib.import_module("superegm.phase"), "next_line", lambda st, hid, read_wait=True: printed)
  assert driver_lines(world, c.hid) == ([shown.format(root=world.repo)] if shown else [])
  # the inbox's mode before a wave card: the entry's, not the live config's
  c.all_filed("U02")
  c.save()
  freeze(c, "leavemealone")
  seen = []
  monkeypatch.setattr(importlib.import_module("superegm.inbox"), "unit_items",
                      lambda hs, repo, state, uid, foreman, mode="normal": seen.append(mode) or [])
  driver_lines(world, c.hid)
  assert seen == ["leavemealone"]
