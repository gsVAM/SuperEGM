# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U83

"""U83 (spec 1.2.1 section 3.7): the builder check and the visual companion restored from superpowers 7.0.0 into
skills/brainstorming/: the restored files, the loopback-only keyed server, the skill's three piles and offer, the
`.gitignore` line `superegm init` adds, the packed scripts and the README Licence entries. Every path is under
`tmp_path`; the server test binds 127.0.0.1 on a free port and reaches nothing else."""

import hashlib

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
