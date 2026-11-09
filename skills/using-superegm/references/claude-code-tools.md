---
name: claude-code-tools
description: The Claude Code platform facts SuperEGM relies on (design section 4), read from using-superegm.
---

<!-- From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: the section 4 platform facts replace the orchestration notes. -->

# Claude Code Platform Notes

Claude Code is the only harness: skills speak its vocabulary (`Agent` for a
subagent dispatch, todos, `Skill`). These are the platform facts SuperEGM
relies on, from the live probes; do not re-derive them.

- `name` on the Agent tool makes an agent addressable and resumable; it is not
  a distinct teammate. Several agents may be dispatched in one message and run
  concurrently in the foreground; their returns arrive together.
- `omitClaudeMd` tracks the agent definition, never the name: an adapter
  subagent does not load CLAUDE.md or the memory index.
  SessionStart hooks run for sessions, not for Agent-tool subagents, so this
  plugin's hook never reaches a goldfish. SubagentStart hooks in the owner's own profile do reach
  adapter subagents; the plugin cannot suppress them, so every dispatch record
  carries what the goldfish reported seeing, and reviews run from a profile
  without SubagentStart hooks.
- A Bash background command dies when its own agent returns; one started from
  the main conversation survives across turns. So builders and the Astra runner
  are launched by the elephant, never by a subagent that then returns (the head's Astra lane excepted:
  the foreman runs it as one bounded foreground call and waits for it).
- Claude Code has no plugin-on-plugin dependency and cannot disable another
  plugin's hook or skills. Hence absorb, not depend.
- A per-dispatch `model` override on a `model: inherit` adapter is honoured; a
  per-dispatch `effort` is passed only when the Agent tool offers that
  parameter. `claude -p` takes the prompt as text (`claude -p "$(cat <file>)"`);
  `--output-format json` writes one result object; `--permission-mode` takes
  `acceptEdits` or `bypassPermissions`; `--allowedTools` entries are tool names,
  the prefix form `Bash(<prefix>:*)`, which matches on the command's
  text and cannot exclude a refspec, the skill rules `Skill(<name>)` and `Skill(<name> *)`
  (amendment 7: a headless session invokes only the skills its `Skill` rules name, none
  without one) and the MCP rules `mcp__<server>__<tool>` or `mcp__<server>__*`.
  `Agent` in a builder's allow-list admits the platform's default subagents, each inheriting the session's allow-list, profile and worktree
  (amendment 15: the owner's opt-in, absent from the default list; a plugin-shipped or worktree
  `.claude/agents/` definition is the owner's own, its `permissionMode` and `model` theirs);
  unprobed: whether a subagent's allow-list equals the builder's (U27's D2, the owner's hand run
  after the merge to settle; until then the inheritance is the default this sentence states).
  `--session-id <uuid>` names the session, its transcript `projects/<slug>/<uuid>.jsonl` under the profile,
  the subagents' beside it in `<uuid>/subagents/agent-*.jsonl`.
  `--plugin-dir <dir>` loads a plugin for the session (its hooks, skills and bundled servers),
  enabled in the profile or not, one flag per directory.
  `--mcp-config <file> --strict-mcp-config` loads that file's servers and no other MCP configuration;
  unprobed: whether the flag keeps a `--plugin-dir` plugin's bundled servers (U27's D1, its default
  that they come with the plugin, the owner's hand run to settle; until then name in the MCP file a
  bundled server a builder must reach);
  `ENABLE_CLAUDEAI_MCP_SERVERS=false` keeps the account's connectors out beside the profile's
  `disableClaudeAiConnectors`.
