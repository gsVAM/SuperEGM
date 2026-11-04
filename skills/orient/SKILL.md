---
name: orient
license: Apache-2.0
effects: external
effect_kinds: [state-store]
disable-model-invocation: true
description: Copies what the repository's own files say about a unit into the store, an extractor that never summarizes.
---

<!-- Added by SuperEGM (gsVAM), 2026: the orient skill (spec section 9.3). -->

# orient

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    /superegm:orient <spec-path> [--unit U<id>]... [--ref <ref>]
