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


LOOP, BRIEF, JUDGES, ASTRA_JUDGE, PANELS = ("skills/review-spec/references/review_loop.md", "skills/wave/references/foreman_brief.md",
                                            "skills/judges/SKILL.md", "skills/judges/references/astra_judge.md", "resources/review_panels.md")
RULE = [(LOOP, n) for n in ("Model and effort, one rule:", "`config.reviewers.model` at `config.reviewers.effort`", "the adapters stay `model: inherit`",
                            "`SUPEREGM_GOLDFISH_MODEL` and `SUPEREGM_GOLDFISH_EFFORT`, when set, override", "`inherit` meaning pass nothing",
                            "`CLAUDE_CODE_EFFORT_LEVEL` is the effective effort of every goldfish", "`CLAUDE_CODE_SUBAGENT_MODEL_FORCE` on no per-call `model` is passed",
                            "judges use their member's model and effort", "the foreman's Astra lane runs at `astra.heads_effort`",
                            "The elephant is the session's model, never in config.", "| Claude goldfish | `config.reviewers.model`, or `SUPEREGM_GOLDFISH_MODEL`")] + [
  (BRIEF, "`<GOLDFISH_MODEL>` and `<GOLDFISH_EFFORT>` are `config.reviewers.model` and"), (BRIEF, "Read `astra.model` and `astra.heads_effort` from .superegm/config.json"),
  (BRIEF, "(a key the file lacks is `gpt-6-astra`, `high`)"), (BRIEF, "--model <model> --effort <heads_effort> --timeout 540"),
  (JUDGES, "the override read per judge from `<STORE>/judges/<PANEL>/panel.json`"), (JUDGES, "`judges.<id>.model` as `model:` and `judges.<id>.effort` as `effort:`"),
  (JUDGES, "the effective pair by `review_loop.md`'s one rule"), (ASTRA_JUDGE, "the `astra` member's `model` and `effort` in `<STORE>/judges/<PANEL>/panel.json`"),
  (PANELS, "SuperEGM's one rule is `skills/review-spec/references/review_loop.md` section 2"),
  (PANELS, "`inherit` is never passed, even when the user selected it"), (PANELS, "pass no other model or effort parameter"), (LOOP, "with `requested -> effective`:")]
ABSENT = [(BRIEF, "`xhigh`"), (JUDGES, "effort `max` where the Agent tool offers it"), (ASTRA_JUDGE, "are `config.astra.model` and `config.astra.effort`"), (LOOP, "section 6 with the variables")]


@pytest.mark.parametrize("path, needle, present", [(p, n, True) for p, n in RULE] + [(p, n, False) for p, n in ABSENT])
def test_the_one_model_rule_in_the_skills_and_resources(path, needle, present):
  assert (needle in (ROOT / path).read_text(encoding="utf-8")) is present, (path, needle)
