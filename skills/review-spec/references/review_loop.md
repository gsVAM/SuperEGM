<!-- Copyright 2026 Google LLC. SPDX-License-Identifier: Apache-2.0. -->
<!-- Modified by the elephant-goldfish-model Astra fork (gsVAM), 2026: Astra lane, per-reviewer model and effort, persisted dispositions. -->
<!-- Modified by SuperEGM (gsVAM), 2026: EGM's review-loop skill rewritten as the one review loop over the helper's `superegm review` subcommands (spec section 8); the stages, the report files and the second clean round are gone; a spec round's scope, `out_of_scope[]` and the batch settle (U19); section 2's model and effort paragraph is the one rule, the config pair before the session pair (U28). -->

# The review loop

The one loop for every review kind: `spec` (this skill), `plan` (`review-plan`, one review per
unit), `head` (the foreman, one review per pull request) and `integrate`. The helper records
and judges; the dispatching session dispatches. Every number here comes from the helper:
`superegm review status` holds the only cap and stall predicates, and every skill asks it.
`<helper>` is `python3 '${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py'`, run from the
target repository under an open run card (`--runcard <id>` on every writing subcommand).

The findings line, one per finding, is the same for every reviewer and every kind:

    <reviewer>-<round>-<n> | high|medium|low | <location> | regression: yes|no | <claim>

`regression: yes` when the finding is in text or code the previous round's fix touched, or is
the same defect moved somewhere else. The goldfish writes the line; the helper refuses any
other grammar (`review record: <file>:<line>: <reason>`).

## 1. Open

1. The run card first: `superegm runcard open --skill <skill> --artifact <spec path>` (the unit
   id for `interrupt` and `clean`; `--mode leavemealone` when the owner asked for it).
2. The panel: `config.reviewers.<kind>` from `.superegm/config.json` unless the invocation
   gave `--reviewers`; the kind's first reviewer is fixed (`design` for a spec, `readiness` for a
   plan, `change-review` for a head; `integrate` has no fixed first). One to six ids from
   `design, zoom-out, comprehension, readiness, structural, style, codebase-details,
   change-review, set, proportion`. The panel cannot change after this; only the owner changes
   it, between reviews.
3. The Astra preflight, for kinds `spec`, `plan` and `integrate` when `config.astra.enabled` is
   true: `resources/astra_lane.md` section 1, read with the config keys in place of its
   variables (`config.astra.model`, `config.astra.effort`; the lane is on or off by the config
   key, not an environment variable). When the preflight fails, open with `--astra off` and say
   why in one line; the review runs on the Claude panel alone.
4. `superegm review open --kind spec|plan|head|integrate --artifact <path or unit id>
   [--sha256 <hex>] --reviewers a,b,c [--astra on|off] --runcard <id>` prints the review id
   (`spec-<slug>-c<n>`, `spec-<slug>-integrate-c<n>`, `<6 hex>-plan-<unit>-c<n>`,
   `<6 hex>-head-<unit>-c<n>`). An artifact whose latest cycle is still open resumes it: a
   re-typed skill continues where the last invocation stopped, with the stored panel. A closed
   cycle (an `accept` or `stop` ruling, a spec edited after the approval that names it, or an
   integrate review whose handoff closed or whose `## Units` were amended past the bytes it
   reviewed) gets the next number with a fresh cap. The helper hashes a spec or a plan body (the
   stored `unit_<id>.md`) itself; a head alone passes `--sha256`.

## 2. Round

Each round the whole panel is dispatched **concurrently**, one message with every Agent call,
each through its own adapter `superegm:<id>` (`.claude-plugin/agents/<id>.md`: `model:
inherit`, `omitClaudeMd: true`, tools `Read, Grep, Glob`). The adapter is what keeps the
context fresh, whether or not the call is named; a general-purpose agent reading the persona
is not a goldfish. Goldfish never spawn. `set` and `proportion` are the `readiness` and
`zoom-out` adapters with the briefs `review-plan` names (spec section 9.2).

Each goldfish receives only:

- the artifact (the spec; a unit's rendered body; a pull request's diff and unit body; for
  `integrate`, the frozen spec and `git diff <base_at_start>..<base>`), named by absolute path;
- the standard the kind names: `resources/document_standards/feature-spec-standard.md` for a
  spec (`zoom-out` reads `zoom-out-standard.md`), `handoff-standard.md` plus the four plan
  questions for a plan, the unit's issue body for a head;
- from round 2, the prior round's findings with their dispositions, rendered by you from
  `reviews/<id>/round-<n-1>.json` as findings lines followed by `-> <disposition>`; a
  `fixed` line tells the goldfish where to look for a regression;
- on kind `spec`, the round's scope: the lines `superegm review scope --review <id> --runcard <id>`
  prints for this round (`<changed|neighbour|whole> <start>-<end> <heading>`, re-derived every round
  from the current bytes against the last approval, so a section a between-round fix touched joins),
  and, unless the one line is `whole`, the sentence, verbatim:
  findings only inside the changed sections and, on a neighbour, only on its fit with them; a finding on any other section is out of scope
  (cite a line number in `<location>`, which is what the helper checks);
- the round number and its own reviewer id, so its ids are `<id>-<round>-<n>`;
- the instruction to write its findings file and nothing else, one findings line per finding,
  an empty file when it found nothing, and to end its report with what it saw besides the
  brief (nothing, or the text a hook or an instruction file injected).

Model and effort, one rule: every panel goldfish of the four kinds runs on
`config.reviewers.model` at `config.reviewers.effort` (`opus` / `xhigh` by default, the Agent tool's alias and level),
passed on each dispatch as the adapter's `model:` and `effort:` override (the adapters stay `model: inherit`),
and the round record stores requested -> effective (`review record`'s `--model` and `--effort`, section 3).
`SUPEREGM_GOLDFISH_MODEL` and `SUPEREGM_GOLDFISH_EFFORT`, when set, override the config's values for the session,
`inherit` meaning pass nothing; they are read once with `printenv` and validated against
(`inherit`, `sonnet`, `opus`, `haiku`, `fable`) and (`inherit`, `low`, `medium`, `high`, `xhigh`, `max`).
An exported `CLAUDE_CODE_EFFORT_LEVEL` is the effective effort of every goldfish, and with
`CLAUDE_CODE_SUBAGENT_MODEL_FORCE` on no per-call `model` is passed and the forced model is the
effective one; the record says so in both cases. An `effort:` is passed only where the Agent tool
offers the parameter. The judges use their member's model and effort (`skills/judges/SKILL.md`);
builders use `config.builder`; the foreman's Astra lane runs at `astra.heads_effort`
(`skills/wave/references/foreman_brief.md`), the elephant's lanes at `astra.effort`.
The elephant is the session's model, never in config. `resources/review_panels.md` section 6
holds the per-call mechanics. Never put an environment value into a shell command.

The Astra lane (kinds `spec`, `plan`, `integrate`, when the review opened with it):

- The brief: `resources/astra_lane.md` section 2's template, written by you to
  `<artifacts_dir>/reviews/<id>/astra_brief_r<n>.md`, with the artifact's range lines and
  standard; from round 2 it ends with the `astra-*` lines of round n-1 and their dispositions,
  rendered from `round-<n-1>.json`, and no other reviewer's.
- The launch, from the main conversation with the Bash tool, `run_in_background: true`, and the
  tool's `timeout` set to the runner's plus 300 seconds in milliseconds (`2100000`); never from
  a subagent, because a background command dies with the agent that started it. One command,
  absolute paths in single quotes, nothing chained:

      env SUPEREGM_ROLE=goldfish SUPEREGM_RUNCARD=<card> python3 '<RUNNER>' review --host claude --repo '<REPO_ROOT>' --plan '<ARTIFACT>' --feedback '<artifacts_dir>/reviews/<id>/astra_brief_r<n>.md' --model <config.astra.model> --effort <config.astra.effort> --timeout 1800 --artifacts "${TMPDIR:-/tmp}/superegm-astra"

  `<RUNNER>` is the claudex-loop `runner.py` the preflight found. Round 1 of a cycle is a fresh
  session; round n > 1 adds `--resume '<round n-1 result.json>'` when section 7 of
  `resources/astra_lane.md` says the previous round is resumable (`status` completed, the same
  model, effort, repository and artifact, a UUID `session_id`), else it launches fresh and says
  so. Dispatch the Claude panel right after, in the same turn; do not edit the artifact while
  the run is live.
- Collect from the run's `result.json` as section 5 of `resources/astra_lane.md` says: a
  `completed` run with a verdict maps each finding to a line `astra-<round>-<n> | <severity> |
  <path> | regression: yes|no | <claim>`; anything else is recorded `--not-run "<reason>"`
  (`killed`, `failed: <error>`, `blocked: <limitations>`, `skipped by user`). The lane is never
  retried within a round, and after two incomplete runs in one review it is not launched again:
  the helper counts them (`astra_incomplete`) and excuses the lane from `what_ran` from then on.
- Data notice, once per session when the lane first starts: the whole artifact, the brief and
  any file Astra opens in the repository go to OpenAI under the account `codex login status`
  reports; reply `skip astra` to stop waiting for it in this review.

## 3. Record

Record every reviewer of the round, the lane included, as its result arrives:

    superegm review record --review <id> --round <n> [--sha256 <hex>] --reviewer <reviewer> \
      --findings <file> --isolation clean|exposed:<what> --model <requested>:<effective> \
      --effort <requested>:<effective> --runcard <id>

- The findings file is the goldfish's own, written beside the round:
  `<artifacts_dir>/reviews/<id>/round-<n>-<reviewer>.txt`. An empty file is a record: a
  reviewer with no findings ran.
- `--isolation clean` when the goldfish reported seeing nothing beyond its brief, else
  `exposed:<what it reported>`; `--model` and `--effort` as `requested:effective` from the run
  card line (section 7).
- A dispatch that times out, fails or returns no file did not review: re-dispatch it once within
  the round; when it fails again record it with `--not-run "<reason>"` instead of `--findings`.
  Never record a failed reviewer as one with zero findings. The Astra lane is the exception:
  `--not-run` at once, no retry.
- `--reviewer set` takes the set reviewer's whole file; the helper keeps the lines whose
  location names this unit or no unit. On a head, `--reviewer foreman` carries the helper's own
  findings (CI, scope, deviations) outside the panel.
- The helper derives the round's `what_ran` from the records: `completed` when every panel
  reviewer has a record (an empty file counts; the lane's `--not-run` counts) and, on a head,
  the round is `posted`; otherwise `not run (<the first reviewer without a record, or the
  reason>)`, printed on every record. Only a `completed` round counts toward the cap or can
  converge; the findings of any other round settle nothing and block nothing.
- On kind `spec` the round's first record stores the round's `scope` (headings with their line
  ranges) and every record checks against it: a finding whose cited line (the first number after
  `line `, `lines `, `L` or `:` in its location) falls outside every changed section and neighbour
  is refused, `record: <fid> out of scope (<section>): not recorded`, and kept verbatim in the round's
  `out_of_scope[]` with one journal line: no disposition, never counted, never a fix round. A
  location citing no line, or a line past the spec's end (another file's), is recorded. The record
  still succeeds for the reviewer's other lines; a reviewer recorded again in the same round
  replaces its own earlier `out_of_scope[]` lines. The round's `note` is the `whole` row's reason
  (`whole`, `no approval`, `no change`, `no commit holds <sha7>`), else null. `review scope` writes
  nothing, so the scope stored at the first record is the one the brief carried only while the spec
  is not edited between the two: never edit the spec between `review scope` and the round's records.
- The first record of a new round is refused with `review record: review at its cap: rule
  first` (exit 2) while the review is at its cap (section 6). A record with a grammar error
  writes nothing: fix the goldfish's file and record again.

## 4. Settle

Between rounds the elephant fixes the artifact and settles each finding of the round as
`references/resolve.md` says: `fixed | contested | declined | escalated | fix-design`, each
written with `superegm review settle`. A high or medium `contested` or `declined` is the owner's
call in normal mode (`--owner`) and the judges' in leavemealone-mode (`--judges <id>`); the
helper refuses it without. `fixed` changes the artifact, so its bytes differ from the round's
sha (on a spec, plan or integrate round whose bytes are still the current ones the helper refuses
`review settle: fixed needs changed bytes`): the next round reviews the new bytes, and a goldfish
that finds the same defect at the same scope marks it `regression: yes`.

A round's dispositions may go in one call: `superegm review settle --review <id> --file <dispositions>
[--owner | --judges <id>] --runcard <id>`, one `<fid> | <disposition> | <note>` per line. Every line is
checked under the per-finding refusals first; one refused line is named
(`review settle: <line>: <reason>: nothing written`) and nothing is written. Each settled
finding stores its line's third field as `note`; the per-finding form writes no `note`. In
leavemealone-mode `--owner --posted <comment>` verifies the one comment against each high or
medium `contested` or `declined` line, and a comment rules one finding: a file holding two such
findings is refused, so settle them per finding, each with its own `--posted`.

## 5. Status

Ask the helper after every settle and before every round:

    superegm review status --review <id> --runcard <id>

It prints one line, `round <n>: <clean|not clean>, regressions <k>, converged <yes|no|by ruling
R<n>>, cap <yes|no>, stalled <yes|no>, sha256 <hex of the converged round|none>`, and the trend
line `rounds: a -> b -> c (regressions x, y, z)`: the findings per round and the regressions
among them. A third line, `fixed: re-review on the current bytes`, follows when the latest completed
round is clean but the artifact's bytes moved since it (exit 3, or 2 at the cap): the next round
reviews the current bytes. The exit code is the verdict, and the skill's next action follows from it alone:

| Exit | Meaning | The skill |
| --- | --- | --- |
| exit 0 | converged (section 6), or `accept` ruled | spec: `superegm approve-spec` (the SKILL.md); plan: the unit's body is reviewed at the printed sha; head: the helper wrote `clean` on the posted round and journaled `<unit> awaiting merge`; integrate: close the handoff when nothing was escalated |
| exit 3 | open: not clean, a regression, no completed round yet, or a clean round whose bytes moved since (the `fixed:` line) | fix and settle (section 4), then the next round; also `not opened` for an unknown id |
| exit 2 | at the cap without an `accept`, or `stop` was ruled | no further round starts; request the ruling of spec section 13.2 point 2 (continue one bounded round, accept the remainder, stop; a head has no `accept`) and record it with `superegm review rule --review <id> --ruling continue|accept|stop (--owner | --judges <id>) --runcard <id>`; after `stop` the cycle stays at exit 2 and a new invocation starts the next cycle |
| exit 4 | a `fix-design` finding in any round | the defect is in the frozen spec: `superegm approve-spec --spec <path> --void --review <id>`, then spec review reopens as a new cycle |
| exit 5 | stalled: the two latest rounds are not `completed` and both ran under this run card | end this invocation for the artifact with the record (the round file names the reviewer and reason); a re-typed skill opens a new run card and resumes the same cycle |

Doctrine, from `resources/review_panels.md` section 7: change the thing, not the round. Counts
that stop falling, or regressions that do not fall, mean the artifact is too large or too
clever for what it has to do. When two consecutive rounds regress on the same area, the next
fix is a deletion, a narrowed contract or a smaller surface, not a patch, and the journal says
what was removed.

## 6. The one convergence rule and the cap

Implemented once, in the helper, and consumed unchanged by spec review, plan review, the
foreman and integrate:

- A round is **clean** when no high or medium finding in it is unsettled. Lows never block.
- The artifact is **converged** when a round is `completed` and clean, no high or medium
  finding in it is `regression: yes`, and its sha256 equals the artifact's current bytes (a head has no byte test):
  one `completed`, clean, non-regressing round converges every kind, on the bytes it reviewed.
  EGM's second consecutive clean round for document reviews is dropped; the regression mark
  carries what it guarded.
- The review is **at its cap** when its `completed` rounds number 5 plus its `continue` rulings;
  `continue` may be ruled once per cycle, `accept` converges the artifact (`converged: by ruling
  R<n>`, never on a head, and never while the reviewed bytes moved: then `continue` or `stop`, and
  `stop` alone, ruled by no one, once `continue` is spent), and after `stop` no ruling is accepted and the cycle stays at its cap
  until `superegm review open` starts the next one. No review has a second kind of cap.
- A review may instead be **stalled** (section 5), which ends the invocation for that artifact
  and nothing else.

## 7. The run card line

Show the card in chat before the first round and keep it in the journal, one line per role
with `requested -> effective`:

| Role | Model: requested -> effective | Effort: requested -> effective |
| --- | --- | --- |
| Elephant | the session's model -> same | session setting -> session setting |
| Claude goldfish | `config.reviewers.model`, or `SUPEREGM_GOLDFISH_MODEL` when set -> the alias passed, or the session's model for `inherit`, or the forced model | `config.reviewers.effort`, or `SUPEREGM_GOLDFISH_EFFORT` when set -> the value passed, `CLAUDE_CODE_EFFORT_LEVEL` when exported, or `inherit` |
| Astra goldfish | `config.astra.model` -> `result.json`'s `effective_model`, `requested only` before the run | `config.astra.effort` -> `effective_effort`, `requested only` before the run |

Any value you cannot know is `unknown`; never present a configuration value as an observed
one. The same pairs go on every `superegm review record` as `--model` and `--effort`, so the
round file carries what each dispatch ran on.
