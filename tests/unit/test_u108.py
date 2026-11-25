# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U108's tests: the `superegm-push` script, the allow-list, the orders' section, the per-form author rules, owner notes, the edited rule, the managed hooks, doctor's `managed:` line and the wave skill's probe (1.3 design section 3.7).

"""U108 (spec section 3.7): builder launch, orders and what reaches the prompt."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from superegm import launch_builder
from test_builders import ISSUE, UNIT, git, launches_of, seed, spawn_fake, no_graphify, which  # noqa: F401  the fixtures a launch runs under


def launch(world, monkeypatch, comments=(), rnd=1, card=None, seeded=None, foreman=None):
  """U07 seeded and marked (once), its foreman record `foreman` when given, its issue comments `comments`, then
  `launch-builder` round `rnd`: (store, card, hid)."""
  if seeded is None:
    s, card, hid, _ = seed(world)
    monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
    assert world.run("launch", "--runcard", card)[0] == 0
  else:
    s, card, hid = seeded
  if foreman is not None:
    from test_builders import put
    put(s.path("foreman", UNIT), json.dumps({"dispatch_id": "d1", "rounds": [], "decisions": [], "rulings": [], **foreman}))
  world.gh.comments[ISSUE] = list(comments)
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", rnd, "--runcard", card)
  assert code == 0, out
  return s, card, hid


def refs(bare: Path) -> dict:
  out = git(["for-each-ref", "--format=%(refname) %(objectname)"], bare)
  return dict(line.split(" ", 1) for line in out.splitlines())


def test_push_script_pushes_head_to_the_launch_branch(world, monkeypatch, spawn_fake):
  s, card, hid = launch(world, monkeypatch)
  bin_dir, wt, bare = s.path("launches", f"{UNIT}_r1_bin"), s.path("worktrees", UNIT, "r1"), world.repo.parent / "origin.git"
  git(["config", "push.followTags", "true"], world.repo)  # the flag the script must override
  main_before = refs(bare)["refs/heads/main"]
  (wt / "w.txt").write_text("w\n", encoding="utf-8")
  git(["add", "-A"], wt); git(["commit", "-qm", "feat(S1): w"], wt)
  git(["tag", "-a", "v-annotated", "-m", "annotated"], wt)
  worktree_head = git(["rev-parse", "HEAD"], wt).strip()
  done = subprocess.run([str(bin_dir / "superegm-push"), "origin", "HEAD:main", "--tags"], cwd=str(wt), capture_output=True, text=True)
  assert done.returncode == 0, done.stderr
  origin_refs, config_text = refs(bare), (world.repo / ".git/config").read_text(encoding="utf-8")
  assert os.access(bin_dir / "superegm-push", os.X_OK)
  assert origin_refs[f"refs/heads/superegm/{hid}/U07"] == worktree_head
  assert origin_refs["refs/heads/main"] == main_before
  assert "refs/tags/v-annotated" not in origin_refs
  assert f'[branch "superegm/{hid}/U07"]' not in config_text


RUNS = "## Definition of done\n2. Run `pytest tests/unit/test_u07.py -q` — passes\n"


@pytest.mark.parametrize("configured, body_text", [
    (["Read", "Edit", "Bash(git add:*)"], RUNS),
    (["Bash(pytest:*)", "Read"], RUNS),
    (["Read", "Agent", "Workflow"], RUNS),
    (["Read", "Bash(git push:*)", "Bash(git push -q origin superegm/h/U07:*)"], RUNS),
    (["Read"], "## Definition of done\n2. Run `git diff --check && pytest -q` — passes\n"),
])
def test_allow_list_names_the_push_script_and_no_git_push(configured, body_text):
  # the push script's absolute path stands in for every git push entry; a DoD segment led by git adds no entry; precheck and reset stay
  tools = launch_builder.allowed_tools(configured, "superegm/h/U07", body_text, "/usr/local/bin/gh", bin=Path("/bin/U07_r1_bin"))
  assert not any(t.startswith("Bash(git push") for t in tools) and "Bash(git:*)" not in tools
  assert tools.count("Bash(/bin/U07_r1_bin/superegm-push:*)") == 1
  assert {"Bash(/bin/U07_r1_bin/superegm-precheck:*)", "Bash(git reset --hard:*)"} <= set(tools)
  assert not any("push" in t for t in launch_builder.allowed_tools(configured, "superegm/h/U07", body_text, "/usr/local/bin/gh"))


def test_orders_carry_the_allow_list_and_the_command_rules(world, monkeypatch, spawn_fake):
  # the launch prompt's orders; launch_tools: the launch's --allowedTools entries; gh: the launch's gh shim path; bin_dir: its bin directory
  s, card, hid = launch(world, monkeypatch)
  prompt = s.path("launches", f"{UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  launch_tools = launches_of(s)[-1]["command"].split("--allowedTools '")[1].split("'")[0].split(",")
  gh, bin_dir = "/usr/local/bin/gh", s.path("launches", f"{UNIT}_r1_bin")
  orders = prompt.split("# Builder orders", 1)[1]
  assert "{{allowed}}" not in orders and "{{push}}" not in orders
  assert all(any(line.strip(" -`") == entry for line in orders.splitlines()) for entry in launch_tools)
  assert f"`{bin_dir}/superegm-push`" in orders and "`git push origin <branch>`" not in orders
  assert f"`{gh} pr view <branch>`" in orders
  for phrase in ("one command per Bash call", "heredoc", "--body-file", "one segment per Bash call", "empty `feat`"):
    assert phrase in orders


def posted(s, rnd: int) -> str:
  """The launch's prompt file without its `# Builder orders` part, whose own text quotes the forms (`**Seam:** ok`)."""
  text = s.path("launches", f"{UNIT}_r{rnd}_prompt.md").read_text(encoding="utf-8")
  return "\n\n---\n\n".join(part for part in text.split("\n\n---\n\n") if not part.startswith("# Builder orders"))


LOGINS = {"builder": "builder-bot", "owner": "owner", "stranger": "stranger"}  # seed's builder login and config.owners
stranger_login = LOGINS["stranger"]


def round_2(world, monkeypatch, s, card, hid, comments=(), reviews=()):
  """Round 1 ended (exit 0) with pull request #70 at the base, its reviews `reviews`; then round 2's launch."""
  from conftest import make_pr
  from test_builders import BASE, PR, REPO, state_of
  Path(launches_of(s)[-1]["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  head = git(["rev-parse", "refs/superegm/base"], world.repo).strip()
  git(["update-ref", f"refs/pull/{PR}/head", head], world.repo.parent / "origin.git")
  state = state_of(s); state["units"][UNIT]["pr"] = {"number": PR, "head": head, "base_ref": BASE}
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  make_pr(world.gh, PR, head, branch=f"superegm/{hid}/U07", closes=[(REPO, ISSUE)])
  world.gh.reviews[PR] = [{**r, "commit_id": head} for r in reviews]
  return launch(world, monkeypatch, comments, rnd=2, seeded=(s, card, hid))


@pytest.mark.parametrize("form, author, kept", [
    ("**Deviation (other):** x", "builder", True), ("**Deviation (other):** x", "owner", True),
    ("**Deviation (other):** x", "stranger", False),
    ("**Seam:** ok", "builder", True), ("**Seam:** ok", "stranger", False),
    ("**Decision D1:** x", "owner", True), ("**Decision D1:** x", "stranger", False),
    ("**Ruling:** foreman-1-1 finding upheld", "owner", True), ("**Ruling:** foreman-1-1 finding upheld", "stranger", False),
    ("**Note:** x", "owner", True), ("**Note:** x", "stranger", False),
    ("PR review body", "owner", True), ("PR review body", "stranger", False),
])
def test_prompt_keeps_each_form_from_its_authors(world, monkeypatch, spawn_fake, form, author, kept):
  # `form` on U07's issue (a PR review body: on its PR, author read from user.login) by `author`: builder = the launch's builder login,
  # owner = a config.owners login, stranger = neither (its login `stranger_login`); prompt and journal after launch-builder
  login = LOGINS[author]
  if form == "PR review body":
    s, card, hid = launch(world, monkeypatch)
    s, card, hid = round_2(world, monkeypatch, s, card, hid, reviews=[{"id": 9, "user": {"login": login}, "body": form}])
    rnd = 2
  else:
    s, card, hid = launch(world, monkeypatch, [{"id": 5, "user": {"login": login}, "body": form,
                                                "created_at": "2026-11-25T10:00:00Z", "updated_at": "2026-11-25T10:00:00Z"}])
    rnd = 1
  prompt = posted(s, rnd)
  journal = s.path("journal").read_text(encoding="utf-8")
  assert (form in prompt) is kept
  assert kept or f"ignored: {stranger_login} is not the builder or an owner" in journal


def comment(cid, login, body, at, updated="same"):
  """An issue comment as the REST list gives it; `updated` `same` copies `at`, None leaves `updated_at` out."""
  c = {"id": cid, "user": {"login": login}, "body": body, "created_at": at}
  if updated is not None:
    c["updated_at"] = at if updated == "same" else updated
  return c


def test_owner_notes_reach_every_later_launch(world, monkeypatch, spawn_fake):
  # owners post `**Note:** first note` at 10:00 and `**Note:** second note` at 11:00 on U07's issue, then round 2 launches
  s, card, hid = launch(world, monkeypatch)
  notes_posted = [comment(5, "owner", "**Note:** first note", "2026-11-25T10:00:00Z"),
                  comment(6, "owner", "**Note:** second note", "2026-11-25T11:00:00Z")]
  round_2(world, monkeypatch, s, card, hid, comments=notes_posted)
  prompt_round_2 = s.path("launches", f"{UNIT}_r2_prompt.md").read_text(encoding="utf-8")
  notes = prompt_round_2.split("# Owner notes", 1)[1].split("\n---\n", 1)[0]
  assert notes.index("first note") < notes.index("second note")


AUTHOR = {"**Deviation (other):** x": "builder-bot", "**Seam:** ok": "builder-bot"}  # every other form: an owner's


@pytest.mark.parametrize("form, updated_at, recorded, shown", [
    ("**Deviation (other):** x", "2026-11-25T11:00:00Z", False, False),
    ("**Seam:** ok", "2026-11-25T11:00:00Z", False, False),
    ("**Decision D1:** x", "2026-11-25T11:00:00Z", False, False),
    ("**Note:** x", "2026-11-25T11:00:00Z", False, False),
    ("**Ruling:** foreman-1-1 finding upheld", "2026-11-25T11:00:00Z", True, True),  # edited before or after its record
    ("**Note:** x", None, False, True),  # no updated_at field: unedited
])
def test_edited_comment_is_left_out(world, monkeypatch, spawn_fake, form, updated_at, recorded, shown):
  # `form` by its allowed author, created_at 2026-11-25T10:00:00Z; recorded: the unit's record consumed it (a rulings[] entry posted `comment <id>`)
  record = {"decisions": [{"id": "q1", "point": 1, "source": "review r round 1"}],
            "rulings": [{"decision": "q1", "ruling": "foreman-1-1 finding upheld", "by": "owner", "reason": None,
                         "posted": "comment 5", "posted_at": "2026-11-25T10:30:00Z"}]} if recorded else None
  s, card, hid = launch(world, monkeypatch, [comment(5, AUTHOR.get(form, "owner"), form, "2026-11-25T10:00:00Z", updated_at)], foreman=record)
  prompt, journal = posted(s, 1), s.path("journal").read_text(encoding="utf-8")
  assert (form in prompt) is shown
  assert ("ignored: edited" in journal) is (not shown)


@pytest.mark.parametrize("remote_settings, events", [
    ({"enabledPlugins": {}, "extraKnownMarketplaces": {}, "hooks": {"SessionStart": [], "PreToolUse": []}}, ["PreToolUse", "SessionStart"]),
    ({"enabledPlugins": {}}, []),
    (None, []),  # no remote-settings.json in the builder profile
])
def test_managed_hooks_are_recorded_per_launch(world, monkeypatch, spawn_fake, remote_settings, events):
  # the builder profile's remote-settings.json; plugins_record: the launch's _plugins.json, whose `managed` field is unchanged
  profile_dir = world.repo.parent / "profile"  # seed's builder profile
  if remote_settings is not None:
    profile_dir.mkdir(exist_ok=True)
    (profile_dir / "remote-settings.json").write_text(json.dumps(remote_settings), encoding="utf-8")
  s, card, hid = launch(world, monkeypatch)
  plugins_record = json.loads(s.path("launches", f"{UNIT}_r1_plugins.json").read_text(encoding="utf-8"))
  assert sorted(launch_builder.managed_hooks(profile_dir)) == events
  assert sorted(plugins_record["managed_hooks"]) == events and plugins_record["managed"] == []


def test_doctor_prints_the_managed_line(world, monkeypatch, tmp_path):
  # `superegm doctor` with a builder profile holding managed plugin data@kw and remote-settings.json hooks PreToolUse and SessionStart; every other line ok
  import shutil
  from conftest import REPO
  monkeypatch.setenv("HOME", str(tmp_path)); seed(world)
  monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(tmp_path / "plugins"))
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"gh": "/usr/local/bin/gh"}.get(cmd))
  git(["remote", "set-url", "--push", "origin", f"git@github.com:{REPO}.git"], world.repo)
  profile = Path(json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]["profile_dir"])
  (profile / "plugins").mkdir()
  (profile / "plugins/installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {"data@kw": [
      {"scope": "managed", "installPath": str(profile / "plugins/cache/kw/data/1.0.0"), "version": "1.0.0"}]}}), encoding="utf-8")
  (profile / "remote-settings.json").write_text(json.dumps({"hooks": {"SessionStart": [], "PreToolUse": []}}), encoding="utf-8")
  code, out = world.run("doctor")
  lines = out.splitlines()
  line = next(l for l in lines if l.startswith("managed: "))
  assert lines[lines.index(line) - 1].startswith("plugins: ")
  assert "data@kw" in line and "PreToolUse" in line and "SessionStart" in line
  assert code == 0, out  # informational: it never fails the exit


MOVED = "It derives all from the store, the plan and the spec (refusing as `status` does on a spec changed since its approval); idle units come from this card alone."
PROBE = "Then run `superegm doctor --probe` once (Bash timeout 600,000 ms); stop unless it prints `probe: session ok` and no `probe:` line fails."


def test_wave_skill_probes_before_the_first_launch():
  # wave, notes: skills/wave/SKILL.md and skills/wave/references/resume_notes.md, each with its whitespace runs joined to one space
  import re
  root = Path(__file__).resolve().parents[2]
  wave, notes = (re.sub(r"\s+", " ", (root / rel).read_text(encoding="utf-8"))
                 for rel in ("skills/wave/SKILL.md", "skills/wave/references/resume_notes.md"))
  entry, batch = wave.split("## Entry", 1)[1].split("## A batch", 1)
  assert PROBE in entry and entry.index(PROBE) < entry.index("superegm status --wait 1 ")
  assert "superegm doctor --probe" not in batch
  assert MOVED not in wave and MOVED in notes
