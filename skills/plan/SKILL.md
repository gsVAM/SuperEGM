---
name: plan
license: Apache-2.0
effects: external
effect_kinds: [state-store, start-session, github-write]
disable-model-invocation: true
description: >-
  Turns an approved spec into build units: one issue body per unit in the
  plan file, graphed into waves, scanned against the body rules and hashed
  in the store, blocking decisions answered in place. Use after
  /superegm:review-spec approved the spec and before /superegm:review-plan.
  Claude Code only.
---

<!-- Modified by SuperEGM (gsVAM), 2026: phase 2 of the SuperEGM loop (the plan file, graph, scan, decide); EGM's approval, review gate, dry run and filing steps live in review-spec, review-plan and file; `[--handoff <id>]`, `filed_elsewhere` and the handoff's directory (U20); the `Tier:` field (U33). -->

<!-- Added by the elephant-goldfish-model Astra fork (gsVAM), 2026: the handoff skill. Not part of google/elephant-goldfish-model. -->

# Plan: approved spec to unit issue bodies

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

This skill runs in Claude Code only. In any other host reply with one line,
`plan runs in Claude Code only`, and stop.

## What it does

An approved spec (`/superegm:review-spec` wrote `approvals/<spec-slug>.json`
in the store) becomes a plan file: one `### U<nn>` section per row of the
spec's `## Units` table, each section the whole brief a builder gets (spec
section 9.1: objective, interfaces, definition of done, review focus, Steps,
decisions). The helper's `graph` parses the file under the approval, derives
the waves, renders one issue body per unit in the layout of
`references/issue_template.md` and hashes the unfiled bodies into the store
(`handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`,
`handoff_bodies.md`, `state.json`); `scan` enforces the body rules one named
rule per line; `decide` answers a blocking decision in place. This skill
posts nothing to GitHub except a decision comment on an already filed unit:
`/superegm:review-plan` reviews the bodies and `/superegm:file` creates the
issues.

## Inputs

*   **`SpecPath`**: the approved spec, absolute or relative to the
    repository root.
*   **`[--handoff <id>]`** (optional, after `<SpecPath>`): the handoff to plan; by default the spec's latest
    approval's. An older handoff is frozen: the helper refuses it (`<handoff>: not the latest approval: plan the rows in the latest handoff`).

Ask for a missing `SpecPath` in plain chat.

## The helper

`<HELPER>` = `${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`
(Python 3.11 or later, standard library only). Run every command as one Bash
call, `python3 '<HELPER>' <subcommand> ...`, absolute paths in single quotes,
no chaining, pipes, redirects or environment variables; the Bash `timeout`
is the default. **One command at a time**: the helper is single-writer, so
let each command finish before starting the next. This skill's commands and
the files they write are in `references/handoff_plan.md` sections 4 to 6;
the body layout is `references/issue_template.md`; the repository config
`.superegm/config.json` is `references/handoff_config.md`. Every store
write runs under the run card of Step 1; `superegm scan` writes a derived
report only and needs no card. When the invocation named a handoff, pass `--handoff '<id>'` to `runcard open` and to every helper call below; without it the card carries the handoff it resolved.

## Step 1: Run card

1.  When `.superegm/config.json` is missing, run `python3 '<HELPER>' init
    --artifacts-dir '<a directory outside the working tree>'` and show the
    owner the by-hand steps it prints.
2.  Run `python3 '<HELPER>' runcard open --skill plan --artifact
    '<SpecPath>'`. The printed id is `<CARD>`; every writing command below
    carries `--runcard '<CARD>'`. A card still open on this spec is marked
    interrupted by the new one.

## Step 2: The plan file

The plan file lives outside the store and the repository (for example next
to the store, `plan.md`); `state.json` records its path after the first
`graph`, so later runs need no `--plan`. Its layout and the unit schema are
`references/handoff_plan.md` sections 1 to 3: the title, the `Design:` line
naming the spec, `## 1. Issue template` (naming
`references/issue_template.md` or the repository's `issue_template`),
`## Global constraints` (one line each, exact values copied from the spec)
and `## 2. Units`.

Run `python3 '<HELPER>' orient --spec '<SpecPath>' --runcard '<CARD>'` before drafting
and again after every `graph` of Step 3 that exits 0; stop on its exit 1 with its line.
It writes `orient/map.md` (the repository map, with graphify's communities when that CLI
is installed) and, once a handoff is open, every unfiled unit's `orient/<unit>.md`, all under the handoff's directory,
copied from the repository's own files and never summarized. Read `orient/map.md` before
drafting.

1.  Read the spec's `## Units` table. For every row not yet in the plan
    file add one `### U<nn>: <title>` section by section 2's schema, its
    Steps by section 3's rules. A row the section's `Landed:` line names (a unit that landed in an earlier handoff) gets no section.
    Nor does a row filed in another handoff of the spec: `graph` lists them in `handoff_units.json`'s `filed_elsewhere` and refuses a section for one.
    Keep every section already there; a filed unit's section (one with an
    issue number in `state.json`) is frozen and stays byte-identical.
    Set `Tier:` on every section by section 2's criteria (`difficult`, `doable` or `easy`): it picks the builder's model and effort, and a wrong tier costs rounds.
2.  Nothing is committed under the repository's docs: the plan file stays
    outside the tree, and the store keeps its copy.

**Writing a Step** (spec section 9.1; the full rules are section 3 of
`references/handoff_plan.md`). The fence carries the test's signature (name, fixtures, any `@pytest.mark.parametrize`)
and its assertions with the spec's exact values, with arrange/act lines only where those do not determine them;
a full test body appears only for an algorithm or data the assertions do not determine.
The `Implement` line is one sentence: the signature, the file and the values the spec pins;
it never restates what the test asserts.
A rule family is one parametrized Step, never one Step per rule; a copy/rename table or an edit list is test data,
one parametrized test over it (the test is the table) and an `Implement` line that says "make the table hold".
The `Run` line and the closing line are optional: absent, the Step's command is `pytest <test path>::<test name> -q`,
or `pytest <test path> -k <test name> -q` when the fence is parametrized, and the commits are
`test(S<n>): <test name>` then `feat(S<n>): <test name>`; an explicit ``Run `<command>` `` line
overrides the default and is the Step's one command.

## Step 3: graph

Run `python3 '<HELPER>' graph --plan '<plan file>' --runcard '<CARD>'`. It
refuses, naming the file and line where one applies, on: a spec whose
sha256 no approval matches (back to `/superegm:review-spec`); an older
handoff (`graph: <handoff>: not the latest approval: plan the rows in the latest handoff`);
a section for a unit filed in another handoff (`graph: <U> is filed in <handoff>: no section for it`);
a plan-shape deviation (a missing block, an interfaces line, a
definition-of-done item, a decide item with one option or a default outside
its options, no `## Global constraints`); an unknown reference; a
`Blocked by` cycle; a shared-file chain that contradicts the blockers; a
filed unit whose section differs from the stored one. Fix the plan file and
run it again until it exits 0. It prints the handoff id, one `wave <n>: …`
line per wave, the critical path and what it wrote.

## Step 4: scan and decisions

1.  Run `python3 '<HELPER>' scan --plan '<plan file>'`. It prints the per-unit numbers table
    (`bytes`, `fenced_share`, `steps`, `spec_range_bytes`, `ratio`; also
    written as `plan/scan/<unit>.json` in the handoff's directory for the proportion reviewer
    with its `warnings[]`, which never block), then one
    `<rule>: <unit>: <line>` per problem, then `scan: clean` or
    `scan: <n> problem(s)`. The rules are spec section 9.1's: `body-size`
    (over 49,152 bytes: split the unit), `checkbox`, `placeholder`,
    `consumes-undefined`, `consumes-producer`, `global-constraints`,
    `review-focus`, `review-focus-test`, `step-group`, `step-scope`,
    `decision-blocking`, and the raw-text `banned-term`, `mention`,
    `merge-marker`, `dod-missing`. Fix the plan file, run `graph`, then
    `scan` again, until `scan: clean`.
2.  Every `decision-blocking` line is decision point 3: ask the owner one
    question whose options are the item's own `(a) …; (b) …` lines, the
    default marked, as the sole tool call in the turn; then run
    `python3 '<HELPER>' decide --unit U07 --decision D1 --answer '(b)'
    --runcard '<CARD>'` (or `--default`). In leavemealone mode the judges
    answer instead (`superegm judges question`, wired by the routing),
    which then runs `decide --unit U07 --decision D1 --default --judges
    <id>` or `--answer` with their choice.
3.  For an unfiled unit `decide` writes `; answer: (b)` into the item's
    line in the plan file and re-renders that unit's body, so the next
    `scan` is clean for it. For a filed unit it leaves the plan line, the
    body and `unit_<id>.md` as filed, records the answer in
    `state.decisions` and writes `decision_comment_<unit>_D<n>.md`
    in the handoff's directory: run `python3 '<HELPER>' scan --plan '<plan file>' --comment '<that file>'`,
    then post it with `GH_HOST=github.com gh issue comment <number> -R
    OWNER/NAME --body-file '<that file>'` under this card (its skill lists
    `github-write`), one Bash approval.

## Step 5: Report and close

1.  Tell the owner, in a few lines, the handoff id, the wave table from
    `handoff_units.json` (wave, unit, title, blocked by), the critical path
    and the scan numbers; no body text in chat.
2.  Run `python3 '<HELPER>' runcard close '<CARD>'`.
3.  Next: `/superegm:review-plan '<SpecPath>'` reviews every unfiled body;
    `/superegm:file` creates the issues once that review converged.

## Leavemealone-mode

In leavemealone-mode (`--leavemealone` on the invocation, or `config.mode`) a
`decision-blocking` line of Step 4 (decision point 3, a `blocking: yes` item)
goes to the judge panel instead of the owner, and what the converged answer
applies is the one routing table
`${CLAUDE_PLUGIN_ROOT}/skills/judges/references/leavemealone.md` (this skill
carries none of its own). Render the item's question from the record:
`python3 '<HELPER>' judges question --unit <U> --decision D<n> --runcard <card>`
(its options are the item's own `(a) …; (b) …` lines). Then the panel sequence
of the reference: `python3 '<HELPER>' judges open --question <path> --evidence <paths> --parent <card>`
(the spec is the evidence; the panel's child card hangs under this card), the
dispatch of the `judges` skill (Astra through the runner, the Claude judges
through `superegm:judge`, `judges record`, `judges diff`, round by round), and
`python3 '<HELPER>' judges verdict --panel <id> --runcard <card>`. A converged
`(<id>)` is applied with
`python3 '<HELPER>' decide --unit <U> --decision D<n> --answer "(<id>)" --judges <panel> --runcard <card>`,
which rewrites the plan line of an unfiled unit (`; answer: (<id>)`) and
re-renders its body, so `graph` and `scan` again; a filed unit gets the comment
file of Step 4 item 3. An unconverged question stays open: end the invocation
naming it and `judges/<id>/verdict.json`, close the card, and the owner answers
it with `decide` by hand.
