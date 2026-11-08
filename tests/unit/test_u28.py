"""U28: the default models and efforts per role (spec section 7, amendment 8)."""
import json

import pytest

import superegm
from conftest import ROOT, REPO, set_config

PRE_U28 = {"builder": {"model": "claude-sonnet-5-5"}, "reviewers": {"head": ["change-review"]}, "astra": {"enabled": True},
           "judges": {"min_vendors": 1, "members": [{"name": "fable", "via": "adapter", "effort": "max"}, {"name": "astra", "via": "runner"}]}}


def test_default_models_and_efforts_per_role(world):
  d = superegm.DEFAULT_CONFIG
  assert (d["builder"]["model"], d["builder"]["effort"]) == ("claude-opus-5-5", "medium")
  assert (d["reviewers"]["model"], d["reviewers"]["effort"]) == ("opus", "xhigh") and set(d["reviewers"]) == {"spec", "plan", "head", "integrate", "model", "effort"}
  assert d["astra"] == {"enabled": False, "model": "gpt-6-astra", "effort": "xhigh", "heads": True, "heads_effort": "high"}
  assert [(m["name"], m["via"], m["effort"]) for m in d["judges"]["members"]] == [("fable", "adapter", "xhigh"), ("opus", "adapter", "max"), ("astra", "runner", "xhigh")]
  set_config(world, repo=REPO, **PRE_U28)
  config = superegm.load_config(world.repo)
  assert (config["builder"]["model"], config["builder"]["effort"], config["builder"]["app"]) == ("claude-sonnet-5-5", "medium", None)
  assert (config["reviewers"]["model"], config["reviewers"]["effort"], config["reviewers"]["head"], config["reviewers"]["spec"]) == ("opus", "xhigh", ["change-review"], ["design", "zoom-out"])
  assert config["astra"] == {**d["astra"], "enabled": True} and config["judges"] == PRE_U28["judges"]   # the written members stand; judge_members fills a runner member's effort
  (world.repo / ".superegm/config.json").unlink()
  world.gh.extend("api", lambda args, cwd, token=None: (0, "octocat\n", ""))
  assert world.run("init", "--artifacts-dir", str(world.artifacts))[0] == 0
  written = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))
  assert all(written[k] == d[k] for k in ("builder", "reviewers", "astra", "judges"))   # init writes DEFAULT_CONFIG verbatim
