<!-- Copyright 2026 Google LLC. SPDX-License-Identifier: Apache-2.0 -->
<!-- Modified by the elephant-goldfish-model Astra fork (gsVAM), 2026: Astra lane section, fork issue tracker. -->
<!-- Modified by SuperEGM (gsVAM), 2026: what SuperEGM sends to GitHub and to OpenAI, the builder account's token, the store and the config keys that bound it. -->

# SuperEGM data handling

SuperEGM is a set of skills, reviewer instructions and a local helper. It operates no hosted
service, database, analytics client or telemetry endpoint and needs no account of its own. Three
things leave the machine: what the skills write to GitHub, what the Astra lane and the Astra judge
send to OpenAI, and what the host (Claude Code) itself processes under its own terms.

## Inputs and outputs

The host reads the project files, the spec, the plan file and the review context for the task at
hand; those can contain personal or confidential information. The helper writes the store under
`artifacts_dir` (`.superegm/config.json`), outside the working tree and never committed: unit
files, rendered issue bodies, review rounds and their findings, dispositions and rulings, launch
records, judge panels and verdicts, the journal. Local files persist until the owner deletes
them.

## GitHub

Issue bodies, comments, pull request reviews and labels go to the repository `repo` names, with
its visibility, under the owner's `gh` login; builders push and open draft pull requests under the
builder account, whose token is `SUPEREGM_BUILDER_TOKEN` (config key `builder.gh_token_env`) and
is passed to a launched builder's environment only.
On the App path (`builder.app`) no token is stored anywhere: `superegm builder-token` mints a one-hour installation token per call from the private key at the path `SUPEREGM_APP_KEY` names (config key `builder.app.private_key_env`), and the builder session can read the key file by that path, so the App must reach this repository alone; the plugin scans no content itself, and GitHub's push protection, where the repository has it, stops a committed token or key.
`banned_terms` in `.superegm/config.json` is
checked against every body and comment before it is written, and a dry run the owner confirms
precedes the filing.

## OpenAI: the Astra lane and the Astra judge

When `config.astra.enabled` is true, one reviewer of a spec, plan or integrate review and one
judge of every panel run through the claudex-loop runner and the Codex CLI, and these leave the
machine to OpenAI under the account `codex login status` reports, on that account's terms: the
whole target (the spec; a unit's body; a question file with its evidence), the review brief the
skill writes (including the standard text and, on a resumed round, the rows of the dispositions
file for Astra's own earlier findings: finding id, final disposition and who ruled, rendered from
`round-<n-1>.json` without quoting any other reviewer), the runner's fixed instructions, any file
the user's OS account can read that Astra opens inside or outside the repository (the read-only
sandbox blocks writes, not reads), and the user's Codex `AGENTS.md` and memories. SuperEGM does
not put the Claude conversation, the Claude reviewers' reports or their dispositions rows in the
brief; Astra is told not to open them, but it can read them like any other file in the folder.
Write artifacts outside the repository (the store is `artifacts_dir`) to keep them out of the folder Astra reviews. The Astra lane
never runs on a pull request head.

Opt out with `"astra": {"enabled": false}` in `.superegm/config.json`, `codex logout`, or by not
installing claudex-loop; the lane then records `not run` and the review runs Claude-only. Local
copies of each prompt and reply stay under `${TMPDIR:-/tmp}`; delete them when done.

## Builders and goldfish

A builder session runs headless under the empty builder profile with the issue body, the orders
and the rulings as its prompt; its exit and its pull request are the record. A goldfish or judge
is dispatched through an adapter with `omitClaudeMd: true`, and each dispatch records whether it
saw anything besides its brief (`clean` or `exposed:<what>`).

## Questions

Use the [issue tracker](https://github.com/gsVAM/superegm/issues). Do not include credentials,
private documents or personal data in public reports. This notice describes the plugin's data
flow; it does not replace the privacy policies of the host or the services the owner invokes.
