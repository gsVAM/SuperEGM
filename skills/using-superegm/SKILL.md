---
name: using-superegm
license: MIT
effects: none
description: Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY response including clarifying questions
---

<!-- From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: renamed to using-superegm; superegm names, the typed and auto-invoked lists, the phase rule; the Claude Code reference only. -->

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill.

IF A SKILL APPLIES TO YOUR TASK, YOU DO NOT HAVE A CHOICE. YOU MUST USE IT.

This is not negotiable. You cannot rationalize your way out of this.
</EXTREMELY-IMPORTANT>

## The Rule

**Invoke relevant or requested skills BEFORE any response or action** — including clarifying questions, exploring the codebase, or checking files. If it turns out wrong for the situation, you don't have to use it.

**Before entering plan mode:** if you haven't already brainstormed, invoke the brainstorming skill first.

Then announce "Using [skill] to [purpose]" and follow the skill exactly. If it has a checklist, create a todo per item.

## Skill Priority

When multiple skills apply, process skills come first — they set the approach, then implementation skills (frontend-design, etc.) carry it out. Brainstorming and systematic-debugging are SuperEGM's most common process skills, but the rule holds for any of them.

- "Let's build X" → superegm:brainstorming first, then implementation skills.
- "Fix this bug" → superegm:systematic-debugging first, then domain skills.

## Typed only

These skills run only when your human partner types the command. Never invoke them yourself:

- `/superegm:review-spec`, `/superegm:plan`, `/superegm:review-plan`, `/superegm:file`, `/superegm:wave`, `/superegm:interrupt`, `/superegm:clean`, `/superegm:finishing-a-development-branch`, `/superegm:integrate`, `/superegm:judges`, `/superegm:orient`: every skill with external effects (the store, a session, GitHub, a remote branch, a local deletion).
- `/superegm:review-spec` and `/superegm:review-plan`: the two review gates.
- `/superegm:draft` and `/superegm:drift-report`: the two EGM entry skills.

## May be auto-invoked

- `superegm:brainstorming`, `superegm:writing-skills`: `brainstorming` and `writing-skills` run on the owner's request outside any unit.
- `superegm:test-driven-development`, `superegm:systematic-debugging`, `superegm:verification-before-completion`: Only for a filed unit on its branch or for an owner-requested fix on a branch; never during brainstorm, spec or plan.
- `superegm:using-superegm`: this skill, injected at session start.

## Red Flags

These thoughts mean STOP—you're rationalizing:

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions are tasks. Check for skills. |
| "I need more context first" | Skill check comes BEFORE clarifying questions. |
| "Let me explore the codebase first" | Skills tell you HOW to explore. Check first. |
| "I can check git/files quickly" | Files lack conversation context. Check for skills. |
| "Let me gather information first" | Skills tell you HOW to gather information. |
| "This doesn't need a formal skill" | If a skill exists, use it. |
| "I remember this skill" | Skills evolve. Read current version. |
| "This doesn't count as a task" | Action = task. Check for skills. |
| "The skill is overkill" | Simple things become complex. Use it. |
| "I'll just do this one thing first" | Check BEFORE doing anything. |
| "This feels productive" | Undisciplined action wastes time. Skills prevent this. |
| "I know what that means" | Knowing the concept ≠ using the skill. Invoke it. |

## Platform Adaptation

Claude Code is the only harness: read `references/claude-code-tools.md`.

## User Instructions

User instructions (CLAUDE.md, AGENTS.md, GEMINI.md, etc, direct requests) take precedence over skills, which in turn override default behavior. Only skip skill workflows or instructions when your human partner has explicitly told you to.
