<!--
Copyright 2026 Google LLC.
SPDX-License-Identifier: Apache-2.0
-->
<!-- Modified by the elephant-goldfish-model Astra fork (gsVAM), 2026: fork install commands, Astra lane section, panel stage order. -->
<!-- Modified by SuperEGM (gsVAM), 2026: the platform facts of design section 4 in SuperEGM's names; EGM's install, stage, review-orchestrator and environment-variable text removed. -->

# Claude Code: the platform facts

Everything below was established by live probes of Claude Code (2.1.271 or later) and is what
the skills and the helper rely on; do not re-derive it in a session.

## Adapters and isolation

- Every goldfish and every judge is dispatched with the Agent tool through its own adapter in
  `.claude-plugin/agents/` (`superegm:design`, `superegm:zoom-out`, `superegm:readiness`,
  `superegm:change-review`, …, `superegm:judge`). The adapter sets `omitClaudeMd: true`,
  `model: inherit` and the read-only tools `[Read, Grep, Glob]`, and reads its persona from
  `${CLAUDE_PLUGIN_ROOT}/agents/<id>.md`. `omitClaudeMd` tracks the agent definition, never the
  name: an adapter subagent does not load `CLAUDE.md` or the memory index, whether or not the
  dispatch passed `name`. A reviewer spawned any other way loads `CLAUDE.md` and is not a goldfish.
- `name` on the Agent tool makes an agent addressable and resumable; it is not a distinct kind of
  agent. Several agents may be dispatched in one message and run concurrently in the foreground;
  their returns arrive together.
- SessionStart hooks run for sessions, not for Agent-tool subagents, so this plugin's hook never
  reaches a goldfish. **SubagentStart hooks in the owner's own profile do reach adapter
  subagents**; the plugin cannot suppress them. Every dispatch is therefore recorded as `clean`
  or `exposed:<what>` from the goldfish's own `saw:` line, and the owner runs reviews from a
  profile without SubagentStart hooks.
- The foreman (`superegm:foreman`, tools `[Agent, Bash, Read, Grep, Glob]`, `omitClaudeMd: true`)
  is a **per-unit elephant**: it carries one unit's context across rounds and dispatches that
  head's goldfish, which stay zero-context and read-only. Goldfish never spawn; builders never
  spawn; a foreman dispatches goldfish and nothing else.
- A per-dispatch `model` override on a `model: inherit` adapter is honoured; `effort` is passed
  only where the Agent tool offers it. The panel goldfish run on `SUPEREGM_GOLDFISH_MODEL` at
  `SUPEREGM_GOLDFISH_EFFORT` (`skills/review-spec/references/review_loop.md`); each record keeps
  the requested and the effective pair.

## Background commands

A Bash background command dies with the agent that started it: a subagent's background command
is killed when that subagent gives its final response, while one started from the main
conversation keeps running across turns. So builders, `status --wait` and the Astra runner are
launched by the elephant from the main conversation, never by a subagent that then returns; the
foreman prepares, this session runs.

## Headless sessions: builders and goldfish

- `claude -p` takes the prompt as text (`claude -p "$(cat <file>)"`); `--output-format json`
  writes one result object; `--permission-mode` takes `acceptEdits` or `bypassPermissions`;
  `--allowedTools` entries are tool names or the one prefix form `Bash(<prefix>:*)`, which
  matches on the command's text and cannot exclude a refspec; a headless session with no `Skill`
  entry invokes no skill. `launch-builder` writes the whole command line; `record-launch` records
  it and, later, its exit.
- Headless sessions SuperEGM starts set `SUPEREGM_ROLE` to `builder` or `goldfish` and
  `SUPEREGM_RUNCARD` to the run card they run under; the session hook prints nothing for those
  roles.
- The builder profile (`config.builder.profile_dir`) is created empty by the owner, with no
  plugins, no `CLAUDE.md` and no hooks (a `settings.json` with a `hooks` key); `launch-builder`
  and `superegm doctor` refuse otherwise. The builder's allow-list is
  `config.builder.allowed_tools`; `Agent`, `Skill` and a bare `Bash` are refused.
- `gh` acts as the account whose token `GH_TOKEN` holds; `git push` does so only over an HTTPS
  remote with `gh` as the credential helper, which `launch-builder` passes in the launched
  command's environment (`SUPEREGM_BUILDER_TOKEN`, the builder account's token made as the
  README's "Before the first run" step 1 says), never written to the shared git config. Every
  `gh` command a skill runs is prefixed `GH_HOST=github.com`, and the helper pins the same host on
  its own calls: an inherited `GH_HOST` would otherwise send a comment or a review to an
  enterprise server nothing approved.
- On the App path (`builder.app` set) the builder holds no token: `launch-builder` writes `launches/<unit>_r<n>_bin/` outside the repository, holding `superegm-token` (a fresh one-hour token on stdout, `superegm builder-token` with the repo, app id and key variable baked in) and a `gh` shim that mints per call and execs the real `gh` by the absolute path resolved at launch, failing closed when the mint fails.
  The launched `GH_TOKEN` is the sentinel `superegm-no-token` (no token: the shim overrides it, and a real `gh` reached any other way fails with 401); the orders carry `{{gh}}` in every `gh` call, filled with the shim's path on the App path and the real `gh`'s on the machine-account path, and the allow-list's `gh` prefixes are rewritten to the same path, so a bare `gh` is refused on both.
  On both paths the builder's git reads none of the owner's configuration: `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` at `/dev/null`, `GIT_SSH_COMMAND=false`, `GIT_ASKPASS` and `SSH_ASKPASS` unset, `GIT_TERMINAL_PROMPT=0`, and the `GIT_CONFIG_KEY_n` pairs carrying the helper reset, `gh auth git-credential` by absolute path, the HTTPS `insteadOf` rewrites and the commit identity; `superegm doctor`'s `environment` line checks exactly that.
- `config.owners` lists the logins that may update the base branch (`launch` refuses an empty
  list, a classic restriction naming a login outside it, and a builder token whose login is in
  it); `config.owner_team` (`<org>/<slug>`) is the one team a ruleset's bypass may name, the
  builder account outside it; `config.pr_block_file` names the file whose text every builder PR
  body carries, read from the launch's ref into the prompt under `# PR block`.
- `git worktree add` refuses a branch another worktree has checked out: `launch-builder` detaches
  the earlier launch's worktree before adding a fresh one, and `clean` removes a unit's worktrees
  only once every launch and round of it is terminal.

## Paths and permissions

- `${CLAUDE_PLUGIN_ROOT}` is substituted in plugin skill and agent bodies; use that resolved root
  for `agents/`, `resources/` and `docs/`, and the invoked skill's directory for its
  `references/`. Never guess a cache version or search another installed copy.
- The store is `artifacts_dir` in `.superegm/config.json`, outside the working tree: unit files,
  issue bodies, reviews, launches and judge panels live there and are never committed. Briefs and
  drafts go to the working directory; EGM's `EGM artifact directory: <path>` line is not read by
  SuperEGM.
- Review worktrees and builder worktrees live under `${TMPDIR:-/tmp}`, and the refs the foreman
  fetches live under `refs/superegm/`, never on a branch you work on.
- Personas and standards live in the plugin cache. SuperEGM installs no permission-approval
  hook: approve resource reads through Claude Code's normal prompts, or for headless runs grant
  read access to the resolved plugin's `agents/`, `docs/`, `resources/` and `skills/` folders in
  `/permissions` (`Read(//absolute/plugin/path/agents/**)` and the three siblings; replace the
  version segment with `*` to survive an update). Keep write access to the project and the store.
  A reviewer that cannot read its persona or standard must report the limitation and stop.

## Claude Cowork

Cowork uses the same package. Install it from the Cowork plugin panel via the marketplace
`gsVAM/superegm`; `plan`, `wave` and the other Claude Code-only skills say so and stop there.
Local testing with `claude --plugin-dir <copy>` is Claude Code only; validate a copy with
`claude plugin validate <copy>/.claude-plugin/plugin.json`.

References: [plugin paths](https://code.claude.com/docs/en/plugins/loading#find-plugins-on-disk),
[skill invocation](https://code.claude.com/docs/en/skills) and
[subagent context and tools](https://code.claude.com/docs/en/sub-agents).
