# Getting started

<!-- Modified by SuperEGM (gsVAM), 2026: EGM's and the Astra fork's workflow guide replaced by SuperEGM's install, by-hand setup and eight phases (design section 5). -->

## Install

Disable the two plugins SuperEGM absorbs, then add the marketplace and install:

```sh
claude plugin disable egm@egm-astra
claude plugin disable superpowers@claude-plugins-official
claude plugin marketplace add gsVAM/superegm
claude plugin install superegm@superegm
```

Every command is `/superegm:<skill>`. The session hook reads `using-superegm` into every session;
a headless session SuperEGM starts itself (a builder, a goldfish) gets nothing from the hook.

## Before the first run

In the target repository, `python3 '<plugin root>/skills/plan/scripts/superegm.py' init` writes
`.superegm/config.json` with every key's default (`repo`, `base`, `artifacts_dir`, `mode`,
`max_in_flight`, `labels`, `reviewers`, `astra`, `judges`, `builder`, `ci_wait_minutes`,
`banned_terms`, `owners`, `owner_team`, `pr_block_file`, …) and prints the owner's by-hand steps;
the first typed skill runs it when the file is missing. The steps:

1. Create the **builder account** and its token as the README's "Before the first run" step 1
   says (the one place the token recipe is written), and put the token in
   `SUPEREGM_BUILDER_TOKEN` (config key `builder.gh_token_env`), never in the repository or the
   config. Builders push and open draft pull requests as that account and can never update
   `<base>`.
2. Create the builder's empty profile at `config.builder.profile_dir`: no hooks, no plugins, no
   `CLAUDE.md`, only the login (`CLAUDE_CONFIG_DIR=<profile_dir> claude`, `/login`, exit) and a
   `settings.json` with `"syncClaudeAiPlugins": false` and `"disableClaudeAiConnectors": true`,
   written before the login so the account's plugins are not synced into the profile and its
   connectors stay out (Claude Code 2.1.273 or later); no `skills/` or `commands/` directory.
   `launch-builder` refuses a profile with anything else in it; the files Claude Code writes on its
   own are not plugins.

   The plugins and MCP servers a builder gets are named in the config, never installed in its
   profile. `builder.plugins` lists `<name>@<marketplace>` ids, each installed once into your own
   session's profile (`user` scope) and disabled there; each launch passes its directory by
   `--plugin-dir <dir>`, and a listed plugin's hooks, skills and bundled servers come with it.
   `builder.mcp` is an object in `mcpServers` form, a secret by `${VAR}` reference, written to
   `launches/<unit>_r<n>_mcp.json` at each launch and passed by
   `--mcp-config <file> --strict-mcp-config`, so no other MCP configuration loads. `builder.mcp` is
   the server map that goes under the file's `mcpServers` key (name to server object), never a whole
   `.mcp.json`. Whether `--strict-mcp-config` keeps a listed plugin's bundled servers is not yet
   probed (decision D1 of U27: the default reads that they come with the plugin, your hand run
   settles it); name in `builder.mcp` a bundled server a builder must reach. Each launch
   records the set in `launches/<unit>_r<n>_plugins.json`: each plugin's id, version, directory
   and hook events, the managed plugins and the MCP file's server names. A plugin's skills are
   invoked only through the allow-list's `Skill(<name>)` rules, its servers' tools through
   `mcp__<server>__*` rules; `superegm doctor` prints both sets on its `plugins:` and `mcp:` lines.
   `Agent` in `builder.allowed_tools` is your opt-in, absent from the default list: a builder may
   then delegate to the platform's default subagents, each confined to its session's allow-list,
   profile and worktree, up to `builder.max_subagent_calls` (12) calls a launch, a budget the
   orders state, not a gate; `record-launch` reads the calls from the session's transcript and
   writes their count on the launch entry as `subagent_calls`.
3. Set the branch protection of design section 11 on `<base>`: updates restricted to the owner
   (the logins in `owners`) with no bypass for the builder account's role and no team but
   `owner_team`; `superegm/**` protected from force-push and deletion by a ruleset whose
   include pattern is exactly `refs/heads/superegm/**/*` (`refs/heads/superegm/**` matches no
   branch on GitHub). `launch` reads the protection and refuses the first wave without it.
4. Add a workflow triggered on `pull_request`, so every builder head gets CI: CI is the
   foreman's evidence.
5. Commit `.superegm/config.json`; `approve-spec` commits it with the spec.
6. Run reviews from a profile without SubagentStart hooks: such hooks in the owner's own profile
   reach adapter subagents, and every dispatch record carries what the goldfish reported seeing.

The store (`artifacts_dir`, outside the working tree) is never committed.

Three keys carry the launch policy. `owners` is the list of GitHub logins that may update
`<base>`; `init` writes the login `gh api user` returns, and `launch` refuses an empty list, a
classic restriction naming a login outside it, and a builder token whose login is in it.
`owner_team` (`<org>/<slug>`, null by default) is the one team a ruleset's bypass may name: it
must exist and the builder account must not be a member. `pr_block_file` (null by default) is a
path relative to the repository root whose text every builder PR body carries, read from the
launch's ref into the prompt under `# PR block`. Then run `superegm doctor`: one line per
prerequisite, `ok` or the refusal `launch` would give.

## The eight phases

One typed skill per phase, nothing chains, and the owner pushes the approval commit to
`origin/<base>` between phases 1 and 5 (`launch` refuses the first wave until the spec there
hashes to the approval).

| # | Phase | Skill | Gate | Record |
| --- | --- | --- | --- | --- |
| 0 | Brainstorm | `/superegm:brainstorming` (auto-invoked; reads and drafts only) | the owner's opt-in | a spec under `docs/specs/` ending in `## Units` |
| 1 | Spec review | `/superegm:review-spec <spec>` | converged or ruled | the review record; the approval freezing the spec at a sha256 |
| 2 | Plan | `/superegm:plan <spec>` | `graph` and `scan` pass | the plan file, one TDD plan per unit; the rendered bodies and their hashes |
| 3 | Plan review | `/superegm:review-plan <spec>` | converged or ruled, per unit | a review record per unit over the exact bytes |
| 4 | File | `/superegm:file <spec>` | a dry run the owner confirms; `verify` reads back | the tracking issue, one issue per unit, blocked-by links, the filing receipt |
| 5 | Wave | `/superegm:wave <spec>` | per unit: a clean head with its contested findings ruled, no regressions | launches, foreman rounds, review comments on the PR, the wave report |
| 6 | Merge | the owner, by hand | the owner | the merged pull request |
| 7 | Integrate | `/superegm:integrate <spec>` (`--close` to give up) | nothing left to escalate | the integrate review record; `closed_at` |

Nothing is merged by a machine: after a wave the owner merges the draft pull requests (or closes
what they give up on) and types the next phase. Around the phases: `/superegm:judges <question>`
convenes the judge panel by hand (advisory), `/superegm:interrupt` pauses a running wave at the
next safe point, `/superegm:clean` removes what a wave left behind locally, and
`/superegm:drift-report` checks the code against the specs after integrate.

## Modes

Every decision point pauses for the owner in normal mode. With `--leavemealone` on the
invocation, or `"mode": "leavemealone"` in `.superegm/config.json`, the four skills that reach a
decision point (`review-spec`, `review-plan`, `plan`, `wave`) ask the judge panel instead: a
contested or declined high or medium finding, a review at its cap, a blocking decision, a blocked
builder. A converged answer is applied and journaled as `Ruling (judges <id>, leavemealone): …`;
an unconverged one waits for the owner with the record. The approval of a converged spec and
"Create" in `file` are mechanical in leavemealone-mode. Merge is excluded from every mode.
