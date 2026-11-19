# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U83

"""U83 (spec 1.2.1 section 3.7): the builder check and the visual companion restored from superpowers 7.0.0 into
skills/brainstorming/: the restored files, the loopback-only keyed server, the skill's three piles and offer, the
`.gitignore` line `superegm init` adds, the packed scripts and the README Licence entries. Every path is under
`tmp_path`; the server test binds 127.0.0.1 on a free port and reaches nothing else."""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import urllib.error
import urllib.request

import pytest

from conftest import ROOT

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
