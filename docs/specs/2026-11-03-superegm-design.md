# SuperEGM — design

Date: 2026-11-03. Status: DRAFT for goldfish spec review. Owner: gsVAM.
Inputs: the brainstorm brief (stream 4); the SuperEGM judge-panel verdict (converged, round 2 of
5); the cap-panel verdict on EGM 0.2.1; superpowers 7.0.0 and the EGM Astra fork at commit
9bc49d4 (0.2.1 plus the four round-12 fixes), both as installed and surveyed file by file.

## 1. Intent

SuperEGM is one Claude Code plugin that is the owner's entire software workflow, from an idea to a
merged pull request, run as one skillset. It absorbs two toolkits that each own half of that
workflow today:

- **superpowers 7.0.0** (MIT) owns the unit of work: brainstorming that ends in a written design;
  plans made of red→green→commit steps with the actual test code; exact interfaces between tasks;
  global constraints copied verbatim; a review focus; no placeholders; a ledger that survives
  compaction; "rulings, not stalls".
- **EGM 0.2.1, Astra fork** (Apache-2.0) owns orchestration and verification: goldfish isolation
  enforced by adapters; an adversarial gate before anything is written anywhere; a second model
  family as reviewer; a dependency graph cut into waves; idempotent, crash-recoverable GitHub
  filing; a foreman per unit reviewing every PR head against the unit's definition of done with CI
  as evidence; convergence with regression marking and a pausing cap; the run card; a merge that
  stays human.

The merge thesis: superpowers' unit of work inside EGM's orchestration, plus one distinction EGM
never had. **The spec is not the plan.** The spec is the design document. The plan belongs to the
GitHub issue, one per unit, and is TDD-shaped from its first line.

### Why now
The owner reviews designs with EGM and builds with superpowers, and the seam costs them: two entry
styles (typed vs auto-invoked), two memory stores, two convergence rules, reviewers that load the
project's CLAUDE.md when they should not, and no way to run the whole thing while asleep. Twelve
adversarial rounds on EGM 0.2.x proved the parts; what remains is the seam.

### What success looks like
The owner types one skill at each gate, sleeps, and wakes to either merge-ready PRs or a short
list of questions three judges could not settle. Nothing was merged by a machine. Every review,
verdict and launch is on disk with its isolation recorded.

## 2. Vocabulary

| Word | Meaning in SuperEGM |
| --- | --- |
| **owner** | the human. Approves and freezes specs, rules at caps when the panel cannot, merges. |
| **elephant** | the main session. Holds context, orchestrates, launches. Never reviews its own work. |
| **foreman** | a sub-elephant: a named subagent dispatched through the `superegm:foreman` adapter that owns one unit while it is in flight. Reviews every PR head through goldfish; keeps its memory in PR comments and its state file. |
| **builder** | a fresh headless local Claude session whose only brief is one issue body. Writes code in its own worktree, commits test-first, opens a draft PR. Not a goldfish: it writes. Never spawns. |
| **goldfish** | a fresh read-only reviewer dispatched through a plugin adapter with `omitClaudeMd: true` and tools `Read, Grep, Glob`. Sees only the artifact and the evidence it is handed. Never spawns. |
| **judge** | a goldfish with a model override that renders a verdict on a question file instead of findings on an artifact. |
| **review panel** | the 1–6 goldfish written into a run card for one artifact. Fixed for every round. |
| **judge panel** | three judges on three model families (one judge when the owner marks a question low-complexity) consulted until they converge. |
| **run card** | the on-disk record of one typed invocation: who typed what, when, on which artifact at which hash, with which panel and model tiering, in which mode, and what it produced. Every effect requires an open one. |
| **effect** | anything that leaves the working tree: GitHub writes, remote branches, publishing, starting a session or worker, writing the store, destructive local operations. |
| **leavemealone-mode** | the mode in which every point that would pause for the owner first consults the judge panel; the owner is paused only when the panel does not converge within its cap. |

## 3. Goals, non-goals, anti-goals

**Goals**
1. One plugin, one vocabulary, one state store, one convergence rule, one entry rule.
2. Spec and plan are distinct artifacts with distinct gates; both get adversarial goldfish review
   before anything downstream reads them.
3. Every reviewer is isolated by construction (adapter, not prompt), and the record says so.
4. Every independent step runs concurrently: goldfish within a review, plan reviews across units,
   builders within a wave, foreman rounds, judges within a panel.
5. Maximal autonomy on request: leavemealone-mode replaces the owner at every pause with the judge
   panel; only non-convergence reaches the owner.
6. Merge stays human. Nothing in SuperEGM merges, ever.

**Non-goals (v1)**
- Harnesses other than Claude Code. EGM's Codex/ChatGPT packaging (`.codex-plugin`,
  `agents/openai.yaml`, `docs/codex.md`) and superpowers' seven other harness manifests are not
  absorbed. (The Astra lane still uses the Codex CLI through the claudex-loop runner; that is a
  reviewer lane, not a harness.)
- External builder backends (cloud workers). Builders are local sessions.
- A local, no-GitHub wave. The wave files issues and reviews PRs; that is the one execution path.
- The brainstorming visual companion (a local Node server that also fetches a logo from the
  network). Brainstorming stays text-only.
- Replacing CI. CI is evidence the foreman reads; SuperEGM runs only the commands a DoD names.
- Hooks beyond the single SessionStart hook in §6. No MCP servers.

**Anti-goals (a build that does these has failed even if it works)**
- Two ways to do one thing: two plan formats, two ledgers, two convergence rules, two reviewers of
  the same kind with different isolation.
- A reviewer that saw CLAUDE.md, the memory index, hook output or a coordination digest.
- A builder that saw the spec, the brainstorm or the planning session's context rather than its
  issue body alone.
- An effect without an open run card.
- A machine merge, or a "merge locally" option anywhere in the plugin.
- A pause that reaches the owner in leavemealone-mode without a panel record showing
  non-convergence.
- A guess about liveness. SuperEGM never infers that a runner, builder or session is dead from
  file silence; only a terminal status in a result file proves termination.
- A code-aware Markdown mention scanner. The scan is raw text plus an allow-list.

## 4. Constraints

**Platform (from the live agent-teams probe; do not re-derive)**
- `name` on the Agent tool makes an agent addressable (`SendMessage`) and resumable; it is not a
  distinct teammate. `team_name` is deprecated.
- `omitClaudeMd` tracks the agent definition, never the name. A `general-purpose` subagent loads
  CLAUDE.md whether or not it is named; an adapter does not.
- A Bash background command dies when its own agent returns; one started from the main
  conversation survives across turns; an Agent launched with `run_in_background` outlives the
  turn. So builders and headless judges are launched by the elephant, never by a subagent that
  then returns.
- A backgrounded agent waiting on its own background Bash child emits an interim `completed`
  notification. The first `completed` is provisional.
- Claude Code has no plugin-on-plugin dependency and cannot disable another plugin's hook or
  skills. Hence absorb, not depend.
- Implementers and reviewers never dispatch subagents (superpowers); goldfish never spawn (EGM).
  Both hold. Foremen may dispatch goldfish; they are neither.

**Packaging (the absorbed EGM tests, kept and amended)**
- Frontmatter of every SKILL.md, in this order: `name`, `license`, `effects`, `effect_kinds` (only
  when `effects: external`), `disable-model-invocation` (only when typed), `description`. The
  frontmatter opens the file (the body is `text.split("---", 2)[2]`).
- Body ≤ 24,000 bytes. Two absorbed skills are within 400 bytes of it (`egm-review` 23,626;
  `egm-bootstrap` 23,767); absorption must move text into `references/`, not grow the body.
- One harness line in every SKILL.md: `In Claude Code, read \`${CLAUDE_PLUGIN_ROOT}/docs/claude.md\`
  first.` (EGM's second line, the Codex link, goes.)
- Every backticked `agents/…`, `resources/…`, `references/…` path in a skill or persona exists.
- Every skill folder carries `assets/icon.svg` (24×24 viewBox, a `<title>`, the two-colour palette)
  and `test_scenarios.yaml` (`skill:` = folder name, non-empty `scenarios`, each with
  `scenario_id`, `eval_type`, `turns`). `agents/openai.yaml` and `TEST.md` are dropped with the
  Codex host.
- Reviewer adapters: `tools` exactly `[Read, Grep, Glob]`, `model: inherit`, `omitClaudeMd: true`,
  no `memory`, body reads `${CLAUDE_PLUGIN_ROOT}/agents/<name>.md`. Two non-reviewer adapters
  have their own exact tool sets (§14).
- The packer forbids MCP (`mcpServers`, `mcp`, `apps`) and allows **exactly one** hook,
  `hooks/hooks.json` with one `SessionStart` entry, whose script hash it records in
  `distributions/claude/.claude-plugin/plugin.json` under `superegm.hook_sha256`.
- `distributions/claude` is the packed output, byte-identical to a fresh pack (the freshness test).
- Licences: `LICENSE` (Apache-2.0, EGM) and `LICENSE-MIT` (superpowers) both ship. Every Apache
  file changed from the fork carries `Modified by SuperEGM (gsVAM), 2026: <what>` in its header in
  the fork's own form; every file taken from superpowers keeps the MIT notice in `LICENSE-MIT` and
  gets `<!-- From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: <what>. -->` after
  the frontmatter when changed. README's **Licence** paragraph lists every modified file.

**Isolation**
- Every goldfish and judge is dispatched through an adapter defined in this plugin with
  `omitClaudeMd: true`. The dispatcher records each dispatch as `clean` or `exposed to <what>` in
  the review or verdict record.
- Headless sessions started by SuperEGM set `SUPEREGM_ROLE` to `builder` or `goldfish`. The hook
  prints nothing when the role is `goldfish`.

**Liveness and destruction (EGM round-12 doctrine, binding)**
- A result file with a terminal status (`completed` or `failed`) is the only evidence that a
  runner terminated.
- Removing a worktree is a destructive decision and is never taken on a guess. Stopping a wait is
  the non-destructive decision and may be taken; the record then says `not run (interrupted: …)`.
- A launched round is never re-prepared; an interrupted round is collected as interrupted and the
  next round number is prepared.

## 5. The workflow, end to end

| # | Phase | Typed? | Artifact | Gate | Record |
| --- | --- | --- | --- | --- | --- |
| 0 | Brainstorm | auto (reads and drafts only) | spec file in the repo | the owner's opt-in; the builder check | none yet |
| 1 | Spec review | **typed** | review report | converged (clean AND no regressions) or cap ruling | review record; **approval record freezing the spec at a commit hash** |
| 2 | Plan | **typed** | the handoff plan with one TDD plan per unit; rendered issue bodies in the store | render and lint pass | render record with body hashes |
| 3 | Plan review | **typed** | review report over the exact bytes | converged or cap ruling | review record keyed by body hash |
| 4 | File | **typed** | tracking issue, sub-issues, blocked-by links | dry run confirmed against the same hashes; `verify` reads back | filing receipt |
| 5 | Wave | **typed** | builders launched, foremen reviewing, draft PRs | per unit: head clean AND no regressions, or cap ruling | foreman state per unit; launch records; review comments on the PR |
| 6 | Merge | **human** | merged PR | the owner | the merge itself |
| 7 | Integrate | **typed** | integration review of the spec against everything merged | clean, or new units | review record; handoff closed |

Rules that span phases:
- **The spec is frozen** by the approval record at a commit hash. Every issue body cites the spec
  path and that hash. A later change to the spec reopens spec review and marks every unfiled plan
  stale; filed units are unaffected, their bodies being frozen by hash already.
- **Render → lint → review → dry run → file.** Review reads the bytes the owner confirms. Gates
  are mechanical: `plan` refuses without an approval record; `file` refuses a body whose hash is
  not in a converged plan-review record; `wave` refuses a unit without a filing receipt.
- **Dependency readiness means merged.** A unit enters a wave only when every unit it is blocked
  by, and every shared-file predecessor, has landed (issue closed as completed and the watched PR
  merged), never on a "clean" head.
- **The builder is always a fresh session whose only brief is the issue body.** Never the
  planning elephant continuing with the brainstorm in context.
- **The unit graph is the last section of the spec**, headed `## Units`, so spec review covers
  the cut: units, interfaces, dependencies, size against the body budget.
- **The panel for an artifact is written into the run card before dispatch and stays fixed every
  round.** The first goldfish's angle is fixed per artifact kind: the design critic for a spec,
  the implementation-readiness reviewer for a plan, the change reviewer for a PR head. Only the
  owner changes a panel, and only between reviews.
- **One convergence rule** for the three loops (spec, plan, PR head): clean AND no regressions;
  cap 5; lows never block. No loop requires two consecutive clean rounds.

## 6. Entry: the hook, effects, typed and auto-invoked skills

**One hook.** `hooks/hooks.json` declares one `SessionStart` command hook (matcher
`startup|clear|compact`, `async: false`) running `hooks/run-hook.cmd session-start`, both scripts
taken from superpowers with two changes: the script reads `skills/using-superegm/SKILL.md`, and it
exits 0 printing nothing when `SUPEREGM_ROLE` is `goldfish`. Output stays `hookSpecificOutput.
additionalContext` only; no other side effect. The injected text is the whole `using-superegm`
skill: superpowers' rule ("if there is even a 1% chance a skill applies, invoke it") rewritten for
SuperEGM's skill names, plus the phase rule below. Tests: run the script with the goldfish role
and assert empty stdout; a packer canary asserts the dispatcher's first line is absent from a
goldfish transcript fixture. This is the single exception to EGM's no-hooks rule; it is removable
if description-only invocation is ever measured to fire as reliably.

**Effects are declared and checked.** Every SKILL.md declares `effects: none | working-tree |
external`. An `external` skill also lists `effect_kinds`, a non-empty subset of `github-write`,
`remote-branch`, `publish`, `start-session`, `state-store`, `destructive-local`. The packer and
`tests/unit/test_effects.py` refuse: a skill without `effects`; an `external` skill without
`effect_kinds`; an `external` skill that is not `disable-model-invocation: true`; a
`disable-model-invocation: true` skill whose effects are `none` unless it is one of the two
review gates.

**Typed vs auto-invoked.** The line is authorization and effect, not "writes".
- Typed only (`disable-model-invocation: true`): every `external` skill, and the two review gates
  `review-spec` and `review-plan`, because the file step checks their records.
- Auto-invoked (the model may invoke from the description): skills whose effects are `none` or
  `working-tree`. Working-tree skills auto-invoke **only in an authorized phase**; each of their
  descriptions carries this sentence verbatim: "Only for a filed unit on its branch or an
  owner-requested fix on a branch; never during brainstorm, spec or plan." The authorization is a
  filed unit or an owner request, and the run card names it; being inside a worktree authorizes
  nothing. `verification-before-completion` never updates snapshots or fixtures.

**Every effect refuses without an open run card.** A typed skill's first action is `superegm
runcard open`, and it passes the id to every helper subcommand that has an effect; the helper
refuses an effect whose run card is missing, closed, bound to another artifact, or of another
skill. The skill's last action is `runcard close`. A run card still open when the next typed skill
starts on the same artifact is marked `interrupted` by that skill and left on disk.

## 7. The store

One store per target repository. One writer: the helper. JSON facts are the source of truth; a
journal is rendered beside them.

- `.superegm/config.json` — committed in the target repo; created by `superegm init` (run by the
  first typed skill when it is missing, from `git remote get-url origin`) and committed by the
  owner before any approval, since approval requires a clean tree. Keys, all with defaults:
  `repo`, `base` (default branch), `labels` (EGM's set, prefix `superegm:`), `issue_template`,
  `tracking_issue_title`, `banned_terms`, `fix_request_mention`, `allowed_mentions`,
  `max_in_flight` (5), `builder` (`profile_dir`, `model`, `allowed_tools`, `permission_mode`),
  `panels` (`spec`, `plan`, `head`: ordered reviewer lists), `judges` (three entries of
  `{model, vendor, lane}`), `astra` (`on|off`, model, effort), `mode` (`normal|leavemealone`),
  `artifacts_dir` (absolute, outside the working tree; default
  `~/.superegm/<owner>-<name>`). Unknown keys stop.
- Under `artifacts_dir`, never committed:
  - `state.json` — EGM's handoff state (`handoff_id, repo, remote, repo_root, plan, design,
    approval, gate, readiness, confirmed, labels, tracking, units, links, verify, decisions,
    status`) written atomically through a temp file and `os.replace`.
  - `runcards/<id>.json` — one per typed invocation: `skill, artifact, artifact_sha256, panel,
    tiering, mode, opened_at, closed_at | interrupted_at, produced[]`.
  - `approvals/<spec-slug>.json` — `path, sha256, commit, runcard, approved_at`.
  - `handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`, `handoff_bodies.md` — the plan and
    its rendered bodies (EGM's files, with the new sections).
  - `reviews/<artifact-sha256>/round-<n>.json` — findings per goldfish: id, severity, location,
    `regression: yes|no`, disposition; dispatch isolation `clean | exposed to <what>`; model and
    effort requested → effective; `what_ran` lines (`completed | not run (<reason>) | running
    (started <time>)`). The Markdown reports EGM writes today are kept beside them.
  - `foreman/<unit-id>.json` — rounds, launches, collected results, decisions (EGM's foreman file).
  - `panel/<id>/question.md`, `round-<n>/<judge>.md`, `verdict.json` — the judge-panel record.
  - `journal.md` — append-only, rendered by the helper from the facts it writes: `Unit U03: filed
    #41`, `Review <sha7> r2: clean, 1 regression — not converged`, `Ruling (panel <id>,
    leavemealone): one more round`. Free-form notes go in through `superegm note "<text>"`,
    prefixed `Note:`. Never a second writer of a fact.

The SDD ledger `progress.md` and the `.superpowers/sdd/` workspace do not survive; their contents
live in `state.json`, `foreman/`, and `journal.md`. `.egm/handoff.json` becomes
`.superegm/config.json`.

## 8. Spec review (phase 1)

`/superegm:review-spec <spec-path> [--panel design,zoom-out,…] [--astra on|off] [--leavemealone]`

- Opens a run card: spec path and sha256; the review panel (1–6 goldfish from `design`,
  `zoom-out`, `comprehension`, `readiness`, `structural`, `style`, `codebase-details`; the design
  critic always first; default from `config.panels.spec`); the Astra lane (on when the claudex-loop
  runner is installed and reachable, else recorded `not run (<reason>)`); model tiering
  (`SUPEREGM_GOLDFISH_MODEL`/`SUPEREGM_GOLDFISH_EFFORT`, EGM's rules renamed); the mode.
- Each round dispatches the whole panel **concurrently** through the adapters; each goldfish
  receives only the spec, the bundled standards, and from round 2 the prior round's report with
  the fixes marked. The Astra lane runs alongside through the runner's `review` mode, launched
  from the main conversation, fresh in round 1 and resumed after.
- Findings carry id `<reviewer>-<round>-<n>`, severity (`high | medium | low`, EGM's
  Blocker/Major/Nit), location, and from round 2 `regression: yes | no` (in text the previous
  round's fix touched, or the same defect elsewhere). A reviewer that fails twice is recorded
  `not run`, never as zero findings.
- A round is **clean** when no high or medium is unsettled (settled = contested or declined by the
  owner, or in leavemealone-mode by the elephant with a recorded reason). **Converged** = clean
  AND no regression. The report shows the trend: `rounds: 19 -> 14 -> 9 (regressions 7, 2)`.
- Between rounds the elephant fixes the spec. Doctrine: change the thing, not the round. If two
  consecutive rounds regress on the same area, the next fix is a deletion, a narrowed contract
  or a smaller surface, not a patch, and the record says what was removed.
- **Cap 5.** At the cap without convergence: in leavemealone-mode the judge panel is convened on
  the record (question: continue one bounded round / accept the remainder / split / stop) and a
  converged verdict becomes the ruling; otherwise, or when the panel does not converge, the owner
  is paused with the trend and the open findings. Round 6 never starts without a ruling.
- On convergence the skill writes the **approval record** through `superegm approve-spec`: the
  spec must be tracked, the tree clean, HEAD containing the spec at its sha256, and the spec's
  last H2 must be `## Units`. In normal mode the owner is asked to approve; in leavemealone-mode
  the converged review is the approval. The record freezes `commit` and `sha256`.

## 9. Plan (phase 2) and plan review (phase 3)

### 9.1 The plan is the issue body
`/superegm:plan <spec-path>` refuses without an approval record matching the spec's current
sha256. The elephant writes `handoff_plan.md` in the store (EGM's layout: title, `Design:` line,
`## 1. Issue template`, `## 2. Units`), one `### U<nn>: <title>` section per unit of the spec's
`## Units`, and runs `superegm graph` (parse, derive waves, render bodies) then `superegm lint`.
Nothing is committed under `docs/…/plans`; the rendered bytes live in the store.

Each unit section carries EGM's fields and the superpowers additions:

| Field | Rule |
| --- | --- |
| Objective | one sentence |
| Scope paths | `` `path` (create\|modify\|delete) ``, comma-separated |
| Design range | `` `path:start-end (heading)` `` into the frozen spec |
| Blocked by | `none` or unit ids |
| Shared files | `none` or `` `path`: after U01, before U05 `` items |
| Risk | `low\|medium\|high: reason` |
| Size | `S\|M\|L` by scope-path count |
| **Interfaces** | `Consumes:` and `Produces:` lines with exact names, parameters and return types, citing units by id |
| Definition of done | numbered items; item 1 is always "The test for each behaviour in Steps exists and was committed at or before its implementation (the foreman checks commit order)"; every other item names a command, a path, or `CI` |
| **Steps** | numbered: write the failing test (fenced code, the spec's exact values) → run, expected FAIL with reason → implement `<signature>` in `<path>` (one line on the approach only when the signature and the test leave a choice) → run, expected PASS → commit `test: …` then `feat: …` |
| Decide before build | `- none` or `- D<n> <question> owner: <owner>; default: <default>; blocking: yes\|no` |

Plan-level sections, rendered into **every** body verbatim: `## Global constraints` (the spec's
project-wide requirements, one line each, exact values) and `## Review focus` (the five input
classes or failure modes the spec implies but no unit's tests exercise; each line assigned to
exactly one unit with its pinning test, which that unit's Steps contain).

The rendered body uses this fixed layout, the first three sections fitting one phone screen:

```
<!-- superegm:handoff=<id> unit=<U07> spec=<sha256> -->
# U07 — <title>
Spec: `docs/specs/2026-11-03-superegm-design.md` @ <sha7> · unit U07 of 10 · wave 3

## Objective
## Interfaces
## Definition of done
## Global constraints
## Review focus (this unit)
## Steps
## Decide before build
## Scope, order and risk
Blocked by: #<n>, #<n> · Shared files: … · Risk: … · Size: … · Branch: `superegm/<handoff-id>/U07`
Part of #<tracking>.
```

Rules the renderer and `lint` enforce (each a test):
- Body ≤ 49,152 bytes (48 KB); a larger unit is refused with "split it".
- Numbered lists only. Never `- [ ]`: ticking edits the body and breaks byte-identity. EGM's
  default issue template is changed accordingly (its DoD was a checkbox list).
- Bodies cite units by id, never by issue number, except the `Blocked by` line and `Part of`,
  which `apply` fills in topological order as today; blocked-by is also an issue relationship.
- No placeholders: `TBD`, `handle edge cases`, `add appropriate validation`, `write tests for
  the above`, or a name in a Consumes line that no unit's Produces line defines.
- Global constraints and review focus are present in every body; every review-focus line names a
  test that appears in its owning unit's Steps.
- The marker line carries the spec sha256; the renderer refuses when it differs from the approval.
- Interfaces are consistent across the set: every Consumes name matches a Produces name exactly.
- No cycles in blocked-by; no shared-file chain that contradicts the blockers (EGM's rule).
- The raw-text mention and banned-term scan (EGM 0.2.1) passes with `allowed_mentions`.

### 9.2 Plan review
`/superegm:review-plan <spec-path> [--units U01,U02] [--panel readiness,design,…] [--leavemealone]`

- Reviews the exact rendered bodies. Each goldfish receives one body, the approved spec at its
  hash, and the Interfaces blocks of every sibling unit. **At least one goldfish reads the whole
  set** (every body) for interface consistency and the cut.
- The implementation-readiness reviewer is always first; the panel is 1–6, fixed in the run card.
  Units run **concurrently**, and the goldfish within a unit's panel concurrently.
- The absorbed handoff standard (seven questions) gains three: 8, interfaces present and
  consistent; 9, TDD order stated for every step and DoD item 1 present; 10, global constraints
  and review focus present. The no-placeholders list is a gate criterion. `fix-design` findings
  send the spec back to spec review and void the approval.
- Readiness is EGM's question, "what would a builder still ask?": one readiness goldfish per unit
  (cap 3 readiness rounds inside the review); a blocking question keeps the unit out of filing.
- Same convergence rule and cap as spec review. The review record is keyed by body hash; a
  re-render produces new bytes and needs a new review; the record for the old bytes stays.

## 10. File (phase 4)

`/superegm:file <spec-path>` is EGM's handoff filing (`gate` → `dry-run` → `apply --yes` →
`verify`) with these changes:
- `gate --pass` requires a converged plan-review record for every body hash it passes; `apply`
  refuses a body whose hash is not in such a record.
- The dry run and the owner's "Create" (or, in leavemealone-mode, the elephant's, recorded) are
  against the same write-list hash `apply` writes; `verify` reads every body back and compares.
- Idempotent filing with marker recovery stays: a rerun after a crash finds its issues by the
  marker line and continues; labels are `superegm:unit`, `superegm:wave-<n>`,
  `superegm:handoff-<id>`, `superegm:tracking`.
- Deviations during the build go in **comments**, never edits to the body. A deviation that
  changes an interface, the DoD or a test goes to the owner, or in leavemealone-mode to the judge
  panel first, before the head can count as clean; the ruling is a comment on the issue.

## 11. Wave, foreman, builder (phase 5)

`/superegm:wave <spec-path> [--leavemealone]`

**Scheduling.** EGM's rule: a unit is ready when every incoming graph edge has landed and no
blocking decision is open and unpublished. Up to `max_in_flight` units run concurrently.

**Launching a builder** is the elephant's job (platform facts, §4). For each unit it launches,
`superegm launch-builder --unit U07 --runcard <id>`:
1. refuses unless the unit's issue is filed and verified, the unit is ready, and no launch for it
   lacks a terminal status;
2. creates `<artifacts_dir>/worktrees/U07` from `base` on branch `superegm/<handoff-id>/U07`;
3. prints the one headless command line the elephant runs in the background from the main
   conversation: `CLAUDE_CONFIG_DIR=<builder.profile_dir> SUPEREGM_ROLE=builder claude -p
   <prompt-file> --model <builder.model> --permission-mode <builder.permission_mode>
   --allowedTools <builder.allowed_tools> --output-format json` with cwd the worktree, where
   `<prompt-file>` holds the issue body followed by the builder's standing orders
   (`references/builder_orders.md`) and nothing else;
4. records the launch (`unit, worktree, branch, started_at, result_file`) in `foreman/U07.json`
   through `record-launch`.
The standing orders: follow the Steps in order; test first, two commits per step; run every DoD
command; push the branch; open a **draft** PR whose body is the unit id and the DoD results;
finish with one comment `**Builder status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT`
(superpowers' implementer statuses) and stop. Wherever an absorbed skill says "ask your human
partner", a builder instead writes the question in that comment with status BLOCKED and stops.
A builder never spawns, never touches files outside its scope paths, never merges, never uses
`--dangerously-skip-permissions` unless `config.builder.permission_mode` says so explicitly.

**The foreman** is a named subagent (`name: foreman-<unit-id>`) dispatched through the
`superegm:foreman` adapter (`omitClaudeMd: true`; tools `Agent, Bash, Read, Grep, Glob`;
`model: inherit`) with `references/foreman_brief.md` and the unit id. Its contract, binding:
- Fresh goldfish per head: for every new head with CI concluded it runs `prepare` (fetch
  `refs/superegm/pr/<n>` and `refs/superegm/base/<n>`, detached review worktree, diff, CI JSON),
  then dispatches the head's panel (the change reviewer first; 1–6, fixed in the run card)
  **concurrently**, without `name`, each receiving the unit file, the frozen spec range, the diff,
  the CI file and the worktree path. The Astra inspect lane, when on, is launched by the elephant
  from the main conversation, never by the foreman.
- Memory in comments and its state file, not context: every decision is a PR comment; a
  re-dispatched foreman reconstructs its state from `foreman/U07.json` and the comments.
- **Clean** = every DoD command passed in CI on this head AND the panel found no unsettled high or
  medium AND `superegm tdd-order` passed: for each Step, the first commit touching the step's test
  file is at or before the first commit touching its implementation file, over the PR's commits.
- **No regressions** = the merge base's suite passes on the head (CI runs it) AND no finding is a
  regression of a prior round's fix.
- A rebase-only head (same tree against a new base) costs no round; an ordinary base merge that
  leaves the merge base's diff unchanged costs no round (EGM's `target-moved` rule).
- A push after review re-reads the head and reschedules the round. A review is posted through
  EGM's posting guard, bound to the reviewed commit with the pull-request reviews API, never
  `--approve` or `--request-changes`, after the raw-text scan of the comment.
- Cap 5 rounds per unit. At the cap: leavemealone-mode convenes the judge panel on the unit's
  record; the ruling, from the owner or the panel, is **one more round / split the unit / close
  the unit**, recorded in `foreman/U07.json` and as a PR comment. A split renders new units
  through `plan` → `review-plan` → `file`.
- The foreman never writes to GitHub except the review comment through the helper, never edits
  the owner's working tree, never merges, never removes a worktree, never infers that a builder
  died. A builder whose result file is terminal without a PR is recorded `not run (<status>)`;
  a builder whose result file is not terminal is left alone; the elephant launches a replacement
  only for the **next** round number.

**Landing.** A unit has landed when its issue is closed as completed and the watched PR is
merged (by the owner). Landing makes dependants ready. Landing never removes worktrees
automatically; `superegm clean --unit U07` is a typed `destructive-local` effect that refuses
while any launch or round of the unit lacks a terminal status and keeps what it cannot prove.

## 12. Merge and integration (phases 6–7)

- **Merge is human.** The absorbed `finishing-a-development-branch` offers two options: push and
  open a pull request; keep the branch as-is. Discard stays behind the typed word `discard`.
  "Merge back locally" is removed. Force-push is never offered.
- `/superegm:integrate <spec-path>` runs after the last unit lands: one goldfish review (the
  design critic; readiness too if the panel says so) of the frozen spec against `git diff
  <base-at-handoff-start>..<base>` of the target repo. Highs and mediums become new units through
  `plan` → `review-plan` → `file`; the handoff closes only when the integration review is clean.
  The close is recorded in `state.json` and the journal.

## 13. The judge panel and leavemealone-mode

### 13.1 `/superegm:panel <question.md> [--judges 1|3] [--evidence <paths…>] [--cap 5]`
- Typed; advisory by default. Opens a run card naming the question file's sha256, the evidence
  list and the judges from `config.judges`.
- Three judges on three model families, each a goldfish through the `superegm:judge` adapter
  (`omitClaudeMd: true`, tools `[Read, Grep, Glob]`, `model: inherit`) with a per-dispatch model
  override: Claude Fable 5.1 at max effort; Claude Opus at max effort; GPT-6 Astra at xhigh
  through the claudex-loop runner's `review` mode on the question file, when the runner is
  installed and reachable. `--judges 1` dispatches Fable only.
- Every judge reads only the question file and the listed evidence. Headless and non-Claude judges
  run with `SUPEREGM_ROLE=goldfish`.
- Round 1 is independent. From round 2 each judge receives every prior verdict verbatim plus a
  neutral list of where positions differ, written by the helper (`panel diff`), never argued by
  the elephant. Judges run **concurrently**.
- Converged = the same position on every question in the file. Rounds continue until convergence
  or the cap, then the owner is paused with the record.
- `panel/<id>/verdict.json` names each judge's model, vendor, effort, `clean | exposed to <what>`,
  and position per question per round. When the runner is absent or the lane is down (quota,
  network), the panel runs Claude-only and the record says so.
- The panel never changes a review panel, a reviewer set, or a run card's tiering.

### 13.2 leavemealone-mode
Set per run card with `--leavemealone` or in `config.json` (`mode: leavemealone`). Every point
that would otherwise pause for the owner first convenes the judge panel with a question file the
skill writes from the record:
- the cap in spec review, plan review, or a foreman's rounds;
- an open design question during `plan` (a readiness blocker the elephant cannot answer from the
  spec);
- a deviation that changes an interface, the DoD or a test;
- a ruling request (one more round / split / close);
- the approval of a converged spec and the "Create" confirmation of a dry run.
A converged verdict is applied and recorded as `Ruling (panel <id>, leavemealone)` so the owner can
read and overturn it. Non-convergence pauses the owner with the panel record. **Merge is
excluded**: no mode makes a machine merge.

## 14. Skill and adapter disposition

| Source | In SuperEGM as | Effects | Invocation | Change |
| --- | --- | --- | --- | --- |
| brainstorming (sp) | `brainstorming` | working-tree | auto | writes `docs/specs/YYYY-MM-DD-<topic>-design.md` ending in `## Units`; the gate's next step is `/superegm:review-spec`; the builder check runs through the `superegm:readiness` adapter; visual companion removed |
| egm-draft (egm) | `draft` | working-tree | typed | "draft a spec from a brief when brainstorming was skipped"; template ends in `## Units` |
| egm-review + egm-review-loop + egm-resolve (egm) | `review-spec` (+ `references/review_loop.md`, `references/resolve.md`) | external: state-store | typed | §8; the stage skills become references, not entry points; the upstream "max 1 re-audit" goes |
| egm-handoff (planning half) + writing-plans (sp) | `plan` | external: state-store | typed | §9.1 |
| new | `review-plan` | external: state-store | typed | §9.2 |
| egm-handoff (filing half) | `file` | external: github-write, state-store | typed | §10 |
| egm-wave + SDD prompts and `review-package` (sp) | `wave` (+ `references/foreman_brief.md`, `references/builder_orders.md`) | external: start-session, github-write, state-store | typed | §11 |
| finishing-a-development-branch (sp) | same name | external: remote-branch | typed | no local merge, no force |
| new | `integrate` | external: state-store | typed | §12 |
| new | `panel` | external: start-session, state-store | typed | §13 |
| new | `clean` | external: destructive-local | typed | §11 landing |
| test-driven-development, systematic-debugging, verification-before-completion, using-git-worktrees, writing-skills (sp) | same names | working-tree | auto, phase-gated | the phase sentence in each description; `systematic-debugging`'s "discuss with your partner after 3 failed fixes" becomes a BLOCKED comment for a builder |
| requesting-code-review, receiving-code-review, dispatching-parallel-agents (sp) | same names | none | auto | the reviewer is the `superegm:change-review` adapter, never `general-purpose`; the `HEAD~1` example is removed; the code-reviewer template gets a `model` line |
| using-superpowers (sp) | `using-superegm` | none | hook + auto | the dispatcher; one platform reference, `references/claude-code-tools.md` |
| diagnosing-superpowers (sp) | `diagnosing-superegm` | none | auto | issues go to `gsVAM/superegm`, only after the owner approves the text |
| egm-drift-report (egm) | `drift-report` | none | typed | |
| egm-bootstrap (egm) | `bootstrap` | working-tree | typed | |
| executing-plans (sp) | **retired** | | | the wave is the one execution path |
| subagent-driven-development (sp) | **retired as an entry point** | | | its prompts and `review-package` live under `wave/references`; `task-brief` and `sdd-workspace` go |
| egm-brainstorm (egm) | **retired** | | | superpowers' brainstorming replaces it |

Adapters in `.claude-plugin/agents/`, all pointing at `agents/<name>.md` personas:
- Reviewers (tools `[Read, Grep, Glob]`, `omitClaudeMd: true`): `superegm-design`,
  `superegm-zoom-out`, `superegm-comprehension`, `superegm-codebase-details`,
  `superegm-readiness`, `superegm-structural`, `superegm-style`, `superegm-change-review`,
  `superegm-judge` (new persona: renders a position per question, states what would change its
  mind, adds no arguments between rounds beyond its own).
- `superegm-foreman` (new; tools `[Agent, Bash, Read, Grep, Glob]`, `omitClaudeMd: true`).
- `superegm-synthesizer` (tools `[Agent, Read, Grep, Glob, Write]`) and
  `superegm-bootstrap-orchestrator` (tools `[Agent, Bash, Read, Grep, Glob, Write, Edit]`) as
  in EGM.

## 15. Repository, packer, tests

- Repository `gsVAM/superegm`; plugin `superegm`; marketplace `superegm` (one plugin, source
  `./`); commands `/superegm:<skill>`; version `1.0.0`.
- Layout: `skills/<name>/{SKILL.md, references/, assets/icon.svg, test_scenarios.yaml}`;
  `agents/*.md`; `.claude-plugin/{plugin.json, marketplace.json, icon.png, agents/*.md}`;
  `hooks/{hooks.json, run-hook.cmd, session-start}`; `resources/{review_panels.md, astra_lane.md,
  execution_instructions.md, document_standards/*.md}`; `scripts/{pack_plugin.py,
  prepare_release.py}`; `skills/plan/scripts/superegm.py` (the helper, single file, single
  writer; it may import from `skills/plan/scripts/superegm/*.py`); `tests/unit`;
  `distributions/claude`; `docs/{index,getting_started,claude,faq,privacy,releases}.md`.
- The packer is EGM's with: one host (`claude`); the one-hook rule and hash; the `effects` checks;
  the superpowers files in its allow-list (`hooks/*`, `skills/*/references/*.md`,
  `skills/*/scripts/*` kept to `.py` and the two hook scripts); the private-string scan.
- `prepare_release.py` names `gsVAM/superegm` in the attestation lines.
- Tests: EGM's unit tests adapted (skill count, names, marketplace, one harness line, no Codex
  host) plus new files: `test_hook.py` (goldfish silence, canary, hash), `test_effects.py`,
  `test_runcards.py` (every effect refuses without an open card), `test_plan_render.py` and
  `test_plan_lint.py` (every rule in §9.1), `test_tdd_order.py`, `test_store.py` (single writer,
  atomic writes, journal rendering), `test_panel.py` (degradation, record, neutral diff),
  `test_leavemealone.py` (routing at each pause point), `test_builder_launch.py` (refusals,
  prompt-file contents, role variable). Helper tests keep EGM's in-process fake `gh`.
- Settled inconsistencies the merge must not carry: the 10-minute quiet rule text in the wave
  skill and foreman brief (the code never infers death); the missing `record-launch`/`collect`
  rows in the command reference; `allowed_mentions` missing from the config example; the
  "read-only except `apply --yes`" sentence (also `defer --yes`, `prepare`, `launch-builder`);
  stale docstrings naming `--remove`; the `{{decisions}}` row claiming answers appear in bodies;
  the `(Recommended)` option in bootstrap; the hook not firing on `resume` (accepted: the context
  survives a resume); superpowers' hardcoded skill path in the hook (kept, now named
  `using-superegm`).
- Install: `claude plugin marketplace add gsVAM/superegm` then `claude plugin install
  superegm@superegm`. The README tells the owner to disable `egm@egm-astra` and
  `superpowers@claude-plugins-official` first, because SuperEGM replaces both and a plugin cannot
  disable another's hook.

## 16. What is left to the builder

- The helper's argparse surface beyond the names here: `init`, `runcard open|close|interrupt`,
  `approve-spec`, `graph`, `lint`, `scan`, `review open|record|close` (writes
  `reviews/<sha>/round-<n>.json`), `gate`, `dry-run`, `apply`, `verify`, `status`, `launch`,
  `launch-builder`, `record-launch`, `collect`, `prepare`, `tdd-order`, `decide`, `defer`,
  `clean`, `integrate record`, `panel open|diff|record|verdict`, `note`.
- The hook script's exact text, as long as it carries the dispatcher rule and the phase rule.
- The builder's allowed-tools default, as long as the dangerous-skip flag rule holds.
- Journal line formats, as long as every line is rendered from a fact or marked `Note:`.
- Module splits inside the helper, as long as the single-writer rule holds.
- The judge persona's wording.

## 17. Units

The unit graph for building SuperEGM 1.0.0. Each unit's plan must fit 48 KB.

| Unit | Name | Blocked by | Size |
| --- | --- | --- | --- |
| U01 | Repository skeleton and absorption: both code bases copied in from superpowers 7.0.0 and EGM 9bc49d4 under the new names, Codex host and visual companion removed, licences and notices, manifests, packer (one host, one hook rule, hash, allow-list), EGM's tests adapted, CI green | — | L |
| U02 | The hook and the dispatcher: `using-superegm`, `hooks/`, role silence, canary and hash tests | U01 | S |
| U03 | Effects: frontmatter on every skill, `test_effects.py`, packer checks, phase sentences, the retired skills removed, `finishing-a-development-branch` without merge | U01 | M |
| U04 | The store and run cards: `init`, `config.json` schema, `artifacts_dir` layout, `runcard`, effect gating in every writing subcommand, `journal.md`, `note`, `status` output | U01 | L |
| U05 | Spec review: `review-spec` skill and references, panel in the run card, concurrent dispatch, `review record`, convergence and cap, `approve-spec` | U03, U04 | M |
| U06 | Plan: unit schema extension in the parser, new body template and renderer, `lint` with every §9.1 rule, `review-plan` skill with the whole-set goldfish, review records by hash, handoff standard questions 8–10 | U03, U04 | L |
| U07 | File: `gate`/`apply` gated on plan-review records; label prefix; journal lines; deviation comments | U06 | M |
| U08 | Wave: `launch-builder` and `builder_orders.md`, the foreman adapter and brief, `tdd-order`, posting guard, cap and rulings, landing, `clean` | U07 | L |
| U09 | Panel and leavemealone-mode: `panel` skill, judge adapter and persona, Astra through the runner with degradation, `panel diff`, verdict record, routing at every pause point named in §13.2 | U04 | M |
| U10 | Finish: `integrate`, README and install notes, docs, release 1.0.0 packed and byte-verified, the inconsistencies list in §15 settled | U05, U06, U08, U09 | M |

Interfaces between units (the names the plans will carry):
- U04 → all: `runcard_open(skill: str, artifact: Path, panel: list[str], mode: str) -> str`;
  `runcard_close(card_id: str) -> None`; `require_open_runcard(card_id: str, artifact_sha256:
  str, skill: str) -> RunCard`; `store(repo_root: Path) -> Store` with `Store.path(kind: str,
  *parts) -> Path`; `journal(store: Store, line: str, kind: str) -> None`.
- U05 → U06: `approval_for(store: Store, spec: Path) -> Approval | None` with
  `Approval(sha256: str, commit: str, runcard: str)`.
- U06 → U07: `rendered_units(store: Store) -> list[RenderedUnit]` with `RenderedUnit(unit_id:
  str, body: str, sha256: str)`; `review_converged(store: Store, sha256: str) -> bool`.
- U07 → U08: `state.json.units[id]` keys `issue`, `filed_at`, `receipt`.
- U08 → U10: `landed(store: Store, unit_id: str) -> bool`; `state.json.base_at_start`.
- U09 → U05, U06, U08: `panel_rule(store: Store, question: Path, evidence: list[Path],
  judges: int = 3, cap: int = 5) -> Verdict` with `Verdict(converged: bool, position: str,
  record_id: str)`.

Waves: {U01} → {U02, U03, U04} → {U05, U06, U09} → {U07} → {U08} → {U10}.
