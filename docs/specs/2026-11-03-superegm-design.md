# SuperEGM — design

Date: 2026-11-03. Status: 1.0.0 released from review cycle 2 (round 5, the cap; cycle 1 ended at
round 6 by the judges' ruling `q-close`: a new approach, not another patch; those cycles are
records outside the store); amendment 2 is under its own spec review for 1.1.0 in the store's
own numbering (cycle `spec-2026-11-03-superegm-design-c2`). Owner: gsVAM.
Inputs: the brainstorm brief (stream 4); the SuperEGM judge-panel verdict (converged, round 2 of
5); the cap-panel verdict on EGM 0.2.1; superpowers 7.0.0 and the EGM Astra fork at commit
9bc49d4, both surveyed file by file; six goldfish rounds of cycle 1 (75, 75, 74, 61, 53, 65
findings; highs 27, 14, 12, 6, 3, 7) and rounds 1–4 of cycle 2 (50, 53, 49, 54; highs 5, 3, 1,
2) with round 5 ruled at the cap; three judge rulings (`q-wave`, `q-cap`, `q-close`). In cycle 2, §11 states the wave's
contracts and invariants only; its mechanics belong to the U09/U09b/U10/U10b plans, where they
become tests; the self-build's plumbing belongs to the U01/U03 plans. The spec says what; the
plans say how.

Amendment 1 (2026-11-03): §9.1 plan-grammar simplification, §9.2 proportion angle, §17 rows U04/U05/U06/U09; owner-approved by text.
Amendment 2 (2026-11-04): §9.3 Orient (graphify-backed), §9.1/§10 adopted issues, §11 owners set and PR block, the builder-token recipe and `doctor`, §17 units U12–U14, with the §2, §3, §3.1, §4, §4.1, §5, §6, §7, §9.1, §9.2, §14, §15 and §16 lines they need; owner-approved by text.

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
judges could not settle, or to a stalled review named in the record (§8), merges, and types the
next phase. Nothing is merged by a machine. Every review, verdict and launch is on disk with its
isolation recorded.

## 2. Vocabulary

| Word | Meaning in SuperEGM |
| --- | --- |
| **owner** | the human, under the GitHub logins `config.owners` names (one person, possibly several logins; §11). Approves and freezes specs, rules when the judges cannot, reviews and merges pull requests. An administrator of the repository. §11's fence is that the builder account can never update the base branch; those logins (and, under an organization's ruleset, the members of `config.owner_team`) may. |
| **elephant** | the main session. Holds context, orchestrates, launches headless sessions, dispatches foremen and goldfish. Never reviews its own work, never settles a finding against itself, never writes the store itself. |
| **helper** | the plugin's one Python program (§15), run as `superegm <subcommand>`. The only writer of the store. It never dispatches an agent. |
| **store** | the per-repository directory `artifacts_dir` (§7) holding every record SuperEGM writes. `.superegm/config.json`, committed in the repo, is its pointer and configuration. |
| **adapter** | a Claude Code agent definition `.claude-plugin/agents/<id>.md` with frontmatter `name: <id>`, fixed `tools`, and `omitClaudeMd: true`, whose body reads the persona `agents/<id>.md`. Invoked as `superegm:<id>`. A review panel lists reviewer ids; every reviewer id except `set`, `astra` and `foreman` is an adapter id. |
| **dispatching session** | the elephant or a foreman: the session that invokes adapters with the Agent tool and records each dispatch. |
| **goldfish** | a fresh read-only reviewer dispatched through an adapter with tools `Read, Grep, Glob`. Sees only the artifact and the evidence it is handed. Never spawns. |
| **judge** | a goldfish with a model override that answers a question file by option id instead of reporting findings. |
| **foreman** | a sub-elephant: a named subagent dispatched through the `superegm:foreman` adapter, in the foreground, to run one review round on one PR head and return one word. Its memory is `foreman/<unit>.json` and the PR's comments, never its context. |
| **builder** | a fresh headless local Claude session whose brief is one issue body, the builder orders, the repository's PR block when configured, the unit's orient text (§9.3), the rulings posted on its issue, and from round 2 the foreman's reviews of its own branch. Writes code in its own worktree under the **builder account**, commits test-first, opens a draft PR. Not a goldfish: it writes. Never spawns. |
| **builder account** | a second GitHub account with write access and no administrator or bypass role, whose token the elephant holds (`config.builder.gh_token_env`). Every PR a wave opens is authored by it, and under §11's protection its token cannot update the base branch, so nothing a wave runs can merge. |
| **Astra lane** | an optional extra reviewer (of a spec or a plan) or judge on a non-Claude model (GPT-6 Astra) driven by the external `claudex-loop` runner (a Python CLI over the Codex CLI). Launched by the elephant from the main conversation, never through an adapter. Recorded `not run (<reason>)` when the runner is absent or its lane is down. Not used on PR heads in v1. |
| **unit** | one buildable piece of a frozen spec: one issue, one branch, one PR. Ids `U01`, `U02`, … are stable for the life of a handoff. |
| **handoff** | one run of plan → file → wave → integrate for one frozen spec. Its id (§7) names the branches, the issue marker lines and `state.json`, and never changes while any unit is filed. One handoff per store at a time (§9.1); `close` ends it (§12). |
| **wave** | the set of units whose blockers have all landed, launched together. At most `max_in_flight` units are in flight at once; a unit is in flight from its first launch until it lands, is stopped, its latest round's outcome is `clean` (§7), or the elephant names it idle (stalled or CI-waiting, §11), and a freed slot is refilled. |
| **head** | the commit at the tip of a unit's PR branch when `prepare` fetches it (§11). |
| **round** | one review of one artifact (a spec, a unit's plan body, or a PR head): dispatch, findings, verdict. Rounds are numbered per review; a round that is not `completed` (§8) does not count toward the cap. |
| **clean** | the verdict on a round with no unsettled high or medium finding (§5). The destructive skill is always written `/superegm:clean`. |
| **stalled** | a review whose two latest rounds under one run card are not `completed` (§8). It ends the invocation for that artifact; it is not a cap and not a pause. |
| **landed** | a unit whose watched PR is merged into `<base>` and whose issue is closed as completed, whoever closed it. Only landing makes dependants ready. |
| **stopped** | a unit a ruling or the owner ended: issue open under `superegm:stopped` (or closed by the owner), branch kept, never relaunched; the owner lands it by hand or closes it with its unlanded dependants and re-appends what is still wanted (§12). |
| **DoD** | definition of done: the numbered, checkable items in a unit's body; the standard every head review is judged against. |
| **review panel** | the 1–6 reviewers written into a run card for one artifact. Fixed for every round. |
| **judge panel** | the judges (three models from two vendors) consulted until every question converges. |
| **run card** | the on-disk record of one typed invocation: skill, artifact and its hash, review panel, model tiering, mode, parent card if any, what it produced. Every effect requires an open one; every round records the top-level card it ran under. |
| **effect** | anything that leaves the working tree: GitHub writes, remote branches, starting a session or worker, writing the store, destructive local operations. |
| **leavemealone-mode** | the mode in which every decision point listed in §13.2 goes to the judge panel first; the owner is paused only with the questions the judges do not converge on within their cap. |
| **graphify** | an external, optional CLI (the PyPI package `graphifyy`, so spelled; the command `graphify` on `PATH`) that extracts a code graph from a directory by AST with no model (its headless `update`; `GRAPHIFY_OUT` names where its `graphify-out/` goes) into `graph.json`: nodes with `source_file` (relative to the directory it scanned), `source_location` and an integer `community`; edges marked EXTRACTED, INFERRED or AMBIGUOUS with a confidence. `orient` (§9.3) reads that file and nothing else of graphify's; nothing requires it. |

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
   control; §4 says how they are recorded. The `## Read first` section of an orient file, §9.3,
   the one place such text enters it, is the repository's own documentation handed to the
   readiness goldfish on purpose and recorded on its dispatch as `exposed:orient <tree sha>`: not
   this.)
3. A builder that saw the brainstorm, the planning session's context, or anything beyond its
   issue body, the frozen spec range that body cites, the builder orders, the unit's orient text
   and the repository's `pr_block_file` text (both inside its prompt file, §9.3 and §11), the
   rulings posted on its issue, and the foreman's reviews of its own branch (the target
   repository's CLAUDE.md and its own hooks excepted: a builder is a session in that repository).
4. An effect without an open run card.
5. A machine approval or merge, or a "merge locally" option anywhere in the plugin.
6. The elephant settling a high or medium finding on its own artifact.
7. A pause that reaches the owner in leavemealone-mode without a judge record showing
   non-convergence. (A stall, §8, is an ending, not a pause: the invocation ends naming the
   reviewer and reason that did not run.)
8. A guess about liveness. SuperEGM never infers that a runner, builder or session is dead from
   file silence. Termination is proved only by a terminal status in a result file, by an exit
   file the launched command wrote, or by the owner's typed interrupt.
9. A code-aware Markdown mention scanner. The scan is raw text plus an allow-list.
10. A ruling, decision, review or close that the builder account wrote being honoured as the
    owner's or the judges'.

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
  the `head-moved` return and the pre-`prepare` tip check (`prepare` reviews the tip it fetches);
  a caller-written `what_ran` (it is derived, §8); the owner's own pull request opened as the
  builder account; U07's claim on `status`, `launch` and `prepare` (one U03 check replaces EGM's
  whole-plan checks there); any contest or settle of the CI finding (it is settled by no one,
  §8); the required non-author review and its administrator exemption; `approve-spec`'s
  tree-clean and tracked preconditions (it adds and commits by path); the worktree-reuse guard
  (a fresh worktree per launch); the hook canary and its transcript fixture (it re-derived a §4
  platform fact from a hand-made file); the double-`error` decision point (a stalled review
  ends its invocation, §8); any round record the elephant writes itself (`review post` and
  `foreman dispatch` write a head round's fate); the unfiled clause of `require_frozen_units`
  (it compared two copies one subcommand writes); a packer scan for private strings (EGM has
  none).
- **Amendment 2: a model-written orientation summary.** Rejected: a summary is a second opinion
  the goldfish cannot check; the extractor copies what exists.
- **Amendment 2: the extractor alone, without graphify.** Kept as the fallback; the owner asked
  for graphify's call graph and communities where it is installed, and the two files have one
  form either way.
- **Amendment 2: linking a unit to an existing issue instead of adopting it.** Rejected: two
  issues for one unit; the adopted issue keeps its number, comments and subscribers.
- **Amendment 2: a single `owner` login instead of the `owners` set and `owner_team`.** Rejected
  by the owner: one person uses several logins, and an organization's ruleset names a team.
- **Amendment 2: `doctor` folded into `launch`'s refusals.** Rejected: the owner needs the checks
  before a wave, with no run card and no effect.
- **Amendment 2: a `pr_body_template` config key instead of `pr_block_file`.** Rejected: the
  block is the repository's own text and stays in the repository.

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
  command's environment, never written to the shared git config. `git worktree add` refuses a
  branch another worktree has checked out.
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
  the owner, with no plugins, no hooks and no `CLAUDE.md`; `launch-builder` refuses otherwise (the
  hooks refusal is 1.1.0's, U14).

**Liveness and destruction (EGM round-12 doctrine, binding)**
- A builder launch is **terminal** when its exit file exists (the launched command writes
  `<result-file>.exit` on any exit) or when the owner's typed `/superegm:interrupt` recorded
  `interrupted`. An Astra review run is terminal when its `result.json` says `completed` or
  `failed`. A round is terminal in phase `posted`, or `collected` with a `not run` reason.
  Nothing else is terminal; silence proves nothing.
- Removing a worktree is a destructive decision and is never taken on a guess: `/superegm:clean`
  refuses while any launch or round of the unit is not terminal, and keeps what it cannot prove.
- A round is never re-prepared: `foreman dispatch` collects any non-terminal round of the unit as
  `not run (superseded)` before it writes a fresh `dispatch_id`, except a `collected` round whose
  review is already on the PR (§11), which it counts `posted`.

### 4.1 Risks and mitigations

| Risk | Impact | Mitigation | Unit |
| --- | --- | --- | --- |
| Runaway spend (goldfish rounds, judge rounds, a builder that blocks on every relaunch, a reviewer that never completes) | a night costs more than it returns | the caps (a review is at its cap when its counted rounds ≥ 5 + its single `continue`; 5 judge rounds per decision, one panel per review round; `relaunch` offered once per unit, then `stop`; a third `blocked` on one unit without an intervening head is a point-3 question) and the stall rule (§8) and `max_in_flight` bound one phase; a phase never chains into the next | U04, U08, U09, U10b |
| GitHub rate limits or half-finished writes | issues created twice, links missing; polling starved | EGM's marker recovery and retry handling, kept; `apply` records its list before its first write; `verify` reads everything back; `status --wait` polls at EGM's interval | U07, U09b |
| A builder dies without an exit file, or exits without a PR | its unit waits | the exit file is written by the shell on any ordinary exit; an exit without a PR is decision point 3; a hard kill is ended by the owner's `/superegm:interrupt`, itself a point-3 question; the wave report, rewritten after every batch, lists every non-terminal launch | U09, U10b |
| Two foremen on one unit after a compaction | duplicate rounds and posts | `foreman/<unit>.json.dispatch_id`, written by `foreman dispatch` and required by `prepare --dispatch`, `collect` and `review post`; `review post` never posts a header already present | U10 |
| A builder merges a PR, pushes to the base branch, retargets or closes a PR, or force-pushes | an undoable merge or a lost branch | builders act as the builder account; `launch` refuses a wave unless the repository's protection meets §11's contract (only the owner updates the base branch); `landed` means merged into `<base>` and `prepare` refuses a PR whose base is not `<base>`; a `closed` by the builder account is a point-3 question, not the owner's ruling; the builder's allow-list has no merge or worktree command. Its push entry is a prefix for its own branch, which cannot exclude a `src:dst` refspec, so a fast-forward push onto a sibling's branch is an accepted residual: the orders forbid it and the owner sees it in the sibling's PR | U09, U10, U10b |
| The foreman merges or removes a worktree; the elephant, holding the owner's credentials, merges | the same | the foreman adapter's Bash cannot be pattern-restricted and the elephant is the owner's session; the plugin ships no approve or merge path and their briefs forbid both; accepted residual risk | U10, U10b |
| A builder-authored comment is taken for a ruling or a decision; a builder edits CI or files outside its scope so its head reads green | a machine clears its own finding | the helper honours `**Ruling:**` and `**Decision D<n>:**` comments only from authors other than the builder account's login; the CI finding is settled by no one; a changed path outside the unit's Scope paths is a `foreman` high | U04, U09, U10 |
| Judges from one vendor only (Astra lane down) | less independent verdicts | `judges.min_vendors` (default 1); the record says `degraded: true` whenever fewer than two vendors answered | U08 |
| A spec edit after a clean round or after approval; an approval not yet on the base branch | unreviewed bytes frozen; bodies cite a stale hash; builders branch from a base without the frozen spec | every round records the sha256 it reviewed; `approve-spec` refuses unless the spec's current sha256 equals the converged round's; `graph` refuses when it differs from the approval; `launch` refuses until the spec at `origin/<base>` hashes to the approval | U04, U05, U09 |
| The claudex-loop runner's lane down | no second vendor | every lane use is optional and recorded `not run (<reason>)`; the every-reviewer-ran check counts its `not run` record | U04, U08 |
| CI absent, queued for ever, or needing manual approval on a draft PR | rounds never start | `launch` refuses the first wave unless `origin/<base>` carries a workflow triggered on `pull_request`; `foreman dispatch` refuses while a head's CI is pending or absent; a head whose CI is still pending or absent at two consecutive `deadline`s of one `wave` invocation is named idle (it holds no slot), the loop ends for it, and the wave report says so | U09, U09b, U10, U10b |
| The owner's profile hooks reach a goldfish | priming the record cannot remove | the dispatch record carries the goldfish's own report of exposure; the README names the profile rule | U04 |
| Extraction over an arbitrary tree (encoding errors, huge files, symlink loops) | `orient` crashes or hangs on a repository | best-effort reads (`errors="replace"`), files over 1 MB skipped, symlinks not followed, one export of the tracked tree (`git archive`) as the only input | U12 |
| graphify's output reaching goldfish and builders as evidence | a wrong edge misleads a reviewer or a builder | the graph is built from an export of the ref `orient` was given, with no model; `orient` projects EXTRACTED edges inline and lists any other edge apart with its confidence; the file's first line names the graph's sha256 | U12 |
| An adopted issue's body overwritten wholesale | a person's text lost | the dry run shows the old body's sha256, `apply` refuses when the body changed since, comments and title are kept | U13 |
| A PR block appended verbatim; a token recipe that does not fit the repository's owner kind | a builder PR the repository's CI rejects; a token with no access | the block is the repository's own text and its CI checks it; the recipe names the fine-grained form for an organization's repository and the classic form for a personal one, and `doctor` reports the token's kind | U14 |

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
none of them without a judge record of non-convergence, and no stall; 1.0.0 ships when that
passes.

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
On an existing repository the elephant may type `/superegm:orient` (§9.3) before phase 2 for its
own reading; the phases need no typed step: `plan` and `review-plan` regenerate the map and every
unfiled unit's `<6 hex>/orient/<unit>.md` when they start and after each `graph --plan` they run,
`review-plan` hands the unit file to the readiness goldfish, and `launch-builder` regenerates it
from the launch's ref, so no phase reads a stale file.

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
  repository's PR block when `pr_block_file` is set and the unit's orient text (§9.3, §11),
  the rulings on its issue and, from round 2, the foreman's reviews of its own branch. Never the
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
  the artifact is **converged** when a round is `completed` (§8) AND clean AND no high or medium
  finding in it is a regression of a prior round's fix. Lows never block. A review is **at its
  cap** when its counted rounds ≥ 5 + its `continue` rulings; at the cap a ruling is required
  (§13.2) before any further round; `accept` makes the artifact converged (`converged: by ruling
  <id>`); `continue` may be ruled at most once per review cycle; after `stop` no ruling is
  accepted and the cycle stays at its cap; a new cycle starts with a fresh cap. No review has a
  second kind of cap. A review may instead be **stalled** (§8), which ends the invocation for
  that artifact and nothing else.

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
card's `artifact` is the spec path for the spec-scoped skills (`review-spec`, `orient`, `plan`,
`review-plan`, `file`, `wave`, `integrate`), the unit id for `interrupt` and `clean`, the
question file for `judges`, and the branch for `finishing-a-development-branch`. Each writing
subcommand declares the skills it serves (`require_runcard(args, skills)`), which refuses unless
the card is open, belongs to one of those skills, and either names the subcommand's artifact or
is the spec-scoped card of the handoff the named unit belongs to. A **child card** (`--parent
<id>`, opened by `judges open` and by `foreman dispatch`) is accepted while its parent is open or
`interrupted`; a record that names a child card names its parent. The skill's last action is
`runcard close`. A card of the same skill on the same artifact still open when that skill starts
again is marked `interrupted`; cards of other skills are left alone.

## 7. The store

One store per target repository. The helper is the only program that writes it, and every file
has exactly one writing invocation at a time:

| File | Writer |
| --- | --- |
| `state.json` | the elephant's typed skills (`plan`, `file`, `wave`, `integrate`), one at a time |
| `approvals/<spec-slug>.json` | `approve-spec` |
| `handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`, `handoff_bodies.md` | `plan` (`graph --plan <file>`; `decide` re-renders one unfiled unit and leaves a filed one as filed) |
| `reviews/<review-id>/…` | the invocation that opened that review; on a head, also the foreman dispatch the round records (`review record`, `collect`, `review post`) |
| `judges/<id>/…` | the invocation that opened that panel |
| `runcards/<id>.json` | the skill that opened the card; `card_add` for later facts |
| `launches/<unit>.json`, `launches/<unit>_r<n>_prompt.md` | the elephant (`launch-builder`, `record-launch`, `interrupt --launch`) |
| `worktrees/<unit>/` | the elephant (`launch-builder`, `/superegm:clean`) |
| `foreman/<unit>.json`, `review/<unit>/pr<n>/` | the foreman dispatch whose `dispatch_id` the round records (`prepare --dispatch`, `collect`, `review post`); between dispatches `foreman dispatch`, `interrupt --round`, `/superegm:clean`, `review settle` (a head's `outcome`, §11) and `decision open\|rule` (`decisions[]`, `rulings[]`) |
| `wave_<n>_report.md` | `wave` (`superegm report`, after every batch) |
| `orient/map.md`, `orient/export/`, `orient/graphify-out/`, `<6 hex>/orient/<unit>.md` | `orient` (`superegm orient`, typed, and run by `plan`, `review-plan` and `launch-builder`; §9.3); `orient/export/` and `graphify-out/` are written by `git archive` and graphify through `orient`, one invocation at a time, the two writes not made through `atomic_write` |
| `journal.md` | append-only, `O_APPEND`, one line per fact, written by the subcommand that wrote the fact |

The unit-keyed kinds `unit`, `foreman`, `launches`, `worktrees`, `review` and `orient_unit` live
under `<6 hex>/` (the handoff label's hex, which the tables above leave implied), so two handoffs
share one store; `Store.path(kind, …)` maps a kind and its parts to the path, `Store.kind_of(path)` back. All
writes go through a temp file and `os.replace`, graphify's own output and `orient`'s export
excepted (§9.3). No lock file.

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
  prefix for the unit's own branch is added per launch), `ci_wait_minutes` (30), `owners` (the
  GitHub logins that may update `<base>`; `init` writes the login `gh api user` returns; a config
  without the key loads as `[]`, and `launch` and `doctor` refuse naming the key), `owner_team`
  (optional, `<org>/<slug>`: the team a ruleset's bypass actors may name) and `pr_block_file`
  (optional: a path in the repository, relative to its root like `issue_template`, whose text
  every builder PR body carries) (§11). Unknown keys stop.
- Under `artifacts_dir`, never committed:
  - `state.json` — EGM's handoff state with EGM's keys, minus `approval`, `pending_approval`,
    `gate_unreviewed_diff` and `decisions[…].published`, plus `plan` (the path of the elephant's
    plan file outside the store, from `--plan` on the first `graph`; EGM's `plan` named the store
    copy), `base_at_start`, per unit `body_sha256`, `filings[]` (the confirmed write list of every
    filing that ran `apply`, appended by `apply` before its first write, once per write-list
    hash; EGM's `confirmed` is the pending one) and `closed_at` (written by `close`). A unit
    with a filed issue number is **frozen**: `graph` reads its section from the store
    (`handoff_plan.md`), never from the plan file, and refuses when the file's section differs;
    `graph` and `dry-run` re-render and re-hash unfiled units only; `apply` and `verify` act on
    the current filing's confirmed write list, `verify` reading back every issue that list names
    and comparing the stored body, never a re-render, and expecting in its obsolete-link pass the
    union of every list in `filings[]`; the tracking issue belongs to the latest filing's list
    only (a later filing rewrites its body, an issue edit EGM's `apply` never made), earlier lists
    being compared on their unit issues. One check, `require_frozen_units(handoff)` in U03 (py),
    replaces EGM's whole-plan checks in `status`, `launch` and `prepare`: for every filed unit,
    the plan file's section equals the stored one and the body its filing's list in `filings[]`
    stores equals the one `unit_<id>.md` carries (EGM's unit file holds the body in a fence);
    any difference refuses.
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
    converged_round, rulings[]`) and `round-<n>.json` (`runcard`, the top-level card the round's
    first `review record` carried; `artifact_sha256`; findings per reviewer with id, severity,
    location, `regression: yes|no`, disposition, ruling; `builder_contested[]` of `{fid, reason}`
    on a head; each dispatch's isolation, model and effort requested → effective; `what_ran`,
    derived as §8 says and stored with the round). Review ids carry a cycle:
    `spec-<spec-slug>-c<n>`, `spec-<spec-slug>-integrate-c<n>`, `plan-<unit>-c<n>`,
    `head-<unit>-c<n>`; `review open` on an artifact whose latest cycle is closed (`accept`,
    `stop`, or a spec change) starts the next cycle, and "the review" of an artifact means its
    latest cycle.
  - `launches/<unit>.json` — `launches[]` with `round` (the launch count), `worktree`, `branch`,
    `started_at`, `status` ∈ `running | exited <code> | interrupted`, `result_file`,
    `prompt_sha256`.
  - `foreman/<unit>.json` — `dispatch_id`, `rounds[]` (`round` (the review's round number),
    `runcard` (the wave card the dispatch ran under), `launch` (the launch count at dispatch),
    `head` (the tip `prepare` fetched), `phase ∈ fetched | prepared | collected | posted | kept |
    cleaned`, `dispatch_id`, `outcome` (the return word for a posted round, written by `review
    post`; else `not run (<reason>)`), `posted_at`), `decisions[]` (`id, point, question,
    asked_at`), `rulings[]` (`decision, ruling, by, posted_at`); a decision is pending from its
    `decisions[]` entry until its `rulings[]` entry. On kind `head` the review's rounds are
    these entries; a `round-<n>.json` exists only for a round whose panel was dispatched.
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
  <requested>:<effective> --effort <requested>:<effective> --runcard <id>`, or `--not-run
  "<reason>"` when the dispatch did not complete. A reviewer with no findings is recorded with an
  empty file; a dispatch that did not complete is re-dispatched once within the round and then
  recorded `--not-run`; the Astra lane is never retried within a round and is stopped for the
  review after two incomplete runs. `--reviewer set` takes the `set` reviewer's whole file and
  keeps the findings whose `<location>` names the review's unit or no unit. On kind `head`,
  `--reviewer foreman` is accepted outside the panel for the helper's own findings (§11) and
  never counts toward every-reviewer-ran. Every persona's output section is re-worded to the
  findings line below and its severity words (U01; each a changed Apache file). A round's
  `what_ran` is **derived** by the helper from the round's reviewer records and, on a head,
  from its `rounds[]` entry's `phase` and `outcome`; no caller sets it, and it is stored with
  the round: `completed` when every panel reviewer has a findings record for the round (an
  empty file counts; for the Astra lane a `--not-run` record counts too) and, on a head, the
  entry's `phase` is `posted`; otherwise `not run (<reason>)`, the reason being the first
  reviewer without a record or the entry's own `not run` reason (a head round with no reviewer
  record at all is `not run` with that reason). Only a `completed` round counts toward the cap
  or can converge; the findings of any other round settle nothing and block nothing. A review
  is **stalled** when its two latest rounds are not `completed` and both carry the run card
  `review status --runcard <id>` is given: the skill ends its invocation for that artifact with
  the record (on a wave or a `review-plan`, the loop ends for that unit and the others
  continue; the report or record names the reviewer and reason); a re-typed skill opens a new
  run card and resumes the same cycle. The findings file holds one finding per line:

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
  finding forward as a `foreman` high until a later builder reply marks it `fixed`. On a head,
  whichever of `review post` and `review settle` leaves `review status` at exit 0 writes `clean`
  into the latest posted round's `outcome` and journals `<unit> awaiting merge`.
- `superegm review status --review <id> --runcard <id>` prints `round <n>: <clean|not clean>,
  regressions <k>, converged <yes|no|by ruling>, cap <yes|no>, stalled <yes|no>, sha256 <hex of
  the converged round>` and the trend line; exits 0 when converged, 5 when stalled, 2 at the cap
  without an `accept` ruling (and for ever after `stop`, until a new cycle), 4 when any finding
  is `fix-design`, 3 otherwise or when the review is not yet opened. The cap and stall
  predicates live here alone; every other subcommand and every skill asks `review status`.
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
  `approve` with its heading check replaced by the `Units` check, its at-HEAD check by the commit
  it makes, `--evidence` dropped, and its tracked and clean checks removed, since it adds and
  commits by path): the spec's working-tree bytes must hash to the converged round's sha256 (for
  `--amend-units`, to the amended bytes), and its last H2 must read `Units` after any numeric
  prefix. In normal mode the owner is asked to approve; in leavemealone-mode the converged
  record is the approval. `approve-spec` then adds and commits the spec and
  `.superegm/config.json` by path, ignoring other changes in the tree, on the owner's current
  branch with the message `superegm: approve <spec-slug> at review <id>` and writes the record
  (`commit`, `sha256`, `handoff_id`); the owner pushes it to the base branch (§5). `superegm
  approve-spec --void --review <id>` sets `voided_by` when a `fix-design` finding is recorded;
  `graph` refuses a voided approval; a re-approval after a void keeps the `handoff_id` whenever
  `state.json` lists a filed unit. `approve-spec --amend-units` is §12's.

## 9. Plan (phase 2) and plan review (phase 3)

### 9.1 The plan is the issue body
`/superegm:plan <spec-path>` opens a run card, then `superegm graph` refuses unless an approval
record matches the spec's current sha256, and refuses while `state.json` carries a `handoff_id`
other than the approval's and `closed_at` is absent: one handoff per store at a time. The
elephant composes the plan text in a plan file outside the store, named by `--plan` on the first
`graph` and by `state.json.plan` after (EGM's layout: title, `Design:` line, `## 1. Issue
template`, `## 2. Units`), keeping every unit's section and adding one `### U<nn>: <title>`
section per row of the spec's `## Units` not yet in it, except a row the section's `Landed:` line
names (a unit that landed in an earlier handoff; the `set` reviewer, which reads the section,
counts those rows covered), and runs `superegm graph --plan <file>`
(copies the text into the store as `handoff_plan.md`, parses, derives waves, renders and hashes
the **unfiled** bodies) then `superegm scan`. Filed units are frozen (§7): their sections in the
plan file must equal the stored ones. Nothing is committed under `docs/…/plans`.

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
| Issue | optional; `#<n>`, an open issue in `config.repo` that `file` adopts instead of creating one (§10); `graph` refuses an `Issue` whose `#<n>` does not appear in the frozen spec's `## Units` section, a text check with no table parser (the owner names the adoption there) |
| **Interfaces** | `Consumes:` and `Produces:` lines, one item per line (grammar below) |
| Definition of done | numbered items; item 1 is always `The test for each Step was committed before its implementation (checked by superegm tdd-order)`; every other item is one of ``Run `<command>` — <what passing means>``, ``Exists `<path>` ``, or `CI green on the head`; only `Run` items are commands |
| **Steps** | numbered groups, each: a `Write` line, a fence carrying the test's signature and assertions (a full body only for an algorithm or data the assertions do not determine), and a one-sentence `Implement` line that never restates what the test asserts (grammar below); the `Run` line expecting FAIL and the closing line that runs the same command, expects PASS and commits are optional and default from the `Write` line; a rule family is one Step whose test is parametrized, never one Step per rule |
| Decide before build | `- none` or `- D<n> <question> options: (a) <option>; (b) <option>[; …]; owner: <owner>; default: (a); blocking: yes\|no` — two or more options, the default among them |

Grammar (each line is one `scan` rule, each with a test):
- `Produces: <name>(<params>) -> <type>` for a Python interface, or `Produces: superegm <sub>
  <flags> → <stdout shape>; exit <codes>` for a helper subcommand, or `Produces: <file> key
  <path>` for a store field. Matching is on `<name>` (the identifier before `(`), the subcommand
  words, or the key path.
- `Consumes: <name> (U04)` — the same name form plus the producing unit; `scan` refuses a
  Consumes whose name no sibling's Produces defines, and a producing unit that is not a direct or
  transitive blocker.
- A Step group, in its short form (the inner fence is the test's signature and assertions):

````
3. Write the failing test `test_body_over_48kb_refused` in `tests/unit/test_plan_scan.py`:
   ```python
   def test_body_over_48kb_refused(world):
       with pytest.raises(SystemExit, match="split it"):
           check_body_size("x" * 49_153)
   ```
   Implement `check_body_size(body: str) -> None` in `skills/plan/scripts/superegm/scan.py`.
````

  The `Write` line carries the test name in its first backtick span and the test path in its
  second; the `Implement` line carries the implementation path in its last backtick span. The
  fence carries the test's signature (name, fixtures, any `@pytest.mark.parametrize`), its
  assertions with the spec's exact values, and arrange/act lines only where the signature and
  assertions do not determine them; a full test body appears only for an algorithm or data the
  assertions do not determine (a plan longer than the code it describes has written the code
  instead). The `Implement` line is one sentence: the signature, the file and the values the
  spec pins; it never restates what the test asserts. A rule family is one parametrized Step,
  never one Step per rule. A copy/rename table or an edit list is test data: one parametrized
  test over the table (the test is the table), and the `Implement` line says "make the table
  hold"; no prose copy of a table in an `Implement` line. The `Run` line and the closing line are
  optional. When absent, the Step's command is `pytest <test path>::<test name> -q`, or `pytest
  <test path> -k <test name> -q` when the fence contains `@pytest.mark.parametrize`; the Step
  still ends "run the same command, expect PASS, commit `test(S<n>)` then `feat(S<n>)`", and both
  commit subjects default to `test(S<n>): <test name>` and `feat(S<n>): <test name>`. An explicit
  `Run` line (``Run `<command>`; expected: FAIL``) or closing line (runs the same command, expects
  PASS, names the commit subjects) remains valid and overrides the default: the first `Run` line
  then carries the Step's one command and the closing line names no command. Commit subjects
  carry the Step number as `test(S<n>)` and `feat(S<n>)`. The parsers of a body live in
  `superegm/body.py` and nothing else parses a body: `run_commands(body)` (the Step commands and
  the DoD `Run` commands) and `step_paths(body)` (Step number, test path, implementation path),
  which derive the defaults above when a Step's `Run` or closing line is absent, so every caller
  sees one form; `dod_items(body)` (item number, kind `run` | `exists` | `ci`, value) and
  `consumes(body)` (name, producing unit); their callers are `scan`, `launch-builder`,
  `tdd-order`, `collect` and `judges question`. The plan file's fields (Scope paths among them)
  are read through EGM's plan parser, by `graph`, `collect` and `orient` (§9.3) from the unit's frozen section
  in `handoff_plan.md`.
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
- `scan` reports per unit, as a stdout table and as `plan/scan/<unit>.json` in the store: `bytes`,
  `fenced_share` (bytes inside fences / bytes), `steps`, `spec_range_bytes` (the Design range's
  bytes in the frozen spec) and `ratio` (bytes / spec_range_bytes). It warns (exit 0;
  `warnings[]` in the json) when bytes > 32,768, or steps > 20, or fenced_share > 0.40. Warnings
  are the `proportion` reviewer's evidence (§9.2); they never block alone.
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
  its owning unit's Steps; every Step group has both paths and its one command (explicit or
  derived), each path under one of the unit's Scope paths; every `D<n>` line has two or more
  options with the default among them.
- The marker line's spec sha256 equals the approval's; `graph` refuses otherwise.
- A filed unit's section equals the stored one; `graph` refuses otherwise (§7).
- No cycles in blocked-by; no shared-file chain that contradicts the blockers (EGM's `graph`).
- The raw-text mention and banned-term scan with `allowed_mentions` (EGM's `scan`).

### 9.2 Plan review
`/superegm:review-plan <spec-path> [--units U01,U02] [--reviewers readiness,proportion,set,…] [--leavemealone]`

- One review per unit, id `plan-<unit>-c<n>`, kind `plan`, over the unit's current rendered
  bytes; the panel is `readiness` first, then `proportion`, then `set` (`PANEL_OF["plan"] =
  "readiness,proportion,set"` in `review.py`). A re-render between rounds is a new round of the same review;
  `apply` requires a body's `body_sha256` to equal the converged round's. Each `review-plan`
  round dispatches every unfiled unit that is not converged, not stalled in this invocation, or
  whose current `body_sha256` differs from its converged round's; a `set` finding naming a
  converged unit reopens it as a new round.
- The reviewer id `set` is the readiness persona dispatched **once per `review-plan` round**
  over the set, for interface consistency and the cut: it receives the spec's `## Units` and,
  from every unfiled body, the Interfaces block and the Scope, Blocked by and Shared files lines
  only. Its one findings file is given to every unit's `review record --reviewer set`, which
  keeps the findings for that unit (§8). Any reviewer other than `set` and `proportion` receives one body, the approved spec
  at its hash, every sibling's Interfaces block and, for `readiness`, the unit's
  `<6 hex>/orient/<unit>.md` when it exists (§9.3). Units run **concurrently**, and the goldfish
  within a unit's panel concurrently.
- The reviewer id `proportion` is the zoom-out persona (`agents/zoom-out.md`, adapter
  `.claude-plugin/agents/zoom-out.md`) dispatched with the plan brief
  `skills/review-plan/references/proportion.md`: it receives the body, that unit's
  `plan/scan/<unit>.json` (§9.1) and the unit's spec range at the frozen hash, and answers
  question 11 only. A proportion finding names the Step and the bytes it would remove; its
  severity is `medium` at most. Dispositions follow §8 unchanged.
- The standard is `resources/document_standards/handoff-standard.md` (EGM's seven questions)
  plus four: 8, interfaces present and consistent; 9, every Step group complete and DoD item 1
  present; 10, global constraints and review focus present; 11, "Is the body no longer than the
  decisions the builder cannot make alone: no fenced test the signature and assertions already
  determine, no Implement line that restates the test, no Step a parametrized sibling covers, no
  prose table that should be test data?" A `fix-design` disposition makes
  `review status` exit 4; the skill then runs `approve-spec --void` and the spec returns to spec
  review.
- Readiness questions ("what would a builder still ask?") are findings of the `readiness`
  reviewer: a blocking question is `high`. Readiness and proportion are an adversarial pair: a
  conflict between them is resolved in favour of the shorter form that keeps the test honest, and
  the elephant records that disposition. There is no second loop and no second cap.

### 9.3 Orient (phases 2, 3 and 5)

`/superegm:orient <spec-path> [--unit U<id>]...` (amendment 2). SuperEGM goes into existing
repositories whose orientation lives in `CLAUDE.md` or `AGENTS.md` files the goldfish never see
(`omitClaudeMd`) and in planning logs that are elephant memory; `orient` copies what a builder or
reviewer needs into the store. It is an **extractor, never a summarizer**: a helper subcommand
with no model call that copies what exists and invents nothing. Typed by hand it is for the
elephant's own reading; the phases run it themselves (the callers below), so the workflow needs
no typed step.

**Effect and command.** The skill declares `external: state-store`; its card's artifact is the
spec path (§6). `superegm orient --spec <path> [--unit U<id>]... [--ref <ref>] --runcard <id>`
refuses without an open `orient`, `plan`, `review-plan` or `wave` card (`require_runcard(args,
["orient", "plan", "review-plan", "wave"])`); `--spec` names the approved spec whose handoff the
units belong to (§6's artifact rule). It reads one tree: the tracked files of the repository it
is run in at `--ref` (default `HEAD`), exported with `git archive <ref>` into the store's
`orient/export/` (emptied first; one fixed path, so graphify's caches key the same files every
call), so an uncommitted edit, an untracked or an ignored file never reaches it or graphify.
Every call exports and, with graphify, builds afresh. Without `--unit` it writes `orient/map.md`
and, when a handoff is open in the store (a `handoff_id` in `state.json` with no `closed_at`),
every unfiled unit's file; with `--unit` it writes the named units' files only. A unit whose
section is not in the store's `handoff_plan.md` is refused (`orient: U12 is not in the plan: run
graph --plan first`). It prints one line per file written, `<store path> <bytes>`, and exits 0,
or 1 with `orient: <reason>`. Every read is best-effort (`errors="replace"`), files over 1 MB are
skipped, symlinks are not followed. The two skills run it as a shell command and stop on its
exit 1 with its line; `launch-builder` calls it in process under its own card (one writing
invocation per file, §7).

**graphify** (§2). When `graphify` is on `PATH` it is the engine: `orient` removes any earlier
`graph.json`, runs graphify's headless `update` with the export's absolute path as its argument
(AST only, no model call by construction, no prompt, the whole code corpus extracted fresh each
build, so no node of another tree survives), with `GRAPHIFY_OUT` naming the store's
`orient/graphify-out/` (the output directory itself, never the working tree) and a timeout of
600 seconds, so nothing leaves the machine, nothing is written outside the store and nothing
hangs the caller; then it projects `graph.json` per unit. Those are the contract; the
subcommand's arguments are U12's `skills/orient/references/graphify.md`, written against a
probe of the installed CLI and pinned by its tests. A build graphify refuses, fails or times out
leaves `## Graph` out and the first line says `graphify: failed: <the last line of its stderr,
or timeout>`: an optional tool never blocks a launch. Every edge graphify marks other than
EXTRACTED (INFERRED, AMBIGUOUS) is listed apart with its confidence; communities are their
integer ids. Without `graphify` the extractor alone writes the same two files, minus `## Graph`,
and the first line says `graphify: not installed`.

**The two files.** Two store kinds: `orient` at the store root (`orient/map.md`,
`orient/export/`, `orient/graphify-out/`; `Store.path("orient", "map.md")`) and `orient_unit`,
handoff-keyed like every unit file (`<6 hex>/orient/<unit>.md`; `Store.path("orient_unit",
"<unit>.md")`; `Store` maps that kind to the directory `orient` under the prefix); never under
the working tree, never committed. Each file's first line is its record:
`orient: tree <sha> · graphify: <graph.json sha256 | not installed | failed: <reason>> · trimmed:
<what was cut | nothing>` (the map's cuts read `communities <n>, depth <d>`; a unit file's name
its trimmed items). A dispatch that is handed a unit file is recorded `exposed:orient <tree
sha>` (the callers table below), so the round record names what its reader saw.

| File | Contents, in order | Cap and trimming |
| --- | --- | --- |
| `orient/map.md` | with graphify: `graph.json`'s summary (nodes, edges, communities, the EXTRACTED share) and the 40 largest communities by node count, each by its id with the five files holding most of its nodes; then the repository map: one line per directory to depth 4 over the tracked files, skipping `dist`, `build`, `vendor`, `target` and `scratchpad`; each line the path, file count, dominant extension, entry points (`__init__.py`, `main.*`, `index.*`, `mod.rs`, `__main__.py`) and the first heading or first sentence of any `README.md`, `AGENTS.md`, `CLAUDE.md` or `context.md` there (one line, ≤160 chars) | 24,576 bytes: the community list is cut to what fits beside the map, then the depth is reduced until the map fits; the first line says so |
| `<6 hex>/orient/<unit>.md` | for every Scope path of the unit (a directory path contributes each file under it): an existing file's module docstring (first paragraph), its public signatures (`def`/`class` lines not starting with `_` for Python; exported `function`/`class`/`export` lines for JS/TS; the first 40 lines otherwise) and the tests under `tests/` that name it; for a path to be created, the sibling files' public signatures; with graphify, a `## Graph` section per Scope path: the nodes whose `source_file` (relative to the export, compared with the Scope path relative to the repository root) is the path or under it, every EXTRACTED edge touching them with the neighbour's `source_file` and `source_location` (callers and callees, one hop), the other edges apart with their confidence, and each node's community id; then `## Read first`: every heading-delimited section of the `README.md`, `AGENTS.md`, `CLAUDE.md` and `context.md` files at the repository root and in the Scope paths' own directories (walking up to the root) that names the unit, verbatim, each section once. "Names" means, as whole words: a Scope path as written, its basename, its directory, or for Python its dotted module name | 16,384 bytes, trimmed in this sequence until it fits: (1) the tests lists, (2) the sibling signatures, (3) `## Read first`, (4) the `## Graph` edges whose neighbour is outside the Scope, (5) the `## Graph` edges between Scope files, (6) the `## Graph` node lines, (7) the docstrings and Scope signatures, path by path in Scope order; the first line says what was trimmed |

**Callers**, each a small change in an existing skill body or module; nothing else runs or
reads the files:

| Caller | What it does |
| --- | --- |
| `plan` | runs `orient --spec <path>` under its card before drafting and after every `graph --plan` (the map, and every unfiled unit's file once a handoff is open); the elephant reads `orient/map.md` before drafting |
| `review-plan` | runs `orient --spec <path>` under its card when it starts and after every `graph --plan` it runs (a fix re-rendered the bodies), names `<6 hex>/orient/<unit>.md` in the `readiness` goldfish's brief (`skills/review-plan/SKILL.md` Step 2) and records that dispatch `--isolation exposed:orient <tree sha>` (with whatever else the goldfish reports); when the file is absent the brief says so |
| `launch-builder` | fetches the launch's ref (`refs/superegm/base`, `launch`'s fetch of `origin/<base>`, in round 1; `refs/superegm/pr/<n>`, the PR tip, after: the tree the builder gets, §11), then, before it adds the worktree, calls `orient` in process with `--unit U<id> --ref <ref>` and refuses the launch with `orient`'s line when it fails, an ordinary precondition that leaves no worktree or branch behind; then writes the file's text into the prompt file under a `# Orient` heading, so `prompt_sha256` covers it; `builder_orders.md` says "read the `# Orient` section before Step 1" |

**Determinism.** The extractor is a function of the exported tree; the projection into
`## Graph` is a function of `graph.json` and the unit's section; a test pins the extractor on a
fixture tree and the projection on a fixture graph, both under `tests/fixtures/orient/`; the
tests never run graphify. The same tree gives byte-identical files when graphify is absent or
its `graph.json` is unchanged; graphify's own build is not pinned, which is why the first line
names the graph's sha256.

**Cost.** The AST extraction runs with no model and no token; `graphify update` extracts the
whole code corpus on every `orient` call, seconds on this repository and minutes on a large one.

## 10. File (phase 4)

`/superegm:file <spec-path>` is EGM's handoff filing (`gate` → `dry-run` → `apply --yes` →
`verify`) with these changes:
- `gate --pass` requires `review status` exit 0 for every unfiled unit it passes and the unit's
  `body_sha256` to equal its converged round's; `apply` refuses otherwise. `gate --accept` goes.
- The dry run and the "Create" confirmation are against the same write-list hash `apply`
  re-checks; `dry-run` renders unfiled units only (§7). In normal mode the owner confirms; in
  leavemealone-mode the confirmation is mechanical and journaled `Create: automatic
  (leavemealone)`.
- `apply` appends the confirmed write list to `state.json.filings[]` before it creates the first
  issue, once per write-list hash; `verify` reads back every issue that list names and compares
  the stored body as §7 says; `base_at_start` is recorded on the first `apply`. Filed units are
  frozen (§7); a later filing (§12's append path) appends its own list and rewrites the tracking
  issue.
- Idempotent filing with marker recovery stays, re-pointed at the new markers. Labels are
  `superegm:unit`, `superegm:wave-<n>`, `superegm:handoff-<6 hex>`, `superegm:tracking`,
  `superegm:stopped`.
- A unit whose section carries `Issue: #<n>` is adopted, not created: a repository that already
  tracks the work as an issue (a backlog item a person opened, with its comments and subscribers)
  keeps that issue's number instead of a second issue linked to it. `graph` reads the field and
  refuses a `#<n>` absent from the spec's `## Units` section (§9.1); `dry-run` reads the issue
  and refuses one that is closed (`adopt: #<n> is closed`), not in `config.repo` (`adopt: #<n>
  not in <repo>`), a pull request (`adopt: #<n> is a pull request`), already a sub-issue of
  another parent (`adopt: #<n> has a parent`), already carrying blocked-by links (`adopt: #<n>
  has dependencies`), carrying any `superegm:` label (`adopt: #<n> carries superegm labels`: an
  earlier handoff's or a stopped unit's issue, which `launch` would skip) or carrying a
  `**Ruling:**`, `**Decision D<n>:**` or `**Deviation**` comment (`adopt: #<n> carries a ruling
  comment`: its history must not rule the unit). Its report heads the unit `### edit #<n> <unit>
  (old body sha256 <hex>)` where a created unit reads `### issue <unit>`, and the write list
  carries the unit as an `issue` entry whose five fixed fields are a created one's (`["issue",
  <unit>, <title>, <labels>, <body>]`, written by `gate.pending_writes`), with the adopted number
  and the old body's sha256 as two trailing fields; `dry-run` is the read that records the old body's sha256 (`apply`'s read is the
  comparison), and `pending_writes` at `apply` time takes it from the dry run's confirmed list, so the
  list re-check passes and the readers of the fixed fields (`require_frozen_units`,
  `launch-builder`'s filed body and `verify`) are unchanged. `apply` finds an adopted unit by its
  number: an issue whose body already carries this handoff's marker for the unit is done (marker
  recovery, as for a created issue, so a crash after the edit resumes); otherwise it re-reads the
  issue, refuses when its body does not hash to the old body (`adopt: #<n> body changed since the
  dry run`), and adds the labels a
  created unit issue gets (`superegm:unit`, the wave and handoff labels) and rewrites the body to
  the rendered unit body (the byte-identical rule unchanged), keeps the issue's existing labels,
  title (which may differ from the body's H1) and comments, and sets the sub-issue and blocked-by
  relationships; `verify` reads it back like a created one, and `#<U04>` placeholders resolve to
  adopted numbers too. Nothing else about filing changes.
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
workflow triggered on `pull_request`; the builder token is set, its login is not an owner, and it
is recorded with that login in the card; and the base branch carries an active protection, in
classic or ruleset form, that restricts updates to `<base>` to the owner with no bypass for the
builder account (a ruleset's restrict-updates or classic restrict-who-can-push, which covers
merging a pull request) and, by a ruleset, forbids force-push and deletion on `superegm/**`. The owner is the
non-empty set `config.owners` (GitHub logins; `init` writes the login `gh api user` returns; §7
says what a missing key does): the check accepts a classic restriction whose users are a non-empty
subset of `owners` with no teams and no apps, or an active ruleset whose bypass actors include
neither the builder account's repository role nor a team other than `config.owner_team` (1.0.0's
rule, which a personal account's repository meets with a bypass for the admin role, which the
builder lacks, teams and classic restrictions being organization features: any other actor, an
organization admin, an app or a deploy key, is not the builder); when the bypass names `owner_team` (`<org>/<slug>`), the team
must exist (`orgs/<org>/teams/<slug>` answers 200) and the builder account must not be a member
(`orgs/<org>/teams/<slug>/memberships/<builder>` answers 404). The refusal names the missing
login, the bypassing role or team, or the team the builder belongs to. When
`config.pr_block_file` names a file in the repository (read from the launch's ref before the
worktree is added, as `orient` is run, §9.3), `launch-builder` writes that file's text verbatim,
filling nothing, into the prompt file under a `# PR block` heading (a path absent from the ref
refuses the launch, as a missing `issue_template` refuses every subcommand), and the orders say "paste the `# PR block` section into the PR body right
after the unit id line, before the DoD results" (so `collect`'s DoD scan is unchanged): a
repository whose CI requires a block in every PR body (a coordination block, a review-evidence
block) gets it
from every builder, and that CI, not SuperEGM, checks it. The builder account is a second GitHub
login, a machine account the owner controls (one is allowed per person), added to the repository
as a collaborator with Write. Its token is a fine-grained personal access token when the
repository belongs to an organization the builder account is a member of (resource owner that
organization, repository access limited to this repository, permissions Contents read and write,
Pull requests read and write, Issues read and write (the builder's status, deviation and reply
comments), Metadata read, no Workflows permission, expiration 90 days), and otherwise a classic
token (a fine-grained token's resource owner is the holder's own account or an organization it
belongs to, so a collaborator on a personal account's repository has no such token) with the `repo` scope
and without `workflow`; either way a builder push that touches `.github/workflows` is refused by
GitHub itself, and an organization's token policies may block either kind, which the owner
checks. It goes in `SUPEREGM_BUILDER_TOKEN` (the variable `builder.gh_token_env` names) in
the shell that runs the wave, never in the repository or the config. The recipe is written once,
in the README's "Before the first run" step 1, with one sentence naming the token's purpose:
builders push and open draft pull requests as that account and can never update the base
branch; `init`'s printed STEPS line 1, `docs/claude.md` and `docs/getting_started.md` point to
that step. Under that
protection the builder account can open PRs and never merge them; the owner, who alone updates
`<base>`, merges by hand; the plugin ships no approve or merge path, and the elephant and the
foreman hold no GitHub write but the review comment, the ruling and decision comments, and the
`superegm:stopped` label. `launch` also skips units labelled `superegm:stopped`, and counts a
unit in flight from its first launch until its latest round's `outcome` is `clean`, it has
landed, it carries that label, or the elephant names it idle (`launch --idle U07,U08`: the units
this invocation found stalled or CI-waiting hold no slot).

**`superegm doctor`** is read-only and needs no run card: the owner's by-hand check before a
wave, run as every helper command is (`python3 '<plugin root>/skills/plan/scripts/superegm.py'
doctor`; `init` ends by saying "then run `superegm doctor`"; `wave` does not run it, `launch` and
`launch-builder` refusing with the same predicates). It fetches `origin/<base>`, runs the
predicates `launch` and `launch-builder` run (the 1.0.0 helper's `origin_problems` minus its
spec-hash line, which needs an approval; `protection_problems` on the placeholder branch
`superegm/x/U01`, which the `superegm/**` rules match as a real unit branch does;
`builder_login`; `profile_problem`) with no effect, and prints one line per prerequisite with
`ok` or the refusal text they would give, exit 1 when any fails: the config loads;
`.superegm/config.json` and a `pull_request` workflow are at `origin/<base>`;
`SUPEREGM_BUILDER_TOKEN` is set; the token's login (`gh api user` with the token) is not an
owner; the protection check of `launch` (the `superegm/**` lines read the ruleset); the builder
profile exists and is empty of `CLAUDE.md`,
plugins and hooks (a `settings.json` with a `hooks` key; `profile_problem` gains that check, so
`launch-builder` refuses it too). Its own lines, which `launch` does not check: the `gh auth`
login is in `config.owners`; the builder's role on the repository
(`repos/<repo>/collaborators/<login>/permission`) is `write` exactly, the role found named
otherwise; the token's kind and scopes, from the `X-OAuth-Scopes` header of `gh api -i user`
with the token (a classic token must carry `repo` and not `workflow`; a fine-grained token sends
no scopes header and is reported `fine-grained: permissions not probed`); and, informationally
and never a failure, that `graphify` is on `PATH`.

**The driver loop** runs in the main conversation, is the only long-lived actor, and is
event-driven: `superegm launch` marks the ready units up to `max_in_flight`; the elephant launches
a builder per marked unit; `superegm status --wait <s> --runcard <id>` (EGM's loop, reading
only and saving once on return, extended to read exit files and each unit's issue and PR
comments) returns **every** unreported change since its last save, one event line each, or
`deadline` when nothing changed. The event kinds are `head` (with its CI state), `status` (a
builder status comment), `exit` (a builder exit), `landed`, `closed` (a PR or issue closed by
hand, with its actor) and `deadline`; the line form is U09b's. Invariants the U10b plan must pin,
driving the loop through `foreman dispatch`'s refusal (below):
- An event is reported once and never lost: `status --wait` saves only the fingerprints of the
  units it reported, and the elephant handles every line of a batch before calling it again.
- A base-branch move under an unchanged head is not an event; the foreman's merge-base check at
  `review post` is its handler.
- A head with pending or absent CI is not reviewed. A head with concluded CI whose unit's latest
  launch is terminal, which has had no round posted since that launch (no `rounds[]` entry in
  phase `posted` with `launch` equal to the latest launch's count), whose unit has no decision
  pending (§7), and whose review is not stalled (`review status --runcard` exit 5), is reviewed
  at the next batch, whether a `head` line or a `deadline` announced it; so a relaunched builder
  that contested every finding and pushed nothing is reviewed too, and a head whose round ended
  `target-moved` or `error` is reviewed again at the next batch. `superegm foreman dispatch`
  refuses, exit 1, whenever that predicate does not hold (U10); it is the one place the
  predicate is evaluated.
- When several heads are ready at once their foremen are dispatched in one message.
- A builder's `exit` and its `**Builder status:**` comment are one decision, never two.
- Lines for a stopped unit are ignored except `landed`. A launched unit whose PR is closed
  unmerged, or whose issue is closed while its PR is unmerged, by an actor other than the builder
  account is `stop` without a ruling (the owner has ruled); a `closed` whose actor is the builder
  account's login, an interrupted launch, and an exit with no PR are point-3 questions.
- Every point-1, -2 and -3 question about a unit is recorded with `decision open` when asked
  and `decision rule` when ruled (the ruling is also applied through the point's own subcommand:
  `review settle`, `review rule`, or the posted `**Ruling:**`); a re-typed `wave` raises every
  pending decision before its first batch.
- The loop ends when every launched unit is clean, landed, stopped, pending a decision, or idle
  (stalled, §8, or waiting on a head whose CI was still pending or absent at two consecutive
  `deadline`s of this `wave` invocation), and no ready unit is unlaunched while a slot is free.
  After every batch, and at the end, the elephant runs `superegm report`, which rewrites
  `wave_<n>_report.md` (per unit: state, head, rounds, open findings, every non-terminal launch,
  every head with pending or absent CI, every idle unit and why, every ready unit unlaunched for
  want of a slot, every pending decision, every stopped unit and its unlanded dependants), and
  at the end closes the run card. The skill is re-typeable and resumes from the store without a
  second launch, ruling or review of anything already recorded. A pause at a decision point
  ends the loop; builders keep running; the next `wave` handles what they reported.

**Launching a builder** (`superegm launch-builder --unit U07 --round <n> --runcard <id>`, where
`--round` is the launch count). It refuses unless the unit is marked by `launch`, every earlier
launch is terminal, the builder token and profile pass §4's checks, and the issue body read back
equals the body the write list of the filing that created the unit's issue (`state.json.filings[]`)
stores for it, filled and normalised as `verify` compares. Every launch adds a fresh worktree
under `worktrees/U07/` on branch `superegm/<handoff-id>/U07` (round 1 from `origin/<base>`,
later rounds at the PR tip), after detaching the earlier launch's worktree from the branch
(`git switch --detach`; nothing in it is removed), and leaves earlier worktrees for
`/superegm:clean`. It writes the prompt file, which holds exactly: the issue body,
`references/builder_orders.md`, the `pr_block_file` text under a `# PR block` heading when the key
is set, the unit's orient text under a `# Orient` heading (§9.3), every `**Deviation**` comment,
every `**Decision D<n>:**` and `**Ruling:**` issue comment **whose author is not the builder
account**, and from round 2 the foreman's review comments on the PR (the platform passes it as one
argument, §4; a prompt past the platform's limit fails the launch, which `record-launch --exit`
records). The launched command carries: the builder profile;
`GH_TOKEN` from `builder.gh_token_env`, with the HTTPS push rewrite and credential helper in its
environment; `SUPEREGM_ROLE=builder` and `SUPEREGM_RUNCARD`; `claude -p` with the prompt file's
content, the configured model and permission mode; the allow-list plus a push prefix for the
unit's own branch and `Bash(<first word>:*)` for every command `run_commands` returns from the
body; `--output-format json` into the result file; and the exit file on exit. The launch is
recorded (`record-launch`), and `record-launch --exit <code>` later records the exit. An
allow-list containing `Agent`, `Skill` or bare `Bash` is refused.

**The builder orders** (`references/builder_orders.md`, absorbing superpowers' implementer prompt
and the discipline of its receiving-code-review and test-driven-development skills): follow the
Steps in order, test first, one `test(S<n>)` commit then one `feat(S<n>)` commit per Step; run
every DoD `Run` command and paste each item's output in the PR body under its item number as a
fenced block; push with `git push origin <branch>` and never to any other branch; open a
**draft** PR against `<base>` whose body is the unit id, the prompt's `# PR block` section when it has
one (verbatim, right after the unit id), the DoD results in that form and
`Closes #<issue>` (later rounds update the existing PR; never retarget or close it); when a Step
cannot be done as written, post the `**Deviation (<kind>):**` comment of §10; from round 2,
verify each review finding against the code before changing anything, reply on the PR `**Reply
<fid>:** fixed | contested — <reason>`, and push; a `**Ruling:**` that says `finding upheld`
means fix it, `finding overruled` means leave it, and an option ruling `(<comment-id>)
<option>` means follow that option; finish with one comment `**Builder status:** DONE |
DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT` on the issue; every builder comment except
`**Reply <fid>:**` (on the PR) goes on the issue. A BLOCKED or NEEDS_CONTEXT comment states the
question and ends with two or more `- (a) <option>` lines, the first the builder's own proposal.
Wherever an absorbed skill says "ask your human partner", the builder writes the question in
that comment with status BLOCKED and stops. A builder never spawns, never touches files outside
its scope paths, never merges.

**The foreman** is a named subagent (`name: foreman-U07-<dispatch_id>`) dispatched through the
`superegm:foreman` adapter (`omitClaudeMd: true`; tools `[Agent, Bash, Read, Grep, Glob]`) in the
foreground, with `references/foreman_brief.md`, the unit id, the wave run card, a child card and
the `dispatch_id` that `superegm foreman dispatch --unit U07 --runcard <id>` wrote (that call
also opens `head-U07-c<n>` with `config.reviewers.head` on the unit's first dispatch of the
cycle, writes the round entry with its `runcard` and `launch`, supersedes any non-terminal round
of the unit, except a `collected` round whose review the PR already carries with the reviewed
sha as `commit_id`, which it counts `posted`, writing `posted_at` and the `outcome` `review
status` implies, and refuses unless the dispatch predicate above holds). It runs **one round**
and returns one word plus one line:
- `prepare --dispatch <id>` is EGM's (fetch the PR and base refs, a detached review worktree, the
  diff, the CI JSON) plus `pr_body.md` and `comments.md` (the PR's and the issue's comments after
  the latest `posted_at`, each with its author, plus every `**Deviation**`, `**Decision D<n>:**`
  and `**Ruling:**` comment regardless of age); it records the tip it fetched as the round's
  `head`, and refuses a PR whose base is not `<base>`.
- It dispatches the head's panel (`change-review` first; fixed in the run card) **concurrently**,
  without `name`, each goldfish receiving the unit file (its DoD is the head's standard), the
  frozen spec range, the diff, the CI file, `pr_body.md`, `comments.md`, the last posted round's
  findings with the builder's replies, and the worktree path, and records each with `review
  record --sha256 <head>`.
- `collect --dispatch <id>` records, through one `review record --reviewer foreman` call, as
  high findings: CI not green on this head; an `Exists` DoD item whose path is absent, or a `Run`
  item without its fenced output in `pr_body.md` (`dod_items`); a changed path outside the unit's
  Scope paths (read from the frozen section, §9.1); a `tdd-order` failure (over the PR's commits
  in order, for each Step n a `test(S<n>)` commit touching that Step's test path precedes a
  `feat(S<n>)` commit touching its implementation path, and every `test(…)` commit touches only
  paths under `tests/`) not overruled by a later `**Ruling:**` from an author other than the
  builder account; a deviation of kind `interface`, `dod` or `test` not yet ruled (ruled when
  such a `**Ruling:**` names its comment id, §10); and every finding of the last posted round the
  builder replied `contested` to, which is unsettled until a ruling. It reads `**Reply <fid>:**
  contested — <reason>` lines into `builder_contested[]` as `{fid, reason}`, ignoring a reply to
  the CI finding. `collect --dispatch <id> --not-run "<reason>"` (EGM's) records a round the
  foreman could not complete (a failed fetch, `prepare` or dispatch, or a panel goldfish still
  not run after its one re-dispatch) as `collected (not run (error: <reason>))`.
- `review post --unit U07 --round <n> --dispatch <id> --runcard <child>` is EGM's posting guard
  moved into the helper: it never posts a header already present, posts only against the commit
  the round reviewed (that binding replaces EGM's head and base-branch refusal), through the
  pull-request reviews API, never `--approve` or `--request-changes`, after the raw-text scan,
  and refuses with exit 3 `target-moved` when the merge base moved since `prepare`, recording
  the round `collected (not run (target-moved))`. When the response's `commit_id` is the
  reviewed sha it counts the round `posted`, writing `posted_at` and the round's `outcome`: the
  word `review status` and `builder_contested[]` imply, in this order: `contested: <ids>` when
  `builder_contested[]` meets an unsettled high or medium; `clean` on exit 0 (**Clean**: CI
  green, every DoD item met, no unsettled high or medium, `tdd-order` passed, no unruled
  deviation, all of them findings in the record; **No regressions**: CI's suite green on the
  head and no high or medium finding a regression of a prior round's fix); `cap-reached` on exit
  2; `revise` when an unsettled high or medium exists. On `clean` it journals `U07 awaiting
  merge`.
- The return word is the round's `outcome` when the round is `posted`, `target-moved` when
  `review post` refused, and `error` otherwise (the round recorded by `collect --not-run`). A
  return that is none of those six words is read as the round's `outcome` when the round is
  `posted`, and as `error` otherwise; the elephant records nothing itself, and the next
  `foreman dispatch` supersedes a round left non-terminal.
- It never merges, never approves, never edits the owner's working tree, never removes a
  worktree, never launches a session, never convenes the judges, never infers that a builder died.

**What the elephant does with a word.** `clean`: the unit awaits merge and its slot is refilled.
`revise`: the next builder is launched (its prompt carries the review). `contested`: decision
point 1 (`decision open --point 1`), then the ruling is recorded with `review settle` and
`decision rule` and posted on the issue as `**Ruling:** <fid> finding upheld (fix it) | finding
overruled — <reason>`, and the unit proceeds by `review status` (converged → awaiting merge; at
the cap → as `cap-reached`; else the next builder). `cap-reached`: decision point 2 (`decision
open --point 2`), **one more round** (once; recorded with `review rule` and `decision rule`; the
next builder is launched with the review) or **stop**. `error`, `target-moved`: the head is
reviewed again at the next batch, unless `review status --runcard` reports the review stalled
(exit 5), which makes the unit idle. `blocked` (a `BLOCKED` or `NEEDS_CONTEXT` status, a builder
exit with no PR, an interrupted launch, a `closed` by the builder account, or a third `blocked`
on one unit without an intervening head): decision point 3 (`decision open --point 3`), whose
ruling is recorded with `decision rule` and posted on the issue as `**Ruling:** (<comment-id>)
<option> — <reason>` quoting the question, then the next builder or `stop`; for an exit with no
PR, an interrupted launch, a builder's `closed` or a third `blocked` the options are `relaunch`,
offered once per unit, and `stop the unit`, and once `relaunch` has been used the case is `stop`
without a question. A by-hand `**Ruling:**` from a non-builder author that names a BLOCKED
comment's id also rules its decision: the next `wave` records it with `decision rule --by
<author>`; any other by-hand `**Ruling:**` rules deviations and `tdd-order` findings and nothing
else. `stop` (from any ruling or from the owner's by-hand close): the issue is labelled
`superegm:stopped`, kept open unless the owner closed it, the branch kept, the unit never
relaunched; it is listed in the wave report with its unlanded dependants; the owner lands it by
hand or closes it with those dependants and re-appends what is still wanted (§12).

**Landing.** A unit has landed when its watched PR is merged into `<base>` and its issue is
closed as completed, whoever closed it. Landing makes dependants ready. `/superegm:clean --unit
U07` (EGM's `prepare --clean` looped over the unit's review rounds, plus the removal of every
builder worktree whose launches are all terminal, dirty or not: the typed skill is the owner's
decision, and EGM's dirty refusal applies to review worktrees) is typed, `destructive-local`,
refuses while any launch or round is not terminal, and keeps what it cannot prove.
`/superegm:interrupt --unit U07 (--launch <n> | --round <n>)` is typed and records
`interrupted` on a launch, or marks a prepared round `collected (not run (interrupted: owner))`;
an owner's decision is not a guess.

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
  to re-append what a stopped unit still owed. The handoff closes (`superegm close`, which writes
  `closed_at`) when an integrate round has nothing to escalate. `/superegm:integrate --close` is
  the owner's typed close of a handoff they have given up on: it runs `superegm close` without a
  review round, journaling every unlanded unit, and frees the store for the next handoff.

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
   interrupted launch, a `closed` by the builder account, or a third `blocked` without an
   intervening head (`relaunch`, offered once per unit; `stop the unit`);
4. the owner's approval of a converged spec in normal mode, and "Create" in normal mode.

In normal mode every point pauses for the owner. In leavemealone-mode (`--leavemealone` or
`config.mode`), at points 1–3 the skill runs `superegm judges question (--review <id> --round <n>
[--reason <fid>=<text>]… | --review <id> --cap | --unit <U> --decision D<n> | --unit <U>
--blocked (<comment-id> | launch <n> | closed <n>)) → <path>` to render the question file from
the record with the options named above, one panel per review round, runs `judges open --parent
<its run card>`, dispatches the judges as §13.1 says, and applies each converged answer (subject
to `min_vendors`) through `review settle --judges`, `review rule --judges`, `decide --judges`,
or `decision rule --by judges:<panel-id>` and a `**Ruling:**` comment the skill posts with `gh
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
| new | `orient` | external: state-store | typed (and run by `plan`, `review-plan` and `launch-builder`) | elephant, before planning on an existing repository; the readiness goldfish and every builder through its callers | §9.3; `orient/map.md`, `<6 hex>/orient/<unit>.md` in the store |
| egm-handoff planning half + writing-plans (sp) | `plan` | external: state-store, start-session, github-write | typed | owner, phase 2 | §9.1; `github-write` for the decision comment on a filed unit |
| new | `review-plan` | external: state-store, start-session | typed | owner, phase 3 | §9.2 |
| egm-handoff filing half | `file` | external: github-write, state-store | typed | owner, phase 4 | §10 |
| egm-wave + SDD implementer prompt (sp) | `wave` (+ `references/foreman_brief.md`, `references/builder_orders.md`) | external: start-session, github-write, remote-branch, state-store | typed | owner, phase 5 | §11; Claude goldfish only on heads |
| new | `interrupt` | external: state-store | typed | owner, phase 5 | §11 |
| new | `clean` | external: destructive-local, state-store | typed | owner, phase 5 | §11 |
| finishing-a-development-branch (sp) | same name | external: github-write, remote-branch, state-store | typed | owner, outside a wave | no local merge, no forced push; the PR as the owner |
| new | `integrate` | external: state-store, start-session | typed | owner, phase 7 | §12; `--close` |
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
  and one module per subcommand; `tests/unit`, `tests/fixtures` (new in 1.1.0),
  `tests/integration/test_claude.py`; `docs/{index,getting_started,claude,faq,privacy,releases}.md`.
  How modules name themselves and attach to subcommand groups, where the fake `gh` test harness
  lives and how units extend it, and how the two source trees are brought in and excluded from
  the repository-walking tests while they exist, are the U01 and U03 plans' decisions, each a
  test.
- The packer is EGM's with one host, the three-file hook rule and hash check, the `effects`
  checks, and the superpowers files and the helper package in its allow-list; its output goes to
  a temporary directory in tests and to the release directory in `prepare_release.py`, which
  builds one archive and names `gsVAM/superegm`.
- Tests: EGM's unit tests are kept where the form they pin is unchanged, amended by U01 where
  the host, the names or the file set change, and rewritten by the unit that changes a form it
  pins (each unit tests in its own file; `test_helper.py` (EGM's `test_egm_handoff.py`, renamed
  by U01) is U03's alone in 1.0.0, U12's and U14's after, and U03 moves every test of a subcommand a later unit changes into that
  unit's named test file). Every new behaviour in §6–§13 has a test in the unit that builds it;
  each unit's plan names its test files. The freshness test and every Codex-host test are
  deleted.
- Each unit's plan lists and removes every sentence, docstring or example in its files that
  names a mechanism §3.1 removed or a form this spec changed.
- Install: `claude plugin marketplace add gsVAM/superegm` then `claude plugin install
  superegm@superegm`. The README tells the owner to disable `egm@egm-astra` and
  `superpowers@claude-plugins-official` first; to create the builder account, its token and an
  empty builder profile (step 1 is the token recipe of §11; `owner_team` is documented in
  `docs/getting_started.md`); to set the branch protection of §11 (updates to the
  base branch restricted to the owner with no bypass for the builder account; `superegm/**`
  protected from force-push and deletion) and a workflow triggered on `pull_request`; to run
  `superegm doctor` before the first wave; and to run reviews from a profile without
  SubagentStart hooks.

## 16. What is left to the builder

- The helper's argparse surface beyond the names and contracts in §17: `init`, `runcard
  open|close`, `approve-spec [--amend-units | --void | --leavemealone]`, `graph`, `scan`, `orient`, `doctor`,
  `review open|record|settle|status|rule|post`, `review-plan due|set-input|proportion-input`,
  `gate`, `dry-run`, `apply`, `verify`, `status [--wait]`, `launch [--idle]`, `launch-builder`, `record-launch [--exit]`, `foreman dispatch`,
  `collect [--not-run]`, `prepare`, `tdd-order`, `decide`, `decision open|rule`, `interrupt`,
  `clean`, `report`, `close`, `judges open|diff|record|verdict|question`.
- The hook script's exact text, as long as it carries the dispatcher rule and the phase rule.
- Journal line formats, as long as every line is written by the subcommand that wrote the fact.
- The judge persona's wording.
- Every mechanism §11 names as the plans' content: the event grammar's line form, the batch
  order, the folding, the retries, the resume derivation, the prompt file's assembly, the
  protection reads' field forms.

## 17. Units

The unit graph for building SuperEGM 1.0.0 (thirteen units) and, from amendment 2, 1.1.0 (U12–U14). Each unit's plan must fit 48 KB.
Interfaces are subcommand contracts and file keys unless marked `py`. A Consumes producer may be
a transitive blocker. After U01 every 1.0.0 skill folder and adapter of §14 exists (the new ones
as stubs), so the later 1.0.0 units modify and never create skill folders, adapters or personas;
`orient` (amendment 2) is created by U12.

Landed: U01, U02, U03, U04, U05, U06, U07, U08, U09, U09b, U10, U10b, U11 (1.0.0, released at
363dd5e); a later handoff on this spec drafts no section for them (§9.1).

| Unit | Scope | Blocked by | Size |
| --- | --- | --- | --- |
| U01 | Skeleton and absorption, packer-test-driven: the kept files of superpowers 7.0.0 and EGM 9bc49d4 brought in under the §14 names, stubs for every new skill, adapter and persona, the helper renamed and its tests kept green under EGM's forms, every persona's output section re-worded to §8's findings line; the Codex host, visual companion, synthesizer, bootstrap and retired skills not kept; licences and notices; manifests; packer; CI workflow; the test amendments the host and name changes need; CI green | — | L |
| U02 | The hook and effects: `using-superegm`, `hooks/`, role silence, manifest hash; `test_effects.py` and the packer's effects checks; the frontmatter, harness line and phase sentence of every SKILL.md; the §14 Change-column edits of the superpowers skills, `draft` and `drift-report`; `finishing-a-development-branch` without merge | U01 | M |
| U03 | Store, run cards, helper package: `superegm/__init__.py` and `body.py` as §15 says (the four body parsers, `fill_numbers`, `normalise`, the markers, `DECISION_HEADING`); each absorbed subcommand in its own module; `init`; the writer partition; `runcard open\|close` with child cards, the artifact rule and the card writers; effect gating in every absorbed writing subcommand; `require_frozen_units` replacing EGM's whole-plan checks in `status`, `launch` and `prepare` (§7); `state.json.plan` as the outside path; config and label renames with their tests in `test_helper.py`; the `approvals/` schema with `handoff_id`; the `foreman/<unit>.json` schema; the fake `gh` harness; `defer` and `--published` removed | U01 | L |
| U04 | The review loop and spec review: `review open\|record\|settle\|status\|rule`, `references/review_loop.md`, the cap and stall predicates, cycles, sha per round, the derived `what_ran` and the round's `runcard`, regression marking, the `foreman` and `set` reviewers in `review record`, the plan panel preset `readiness,proportion,set` (`PANEL_OF["plan"]`), the findings-file grammar, `--kind integrate`, `converged_round`, `review settle`'s head `outcome` write, the Astra review lane, the `review-spec` skill body, `approve-spec` with `--void`, `--amend-units`, the `Units` check and `handoff_id` | U02, U03 | L |
| U05 | Plan: the unit schema, the Interfaces grammar in `scan.py` over `body.py`'s parsers, the body template with EGM's placeholders and the new markers, `graph --plan` and `scan` rules incl. decision options, Step paths under Scope paths, frozen units and one handoff per store, body hashing as EGM does it, `decide`, the `plan` skill body; the Step defaults of §9.1 derived in `skills/plan/scripts/superegm/body.py` (modify; shared file, after U03), the `scan` numbers and warnings with `plan/scan/<unit>.json`, and the drafting rules of §9.1 (what the fence carries, the one-sentence `Implement` line, one parametrized Step per rule family, tables as test data) written into `skills/plan/SKILL.md` and `skills/plan/references/writing_plans.md` (modify) | U02, U03 | L |
| U06 | Plan review: the `review-plan` skill body, the `set` reviewer and its inputs, the `proportion` reviewer (the zoom-out persona with the plan brief `skills/review-plan/references/proportion.md`, create) and its inputs, the panel order `readiness,proportion,set`, per-unit reviews keyed `plan-<unit>-c<n>`, which units a round dispatches (stalled units excluded), handoff standard questions 8–11 with the `medium`-at-most proportion finding, the readiness/proportion adversarial pair and its recorded disposition, `fix-design` to `approve-spec --void` | U04, U05 | M |
| U07 | File: `gate`/`dry-run`/`apply`/`verify` on the confirmed write list, `filings[]` (appended before the first write), `verify`'s obsolete-link pass over the union, the tracking issue in the latest list (rewritten by `apply`, an issue edit, a new write), `gate --accept` removed, marker recovery on the new markers, `base_at_start`, the labels incl. `superegm:stopped` and the 6-hex handoff label, leavemealone "Create", the `file` skill body | U04, U05 | M |
| U08 | Judges: the `judges` skill body, `judge` adapter and persona, the question-file grammar with several questions, `judges open\|diff\|record\|verdict` with per-question convergence, child card, Astra judge lane with degradation, `min_vendors` | U02, U03 | M |
| U09 | Builders: `launch` with every §11 precondition (the protection, the `pull_request` workflow, the token, the in-flight count, `--idle`), `launch-builder` with its refusals, a fresh worktree per launch after detaching the earlier one, the launched command's environment, the prompt file and the allow-list, `builder_orders.md` incl. the PR body's DoD-results form and the Step defaults of §9.1 (the command a builder runs and the commit subjects it writes when a Step's `Run` and closing lines are absent), `launches/` with the exit file, `record-launch [--exit]`, `interrupt`, `clean` | U02, U03 | L |
| U09b | Events: `status --wait` returning every unreported event, the six event kinds (`closed` with its actor) and the line form, the exit-and-status folding | U09 | M |
| U10 | Foreman: `foreman` adapter and brief, `foreman dispatch` with the dispatch-predicate refusal, the round entry's `runcard` and `launch`, and the recovery of a `collected` round already on the PR, `prepare --dispatch` with the fetched tip as `head`, the `<base>` refusal, `pr_body.md`, `comments.md` (after `posted_at`, plus the aged comments) and the last round's findings, `collect` with the foreman findings (incl. scope paths) and the contested reads and `--not-run`, `tdd-order`, `review post` with `posted_at`, the `outcome` write, its exit 3 and the `awaiting merge` journal fact, the return word | U04, U09 | L |
| U10b | The driver: the `wave` skill body with the loop's invariants as tests through `foreman dispatch`'s refusal, the batch order, the resume derivation incl. pending decisions, `report` after every batch, the end condition incl. idle and pending units, what the elephant does with each word, `decision open\|rule` at every point, the by-hand ruling of a BLOCKED comment | U09b, U10 | M |
| U11 | leavemealone routing and finish: `judges question` and its forms, the §13.2 wiring at points 1–3 in `review-spec`, `review-plan`, `plan`, `wave`, the interface-deviation fan-out; `integrate` with `--close`, `close` and `closed_at`; docs and the README (install notes, the builder account and profile, the protection, the Licence paragraph); release 1.0.0 packed by `prepare_release.py` | U06, U07, U08, U10b | M |
| U12 | Orient (§9.3): `skills/orient/SKILL.md` (create, with `assets/icon.svg` and `test_scenarios.yaml`), `skills/orient/references/graphify.md` (create: how orient drives graphify, the flags, the fallback), `skills/plan/scripts/superegm/orient.py` (create), `skills/plan/scripts/superegm/__init__.py` (modify: the `orient` and `orient_unit` store kinds, `SUBCOMMANDS`), `skills/plan/scripts/superegm/launch_builder.py` (modify: the in-process `orient` call on the launch's ref before `add_worktree`, its refusal, and the `# Orient` prompt section), `skills/wave/references/builder_orders.md` (modify: the orders line), `skills/plan/SKILL.md` and `skills/review-plan/SKILL.md` (modify: the orient sentence each), `skills/using-superegm/SKILL.md` (modify: the typed list), `scripts/pack_plugin.py`, `tests/unit/test_effects.py`, `tests/unit/test_skeleton.py`, `tests/unit/test_packaging.py`, `tests/unit/test_helper.py` (modify: the skill and module lists, `MODULES` included), `tests/unit/test_builders.py` (modify: the `orient` call and the refusal), `README.md` (modify: the Skills list), `tests/unit/test_orient.py` (create), `tests/fixtures/orient/` (create: a small hand-written graph and a fixture tree) | — | L |
| U13 | File adopts existing issues (§9.1, §10): `skills/plan/scripts/superegm/__init__.py` (modify: `Issue` parsed as an optional field, not added to `FIELDS`), `graph.py` (modify: the `Issue` field's `#<n>` in the spec's `## Units` section), `dry_run.py` (modify: the refusals and the `### edit` heading), `gate.py` (modify: the entry's two trailing fields), `apply.py` (modify), `skills/file/SKILL.md` and `skills/plan/references/handoff_plan.md` (the plan skill's schema reference; modify: the field and the dry-run line), `skills/plan/SKILL.md` and `skills/review-plan/SKILL.md` (modify: the landed-row sentence each, §9.1), `tests/unit/test_file.py`, `tests/unit/test_plan.py` (modify) | U12 | L |
| U14 | Launch policy: owners set, PR block, the builder-token recipe and `doctor` (§11): `skills/plan/scripts/superegm/launch.py`, `launch_builder.py` (modify: the owners, role and team checks, `profile_problem`'s hooks check, the PR block read from the ref), `__init__.py` (modify: `DEFAULT_CONFIG` keys, `SUBCOMMANDS`), `init.py` (modify: `owners` and the STEPS text), `doctor.py` (create), `skills/wave/references/builder_orders.md` (modify), `README.md` (modify: step 1 and one sentence naming `doctor`), `docs/claude.md` and `docs/getting_started.md` (modify: the three keys and step 1, pointing to README step 1), `skills/plan/references/handoff_config.md` (modify: brought to `.superegm/config.json`'s key set, the three keys included), `tests/unit/test_builders.py`, `tests/unit/test_helper.py`, `tests/unit/test_leavemealone_finish.py` (modify: the README pins follow the new step 1), `tests/unit/test_packaging.py` (modify), `tests/unit/test_doctor.py` (create) | U12, U13 | L |

Shared files of the 1.0.0 build: `test_helper.py` is U03's alone. `body.py` is U03's and then U05's (the derived Step
defaults), which U03 blocks. Each workflow SKILL.md stub U01 creates is filled
by the unit that owns its section after U02 has set its frontmatter and lines, and edited again
only by U11; U02 is a blocker of every one of them. `README.md` is U01's (skeleton) and U11's
only. The `status`, `launch` and `prepare` modules are edited by U03 and then by U09b, U09 and
U10 respectively, which U03 blocks; the `review` modules by U04 and then U10; the `foreman`
file's writers are U03 (schema), U04 (`review settle`), U10 and U10b, each behind its blockers.
No other file is edited by two units their blockers do not order.

Amendment 2 units (1.1.0): every 1.0.0 unit has landed (1.0.0 was released at 363dd5e); those
rows are landed rows under §9.1's drafting rule, so a plan for this handoff carries sections for
U12–U14 only (for this handoff the elephant applies that rule by hand: the skills carry it once
U13 lands). The units are filed from this spec in the repository's one store (§7), which holds
no open handoff; the handoff id has §7's form, `2026-11-03-superegm-<first 6 hex of the
approval's sha256>`, and the approval record carries the value; the owner sets
`tracking_issue_title` for 1.1.0 in the config before the approval commits it. U13 is blocked by
U12 and U14 by U12 and U13: each edits files its blockers change and consumes nothing from them,
so the waves are {U12} → {U13} → {U14}, and the shared files agree:
`skills/plan/scripts/superegm/__init__.py`, `skills/plan/SKILL.md` and
`skills/review-plan/SKILL.md` are U12's, then U13's (`__init__.py` then U14's);
`launch_builder.py`, `builder_orders.md`, `README.md`, `tests/unit/test_packaging.py`,
`tests/unit/test_helper.py` and `tests/unit/test_builders.py` are U12's, then U14's. None names a 1.0.0 producer in a Consumes
line (landed code is read in the Steps, not consumed from a sibling). The sentences above that
give `test_helper.py` to U03 alone, `README.md` to U01 and U11, each workflow SKILL.md to U11
last, and the rule that later units never create skill folders, describe the 1.0.0 build; U12
creates `skills/orient/`, and U12–U14 edit those files after every 1.0.0 unit landed. Risk: U12
medium (extraction over arbitrary trees: encoding errors, huge files, symlink loops; §9.3's
best-effort reads); U13 medium (an adopted issue's body is replaced wholesale; the dry run shows
the old body's sha256 and `apply` refuses a body that changed since); U14 low. Review focus for
U12's plan: a repository with no docs at all (the map still written; the unit file holds
signatures only); a Scope path that does not exist yet; a `CLAUDE.md` over the cap; a non-Python
repository; a unit whose section is not yet in the store's `handoff_plan.md` (refusal: `run graph
--plan first`); graphify absent, and graphify failing. The version bump to 1.1.0 (both
manifests, `docs/releases.md`), the tag and the release packed by `prepare_release.py` are the
owner's by-hand steps after the three merge, as they were for 1.0.0.

Interfaces (the names the plans will carry):
- U01 → all: the absorbed `state.json` keys and subcommands with EGM's contracts until a later
  unit changes them.
- U03 → U04–U11: `superegm runcard open --skill <s> --artifact <a> [--parent <id>] [--mode <m>]
  → <id>`; `superegm runcard close <id>`; every writing subcommand takes `--runcard <id>` and
  exits 1 with `runcard: <reason>` under the §6 artifact rule; `superegm init`;
  `approvals/<spec-slug>.json` per §7; `foreman/<unit>.json` per §7 (`rounds[]` with `runcard`,
  `launch`, `head`, `phase`, `outcome`, `posted_at`; `decisions[]`; `rulings[]`);
  `handoff_units.json` key `units[<id>].body_sha256` per §7 (its values are written by U05's
  `graph --plan` and absent until then); `state.json` keys `plan`, `filings[]` (written by U07's
  `apply`, absent until then) and `closed_at` (written by U11's `close`, absent until then) per
  §7; py: `store(repo_root) -> Store`, `Store.path(kind, *parts) -> Path`, `atomic_write(path,
  obj)`, `journal(store, line)`, `spec_slug(path) -> str`, `require_runcard(args, skills) ->
  dict`, `require_frozen_units(handoff) -> None`, `open_runcard(store, skill, artifact,
  parent=None) -> str`, `card_add(store, id, key, item)`, `gh(args, *, token=None) -> str`,
  `run_commands(body) -> list[str]`, `step_paths(body) -> list[tuple[int, str, str]]`,
  `dod_items(body) -> list[tuple[int, str, str]]`, `consumes(body) -> list[tuple[str, str]]`,
  `fill_numbers(body, numbers, tracking=None) -> str`, `normalise(text) -> str`, `MARKER_RE`,
  `DECISION_HEADING`; the fake `gh` harness's extension point.
- U04 → U06, U07, U10, U10b, U11: `review open … → <review-id>`; `review record …` (incl.
  `--reviewer set` and `--reviewer foreman`); `review settle …`; `review status --review <id>
  --runcard <id> → one line; exit 0 converged / 5 stalled / 2 cap / 3 open or unopened / 4
  fix-design`; `review rule …`; `reviews/<review-id>/review.json` keys `converged`,
  `converged_round`, `rulings[]`; `round-<n>.json` keys `runcard`, `artifact_sha256`,
  `builder_contested[]` of `{fid, reason}`, `what_ran`; `approve-spec` writes
  `approvals/<spec-slug>.json` with `handoff_id`.
- U05 → U06, U07, U11: `graph --plan <file>` writes `handoff_units.json` with
  `units[<id>].body_sha256` and `unit_<id>.md`; `scan → exit 1 with "<rule>: <line>"`; `decide
  --unit <U> --decision D<n> (--answer "(<id>)" | --default) [--judges <id>]` and the comment
  file it writes.
- U07 → U11: `state.json` keys `base_at_start`, `filings[]`.
- U08 → U11: `judges open … → <panel-id>`; `judges record …`; `judges diff …`; `judges verdict
  --panel <id> → verdict JSON; exit 0 every question converged / 2 not`; the question-file
  grammar.
- U09 → U09b, U10, U10b, U11: `launch [--idle <units>]`; `launch-builder --unit <U> --round <n>
  --runcard <id> → command line; exit 1 with the refusal`; `record-launch --unit <U> [--exit
  <code>]`; `launches/<unit>.json` per §7 (`launches[].round`, `launches[].status`,
  `launches[].result_file`, `launches[].prompt_sha256`); the `**Deviation**`, `**Reply <fid>:**`,
  `**Ruling:**` and `**Builder status:**` headings, the option-line form and the PR body's
  DoD-results form.
- U09b → U10b: `status --wait <s> --runcard <id> → one or more event lines`; the six event kinds.
- U10 → U10b, U11: `foreman dispatch --unit <U> --runcard <id> → <dispatch_id> <child-card>;
  exit 1 when the dispatch predicate fails`; `foreman-<unit>-<dispatch_id>` returns `clean |
  revise | contested: <ids> | cap-reached | target-moved | error`; `review post … → exit 0 posted
  / 3 target-moved`.
- U10b → U11: `report`; `decision open --unit <U> --point <1|2|3> --question <file> → <id>`;
  `decision rule --unit <U> --decision <id> --ruling <text> --by <login | judges:<panel-id>>`;
  the `wave` skill's decision-point hooks.
- U12 → the owner: `superegm orient --spec <path> [--unit U<id>]... [--ref <ref>] --runcard <id>
  → one line per file written: <store path> <bytes>; exit 0 / 1 with "orient: <reason>"`; `orient/map.md` and
  `<6 hex>/orient/<unit>.md` with their first line; py: `Store.path("orient", …)`,
  `Store.path("orient_unit", …)`.
- U13 → the owner: the write list's `issue` entry with its two trailing fields (the adopted
  number, the old body's sha256); `dry-run`'s `### edit #<n> <unit> (old body sha256 <hex>)` heading.
- U14 → the owner: `superegm doctor → one line per prerequisite; exit 0 / 1`; the config keys
  `owners`, `owner_team`, `pr_block_file`.

Waves: {U01} → {U02, U03} → {U04, U05, U08, U09} → {U06, U07, U09b, U10} → {U10b} → {U11}; then,
as a second handoff (`2026-11-03-superegm-<6 hex>`), {U12} → {U13} → {U14}, and version 1.1.0
after all three merge.
