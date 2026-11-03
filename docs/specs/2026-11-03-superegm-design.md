# SuperEGM — design

Date: 2026-11-03. Status: DRAFT, round 5 (the cap) of goldfish spec review. Owner: gsVAM.
Inputs: the brainstorm brief (stream 4); the SuperEGM judge-panel verdict (converged, round 2 of
5); the cap-panel verdict on EGM 0.2.1; superpowers 7.0.0 and the EGM Astra fork at commit
9bc49d4 (0.2.1 plus the four round-12 fixes), both as installed and surveyed file by file; the
round-1 to round-4 goldfish reports (75, 75, 74 and 61 findings); the judge panel's ruling on the
wave's scope at round 3 (`judges/q-wave`: Astra on PR heads deferred, automatic builder launch
kept). Rounds 2–5 apply the non-convergence doctrine: each deletes and narrows rather than
patches; the removals are listed in §3.1.

## 1. Intent

SuperEGM is one Claude Code plugin that is the owner's entire software workflow, from an idea to a
merged pull request, run as one skillset. It absorbs two toolkits that each own half of that
workflow today:

- **superpowers 7.0.0** (MIT) owns the unit of work: brainstorming that ends in a written design;
  plans made of red→green→commit steps with the actual test code; exact interfaces between units;
  global constraints copied verbatim; a review focus; no placeholders; "rulings, not stalls".
- **EGM 0.2.1, Astra fork** (Apache-2.0) owns orchestration and verification: goldfish isolation
  enforced by adapters; an adversarial gate before anything is written anywhere; a second vendor's
  model as reviewer; a dependency graph cut into waves; idempotent, crash-recoverable GitHub
  filing; a foreman per unit reviewing every PR head against the unit's definition of done with CI
  as evidence; convergence with regression marking and a pausing cap; the run card; a merge that
  stays human.

The merge thesis: superpowers' unit of work inside EGM's orchestration, plus one distinction EGM
never had. **The spec is not the plan.** The spec is the design document. The plan belongs to the
GitHub issue, one per unit, and is TDD-shaped from its first line.

### 1.1 Why now
The owner reviews designs with EGM and builds with superpowers, and the seam costs them: two entry
styles (typed vs auto-invoked), two memory stores, two convergence rules, reviewers that load the
project's CLAUDE.md when they should not, and no way to run a phase while asleep. Twelve
adversarial rounds on EGM 0.2.x proved the parts; what remains is the seam.

### 1.2 What success looks like
The owner types one skill per phase. A phase typed in leavemealone-mode runs to its gate without
the owner: a spec review converges or is ruled on, a plan review converges, a wave ends with one
set of merge-ready draft PRs. The owner wakes to those PRs, or to a short list of questions the
judges could not settle, merges, and types the next phase. Nothing is merged by a machine. Every
review, verdict and launch is on disk with its isolation recorded.

## 2. Vocabulary

| Word | Meaning in SuperEGM |
| --- | --- |
| **owner** | the human. Approves and freezes specs, rules when the judges cannot, merges. |
| **elephant** | the main session. Holds context, orchestrates, launches headless sessions, dispatches foremen and goldfish. Never reviews its own work and never settles a finding against itself. |
| **helper** | the plugin's one Python program (§15), run as `superegm <subcommand>`. The only writer of the store. It never dispatches an agent. |
| **store** | the per-repository directory `artifacts_dir` (§7) holding every record SuperEGM writes. `.superegm/config.json`, committed in the repo, is its pointer and configuration. |
| **adapter** | a Claude Code agent definition `.claude-plugin/agents/<id>.md` with frontmatter `name: <id>`, fixed `tools`, and `omitClaudeMd: true`, whose body reads the persona `agents/<id>.md`. Invoked as `superegm:<id>`. A review panel lists reviewer ids; every reviewer id except `set` and `astra` is an adapter id. |
| **dispatching session** | the elephant or a foreman: the session that invokes adapters with the Agent tool and records each dispatch. |
| **goldfish** | a fresh read-only reviewer dispatched through an adapter with tools `Read, Grep, Glob`. Sees only the artifact and the evidence it is handed. Never spawns. |
| **judge** | a goldfish with a model override that answers a question file by option id instead of reporting findings. |
| **foreman** | a sub-elephant: a named subagent dispatched through the `superegm:foreman` adapter, in the foreground, to run one review round on one PR head and return one word. Its memory is `foreman/<unit>.json` and the PR's comments, never its context. |
| **builder** | a fresh headless local Claude session whose brief is one issue body, the builder orders, the rulings posted on its issue, and from round 2 the foreman's reviews of its own branch. Writes code in its own worktree, commits test-first, opens a draft PR. Not a goldfish: it writes. Never spawns. |
| **Astra lane** | an optional extra reviewer (of a spec or a plan) or judge on a non-Claude model (GPT-6 Astra) driven by the external `claudex-loop` runner (a Python CLI over the Codex CLI). Launched by the elephant from the main conversation, never through an adapter. Recorded `not run (<reason>)` when the runner is absent or its lane is down. Not used on PR heads in v1. |
| **unit** | one buildable piece of a frozen spec: one issue, one branch, one PR. Ids `U01`, `U02`, … are stable for the life of a handoff. |
| **handoff** | one run of plan → file → wave → integrate for one frozen spec. Its id names the labels, the branches, the issue marker lines and `state.json`. |
| **wave** | the set of units whose blockers have all landed, launched together. At most `max_in_flight` units are in flight at once; a unit is in flight from its first launch until it lands, is stopped, or is clean and awaiting merge. |
| **head** | the commit at the tip of a unit's PR branch at the moment a round starts. |
| **round** | one review of one artifact (a spec, a unit's plan body, or a PR head): dispatch, findings, verdict. Rounds are numbered per artifact and capped. |
| **clean** | the verdict on a round with no unsettled high or medium finding (§5). The destructive skill is always written `/superegm:clean`. |
| **landed** | a unit whose issue is closed as completed and whose watched PR is merged. Only landing makes dependants ready. |
| **DoD** | definition of done: the numbered, checkable items in a unit's body. |
| **review panel** | the 1–6 reviewers written into a run card for one artifact. Fixed for every round. |
| **judge panel** | the judges (three models from two vendors) consulted until they converge. |
| **run card** | the on-disk record of one typed invocation: skill, artifact and its hash, review panel, model tiering, mode, parent card if any, what it produced. Every effect requires an open one. |
| **effect** | anything that leaves the working tree: GitHub writes, remote branches, starting a session or worker, writing the store, destructive local operations. |
| **leavemealone-mode** | the mode in which every decision point listed in §13.2 goes to the judge panel first; the owner is paused only when the judges do not converge within their cap. |

## 3. Goals, non-goals, anti-goals

**Goals**
1. One plugin, one vocabulary, one store, one convergence rule, one entry rule.
2. Spec and plan are distinct artifacts with distinct gates; both get adversarial goldfish review
   before anything downstream reads them.
3. Every Claude goldfish and judge is isolated by construction (adapter, not prompt), and the
   record says so; the Astra lane's isolation is the runner's, recorded as the elephant reports
   it. The foreman and the builder are not goldfish: a builder's tools are an allow-list and the
   base branch is protected against direct pushes by an active protection that binds
   administrators (§11); the foreman's "never merge, never remove, never launch" is its brief,
   named in §4.1 as an accepted residual risk.
4. Every independent step runs concurrently: goldfish within a review, plan reviews across units,
   builders within a wave, foremen for every head that is ready at once, judges within a panel.
5. Maximal autonomy on request: leavemealone-mode replaces the owner at every decision point in
   §13.2 with the judge panel; only non-convergence reaches the owner.
6. Merge stays human. Nothing in SuperEGM merges, ever.

**Non-goals (v1)**
- Harnesses other than Claude Code. EGM's Codex/ChatGPT host (`.codex-plugin`,
  `agents/openai.yaml`, `docs/codex.md`, `docs/harnesses.md`) and superpowers' ten other harness
  entry points are not absorbed. The Astra lane uses the Codex CLI as a reviewer, not as a host.
- The Astra inspect lane on PR heads. Astra reviews specs and plans and sits on the judge panel;
  heads are reviewed by Claude goldfish. The lane returns in a later release with its own spec
  (judge ruling `q-wave` Q1).
- Chaining phases. Each phase is typed; a night of leavemealone work is one phase.
- External builder backends (cloud workers). Builders are local sessions.
- A local, no-GitHub wave. The wave files issues and reviews PRs; that is the one execution path.
- The brainstorming visual companion (a local Node server that also fetches a logo from the
  network). Brainstorming stays text-only.
- Running a target repository's test suite inside SuperEGM. DoD commands are run by the builder
  before it opens its PR and by the repository's CI on the head; the foreman reads CI as evidence
  and runs nothing. SuperEGM's `clean` verdict needs CI green on the head (stricter than EGM,
  whose `no-ci` state lets the owner review without CI).
- Automatic splitting of a unit that will not converge. At a PR cap the rulings are "one more
  round" or "stop"; reshaping units is the owner's, by hand, with `integrate`'s append path.
- A packed copy of the plugin in the repository. The marketplace installs from the repository
  root; `prepare_release.py` packs at release time only.
- Hooks beyond the single SessionStart hook in §6. No MCP servers.

**Anti-goals (a build that does these has failed even if it works)**
1. Two ways to do one thing: two plan formats, two ledgers, two convergence rules, two parsers
   of one grammar, two reviewers of the same kind with different isolation, two caps inside one
   review.
2. A goldfish or judge that saw CLAUDE.md, the memory index, hook output or a coordination digest.
3. A builder that saw the brainstorm, the planning session's context, or anything beyond its
   issue body, the frozen spec range that body cites, the builder orders, the rulings posted on
   its issue, and the foreman's reviews of its own branch (the target repository's CLAUDE.md and
   the hook text excepted: a builder is a session in that repository).
4. An effect without an open run card.
5. A machine merge, or a "merge locally" option anywhere in the plugin.
6. The elephant settling a high or medium finding on its own artifact.
7. A pause that reaches the owner in leavemealone-mode without a judge record showing
   non-convergence.
8. A guess about liveness. SuperEGM never infers that a runner, builder or session is dead from
   file silence. Termination is proved only by a terminal status in a result file, by an exit
   file the launched command wrote, or by the owner's typed interrupt.
9. A code-aware Markdown mention scanner. The scan is raw text plus an allow-list.

### 3.1 Alternatives considered, and what the rounds removed
- **Two plugins plus a bridge skill**. Rejected: a plugin cannot disable another plugin's hook or
  skills, so superpowers' `general-purpose` reviewers and its "merge locally" option stay
  reachable (goals 3 and 6), and the two stores and two convergence rules remain (anti-goal 1).
- **EGM 0.3 that requires superpowers**. Rejected: Claude Code has no plugin-on-plugin
  dependency; the requirement would be prose, and the same two-store problem remains.
- **Plans committed under `docs/…/plans`** (superpowers' layout). Rejected by the judge panel
  3–0: the builder's only brief must be the issue body; a committed plan file either duplicates
  the body or replaces it with something the builder must read from the repo.
- **Local merge by the foreman when a head is clean**. Rejected by the owner: merge stays human.
- **Owner-only pauses, no judge panel.** Rejected by the owner: leavemealone-mode exists so a
  phase can run without a human; the judges are the substitute, and non-convergence still reaches
  the owner.
- **A lock file in the store.** Rejected: EGM deleted locking after it caused four of seven high
  findings; SuperEGM gives every file one writer instead (§7).
- **Builders started by the owner by hand (EGM 0.2.1's wave).** Rejected by the judge panel
  (`q-wave` Q2): without automatic launch no new head appears after a `revise` until the owner
  acts, so a leavemealone wave stops after one round.
- **Removed after round 2** (each had bred findings and served no asked-for scenario): an
  automatic `split` ruling; a `deviate` subcommand (builders post the comment themselves); a
  `budget` subcommand, `max_rounds_per_night` and `stale`/`max_minutes`; a `publish` effect
  kind; a second Astra config block; a `wait` subcommand separate from EGM's `status --wait`; a
  byte-identity scheme different from EGM's; the `dangerous` sentinel; two units of a
  thirteen-unit cut.
- **Removed after round 3**: the two-step foreman round and the Astra inspect lane on heads that
  required it (judge ruling); background foremen and the `inspect`/`round` events; the `note`
  subcommand; `--judges 1|3` and `--cap` on the judges skill; `gate --accept` (an `accept`
  ruling now converges the review).
- **Removed after round 4**: the brainstorm "builder check" (the recorded spec review answers
  the same question one step later); the committed `distributions/claude` copy and its freshness
  test (a file every concurrent unit would edit); the `bootstrap` skill and its
  `bootstrap-orchestrator` adapter (no caller; a writing, spawning adapter in a plugin whose goal
  is isolation); EGM's `defer` (no caller) and `decide --published` gate (`decide` posts its own
  comment); the `launched` round phase (nothing launches inside a round any more).

## 4. Constraints

**Platform (from the live agent-teams probe and the two code bases; do not re-derive)**
- `name` on the Agent tool makes an agent addressable (`SendMessage`) and resumable; it is not a
  distinct teammate. `team_name` is deprecated. Several agents may be dispatched in one message
  and run concurrently in the foreground; their returns arrive together.
- `omitClaudeMd` tracks the agent definition, never the name. A `general-purpose` subagent loads
  CLAUDE.md whether or not it is named; an adapter does not. SessionStart hooks run for sessions,
  not for subagents dispatched by the Agent tool; the hook's role check therefore covers headless
  sessions only, and adapter subagents never see hook output.
- A Bash background command dies when its own agent returns; one started from the main
  conversation survives across turns. So builders and the Astra runner are launched by the
  elephant, never by a subagent that then returns.
- Claude Code has no plugin-on-plugin dependency and cannot disable another plugin's hook or
  skills. Hence absorb, not depend.
- A per-dispatch `model` override on a `model: inherit` adapter is honoured (EGM relies on it for
  `EGM_GOLDFISH_MODEL`); a per-dispatch `effort` is passed only when the Agent tool offers that
  parameter, and the run card records `effective: inherit` otherwise. `claude -p` takes the
  prompt as text, so a prompt file is passed by content (`claude -p "$(cat <file>)"`), never as a
  path; `--output-format json` writes one result object with `is_error` and `subtype`, no status;
  `--permission-mode` takes `acceptEdits` or `bypassPermissions`.
- `--allowedTools` entries are tool names or the one prefix form `Bash(<prefix>:*)`; each entry
  is single-quoted on a printed command line.
- Goldfish never spawn; builders never spawn; a foreman dispatches goldfish and nothing else.

**Packaging (the absorbed EGM tests, kept and amended; §15 names every amended test)**
- Frontmatter of every SKILL.md, in this order: `name`, `license`, `effects`, `effect_kinds` (only
  when `effects: external`), `disable-model-invocation` (only when typed), `description`. The
  frontmatter opens the file (the body is `text.split("---", 2)[2]`).
- Body ≤ 24,000 bytes. One absorbed skill is within 400 bytes of it (`egm-review` 23,626);
  absorption moves text into `references/`, never grows a body.
- One harness line in every SKILL.md, EGM's own, kept verbatim:

  ```
  In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.
  ```

  (EGM's second line, the Codex link, goes; the absorbed test keeps asserting the substring
  `${CLAUDE_PLUGIN_ROOT}/docs/claude.md`.)
- Every backticked `agents/…`, `resources/…`, `references/…` path in a skill or persona exists.
- Every skill folder carries `assets/icon.svg` (24×24 viewBox, a `<title>`, the two-colour
  palette, read from the SVG itself) and `test_scenarios.yaml` (`skill:` = folder name, non-empty
  `scenarios`, each with `scenario_id`, `eval_type`, `turns`).
- Reviewer adapters: `tools` exactly `[Read, Grep, Glob]`, `model: inherit`, `omitClaudeMd: true`,
  no `memory`, body reads `${CLAUDE_PLUGIN_ROOT}/agents/<id>.md`. The one non-reviewer adapter
  (`foreman`) has the exact tool set in §14.
- The packer forbids MCP (`mcpServers`, `mcp`, `apps`) and allows **exactly** these three hook
  files, nothing else under `hooks/`: `hooks/hooks.json` (one `SessionStart` entry),
  `hooks/run-hook.cmd`, `hooks/session-start`. The source `.claude-plugin/plugin.json` carries
  `"superegm": {"hook_sha256": "<sha256 of hooks/session-start>"}`; the packer refuses when the
  value differs from the file, and copies the manifest byte for byte as today.
- The packer's output is not committed; `prepare_release.py` runs it at release and the
  packaging tests run it into a temporary directory.
- Licences: `LICENSE` (Apache-2.0, EGM) and `LICENSE-MIT` (superpowers) both ship. Every Apache
  file changed from the fork carries `Modified by SuperEGM (gsVAM), 2026: <what>` in its header in
  the fork's own form; every file taken from superpowers gets `<!-- From superpowers 7.0.0 (MIT);
  modified by SuperEGM (gsVAM), 2026: <what>. -->` after the frontmatter when changed. README's
  **Licence** paragraph lists every modified file.

**Isolation**
- Every Claude goldfish and judge is dispatched through an adapter. `superegm review record` and
  `superegm judges record` store each dispatch as `clean` or `exposed to <what>`, as the
  dispatching session reports it from the adapter it used; an Astra lane dispatch is recorded with
  the runner's own isolation note.
- Headless sessions started by SuperEGM set `SUPEREGM_ROLE` to `builder` or `goldfish`, and
  `SUPEREGM_RUNCARD` to the run card they run under. The hook prints nothing when the role is
  `goldfish`.

**Liveness and destruction (EGM round-12 doctrine, binding)**
- A builder launch is **terminal** when its exit file exists (the launched command writes
  `<result-file>.exit` on any exit, so the helper reads the code) or when the owner's typed
  `/superegm:interrupt` recorded `interrupted`. An Astra review run is terminal when its
  `result.json` says `completed` or `failed`. A round is terminal in phase `posted`, or
  `collected` with `not run (…)`. Nothing else is terminal; silence proves nothing.
- Removing a worktree is a destructive decision and is never taken on a guess: `/superegm:clean`
  refuses while any launch or round of the unit is not terminal, and keeps what it cannot prove.
- A prepared round whose review never posted is collected as `not run (…)` and the next round
  number is prepared; a round is never re-prepared.

### 4.1 Risks and mitigations

| Risk | Impact | Mitigation | Unit |
| --- | --- | --- | --- |
| Runaway spend (6 goldfish × 5 rounds per artifact and per head; 3 judges × 5 rounds per decision) | a night costs more than it returns | the caps (a review is at its cap when its round count ≥ 5 + its `continue` rulings, and `continue` is ruled at most once; 5 judge rounds per decision) and `max_in_flight` (5) bound one phase; a phase never chains into the next | U04, U08, U10 |
| GitHub rate limits or half-finished writes | issues created twice, links missing | EGM's marker recovery and 3-retry rate-limit handling, kept; `verify` reads everything back | U07 |
| A builder dies without an exit file (hard kill) or exits without a PR | its unit stalls | the exit file is written by the shell on any ordinary exit; an exit without a PR or status comment is decision point 3; a hard kill leaves no exit file and the owner's `/superegm:interrupt` is terminal; every `deadline` rewrites the wave report, which lists every non-terminal launch | U09, U10 |
| Two foremen on one unit after a compaction | duplicate rounds, duplicate review posts | `foreman/<unit>.json.dispatch_id`, written by `foreman dispatch`; `prepare`, `collect`, `review post` require `--dispatch` to match | U10 |
| A builder pushes to the base branch or force-pushes | an undoable merge or a lost branch | `launch` refuses to start a wave unless the protection reads in §11 pass; the result is recorded in the wave card; the builder's allow-list has no merge or worktree command (lint) | U09 |
| The foreman merges or removes a worktree | the same | the foreman adapter's Bash cannot be pattern-restricted; its brief forbids both; accepted residual risk | U10 |
| Judges from one vendor only (Astra lane down) | less independent verdicts | `judges.min_vendors` (default 1, so a Claude-only panel may rule); the record says `degraded: true` whenever fewer than two vendors answered; the owner can set 2 to force a pause | U08 |
| A spec edit after a clean round or after approval | bytes nobody reviewed get frozen; bodies cite a stale hash | every round records the sha256 it reviewed; `approve-spec` refuses unless the spec's current sha256 equals the converged round's; `graph` refuses when it differs from the approval | U04, U05 |
| The claudex-loop runner's lane down (quota, network) | no second vendor | every lane use is optional and recorded `not run (<reason>)`; the every-reviewer-ran check excepts a `not run` lane | U04, U08 |
| CI absent or needing manual approval on a draft PR | rounds never start | EGM's `waiting-for-ci`/`no-ci` states; `status --wait` reports them; the wave report tells the owner | U09, U10 |

**Cost and timeline (estimate, not a promise).** One leavemealone phase: spec review 2–3 rounds
× 6 goldfish; plan review 2 rounds × 11 units × 3 goldfish; a wave of 5 builders × 2 rounds with 2
goldfish per head; two judge decisions × 3 judges × 2 rounds. About 150 subagent dispatches and
10 headless sessions. The self-build (§17) is five waves; at one wave a night it is one week.
The first mid-term exam is that build. It is filed and driven by hand by the elephant following
this spec's forms (its plans as issue bodies in the §9.1 layout, its rounds with the §8 loop run
by hand), since the tools that would run it are what it builds; if its unit plans do not fit the
body budget, or its first wave pauses the owner for anything other than merges more than twice,
the cut or the caps are wrong.

## 5. The workflow, end to end

| # | Phase | Typed? | Artifact | Gate | Record |
| --- | --- | --- | --- | --- | --- |
| 0 | Brainstorm | auto (reads and drafts only) | spec file in the repo | the owner's opt-in | none yet |
| 1 | Spec review | **typed** | review report | converged or ruled | review record; **approval record freezing the spec at a commit hash** |
| 2 | Plan | **typed** | the handoff plan with one TDD plan per unit; rendered issue bodies in the store | `graph` and `scan` pass | `handoff_units.json` with body hashes |
| 3 | Plan review | **typed** | review report per unit over the exact bytes | converged or ruled | review record per unit |
| 4 | File | **typed** | tracking issue, sub-issues, blocked-by links | dry run confirmed; `verify` reads back | filing receipt |
| 5 | Wave | **typed** | builders launched, foremen reviewing, draft PRs | per unit: head clean AND no regressions, or ruled | foreman state per unit; launch records; review comments on the PR; the wave report |
| 6 | Merge | **human** | merged PR | the owner | the merge itself |
| 7 | Integrate | **typed** | integration review of the spec against everything merged | nothing left to escalate | review record; handoff closed |

Rules that span phases:
- **The spec is frozen** by the approval record at a commit hash. Every issue body cites the spec
  path and that hash. A change to any section other than `## Units` reopens spec review and marks
  every unfiled plan stale; rows appended to `## Units` are re-approved by `approve-spec
  --amend-units` without a review round (§12). Filed units are unaffected, their bodies being
  frozen by hash already.
- **Render → scan → review → dry run → file.** Review reads the bytes the owner confirms. Gates
  are mechanical: `graph` refuses without an approval record matching the spec; `apply` refuses a
  body whose hash is not the one its converged review round recorded; `launch` refuses a unit
  without a filing receipt.
- **Dependency readiness means landed.** A unit enters a wave only when every unit it is blocked
  by, and every shared-file predecessor, has landed, never on a "clean" head.
- **The builder is always a fresh session.** Its brief is the issue body, the builder orders, the
  rulings on its issue and, from round 2, the foreman's reviews of its own branch. Never the
  planning elephant.
- **The unit graph is the last section of the spec.** The spec's last H2, after any numeric
  prefix, is `Units`; it lists units, interfaces, dependencies and sizes against the body budget,
  so spec review covers the cut. A Consumes line's producer must be a blocker of the consuming
  unit, directly or transitively. A shared file is a file two units edit that their blockers do
  not already order.
- **The review panel for an artifact is written into the run card before dispatch and stays
  fixed every round.** The first reviewer's angle is fixed per artifact kind: `design` for a spec,
  `readiness` for a plan, `change-review` for a PR head. Only the owner changes a panel, and only
  between reviews.
- **One convergence rule** for the three loops (spec, plan, PR head), implemented once (§8) and
  consumed by the other two: a round is **clean** when no high or medium finding is unsettled;
  the artifact is **converged** when a round is clean AND no finding in it is a regression of a
  prior round's fix AND every reviewer in the run card's panel ran (the Astra lane excepted when
  recorded `not run`). Lows never block. A review is **at its cap** when its round count ≥ 5 +
  its `continue` rulings; at the cap a ruling is required (§13.2) before any further round, and a
  ruling of `accept` makes the artifact converged (`converged: by ruling <id>`); `continue` may
  be ruled at most once per review. No review has a second kind of cap.

## 6. Entry: the hook, effects, typed and auto-invoked skills

**One hook.** `hooks/hooks.json` declares one `SessionStart` command hook (matcher
`startup|clear|compact`, `async: false`) running `hooks/run-hook.cmd session-start`, both scripts
taken from superpowers with three changes: the script reads `skills/using-superegm/SKILL.md`; the
wrapper line names `superegm:using-superegm`; and it exits 0 printing nothing when
`SUPEREGM_ROLE` is `goldfish`. The non-Claude output branches are removed; output is
`hookSpecificOutput.additionalContext` only. The injected text is the whole `using-superegm`
skill: superpowers' rule ("if there is even a 1% chance a skill applies, invoke it") rewritten
for SuperEGM's skill names, plus the phase rule below. Tests: run the script with the goldfish
role and assert empty stdout; a canary test greps every `content` string of
`tests/fixtures/goldfish_transcript.jsonl` (captured by the owner from one `superegm:readiness`
dispatch and committed before the build is filed) for the skill's first line and asserts no
match; the hash test compares the manifest value to the script. This is the single exception to
EGM's no-hooks rule; it is removable if description-only invocation is ever measured to fire as
reliably.

**Effects are declared and checked.** Every SKILL.md declares `effects: none | working-tree |
external`. An `external` skill also lists `effect_kinds`, a non-empty subset of `github-write`,
`remote-branch`, `start-session`, `state-store`, `destructive-local`. The packer and
`tests/unit/test_effects.py` refuse: a skill without `effects`; an `external` skill without
`effect_kinds`; an `external` skill that is not `disable-model-invocation: true`; a skill whose
§14 row says typed but whose frontmatter lacks `disable-model-invocation: true` (the test carries
the §14 table as data). Launching the claudex-loop runner is a `start-session` effect; opening a
run card is a `state-store` effect, so every `external` skill lists `state-store`.

**Typed vs auto-invoked.** The line is authorization and effect, not "writes".
- Typed only (`disable-model-invocation: true`): every `external` skill; the two review gates,
  because the file step checks their records; and the two EGM entry skills `draft` and
  `drift-report`, because each writes files on the owner's typed request and nothing in the
  workflow calls them.
- May be auto-invoked: every other skill. Working-tree skills that are not typed
  (`test-driven-development`, `systematic-debugging`, `verification-before-completion`) carry
  this sentence verbatim in their descriptions: "Only inside a SuperEGM builder session, for a
  filed unit on its branch, or for an owner-requested fix on a branch; never during brainstorm,
  spec or plan." A builder session is authorized by the wave run card it carries in
  `SUPEREGM_RUNCARD`; a filed unit or an owner request is authorized by the run card the elephant
  holds. Being inside a worktree authorizes nothing. `brainstorming` and `writing-skills` are
  working-tree and auto-invoked but exempt from the sentence: they run on the owner's request
  outside any unit. `verification-before-completion` never updates snapshots or fixtures.

**Every effect refuses without an open run card.** An `external` skill's first action is
`superegm runcard open`, and it passes the id to every helper subcommand that has an effect. A
card's `artifact` is the spec path for the spec-scoped skills (`review-spec`, `plan`,
`review-plan`, `file`, `wave`, `integrate`), the unit id for `interrupt` and `clean`, the
question file for `judges`, and the branch for `finishing-a-development-branch`. Each writing
subcommand declares the skills it serves in its own module (`require_runcard(args, skills)`),
which refuses unless the card is open, belongs to one of those skills, and either names the
subcommand's artifact or is the spec-scoped card of the handoff the named unit belongs to. A
**child card** (`--parent <id>`, opened by `judges open` and by `foreman dispatch`) is accepted
while its parent is open or `interrupted`. The skill's last action is `runcard close`. A card of
the same skill on the same artifact still open when that skill starts again is marked
`interrupted` by the new invocation; cards of other skills are left alone.

## 7. The store

One store per target repository. The helper is the only program that writes it, and every file
has exactly one writing invocation at a time:

| File | Writer |
| --- | --- |
| `state.json` | the elephant's typed skills (`plan`, `file`, `wave`, `integrate`), one at a time |
| `approvals/<spec-slug>.json` | `approve-spec` |
| `handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`, `handoff_bodies.md` | `plan` (`graph --plan <file>` copies the elephant's text in, then renders; `decide` re-renders one unit) |
| `reviews/<review-id>/…` | the invocation that opened that review |
| `judges/<id>/…` | the invocation that opened that panel |
| `runcards/<id>.json` | the skill that opened the card |
| `launches/<unit>.json`, `launches/<unit>_r<n>_prompt.md` | the elephant (`launch-builder`, `record-launch`, `interrupt --launch`) |
| `worktrees/<unit>/` | the elephant (`launch-builder`, `/superegm:clean`) |
| `foreman/<unit>.json`, `review/<unit>/pr<n>/` | the foreman dispatch whose `dispatch_id` the file records (`prepare`, `collect`, `review post`); the elephant's `foreman dispatch`, `interrupt --round` and `/superegm:clean` between dispatches |
| `wave_<n>_report.md` | `wave` (the driver loop) |
| `journal.md` | append-only, `O_APPEND`, one line per fact, any invocation |

All writes go through a temp file and `os.replace` (EGM's pattern, extracted as `atomic_write`).
No lock file.

- `.superegm/config.json` — committed in the target repo; created by `superegm init` (run by the
  first typed skill when it is missing) and committed by the owner before any approval, or by
  `approve-spec --leavemealone` (§8). Defaults written by `init`:

```json
{
  "repo": "<owner>/<name from git remote get-url origin>",
  "base": "main",
  "artifacts_dir": "/Users/<user>/.superegm/<owner>-<name>",
  "mode": "normal",
  "max_in_flight": 5,
  "labels": {"unit": "superegm:unit", "wave_prefix": "superegm:wave-",
             "handoff_prefix": "superegm:handoff-", "tracking": "superegm:tracking",
             "stopped": "superegm:stopped", "extra": []},
  "issue_template": null,
  "tracking_issue_title": "Build: <spec title>",
  "banned_terms": [], "fix_request_mention": null, "allowed_mentions": [],
  "reviewers": {"spec": ["design", "zoom-out", "readiness"],
                "plan": ["readiness", "set", "design"],
                "head": ["change-review"],
                "integrate": ["design"]},
  "astra": {"enabled": true, "model": "gpt-6-astra", "effort": "xhigh"},
  "judges": {"min_vendors": 1,
             "members": [{"id": "fable", "model": "fable", "effort": "max", "vendor": "anthropic", "lane": "adapter"},
                         {"id": "opus", "model": "opus", "effort": "max", "vendor": "anthropic", "lane": "adapter"},
                         {"id": "astra", "vendor": "openai", "lane": "claudex-loop"}]},
  "builder": {"profile_dir": "/Users/<user>/.claude-work", "model": "opus",
              "permission_mode": "acceptEdits",
              "allowed_tools": ["Read", "Edit", "Write", "Glob", "Grep",
                                "Bash(git add:*)", "Bash(git commit:*)", "Bash(git status:*)",
                                "Bash(git diff:*)", "Bash(git log:*)",
                                "Bash(git push origin superegm/:*)", "Bash(gh pr create:*)",
                                "Bash(gh issue comment:*)", "Bash(gh pr comment:*)"]}
}
```

  The Astra judge member reads its model and effort from `config.astra`. `builder.allowed_tools`
  has no test command by default; `launch-builder` adds, for that launch only, `Bash(<first
  word>:*)` for every command `run_commands` returns from the body (§9.1). Unknown keys stop.
- Under `artifacts_dir`, never committed:
  - `state.json` — EGM's handoff state with EGM's keys (`handoff_id, repo, remote, repo_root,
    plan, design, gate, gate_plan_sha256, gate_bodies_sha256, readiness, confirmed_sha256,
    confirmed_at, confirmed, dry_run, labels, tracking, units, links, verify, decisions, status`)
    plus `base_at_start` (the base commit when `file` first ran) and, per unit, `body_sha256`.
    EGM's `approval` and `pending_approval` keys go: `graph` reads `approvals/<spec-slug>.json`
    instead; `gate_unreviewed_diff` goes with `gate --accept`; `decisions[…].published` goes with
    the `--published` gate.
  - `runcards/<id>.json` — `skill, artifact, artifact_sha256, reviewers, tiering, mode, parent,
    opened_at, closed_at | interrupted_at, produced[]`.
  - `approvals/<spec-slug>.json` — `path, sha256, commit, runcard, review, approved_at,
    amended[], voided_by`. `<spec-slug>` is the spec file's stem (`2026-11-03-superegm-design`),
    from `spec_slug(path)`.
  - `handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`, `handoff_bodies.md` — EGM's files
    with the new sections; `handoff_units.json` carries `body_sha256` per unit.
  - `reviews/<review-id>/review.json` (`kind, artifact, reviewers, runcard, converged, rulings[]`)
    and `round-<n>.json` (`artifact_sha256` of the bytes reviewed; findings per reviewer: id,
    severity, location, `regression: yes|no`, disposition, ruling; `builder_contested[]` for a
    head; each dispatch's isolation, model and effort requested → effective; `what_ran`:
    `completed | not run (<reason>)`). The Markdown reports EGM writes today are kept beside
    them. Review ids are `spec-<spec-slug>`, `spec-<spec-slug>-integrate`, `plan-<unit>`,
    `head-<unit>`.
  - `launches/<unit>.json` — `launches[]` with `round, worktree, branch, started_at, status,
    result_file, prompt_sha256`; `status` ∈ `running | exited <code> | interrupted`.
  - `foreman/<unit>.json` — `dispatch_id`, rounds (phases `fetched → prepared → collected →
    posted`, plus `kept` and `cleaned` from `/superegm:clean`), decisions, rulings.
  - `worktrees/<unit>/` — the builder's worktree; `review/<unit>/pr<n>/` — the foreman's
    detached review worktree (EGM's, moved from `$TMPDIR/egm-wave/…` into the store).
  - `judges/<id>/question.md`, `round-<n>/<judge>.md`, `verdict.json`.
  - `wave_<n>_report.md` — per unit: state, head, rounds, open findings, every non-terminal
    launch, every head at `ci none|waiting`, every stopped unit and its unlanded dependants;
    rewritten on every `deadline` and at the end.
  - `journal.md` — one line per fact, rendered by the subcommand that wrote the fact: `Unit U03:
    filed #41`, `Review plan-U03 r2: clean, 1 regression — not converged`, `Ruling (judges j7,
    leavemealone): one more round`.

The SDD ledger `progress.md` and the `.superpowers/sdd/` workspace do not survive; their contents
live in `state.json`, `foreman/`, and `journal.md`. `.egm/handoff.json` becomes
`.superegm/config.json`.

## 8. Spec review (phase 1) and the one review loop

`/superegm:review-spec <spec-path> [--reviewers design,zoom-out,…] [--astra on|off] [--leavemealone]`

The review loop below is implemented once, in U04, as helper subcommands plus
`skills/review-spec/references/review_loop.md`, and is consumed unchanged by `review-plan` and
by the foreman. The helper records and judges; the dispatching session dispatches.

- `superegm review open --kind spec|plan|head|integrate --artifact <path or unit id>
  [--sha256 <hex>] --reviewers a,b,c --runcard <id>` records the review id (`spec-<spec-slug>`,
  `plan-<unit>`, `head-<unit>`, or `spec-<spec-slug>-integrate` for kind `integrate`, which is
  otherwise kind `spec`), the panel (1–6 reviewer ids from `design`, `zoom-out`, `comprehension`,
  `readiness`, `structural`, `style`, `codebase-details`, `change-review`, `set`; the kind's fixed
  first reviewer must be first) and the Astra lane state (`astra` is added to the panel for kinds
  `spec`, `plan` and `integrate` when `config.astra.enabled` and the runner is installed). The
  panel cannot change after this. Later rounds review the artifact's **current** bytes; each
  `round-<n>.json` records the sha256 it reviewed: for kinds `spec` and `integrate` the helper
  hashes the file; for `plan` and `head` the caller passes `--sha256 <hex>` (the `body_sha256`,
  or the head commit) to `review open` and `review record`.
- Each round the dispatching session dispatches the whole panel **concurrently** through the
  adapters, each goldfish receiving only the artifact, the standards the kind names, and from
  round 2 the prior round's report with the fixes marked; for kinds `spec`, `plan` and
  `integrate` the Astra lane runs alongside through the runner's `review` mode, launched by the
  elephant from the main conversation, fresh in round 1 and resumed after. The dispatching
  session records each reviewer, the lane included, with `superegm review record --review <id>
  --round <n> [--sha256 <hex>] --reviewer <id> --findings <file> --isolation
  clean|exposed:<what> --model <requested>:<effective> --effort <requested>:<effective>`, or
  `--not-run "<reason>"` when the dispatch did not complete. A reviewer with no findings is
  recorded with an empty file; a failed dispatch is never recorded as one. The Astra lane is
  never retried within a round and is stopped for the review after two incomplete runs (EGM's
  rule). The findings file holds one finding per line:

  ```
  <reviewer>-<round>-<n> | high|medium|low | <location> | regression: yes|no | <claim>
  ```

  The helper dedups on `<location>` plus `<claim>` and keeps the first id.
- Dispositions are `fixed | contested | declined | escalated | fix-design`, written by
  `superegm review settle --review <id> --finding <fid> --disposition <d> --runcard <id>
  [--owner | --judges <judges-id>]`. For a high or medium `contested` or `declined` the helper
  refuses without `--owner` in normal mode and without `--judges` in leavemealone-mode; the
  elephant never settles one alone (anti-goal 6). `escalated` means moved to a new unit or a
  decision point, and is settled. `fix-design` means the defect is in the spec.
- `superegm review status --review <id>` prints `round <n>: <clean|not clean>, regressions <k>,
  converged <yes|no|by ruling>, cap <yes|no>` and the trend line, and exits 0 when converged, 2
  at the cap without an `accept` or `stop` ruling, 4 when any finding is `fix-design`, 3
  otherwise. The cap predicate lives here alone (§5); every other subcommand and every skill asks
  `review status`.
- Between rounds the elephant fixes the artifact. Doctrine: change the thing, not the round. If
  two consecutive rounds regress on the same area, the next fix is a deletion, a narrowed contract
  or a smaller surface, not a patch, and the journal says what was removed.
- **At the cap** (exit 2) the skill requests a ruling (§13.2 point 2): for kinds `spec`, `plan`
  and `integrate`, continue one bounded round / accept the remainder / stop; for kind `head`, one
  more round / stop. `superegm review rule --review <id> --ruling continue|accept|stop [--owner |
  --judges <judges-id>]` records it, refuses `accept` for kind `head`, and refuses a second
  `continue` on the same review; `accept` sets `converged: by ruling`; `continue` raises the cap
  by one round. No further round starts while `review status` exits 2.
- Model tiering: panel goldfish run on `SUPEREGM_GOLDFISH_MODEL` at `SUPEREGM_GOLDFISH_EFFORT`
  (EGM's rules renamed; default `inherit`, never passed as a value); judges use their configured
  model and effort; builders use `config.builder`. The run card shows requested → effective.

Spec review specifics:
- `review-spec` opens a run card and the review `spec-<spec-slug>` with `config.reviewers.spec`
  unless `--reviewers` is given; `design` is first.
- On convergence, `superegm approve-spec --spec <path> --runcard <id> [--leavemealone]` (EGM's
  `approve` with its heading check replaced): the spec must be tracked, the tree clean, HEAD must
  contain the spec at its sha256, that sha256 must equal the one the converged round recorded,
  and the spec's last H2 must read `Units` after any numeric prefix. In normal mode the owner is
  asked to approve. In leavemealone-mode the converged review record is the approval, and
  `approve-spec` first commits the spec and `.superegm/config.json` with the message
  `superegm: approve <spec-slug> at review <id>` so the clean-tree check can pass without a human.
  The record freezes `commit` and `sha256`. `superegm approve-spec --void --review <id>` sets
  `voided_by` when a `fix-design` finding is recorded; `graph` refuses a voided approval.

## 9. Plan (phase 2) and plan review (phase 3)

### 9.1 The plan is the issue body
`/superegm:plan <spec-path>` opens a run card, then `superegm graph` refuses unless an approval
record matches the spec's current sha256. The elephant composes the plan text in the file
`state.json.plan` names (EGM's layout: title, `Design:` line, `## 1. Issue template`,
`## 2. Units`), one `### U<nn>: <title>` section per row of the spec's `## Units` that is not yet
filed, and runs `superegm graph --plan <file>` (copies the text into the store as
`handoff_plan.md`, parses, derives waves, renders bodies, hashes them) then `superegm scan`.
Filed units are never re-rendered; their bodies and hashes stay as filed. Nothing is committed
under `docs/…/plans`; the rendered bytes live in the store.

Each unit section carries EGM's fields and the superpowers additions:

| Field | Rule |
| --- | --- |
| Objective | one sentence |
| Scope paths | `` `path` (create\|modify\|delete) ``, comma-separated; a path may be a directory (`` `skills/` (create) ``) |
| Design range | `` `path:start-end (heading)` `` into the frozen spec |
| Blocked by | `none` or unit ids |
| Shared files | `none` or `` `path`: after U01, before U05 `` items; a shared file is one two units edit that their blockers do not already order |
| Risk | `low\|medium\|high: reason` |
| Size | `S\|M\|L` by scope-path count (as a guide, `L` is about twenty Step groups, the most a 48 KB body holds) |
| **Interfaces** | `Consumes:` and `Produces:` lines, one item per line (grammar below) |
| Definition of done | numbered items; item 1 is always the sentence `The test for each Step was committed before its implementation (checked by superegm tdd-order)`; every other item is one of ``Run `<command>` — <what passing means>``, ``Exists `<path>` ``, or `CI green on the head`; only `Run` items are commands |
| **Steps** | numbered groups of five lines (grammar below); a rule family (the three Produces forms, the placeholder list, the DoD item forms) may be one Step whose test is parametrized |
| Decide before build | `- none` or `- D<n> <question> owner: <owner>; default: <default>; blocking: yes\|no` |

Grammar (each line is one `scan` rule, each with a test):
- `Produces: <name>(<params>) -> <type>` for a Python interface, or `Produces: superegm <sub>
  <flags> → <stdout shape>; exit <codes>` for a helper subcommand, or `Produces: <file> key
  <path>` for a store field. Matching is on `<name>` (the identifier before `(`), the subcommand
  words, or the key path.
- `Consumes: <name> (U04)` — the same name form plus the producing unit in parentheses; `scan`
  refuses a Consumes whose name no sibling's Produces defines, and a producing unit that is not a
  direct or transitive blocker.
- A Step group (the inner fence is the test code):

````
3. Write the failing test `test_body_over_48kb_refused` in `tests/unit/test_plan_scan.py`:
   ```python
   def test_body_over_48kb_refused(world): ...
   ```
   Run `pytest tests/unit/test_plan_scan.py::test_body_over_48kb_refused -q`; expected: FAIL (`unknown rule`).
   Implement `check_body_size(body: str) -> None` in `skills/plan/scripts/superegm/scan.py`.
   Run the same command; expected: PASS. Commit `test(S3): …` then `feat(S3): …`.
````

  Line 1 carries the test path in its second backtick span; line 4 is ``Run `<command>`;
  expected: FAIL (<reason>)`` and carries the Step's one command; line 5 carries the
  implementation path in its last backtick span; line 6 is `Run the same command; expected: PASS.
  Commit …` and names no command. Commit subjects carry the Step number as `test(S<n>)` and
  `feat(S<n>)`. The two parsers of these forms are `run_commands(body) -> list[str]` (every DoD
  `Run` item and every Step line-4 command) and `step_paths(body) -> list[tuple[str, str]]` in
  `superegm/body.py`; `scan`, `launch-builder` and `tdd-order` call them and nothing else parses
  a body (anti-goal 1).
- `## Review focus` lines: ``- U06: <input or failure mode> — <expected behaviour>; pinned by
  `<test name>` ``; the test name must appear in the owning unit's Steps.
- `## Global constraints`: one line each, exact values; rendered verbatim into every body.
- A `Decide before build` item with `blocking: yes` must be answered before the body can pass
  `scan`: `superegm decide --unit U07 --decision D1 (--answer "<text>" | --default)` (the
  owner's, or the judges' through §13.2 point 3) rewrites the line in the file `state.json.plan`
  names, re-runs `graph --plan` on it and re-renders that unit's body, `--default` keeping the
  default and setting `blocking: no`; once the unit is filed it also posts the answer itself as
  one issue comment headed `**Decision D<n>:**` (EGM's `--published` second step and its
  `published` gate go).

The rendered body uses this fixed layout, the first three sections fitting one phone screen:

```
<!-- superegm:handoff=<id> unit=U07 spec=<spec sha256> -->
# U07 — <title>
Spec: `docs/specs/2026-11-03-superegm-design.md` @ <sha7> · `<path:start-end (heading)>`

## Objective
## Interfaces
## Definition of done
## Global constraints
## Review focus (this unit)
## Steps
## Decide before build
## Scope, order and risk
Scope: `skills/plan/scripts/superegm/scan.py` (create), … · Blocked by: #<U04>, #<U06> · Shared files: … · Risk: … · Size: M
Branch: `superegm/<handoff-id>/U07` · Part of #<tracking>
```

Rules `graph` and `scan` enforce (each a test; `graph` owns plan-shape rules, `scan` owns body
rules; there is no third checker):
- Body ≤ 49,152 bytes; a larger unit is refused with "split it".
- Numbered lists only. Never `- [ ]`: ticking edits the body and breaks byte-identity. EGM's
  default issue template is replaced by the layout above (its DoD was a checkbox list), and
  EGM's `MARKER_RE` is updated to the marker line above.
- **Byte identity, as EGM does it today.** `body_sha256` and the write-list hash the dry run
  confirms cover the rendered body with EGM's placeholders `#<U04>` and `#<tracking>`; `apply`
  re-checks that hash, creates issues in blocked-by order and rewrites the placeholders to `#<n>`
  as it goes (EGM's `fill_numbers`); `verify` re-substitutes the rendered body the same way and
  compares normalised text (CRLF and trailing whitespace stripped) as EGM's `verify` does.
  Blocked-by is also an issue relationship, set by `apply` as today.
- No placeholders: `TBD`, `handle edge cases`, `add appropriate validation`, `write tests for
  the above`, or a Consumes name no Produces line defines.
- Global constraints and review focus present in every body; every review-focus line's test
  appears in its owning unit's Steps; every Step group has both paths and its line-4 command.
- The marker line's spec sha256 equals the approval's; `graph` refuses otherwise.
- No cycles in blocked-by; no shared-file chain that contradicts the blockers (EGM's `graph`).
- The raw-text mention and banned-term scan with `allowed_mentions` (EGM's `scan`).

### 9.2 Plan review
`/superegm:review-plan <spec-path> [--units U01,U02] [--reviewers readiness,set,…] [--leavemealone]`

- One review per unit, id `plan-<unit>`, kind `plan`, over the unit's current rendered bytes
  (each round records the `body_sha256` it reviewed), `readiness` first. A re-render between
  rounds is a new round of the same review, so regressions are marked and the cap holds; `apply`
  requires a body's `body_sha256` to equal the one its converged round recorded. Each
  `review-plan` round dispatches every unfiled unit that is not converged or whose current
  `body_sha256` differs from its converged round's; a `set` finding naming a converged unit
  reopens it as a new round.
- The reviewer id `set` is the readiness persona dispatched **once per `review-plan` round**
  over every unfiled body, for interface consistency and the cut; its findings file is recorded
  into every unit's review for that round; a finding whose location names a unit is unsettled
  only in that unit's record, one naming none counts in all. Any other reviewer receives one
  body, the approved spec at its hash, and every sibling's Interfaces block. Units run
  **concurrently**, and the goldfish within a unit's panel concurrently.
- The standard is `resources/document_standards/handoff-standard.md` (EGM's seven questions)
  plus three: 8, interfaces present and consistent; 9, every Step group complete and DoD item 1
  present; 10, global constraints and review focus present. The no-placeholders list is a gate
  criterion. A `fix-design` disposition makes `review status` exit 4; the skill then runs
  `approve-spec --void` and the spec returns to spec review.
- Readiness questions ("what would a builder still ask?") are findings of the `readiness`
  reviewer: a blocking question is `high`. There is no second loop and no second cap.

## 10. File (phase 4)

`/superegm:file <spec-path>` is EGM's handoff filing (`gate` → `dry-run` → `apply --yes` →
`verify`) with these changes:
- `gate --pass` requires `review status` exit 0 for every unit it passes and the unit's
  `body_sha256` to equal its converged round's; `apply` refuses otherwise. `gate --accept` goes.
- The dry run and the "Create" confirmation are against the same write-list hash `apply`
  re-checks (§9.1). In normal mode the owner confirms; in leavemealone-mode the confirmation is
  mechanical (the hashes match converged records) and the journal says `Create: automatic
  (leavemealone)`.
- `verify` reads every body back and compares as §9.1 says; `state.json.base_at_start` is
  recorded on the first `apply`.
- Idempotent filing with marker recovery stays, re-pointed at the new marker: a rerun after a
  crash finds its issues by the marker line and continues. Labels are `superegm:unit`,
  `superegm:wave-<n>`, `superegm:handoff-<id>`, `superegm:tracking`, `superegm:stopped`.
- Deviations during the build go in **comments**, never edits to the body. The builder posts
  `gh issue comment <n> --body "**Deviation (<kind>):** <text>"` with kind `interface | dod |
  test | other`, as the builder orders say (U09), and stops with status BLOCKED when the kind is
  not `other`. The foreman's review package carries the issue's comments; `collect` records a
  deviation of kind `interface`, `dod` or `test` without a later `**Ruling:**` reply as a high
  finding of reviewer `foreman`, so the head cannot count as clean until the ruling is posted.

## 11. Wave, foreman, builder (phase 5)

`/superegm:wave <spec-path> [--leavemealone]`

**Preconditions.** `superegm launch` (EGM's readiness guards, plus the branch-protection reads)
refuses to start a wave unless the repository's protection passes, in one of two forms, and
records which it found in the wave's run card:
- classic: `GET repos/O/R/branches/<base>/protection` has `required_pull_request_reviews`
  present, `enforce_admins.enabled: true`, `allow_force_pushes.enabled: false` and
  `allow_deletions.enabled: false`, and the GraphQL `branchProtectionRules` list has a rule whose
  `pattern` covers `superegm/**` with `allowsForcePushes: false` and `allowsDeletions: false`;
- rulesets: `GET repos/O/R/rulesets` then each `active` ruleset by id; one must apply a
  `pull_request` rule to the base branch with `bypass_actors: []`, and one must apply
  `non_fast_forward` and `deletion` rules whose `conditions.ref_name.include` covers
  `refs/heads/superegm/**`.
`launch` also skips units labelled `superegm:stopped` (the owner removes the label to resume).

**The driver loop** runs in the main conversation and is the only long-lived actor:
1. `superegm launch` marks the ready units up to `max_in_flight`.
2. For each marked unit the elephant runs `launch-builder` and starts the printed command in the
   background.
3. `superegm status --wait 1500 --runcard <id>` blocks (EGM's `status --wait`, which reads only
   and saves once on return, extended to read `launches/*.json` exit files and each unit's issue
   and PR conversation comments on every pass) and returns **every unreported change since the
   last save, oldest first, one event line each**: `builder-exit U07 <code>`, `head U07 pr 412
   <sha7> ci <green|red|waiting|none>`, `blocked U07`, `landed U07`; it returns at once while
   unreported events remain and `deadline` alone when none arrived within the wait. Only the
   reported units' fingerprints are saved.
4. The elephant acts on every returned line, in order, before calling step 3 again:
   - `builder-exit`: records the code on the launch; if the unit has no PR and no `**Builder
     status:**` comment on the issue or the PR, the unit is treated as `blocked`.
   - `head` with CI `green` or `red`: for every such line in the batch the elephant runs
     `superegm foreman dispatch --unit U07 --runcard <id>` (opens `head-U07` with
     `config.reviewers.head` under the wave card on the unit's first dispatch, writes a fresh
     `dispatch_id`, opens the child card, prints both) and dispatches all the foremen
     `foreman-U07-<dispatch_id>` in **one message, in the foreground**. The foreman's return
     word is the channel: `clean` → journals `U07 awaiting merge`; `revise` → launches the
     round-(n+1) builder; `contested: <ids>` → takes decision point 1, records it with `review
     settle --judges` or `--owner`, posts `**Ruling:** <fid> finding upheld (fix it) | finding
     overruled — <reason>` on the issue, then acts on `review status` (0 → `awaiting merge`; 2 →
     as `cap-reached`; else launches the next builder); `cap-reached` → takes decision point 2
     (`continue` → launches the next builder; `stop` → as the foreman's cap bullet says);
     `target-moved` or `head-moved` → waits for the next `head`; `error` → re-dispatches the
     foreman once, and on a second `error` treats the unit as `blocked`. Before any launch the
     elephant checks `review status --review head-U07`: exit 2 is handled as `cap-reached`, and a
     refusal of `launch-builder` for a non-terminal launch is retried after that unit's next
     `builder-exit`. `head` with CI `waiting` or `none`: nothing.
   - `blocked`: takes decision point 3, posts the ruling as `**Ruling:**` on the issue, and
     launches the next builder, or stops the unit as the foreman's cap bullet says.
   - `landed`: goes to step 1.
   - `deadline`: rewrites `wave_<n>_report.md`; for every in-flight unit whose current head has
     no terminal round, dispatches a foreman as for `head`; then step 3.
5. The loop ends when every in-flight unit is clean, landed or stopped; it writes
   `wave_<n>_report.md` and closes the run card. The skill is re-typeable: on entry it reads
   `launches/*.json` and `foreman/*.json`; for every unit whose last round is `posted` and not
   followed by a launch, a ruling or an `awaiting merge` journal line, it runs `review status
   --review head-<unit>` and acts as step 4 would (0 → `awaiting merge`; 2 → `cap-reached`; 3 →
   `contested` when `builder_contested[]` meets an unsettled finding, else `revise`); then step 3.

**Launching a builder** (`superegm launch-builder --unit U07 --round <n> --runcard <id>`):
1. refuses unless the unit is marked by `launch` and every earlier launch of the unit is terminal;
2. round 1: creates `worktrees/U07` from `base` on branch `superegm/<handoff-id>/U07`; round
   n ≥ 2: reuses the same worktree and branch, fetching the branch tip;
3. reads the issue body by number, refuses when it differs from `unit_U07.md` filled and
   normalised as `verify` compares, and writes the prompt file `launches/U07_r<n>_prompt.md`: the
   issue body, then `references/builder_orders.md`, then every issue comment headed
   `**Decision D<n>:**`, `**Deviation (<kind>):**` or `**Ruling:**`, then for n ≥ 2 the
   foreman's review comments on this PR verbatim, and nothing else; records its sha256;
4. prints the one command line the elephant runs in the background from the main conversation,
   every allow-list entry single-quoted: `cd <worktree> && CLAUDE_CONFIG_DIR=<builder.profile_dir>
   SUPEREGM_ROLE=builder SUPEREGM_RUNCARD=<id> claude -p "$(cat <prompt-file>)" --model
   <builder.model> --permission-mode <builder.permission_mode> --allowedTools <entries plus
   Bash(<first word>:*) for every command run_commands returns> --output-format json >
   <result-file>; echo $? > <result-file>.exit`;
5. records the launch through `record-launch`.
`launch-builder` refuses an `allowed_tools` containing `Agent` or bare `Bash` (a lint; the branch
protection in **Preconditions** is the fence).

The builder orders (`references/builder_orders.md`, absorbing superpowers' implementer prompt and
the discipline of its receiving-code-review skill): follow the Steps in order; test first, one
`test(S<n>)` commit then one `feat(S<n>)` commit per Step; run every DoD `Run` command and paste
the output in the PR body; push the branch; open a **draft** PR whose body is the unit id, the
DoD results and `Closes #<issue>` (from round 2 the PR exists: push and update its body instead);
when a Step cannot be done as written, post the `**Deviation (<kind>):**` comment of §10 on the
issue; from round 2, read each review finding, verify it against the code before changing
anything, then reply on the PR `**Reply <fid>:** fixed | contested — <reason>`, and push; a
`**Ruling:**` that says `finding upheld` means fix it, `finding overruled` means leave it; finish
with one comment `**Builder status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT` on the
PR, or on the issue when no PR exists, and stop. Wherever an absorbed skill says "ask your human
partner", a builder writes the question in that comment with status BLOCKED and stops. A builder
never spawns, never touches files outside its scope paths, never merges.

**The foreman** is a named subagent (`name: foreman-U07-<dispatch_id>`) dispatched through the
`superegm:foreman` adapter (`omitClaudeMd: true`; tools `[Agent, Bash, Read, Grep, Glob]`;
`model: inherit`) in the foreground, with `references/foreman_brief.md`, the unit id, the wave
run card id, its child card and its `dispatch_id`. It runs **one round** and returns one word plus
one line. Its contract, binding:
- `prepare --dispatch <id>` (EGM's: fetch `refs/superegm/pr/<n>` and `refs/superegm/base/<n>`,
  detached review worktree, the diff, the CI JSON, plus `pr_body.md` and `comments.md` holding the
  PR's comments and the issue's comments since the last posted round).
- Dispatches the head's panel (`change-review` first; 1–6, fixed in the run card)
  **concurrently**, without `name`, each receiving the unit file, the frozen spec range, the diff,
  the CI file, `pr_body.md`, `comments.md` and the worktree path; records each with `review
  record --sha256 <head>`; runs `collect --dispatch <id>`, which records CI not green, a
  `tdd-order` failure and an unruled deviation each as a high finding of reviewer `foreman`, and
  reads `**Reply <fid>:** contested` into `builder_contested[]`; posts through `review post`;
  then returns the word `review status` implies: `clean` on exit 0 (so **Clean** and **No
  regressions** below both hold); `cap-reached` on exit 2; otherwise `contested: <ids>` when
  `builder_contested[]` meets an unsettled high or medium, else `revise`. Before `prepare` it
  returns `target-moved` when the base moved and the merge-base diff is unchanged (no round
  cost), `head-moved` when the PR tip changed since the `head` event (no round cost), and
  `error` after recording the round `collected (not run (error: <reason>))` when a step failed.
- **Clean** = CI green on this head AND `change-review` reports every DoD item met from the
  diff, the CI file and the DoD output in `pr_body.md` AND no unsettled high or medium AND
  `superegm tdd-order --unit U07 --dispatch <id>` passed (over the PR's commits in order, for
  each Step n a commit subject `test(Sn)` touching that Step's test path precedes a commit
  subject `feat(Sn)` touching its implementation path, and every `test(…)` commit touches only
  test paths) AND no unruled deviation of kind `interface`, `dod` or `test`. All of these are
  findings in the round record, so `review status` exit 0 is the one Clean rule.
- **No regressions** = CI's suite is green on the head (the merge base's suite included) AND no
  finding is a regression of a prior round's fix.
- A rebase-only head (same tree against a new base) costs no round (new in SuperEGM; EGM's
  `target-moved` covers only a base move under an unchanged head).
- `superegm review post --unit U07 --round <n> --dispatch <id> --runcard <child>` is EGM's
  posting guard moved from skill prose into the helper: it scans the comment text, re-reads the
  target triple, re-checks the merge base, posts bound to the reviewed commit through the
  pull-request reviews API, never `--approve` or `--request-changes`, checks the echoed
  `commit_id`, and records `posted`.
- At the cap (`review status` exit 2) it returns `cap-reached`; the elephant requests the ruling
  (§13.2 point 2): **one more round** (once) or **stop**. `stop` labels the issue
  `superegm:stopped`, leaves it open, keeps the branch, journals it, and lists it in the wave
  report with its unlanded dependants; the owner lands it by hand (finish, merge), or closes it
  together with its unlanded dependants and re-appends what is still wanted (§12).
- It never merges, never edits the owner's working tree, never removes a worktree, never
  launches a session, never convenes the judges, never infers that a builder died.

**Landing.** A unit has landed when its issue is closed as completed (the PR body's `Closes
#<issue>` does this on merge) and the watched PR is merged by the owner. `status --wait` reports
it; landing makes dependants ready. `/superegm:clean --unit U07` (helper `clean`, EGM's `prepare
--clean` looped over the unit's rounds and its builder worktree) is typed, `destructive-local`,
refuses while any launch or round is not terminal, and keeps what it cannot prove.
`/superegm:interrupt --unit U07 (--launch <n> | --round <n>)` is typed and records `interrupted`
on a launch, or marks a prepared round `collected (not run (interrupted: owner))`; an owner's
decision is not a guess.

## 12. Merge and integration (phases 6–7)

- **Merge is human.** The absorbed `finishing-a-development-branch` offers two options: push and
  open a pull request; keep the branch as-is. Discard stays behind the typed word `discard`.
  "Merge back locally" is removed. A forced push is never offered.
- `/superegm:integrate <spec-path>` runs after every unit has landed or been closed by the owner
  (who closes a stopped unit's unlanded dependants with it): one round of the review
  `spec-<spec-slug>-integrate` (kind `integrate`, `config.reviewers.integrate`) of the frozen spec
  against `git diff <base_at_start>..<base>` of the target repo. Each high or medium is settled
  `escalated` with a new unit's id: the elephant appends rows to the spec's `## Units` with the
  note `(from integrate, review <id>)`, runs `superegm approve-spec --amend-units` (which
  re-records the approval at the new commit without a review round, refusing if any line outside
  `## Units` changed), then `plan` → `review-plan` → `file` → `wave` for the new units only. The
  owner uses the same path by hand to re-append what a stopped unit still owed. The handoff
  closes when an integrate round has nothing to escalate; the close is recorded in `state.json`
  and the journal.

## 13. The judge panel and leavemealone-mode

### 13.1 The judge panel
`/superegm:judges <question.md> [--evidence <paths…>]`

- Typed; advisory by default. The helper never dispatches a judge: `superegm judges open
  --question <file> --evidence <paths> --runcard <id> [--parent <id>]` records the question
  file's sha256, the evidence list and the judges from `config.judges.members`, and prints the
  panel id; the dispatching session (the elephant) dispatches the Claude judges through the
  `superegm:judge` adapter and the Astra judge through the runner, and records each with
  `superegm judges record --panel <id> --round <n> --judge <id> --verdict <file> --isolation …`.
- The question file's grammar: `## Q<n> <question>` followed by two or more `- (a) <option>`
  lines; judges answer by option id and may add a short reason and "what would change my mind".
  `superegm judges diff --panel <id> --round <n>` compares option ids and writes the neutral list
  of where positions differ; no one adds arguments between rounds.
- Three models from two vendors, each a goldfish through the `superegm:judge` adapter
  (`omitClaudeMd: true`, tools `[Read, Grep, Glob]`, `model: inherit`) with a per-dispatch model
  override (`fable` at max, `opus` at max), plus GPT-6 Astra through the claudex-loop runner's
  `review` mode on the question file when the runner is installed and reachable.
- Every judge reads only the question file and the listed evidence. The Astra judge runs with
  `SUPEREGM_ROLE=goldfish`.
- Round 1 is independent. From round 2 each judge receives every prior verdict verbatim plus the
  neutral diff. Judges run **concurrently**.
- `superegm judges verdict --panel <id>` computes convergence (the same option id on every
  question), writes `judges/<id>/verdict.json` (each judge's model, vendor, effort, `clean |
  exposed to <what>`, option per question per round; `degraded: true` when fewer than two
  vendors answered; `converged`), and exits 0 converged / 2 not. Rounds continue until
  convergence or the cap of 5, then the owner is paused with the record. When the runner is
  absent or the lane is down, the panel runs Claude-only and the record says so.
- The judge panel never changes a review panel, a reviewer set, or a run card's tiering.

### 13.2 Decision points and leavemealone-mode
These are the decision points of the workflow, and this list is the only one:
1. contesting or declining a high or medium finding in any review, including a builder's
   `contested` reply on a PR head;
2. a review at its cap: for a spec, plan or integrate review, continue one bounded round (once)
   / accept the remainder / stop; for a head, one more round (once) / stop;
3. an open question the elephant cannot answer from the frozen spec: a `blocking: yes` decision
   during `plan`; a builder's `BLOCKED` / `NEEDS_CONTEXT` status, including a deviation of kind
   `interface`, `dod` or `test`; a builder that exited without a PR or a status comment; a
   foreman that returned `error` twice (ruling: relaunch, or stop the unit);
4. the owner's approval of a converged spec in normal mode, and "Create" in normal mode.

In normal mode every point pauses for the owner. In leavemealone-mode (`--leavemealone` or
`config.mode`), at points 1–3 the skill runs `superegm judges question (--review <id> --finding
<fid> | --review <id> --cap | --unit <U> --decision D<n> | --unit <U> --blocked <comment-id>) →
<path>` to render the question file from the record, runs `judges open --parent <its run
card>`, dispatches the judges as §13.1 says, and applies a converged verdict (subject to
`min_vendors`) through `review settle --judges`, `review rule --judges`, `decide`, or a
`**Ruling:**` comment, journaled as `Ruling (judges <id>, leavemealone): …` so the owner can read
and overturn it; a non-converged verdict pauses the owner with the record. A ruling that upholds
a deviation of kind `interface` is also posted as `**Ruling:**` on every filed issue whose body
consumes that name, so each of those builders is briefed. Point 4 is mechanical in
leavemealone-mode (§8, §10): a converged record is the approval, and matching hashes are the
confirmation. A foreman never convenes the judges: it returns `cap-reached` or `contested` and
the elephant does. **Merge is excluded**: no mode makes a machine merge.

## 14. Skill and adapter disposition

Naming: adapter file `.claude-plugin/agents/<id>.md`, frontmatter `name: <id>`, persona
`agents/<id>.md`, invoked `superegm:<id>`, reviewer list entry `<id>`. "The dispatcher text" below
means the hook-injected `using-superegm` skill.

| Source | In SuperEGM as | Effects | Invocation | Caller | Change |
| --- | --- | --- | --- | --- | --- |
| brainstorming (sp) | `brainstorming` | working-tree | auto | owner, phase 0 | writes `docs/specs/YYYY-MM-DD-<topic>-design.md` ending in `## Units`; the gate's next step is `/superegm:review-spec`; the builder check and the visual companion removed |
| egm-draft (egm) | `draft` | working-tree | typed | owner, phase 0 | "draft a spec from a brief when brainstorming was skipped"; `references/design_doc.md` template ends in `## Units` |
| egm-review + egm-review-loop + egm-resolve (egm) | `review-spec` (+ `references/review_loop.md`, `references/resolve.md`) | external: state-store, start-session | typed | owner, phase 1 | §8; the stage skills become references; upstream's "max 1 re-audit" goes; owns the Astra review lane |
| egm-handoff planning half + writing-plans (sp) | `plan` | external: state-store, start-session | typed | owner, phase 2 | §9.1; `start-session` for the judges at point 3 |
| new | `review-plan` | external: state-store, start-session | typed | owner, phase 3 | §9.2 |
| egm-handoff filing half | `file` | external: github-write, state-store | typed | owner, phase 4 | §10 |
| egm-wave + SDD implementer prompt (sp) | `wave` (+ `references/foreman_brief.md`, `references/builder_orders.md`) | external: start-session, github-write, remote-branch, state-store | typed | owner, phase 5 | §11; Claude goldfish only on heads |
| new | `interrupt` | external: state-store | typed | owner, phase 5 | §11 |
| new | `clean` | external: destructive-local, state-store | typed | owner, phase 5 | §11 |
| finishing-a-development-branch (sp) | same name | external: github-write, remote-branch, state-store | typed | owner, outside a wave | no local merge, no forced push |
| new | `integrate` | external: state-store, start-session | typed | owner, phase 7 | §12 |
| new | `judges` | external: start-session, state-store | typed | owner (leavemealone skills call the `judges` helper subcommands directly, §13.2) | §13 |
| test-driven-development, systematic-debugging, verification-before-completion (sp) | same names | working-tree | auto, phase-gated | builder sessions; owner fixes | the phase sentence; "discuss with your partner after 3 failed fixes" becomes a BLOCKED comment for a builder |
| writing-skills (sp) | same name | working-tree | auto | owner, maintaining this plugin | |
| using-superpowers (sp) | `using-superegm` | none | hook + auto | every elephant and builder session | the dispatcher text; one platform reference, `references/claude-code-tools.md` |
| egm-drift-report (egm) | `drift-report` | working-tree | typed | owner, any time | writes `<date>_DRIFT_REPORT.md` |
| egm-bootstrap (egm) | **retired** | | | | no caller; its orchestrator adapter wrote and spawned |
| executing-plans, subagent-driven-development (sp) | **retired** | | | | the wave is the one execution path; the implementer prompt's statuses and the receiving-code-review discipline live in `builder_orders.md`; `task-brief`, `sdd-workspace`, `review-package` go (EGM's `prepare` produces the diff and CI file; `tdd-order` reads the PR's commits itself) |
| requesting-code-review, receiving-code-review, dispatching-parallel-agents, using-git-worktrees, diagnosing-superpowers (sp) | **retired** | | | | no caller in the workflow: the foreman reviews heads, `launch-builder` makes worktrees, builders never spawn |
| egm-brainstorm (egm) | **retired** | | | | superpowers' brainstorming replaces it |

Adapters in `.claude-plugin/agents/`:
- Reviewers (tools `[Read, Grep, Glob]`, `omitClaudeMd: true`): `design`, `zoom-out`,
  `comprehension`, `codebase-details`, `readiness`, `structural`, `style`, `change-review`, and
  `judge` (new persona: answers by option id, states what would change its mind, adds no
  arguments beyond its own). The reviewer id `set` is `readiness` dispatched with every body;
  `astra` is the lane.
- `foreman` (new; tools `[Agent, Bash, Read, Grep, Glob]`, `omitClaudeMd: true`).
- EGM's `synthesizer` and `bootstrap-orchestrator` are **dropped**: the dispatching session sends
  every goldfish in one message and consolidates findings itself; the helper's `review record`
  dedups.

## 15. Repository, packer, tests

- Repository `gsVAM/superegm`; plugin `superegm`; marketplace `superegm` (one plugin, source
  `./`); commands `/superegm:<skill>`; version `1.0.0`.
- Layout: `plugin.json` (portable root manifest, kept, without `extensions.com.openai`);
  `skills/<name>/{SKILL.md, references/, assets/icon.svg, test_scenarios.yaml}`; `agents/*.md`;
  `.claude-plugin/{plugin.json, marketplace.json, icon.png, agents/*.md}`; `hooks/{hooks.json,
  run-hook.cmd, session-start}`; `resources/{review_panels.md, astra_lane.md,
  execution_instructions.md, document_standards/*.md}`; `scripts/{pack_plugin.py,
  prepare_release.py}`; `.github/workflows/tests.yml`; the helper: `skills/plan/scripts/
  superegm.py` holds `main()` only, and the package `skills/plan/scripts/superegm/` holds
  `__init__.py` (`store`, `atomic_write`, `journal`, `spec_slug`, `require_runcard`, and the
  `register` discovery over its modules with `pkgutil.iter_modules` in sorted order), `body.py`
  (`run_commands`, `step_paths`), plus one module per subcommand, `superegm/<subcommand>.py`,
  each exposing `register(subparsers)`, so a unit adds a subcommand by adding a module and edits
  only the modules its scope names; `tests/unit`; `tests/fixtures`;
  `tests/integration/test_claude.py`; `docs/{index,getting_started,claude,faq,privacy,releases}.md`.
  No `distributions/` directory.
- The packer is EGM's with: one host (`claude`; the `portable`/`openai` branches removed);
  `SKILLS` and `REQUIRED_SHARED` rewritten to the §14 and layout names; the three-file hook rule
  and the manifest hash check; the `effects` checks; `SHARED` gains `hooks/hooks.json`,
  `hooks/run-hook.cmd`, `hooks/session-start`, `skills/*/scripts/*/*.py`, `LICENSE-MIT`; the
  private-string scan. Its output goes to a temporary directory in tests and to the release
  directory in `prepare_release.py`.
- `prepare_release.py` builds one archive and names `gsVAM/superegm` in the attestation lines.
- Tests, EGM's unit tests kept, amended or replaced as follows (each a Step in the owning unit):
  - `test_packaging.py` (U01): `openai` dropped from every `target` parametrization; the
    `extensions.com.openai` tests and the `.codex-plugin` case deleted, except
    `test_refuses_unbundled_services`, re-pointed at `.claude-plugin/plugin.json`; the fixture
    copies the layout above only; skill count and names to the §14 set; the `.py` list to the
    helper and its package; `hooks/` allowed for the three files;
    `test_refuses_hooks_and_overwrites` becomes `test_refuses_a_second_hook` plus
    `test_refuses_overwrites`; the icon palette read from `assets/icon.svg`; `agents/openai.yaml`
    and `icon_small/icon_large` gone; `test_published_claude_runtime_is_current` deleted.
  - `test_harnesses.py` (U01): marketplace `superegm`, `MARKETPLACES` is
    `.claude-plugin/marketplace.json` only; plugin `superegm`; no `.codex-plugin`;
    `test_openai_submission_metadata_and_assets` and `test_jsonl_preserves_unicode_separators`
    deleted; `test_claude_permissions_remain_under_user_control` becomes
    `test_exactly_one_session_start_hook`; the Codex-link assertion, `docs/codex.md`,
    `docs/harnesses.md` and the `EGM artifact directory:` marker gone; adapter sets per §14; no
    synthesizer, no bootstrap orchestrator.
  - `test_codex_traces.py` and `tests/integration/test_codex.py` deleted; `test_claude_traces.py`
    kept; `tests/integration/test_claude.py` re-pointed at `review-spec`, `zoom-out` and
    `agents/zoom-out.md` (U01).
  - `test_releases.py` (U01): one checksum line, no codex manifest.
  - `test_astra_fork.py` (U01) becomes `test_fork_wiring.py` keeping only the background rule,
    the isolation-names-adapter rule, the non-convergence doctrine strings, the single-writer
    strings, the convergence-rule strings and the launch-line safety checks, re-pointed at the
    new file names; every other assertion is deleted or rewritten to SuperEGM's text.
  - `test_egm_handoff.py` becomes `test_helper.py`: only the in-process fake `gh` harness and
    the tests of behaviour SuperEGM keeps unchanged survive U01; U03 rewrites the tests pinning
    `.egm/handoff.json`, `handoff_state.json` and the `egm:` labels in this file; every later
    unit tests the forms it changes in its own file (U04 the `Units` check in
    `test_review_loop.py`; U05 the template, marker, placeholders and `decide` in
    `test_plan_scan.py`; U07 gate, apply and marker recovery in `test_file.py`), so only U03
    edits `test_helper.py`.
  - `test_frontmatter.py`, `test_skill_load_limits.py`, `test_scenario_coverage.py`,
    `test_markdown_tables.py`, `test_link_integrity.py` kept.
  - New: `test_hook.py` (goldfish silence, canary, hash; U02), `test_effects.py` (U02),
    `test_store.py` (writer partition, `atomic_write`, journal rendering, `init` defaults, run
    cards, child cards and the artifact rule, effect gating, `spec_slug`, `body.py`; U03),
    `test_review_loop.py` (status exit codes and the cap predicate, sha per round, regression
    marking, every-reviewer-ran, settle refusals, rule limits, the `Units` check, `--kind
    integrate`; U04), `test_plan_graph.py` and `test_plan_scan.py` (every rule in §9.1; U05),
    `test_review_plan.py` (U06), `test_file.py` (U07), `test_judges.py` (option-id convergence,
    diff, degradation, record, question grammar; U08), `test_builder_launch.py` (refusals,
    body-equality check, prompt file contents, round-n prompt, role and run-card variables, exit
    file, the branch-protection reads; U09), `test_wait_events.py` (the five events, batches,
    comment sources; U09), `test_foreman.py` (`foreman dispatch` opening `head-<unit>`,
    `tdd-order`, `review post`, `collect`'s foreman findings and contested reads; U10),
    `test_leavemealone.py` (routing at each of the three routed points, `judges question`, the
    interface-deviation fan-out; U11).
- Settled inconsistencies the merge must not carry: the 10-minute quiet rule text in the wave
  skill and foreman brief (the code never infers death); the missing `record-launch`/`collect`
  rows in the command reference; `allowed_mentions` missing from the config example; the
  "read-only except `apply --yes`" sentence (also `prepare`, `launch-builder`, `review post`,
  `decide`); stale docstrings naming `--remove`; the `{{decisions}}` row claiming answers appear
  in bodies; the hook not firing on `resume` (accepted: the context survives a resume);
  `handoff_plan.md` §3 and `design_doc.md` rewritten to the `## Units` cut; `prepare_release.py`
  pointing at upstream.
- Install: `claude plugin marketplace add gsVAM/superegm` then `claude plugin install
  superegm@superegm`. The README tells the owner to disable `egm@egm-astra` and
  `superpowers@claude-plugins-official` first, because SuperEGM replaces both and a plugin cannot
  disable another's hook.

## 16. What is left to the builder

- The helper's argparse surface beyond the names and contracts in §17: `init`, `runcard
  open|close`, `approve-spec [--amend-units | --void | --leavemealone]`, `graph`, `scan`,
  `review open|record|settle|status|rule|post`, `gate`, `dry-run`, `apply`, `verify`, `status
  [--wait]`, `launch`, `launch-builder`, `record-launch`, `foreman dispatch`, `collect`,
  `prepare`, `tdd-order`, `decide`, `interrupt`, `clean`, `judges open|diff|record|verdict|question`.
- The hook script's exact text, as long as it carries the dispatcher rule and the phase rule.
- Journal line formats, as long as every line is rendered from a fact.
- The judge persona's wording.
- The exact event-line grammar of `status --wait`, as long as the four event kinds and
  `deadline` in §11 exist and a call returns every unreported event.

## 17. Units

The unit graph for building SuperEGM 1.0.0. Each unit's plan must fit 48 KB. Interfaces are
subcommand contracts and file keys unless marked `py` (helper-internal). A Consumes producer may
be a transitive blocker. After U01 every §14 skill folder and every §14 adapter exists (the new
ones as stubs: a SKILL.md with its full frontmatter, the harness line and a one-line body;
`assets/icon.svg`; `test_scenarios.yaml`; an adapter with its §4 frontmatter whose body reads a
one-line persona), so later units modify and never create skill folders, adapters or personas.

| Unit | Scope | Blocked by | Size |
| --- | --- | --- | --- |
| U01 | Skeleton and absorption, packer-test-driven: the kept files of superpowers 7.0.0 and EGM 9bc49d4 copied in under the §14 names, stubs for every new skill, adapter and persona, the helper renamed and its tests kept green under EGM's forms; Codex host, visual companion, synthesizer, bootstrap and retired skills not copied; licences and notices; manifests; packer; CI workflow; the §15 test amendments owned by U01; CI green | — | L |
| U02 | The hook and effects: `using-superegm`, `hooks/`, role silence, canary, manifest hash, `test_hook.py`; `test_effects.py` and the packer's effects checks; the frontmatter, harness line and phase sentence of every SKILL.md; the §14 Change-column edits of the superpowers skills, `draft` and `drift-report`; `finishing-a-development-branch` without merge | U01 | M |
| U03 | Store, run cards, helper package: `superegm/__init__.py` with `store`, `atomic_write`, `journal`, `spec_slug`, `require_runcard` and module discovery; `body.py`; each absorbed subcommand moved to its own module; `init` with the §7 defaults; the writer partition; `runcard open|close` with child cards and the artifact rule; effect gating in every absorbed writing subcommand; config and label renames with their tests in `test_helper.py`; `approvals/` schema; `defer` and `--published` removed | U01 | L |
| U04 | The review loop and spec review: `review open|record|settle|status|rule`, `references/review_loop.md`, the cap predicate, sha per round, regression marking, every-reviewer-ran, the findings-file grammar, `--kind integrate`, the Astra review lane, the `review-spec` skill body, `approve-spec` with `--leavemealone`, `--void` and the `Units` check | U02, U03 | L |
| U05 | Plan: the unit schema in the parser, Interfaces and Step grammars through `body.py`, the body template with EGM's placeholders and the new `MARKER_RE`, `graph --plan` and `scan` rules, body hashing as EGM does it, `decide` with `--default`, the re-render and the self-posted comment, the `plan` skill body | U02, U03 | L |
| U06 | Plan review: the `review-plan` skill body, the `set` reviewer and its recording rule, per-unit reviews keyed `plan-<unit>`, which units a round dispatches, handoff standard questions 8–10, `fix-design` to `approve-spec --void` | U04, U05 | M |
| U07 | File: `gate`/`apply`/`verify` against converged rounds, `gate --accept` removed, marker recovery on the new marker, `base_at_start`, the `superegm:stopped` label, leavemealone "Create", the `file` skill body | U04, U05 | M |
| U08 | Judges: the `judges` skill body, `judge` adapter and persona, the question-file grammar, `judges open|diff|record|verdict`, child card, Astra judge lane with degradation, `min_vendors` | U02, U03 | M |
| U09 | Builders and events: `launch` with the branch-protection reads and the `stopped` skip, `launch-builder` with its refusals, the body-equality check, allow-list additions and the prompt file, `builder_orders.md` with the §10 deviation paragraph and the ruling words, `launches/` with the exit file, `record-launch`, `interrupt`, `clean`, `status --wait` returning every unreported event from exit files, issue and PR comments | U02, U03 | L |
| U10 | Foreman and the driver: `foreman` adapter and brief, `foreman dispatch` (opening `head-<unit>`), `prepare --dispatch` with `pr_body.md` and `comments.md`, `collect` with the foreman findings and contested reads, `tdd-order`, `review post` (the posting guard in the helper), the return words, `cap-reached` and `stop`, the `wave` skill body with the driver loop, batches, resume and report, landing | U04, U09 | L |
| U11 | leavemealone routing and finish: `judges question`, the §13.2 wiring at points 1–3 in `review-spec`, `review-plan`, `plan`, `wave`, the interface-deviation fan-out; `test_leavemealone.py`; `integrate` and `approve-spec --amend-units`; docs, README and install notes; release 1.0.0 packed by `prepare_release.py`; the §15 inconsistencies settled | U06, U07, U08, U10 | M |

Shared files: `test_helper.py` is U03's alone (later units test in their own files). Each
workflow SKILL.md stub U01 creates is filled by the unit that owns its section (U04
`review-spec`, U05 `plan`, U06 `review-plan`, U07 `file`, U08 `judges`, U09 `interrupt` and
`clean`, U10 `wave`, U11 `integrate`) after U02 has set its frontmatter and lines, and edited
again only by U11; U02 is a blocker of every one of them, so no shared-file order is needed. No
other file is edited by two units.

Interfaces (the names the plans will carry):
- U01 → all: the absorbed `state.json` keys (`units[<id>].issue`, `verify.complete`, `confirmed`,
  …), the absorbed subcommands (`approve`, `graph`, `scan`, `gate`, `dry-run`, `apply`,
  `verify`, `status`, `launch`, `decide`, `record-launch`, `collect`, `prepare`) with EGM's
  contracts until a later unit changes them.
- U03 → U04–U11: `superegm runcard open --skill <s> --artifact <a> [--parent <id>] [--mode <m>]
  → <id>; exit 0`; `superegm runcard close <id>`; every writing subcommand takes `--runcard <id>`
  and exits 1 with `runcard: <reason>` under the §6 artifact rule; `superegm init →
  .superegm/config.json`; `approvals/<spec-slug>.json` keys per §7; py: `store(repo_root: Path)
  -> Store`, `Store.path(kind: str, *parts) -> Path`, `atomic_write(path: Path, obj: dict) ->
  None`, `journal(store: Store, line: str) -> None`, `spec_slug(path: Path) -> str` (the file
  stem), `require_runcard(args, skills: frozenset[str]) -> dict`, `run_commands(body: str) ->
  list[str]`, `step_paths(body: str) -> list[tuple[str, str]]`, `register(subparsers)` per
  module.
- U04 → U06, U07, U10, U11: `superegm review open --kind <k> --artifact <a> [--sha256 <hex>]
  --reviewers <ids> --runcard <id> → <review-id>`; `superegm review record … [--sha256 <hex>]`;
  `superegm review settle …`; `superegm review status --review <id> → one line; exit 0
  converged / 2 cap / 3 open / 4 fix-design`; `superegm review rule …`;
  `reviews/<review-id>/review.json` keys `converged`, `rulings[]`; `round-<n>.json` keys
  `artifact_sha256`, `builder_contested[]`; `approve-spec` writes `approvals/<spec-slug>.json`.
- U05 → U06, U07, U11: `superegm graph --plan <file>` writes `handoff_units.json` with key
  `units[<id>].body_sha256` and `unit_<id>.md`; `superegm scan → exit 1 with "<rule>: <line>"`;
  `superegm decide --unit <U> --decision D<n> (--answer <text> | --default)`.
- U07 → U11: `state.json` key `base_at_start`.
- U08 → U11: `superegm judges open … → <panel-id>`; `superegm judges verdict --panel <id> →
  verdict JSON; exit 0 converged / 2 not`; the question-file grammar.
- U09 → U10: `superegm launch-builder --unit <U> --round <n> --runcard <id> → command line on
  stdout; exit 1 with the refusal`; `launches/<unit>.json` keys `launches[].status`,
  `launches[].prompt_sha256`; `superegm status --wait <s> --runcard <id> → one or more event
  lines`; the `**Deviation (<kind>):**`, `**Reply <fid>:**`, `**Ruling:**` and `**Builder
  status:**` headings.
- U10 → U11: `superegm foreman dispatch --unit <U> --runcard <id> → <dispatch_id> <child-card>`;
  `foreman-<unit>-<dispatch_id>` returns `clean | revise | contested: <ids> | cap-reached |
  target-moved | head-moved | error`; `superegm review post … → exit 0 posted / 3 target-moved`.

Waves: {U01} → {U02, U03} → {U04, U05, U08, U09} → {U06, U07, U10} → {U11}.
