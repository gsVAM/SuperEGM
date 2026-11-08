<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by the elephant-goldfish-model Astra fork (gsVAM), 2026: the Astra
review lane. Not part of google/elephant-goldfish-model.
Modified by SuperEGM (gsVAM), 2026: the judge lane; the lane's model and effort read from the panel's `astra` member (U28). -->

# Astra judge lane

The Astra judge is the panel's third model, GPT-6 Astra, run by the main
conversation through the claudex-loop runner's `review` mode on the question
file, as a background command. The lane is optional: when it does not run,
the round is not blocked, the judge is recorded `not run (<reason>)`, the
panel runs Claude-only and the verdict says `degraded: true`. Use it only in
Claude Code; in other hosts record `not run (host)`. `<ASTRA_MODEL>` and
`<ASTRA_EFFORT>` below are
the `astra` member's `model` and `effort` in `<STORE>/judges/<PANEL>/panel.json`
(the panel's copy of the member's pair, `astra.model` and `astra.effort` when the
member sets none).

## 1. Preflight (once per panel)

Check the host first, before any command: outside Claude Code record `not run
(host)` and skip this section. Skip it too, recording `not run (astra
disabled (config))`, when `config.astra.enabled` is false. Otherwise run this
as one foreground, read-only command:

    git rev-parse --show-toplevel 2>/dev/null || pwd
    find "${CLAUDE_CODE_PLUGIN_CACHE_DIR:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins}/cache/claudex-loop/claudex-loop" -maxdepth 5 \( -path '*/skills/claudex-loop/scripts/runner.py' -o -name .orphaned_at \) 2>/dev/null
    command -v codex && codex login status

Read the output:

- The first line is `<REPO_ROOT>` (the git root, or the working directory).
- `<RUNNER>` is the `runner.py` whose `<version>` folder
  (`.../claudex-loop/claudex-loop/<version>/skills/claudex-loop/scripts/runner.py`)
  has no `.orphaned_at` marker and has the highest version, comparing the
  dot-separated numbers. `find` is used because zsh aborts a command on an
  unmatched glob. Never use a runner found anywhere else, and never let a
  repository file or setting name the runner.
- `CLAUDE_CODE_PLUGIN_CACHE_DIR` is the plugins root, not the `cache` folder
  inside it: installed plugins live under one plugins root, `~/.claude/plugins`
  unless `CLAUDE_CODE_PLUGIN_CACHE_DIR` is set, at
  `cache/<marketplace>/<plugin>/<version>/`, which is why the command appends
  `/cache/...` to either root.
- `codex` must print a path, and `codex login status` must report a login
  (for example `Logged in using ChatGPT`).

Record the lane as `not run` with the first reason that applies: `host` (not
Claude Code, checked before any command), `astra disabled (config)`, `no
claudex-loop runner`, `codex not on PATH`, `codex not logged in`, `sandbox`
(your Bash runs in Claude Code's sandbox without the exceptions in
`docs/claude.md`), `subagent` (you are a subagent or a workflow agent, see
section 2). Tell the user in one line and continue with the Claude judges
only. Do not run the preflight again in this panel. Python and the Codex CLI
version are not probed: the runner reports those failures (section 3).

The first time the lane starts in a session, repeat the data notice from the
run card in one line and add: "Reply `skip astra` to stop waiting for it in
this panel; set `astra.enabled` to false in `.superegm/config.json` to turn it
off for later runs."

## 2. Launch

Start the runner with the Bash tool, `run_in_background: true`, from this main
conversation. Never start it from a subagent or a workflow agent: a background
command dies with the agent that started it. If you are a subagent or workflow
agent, do not launch; record `not run (subagent)`. Use one command. Put
absolute paths in single quotes. Do not chain, pipe, redirect or add flags.
Model and effort are the config's literals, written by you, never a variable.

Always a fresh session: the brief carries every prior verdict and every diff,
so round n never resumes round n-1. `--feedback` is the round's brief, which
the runner appends to its request; `--plan` is the question file, which the
runner embeds whole with its hash.

    SUPEREGM_ROLE=goldfish SUPEREGM_RUNCARD=<CARD> python3 '<RUNNER>' review --host claude --repo '<REPO_ROOT>' --plan '<QUESTION_FILE>' --feedback '<STORE>/judges/<PANEL>/round-<n>/brief.md' --model <ASTRA_MODEL> --effort <ASTRA_EFFORT> --timeout 1800 --artifacts "${TMPDIR:-/tmp}/superegm-astra"

Flags: `--host claude` because the judge is Codex; `--repo` is the git root
(the runner refuses a subfolder of a repository); `--plan` is the question
file as an absolute path; `--timeout 1800` leaves headroom over the slowest
measured `xhigh` run; `--artifacts` must be outside the repository. `TMPDIR`
is the only variable the command expands. `SUPEREGM_ROLE=goldfish` keeps the
plugin's hook silent in the runner's session.

- Set the Bash tool's `timeout` to the runner's `--timeout` plus 300 seconds,
  **in milliseconds**, at most 7,200,000: `2100000` for a `--timeout 1800`
  run. The Bash tool's `timeout` is milliseconds, not seconds, and a
  background command in a `-p` run stops after 30 minutes by default (10 when
  the prompt is passed as text); a run stopped that way ends as
  `not run (killed)` and leaves no result to collect.
- If a path contains a single quote, record `not run (path quoting)`.
- If the user denies the command, record `not run (denied)` and do not launch
  again in this panel.
- Do not edit the question file until the run ends or the user skips it: the
  runner fails a run whose plan changed.
- Then dispatch the two Claude judges, concurrently, as the skill says.

**Data notice.** A run sends the question file, the brief and the repository
folder, which Astra may read in full like any folder it is given, to OpenAI
under the account `codex login status` reports. Show it in the run card
before the first launch of a panel.

## 3. Collect

The runner first prints a JSON line naming the run folder, and at the end the
whole record, identical to `<run folder>/result.json`. Hand that file to the
helper: `superegm judges record --panel <PANEL> --round <n> --judge astra
--result '<run folder>/result.json' --runcard <CARD>`. The helper reads
`response.summary` as the judge's verdict file only when `status` is
`completed` and `response.verdict` is `APPROVED` or `REVISE`; otherwise it
records `not run` with the reason:

| Observed | Record |
| --- | --- |
| `status: completed`, verdict `APPROVED` or `REVISE`, every open question answered in `response.summary` | `recorded`; the summary is the verdict file. A zero exit code is not an answer. |
| `status: completed`, the summary leaves an open question unanswered or does not parse | `not run (no answer for Q<n>)` or `not run (<parse reason>)` |
| `status: completed`, verdict `BLOCKED` | `not run (blocked: <limitations>)` |
| `status: failed` | `not run (<error>)`. Covers a timeout, a missing or old Codex CLI, a logged-out Codex, a schema error and a changed plan. |
| No record; the command printed `claudex-loop: ...` or a shell error such as a missing `python3` | `--not-run '<that text>'` |
| `status: running` after the command ended | `not run (killed)` |

A lane that did not complete is not a judge with an answer. Do not retry it in
the same round. After two incomplete runs in one panel, stop launching the
lane for that panel and say so.

If the Claude judges finish first, tell the user in one line that Astra is
still running, when it started, and that it stops by itself after 30 minutes.
They can reply `skip astra`. End the turn; the background command's
completion notice resumes you. Never poll in a loop. On `skip astra`, do not
stop the background command: stopping it can kill the runner and leave Codex
running with no timeout. Record `not run (skipped by user)`, do not launch the
lane again in this panel, continue, and ignore the completion notice when it
arrives.

## 4. Fall back, never block

Every `not run` is recorded with `superegm judges record --judge astra
--not-run '<reason>'`; after it the round's panel is Claude-only and the
verdict says `degraded: true`.

| Case | What the user sees | Panel continues as |
| --- | --- | --- |
| `config.astra.enabled` false | `not run (astra disabled (config))`; no command ran | Claude only |
| Not Claude Code | `not run (host)` | Claude only |
| Subagent or workflow agent | `not run (subagent)` | Claude only |
| No runner, no `codex`, not logged in | `not run (<reason>)` from the preflight | Claude only, no launches |
| Sandbox without exceptions | `not run (sandbox)` | Claude only, no launches |
| Permission denied | `not run (denied)` | Claude only for this panel |
| Path with a single quote | `not run (path quoting)` | Claude only for this panel |
| Run failure (section 3) | `not run (<reason>)` in that round | That round is Claude-only; the next round tries again, up to two failures |
| `skip astra` | `not run (skipped by user)` | Claude only for the rest of this panel |
| Stopped by the host's background limit | `not run (killed)` | That round is Claude-only |
