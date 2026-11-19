# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U83

"""U83 (spec 1.2.1 section 3.7): the builder check and the visual companion restored from superpowers 7.0.0 into
skills/brainstorming/: the restored files, the loopback-only keyed server, the skill's three piles and offer, the
`.gitignore` line `superegm init` adds, the packed scripts and the README Licence entries. Every path is under
`tmp_path`; the server test binds 127.0.0.1 on a free port and reaches nothing else."""

import hashlib
import json
import os
import re
import runpy
import shutil
import socket
import subprocess
import urllib.error
import urllib.request
import zipfile

import pytest

from conftest import ROOT, Harness, make_repo

# source: superpowers 7.0.0 at ~/.claude/plugins/cache/claude-plugins-official/superpowers/7.0.0/skills/brainstorming/, or where that cache is absent https://github.com/obra/superpowers at tag v7.0.0, skills/brainstorming/ (the README's credited source); copied into the test as constants
SHA_7_0_0 = {  # files restored byte for byte
  "references/builder-check-prompt.md": "36d51a4723d6f0a3ce5811a0ea3b3a8424f07533947e1355f5d8cb8cce40c55e",  # 7.0.0 path: builder-check-prompt.md
  "scripts/frame-template.html": "6a8a4e58bd6a44b904e2e3c57de774481d909204597e1498de53f1b2fecc4c4e",
  "scripts/helper.js": "43c6d69954a46ec34a2a262bcc62a9a7e83e839c739f199cb72646d397c686e3"}
EDITED = ["references/visual-companion.md", "scripts/server.cjs", "scripts/start-server.sh", "scripts/stop-server.sh"]


@pytest.mark.parametrize("path", [*SHA_7_0_0, *EDITED])
def test_restored_files_match_7_0_0(path):
  # unchanged files hash to 7.0.0's sha256; edited files carry no .superpowers/ path and no non-loopback host
  data = (ROOT / "skills/brainstorming" / path).read_bytes()
  if path in SHA_7_0_0:
    assert hashlib.sha256(data).hexdigest() == SHA_7_0_0[path]
  else:
    text = data.decode()
    assert ".superpowers/" not in text and "0.0.0.0" not in text and "BRAINSTORM_HOST" not in text
    assert ".superegm/brainstorm/" in text or path == "scripts/server.cjs"


def _free_port():
  with socket.socket() as probe:
    probe.bind(("127.0.0.1", 0))
    return probe.getsockname()[1]


def _status(url):
  try:
    with urllib.request.urlopen(url, timeout=10) as reply:
      return reply.status
  except urllib.error.HTTPError as err:
    return err.code


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_server_is_loopback_and_keyed(tmp_path):
  # the started server listens on 127.0.0.1 only and answers 403 without ?key=
  src = (ROOT / "skills/brainstorming/scripts/server.cjs").read_text()
  assert "'127.0.0.1'" in src and "BRAINSTORM_HOST" not in src and "0.0.0.0" not in src
  port, key = _free_port(), "ab12" * 16
  env = {**os.environ, "BRAINSTORM_DIR": str(tmp_path / "session"), "BRAINSTORM_PORT": str(port),
         "BRAINSTORM_TOKEN": key, "SUPERPOWERS_DISABLE_TELEMETRY": "1"}
  env.pop("BRAINSTORM_OPEN", None)
  proc = subprocess.Popen(["node", str(ROOT / "skills/brainstorming/scripts/server.cjs")], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
  try:
    started = json.loads(proc.stdout.readline())
    assert started["type"] == "server-started" and started["host"] == "127.0.0.1" and started["port"] == port
    assert _status(f"http://127.0.0.1:{port}/") == 403
    assert _status(f"http://127.0.0.1:{port}/?key=wrong") == 403
    assert _status(f"http://127.0.0.1:{port}/?key={key}") == 200
  finally:
    proc.terminate()
    proc.wait(timeout=10)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_started_page_loads_nothing_external(tmp_path):
  # started through start-server.sh with no telemetry variable set, the served page names no external src (nothing leaves the machine)
  scripts = ROOT / "skills/brainstorming/scripts"
  env = {k: v for k, v in os.environ.items()
         if k not in ("SUPERPOWERS_DISABLE_TELEMETRY", "DISABLE_TELEMETRY", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "BRAINSTORM_OPEN")}
  project = tmp_path / "project"
  project.mkdir()
  started = subprocess.run(["bash", str(scripts / "start-server.sh"), "--project-dir", str(project)], env=env,
                           capture_output=True, text=True, timeout=30, cwd=tmp_path)
  info = json.loads(started.stdout.strip().splitlines()[-1])
  try:
    assert info["type"] == "server-started" and info["host"] == "127.0.0.1"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())  # the key URL sets the cookie, then `/` is the page
    opener.open(info["url"], timeout=10).read()
    with opener.open(info["url"].split("?")[0], timeout=10) as reply:
      page = reply.read().decode()
    assert "Brainstorm Companion" in page
    assert not re.search(r"""\bsrc\s*=\s*["']?(https?:)?//""", page)
    assert "primeradiant.com" not in page
  finally:
    subprocess.run(["bash", str(scripts / "stop-server.sh"), info["screen_dir"].rsplit("/", 1)[0]], env=env,
                   capture_output=True, timeout=30)


@pytest.mark.skipif(shutil.which("node") is None or shutil.which("git") is None, reason="node or git is not installed")
def test_started_session_leaves_the_checkout_clean(tmp_path):
  # a repository set up before 1.2.1 has no root ignore line: starting the server there writes
  # .superegm/brainstorm/.gitignore holding `*` before the key, so `git status --porcelain` shows nothing
  scripts = ROOT / "skills/brainstorming/scripts"
  env = {k: v for k, v in os.environ.items() if k != "BRAINSTORM_OPEN"}
  project = tmp_path / "project"
  project.mkdir()
  subprocess.run(["git", "init", "-q"], cwd=project, check=True, capture_output=True)
  started = subprocess.run(["bash", str(scripts / "start-server.sh"), "--project-dir", str(project)], env=env,
                           capture_output=True, text=True, timeout=30, cwd=tmp_path)
  info = json.loads(started.stdout.strip().splitlines()[-1])
  try:
    assert info["type"] == "server-started"
    store = project / ".superegm" / "brainstorm"
    assert (store / ".gitignore").read_text(encoding="utf-8").strip() == "*"
    assert (store / ".last-token").exists()
    status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=project, capture_output=True, text=True)
    assert status.stdout == ""
  finally:
    subprocess.run(["bash", str(scripts / "stop-server.sh"), info["screen_dir"].rsplit("/", 1)[0]], env=env,
                   capture_output=True, timeout=30)


def test_companion_guide_never_edits_the_tracked_gitignore():
  # the guide leaves the ignore rule to start-server.sh and names the session directory stop-server.sh takes
  guide = (ROOT / "skills/brainstorming/references/visual-companion.md").read_text(encoding="utf-8")
  assert "add it if not" not in guide and "check `.gitignore`" not in guide
  assert "$SESSION_DIR" not in guide and "stop-server.sh <session_dir>" in guide
  assert "parent of the `screen_dir` and `state_dir`" in guide


def test_skill_names_piles_offer_and_retro():
  # the skill runs the builder check before hand-over and the SDLC step, sorts three piles, offers the companion
  text = (ROOT / "skills/brainstorming/SKILL.md").read_text()
  for phrase in ("Answered already", "Minor", "Theirs", "list of calls", "references/builder-check-prompt.md",
                 "This might be easier if I show you. Want me to open a browser tab with some mockups?",
                 "## Visual Companion", "## Play It Back", ".superegm/brainstorm.md"):
    assert phrase in text
  assert text.index("builder check") < text.index("SDLC")
  assert text.index("**Builder check:**") < text.index("## Design the SDLC Workflow")


@pytest.mark.parametrize("before, tracked, said", [
  ("node_modules/\n", False, "a file git does not track yet"),
  ("node_modules/\n.superegm/brainstorm/\n", False, "was already in .gitignore"),
  ("node_modules/", False, "a file git does not track yet"),
  (None, False, "a file git does not track yet"),
  ("node_modules/", True, "the checkout stays dirty until you do"),
  ("node_modules/\n.superegm/brainstorm/\n", True, "was already in .gitignore")])
def test_init_ignores_the_session_dir_once(before, tracked, said, tmp_path, capsys, monkeypatch):
  # a fresh init (no .superegm/config.json) in a repo whose .gitignore holds `before` (None: no .gitignore, "node_modules/": no trailing newline; `tracked`: committed first), gh stubbed as in test_init_writes_the_config_with_every_key_and_refuses_another_base; step 5 says what init did about .gitignore
  repo = make_repo(tmp_path / "fresh")
  gitignore = repo / ".gitignore"
  if before is not None:
    gitignore.write_text(before, encoding="utf-8")
  if tracked:
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "ignore"], cwd=repo, check=True)
  monkeypatch.chdir(repo)
  harness = Harness(capsys)
  harness.gh.extend("api", lambda args, cwd, token=None: (0, "octocat\n", "") if args[1:] == ["user", "-q", ".login"] else (1, "", "unexpected"))
  code, out = harness.run("init", "--artifacts-dir", str(tmp_path / "store"))
  assert code == 0
  assert gitignore.read_text().splitlines().count(".superegm/brainstorm/") == 1
  assert gitignore.read_text().startswith("node_modules/\n" if before is not None else ".superegm/brainstorm/\n")
  assert said in out
  assert [phrase for phrase in ("a file git does not track yet", "was already in .gitignore", "the checkout stays dirty until you do")
          if phrase in out] == [said]


def test_pack_holds_the_scripts(tmp_path):
  # the built plugin carries the five companion scripts
  source = tmp_path / "source"
  source.mkdir()
  for name in ("plugin.json", "LICENSE", "LICENSE-MIT", "README.md", "pyproject.toml"):
    shutil.copyfile(ROOT / name, source / name)
  for name in ("skills", "agents", "resources", "docs", ".claude-plugin", "hooks"):
    shutil.copytree(ROOT / name, source / name)
  build = runpy.run_path(str(ROOT / "scripts/pack_plugin.py"))["build"]
  _, archive = build(source, tmp_path / "out")
  with zipfile.ZipFile(archive) as bundle:
    packed_paths = bundle.namelist()
  names = set(packed_paths)
  assert {f"skills/brainstorming/scripts/{n}" for n in ("frame-template.html", "helper.js", "server.cjs", "start-server.sh", "stop-server.sh")} <= names


def test_licence_lists_the_restored_notices():
  # every restored file carrying the provenance notice is named in the README Licence paragraph
  readme = (ROOT / "README.md").read_text(encoding="utf-8")
  paragraph = next(p for p in readme.split("\n\n") if p.startswith("**Licence.**"))
  restored_with_notice = {f"skills/brainstorming/{path}" for path in (*SHA_7_0_0, *EDITED)
                          if "modified by SuperEGM (gsVAM), 2026: " in (ROOT / "skills/brainstorming" / path).read_text(encoding="utf-8")}
  assert len(restored_with_notice) == len(EDITED)
  assert restored_with_notice <= set(re.findall(r"`([^`]+)`", paragraph))
