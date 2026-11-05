<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
Modified by SuperEGM (gsVAM), 2026: EGM's repository-rules reference brought to `.superegm/config.json`'s key set, the launch-policy keys `owners`, `owner_team` and `pr_block_file` included (spec section 11). -->

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
  "reviewers": {"spec": ["design", "zoom-out"], "plan": ["readiness", "proportion", "set"], "head": ["change-review"], "integrate": ["design"]},
  "astra": {"enabled": false, "model": "gpt-6-astra", "effort": "xhigh"},
  "judges": {"min_vendors": 1, "members": [{"name": "fable", "via": "adapter", "effort": "max"}, {"name": "opus", "via": "adapter", "effort": "max"}, {"name": "astra", "via": "runner"}]},
  "builder": {"profile_dir": "~/.superegm/builder-profile", "model": "claude-fable-5-1", "permission_mode": "acceptEdits", "gh_token_env": "SUPEREGM_BUILDER_TOKEN", "allowed_tools": ["Read", "Edit", "Write", "Glob", "Grep", "Bash(git add:*)", "Bash(git commit:*)", "Bash(gh pr create:*)"]},
  "ci_wait_minutes": 30,
  "commit_trailer": "",
  "owners": ["OWNER"],
  "owner_team": null,
  "pr_block_file": null
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
| `reviewers` | the spec's panels | One reviewer list per review kind (`spec`, `plan`, `head`, `integrate`); each name is an adapter in `.claude-plugin/agents/`. |
| `astra` | disabled | `enabled`, `model`, `effort`: the Astra lane, GPT-model reviewers run headlessly through claudex-loop. |
| `judges` | `min_vendors` 1; fable, opus (adapter, max), astra (runner) | The judge panel of leavemealone-mode: a converged verdict needs judges spanning `min_vendors` vendors; each member runs `via` an adapter or the runner. |
| `builder` | see the example | `profile_dir` (the empty builder profile), `model`, `permission_mode` (`acceptEdits`), `gh_token_env` (`SUPEREGM_BUILDER_TOKEN`, the variable holding the builder account's token) and `allowed_tools` (tool names and `Bash(<prefix>:*)` patterns; `Agent`, `Skill` and a bare `Bash` are refused; the push prefix for the unit's own branch is added per launch). |
| `ci_wait_minutes` | `30` | A positive integer: how long a head's CI may stay pending or absent before the wave reports it CI-waiting. |
| `commit_trailer` | `""` | A string appended, after a blank line, to every commit the helper makes (`approve-spec`'s approval and `--amend-units` commits), e.g. a `Co-Authored-By:` line; empty appends nothing. |
| `owners` | `[]` (`init` writes the login `gh api user` returns) | A list of GitHub logins: the owner, who alone may update `<base>`. `launch` and `doctor` refuse an empty list naming the key, a classic restriction naming a login outside it, and a builder token whose login is in it. |
| `owner_team` | `null` | `<org>/<slug>` or null: the one team a ruleset's bypass actors may name. The team must exist and the builder account must not be a member; a bypass for any other team is refused. |
| `pr_block_file` | `null` | A path relative to the repository root, or null: the file whose text every builder PR body carries, read verbatim from the launch's ref into the prompt under `# PR block`. A path absent from the ref refuses the launch; the file is not checked when the config loads. |

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
