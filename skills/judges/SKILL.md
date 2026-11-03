---
name: judges
license: Apache-2.0
effects: external
effect_kinds: [start-session, state-store, github-write]
disable-model-invocation: true
description: Runs one judge panel over a review round and posts the settled findings.
---

# judges

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

U08 writes this skill's body (design section 13).
