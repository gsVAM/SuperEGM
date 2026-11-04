---
name: file
license: Apache-2.0
effects: external
effect_kinds: [github-write, state-store]
disable-model-invocation: true
description: Files a confirmed handoff plan as GitHub issues, with the tracking issue, one sub-issue per unit and the blocked-by links.
---

<!-- Modified by SuperEGM (gsVAM), 2026: the file skill body, phase 4 of the SuperEGM loop (design section 10). -->

# file

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

This skill runs in Claude Code only. In any other host reply with one line,
`file runs in Claude Code only`, and stop.

## What it does

The converged, unfiled unit bodies of an approved spec become labelled GitHub
issues: one tracking issue, one issue per unit as a sub-issue of it, and a
blocked-by link per `Blocked by` entry. Six helper commands do it in order,
each under one run card: the gate, the dry run, the owner's one answer, the
writes, the read-back, the close. Every write is on one confirmed write list
that the helper hashes, shows, and re-checks before it writes. Units already
filed are frozen: a later filing (after `/superegm:plan` appended units)
creates only the new issues and rewrites the tracking issue.

## Inputs

*   **`SpecPath`**: the approved spec, absolute or relative to the
    repository root.
*   **`--leavemealone`** (optional): the automatic Create of leavemealone-mode
    for this run; without it the mode is the config's `mode`.

Ask for a missing `SpecPath` in plain chat.

## The helper

`<HELPER>` = `${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`
(Python 3.11 or later, standard library only). Run every command as one Bash
call, `python3 '<HELPER>' <subcommand> ...`, absolute paths in single quotes,
no chaining, pipes, redirects or environment variables; the Bash `timeout`
is the default. **One command at a time**: the helper is single-writer, so
let each command finish before starting the next. Every command below takes
`--spec '<SpecPath>'` and `--runcard '<CARD>'` and exits 1 with one
`superegm: <reason>` line when it refuses; show that line to the owner.

## Step 1: Run card

Run `python3 '<HELPER>' runcard open --skill file --artifact '<SpecPath>'`,
adding `--mode leavemealone` when the invocation said `--leavemealone` or
the config's `mode` is `leavemealone`. The printed id is `<CARD>`. A card
still open on this spec is marked interrupted by the new one.

## Step 2: The gate

Run `python3 '<HELPER>' gate --pass --spec '<SpecPath>' --runcard '<CARD>'`.
It passes when every unfiled unit's plan review converged on the body the
store holds now (`handoff_units.json`'s `body_sha256`), records the pair of
hashes the rest of the filing is checked against, and prints
`gate passed: <k> unfiled units converged`. Its refusals:

*   `gate: <unit> plan review not converged`: the unit has no converged plan
    review. The owner returns to `/superegm:review-plan`; this skill ends.
*   `gate: <unit> body differs from its converged round`: the plan changed
    after the review (an edit, a `decide`, a re-run `graph`). The unit needs
    one more `/superegm:review-plan` round on the current body; this skill
    ends.
*   `gate: nothing to file (every unit is filed)`: there is nothing to do;
    report that and close the card (Step 6).

## Step 3: The dry run

Run `python3 '<HELPER>' dry-run --spec '<SpecPath>' --runcard '<CARD>'`. It
scans the bodies with the current rules, reads GitHub three times (login,
push access, the labels) and, per adopted issue, four more (the issue, its parent, its dependencies, its comments),
and writes nothing there. It writes
`handoff_dryrun.md` in the store: the labels it will create, every issue
with its title, labels and body, every link, the `Writes:` line with the
counts, and the `Confirmed write list sha256`. On a later filing it names
the tracking issue it will rewrite. The refusals (`changed after the gate`,
`split the handoff`, `scan failed`, a missing `extra` label, no push access)
end the skill with the line shown.

A unit whose section carries `Issue: #<n>` is adopted, not created: the dry
run reads that issue and refuses one it cannot adopt (`adopt: #<n> is
closed`, `not in <repo>`, `is a pull request`, `has a parent`, `has
dependencies`, `carries superegm labels`, `carries a ruling comment`), each
ending the skill with the line shown. `handoff_dryrun.md` heads such a unit
`### edit #<n> <unit> (old body sha256 <hex>)` where a created unit reads
`### issue <unit>`: Step 4 adds the unit labels to that issue and replaces
its body with the rendered one, keeping its title, other labels and
comments.

Then the one question, as the sole tool call of its turn, with the numbers
from the `Writes:` line and the repository from the config, and no
`(Recommended)` on any option:

> Create these <n> issues and <m> links on OWNER/NAME as handoff_dryrun.md shows?

Options, in this order: Create, Change the plan, Stop.

*   **Create**: go to Step 4.
*   **Change the plan**: this skill ends; the owner re-types `/superegm:plan`
    (and `/superegm:review-plan`) and comes back.
*   **Stop**: this skill ends and leaves every store file as it is; nothing
    was written to GitHub.

In leavemealone-mode there is no question: go to Step 4, where the helper
journals `Create: automatic (leavemealone)` once per filing.

## Step 4: The writes

Run `python3 '<HELPER>' apply --yes --spec '<SpecPath>' --runcard '<CARD>'`.
Before its first write it re-checks the gate pair and the write list against
the dry run's hash, every unit's converged review, and the scan; then it
appends the confirmed write list to `filings[]` in `state.json` (once per
write-list hash) and, on the first filing of the handoff, records
`base_at_start` (the local tip of the config's `base`). Then it creates the
labels (`superegm:unit`, `superegm:tracking`, `superegm:handoff-<6 hex>`,
`superegm:stopped`, one `superegm:wave-<n>` per wave), the tracking issue
(or rewrites it on a later filing), the unit issues in graph order with
their blocker numbers filled in, the sub-issue links, the blocked-by links,
and reads everything back (Step 5's check, run once by `apply` itself).

*   It is idempotent: a crash, a rate limit (`rate limited: resume with
    ...`) or a stop at `--max-writes` leaves a state the same command resumes
    from; issues already created are found again by their label and marker
    line, never created twice. Resume with the same command.
*   For a large filing (the dry run warned above 450 writes) run it as
    `python3 '<HELPER>' apply --yes --spec '<SpecPath>' --runcard '<CARD>' --max-writes <N>`
    in several calls, until it no longer prints `stopped after`.
*   `adopt: #<n> body changed since the dry run` (or `adopt: #<n> not in
    <repo>`): the adopted issue changed, or went, between the dry run and
    the writes; nothing was written. The owner re-runs the dry run (Step 3)
    and answers the question again.
*   A filed issue body is never edited; a deviation during the build is a comment on the issue (§10).

## Step 5: The read-back

Run `python3 '<HELPER>' verify --spec '<SpecPath>' --runcard '<CARD>'`. It
reads every label, issue body and link of every filing back and compares
each with the stored write list (the union of `filings[]`; the tracking
issue against the latest), then records the receipt in `state.json`
(`verify.complete`, `verify.sha256`, `verify.problems`). Exit 0 with
`verify: complete, <k> of <k> checked, 0 problem(s)` is the receipt
`/superegm:wave` needs. Each `MISMATCH ...` line names one thing on GitHub
that differs from the list (a body edited by hand, a label removed, a link
missing or obsolete): report every line to the owner, who fixes it on
GitHub by hand (the helper never edits a filed body), then run this step
again until it is clean.

## Step 6: Report and close

Report in chat, in this order: the tracking issue's URL; one line per unit,
`U07 #412 <title>` (the numbers are in `state.json` under `units`); the
`verify:` line. Then say that `/superegm:wave` starts the first wave.
Finally run `python3 '<HELPER>' runcard close '<CARD>'`.

## Resuming

Every step is re-entrant from `state.json`: a new invocation opens a new
card (Step 1) and runs the steps again; the gate and the dry run recompute
the same hashes on an unchanged store, `apply` finds what was created, and
the read-back reports only what differs. If the owner answered the question
already in this filing (`filings[]` holds the dry run's hash), do not ask it
again: go to Step 4.
