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
  are launched by the elephant, never by a subagent that then returns.
- Claude Code has no plugin-on-plugin dependency and cannot disable another
  plugin's hook or skills. Hence absorb, not depend.
- A per-dispatch `model` override on a `model: inherit` adapter is honoured; a
  per-dispatch `effort` is passed only when the Agent tool offers that
  parameter. `claude -p` takes the prompt as text (`claude -p "$(cat <file>)"`);
  `--output-format json` writes one result object; `--permission-mode` takes
  `acceptEdits` or `bypassPermissions`; `--allowedTools` entries are tool names
  or the one prefix form `Bash(<prefix>:*)`, which matches on the command's
  text and cannot exclude a refspec; a headless session with no `Skill` entry
  invokes no skill.
