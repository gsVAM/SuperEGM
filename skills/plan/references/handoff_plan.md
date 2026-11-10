<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by the elephant-goldfish-model Astra fork (gsVAM), 2026. -->
<!-- Modified by SuperEGM (gsVAM), 2026: the section 9.1 unit schema (interfaces, review focus, Steps, decisions with options), the plan file outside the store, the files and commands of the plan skill only; one directory per handoff (U32); the optional Tier field (U33). -->

# The plan file: schema, the unit's Steps, files and commands

The plan file is the elephant's text, kept outside the store and the
repository and named by `--plan` on the first `graph` (`state.json.plan`
after). The helper `scripts/superegm.py graph` parses it strictly (any
deviation stops with the file and line number), copies it into the store as
`handoff_plan.md`, writes `handoff_units.json`, one `unit_<id>.md` per unfiled
unit and `handoff_bodies.md`, and never writes the plan file itself.

## 1. File layout

```markdown
# Handoff plan: <spec title>

Design: `/absolute/path/to/docs/specs/2026-11-03-webhooks-design.md`

## 1. Issue template

(the layout of references/issue_template.md, or the repository's
`issue_template`)

## Global constraints
- Python 3.11, standard library only
- <one line per project-wide rule of the spec, exact values>

## 2. Units

### U01: <title>
...one section per unit, as in section 2 below...
```

The `Design:` line names the approved spec (absolute, or relative to the
plan's folder). `graph` reads `approvals/<spec-slug>.json` in the store: the
spec's sha256 must equal the approval's, the handoff id is the approval's
(`<slug>-<6 hex>`, kept across a re-approval), and the store holds one
`<handoff id>/` directory per handoff, several side by side (a flat
1.0/1.1 store keeps its own layout, section 4). The `## Global constraints` lines
are rendered verbatim into every body.

## 2. One unit

```markdown
### U03: Webhook delivery worker
| Field | Value |
| --- | --- |
| Objective | One sentence: what exists when this unit is done. |
| Scope paths | `src/webhooks/queue.ts` (modify), `src/webhooks/deliver.ts` (create) |
| Design range | `docs/specs/2026-11-03-webhooks-design.md:140-171 (### 4.2 Delivery and retries)` |
| Blocked by | U01, U02 |
| Shared files | `src/webhooks/queue.ts`: after U01, before U05 |
| Risk | medium: touches the request path |
| Size | M |
| Tier | doable |

Interfaces
- Consumes: enqueue(event) -> Job (U01)
- Produces: deliver(job: Job) -> Result

Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `npm test -- src/webhooks/deliver.test.ts` — cases A, B, C pass
3. Exists `src/webhooks/deliver.ts`
4. CI green on the head

Review focus (this unit)
- U03: a job whose endpoint times out — retried, never duplicated; pinned by `test_deliver_timeout`

Steps
1. Write the failing test `test_deliver_timeout` in `src/webhooks/deliver.test.ts`:
   ```ts
   test("test_deliver_timeout", () => { expect(deliver(timedOut)).toEqual({retry: true}) })
   ```
   Implement `deliver(job: Job) -> Result` in `src/webhooks/deliver.ts`.

Decide before build
- D1 Retry ceiling? options: (a) 5 attempts; (b) 10 attempts; owner: the owner; default: (a); blocking: no
```

| Field | Rule |
| --- | --- |
| Heading | `### U<nn>: <title>`. Ids are stable: never renumber; a new unit takes the next number. |
| Objective | One sentence, not empty. |
| Scope paths | Comma-separated `` `path` (create\|modify\|delete) ``; a path may be a directory; nothing else in the cell. |
| Design range | `` `path:start-end (heading)` `` into the frozen spec, start <= end. |
| Blocked by | `none` or unit ids, comma-separated. A blocker is a unit that creates or changes a file or symbol this unit uses. |
| Shared files | `none` or `` `path`: after U01, before U05 `` items separated by `; `. `after` adds an edge from that unit to this one; `before` from this one to that unit. |
| Risk | `low\|medium\|high: reason`. |
| Size | `S` (up to 3 scope paths), `M` (up to 8), `L` (more; about twenty Step groups, the most a body holds). |
| Tier | Optional; `difficult`, `doable` or `easy`, set by the author: `difficult` when the Steps leave a design choice open, the unit holds a novel algorithm or an unverified platform behaviour, or it consumes the interfaces of more than one subsystem; `easy` when the Steps are mechanical with pinned signatures and no open choice; else `doable`. A difficult unit keeps a small Scope and few Steps. The tier picks the builder's model and effort (`builder.tiers`; doable is `builder.model` and `builder.effort`); a section without it is doable; another word is refused as a bad `Size` is. |
| Issue | Optional; `#<n>`, an open issue in `config.repo` that `file` adopts instead of creating one; `graph` refuses a `#<n>` the spec's `## Units` section does not name; the dry run heads such a unit `### edit #<n> <unit> (old body sha256 <hex>)` where a created unit reads `### issue <unit>`. |
| Interfaces | One item per line: `- Consumes: <name> (U<nn>)` names what this unit uses and the producing unit; `- Produces: <name>` what later units rely on. A name is `fn(params) -> type` for a Python interface, `superegm <sub> <flags> → <stdout shape>; exit <codes>` for a helper subcommand, or `<file> key <path>` for a store field; `scan` matches on the identifier before `(`, the subcommand words, or the key path, and refuses a Consumes no sibling produces or whose producer is not a direct or transitive blocker. |
| Definition of done | Numbered items. Item 1 is always `The test for each Step was committed before its implementation (checked by superegm tdd-order)`; every other item is ``Run `<command>` — <what passing means>``, ``Exists `<path>` `` or `CI green on the head`. Only `Run` items are commands. |
| Review focus (this unit) | ``- U<nn>: <input or failure mode> — <expected behaviour>; pinned by `<test name>` ``; the test must be one of the owning unit's Steps. |
| Steps | Numbered groups, each a `Write` line, a fence and an `Implement` line (section 3). |
| Decide before build | `- none`, or `- D<n> <question> options: (a) <option>; (b) <option>[; …]; owner: <owner>; default: (a); blocking: yes\|no` with two or more options and the default among them. `decide` appends `; answer: (b)` to the line of an unfiled unit; a `blocking: yes` item without an answer keeps the unit from passing `scan`. |

The graph: edges are the `Blocked by` entries and the shared-file `after` and
`before` entries. A unit's wave is `1 + max(wave of its predecessors)`. A
`Blocked by` cycle stops with the cycle listed. A shared-file chain that
contradicts the blockers stops with "shared-file chain contradicts the
blockers": fix the chain or the blockers; the helper never drops an edge
silently. The critical path is the longest chain by waves, ties broken by id.
There are no parts: a unit is one issue and one PR.

## 3. Writing a unit's Steps

A Step is done when the builder can write exactly one reasonable thing from
it: unambiguous, not complete. Each group is three parts:

- The `Write` line, `` <n>. Write the failing test `<test name>` in `<test path>`: ``
  (the test name in its first backtick span, the test path in its second).
- The fence: the test's signature (name, fixtures, any
  `@pytest.mark.parametrize`), its assertions with the spec's exact values,
  and arrange/act lines only where the signature and assertions do not
  determine them. A full test body appears only for an algorithm or data the
  assertions do not determine: a plan longer than the code it describes has
  written the code instead.
- The `Implement` line, one sentence: the signature, the file (its last
  backtick span is the implementation path, under one of the Scope paths)
  and the values the spec pins. It never restates what the test asserts.

The `Run` line expecting FAIL and the closing line (runs the same command,
expects PASS, names the commits) are optional. Absent, the Step's command is
`pytest <test path>::<test name> -q`, or `pytest <test path> -k <test name>
-q` when the fence holds `@pytest.mark.parametrize`, and the commit subjects
are `test(S<n>): <test name>` then `feat(S<n>): <test name>`. An explicit
``Run `<command>`; expected: FAIL`` line overrides the default and is the
Step's one command. A rule family is one Step whose test is parametrized,
never one Step per rule. A copy/rename table or an edit list is test data:
one parametrized test over the table (the test is the table) and an
`Implement` line that says "make the table hold"; no prose copy of a table.

Lines that decide nothing (`TBD`, `handle edge cases`, `add appropriate
validation`, `write tests for the above`, a Consumes no unit produces) are
refused by `scan`; a function body the signature and the test already
determine is a transcript, which the proportion reviewer refuses.

Self-review before `graph`, with the spec in front of you: every section of
the spec's range for this unit has a Step; every Step lets the builder write
exactly one reasonable thing and carries nothing more; the names and
signatures a later unit consumes are the ones an earlier unit produces; every
review-focus line has its test in the owning unit's Steps; the body is no
longer than the decisions the builder cannot make alone (compare `scan`'s
`ratio` and `fenced_share` to the spec range).

## 4. Files the helper writes

| File | Written by | Content |
| --- | --- | --- |
| `<handoff id>/handoff_plan.md` | `graph`, `decide` | The store's copy of the plan file; a filed unit's section here is the one the plan file must still carry. |
| `<handoff id>/handoff_units.json` | `graph`, `decide` | The parsed units (interfaces, review focus, decisions with options and answers, `body_sha256` per unit) with waves and predecessors, the `order`, the edges, the critical path. Derived; never hand-edited. |
| `<handoff id>/unit_<id>.md` | `graph`, `decide` | The unit's section plus its issue body as it will be posted, in a four-backtick `markdown` fence under `## Issue body as posted`. Written for unfiled units only; a filed unit's file is frozen. |
| `<handoff id>/handoff_bodies.md` | `graph`, `decide` | Every title, label set and body in creation order, with placeholders `#<U01>` for blockers and `#<tracking>` for the tracking issue. |
| `<handoff id>/state.json` | `graph`, `decide` | `handoff_id`, `repo`, `remote`, `repo_root`, `plan` (the plan file's path), `design`, `units[<id>].body_sha256`, `decisions` (section 5). |
| `<handoff id>/plan/scan/<unit>.json` | `scan` | `bytes`, `fenced_share`, `steps`, `spec_range_bytes`, `ratio`, `warnings[]`: the proportion reviewer's evidence. A derived report, written without a card. |
| `<handoff id>/decision_comment_<unit>_D<n>.md` | `decide` | For a filed unit only: the comment headed `**Decision D<n>:**` the skill posts on the issue under a `github-write` card. |

A flat 1.0/1.1 store keeps `handoff_plan.md`, `handoff_units.json`, `handoff_bodies.md` and `state.json` at its root and the unit-keyed files (`unit_<id>.md`, `plan/scan/<unit>.json`, `decision_comment_<unit>_D<n>.md`) under `<6 hex>/`.

## 5. The state file

`state.json` holds EGM's handoff state with `plan` (the plan file outside
the store), per unit `body_sha256` (the sha256 of the rendered body with its
placeholders, as filed once the unit is filed), and `decisions`
(`"U03/D1": {answer, by, decided_at}`, `by` being `owner` or
`judges:<id>`). Later skills add `filings[]`, `base_at_start` and
`closed_at`; `graph` starts a fresh state once `closed_at` is set.

## 6. Helper commands

Run every command as one Bash call, `python3 '<HELPER>' <subcommand> ...`,
absolute paths in single quotes, no chaining. `<HELPER>` is
`${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`.

| Command | Writes | What it does |
| --- | --- | --- |
| `graph [--plan P] --runcard C` | the store | Parses the plan under its approval, builds the graph, renders and hashes the unfiled bodies, writes the files above; prints `handoff <id> on <repo>: <n> units, <w> waves`, one `wave <n>: …` line per wave, the critical path and what it wrote. Exit 1 with `graph: <reason>`. |
| `scan [--plan P] [--comment FILE]` | `<handoff id>/plan/scan/<unit>.json` | Prints the numbers table, then one `<rule>: <unit>: <line>` per problem, then `scan: clean` or `scan: <n> problem(s)`; exit 1 on a problem. With `--comment` it scans that file as a comment (the configured `fix_request_mention` may open it). |
| `decide --unit U --decision D<n> (--answer "(x)" \| --default) [--judges ID] --runcard C` | the store, the plan file | Records the answer, one of the item's own options: an unfiled unit's plan line gains `; answer: (x)` and its body is re-rendered; a filed unit keeps its line, body and file and gets the comment file. Exit 1 with `decide: <reason>`. |
