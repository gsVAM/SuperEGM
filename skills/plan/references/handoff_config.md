<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
Modified by SuperEGM (gsVAM), 2026: EGM's repository-rules reference brought to `.superegm/config.json`'s key set, the launch-policy keys `owners`, `owner_team` and `pr_block_file` included (spec section 11); SuperEGM 1.2's keys added, the example brought to `DEFAULT_CONFIG`: `reviewers.model`, `reviewers.effort`, `brainstorm.team`, `foreman.run_timeout_minutes`, `notify_timeout_seconds`, `builder.effort`, `builder.plugins`, `builder.mcp`, `builder.max_subagent_calls`, `builder.stall_minutes`, `builder.tiers`, `astra.heads_effort` and `ingest` (spec sections 6, 7, 8, 11, 11.1 and 11.2). -->

# Repository configuration: `.superegm/config.json`

Repository rules live in `.superegm/config.json` at the repository root (the git
top level of the design file), not in the plugin: the plugin is generic.
`superegm init` writes the file with every key's default and prints the owner's
by-hand steps; a missing file means the defaults, and the dry run says so.
Unknown keys stop.

```json
{
  "repo": "OWNER/NAME",
  "base": "main",
  "artifacts_dir": "/home/me/.superegm/OWNER/NAME",
  "mode": "normal",
  "max_in_flight": 5,
  "labels": {
    "unit": "superegm:unit",
    "wave_prefix": "superegm:wave-",
    "handoff_prefix": "superegm:handoff-",
    "tracking": "superegm:tracking",
    "stopped": "superegm:stopped",
    "extra": []
  },
  "issue_template": null,
  "tracking_issue_title": "Build: <design title>",
  "banned_terms": [],
  "fix_request_mention": null,
  "allowed_mentions": [],
  "reviewers": {"spec": ["design", "zoom-out"], "integrate": ["design"], "plan": ["readiness", "proportion", "set"], "head": ["change-review", "astra"], "model": "opus", "effort": "xhigh"},
  "commit_trailer": "",
  "owners": ["OWNER"],
  "owner_team": null,
  "pr_block_file": null,
  "brainstorm": {"team": false},
  "foreman": {"run_timeout_minutes": 8},
  "notify_timeout_seconds": 30,
  "judges": {"min_vendors": 1, "members": [{"name": "fable", "via": "adapter", "effort": "xhigh"}, {"name": "opus", "via": "adapter", "effort": "max"}, {"name": "astra", "via": "runner", "effort": "xhigh"}]},
  "builder": {
    "profile_dir": "~/.superegm/builder-profile",
    "model": "claude-opus-5-5",
    "effort": "medium",
    "permission_mode": "acceptEdits",
    "gh_token_env": "SUPEREGM_BUILDER_TOKEN",
    "allowed_tools": ["Read", "Edit", "Write", "Glob", "Grep", "Bash(git add:*)", "Bash(git commit:*)", "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git mv:*)", "Bash(git rm:*)",
                      "Bash(gh pr create:*)", "Bash(gh pr edit:*)", "Bash(gh pr comment:*)", "Bash(gh issue comment:*)", "Bash(gh pr view:*)", "Bash(pytest:*)"],
    "plugins": [],
    "mcp": {},
    "max_subagent_calls": 12,
    "stall_minutes": 30,
    "tiers": {"difficult": {"model": "claude-opus-5-5", "effort": "high"}, "easy": {"model": "claude-sonnet-5-5", "effort": "medium"}},
    "app": null
  },
  "ci_wait_minutes": 30,
  "astra": {"enabled": false, "model": "gpt-6-astra", "effort": "xhigh", "heads": true, "heads_effort": "high"},
  "ingest": {"severity_words": {"bug": "high", "issue": "medium", "nit": "low", "suggestion": "low"}, "human_role": "write"}
}
```

| Key | Default | Rule |
| --- | --- | --- |
| `repo` | parsed from `git remote get-url origin` | `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`. The helper then finds, in `git remote -v`, the remote whose URL names it in any form (`https://github.com/O/N[.git]`, `git@github.com:O/N[.git]`, `ssh://git@github.com/O/N[.git]`), records it as `remote` in the state for `prepare`, and stops with "no remote for OWNER/NAME in <repo root>: add one or fix `repo`" when none matches. In a fork checkout `origin` is the fork and the target is usually `upstream`. |
| `base` | `main` | The default branch; `init` refuses another. The owner pushes the approval commit to `origin/<base>`, `launch` fetches it, and every builder branch starts from it. |
| `artifacts_dir` | `~/.superegm/<owner>/<name>` (`init`) | An absolute path outside the working tree: the store (unit files, issue bodies, reviews, launches, judge panels), never committed. |
| `mode` | `normal` | `normal` or `leavemealone`: in leavemealone-mode the judge panel rules at every decision point; merge stays the owner's in both. |
| `max_in_flight` | `5` | A positive integer: how many units `launch` keeps in flight at once. |
| `labels.unit` | `superegm:unit` | On every unit issue. Each label name must match `^[^,\s]{1,50}$` (GitHub rejects longer names). |
| `labels.wave_prefix` | `superegm:wave-` | `superegm:wave-<n>` on every unit issue. |
| `labels.handoff_prefix` | `superegm:handoff-` | `superegm:handoff-<handoff id>` on every issue of the handoff; the listing `apply` reads for idempotency. |
| `labels.tracking` | `superegm:tracking` | On the tracking issue. |
| `labels.stopped` | `superegm:stopped` | The owner's stop on a unit (`decision rule … stop`); `launch` never marks a unit carrying it. |
| `labels.extra` | `[]` | Labels the repository already has, added to every unit issue. The helper never creates or edits them; a missing one stops the dry run with "create the label `<name>` on OWNER/NAME or remove it from `extra`". |
| `issue_template` | the built-in template | A path relative to the repository root. It must start with the marker line and contain `{{objective}}`, `{{scope}}` and `{{dod}}` (`references/issue_template.md`). |
| `tracking_issue_title` | `Build: <design title>` | `<design title>` is replaced by the design's H1. |
| `banned_terms` | `[]` | Regular expressions matched line by line against the RAW text of every body and comment - code spans and fenced blocks included; the banned-term rule is not code-aware, so a banned term in backticks is still refused and the author rewords. A repository that must not name AI tools in GitHub text lists them here. |
| `fix_request_mention` | none | `^@[A-Za-z0-9-]+(\[bot\])?$`. The one mention the scan allows, on the first line of a round comment, because coding-agent services act on PR feedback only when a comment mentions them. Never allowed in a body. |
| `allowed_mentions` | `[]` | `@name` strings that may appear in any body or comment. A name inside a fenced code block or an inline code span is never a mention (GitHub notifies for neither); any other legitimate mention must be listed here as the EXACT token GitHub would resolve, e.g. `@types/node` - `@types` does not cover `@types/node`, and `@acme` never covers the team `@acme/release`, which would subscribe its members. The allowlist exempts mentions only, never banned terms. Otherwise a refusal names the line and the author rewords. |
| `reviewers` | the spec's panels | One reviewer list per review kind (`spec`, `plan`, `head`, `integrate`); each name is an adapter in `.claude-plugin/agents/`, except `head`'s `astra`, which is informational: `astra.enabled` and `astra.heads` seat the Astra lane. |
| `reviewers.model` | `opus` | The model of every review goldfish dispatch of the four kinds, in the Agent tool's alias form (`sonnet`, `opus`, `haiku`, `fable`), passed as the adapter's per-dispatch override; the judges use their members' values instead. `SUPEREGM_GOLDFISH_MODEL`, when set, overrides it for the session, and `inherit` passes nothing. |
| `reviewers.effort` | `xhigh` | The effort of those dispatches, `low` to `max`. `SUPEREGM_GOLDFISH_EFFORT` overrides it the same way, and an exported `CLAUDE_CODE_EFFORT_LEVEL` becomes every goldfish's effective effort. |
| `astra` | disabled | `enabled`, `model`, `effort`, `heads`: the Astra lane, GPT-model reviewers run headlessly through claudex-loop. Once `enabled` is true, `heads` (true; a config without it reads true) seats the lane on every head review. `effort` is the elephant's lanes'. |
| `astra.heads_effort` | `high` | The effort of the foreman's Astra lane on head reviews. A config without it reads `high`. |
| `judges` | `min_vendors` 1; fable (adapter, xhigh), opus (adapter, max), astra (runner, xhigh) | The judge panel of leavemealone-mode: a converged verdict needs judges spanning `min_vendors` vendors; each member runs `via` an adapter or the runner. |
| `builder` | see the example | `profile_dir` (the empty builder profile), `model`, `permission_mode` (`acceptEdits`), `gh_token_env` (`SUPEREGM_BUILDER_TOKEN`, the variable holding the builder account's token) and `allowed_tools` (tool names and `Bash(<prefix>:*)` patterns; `Skill`, a bare `Bash` and `Bash(*)` are refused; `Agent` is the owner's opt-in, absent from the default; the push prefix for the unit's own branch is added per launch) and `app` (`"app": null`, the machine account; or `{app_id, slug, private_key_env}`, the builder as a GitHub App: `<slug>[bot]` under one-hour tokens minted per call from the key file the variable `private_key_env` names, `SUPEREGM_APP_KEY` by default; with it set, `gh_token_env`'s variable must be unset). |
| `builder.effort` | `medium` | The builder's effort, passed to the launched `claude -p` as `--effort <level>` with `CLAUDE_CODE_EFFORT_LEVEL` unset. With `builder.model` it is the doable tier's pair. |
| `builder.plugins` | `[]` | Plugin ids `<name>@<marketplace>` passed to the builder, one `--plugin-dir` each, resolved to the directory of the id's `user`-scope entry in the elephant profile's `plugins/installed_plugins.json`; the owner keeps the listed plugins installed and disabled there. Another form stops the load. |
| `builder.mcp` | `{}` | The builder's MCP servers in `.mcp.json`'s `mcpServers` form: the server map, name to server object, never a whole `.mcp.json`. It is written to the store per launch and passed with `--strict-mcp-config`, so no other MCP configuration loads. A secret goes in by `${VAR}` reference, never literally: the config is committed. |
| `builder.max_subagent_calls` | `12` | A positive integer: the subagent calls a launch may make when `allowed_tools` carries `Agent`, a budget the builder's orders state, not a gate. `record-launch` writes the calls on the launch entry. |
| `builder.stall_minutes` | `30` | A positive integer: the watchdog's bound. A `running` launch whose branch shows no commit newer than its own newest commit (or than its start) for this long is reported stalled by `status`. |
| `builder.tiers.difficult` | `claude-opus-5-5`, `high` | `{model, effort}`: the builder's pair for a unit whose `Tier:` line says `difficult`. A doable unit, and a unit with no tier, use `builder.model` and `builder.effort`. A key under `tiers` other than `difficult` and `easy`, or a row that is not exactly `model` and `effort` (`low` to `max`), stops the load. |
| `builder.tiers.easy` | `claude-sonnet-5-5`, `medium` | `{model, effort}`: the pair for an `easy` unit. A config without `tiers` reads both default rows; a tier whose row the owner removes uses the doable pair. |
| `ci_wait_minutes` | `30` | A positive integer: how long a head's CI may stay pending or absent before the wave reports it CI-waiting. |
| `commit_trailer` | `""` | A string appended, after a blank line, to every commit the helper makes (`approve-spec`'s approval and `--amend-units` commits), e.g. a `Co-Authored-By:` line; empty appends nothing. |
| `owners` | `[]` (`init` writes the login `gh api user` returns) | A list of GitHub logins: the owner, who alone may update `<base>`. `launch` and `doctor` refuse an empty list naming the key, a classic restriction naming a login outside it, and a builder token whose login is in it. |
| `owner_team` | `null` | `<org>/<slug>` or null: the one team a ruleset's bypass actors may name. The team must exist and the builder account must not be a member; a bypass for any other team is refused. |
| `pr_block_file` | `null` | A path relative to the repository root, or null: the file whose text every builder PR body carries, read verbatim from the launch's ref into the prompt under `# PR block`. A path absent from the ref refuses the launch; the file is not checked when the config loads. |
| `brainstorm.team` | `false` | True or false: `true` runs `/superegm:brainstorming` in its team mode by config, as `--team` does. Another key under `brainstorm` stops the load. |
| `foreman.run_timeout_minutes` | `8` | A number above 0 and at most 9, under the Bash tool's 10-minute cap: the bound on one whole `collect` call, which re-runs every DoD `Run` item the PR body pastes under its `### DoD <n>` fence in the review worktree. Another key under `foreman` stops the load. |
| `notify_timeout_seconds` | `30` | A positive number: how long `notify` waits on the owner's `~/.superegm/notify` hook, which `wave` runs with the inbox lines new since the last notify on its stdin. The hook lives outside every repository; absent means no hook. |
| `ingest.severity_words` | `bug` high, `issue` medium, `nit` low, `suggestion` low (Devin's words) | Words mapped to `high`, `medium` or `low` for `review ingest`, which reads PR review threads into the unit's latest posted round. Words match whole and case-folded, and `high`, `medium` and `low` themselves always count. An inline thread takes the word its first line starts with or carries in a bold or bracketed marker, else `low`; a human's review body is `medium` when its first line carries such a word, else `low`; a bot's review body is always `low`. |
| `ingest.human_role` | `write` | `read`, `triage`, `write`, `maintain` or `admin`: the repository role from which a human's thread counts. A thread from a human below it is `low` whatever its words, recorded and never posted. |

Fixed behaviour, not configuration: a bare `@name` in the text outside code is refused
(it notifies that user); CI is required; a merged PR is required for landed;
both PR-matching rules of the wave skill apply; the label colour is `1b6ef3`;
derived labels are created without `--force` and existing labels are never
edited; nothing is merged by a machine.

The dry run makes three read-only `gh` calls: `gh auth status --hostname
github.com`, `gh api repos/OWNER/NAME -q .permissions` (push access is
required, because labels are silently dropped without it) and `gh api
repos/OWNER/NAME/labels --paginate --slurp`. Repository selection is per
command: `issue`, `pr` and `label` commands take `-R OWNER/NAME`; `api` calls
name the repository in the endpoint, never through the `{owner}`/`{repo}`
placeholders (the helper's `cwd` is the store, not the
repository); the GraphQL read passes `owner` and `name` as variables.

## One command at a time

The helper `superegm.py` is **single-writer**: it has no locking and needs none. Run one
command, let it finish, run the next. `status --wait` is the only long command
and it only reads while waiting, saving once when it returns; it refuses
`--watch` and `--confirm-landed` so a long wait can never record a choice late.
