# SuperEGM — design

Date: 2026-11-03. Status: review cycle 2, round 4 (cycle 1 ended at round 6 by the judges'
ruling `q-close`: a new approach, not another patch). Owner: gsVAM.
Inputs: the brainstorm brief (stream 4); the SuperEGM judge-panel verdict (converged, round 2 of
5); the cap-panel verdict on EGM 0.2.1; superpowers 7.0.0 and the EGM Astra fork at commit
9bc49d4, both surveyed file by file; six goldfish rounds of cycle 1 (75, 75, 74, 61, 53, 65
findings; highs 27, 14, 12, 6, 3, 7) and rounds 1–3 of cycle 2 (50, 53, 49; highs 5, 3, 1);
three judge rulings (`q-wave`, `q-cap`, `q-close`). In cycle 2, §11 states the wave's contracts
and invariants only; its mechanics belong to the U09/U09b/U10/U10b plans, where they become
tests; the self-build's plumbing belongs to the U01/U03 plans. The spec says what; the plans say
how.

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
| **owner** | the human. Approves and freezes specs, rules when the judges cannot, reviews and merges pull requests. An administrator of the repository and the only account that may update its base branch (§11). |
| **elephant** | the main session. Holds context, orchestrates, launches headless sessions, dispatches foremen and goldfish. Never reviews its own work and never settles a finding against itself. |
| **helper** | the plugin's one Python program (§15), run as `superegm <subcommand>`. The only writer of the store. It never dispatches an agent. |
| **store** | the per-repository directory `artifacts_dir` (§7) holding every record SuperEGM writes. `.superegm/config.json`, committed in the repo, is its pointer and configuration. |
| **adapter** | a Claude Code agent definition `.claude-plugin/agents/<id>.md` with frontmatter `name: <id>`, fixed `tools`, and `omitClaudeMd: true`, whose body reads the persona `agents/<id>.md`. Invoked as `superegm:<id>`. A review panel lists reviewer ids; every reviewer id except `set`, `astra` and `foreman` is an adapter id. |
| **dispatching session** | the elephant or a foreman: the session that invokes adapters with the Agent tool and records each dispatch. |
| **goldfish** | a fresh read-only reviewer dispatched through an adapter with tools `Read, Grep, Glob`. Sees only the artifact and the evidence it is handed. Never spawns. |
| **judge** | a goldfish with a model override that answers a question file by option id instead of reporting findings. |
| **foreman** | a sub-elephant: a named subagent dispatched through the `superegm:foreman` adapter, in the foreground, to run one review round on one PR head and return one word. Its memory is `foreman/<unit>.json` and the PR's comments, never its context. |
| **builder** | a fresh headless local Claude session whose brief is one issue body, the builder orders, the rulings posted on its issue, and from round 2 the foreman's reviews of its own branch. Writes code in its own worktree under the **builder account**, commits test-first, opens a draft PR. Not a goldfish: it writes. Never spawns. |
| **builder account** | a second GitHub account with write access and no administrator or bypass role, whose token the elephant holds (`config.builder.gh_token_env`). Every PR a wave opens is authored by it, and under §11's protection its token cannot update the base branch, so nothing a wave runs can merge. |
| **Astra lane** | an optional extra reviewer (of a spec or a plan) or judge on a non-Claude model (GPT-6 Astra) driven by the external `claudex-loop` runner (a Python CLI over the Codex CLI). Launched by the elephant from the main conversation, never through an adapter. Recorded `not run (<reason>)` when the runner is absent or its lane is down. Not used on PR heads in v1. |
| **unit** | one buildable piece of a frozen spec: one issue, one branch, one PR. Ids `U01`, `U02`, … are stable for the life of a handoff. |
| **handoff** | one run of plan → file → wave → integrate for one frozen spec. Its id (§7) names the branches, the issue marker lines and `state.json`, and never changes while any unit is filed. One handoff per store at a time (§9.1). |
| **wave** | the set of units whose blockers have all landed, launched together. At most `max_in_flight` units are in flight at once; a unit is in flight from its first launch until it lands, is stopped, or its latest round's outcome is `clean` (§7), and a freed slot is refilled. |
| **head** | the commit at the tip of a unit's PR branch at the moment a round starts. |
| **round** | one review of one artifact (a spec, a unit's plan body, or a PR head): dispatch, findings, verdict. Rounds are numbered per review; a round that is not `completed` (§8) does not count toward the cap. |
| **clean** | the verdict on a round with no unsettled high or medium finding (§5). The destructive skill is always written `/superegm:clean`. |
| **landed** | a unit whose watched PR is merged and whose issue is closed as completed, whoever closed it. Only landing makes dependants ready. |
| **stopped** | a unit a ruling or the owner ended: issue open under `superegm:stopped` (or closed by the owner), branch kept, never relaunched; the owner lands it by hand or closes it with its unlanded dependants and re-appends what is still wanted (§12). |
| **DoD** | definition of done: the numbered, checkable items in a unit's body; the standard every head review is judged against. |
| **review panel** | the 1–6 reviewers written into a run card for one artifact. Fixed for every round. |
| **judge panel** | the judges (three models from two vendors) consulted until every question converges. |
| **run card** | the on-disk record of one typed invocation: skill, artifact and its hash, review panel, model tiering, mode, parent card if any, what it produced. Every effect requires an open one. |
| **effect** | anything that leaves the working tree: GitHub writes, remote branches, starting a session or worker, writing the store, destructive local operations. |
| **leavemealone-mode** | the mode in which every decision point listed in §13.2 goes to the judge panel first; the owner is paused only with the questions the judges do not converge on within their cap. |

## 3. Goals, non-goals, anti-goals

**Goals**
1. One plugin, one vocabulary, one store, one convergence rule, one entry rule.
2. Spec and plan are distinct artifacts with distinct gates; both get adversarial goldfish review
   before anything downstream reads them.
3. Every Claude goldfish and judge is isolated by construction (adapter, not prompt), and the
   record says what each dispatch saw. The foreman and the builder are not goldfish: a builder's
   tools are an allow-list, it acts as the builder account, and nothing the plugin ships can
   approve or merge a pull request (§11); the foreman's "never merge, never remove, never launch"
   is its brief, and the elephant's own session holds the owner's credentials; both are named in
   §4.1 as accepted residual risks.
4. Every independent step runs concurrently: goldfish within a review, plan reviews across units,
   builders within a wave, foremen for every head that is ready at once, judges within a panel.
5. Maximal autonomy on request: leavemealone-mode replaces the owner at every decision point in
   §13.2 with the judge panel; only non-convergence reaches the owner.
6. Merge stays human. Nothing the plugin ships approves or merges, ever.

**Non-goals (v1)**
- Harnesses other than Claude Code. EGM's Codex/ChatGPT host and superpowers' ten other harness
  entry points are not absorbed. The Astra lane uses the Codex CLI as a reviewer, not as a host.
- The Astra inspect lane on PR heads (judge ruling `q-wave` Q1). Astra reviews specs and plans and
  sits on the judge panel; heads are reviewed by Claude goldfish.
- Chaining phases. Each phase is typed; a night of leavemealone work is one phase.
- External builder backends (cloud workers). Builders are local sessions.
- A local, no-GitHub wave. The wave files issues and reviews PRs; that is the one execution path.
- The brainstorming visual companion (a local Node server that also fetches a logo from the
  network). Brainstorming stays text-only.
- Running a target repository's test suite inside SuperEGM. DoD commands are run by the builder
  before it opens its PR and by the repository's CI on the head; the foreman reads CI as evidence
  and runs nothing. SuperEGM's `clean` verdict needs CI green on the head.
- Automatic splitting of a unit that will not converge. At a PR cap the rulings are "one more
  round" or "stop"; reshaping units is the owner's, by hand, with `integrate`'s append path.
- A packed copy of the plugin in the repository. The marketplace installs from the repository
  root; `prepare_release.py` packs at release time only.
- Hooks beyond the single SessionStart hook in §6. No MCP servers.
- Handler-level mechanics in this document. §11 states contracts; the U09, U09b, U10 and U10b
  plans state the event grammar's line form, the batch order, the folding of a builder's events,
  the retries, the resume derivation, the prompt file's assembly and the exact GitHub reads, each
  as a test.

**Anti-goals (a build that does these has failed even if it works)**
1. Two ways to do one thing: two plan formats, two ledgers, two convergence rules, two parsers
   of one grammar, two reviewers of the same kind with different isolation, two caps inside one
   review.
2. A goldfish or judge that saw CLAUDE.md, the memory index, this plugin's hook output or a
   coordination digest, unrecorded. (The owner's own profile hooks are outside the plugin's
   control; §4 says how they are recorded.)
3. A builder that saw the brainstorm, the planning session's context, or anything beyond its
   issue body, the frozen spec range that body cites, the builder orders, the rulings posted on
   its issue, and the foreman's reviews of its own branch (the target repository's CLAUDE.md and
   its own hooks excepted: a builder is a session in that repository).
4. An effect without an open run card.
5. A machine approval or merge, or a "merge locally" option anywhere in the plugin.
6. The elephant settling a high or medium finding on its own artifact.
7. A pause that reaches the owner in leavemealone-mode without a judge record showing
   non-convergence.
8. A guess about liveness. SuperEGM never infers that a runner, builder or session is dead from
   file silence. Termination is proved only by a terminal status in a result file, by an exit
   file the launched command wrote, or by the owner's typed interrupt.
9. A code-aware Markdown mention scanner. The scan is raw text plus an allow-list.
10. A ruling, decision or review that the builder account wrote being honoured as the owner's or
    the judges'.

### 3.1 Alternatives considered, and what the rounds removed
- **Two plugins plus a bridge skill**. Rejected: a plugin cannot disable another plugin's hook or
  skills, so superpowers' `general-purpose` reviewers and its "merge locally" option stay
  reachable (goals 3 and 6), and the two stores and two convergence rules remain (anti-goal 1).
- **EGM 0.3 that requires superpowers**. Rejected: Claude Code has no plugin-on-plugin
  dependency; the requirement would be prose, and the same two-store problem remains.
- **Plans committed under `docs/…/plans`** (superpowers' layout). Rejected by the judge panel
  3–0: the builder's only brief must be the issue body.
- **Local merge by the foreman when a head is clean**. Rejected by the owner: merge stays human.
- **Owner-only pauses, no judge panel.** Rejected by the owner: leavemealone-mode exists so a
  phase can run without a human; the judges are the substitute, and non-convergence still reaches
  the owner.
- **A lock file in the store.** Rejected: EGM deleted locking after it caused four of seven high
  findings; SuperEGM gives every file one writer instead (§7).
- **Builders started by the owner by hand (EGM 0.2.1's wave).** Rejected by the judge panel
  (`q-wave` Q2): without automatic launch no new head appears after a `revise` until the owner
  acts, so a leavemealone wave stops after one round.
- **Builders on the owner's own GitHub identity.** Rejected in cycle 1: a builder holding the
  owner's credentials can do whatever the owner can, merging included; every PR a wave opens is
  authored by the builder account, whose token cannot update the base branch.
- **A protection that binds administrators, with the approval travelling as a PR; later, a
  required non-author review.** Rejected in cycle 2: restricting updates to the base branch to
  the owner is the whole fence (the builder account cannot update it; the owner merges by hand),
  so the review requirement and its administrator exemption constrained no actor the design cares
  about and cost an approval-PR step, a fixed branch name and a second identity on every owner
  commit. The owner commits the approval to the base branch directly; `launch` checks the content
  hash there.
- **A spec that specifies the wave's handlers.** Rejected by the judge panel (`q-close`): six
  rounds of cycle 1 found their highs in §11's mechanics and in each round's patches to them;
  the mechanics are now the plans' tests, and §11 keeps the contracts they must satisfy.
- **Removed in cycle 1** (each had bred findings and served no asked-for scenario): an automatic
  `split` ruling; a `deviate` subcommand; a `budget` subcommand and per-night counters;
  `stale`/`max_minutes`; a `publish` effect kind; a second Astra config block; a `wait`
  subcommand separate from EGM's `status --wait`; a byte-identity scheme different from EGM's;
  the `dangerous` sentinel; the two-step foreman round and background foremen; the `note`
  subcommand; `--judges 1|3` and `--cap` on the judges skill; `gate --accept`; the brainstorm
  "builder check"; the committed `distributions/claude` copy and its freshness test; the
  `bootstrap` skill and its orchestrator adapter; EGM's `defer` and the `decide --published`
  gate; the `launched` round phase; the "rebase-only head" rule; `fix-design` on a head review;
  a commit-ancestry launch gate (replaced by a content check); a label carrying the full
  handoff id.
- **Removed in cycle 2**: the approval branch and PR; `target-moved` before `prepare`; one judge
  panel per contested finding (one per round instead); the §15 list of source-tree corrections
  (each unit's plan carries its own); builders invoking skills (the orders carry the discipline);
  a `head-moved` return for a round whose only defect is a reviewer that did not run; a
  caller-written `what_ran` (it is derived, §8); the owner's own pull request opened as the
  builder account; U07's claim on `status`, `launch` and `prepare` (one U03 check replaces EGM's
  whole-plan checks there); any contest or settle of the CI finding (it is settled by no one,
  §8); the required non-author review and its administrator exemption; `approve-spec`'s
  tree-clean precondition (it commits by path); the worktree-reuse guard (a fresh worktree per
  launch); the hook canary and its transcript fixture (it re-derived a §4 platform fact from a
  hand-made file); the double-`error` decision point (a stalled review ends its invocation, §8).

## 4. Constraints

**Platform (from the live probes and the two code bases; do not re-derive)**
- `name` on the Agent tool makes an agent addressable and resumable; it is not a distinct
  teammate. Several agents may be dispatched in one message and run concurrently in the
  foreground; their returns arrive together.
- `omitClaudeMd` tracks the agent definition, never the name: an adapter subagent does not load
  CLAUDE.md or the memory index. SessionStart hooks run for sessions, not for Agent-tool
  subagents, so this plugin's hook never reaches a goldfish. **SubagentStart hooks in the owner's
  own profile do reach adapter subagents** (observed in cycle 1 and in every round of cycle 2);
  the plugin cannot suppress them, so every dispatch record carries what the goldfish reported
  seeing, and the README tells the owner to run reviews from a profile without SubagentStart
  hooks.
- A Bash background command dies when its own agent returns; one started from the main
  conversation survives across turns. So builders and the Astra runner are launched by the
  elephant, never by a subagent that then returns.
- Claude Code has no plugin-on-plugin dependency and cannot disable another plugin's hook or
  skills. Hence absorb, not depend.
- A per-dispatch `model` override on a `model: inherit` adapter is honoured; a per-dispatch
  `effort` is passed only when the Agent tool offers that parameter. `claude -p` takes the prompt
  as text (`claude -p "$(cat <file>)"`); `--output-format json` writes one result object;
  `--permission-mode` takes `acceptEdits` or `bypassPermissions`; `--allowedTools` entries are
  tool names or the one prefix form `Bash(<prefix>:*)`, which matches on the command's text and
  cannot exclude a refspec; a headless session with no `Skill` entry invokes no skill.
- `gh` acts as the account whose token `GH_TOKEN` holds; `git push` does so only over an HTTPS
  remote with `gh` as the credential helper, which `launch-builder` passes in the launched
  command's environment, never written to the shared git config.
- Goldfish never spawn; builders never spawn; a foreman dispatches goldfish and nothing else.

**Packaging (EGM's tests, kept where the form is unchanged; §15)**
- Frontmatter of every SKILL.md, in this order: `name`, `license`, `effects`, `effect_kinds` (only
  when `effects: external`), `disable-model-invocation` (only when typed), `description`. The
  frontmatter opens the file (the order and the opening-line rule are U02's new test).
- Body ≤ 24,000 bytes; absorption moves text into `references/`, never grows a body.
- One harness line in every SKILL.md, EGM's own, kept verbatim: `In Claude Code or Cowork, read`
  followed by the backticked path `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` and `first.`
- Every backticked `agents/…`, `resources/…`, `references/…` path in a skill or persona exists.
- Every skill folder carries `assets/icon.svg` (EGM's palette rule, read from the SVG) and
  `test_scenarios.yaml` (EGM's shape).
- Reviewer adapters: `tools` exactly `[Read, Grep, Glob]`, `model: inherit`, `omitClaudeMd: true`,
  no `memory`, body reads `${CLAUDE_PLUGIN_ROOT}/agents/<id>.md`. The one non-reviewer adapter
  (`foreman`) has the exact tool set in §14.
- The packer forbids MCP and allows **exactly** three hook files, nothing else under `hooks/`:
  `hooks/hooks.json` (one `SessionStart` entry), `hooks/run-hook.cmd`, `hooks/session-start`. The
  source `.claude-plugin/plugin.json` carries `"superegm": {"hook_sha256": …}`; the packer refuses
  when it differs from the script. The packer's output is never committed.
- Licences: `LICENSE` (Apache-2.0) and `LICENSE-MIT` both ship; every changed Apache file carries
  `Modified by SuperEGM (gsVAM), 2026: <what>` in the fork's own form; every changed superpowers
  file carries `<!-- From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: <what>.
  -->`; README's **Licence** paragraph lists every modified file and is written once, by U11.

**Isolation**
- Every Claude goldfish and judge is dispatched through an adapter. `superegm review record` and
  `superegm judges record` store each dispatch as `clean` or `exposed:<what>`, as the dispatching
  session reports it from the goldfish's own account of what it saw.
- Headless sessions started by SuperEGM set `SUPEREGM_ROLE` to `builder` or `goldfish`, and
  `SUPEREGM_RUNCARD` to the run card they run under. The hook prints nothing when the role is
  `goldfish` or `builder`. The builder profile (`config.builder.profile_dir`) is created empty by
  the owner, with no plugins and no `CLAUDE.md`; `launch-builder` refuses otherwise.

**Liveness and destruction (EGM round-12 doctrine, binding)**
- A builder launch is **terminal** when its exit file exists (the launched command writes
  `<result-file>.exit` on any exit) or when the owner's typed `/superegm:interrupt` recorded
  `interrupted`. An Astra review run is terminal when its `result.json` says `completed` or
  `failed`. A round is terminal in phase `posted`, or `collected` with a `not run` reason.
  Nothing else is terminal; silence proves nothing.
- Removing a worktree is a destructive decision and is never taken on a guess: `/superegm:clean`
  refuses while any launch or round of the unit is not terminal, and keeps what it cannot prove.
- A round is never re-prepared: `foreman dispatch` collects any non-terminal round of the unit as
  `not run (superseded)` before it writes a fresh `dispatch_id`.

### 4.1 Risks and mitigations

| Risk | Impact | Mitigation | Unit |
| --- | --- | --- | --- |
| Runaway spend (goldfish rounds, judge rounds, a builder that blocks on every relaunch, a reviewer that never completes) | a night costs more than it returns | the caps (a review is at its cap when its counted rounds ≥ 5 + its single `continue`; 5 judge rounds per decision, one panel per review round; `relaunch` offered once per unit, then `stop`; a third `blocked` on one unit without an intervening head is a point-3 question; two consecutive rounds that are not `completed` stall the review's invocation, §8) and `max_in_flight` bound one phase; a phase never chains into the next | U04, U08, U09, U10b |
| GitHub rate limits or half-finished writes | issues created twice, links missing; polling starved | EGM's marker recovery and retry handling, kept; `verify` reads everything back; `status --wait` polls at EGM's interval | U07, U09b |
| A builder dies without an exit file, or exits without a PR | its unit stalls | the exit file is written by the shell on any ordinary exit; an exit without a PR is decision point 3; a hard kill is ended by the owner's `/superegm:interrupt`, itself a point-3 question; the wave report, rewritten after every batch, lists every non-terminal launch | U09, U10b |
| Two foremen on one unit after a compaction | duplicate rounds and posts | `foreman/<unit>.json.dispatch_id`, written by `foreman dispatch` and required by `prepare --dispatch`, `collect` and `review post` | U10 |
| A builder merges a PR, pushes to the base branch, or force-pushes | an undoable merge or a lost branch | builders act as the builder account; `launch` refuses a wave unless the repository's protection meets §11's contract (only the owner updates the base branch); the builder's allow-list has no merge or worktree command. Its push entry is a prefix for its own branch, which cannot exclude a `src:dst` refspec, so a fast-forward push onto a sibling's branch is an accepted residual: the orders forbid it and the owner sees it in the sibling's PR | U09 |
| The foreman merges or removes a worktree; the elephant, holding the owner's credentials, merges | the same | the foreman adapter's Bash cannot be pattern-restricted and the elephant is the owner's session; the plugin ships no approve or merge path and their briefs forbid both; accepted residual risk | U10, U10b |
| A builder-authored comment is taken for a ruling or a decision; a builder edits CI or files outside its scope so its head reads green | a machine clears its own finding | the helper honours `**Ruling:**` and `**Decision D<n>:**` comments only from authors other than the builder account's login; the CI finding is settled by no one; a changed path outside the unit's Scope paths is a `foreman` high | U04, U09, U10 |
| Judges from one vendor only (Astra lane down) | less independent verdicts | `judges.min_vendors` (default 1); the record says `degraded: true` whenever fewer than two vendors answered | U08 |
| A spec edit after a clean round or after approval; an approval not yet on the base branch | unreviewed bytes frozen; bodies cite a stale hash; builders branch from a base without the frozen spec | every round records the sha256 it reviewed; `approve-spec` refuses unless the spec's current sha256 equals the converged round's; `graph` refuses when it differs from the approval; `launch` refuses until the spec at `origin/<base>` hashes to the approval | U04, U05, U09 |
| The claudex-loop runner's lane down | no second vendor | every lane use is optional and recorded `not run (<reason>)`; the every-reviewer-ran check excepts it | U04, U08 |
| CI absent, queued for ever, or needing manual approval on a draft PR | rounds never start | `launch` refuses the first wave unless `origin/<base>` carries a workflow triggered on `pull_request`; `foreman dispatch` refuses while a head's CI is pending or absent; a head whose CI is still pending or absent at two consecutive `deadline`s of one `wave` invocation ends the loop for that unit, and the wave report says so | U09, U09b, U10, U10b |
| The owner's profile hooks reach a goldfish | priming the record cannot remove | the dispatch record carries the goldfish's own report of exposure; the README names the profile rule | U04 |

**Cost and timeline (estimate, not a promise).** One leavemealone phase: spec review 2–3 rounds
× 6 goldfish; plan review 2 rounds × 13 units × 3 goldfish; a wave of 5 builders × 2 rounds with 2
goldfish per head; up to one judge panel (3 judges, 1–2 rounds) per review round with a contest.
About 180 subagent dispatches and 10 headless sessions. The self-build (§17) is six waves; at one
wave a night it is one week. The first mid-term exam is that build, filed and driven by hand by
the elephant following this spec's forms, since the tools that would run it are what it builds;
its by-hand waves open their PRs as the owner, and the owner merges them (the fence is the
protection, not the author). If its unit plans do not fit the body budget, or its first wave
pauses the owner for anything other than approvals and merges more than twice, the cut or the
caps are wrong. The final exam: one leavemealone phase of each kind (spec review, plan review,
wave, integrate) on a second repository, each ending at its gate with at most two owner pauses,
none of them without a judge record of non-convergence; 1.0.0 ships when that passes.

## 5. The workflow, end to end

| # | Phase | Typed? | Artifact | Gate | Record |
| --- | --- | --- | --- | --- | --- |
| 0 | Brainstorm | auto (reads and drafts only) | spec file in the repo | the owner's opt-in | none yet |
| 1 | Spec review | **typed** | review report | converged or ruled | review record; **approval record freezing the spec at a sha256** |
| 2 | Plan | **typed** | the handoff plan with one TDD plan per unit; rendered issue bodies in the store | `graph` and `scan` pass | `handoff_units.json` with body hashes |
| 3 | Plan review | **typed** | review report per unit over the exact bytes | converged or ruled | review record per unit |
| 4 | File | **typed** | tracking issue, sub-issues, blocked-by links | dry run confirmed; `verify` reads back | filing receipt |
| 5 | Wave | **typed** | builders launched, foremen reviewing, draft PRs | per unit: head clean (its contested findings ruled) AND no regressions | foreman state per unit; launch records; review comments on the PR; the wave report |
| 6 | Merge | **human** | the merged PR | the owner | the merge itself |
| 7 | Integrate | **typed** | integration review of the spec against everything merged | nothing left to escalate | review record; handoff closed |

One human step sits between phases 1 and 5: the owner pushes the approval commit (the spec and
`.superegm/config.json`, which `approve-spec` commits on the owner's branch) to `origin/<base>`;
the protection of §11 lets only the owner update the base branch, so this is one push. `launch`
refuses the first wave until the spec at `origin/<base>` hashes to the approval's `sha256`. The
same step follows every `--amend-units`, and the owner then types the next phase; nothing chains.

Rules that span phases:
- **The spec is frozen** by the approval record at its sha256. Every issue body cites the spec
  path and that hash. A change to any section other than `## Units` reopens spec review as a new
  cycle of its review and marks every unfiled plan stale; rows appended to `## Units` are
  re-approved by `approve-spec --amend-units` without a review round (§12). Filed units are
  unaffected, their bodies being frozen by hash already, and the handoff id does not change.
- **Render → scan → review → dry run → file.** Review reads the bytes the owner confirms. Gates
  are mechanical: `graph` refuses without an approval record matching the spec; `apply` refuses a
  body whose hash is not the one its review's converged round recorded; `launch` refuses a unit
  without a filing receipt.
- **Dependency readiness means landed.** A unit enters a wave only when every unit it is blocked
  by, and every shared-file predecessor, has landed, never on a "clean" head.
- **The builder is always a fresh session.** Its brief is the issue body, the builder orders, the
  rulings on its issue and, from round 2, the foreman's reviews of its own branch. Never the
  planning elephant.
- **The unit graph is the last section of the spec.** The spec's last H2, after any numeric
  prefix, is `Units`. A Consumes line's producer must be a blocker of the consuming unit, directly
  or transitively. A shared file is a file two units edit that their blockers do not already order.
- **The review panel for an artifact is written into the run card before dispatch and stays
  fixed every round.** The first reviewer's angle is fixed per artifact kind: `design` for a spec,
  `readiness` for a plan, `change-review` for a PR head. Only the owner changes a panel, and only
  between reviews.
- **One convergence rule** for the three loops (spec, plan, PR head), implemented once (§8) and
  consumed by the other two: a round is **clean** when no high or medium finding is unsettled;
  the artifact is **converged** when a round is `completed` (§8: every reviewer in the run card's
  panel has a record, the Astra lane's being findings or `not run`; the `foreman` reviewer never
  counted; on a head, the round posted) AND clean AND no high or medium finding in it is a
  regression of a prior round's fix. Lows never block. A review is **at its cap** when its
  counted rounds ≥ 5 + its `continue` rulings; at the cap a ruling is required (§13.2) before any
  further round; `accept` makes the artifact converged (`converged: by ruling <id>`); `continue`
  may be ruled at most once per review cycle; after `stop` no ruling is accepted and the cycle
  stays at its cap; a new cycle starts with a fresh cap. No review has a second kind of cap. A
  review whose two latest rounds under the current run card are not `completed` is **stalled**
  (§8): the invocation ends with the record and a re-typed skill resumes.

## 6. Entry: the hook, effects, typed and auto-invoked skills

**One hook.** `hooks/hooks.json` declares one `SessionStart` command hook (matcher
`startup|clear|compact`, `async: false`) running `hooks/run-hook.cmd session-start`, both scripts
taken from superpowers with four changes, all in `session-start`: it reads
`skills/using-superegm/SKILL.md`; the wrapper line names `superegm:using-superegm`; it exits 0
printing nothing when `SUPEREGM_ROLE` is `goldfish` or `builder`; the non-Claude output branches
are removed. Output is `hookSpecificOutput.additionalContext` only. The injected text is the
whole `using-superegm` skill: superpowers' rule ("if there is even a 1% chance a skill applies,
invoke it") rewritten for SuperEGM's skill names, plus the phase rule below. Tests: the script
under the goldfish and builder roles prints nothing; the hash test compares the manifest to the
script. (Goldfish never see the hook because SessionStart hooks do not reach Agent-tool
subagents, a §4 platform fact; the dispatch record carries what each goldfish reported seeing.)

**Effects are declared and checked.** Every SKILL.md declares `effects: none | working-tree |
external`. An `external` skill also lists `effect_kinds`, a non-empty subset of `github-write`,
`remote-branch`, `start-session`, `state-store`, `destructive-local`. The packer and
`tests/unit/test_effects.py` refuse: a skill without `effects`; an `external` skill without
`effect_kinds`; an `external` skill that is not `disable-model-invocation: true`; a skill whose
§14 row says typed but whose frontmatter lacks `disable-model-invocation: true`. Launching the
claudex-loop runner is a `start-session` effect; opening a run card is a `state-store` effect, so
every `external` skill lists `state-store`.

**Typed vs auto-invoked.** The line is authorization and effect, not "writes".
- Typed only: every `external` skill; the two review gates `review-spec` and `review-plan`; and
  the two EGM entry skills `draft` and `drift-report`.
- May be auto-invoked: every other skill. The three working-tree skills that are not typed
  (`test-driven-development`, `systematic-debugging`, `verification-before-completion`) carry
  this sentence verbatim in their descriptions: "Only for a filed unit on its branch or for an
  owner-requested fix on a branch; never during brainstorm, spec or plan." A filed unit or an
  owner request is authorized by the run card the elephant holds; builders cannot invoke skills
  and follow the orders instead. `brainstorming` and `writing-skills` are exempt: they run on the
  owner's request outside any unit. `verification-before-completion` never updates snapshots or
  fixtures.

**Every effect refuses without an open run card.** An `external` skill's first action is
`superegm runcard open`, and it passes the id to every helper subcommand that has an effect. A
card's `artifact` is the spec path for the spec-scoped skills (`review-spec`, `plan`,
`review-plan`, `file`, `wave`, `integrate`), the unit id for `interrupt` and `clean`, the
question file for `judges`, and the branch for `finishing-a-development-branch`. Each writing
subcommand declares the skills it serves (`require_runcard(args, skills)`), which refuses unless
the card is open, belongs to one of those skills, and either names the subcommand's artifact or
is the spec-scoped card of the handoff the named unit belongs to. A **child card** (`--parent
<id>`, opened by `judges open` and by `foreman dispatch`) is accepted while its parent is open or
`interrupted`. The skill's last action is `runcard close`. A card of the same skill on the same
artifact still open when that skill starts again is marked `interrupted`; cards of other skills
are left alone.

## 7. The store

One store per target repository. The helper is the only program that writes it, and every file
has exactly one writing invocation at a time:

| File | Writer |
| --- | --- |
| `state.json` | the elephant's typed skills (`plan`, `file`, `wave`, `integrate`), one at a time |
| `approvals/<spec-slug>.json` | `approve-spec` |
| `handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`, `handoff_bodies.md` | `plan` (`graph --plan <file>`; `decide` re-renders one unfiled unit and leaves a filed one as filed) |
| `reviews/<review-id>/…` | the invocation that opened that review; on a head, also the foreman dispatch the round records (`review record`, `collect`) |
| `judges/<id>/…` | the invocation that opened that panel |
| `runcards/<id>.json` | the skill that opened the card; `card_add` for later facts |
| `launches/<unit>.json`, `launches/<unit>_r<n>_prompt.md` | the elephant (`launch-builder`, `record-launch`, `interrupt --launch`) |
| `worktrees/<unit>/` | the elephant (`launch-builder`, `/superegm:clean`) |
| `foreman/<unit>.json`, `review/<unit>/pr<n>/` | the foreman dispatch whose `dispatch_id` the round records (`prepare --dispatch`, `collect`, `review post`); the elephant's `foreman dispatch`, `interrupt --round` and `/superegm:clean` between dispatches; `decision open\|rule` (U10b) for `decisions[]` and `rulings[]` |
| `wave_<n>_report.md` | `wave` (`superegm report`, after every batch) |
| `journal.md` | append-only, `O_APPEND`, one line per fact, written by the subcommand that wrote the fact |

All writes go through a temp file and `os.replace`. No lock file.

- `.superegm/config.json` — committed in the target repo; created by `superegm init` (run by the
  first typed skill when it is missing; it prints the owner's by-hand steps: the builder account
  and profile, the branch protection of §11) and committed by `approve-spec` with the spec (§8).
  Keys, all with defaults `init` writes: `repo`, `base` (the default branch; `init` refuses
  another), `artifacts_dir` (absolute, outside the working tree), `mode` (`normal |
  leavemealone`), `max_in_flight` (5), `labels` (EGM's set with prefix `superegm:` plus
  `stopped`), `issue_template`, `tracking_issue_title`, `banned_terms`, `fix_request_mention`,
  `allowed_mentions`, `reviewers` (`spec`, `plan`, `head`, `integrate`: ordered reviewer lists),
  `astra` (`enabled`, `model`, `effort`), `judges` (`min_vendors` 1; `members`: `fable` and
  `opus` through the adapter at max effort, `astra` through the runner), `builder`
  (`profile_dir`, `model`, `permission_mode` = `acceptEdits`, `gh_token_env` =
  `SUPEREGM_BUILDER_TOKEN`, `allowed_tools`: the read/edit tools, `git add|commit|status|diff|log|
  mv|rm`, `gh pr create|edit|comment`, `gh issue comment`, each as a prefix pattern; the push
  prefix for the unit's own branch is added per launch). Unknown keys stop.
- Under `artifacts_dir`, never committed:
  - `state.json` — EGM's handoff state with EGM's keys, minus `approval`, `pending_approval`,
    `gate_unreviewed_diff` and `decisions[…].published`, plus `base_at_start`, per unit
    `body_sha256`, and `filings[]`: the confirmed write list of every filing that ran `apply`,
    appended by `apply` (EGM's `confirmed` is the pending one). A unit with a filed issue number
    is **frozen**: `graph` reads its section from the store (`handoff_plan.md`), never from the
    plan file, and refuses when the file's section differs; `graph` and `dry-run` re-render and
    re-hash unfiled units only; `apply` and `verify` act on the current filing's confirmed write
    list, `verify` reading back every issue that list names and comparing the stored body, never
    a re-render; the tracking issue belongs to the latest filing's list only (a later filing
    rewrites its body), earlier lists being compared on their unit issues. One check,
    `require_frozen_units(handoff)` in U03 (py), replaces EGM's whole-plan checks in `status`,
    `launch` and `prepare`: for every filed unit, the plan file's section equals the stored one
    and `unit_<id>.md` equals the body its filing's list in `filings[]` stores; for every unfiled
    unit, `state.json`'s `body_sha256` equals `handoff_units.json`'s; any difference refuses.
  - `runcards/<id>.json` — `skill, artifact, artifact_sha256, reviewers, tiering, mode, parent,
    opened_at, closed_at | interrupted_at, produced[]`.
  - `approvals/<spec-slug>.json` — `path, sha256, commit, runcard, review, approved_at,
    amended[], voided_by, handoff_id`. `<spec-slug>` is the spec file's stem. `handoff_id` is
    `<EGM's 20-character slug of the stem>-<first 6 hex of the first approval's sha256>`, set by
    the first approval, copied by every amendment and by every re-approval while any unit is
    filed. The handoff label is `superegm:handoff-<6 hex>`; markers and branches carry the full
    id.
  - `handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`, `handoff_bodies.md` — EGM's files
    with the new sections; `handoff_units.json` carries `body_sha256` per unit.
  - `reviews/<review-id>/review.json` (`kind, artifact, cycle, reviewers, runcard, converged,
    converged_round, rulings[]`) and `round-<n>.json` (`artifact_sha256`; findings per reviewer
    with id, severity, location, `regression: yes|no`, disposition, ruling; `builder_contested[]`
    of `{fid, reason}` on a head; each dispatch's isolation, model and effort requested →
    effective; `what_ran`, derived as §8 says and stored with the round). Review ids carry a
    cycle: `spec-<spec-slug>-c<n>`, `spec-<spec-slug>-integrate-c<n>`, `plan-<unit>-c<n>`,
    `head-<unit>-c<n>`; `review open` on an artifact whose latest cycle is closed (`accept`,
    `stop`, or a spec change) starts the next cycle, and "the review" of an artifact means its
    latest cycle.
  - `launches/<unit>.json` — `launches[]` with `round` (the launch count), `worktree`, `branch`,
    `started_at`, `status` ∈ `running | exited <code> | interrupted`, `result_file`,
    `prompt_sha256`.
  - `foreman/<unit>.json` — `dispatch_id`, `rounds[]` (`round` (the review's round number; a
    `head-moved` entry carries the number the round would have had, reused by the next
    dispatch), `launch` (the launch count at dispatch), `head`, `phase ∈ fetched | prepared |
    collected | posted | kept | cleaned`, `dispatch_id`, `outcome` (the return word for a posted
    round, else `not run (<reason>)`), `posted_at`), `decisions[]` (`id, point, question,
    asked_at`), `rulings[]` (`decision, ruling, by, posted_at`); a decision is pending from its
    `decisions[]` entry until its `rulings[]` entry.
  - `worktrees/<unit>/` and `review/<unit>/pr<n>/`; `judges/<id>/question.md`,
    `round-<n>/<judge>.md`, `verdict.json`; `wave_<n>_report.md`; `journal.md`.

## 8. Spec review (phase 1) and the one review loop

`/superegm:review-spec <spec-path> [--reviewers design,zoom-out,…] [--astra on|off] [--leavemealone]`

The review loop below is implemented once, in U04, as helper subcommands plus
`skills/review-spec/references/review_loop.md`, and is consumed unchanged by `review-plan` and
by the foreman. The helper records and judges; the dispatching session dispatches.

- `superegm review open --kind spec|plan|head|integrate --artifact <path or unit id>
  [--sha256 <hex>] --reviewers a,b,c --runcard <id>` records the review id (with its cycle), the
  panel (1–6 reviewer ids from `design`, `zoom-out`, `comprehension`, `readiness`, `structural`,
  `style`, `codebase-details`, `change-review`, `set`; the kind's fixed first reviewer must be
  first) and the Astra lane state (`astra` is added for kinds `spec`, `plan` and `integrate` when
  enabled and installed). The panel cannot change after this. Later rounds review the artifact's
  **current** bytes; each round records the sha256 it reviewed (the helper hashes a spec; the
  caller passes `--sha256` for a plan body or a head).
- Each round the dispatching session dispatches the whole panel **concurrently** through the
  adapters, each goldfish receiving only the artifact, the standards the kind names, and from
  round 2 the prior round's report with the fixes marked; for kinds `spec`, `plan` and
  `integrate` the Astra lane runs alongside through the runner's `review` mode, launched by the
  elephant, fresh in round 1 and resumed after. The dispatching session records each reviewer,
  the lane included, with `superegm review record --review <id> --round <n> [--sha256 <hex>]
  --reviewer <id> --findings <file> --isolation clean|exposed:<what> --model
  <requested>:<effective> --effort <requested>:<effective>`, or `--not-run "<reason>"` when the
  dispatch did not complete. A reviewer with no findings is recorded with an empty file; a
  dispatch that did not complete is re-dispatched once within the round and then recorded
  `--not-run`; the Astra lane is never retried within a round and is stopped for the review
  after two incomplete runs. `--reviewer set` takes the `set` reviewer's whole file and keeps the
  findings whose `<location>` names the review's unit or no unit. On kind `head`, `--reviewer
  foreman` is accepted outside the panel for the helper's own findings (§11) and never counts
  toward every-reviewer-ran. A round's `what_ran` is **derived** by the helper from the round's
  reviewer records and, on a head, from `foreman/<unit>.json.rounds[].outcome`; no caller sets
  it, and it is stored with the round: `completed` when every panel reviewer has a record for
  the round (the Astra lane's being findings or `--not-run`) and, on a head, the foreman's entry
  is `posted`; otherwise `not run (<reason>)`, the reason being the first reviewer without
  findings or the foreman's own `not run` reason. Only a `completed` round counts toward the cap
  or can converge; the findings of any other round settle nothing and block nothing. A review
  whose two latest rounds under the current run card are not `completed` is **stalled**: the
  skill ends its invocation with the record (on a wave, the loop ends for that unit and the
  report names the reason); a re-typed skill opens a new run card and resumes the same cycle.
  The findings file holds one finding per line:

  ```
  <reviewer>-<round>-<n> | high|medium|low | <location> | regression: yes|no | <claim>
  ```

- Dispositions are `fixed | contested | declined | escalated | fix-design`, written by
  `superegm review settle --review <id> --finding <fid> --disposition <d> --runcard <id>
  [--owner | --judges <judges-id>]`. For a high or medium `contested` or `declined` the helper
  refuses without `--owner` in normal mode and without `--judges` in leavemealone-mode. The
  `foreman` finding that records CI not green is settled by no one: `collect` records it afresh
  each round from the CI file and omits it when CI is green, `review settle` refuses it, a
  builder's reply to it is ignored, and `judges question` never renders it. `escalated` means
  moved to a new unit or a decision point, and is settled. `fix-design` means the defect is in
  the spec and is refused on kind `head`. A ruling that overrules a finding settles it
  `contested`; one that upholds it leaves it unsettled, and on a head `collect` carries an upheld
  finding forward as a `foreman` high until a later builder reply marks it `fixed`.
- `superegm review status --review <id>` prints `round <n>: <clean|not clean>, regressions <k>,
  converged <yes|no|by ruling>, cap <yes|no>, stalled <yes|no>, sha256 <hex of the converged
  round>` and the trend line; exits 0 when converged, 5 when stalled, 2 at the cap without an
  `accept` ruling (and for ever after `stop`, until a new cycle), 4 when any finding is
  `fix-design`, 3 otherwise or when the review is not yet opened. The cap and stall predicates
  live here alone; every other subcommand and every skill asks `review status`.
- Between rounds the elephant fixes the artifact. Doctrine: change the thing, not the round. If
  two consecutive rounds regress on the same area, the next fix is a deletion, a narrowed contract
  or a smaller surface, not a patch, and the journal says what was removed.
- **At the cap** (exit 2) the skill requests a ruling (§13.2 point 2): for kinds `spec`, `plan`
  and `integrate`, continue one bounded round / accept the remainder / stop; for kind `head`, one
  more round / stop. `superegm review rule --review <id> --ruling continue|accept|stop [--owner |
  --judges <judges-id>]` records it, refuses `accept` for kind `head`, a second `continue`, and
  every ruling after `stop`; `accept` sets `converged: by ruling`; `continue` raises the cap by
  one. No further round starts while `review status` exits 2.
- Model tiering: panel goldfish run on `SUPEREGM_GOLDFISH_MODEL` at `SUPEREGM_GOLDFISH_EFFORT`
  (EGM's rules renamed); judges use their configured model and effort; builders use
  `config.builder`. The run card shows requested → effective.

Spec review specifics:
- `review-spec` opens a run card and the review `spec-<spec-slug>-c<n>` with
  `config.reviewers.spec` unless `--reviewers` is given; `design` is first.
- On convergence, `superegm approve-spec --spec <path> --runcard <id> [--leavemealone]` (EGM's
  `approve` with its heading and at-HEAD checks replaced by the commit it makes, `--evidence`
  dropped, and its clean check removed, since it commits by path): the spec must be tracked; its
  working-tree bytes must hash to the converged round's sha256 (for `--amend-units`, to the
  amended bytes); and the spec's last H2 must read `Units` after any numeric prefix. In normal
  mode the owner is asked to approve; in leavemealone-mode the converged record is the approval.
  `approve-spec` then commits the spec and `.superegm/config.json` by path, ignoring other
  changes in the tree, on the owner's current branch with the message `superegm: approve
  <spec-slug> at review <id>` and writes the record (`commit`, `sha256`, `handoff_id`); the owner
  pushes it to the base branch (§5). `superegm approve-spec --void --review <id>` sets
  `voided_by` when a `fix-design` finding is recorded; `graph` refuses a voided approval; a
  re-approval after a void keeps the `handoff_id` whenever `state.json` lists a filed unit.
  `approve-spec --amend-units` is §12's.

## 9. Plan (phase 2) and plan review (phase 3)

### 9.1 The plan is the issue body
`/superegm:plan <spec-path>` opens a run card, then `superegm graph` refuses unless an approval
record matches the spec's current sha256, and refuses while `state.json` carries a `handoff_id`
other than the approval's and `close` has not run: one handoff per store at a time. The
elephant composes the plan text in the file `state.json.plan` names (EGM's layout: title,
`Design:` line, `## 1. Issue template`, `## 2. Units`), keeping every unit's section and adding
one `### U<nn>: <title>` section per row of the spec's `## Units` not yet in it, and runs
`superegm graph --plan <file>` (copies the text into the store, parses, derives waves, renders
and hashes the **unfiled** bodies) then `superegm scan`. Filed units are frozen (§7): their
sections in the plan file must equal the stored ones. Nothing is committed under `docs/…/plans`.

Each unit section carries EGM's fields and the superpowers additions:

| Field | Rule |
| --- | --- |
| Objective | one sentence |
| Scope paths | `` `path` (create\|modify\|delete) ``, comma-separated; a path may be a directory |
| Design range | `` `path:start-end (heading)` `` into the frozen spec |
| Blocked by | `none` or unit ids |
| Shared files | `none` or `` `path`: after U01, before U05 `` items |
| Risk | `low\|medium\|high: reason` |
| Size | `S\|M\|L` by scope-path count (`L` is about twenty Step groups, the most a 48 KB body holds) |
| **Interfaces** | `Consumes:` and `Produces:` lines, one item per line (grammar below) |
| Definition of done | numbered items; item 1 is always `The test for each Step was committed before its implementation (checked by superegm tdd-order)`; every other item is one of ``Run `<command>` — <what passing means>``, ``Exists `<path>` ``, or `CI green on the head`; only `Run` items are commands |
| **Steps** | numbered groups, each: a `Write` line, the fenced test code, a `Run` line expecting FAIL, an `Implement` line, and a closing line that runs the same command, expects PASS and commits (grammar below); a rule family may be one Step whose test is parametrized |
| Decide before build | `- none` or `- D<n> <question> options: (a) <option>; (b) <option>[; …]; owner: <owner>; default: (a); blocking: yes\|no` — two or more options, the default among them |

Grammar (each line is one `scan` rule, each with a test):
- `Produces: <name>(<params>) -> <type>` for a Python interface, or `Produces: superegm <sub>
  <flags> → <stdout shape>; exit <codes>` for a helper subcommand, or `Produces: <file> key
  <path>` for a store field. Matching is on `<name>` (the identifier before `(`), the subcommand
  words, or the key path.
- `Consumes: <name> (U04)` — the same name form plus the producing unit; `scan` refuses a
  Consumes whose name no sibling's Produces defines, and a producing unit that is not a direct or
  transitive blocker.
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

  The `Write` line carries the test path in its second backtick span; the first `Run` line
  carries the Step's one command; the `Implement` line carries the implementation path in its
  last backtick span; the closing line names no command. Commit subjects carry the Step number as
  `test(S<n>)` and `feat(S<n>)`. The parsers of a body live in `superegm/body.py` and nothing
  else parses a body: `run_commands(body)` (the Step commands and the DoD `Run` commands),
  `step_paths(body)` (Step number, test path, implementation path), `dod_items(body)` (item
  number, kind `run` | `exists` | `ci`, value) and `consumes(body)` (name, producing unit);
  their callers are `scan`, `launch-builder`, `tdd-order`, `collect` and `judges question`.
- `## Review focus` lines: ``- U06: <input or failure mode> — <expected behaviour>; pinned by
  `<test name>` ``; the test name must appear in the owning unit's Steps.
- `## Global constraints`: one line each, exact values; rendered verbatim into every body.
- A `Decide before build` item with `blocking: yes` must be answered before the body can pass
  `scan`: `superegm decide --unit U07 --decision D1 (--answer "(b)" | --default) [--judges
  <id>]`, the owner's or the judges' choice among the item's own options. For an unfiled unit it
  rewrites the line in the plan file, re-runs `graph --plan` and re-renders that unit's body. For
  a filed unit it leaves the plan line, the body and `unit_<id>.md` as filed (EGM appended the
  answer to the unit file; here it reaches builders through the prompt file and head goldfish
  through `comments.md`, §11), records the answer in `state.decisions`, and writes the comment
  file EGM writes, re-headed `**Decision D<n>:**` (`DECISION_HEADING` in `body.py`); the calling
  skill posts it under a card whose skill lists `github-write`.

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
Scope: … · Blocked by: #<U04>, #<U06> · Shared files: … · Risk: … · Size: M
Branch: `superegm/<handoff-id>/U07` · Part of #<tracking>
```

The tracking issue's marker is `<!-- superegm:handoff=<id> unit=tracking spec=<spec sha256> -->`.

Rules `graph` and `scan` enforce (each a test; `graph` owns plan-shape rules, `scan` owns body
rules; there is no third checker):
- Body ≤ 49,152 bytes; a larger unit is refused with "split it".
- Numbered lists only. Never `- [ ]`. EGM's default issue template is replaced by the layout
  above and EGM's marker regex by the markers above.
- **Byte identity, as EGM does it today.** `body_sha256` and the write-list hash the dry run
  confirms cover the rendered body with EGM's placeholders `#<U04>` and `#<tracking>`; `apply`
  re-checks that hash, creates issues in blocked-by order and rewrites the placeholders as it
  goes; `verify` re-substitutes and compares normalised text. Blocked-by is also an issue
  relationship, set by `apply`.
- No placeholders: `TBD`, `handle edge cases`, `add appropriate validation`, `write tests for
  the above`, or a Consumes name no Produces line defines.
- Global constraints and review focus present in every body; every review-focus test appears in
  its owning unit's Steps; every Step group has both paths and its one command; every `D<n>`
  line has two or more options with the default among them.
- The marker line's spec sha256 equals the approval's; `graph` refuses otherwise.
- A filed unit's section equals the stored one; `graph` refuses otherwise (§7).
- No cycles in blocked-by; no shared-file chain that contradicts the blockers (EGM's `graph`).
- The raw-text mention and banned-term scan with `allowed_mentions` (EGM's `scan`).

### 9.2 Plan review
`/superegm:review-plan <spec-path> [--units U01,U02] [--reviewers readiness,set,…] [--leavemealone]`

- One review per unit, id `plan-<unit>-c<n>`, kind `plan`, over the unit's current rendered
  bytes, `readiness` first. A re-render between rounds is a new round of the same review;
  `apply` requires a body's `body_sha256` to equal the converged round's. Each `review-plan`
  round dispatches every unfiled unit that is not converged or whose current `body_sha256`
  differs from its converged round's; a `set` finding naming a converged unit reopens it as a new
  round.
- The reviewer id `set` is the readiness persona dispatched **once per `review-plan` round**
  over the set, for interface consistency and the cut: it receives the spec's `## Units` and,
  from every unfiled body, the Interfaces block and the Scope, Blocked by and Shared files lines
  only. Its one findings file is given to every unit's `review record --reviewer set`, which
  keeps the findings for that unit (§8). Any other reviewer receives one body, the approved spec
  at its hash, and every sibling's Interfaces block. Units run **concurrently**, and the goldfish
  within a unit's panel concurrently.
- The standard is `resources/document_standards/handoff-standard.md` (EGM's seven questions)
  plus three: 8, interfaces present and consistent; 9, every Step group complete and DoD item 1
  present; 10, global constraints and review focus present. A `fix-design` disposition makes
  `review status` exit 4; the skill then runs `approve-spec --void` and the spec returns to spec
  review.
- Readiness questions ("what would a builder still ask?") are findings of the `readiness`
  reviewer: a blocking question is `high`. There is no second loop and no second cap.

## 10. File (phase 4)

`/superegm:file <spec-path>` is EGM's handoff filing (`gate` → `dry-run` → `apply --yes` →
`verify`) with these changes:
- `gate --pass` requires `review status` exit 0 for every unfiled unit it passes and the unit's
  `body_sha256` to equal its converged round's; `apply` refuses otherwise. `gate --accept` goes.
- The dry run and the "Create" confirmation are against the same write-list hash `apply`
  re-checks; `dry-run` renders unfiled units only (§7). In normal mode the owner confirms; in
  leavemealone-mode the confirmation is mechanical and journaled `Create: automatic
  (leavemealone)`.
- `apply` appends the confirmed write list to `state.json.filings[]`; `verify` reads back every
  issue that list names and compares the stored body as §7 says; `base_at_start` is recorded on
  the first `apply`. Filed units are frozen (§7); a later filing (§12's append path) appends its
  own list and rewrites the tracking issue.
- Idempotent filing with marker recovery stays, re-pointed at the new markers. Labels are
  `superegm:unit`, `superegm:wave-<n>`, `superegm:handoff-<6 hex>`, `superegm:tracking`,
  `superegm:stopped`.
- Deviations during the build go in **comments** on the issue, never edits to the body. The
  builder posts `**Deviation (<kind>):** <text>` with kind `interface | dod | test | other`; when
  the kind is not `other` the same comment ends with `**Builder status:** BLOCKED` and its option
  lines (§11) and the builder stops. Such a deviation is ruled by a `**Ruling:** (<comment-id>)
  <option> — <reason>` from an author other than the builder account, naming that comment's id
  (§13.2); until then it is a `foreman` high (§11).

## 11. Wave, foreman, builder (phase 5): the contracts

`/superegm:wave <spec-path> [--leavemealone]`

This section states what the wave guarantees and what each actor may do. How the elephant's loop
observes events, orders a batch, folds a builder's exit with its status comment, retries an
`error`, resumes after a compaction, assembles a prompt file or reads a GitHub protection is the
U09, U09b, U10 and U10b plans' content, written as tests against these contracts.

**The repository's protection (checked by `launch`, recorded in the wave card).** Before any
builder is launched, `launch` fetches and refuses unless: the spec at `origin/<base>` hashes to
the approval's `sha256` and `.superegm/config.json` exists there; `origin/<base>` carries a
workflow triggered on `pull_request`; the builder token is set, is not the elephant's own login,
and is recorded with that login in the card; and the base branch carries an active protection,
in classic or ruleset form, that restricts updates to `<base>` to the owner with no bypass for
the builder account's role (a ruleset's restrict-updates or classic restrict-who-can-push, which
covers merging a pull request) and forbids force-push and deletion on `superegm/**`. Under that
protection the builder account can open PRs and never merge them; the owner, who alone updates
`<base>`, merges by hand; the plugin ships no approve or merge path, and the elephant and the
foreman hold no GitHub write but the review comment, the ruling and decision comments, and the
`superegm:stopped` label. `launch` also skips units labelled `superegm:stopped`, and counts a
unit in flight from its first launch until its latest round's `outcome` is `clean`, it has
landed, or it carries that label.

**The driver loop** runs in the main conversation, is the only long-lived actor, and is
event-driven: `superegm launch` marks the ready units up to `max_in_flight`; the elephant launches
a builder per marked unit; `superegm status --wait <s> --runcard <id>` (EGM's loop, reading
only and saving once on return, extended to read exit files and each unit's issue and PR
comments) returns **every** unreported change since its last save, one event line each, or
`deadline` when nothing changed. The event kinds are `head` (with its CI state), `status` (a
builder status comment), `exit` (a builder exit), `landed`, `closed` (a PR or issue closed by
hand) and `deadline`; the line form is U09b's. Invariants the U10b plan must pin, driving the
loop through `foreman dispatch`'s refusal (below):
- An event is reported once and never lost: `status --wait` saves only the fingerprints of the
  units it reported, and the elephant handles every line of a batch before calling it again.
- A base-branch move under an unchanged head is not an event; the foreman's merge-base check at
  `review post` is its handler.
- A head with pending or absent CI is not reviewed. A head with concluded CI whose unit's latest
  launch is terminal, which has had no round posted since that launch (no `rounds[]` entry in
  phase `posted` with `launch` equal to the latest launch's count), and whose unit has no
  decision pending (§7), is reviewed at the next batch, whether a `head` line or a `deadline`
  announced it; so a relaunched builder that contested every finding and pushed nothing is
  reviewed too, and a head whose round ended `target-moved` or `error` is reviewed again at the
  next batch. `superegm foreman dispatch` refuses, exit 1, whenever that predicate does not hold
  (U10); it is the one place the predicate is evaluated.
- When several heads are ready at once their foremen are dispatched in one message.
- A builder's `exit` and its `**Builder status:**` comment are one decision, never two.
- Lines for a stopped unit are ignored except `landed`. A launched unit whose PR is closed
  unmerged, or whose issue is closed while its PR is unmerged, is `stop` without a ruling (the
  owner has ruled); an interrupted launch is a point-3 question.
- The loop ends when every launched unit is clean, landed, stopped, stalled (§8), or waiting on
  a head whose CI was still pending or absent at two consecutive `deadline`s of this `wave`
  invocation, and no ready unit is unlaunched. After every batch, and at the end, the elephant
  runs `superegm report`, which rewrites `wave_<n>_report.md` (per unit: state, head, rounds,
  open findings, every non-terminal launch, every head with pending or absent CI, every stalled
  unit and why, every stopped unit and its unlanded dependants), and at the end closes the run
  card. The skill is re-typeable and resumes from the store without a second launch, ruling or
  review of anything already recorded. A pause at a decision point ends the loop; builders keep
  running; the next `wave` handles what they reported.

**Launching a builder** (`superegm launch-builder --unit U07 --round <n> --runcard <id>`, where
`--round` is the launch count). It refuses unless the unit is marked by `launch`, every earlier
launch is terminal, the builder token and profile pass §4's checks, and the issue body read back
equals the body the write list of the filing that created the unit's issue (`state.json.filings[]`)
stores for it, filled and normalised as `verify` compares. Every launch adds a fresh worktree
under `worktrees/U07/` on branch `superegm/<handoff-id>/U07` (round 1 from `origin/<base>`,
later rounds at the PR tip) and leaves earlier ones for `/superegm:clean`. It writes the prompt
file, which holds exactly: the issue body, `references/builder_orders.md`, every `**Deviation**`
comment, every `**Decision D<n>:**` and `**Ruling:**` issue comment **whose author is not the
builder account**, and from round 2 the foreman's review comments on the PR. The launched command
carries: the builder profile; `GH_TOKEN` from `builder.gh_token_env`, with the HTTPS push rewrite
and credential helper in its environment; `SUPEREGM_ROLE=builder` and `SUPEREGM_RUNCARD`;
`claude -p` with the prompt file's content, the configured model and permission mode; the
allow-list plus a push prefix for the unit's own branch and `Bash(<first word>:*)` for every
command `run_commands` returns from the body; `--output-format json` into the result file; and
the exit file on exit. The launch is recorded (`record-launch`), and `record-launch --exit
<code>` later records the exit. An allow-list containing `Agent`, `Skill` or bare `Bash` is
refused.

**The builder orders** (`references/builder_orders.md`, absorbing superpowers' implementer prompt
and the discipline of its receiving-code-review and test-driven-development skills): follow the
Steps in order, test first, one `test(S<n>)` commit then one `feat(S<n>)` commit per Step; run
every DoD `Run` command and paste each item's output in the PR body under its item number as a
fenced block; push with `git push origin <branch>` and never to any other branch; open a
**draft** PR whose body is the unit id, the DoD results in that form and `Closes #<issue>`
(later rounds update the existing PR); when a Step cannot be done as written, post the
`**Deviation (<kind>):**` comment of §10; from round 2, verify each review finding against the
code before changing anything, reply on the PR `**Reply <fid>:** fixed | contested — <reason>`,
and push; a `**Ruling:**` that says `finding upheld` means fix it, `finding overruled` means
leave it, and an option ruling `(<comment-id>) <option>` means follow that option; finish with
one comment `**Builder status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT` on the
issue; every builder comment except `**Reply <fid>:**` (on the PR) goes on the issue. A BLOCKED
or NEEDS_CONTEXT comment states the question and ends with two or more `- (a) <option>` lines,
the first the builder's own proposal. Wherever an absorbed skill says "ask your human partner",
the builder writes the question in that comment with status BLOCKED and stops. A builder never
spawns, never touches files outside its scope paths, never merges.

**The foreman** is a named subagent (`name: foreman-U07-<dispatch_id>`) dispatched through the
`superegm:foreman` adapter (`omitClaudeMd: true`; tools `[Agent, Bash, Read, Grep, Glob]`) in the
foreground, with `references/foreman_brief.md`, the unit id, the head, the wave run card, a child
card and the `dispatch_id` that `superegm foreman dispatch --unit U07 --head <sha> --runcard
<id>` wrote (that call also opens `head-U07-c<n>` with `config.reviewers.head` on the unit's
first dispatch of the cycle, supersedes any non-terminal round, writes the round entry's
`launch`, and refuses unless the dispatch predicate above holds). It runs **one round** and
returns one word plus one line:
- It re-reads the PR tip before `prepare` and returns `head-moved` when it differs from `--head`;
  that costs no round, and the round is recorded `collected (not run (head-moved))`. A merge base
  that moved before the round is the round's base.
- `prepare --dispatch <id>` is EGM's (fetch the PR and base refs, a detached review worktree, the
  diff, the CI JSON) plus `pr_body.md` and `comments.md` (the PR's and the issue's comments after
  the latest `posted_at`, each with its author, plus every `**Deviation**`, `**Decision D<n>:**`
  and `**Ruling:**` comment regardless of age).
- It dispatches the head's panel (`change-review` first; fixed in the run card) **concurrently**,
  without `name`, each goldfish receiving the unit file (its DoD is the head's standard), the
  frozen spec range, the diff, the CI file, `pr_body.md`, `comments.md`, the last posted round's
  findings with the builder's replies, and the worktree path, and records each with `review
  record --sha256 <head>`.
- `collect --dispatch <id>` records, through one `review record --reviewer foreman` call, as
  high findings: CI not green on this head; an `Exists` DoD item whose path is absent, or a `Run`
  item without its fenced output in `pr_body.md` (`dod_items`); a changed path outside the unit's
  Scope paths; a `tdd-order` failure (over the PR's commits in order, for each Step n a
  `test(S<n>)` commit touching that Step's test path precedes a `feat(S<n>)` commit touching its
  implementation path, and every `test(…)` commit touches only paths under `tests/`) not
  overruled by a later `**Ruling:**` from an author other than the builder account; a deviation
  of kind `interface`, `dod` or `test` not yet ruled (ruled when such a `**Ruling:**` names its
  comment id, §10); and every finding of the last posted round the builder replied `contested`
  to, which is unsettled until a ruling. It reads `**Reply <fid>:** contested — <reason>` lines
  into `builder_contested[]` as `{fid, reason}`, ignoring a reply to the CI finding.
- `review post --unit U07 --round <n> --dispatch <id> --runcard <child>` is EGM's posting guard
  moved into the helper: it never posts a header already present, posts only against the commit
  the round reviewed (that binding replaces EGM's head and base-branch refusal), through the
  pull-request reviews API, never `--approve` or `--request-changes`, after the raw-text scan,
  counts the round `posted` (writing `posted_at`) only when the response's `commit_id` is the
  reviewed sha, and refuses with exit 3 `target-moved` when the merge base moved since
  `prepare`, which the foreman records (`collected (not run (target-moved))`) and returns. When
  `review status` then exits 0, `review post` journals `U07 awaiting merge`.
- After `review post`, the return word is what `review status` implies, in this order: `error`
  first, when a step failed or a panel goldfish is still not run after its one re-dispatch, the
  round recorded `collected (not run (error: <reason>))` and nothing posted; then `contested:
  <ids>` when `builder_contested[]` meets an unsettled high or medium; `clean` on exit 0
  (**Clean**: CI green, every DoD item met, no unsettled high or medium, `tdd-order` passed, no
  unruled deviation, all of them findings in the record; **No regressions**: CI's suite green on
  the head and no high or medium finding a regression of a prior round's fix); `cap-reached` on
  exit 2; `revise` when an unsettled high or medium exists. A return that is none of the seven
  words is `error`, and the elephant records that round `collected (not run (error: no word))`
  itself.
- It never merges, never approves, never edits the owner's working tree, never removes a
  worktree, never launches a session, never convenes the judges, never infers that a builder died.

**What the elephant does with a word.** `clean`: the unit awaits merge and its slot is refilled.
`revise`: the next builder is launched (its prompt carries the review). `contested`: decision
point 1, then the ruling is posted on the issue as `**Ruling:** <fid> finding upheld (fix it) |
finding overruled — <reason>` and recorded with `review settle`, and the unit proceeds by
`review status` (converged → awaiting merge; at the cap → as `cap-reached`; else the next
builder). `cap-reached`: decision point 2, **one more round** (once; the next builder is
launched with the review) or **stop**. `error`, `target-moved`, `head-moved`: the head is
reviewed again at the next batch, unless `review status` reports the review stalled (exit 5),
which ends the loop for that unit. `blocked` (a `BLOCKED` or `NEEDS_CONTEXT` status, a builder
exit with no PR, an interrupted launch, or a third `blocked` on one unit without an intervening
head): decision point 3, recorded with `decision open` and, when ruled, `decision rule`; the
ruling is posted on the issue as `**Ruling:** (<comment-id>) <option> — <reason>` quoting the
question, then the next builder or `stop`; for an exit with no PR, an interrupted launch or a
third `blocked` the options are `relaunch`, offered once per unit, and `stop the unit`, and once
`relaunch` has been used the case is `stop` without a question. A decision is ruled only through
`decision rule`; a by-hand `**Ruling:**` comment rules deviations and `tdd-order` findings and
nothing else. `stop` (from any ruling or from the owner's by-hand close): the issue is labelled
`superegm:stopped`, kept open unless the owner closed it, the branch kept, the unit never
relaunched; it is listed in the wave report with its unlanded dependants; the owner lands it by
hand or closes it with those dependants and re-appends what is still wanted (§12).

**Landing.** A unit has landed when its watched PR is merged and its issue is closed as
completed, whoever closed it. Landing makes dependants ready. `/superegm:clean --unit U07`
(EGM's `prepare --clean` looped over the unit's review rounds, plus the removal of every builder
worktree whose launches are all terminal, dirty or not: the typed skill is the owner's decision,
and EGM's dirty refusal applies to review worktrees) is typed, `destructive-local`, refuses while
any launch or round is not terminal, and keeps what it cannot prove. `/superegm:interrupt --unit
U07 (--launch <n> | --round <n>)` is typed and records `interrupted` on a launch, or marks a
prepared round `collected (not run (interrupted: owner))`; an owner's decision is not a guess.

## 12. Merge and integration (phases 6–7)

- **Merge is human.** The absorbed `finishing-a-development-branch` offers two options: push and
  open a pull request as the owner, for a colleague's review (the owner's own branches need no
  PR: only the owner updates `<base>`); keep the branch as-is. Discard stays behind the typed
  word `discard`. "Merge back locally" is removed. A forced push is never offered.
- `/superegm:integrate <spec-path>` runs after every unit has landed or been closed by the owner
  (who closes a stopped unit's unlanded dependants with it): one round of the review
  `spec-<spec-slug>-integrate-c<n>` (kind `integrate`, `config.reviewers.integrate`) of the
  frozen spec against `git diff <base_at_start>..<base>`. Each high or medium is settled
  `escalated` with a new unit's id: the elephant appends rows to the spec's `## Units` with the
  note `(from integrate, review <id>)`, runs `superegm approve-spec --amend-units` (which
  re-records the approval at the new bytes without a review round, keeps the handoff id and
  refuses if any line outside `## Units` changed); the owner pushes it (§5) and then types `plan`
  → `review-plan` → `file` → `wave` for the new units only. The owner uses the same path by hand
  to re-append what a stopped unit still owed. The handoff closes (`superegm close`) when an
  integrate round has nothing to escalate.

## 13. The judge panel and leavemealone-mode

### 13.1 The judge panel
`/superegm:judges <question.md> [--evidence <paths…>]`

- Typed; advisory by default. The helper never dispatches a judge: `superegm judges open
  --question <file> --evidence <paths> --runcard <id> [--parent <id>]` records the question
  file's sha256, the evidence and the judges from `config.judges.members` and prints the panel
  id; the elephant dispatches the Claude judges through the `superegm:judge` adapter and the
  Astra judge through the runner, and records each with `superegm judges record --panel <id>
  --round <n> --judge <id> --verdict <file> --isolation …`.
- The question file's grammar: `## Q<n> <question>` followed by two or more `- (a) <option>`
  lines; a file may hold several questions; judges answer each by option id and may add a short
  reason and "what would change my mind". `superegm judges diff --panel <id> --round <n>`
  compares option ids and writes the neutral list of where positions differ; no one adds
  arguments between rounds.
- Three models from two vendors, each a goldfish through the `superegm:judge` adapter
  (`omitClaudeMd: true`, tools `[Read, Grep, Glob]`, `model: inherit`) with a per-dispatch model
  override (`fable` at max, `opus` at max), plus GPT-6 Astra through the claudex-loop runner's
  `review` mode on the question file when the runner is installed and reachable.
- Every judge reads only the question file and the listed evidence. The Astra judge runs with
  `SUPEREGM_ROLE=goldfish`.
- Round 1 is independent. From round 2 each judge receives every prior verdict verbatim plus the
  neutral diff, for the questions not yet converged. Judges run **concurrently**.
- `superegm judges verdict --panel <id>` computes convergence **per question** (the same option
  id from every judge), writes `judges/<id>/verdict.json` (each judge's model, vendor, effort,
  isolation, option per question per round; `degraded: true` when fewer than two vendors
  answered; `converged` per question), journals every applied answer, and exits 0 when every
  question converged / 2 otherwise. Rounds continue until every question converges or the cap of
  5; converged answers are applied as they converge, and the owner is paused only with the
  unconverged ones. When the runner is absent or the lane is down, the panel runs Claude-only and
  the record says so.
- The judge panel never changes a review panel, a reviewer set, or a run card's tiering.

### 13.2 Decision points and leavemealone-mode
These are the decision points of the workflow, and this list is the only one:
1. contesting or declining a high or medium finding in any review, including a builder's
   `contested` reply on a PR head (options: `finding upheld`, `finding overruled`; the
   elephant's or the builder's reason is copied verbatim as the overrule option's text; every
   such finding of a round is one question of one panel; the CI finding is never one);
2. a review at its cap: for a spec, plan or integrate review, continue one bounded round (once)
   / accept the remainder / stop; for a head, one more round (once) / stop;
3. an open question the elephant cannot answer from the frozen spec: a `blocking: yes` decision
   during `plan` (the options are the item's own); a builder's `BLOCKED` / `NEEDS_CONTEXT`
   status (the comment's own `- (a)` lines, plus `stop the unit`); a builder exit with no PR, an
   interrupted launch, or a third `blocked` without an intervening head (`relaunch`, offered
   once per unit; `stop the unit`);
4. the owner's approval of a converged spec in normal mode, and "Create" in normal mode.

In normal mode every point pauses for the owner. In leavemealone-mode (`--leavemealone` or
`config.mode`), at points 1–3 the skill runs `superegm judges question (--review <id> --round <n>
[--reason <fid>=<text>]… | --review <id> --cap | --unit <U> --decision D<n> | --unit <U>
--blocked (<comment-id> | launch <n>)) → <path>` to render the question file from the record
with the options named above, one panel per review round, runs `judges open --parent <its run
card>`, dispatches the judges as §13.1 says, and applies each converged answer (subject to
`min_vendors`) through `review settle --judges`, `review rule --judges`, `decide --judges`, or
`decision rule --by judges:<panel-id>` and a `**Ruling:**` comment the skill posts with `gh
issue comment` under the elephant's token, journaled as `Ruling (judges <id>, leavemealone): …`
so the owner can read and overturn it; the unconverged questions pause the owner with the
record. A ruling that chooses a deviation of kind `interface` is also posted as `**Ruling:**` on
every filed issue whose body consumes that name (`consumes`, §9.1). Point 4 is mechanical in
leavemealone-mode (§8, §10). A foreman never convenes the judges; the elephant does. **Merge is
excluded**: no mode makes a machine approve or merge.

## 14. Skill and adapter disposition

Naming: adapter file `.claude-plugin/agents/<id>.md`, frontmatter `name: <id>`, persona
`agents/<id>.md`, invoked `superegm:<id>`, reviewer list entry `<id>`.

| Source | In SuperEGM as | Effects | Invocation | Caller | Change |
| --- | --- | --- | --- | --- | --- |
| brainstorming (sp) | `brainstorming` | working-tree | auto | owner, phase 0 | writes `docs/specs/YYYY-MM-DD-<topic>-design.md` (path changed from `docs/superpowers/specs/`) ending in `## Units`; the gate's next step is `/superegm:review-spec`; the builder check and the visual companion removed |
| egm-draft (egm) | `draft` | working-tree | typed | owner, phase 0 | "draft a spec from a brief when brainstorming was skipped"; template ends in `## Units` |
| egm-review + egm-review-loop + egm-resolve (egm) | `review-spec` (+ `references/review_loop.md`, `references/resolve.md`) | external: state-store, start-session | typed | owner, phase 1 | §8; the stage skills become references; "max 1 re-audit" goes; owns the Astra review lane |
| egm-handoff planning half + writing-plans (sp) | `plan` | external: state-store, start-session, github-write | typed | owner, phase 2 | §9.1; `github-write` for the decision comment on a filed unit |
| new | `review-plan` | external: state-store, start-session | typed | owner, phase 3 | §9.2 |
| egm-handoff filing half | `file` | external: github-write, state-store | typed | owner, phase 4 | §10 |
| egm-wave + SDD implementer prompt (sp) | `wave` (+ `references/foreman_brief.md`, `references/builder_orders.md`) | external: start-session, github-write, remote-branch, state-store | typed | owner, phase 5 | §11; Claude goldfish only on heads |
| new | `interrupt` | external: state-store | typed | owner, phase 5 | §11 |
| new | `clean` | external: destructive-local, state-store | typed | owner, phase 5 | §11 |
| finishing-a-development-branch (sp) | same name | external: github-write, remote-branch, state-store | typed | owner, outside a wave | no local merge, no forced push; the PR as the owner |
| new | `integrate` | external: state-store, start-session | typed | owner, phase 7 | §12 |
| new | `judges` | external: start-session, state-store, github-write | typed | owner (leavemealone skills call the `judges` helper subcommands directly) | §13 |
| test-driven-development, systematic-debugging, verification-before-completion (sp) | same names | working-tree | auto, phase-gated | owner fixes on a filed unit's branch (builders invoke no skills; the orders carry the discipline) | the phase sentence |
| writing-skills (sp) | same name | working-tree | auto | owner, maintaining this plugin | |
| using-superpowers (sp) | `using-superegm` | none | hook + auto | every elephant session (the builder profile has no plugins) | the dispatcher text; one platform reference |
| egm-drift-report (egm) | `drift-report` | working-tree | typed | owner, after `integrate` | writes `<date>_DRIFT_REPORT.md` |
| egm-bootstrap (egm); executing-plans, subagent-driven-development, requesting-code-review, receiving-code-review, dispatching-parallel-agents, using-git-worktrees, diagnosing-superpowers (sp); egm-brainstorm (egm) | **retired** | | | | no caller in the workflow; their surviving content lives in `builder_orders.md` and `brainstorming` |

Adapters in `.claude-plugin/agents/`: the reviewers `design`, `zoom-out`, `comprehension`,
`codebase-details`, `readiness`, `structural`, `style`, `change-review`, `judge` (tools `[Read,
Grep, Glob]`, `omitClaudeMd: true`); and `foreman` (tools `[Agent, Bash, Read, Grep, Glob]`,
`omitClaudeMd: true`). EGM's `synthesizer` and `bootstrap-orchestrator` are dropped.

## 15. Repository, packer, tests

- Repository `gsVAM/superegm`; plugin `superegm`; marketplace `superegm` (source `./`); commands
  `/superegm:<skill>`; version `1.0.0`.
- Layout: `plugin.json`; `skills/<name>/{SKILL.md, references/, assets/icon.svg,
  test_scenarios.yaml}`; `agents/*.md`; `.claude-plugin/{plugin.json, marketplace.json, icon.png,
  agents/*.md}`; `hooks/{hooks.json, run-hook.cmd, session-start}`; `resources/`; `scripts/
  {pack_plugin.py, prepare_release.py}`; `.github/workflows/tests.yml`; the helper under
  `skills/plan/scripts/`: `superegm.py` (`main()` only) and the package `superegm/` with
  `__init__.py` (the store, `atomic_write`, `journal`, `spec_slug`, `require_runcard`,
  `require_frozen_units`, the run card writers, EGM's `gh` wrapper with its retries, and
  subcommand discovery), `body.py` (the body parsers `run_commands`, `step_paths`, `dod_items`,
  `consumes`; EGM's `fill_numbers` and `normalise`; the marker regex and `DECISION_HEADING`),
  and one module per subcommand; `tests/unit`, `tests/fixtures`,
  `tests/integration/test_claude.py`; `docs/{index,getting_started,claude,faq,privacy,releases}.md`.
  How modules name themselves and attach to subcommand groups, where the fake `gh` test harness
  lives and how units extend it, and how the two source trees are brought in and excluded from
  the repository-walking tests while they exist, are the U01 and U03 plans' decisions, each a
  test.
- The packer is EGM's with one host, the three-file hook rule and hash check, the `effects`
  checks, the superpowers files and the helper package in its allow-list, and EGM's scan for
  private strings; its output goes to a temporary directory in tests and to the release
  directory in `prepare_release.py`, which builds one archive and names `gsVAM/superegm`.
- Tests: EGM's unit tests are kept where the form they pin is unchanged, amended by U01 where
  the host, the names or the file set change, and rewritten by the unit that changes a form it
  pins (each unit tests in its own file; `test_helper.py` is U03's alone, and U03 moves every
  test of a subcommand a later unit changes into that unit's named test file). Every new
  behaviour in §6–§13 has a test in the unit that builds it; each unit's plan names its test
  files. The freshness test and every Codex-host test are deleted.
- Each unit's plan lists and removes every sentence, docstring or example in its files that
  names a mechanism §3.1 removed or a form this spec changed.
- Install: `claude plugin marketplace add gsVAM/superegm` then `claude plugin install
  superegm@superegm`. The README tells the owner to disable `egm@egm-astra` and
  `superpowers@claude-plugins-official` first; to create the builder account, its token and an
  empty builder profile; to set the branch protection of §11 (updates to the base branch
  restricted to the owner with no bypass for the builder account's role; `superegm/**` protected
  from force-push and deletion) and a workflow triggered on `pull_request`; and to run reviews
  from a profile without SubagentStart hooks.

## 16. What is left to the builder

- The helper's argparse surface beyond the names and contracts in §17: `init`, `runcard
  open|close`, `approve-spec [--amend-units | --void | --leavemealone]`, `graph`, `scan`,
  `review open|record|settle|status|rule|post`, `gate`, `dry-run`, `apply`, `verify`, `status
  [--wait]`, `launch`, `launch-builder`, `record-launch [--exit]`, `foreman dispatch --head`,
  `collect`, `prepare`, `tdd-order`, `decide`, `decision open|rule`, `interrupt`, `clean`,
  `report`, `close`, `judges open|diff|record|verdict|question`.
- The hook script's exact text, as long as it carries the dispatcher rule and the phase rule.
- Journal line formats, as long as every line is written by the subcommand that wrote the fact.
- The judge persona's wording.
- Every mechanism §11 names as the plans' content: the event grammar's line form, the batch
  order, the folding, the retries, the resume derivation, the prompt file's assembly, the
  protection reads' field forms.

## 17. Units

The unit graph for building SuperEGM 1.0.0 (thirteen units). Each unit's plan must fit 48 KB.
Interfaces are subcommand contracts and file keys unless marked `py`. A Consumes producer may be
a transitive blocker. After U01 every §14 skill folder and adapter exists (the new ones as
stubs), so later units modify and never create skill folders, adapters or personas.

| Unit | Scope | Blocked by | Size |
| --- | --- | --- | --- |
| U01 | Skeleton and absorption, packer-test-driven: the kept files of superpowers 7.0.0 and EGM 9bc49d4 brought in under the §14 names, stubs for every new skill, adapter and persona, the helper renamed and its tests kept green under EGM's forms; the Codex host, visual companion, synthesizer, bootstrap and retired skills not kept; licences and notices; manifests; packer; CI workflow; the test amendments the host and name changes need; CI green | — | L |
| U02 | The hook and effects: `using-superegm`, `hooks/`, role silence, manifest hash; `test_effects.py` and the packer's effects checks; the frontmatter, harness line and phase sentence of every SKILL.md; the §14 Change-column edits of the superpowers skills, `draft` and `drift-report`; `finishing-a-development-branch` without merge | U01 | M |
| U03 | Store, run cards, helper package: `superegm/__init__.py` and `body.py` as §15 says (the four body parsers, `fill_numbers`, `normalise`, the markers, `DECISION_HEADING`); each absorbed subcommand in its own module; `init`; the writer partition; `runcard open\|close` with child cards, the artifact rule and the card writers; effect gating in every absorbed writing subcommand; `require_frozen_units` replacing EGM's whole-plan checks in `status`, `launch` and `prepare` (§7); config and label renames with their tests in `test_helper.py`; the `approvals/` schema with `handoff_id`; the `foreman/<unit>.json` schema; the fake `gh` harness; `defer` and `--published` removed | U01 | L |
| U04 | The review loop and spec review: `review open\|record\|settle\|status\|rule`, `references/review_loop.md`, the cap and stall predicates, cycles, sha per round, the derived `what_ran`, regression marking, the `foreman` and `set` reviewers in `review record`, the findings-file grammar, `--kind integrate`, `converged_round`, the Astra review lane, the `review-spec` skill body, `approve-spec` with `--void`, `--amend-units`, the `Units` check and `handoff_id` | U02, U03 | L |
| U05 | Plan: the unit schema, the Interfaces grammar in `scan.py` over `body.py`'s parsers, the body template with EGM's placeholders and the new markers, `graph --plan` and `scan` rules incl. decision options, frozen units and one handoff per store, body hashing as EGM does it, `decide`, the `plan` skill body | U02, U03 | L |
| U06 | Plan review: the `review-plan` skill body, the `set` reviewer and its inputs, per-unit reviews keyed `plan-<unit>-c<n>`, which units a round dispatches, handoff standard questions 8–10, `fix-design` to `approve-spec --void` | U04, U05 | M |
| U07 | File: `gate`/`dry-run`/`apply`/`verify` on the confirmed write list, `filings[]`, the tracking issue in the latest list, `gate --accept` removed, marker recovery on the new markers, `base_at_start`, the labels incl. `superegm:stopped` and the 6-hex handoff label, leavemealone "Create", the `file` skill body | U04, U05 | M |
| U08 | Judges: the `judges` skill body, `judge` adapter and persona, the question-file grammar with several questions, `judges open\|diff\|record\|verdict` with per-question convergence, child card, Astra judge lane with degradation, `min_vendors` | U02, U03 | M |
| U09 | Builders: `launch` with every §11 precondition (the protection, the `pull_request` workflow, the token, the in-flight count), `launch-builder` with its refusals and a fresh worktree per launch, the launched command's environment, the prompt file and the allow-list, `builder_orders.md` incl. the PR body's DoD-results form, `launches/` with the exit file, `record-launch [--exit]`, `interrupt`, `clean` | U02, U03 | L |
| U09b | Events: `status --wait` returning every unreported event, the six event kinds and the line form, the exit-and-status folding | U09 | M |
| U10 | Foreman: `foreman` adapter and brief, `foreman dispatch --head` with the dispatch-predicate refusal and the round entry's `launch`, the pre-`prepare` head check, `prepare --dispatch` with `pr_body.md`, `comments.md` (after `posted_at`, plus the aged comments) and the last round's findings, `collect` with the foreman findings (incl. scope paths) and the contested reads, `tdd-order`, `review post` with `posted_at`, its exit 3 and the `awaiting merge` journal fact, the return-word order | U04, U09 | L |
| U10b | The driver: the `wave` skill body with the loop's invariants as tests through `foreman dispatch`'s refusal, the batch order, the resume derivation, `report` after every batch, the end condition incl. stalled and CI-waiting units, what the elephant does with each word, `decision open\|rule` | U09b, U10 | M |
| U11 | leavemealone routing and finish: `judges question` and its forms, the §13.2 wiring at points 1–3 in `review-spec`, `review-plan`, `plan`, `wave`, the interface-deviation fan-out; `integrate` and `close`; docs and the README (install notes, the builder account and profile, the protection, the Licence paragraph); release 1.0.0 packed by `prepare_release.py` | U06, U07, U08, U10b | M |

Shared files: `test_helper.py` is U03's alone. Each workflow SKILL.md stub U01 creates is filled
by the unit that owns its section after U02 has set its frontmatter and lines, and edited again
only by U11; U02 is a blocker of every one of them. `README.md` is U01's (skeleton) and U11's
only. The `status`, `launch` and `prepare` modules are edited by U03 and then by U09b, U09 and
U10 respectively, which U03 blocks. No other file is edited by two units their blockers do not
order.

Interfaces (the names the plans will carry):
- U01 → all: the absorbed `state.json` keys and subcommands with EGM's contracts until a later
  unit changes them.
- U03 → U04–U11: `superegm runcard open --skill <s> --artifact <a> [--parent <id>] [--mode <m>]
  → <id>`; `superegm runcard close <id>`; every writing subcommand takes `--runcard <id>` and
  exits 1 with `runcard: <reason>` under the §6 artifact rule; `superegm init`;
  `approvals/<spec-slug>.json` per §7; `foreman/<unit>.json` per §7 (`rounds[]` with `launch`,
  `outcome`, `posted_at`; `decisions[]`; `rulings[]`); `handoff_units.json` key
  `units[<id>].body_sha256` per §7 (its values are written by U05's `graph --plan` and absent
  until then); `state.json` key `filings[]` per §7 (written by U07's `apply`, absent until then);
  py: `store(repo_root) -> Store`, `Store.path(kind, *parts) -> Path`, `atomic_write(path,
  obj)`, `journal(store, line)`, `spec_slug(path) -> str`, `require_runcard(args, skills) ->
  dict`, `require_frozen_units(handoff) -> None`, `open_runcard(store, skill, artifact,
  parent=None) -> str`, `card_add(store, id, key, item)`, `gh(args, *, token=None) -> str`,
  `run_commands(body) -> list[str]`, `step_paths(body) -> list[tuple[int, str, str]]`,
  `dod_items(body) -> list[tuple[int, str, str]]`, `consumes(body) -> list[tuple[str, str]]`,
  `fill_numbers(body, numbers, tracking=None) -> str`, `normalise(text) -> str`, `MARKER_RE`,
  `DECISION_HEADING`; the fake `gh` harness's extension point.
- U04 → U06, U07, U10, U10b, U11: `review open … → <review-id>`; `review record …` (incl.
  `--reviewer set` and `--reviewer foreman`); `review settle …`; `review status --review <id> →
  one line; exit 0 converged / 5 stalled / 2 cap / 3 open or unopened / 4 fix-design`; `review
  rule …`; `reviews/<review-id>/review.json` keys `converged`, `converged_round`, `rulings[]`;
  `round-<n>.json` keys `artifact_sha256`, `builder_contested[]` of `{fid, reason}`, `what_ran`;
  `approve-spec` writes `approvals/<spec-slug>.json` with `handoff_id`.
- U05 → U06, U07, U11: `graph --plan <file>` writes `handoff_units.json` with
  `units[<id>].body_sha256` and `unit_<id>.md`; `scan → exit 1 with "<rule>: <line>"`; `decide
  --unit <U> --decision D<n> (--answer "(<id>)" | --default) [--judges <id>]` and the comment
  file it writes.
- U07 → U09, U11: `state.json` keys `base_at_start`, `filings[]`.
- U08 → U11: `judges open … → <panel-id>`; `judges record …`; `judges diff …`; `judges verdict
  --panel <id> → verdict JSON; exit 0 every question converged / 2 not`; the question-file
  grammar.
- U09 → U09b, U10, U10b, U11: `launch-builder --unit <U> --round <n> --runcard <id> → command
  line; exit 1 with the refusal`; `record-launch --unit <U> [--exit <code>]`;
  `launches/<unit>.json` per §7 (`launches[].round`, `launches[].status`,
  `launches[].result_file`, `launches[].prompt_sha256`); the `**Deviation**`, `**Reply <fid>:**`,
  `**Ruling:**` and `**Builder status:**` headings, the option-line form and the PR body's
  DoD-results form.
- U09b → U10b: `status --wait <s> --runcard <id> → one or more event lines`; the six event kinds.
- U10 → U10b, U11: `foreman dispatch --unit <U> --head <sha> --runcard <id> → <dispatch_id>
  <child-card>; exit 1 when the dispatch predicate fails`; `foreman-<unit>-<dispatch_id>` returns
  `clean | revise | contested: <ids> | cap-reached | target-moved | head-moved | error`; `review
  post … → exit 0 posted / 3 target-moved`.
- U10b → U11: `report`; `decision open --unit <U> --point <1|2|3> --question <file> → <id>`;
  `decision rule --unit <U> --decision <id> --ruling <text> --by <login | judges:<panel-id>>`;
  the `wave` skill's decision-point hooks.

Waves: {U01} → {U02, U03} → {U04, U05, U08, U09} → {U06, U07, U09b, U10} → {U10b} → {U11}.
