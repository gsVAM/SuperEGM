# SuperEGM — design

Date: 2026-11-03. Status: 1.0.0 released from review cycle 2 (round 5, the cap; cycle 1 ended at
round 6 by the judges' ruling `q-close`: a new approach, not another patch; those cycles are
records outside the store); amendments 2–6 each reviewed in their own cycle in a store's
own numbering (amendments 5 and 6: the 1.2 store's cycles, 2026-11-05, the approval naming the last; owner rulings 2026-11-04 on zoom-out-1-4 and 1-7 (orient re-run on re-render; `--unit` writes unit files only); owner ruling 2026-11-04: the audit-trail line). Fixes 2026-11-05, released as 1.1.2: the tdd-order rule reads `test(S<n>)` subjects only and takes any test file by name (§11.1); test files are found by name wherever they live (§9.3). Owner: gsVAM.
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
Amendment 3 (2026-11-04): the builder as a GitHub App (§11, §16), the convergence rule, the judges record, the mention scan, approve-spec with escalations, the commit trailer (§8, §9.1, §13.1), units U15–U16; owner-approved by text.
Amendment 4 (2026-11-05): Astra on every head review (§8, §11), the redesign ruling (§11, §12, §13.2), units U17–U18, amendment-scoped review (§8), unit U19, one store per handoff (§7, §9.1), unit U20; three follow-ups (§3, §5, §7); owner-approved by text; owner ruling 2026-11-05: approval chain (§5, §11, U20); owner ruling 2026-11-05: App installation and permissions (§3.1, §4.1, §11).
Amendment 5 (2026-11-05): the fleet layer (external-review ingest, rulings by comment, the inbox and notify hook, the headless driver and registry, the foreman verifies), units U21–U25; owner-approved by text.
Amendment 6 (2026-11-05): external review on the elephant's own PRs (`review ingest --pr`, §8, §11.2), unit U26; owner-approved by text.
Amendment 7 (2026-11-06): the builder's plugins and MCP servers, passed per launch (`config.builder.plugins`, `config.builder.mcp`, `Skill` and `mcp__*` rules in `allowed_tools`; §4, §7, §11, §15), unit U27; owner-approved by text.
Amendment 8 (2026-11-06): the default models and efforts per role (`builder.model` and `builder.effort`, `reviewers.model` and `reviewers.effort`, `astra.heads_effort`, `judges.members`; §7, §8, §11, §13), unit U28; owner-approved by text.
Amendment 9 (2026-11-06): split units for parallel waves (the plan rules of §9.1, the proportion and set checks of §9.2, `graph --plan`'s `width:` line), unit U29; owner-approved by text.
Amendment 10 (2026-11-06): the board and the watchdog (§3, §3.1, §4, §7, §11, §11.2, §13.2, §14), units U30–U31; owner-approved by text.
Amendment 11 (2026-11-06): 1.1.3's integrate review carried mediums and the first wave's findings (scope additions to U22, U23, U27, U29 and U30; §7, §8, §9.1, §9.2, §11, §12, §13.2, §14), unit U32; owner-approved by text.

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
judges could not settle, or to a stalled review, a review ended at its cap, an approval
carrying `escalated[]` or a unit stopped for redesign with its brief (§11), each named in the record (§8), merges, and types the next phase. Nothing is merged by a machine. Every review, verdict and launch is on disk with its
isolation recorded.

## 2. Vocabulary

| Word | Meaning in SuperEGM |
| --- | --- |
| **owner** | the human, under the GitHub logins `config.owners` names (one person, possibly several logins; §11). Approves and freezes specs, rules when the judges cannot, reviews and merges pull requests. An administrator of the repository. §11's fence is that the builder account can never update the base branch; those logins (and, under an organization's ruleset, the members of `config.owner_team`) may. |
| **elephant** | the main session. Holds context, orchestrates, launches headless sessions, dispatches foremen and goldfish. Never reviews its own work, never settles a finding against itself, never writes the store itself. |
| **helper** | the plugin's one Python program (§15), run as `superegm <subcommand>`. The only writer of the store. It never dispatches an agent. |
| **store** | the per-repository directory `artifacts_dir` (§7) holding every record SuperEGM writes. `.superegm/config.json`, committed in the repo, is its pointer and configuration. |
| **adapter** | a Claude Code agent definition `.claude-plugin/agents/<id>.md` with frontmatter `name: <id>`, fixed `tools`, and `omitClaudeMd: true`, whose body reads the persona `agents/<id>.md`. Invoked as `superegm:<id>`. A review panel lists reviewer ids; every reviewer id except `set`, `astra`, `foreman` and `external:*` is an adapter id. |
| **dispatching session** | the elephant or a foreman: the session that invokes adapters with the Agent tool and records each dispatch. |
| **goldfish** | a fresh read-only reviewer dispatched through an adapter with tools `Read, Grep, Glob`. Sees only the artifact and the evidence it is handed. Never spawns. |
| **judge** | a goldfish with a model override that answers a question file by option id instead of reporting findings. |
| **foreman** | a sub-elephant: a named subagent dispatched through the `superegm:foreman` adapter, in the foreground, to run one review round on one PR head and return one word. Its memory is `foreman/<unit>.json` and the PR's comments, never its context. |
| **builder** | a fresh headless local Claude session whose brief is one issue body, the builder orders, the repository's PR block when configured, the unit's orient text (§9.3), the rulings posted on its issue, and from round 2 the foreman's reviews of its own branch. Writes code in its own worktree under the **builder account**, commits test-first, opens a draft PR. Not a goldfish: it writes. Never spawns. |
| **builder account** | a second GitHub account with write access and no administrator or bypass role, whose token the elephant holds (`config.builder.gh_token_env`); or, on the App path (§11), the GitHub App installed on the repository, acting as `<slug>[bot]`. Every PR a wave opens is authored by it, and under §11's protection its credential cannot update the base branch, so nothing a wave runs can merge. |
| **Astra lane** | an optional extra reviewer (of a spec, a plan or, from amendment 4, a PR head) or judge on a non-Claude model (GPT-6 Astra) driven by the external `claudex-loop` runner (a Python CLI over the Codex CLI). Launched by the elephant from the main conversation, or by the foreman on a head (§11), never through an adapter. Recorded `not run (<reason>)` when the runner is absent or its lane is down. |
| **unit** | one buildable piece of a frozen spec: one issue, one branch, one PR. Ids `U01`, `U02`, … are stable for the life of a handoff. |
| **handoff** | one run of plan → file → wave → integrate for one frozen spec. Its id (§7) names the branches, the issue marker lines and `state.json`, and never changes while any unit is filed. Its files live under `artifacts_dir/<handoff id>/` (§7); one handoff per opening approval, and a spec's handoffs run beside one another, each at its link of the approval chain (§7, §9.1); `close` ends it (§12). |
| **wave** | the set of units whose blockers have all landed, launched together. At most `max_in_flight` units are in flight at once; a unit is in flight from its first launch until it lands, is stopped, its latest round's outcome is `clean` (§7; an outcome an ingest rewrites `revise` makes it ready again, not in flight, §11), the elephant names it idle (stalled or CI-waiting, §11) or, from amendment 5, it is pending a decision (§11.2), and a freed slot is refilled. |
| **head** | the commit at the tip of a unit's PR branch when `prepare` fetches it (§11). |
| **round** | one review of one artifact (a spec, a unit's plan body, or a PR head): dispatch, findings, verdict. Rounds are numbered per review; a round that is not `completed` (§8) does not count toward the cap. |
| **clean** | the verdict on a round with no unsettled high or medium finding (§5). The destructive skill is always written `/superegm:clean`; from amendment 10 `wave` carries its `destructive-local` effect kind too (§14), for the watchdog's kill at the owner's configured bound (§11, §14). |
| **stalled** | a review whose two latest rounds under one run card are not `completed` (§8). It ends the invocation for that artifact; it is not a cap and not a pause. From amendment 10 also a launch past `builder.stall_minutes` with no newer commit of its own (§11): the event line, the journal line and `exited (stalled)` carry that sense. |
| **landed** | a unit whose watched PR is merged into `<base>` and whose issue is closed as completed, whoever closed it. Only landing makes dependants ready. |
| **stopped** | a unit a ruling or the owner ended: issue open under `superegm:stopped` (or closed by the owner), branch kept, never relaunched; the owner lands it by hand or closes it with its unlanded dependants and re-appends what is still wanted (§12). |
| **DoD** | definition of done: the numbered, checkable items in a unit's body; the standard every head review is judged against. |
| **review panel** | the 1–6 reviewers written into a run card for one artifact. Fixed for every round. |
| **judge panel** | the judges (three models from two vendors) consulted until every question converges. |
| **run card** | the on-disk record of one typed invocation: skill, artifact and its hash, review panel, model tiering, mode, parent card if any, what it produced. Every effect requires an open one; every round records the top-level card it ran under. |
| **effect** | anything that leaves the working tree: GitHub writes, remote branches, starting a session or worker, writing the store, destructive local operations. |
| **leavemealone-mode** | the mode in which every decision point listed in §13.2 goes to the judge panel first; the owner is paused only with the questions the judges do not converge on within their cap. |
| **graphify** | an external, optional CLI (the PyPI package `graphifyy`, so spelled; the command `graphify` on `PATH`) that extracts a code graph from a directory by AST with no model (its headless `update`; `GRAPHIFY_OUT` names where its `graphify-out/` goes) into `graph.json`: nodes with `source_file` (relative to the directory it scanned), `source_location` and an integer `community`; edges marked EXTRACTED, INFERRED or AMBIGUOUS with a confidence. `orient` (§9.3) reads that file and nothing else of graphify's; nothing requires it. |
| **external reviewer** | a review thread on a unit's PR, or on the spec PR (amendment 6), from any login but the builder account's, a person's or a bot's (Devin's), recorded by `review ingest` (§8, amendment 5) as findings of the reviewer id `external:<login>`: accepted on kinds `head` and `spec` (the spec PR, amendment 6), outside the panel, never an adapter, never dispatched. |
| **registry** | `~/.superegm/registry.json`, outside every store: the list of the stores on this machine, written by `superegm register` alone and read by `inbox --all` and the driver (§11.2). It lists stores, not a graph; a store's own `handoffs/<id>.json` files index (§7) names that store's handoffs. |
| **driver** | the owner's timer (a launchd agent; on Linux a systemd user timer) that runs `superegm driver tick` every `install --interval <minutes>` (15) in the environment of `~/.superegm/env`; a tick types `wave --leavemealone` for one open handoff of a registered store at a time (one session per store), chains nothing and merges nothing (§11.2). The session it launches runs with `SUPEREGM_ROLE=driver`. |

## 3. Goals, non-goals, anti-goals

**Goals**
1. One plugin, one vocabulary, one store, one convergence rule, one entry rule.
2. Spec and plan are distinct artifacts with distinct gates; both get adversarial goldfish review
   before anything downstream reads them.
3. Every Claude goldfish and judge is isolated by construction (adapter, not prompt), and the
   record says what each dispatch saw. The foreman and the builder are not goldfish: a builder's
   tools are an allow-list, it acts as the builder account, and nothing the plugin ships can
   approve or merge a pull request (§11); the foreman's "never merge, never remove, never launch"
   (a head's bounded Astra runner excepted, §11) is its brief, and the elephant's own session holds the owner's credentials; both are named in
   §4.1 as accepted residual risks.
4. Every independent step runs concurrently: goldfish within a review, plan reviews across units,
   builders within a wave, foremen for every head that is ready at once, judges within a panel.
5. Maximal autonomy on request: leavemealone-mode replaces the owner at every decision point in
   §13.2 with the judge panel; only non-convergence reaches the owner.
6. Merge stays human. Nothing the plugin ships approves or merges, ever.

**Non-goals (v1)**
- Harnesses other than Claude Code. EGM's Codex/ChatGPT host and superpowers' ten other harness
  entry points are not absorbed. The Astra lane uses the Codex CLI as a reviewer, not as a host.
- Chaining phases. Each phase is typed; a night of leavemealone work is one phase. A timer that
  re-types `wave` (the driver, §11.2) is one phase re-typed, not a chain: it never types
  `integrate`, `plan`, `review-plan` or `file`.
- External builder backends (cloud workers). Builders are local sessions.
- A local, no-GitHub wave. The wave files issues and reviews PRs; that is the one execution path.
- The brainstorming visual companion (a local Node server that also fetches a logo from the
  network). Brainstorming stays text-only.
- A target repository's test suite as SuperEGM's evidence. DoD commands are run by the builder
  before it opens its PR and by the repository's CI on the head; the foreman reads CI as evidence
  and, from amendment 5 (the owner's word, not a panel's), re-runs the body's DoD `Run` items in
  its review worktree as a check on the builder's paste and on each item's exit, nothing more (§11): CI stays the
  evidence for the suite, and SuperEGM's `clean` verdict still needs CI green on the head.
- Automatic splitting of a unit that will not converge. At a PR cap the rulings are "one more
  round", "stop" or "redesign" (§11, a stop with a brief); reshaping units is the owner's, by hand,
  with `integrate`'s append path or the brainstorm the brief starts.
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
   file the launched command wrote, by the return of a bounded foreground command the session itself ran
   (the Bash tool's timeout ends it and returns; a foreman's Astra lane, §11), by the owner's typed
   interrupt, or by a boot id recorded at launch that is not the machine's current one (amendment 5,
   §11.2: no process survives a reboot). From amendment 10 the watchdog's kill at
   `builder.stall_minutes` is the owner's standing interrupt, set once in the config, and the
   exit file the wrapper writes on the signal is its proof (§4, §11).
9. A code-aware Markdown mention scanner. The scan is raw text plus an allow-list, with the
   one exception §9.1 states, in §9.1's smallest CommonMark grammar and no other: a fenced code
   block and an inline code span are skipped, so a `@` inside either is never a mention (GitHub
   does not notify for a mention inside code); everything else stays raw text.
10. A ruling, decision or review that an account outside `config.owners` wrote (the builder
    account first among them) being honoured as the owner's or the judges'; a close by any
    account but the builder's stops the unit as 1.0.0 built it (write access is its
    authentication), never honoured as a ruling. GitHub's
    author field is the authentication; nothing in a comment's text is (§11.2).

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
  `stale`/`max_minutes` (a bound the owner sets returns as amendment 10's `builder.stall_minutes`,
  the watchdog: the kill is the owner's standing interrupt, its exit file the proof); a `publish` effect kind; a second Astra config block; a `wait`
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
- **Amendment 3: the machine account alone.** Kept as the quick path for a personal
  repository; the App path is added because an organisation's seat, SSO or token policy may
  grant no second account or no fine-grained token, a fine-grained token expires in 90 days and
  is rotated by hand, and a classic token's `repo` scope reaches every repository the account
  can see, while an App has the installations the owner chose, four scoped permissions and a
  key with no scheduled expiry.
- **Amendment 3: a one-hour App token minted by the elephant at launch (or on each relaunch)
  instead of the builder minting on demand.** Rejected: a builder round runs for hours and the
  token dies under it; a refresher the elephant starts from the main conversation, re-minting
  into a per-launch file, would keep the key out of the builder's environment but is a second
  long-lived process whose liveness §4's doctrine forbids guessing about, and a wave loop that
  pauses while builders run on; the `superegm-token` helper and the `gh` shim at an absolute
  path (§11) mint on demand in the builder's environment, the orders naming that path. A static
  machine-account token stays the quick path for a personal repository.
- **Amendment 3: `allowed_mentions` alone for a `@` inside a fence (`@pytest`).** Kept as the
  general rule; the one fence-and-span exception of §9.1 is added because a mention inside code
  never notifies anyone, and every plan with a parametrized Step tripped the scan until the
  owner edited the config.
- **Amendment 3: `approve-spec`'s `escalated` refusal as a judge decision point.** Rejected: an
  escalated finding is the owner's by definition (§8); in leavemealone-mode the approval record
  and the journal carry the ids instead of a pause (anti-goal 7).
- **Amendment 3: a second OS user (`sudo -u`) so a builder cannot read the owner's keys.**
  Rejected as a remedy: the whole wave shell under a second user carries the owner's `gh`
  login with it (the elephant holds the owner's credentials by design, goal 3), and the builder
  alone under a second user cannot commit (a worktree's HEAD, index and refs live under the
  owner's `.git/`, and the store, the profile and the key would all have to be shared). §4.1
  names the residual as accepted on both paths.
- **Amendment 4: the Astra lane kept off heads (the 1.0 ruling `q-wave` Q1).** Reversed by the
  owner on 2026-11-04: a second vendor on every head was the lane's point, and a foreman can
  run one bounded runner call (§4, §11); the cost is one run per head per round (§4.1).
- **Amendment 4: an automatic `split` ruling back, beside `redesign`.** Not revived: `redesign` is
  the owner's or the judges' word at a head's point 1 or 2, stops the unit and hands a brief to a
  typed brainstorm; nothing re-cuts a unit by itself (the cycle-1 removal stands).
- **Amendment 4: the shared flat store with a `<6 hex>/` prefix per handoff (1.0's layout).**
  Rejected: the prefix kept the unit files apart and nothing else, so two handoffs shared
  `state.json`, the journal and the run cards; one directory per handoff gives each its own, and
  a flat store is read in place as legacy (§7).
- **Amendment 5: one long-lived session instead of a timer that re-types `wave`.** Rejected: a
  session is one phase (§3), dies with its terminal, and its liveness is the guess anti-goal 8
  forbids; a tick is a phase re-typed, with an exit file per launch. A GitHub Actions schedule
  that re-types it was rejected with the fleet box: the owner's login would leave the machine.
  A webhook needs a listener, which is the long-lived process again.
- **Amendment 5: a token inside a ruling comment, the hook's command line in the committed
  config, a graph of stores in the registry, `setsid(1)` for detachment.** Rejected: GitHub's
  author field authenticates a ruling and a token would make a phone ruling harder (§11.2); a
  command line in repository data lets a commit choose what runs as the owner (`~/.superegm/notify`
  instead); a store's handoffs are its own index's and a cross-store `Blocked by` is prose and
  `Landed:` rows (§9.1); macOS has no `setsid(1)`, so the wrapper is started in its own session.
- **Amendment 6: the owner reading the elephant's PR threads by hand; a pseudo-unit for those
  PRs through U21's `--unit` path; an ingest at every `review-spec` round.** Rejected: by hand is
  the gap (the spec PR sat unread); a pseudo-unit would need a head, a foreman and a builder the
  elephant's PR has none of; an ingest per round is a second moment (anti-goal 1): the one kept by choice is before the
  approval, every push's threads read then at the cost §8 names (a stale thread settles by an
  edit and a round, or by the owner's decline or a point-1 overrule), the PR open from the
  review's first round (§8); a
  plan kind and a `file` step were cut in review: no plan PR exists and `file` opens none.
- **Amendment 7: a builder profile with no plugins (1.0.0's rule) and cycle 2's removal of
  builders invoking skills (above).** Both reversed by the owner on 2026-11-06: a builder that
  may run no skill and no MCP tool cannot use the house's tooling (context7, ponytail). The builder's plugins and MCP servers are passed on its command line per
  launch (`--plugin-dir` per listed plugin, `--mcp-config <launch file> --strict-mcp-config`,
  §11), so the set is exact by construction and the profile stays the login; each plugin's
  version and hook events and every server go on the launch's record. A listed plugin's own
  hooks come with it: the owner named the plugin, so its hooks are chosen, not hidden (ponytail's
  lazy mode is its SessionStart hook). What stays refused is a hook or a skill the owner did not
  choose through the list: the profile's `settings.json` hooks, a profile `skills/` or
  `commands/` directory, a synced or installed plugin of the profile's own. Rejected: a profile
  the owner installs the plugins into, inspected at the launch (what loads is then the profile's
  state, not the config's, and a plugin both installed there and passed loads twice), and the
  skills' text inlined into the orders (no hooks, no updates, a copy to maintain).
- **Amendment 10: a per-step timer; a stall left `idle` with no kill; the wave report alone as
  the board.** Rejected: a per-step timer needs the builder's cooperation and bounds nothing it
  does not report; a stall left idle leaves its process running for the night, and
  `launch-builder` refuses the relaunch while the launch is not terminal; the report is a store
  file the owner cannot see from the tracking issue, the one page GitHub shows them. The
  watchdog's kill is the owner's standing interrupt at a bound they set, the exit file the wrapper
  writes on the signal its proof (anti-goal 8 amended); the board is the tracking issue's page.

## 4. Constraints

**Platform (from the live probes and the two code bases; do not re-derive)**
- `name` on the Agent tool makes an agent addressable and resumable; it is not a distinct
  teammate. Several agents may be dispatched in one message and run concurrently in the
  foreground; their returns arrive together.
- A foreground Bash tool call is capped at 10 minutes (600 s); a helper call that runs code under
  it (the foreman's `collect`, §11) bounds its runs below that cap.
- `omitClaudeMd` tracks the agent definition, never the name: an adapter subagent does not load
  CLAUDE.md or the memory index. SessionStart hooks run for sessions, not for Agent-tool
  subagents, so this plugin's hook never reaches a goldfish. **SubagentStart hooks in the owner's
  own profile do reach adapter subagents** (observed in cycle 1 and in every round of cycle 2);
  the plugin cannot suppress them, so every dispatch record carries what the goldfish reported
  seeing, and the README tells the owner to run reviews from a profile without SubagentStart
  hooks.
- A Bash background command dies when its own agent returns; one started from the main
  conversation survives across turns. So builders and the Astra runner are launched by the
  elephant, never by a subagent that then returns; the foreman's lane on a head is one bounded
  foreground call (the tool caps a foreground call at 600 s), no background command (§11).
- Claude Code has no plugin-on-plugin dependency and cannot disable another plugin's hook or
  skills. Hence absorb, not depend.
- A per-dispatch `model` override on a `model: inherit` adapter is honoured; a per-dispatch
  `effort` is passed only when the Agent tool offers that parameter. `claude -p` takes the prompt
  as text (`claude -p "$(cat <file>)"`); `--output-format json` writes one result object;
  `--permission-mode` takes `acceptEdits` or `bypassPermissions`; `--allowedTools` entries are
  tool names, the one prefix form `Bash(<prefix>:*)`, which matches on the command's text and
  cannot exclude a refspec, and, from amendment 7, `Skill(<name>)` and `Skill(<name> *)` (exact
  and prefix, Claude Code's own forms; a plugin's skill is named `<plugin>:<skill>`) and
  `mcp__<server>__<tool>` or `mcp__<server>__*` (a plugin's bundled server is named
  `plugin_<plugin>_<server>`); a rule naming no loaded skill or tool grants nothing; a
  headless session with no `Skill` entry invokes no skill. `--plugin-dir <dir>` loads a plugin
  for the session (repeatable; its hooks, skills and bundled servers with it); `--mcp-config
  <file> --strict-mcp-config` loads that file's servers and no other configuration's.
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
- Headless sessions started by SuperEGM set `SUPEREGM_ROLE` to `builder` or `goldfish` (a tick's
  wave session, `driver`, §11.2), and
  `SUPEREGM_RUNCARD` to the run card they run under. The hook prints nothing when the role is
  `goldfish` or `builder`. The builder profile (`config.builder.profile_dir`) is created by
  the owner as the login alone: no hooks, no `CLAUDE.md`, no plugin of its own (the
  organization's managed plugins are policy, recorded), `syncClaudeAiPlugins` false and, from
  amendment 7, `disableClaudeAiConnectors` true in its `settings.json` (the account's claude.ai
  connectors reach every subscription-login session, and the allow-list stops calls, not
  descriptions) and no `skills/` or `commands/` directory; `launch-builder` refuses otherwise
  (the hooks refusal is 1.1.0's, U14; the setting and directory checks are U27's). The builder's plugins and MCP
  servers come from the config, passed per launch (§11).

**Liveness and destruction (EGM round-12 doctrine, binding)**
- A builder launch is **terminal** when its exit file exists (the launched command writes
  `<result-file>.exit` on any exit), when the owner's typed `/superegm:interrupt` recorded
  `interrupted`, or, from amendment 5, when `driver tick`, `launch-builder`'s terminal check or
  `runcard open` recorded it `interrupted (reboot)` on the one proof §11.2 adds (a boot id recorded at launch that is not the machine's current
  one: no process survives a reboot), or, from amendment 10, when the watchdog's signal made the
  wrapper write the exit file `stalled` (the wrapper traps the signal) within 30 s, the one
  proof; no exit file at that bound is recorded `kill_failed` on the launch, which stays
  `running` and is signalled no more, the unit marked idle with that reason and listed by the
  inbox for the owner's typed interrupt, nothing else touched; a later pass that finds its exit
  file reports the exit as the file reads, which clears the mark (§11). An Astra review run is terminal when its `result.json` says `completed` or
  `failed`, or when the bounded command that ran it has returned without one (its timeout, §11:
  the lane is then `not run (timeout)`). A round is terminal in phase `posted`, or `collected` with a `not run` reason.
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
| A builder-authored comment is taken for a ruling or a decision; a builder edits CI or files outside its scope so its head reads green | a machine clears its own finding | the helper honours `**Ruling:**` and `**Decision D<n>:**` comments only from logins in `config.owners` (amendment 5; 1.0.0 excluded the builder account's login alone); the CI finding is settled by no one; a changed path outside the unit's Scope paths is a `foreman` high | U04, U09, U10 |
| Judges from one vendor only (Astra lane down) | less independent verdicts | `judges.min_vendors` (default 1); the record says `degraded: true` whenever fewer than two vendors answered | U08 |
| A spec edit after a clean round or after approval; an approval not yet on the base branch | unreviewed bytes frozen; bodies cite a stale hash; builders branch from a base without the frozen spec | every round records the sha256 it reviewed; `approve-spec` refuses unless the spec's current sha256 equals the converged round's; `graph` refuses when it differs from the approval; `launch` refuses until the spec at `origin/<base>` hashes to the approval or to a later link of its chain (§11) | U04, U05, U09 |
| The claudex-loop runner's lane down | no second vendor | every lane use is optional and recorded `not run (<reason>)`; the every-reviewer-ran check counts its `not run` record | U04, U08 |
| CI absent, queued for ever, or needing manual approval on a draft PR | rounds never start | `launch` refuses the first wave unless `origin/<base>` carries a workflow triggered on `pull_request`; `foreman dispatch` refuses while a head's CI is pending or absent; a head whose CI is still pending or absent at two consecutive `deadline`s of one `wave` invocation is named idle (it holds no slot), the loop ends for it, and the wave report says so | U09, U09b, U10, U10b |
| The owner's profile hooks reach a goldfish | priming the record cannot remove | the dispatch record carries the goldfish's own report of exposure; the README names the profile rule | U04 |
| Extraction over an arbitrary tree (encoding errors, huge files, symlink loops) | `orient` crashes or hangs on a repository | best-effort reads (`errors="replace"`), files over 1 MB skipped, symlinks not followed, one export of the tracked tree (`git archive`) as the only input | U12 |
| graphify's output reaching goldfish and builders as evidence | a wrong edge misleads a reviewer or a builder | the graph is built from an export of the ref `orient` was given, with no model; `orient` projects EXTRACTED edges inline and lists any other edge apart with its confidence; the file's first line names the graph's sha256 | U12 |
| An adopted issue's body overwritten wholesale | a person's text lost | the dry run shows the old body's sha256, `apply` refuses when the body changed since, comments and title are kept | U13 |
| A PR block appended verbatim; a token recipe that does not fit the repository's owner kind | a builder PR the repository's CI rejects; a token with no access | the block is the repository's own text and its CI checks it; the recipe names the fine-grained form for an organization's repository and the classic form for a personal one, and `doctor` reports the token's kind | U14 |
| The App's private key readable by the builder session (it mints in the builder's environment) | a misbehaving builder mints tokens for every repository the App is installed on | the key is a file the path names, never PEM text in the environment; the App's installations are the owner's choice (several accounts allowed, owner ruling 2026-11-05: a public App when several, which a stranger may install too), so a builder that mints reaches every repository every installation includes, an accepted residual of the ruling the owner bounds by reviewing the installations `doctor` lists (`GET /app/installations` with the JWT: account and repository count per installation, information only) and by installing narrowly; a `doctor` line reads `GET /repos/<repo>/installation` with the JWT and refuses unless an installation includes `config.repo`; a builder runs as the owner's OS user, so code it runs (a test, a DoD command) can reach what that user can on either path, the owner's SSH key and keyring included, and the protection does not fence the owner's own logins: an accepted residual of a local session on both paths, which no by-hand step of this plugin removes (§3.1 rejects the second OS user); a builder that commits a token is stopped by GitHub's push protection where it is enabled, and one that commits the key by its non-provider pattern scanning where that is enabled too (two fields `doctor` reports; free on a public repository), otherwise either is seen by the owner's eyes on the diff, after which the owner rotates the key or token; each minted token lives its hour unrevoked, a residual beside the key's; the elephant minting at launch was rejected (§3.1: a round outlives an hour) | U15 |
| A timer that runs `wave` unattended with the owner's credentials (the `gh` login, the App key path, the profile) | a session acts as the owner while nobody watches; every PR and issue comment (`comments.md`, any author) and every ingested thread (§8) reaches that session's foreman as text | the driver types one phase, `wave --leavemealone`, and chains nothing; a tick launches only when the store has no open `wave` card or live launch of its own and the handoff no open typed phase card (a reboot proven by the boot id excepted), and `runcard open` refuses a typed `wave` store-wide and a typed `plan`, `file`, `integrate`, `review-plan` or `orient` on the handoff while a tick's launch has none; the session never asks, journals and ends; merge stays human (the driver never merges; the inbox lists merge-ready PRs); the owner's login never leaves the machine (a fleet box is not supported); the launchd agent runs only what the plugin root names; a ruling is parsed by `ruling_of` from owners only, never read as prose; accepted residual: the credentials are the owner's, unattended (`~/.superegm/env`, mode 0600: the same the owner's shell holds), in a session that never prompts (`bypassPermissions`, or an allow-list as wide: the U24 plan's); the machine stays awake and logged in (a `gui/<uid>` agent fires no tick in sleep, and a sleeping machine suspends the live session's builders: `pmset` or `caffeinate`, a by-hand step; `doctor`'s driver line reports the sleep setting as information); and prompt injection through comment text into the foreman's context, bounded by its brief and by merge staying human (§11.2) | U24 |
| The head's code runs on the owner's machine (the foreman re-runs the DoD `Run` items) | a builder's test reaches what the owner's OS user can: the keyring, `~/.ssh`, the App key file, the store itself | the run's environment is the builder's shut-out one (§11: no owner git config, SSH or askpass; the sentinel `GH_TOKEN`; `SUPEREGM_APP_KEY` unset), which removes the variables and not the filesystem; `collect` reads every input it judges before the first `Run` item and writes the round's record and `foreman/<unit>.json` back whole after the last, so an edit a run makes to those two files is overwritten; the re-run is bounded by `config.foreman.run_timeout_minutes` and its process groups are killed at the bound; a `Run` line installs into the worktree, never globally; a service the worktree lacks reads `ran red`, the plan's defect; accepted residual: the head's code runs as the owner's OS user, exactly as the builder's own test run of the same code already did (§11: the builder is a session on this machine), and a run, or a process it leaves behind, can write every other file of the store (a forged exit file, `state.json`) and the checkout's shared `.git/` (a hook or a `core.hooksPath`: the helper's own git calls pass `-c core.hooksPath=<an empty directory> -c core.fsmonitor=false`, so `prepare`'s and `launch-builder`'s checkouts run none; `collect` reads `.git/config` before the first `Run` item and writes it back after the last, as it does the two store files, so a `credential.helper`, `core.sshCommand`, `insteadOf` or `include.path` a run writes is undone before the next fetch; the owner's next typed commit, a process the run leaves behind, and a sibling `collect`'s read between a run's edit and the write-back (the normal batch of several ready heads) are the window; `doctor` reports the hooks directory's contents and a `core.hooksPath` as information), and the owner's files the next tick runs (`~/.superegm/notify`, `~/.superegm/env`, the plist, the installed plugin root; `doctor` reports the hook's sha as it reports the hooks directory) | U25 |

**Cost and timeline (estimate, not a promise).** One leavemealone phase: spec review 2–5 rounds
× 6 goldfish (two is the floor, the last one clean and its bytes left alone; this spec's own
cycles each ended by a cap ruling, the usual exit for a six-reviewer review); plan review 2 rounds × 13 units × 3 goldfish; a wave of 5 builders × 2 rounds with 2
goldfish and one Astra run per head; up to one judge panel (3 judges, 1–2 rounds) per review round with a contest.
About 180 subagent dispatches and 10 headless sessions. The 1.0.0 self-build (§17) is six waves; at one
wave a night it is one week (the 1.1.0 and 1.1.1 handoffs add three and two). The first mid-term exam is that build, filed and driven by hand by
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
refuses the first wave until the spec at `origin/<base>` hashes to the approval's `sha256` or to
a later link of its approval chain (§11). The
same step follows every `--amend-units`, and the owner then types the next phase; nothing chains.
On an existing repository the elephant may type `/superegm:orient` (§9.3) before phase 2 for its
own reading; the phases need no typed step: `plan` and `review-plan` regenerate the map and every
unfiled unit's `orient/<unit>.md` when they start and after each `graph --plan` they run,
`review-plan` hands the unit file to the readiness goldfish, and `launch-builder` regenerates it
from the launch's ref, so no phase reads a stale file.

Rules that span phases:
- **The spec is frozen** by the approval record at its sha256. Every issue body cites the spec
  path and that hash. A change to any section other than `## Units` reopens spec review as a new
  cycle of its review, reviewed in scope (the sections that changed since the last approval and
  their neighbours, §8; the whole spec on `--scope whole` or when no approval exists), and marks
  every unfiled plan stale; rows appended to `## Units` are
  re-approved by `approve-spec --amend-units` without a review round (§12). Filed units are
  unaffected, their bodies being frozen by hash already, and their handoff keeps its id; the new
  approval opens a new handoff (§7; a re-approval after a void keeps the handoff, §7's one rule),
  where the unfiled rows are planned: an older handoff is frozen (`plan`, `review-plan`, `file`
  and `graph` refuse it, §7), which is what "stale" means.
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
  finding in it is a regression of a prior round's fix AND the round's `artifact_sha256` equals
  the artifact's current bytes where the kind has a byte test (§8: a head has none). Lows never
  block, and after a clean round a low is fixed only while another counted round can run; at
  the cap it is settled `declined` (or left: it never blocks), the approval's journal line names
  it, and the artifact is approved at the clean round's bytes. A review is **at its
  cap** when its counted rounds ≥ 5 + its `continue` rulings; at the cap a ruling is required
  (§13.2) before any further round; `accept` makes the artifact converged (`converged: by ruling
  <id>`); `continue` may be ruled at most once per review cycle; after `stop` no ruling is
  accepted and the cycle stays at its cap; a new cycle starts with a fresh cap. No review has a
  second kind of cap. A review may instead be **stalled** (§8), which ends the invocation for
  that artifact and nothing else.
- **The store is the memory; the session is not.** A fresh session per phase (or per review
  cycle) is the normal way to run a long handoff; a session is never carried across phases for
  hours, and after a plugin install or update the next phase starts in a new session (adapters
  and skills load at session start). Every skill that commits (`review-spec`'s fixes and
  `approve-spec`'s approval commit) works on the checkout's current branch and never
  switches branches or adds a worktree in the owner's checkout: its first step says "start on
  the branch you want the commits on", and `using-superegm` recommends one worktree per
  handoff. Where the base ruleset restricts updates to the owners, the owner's merge needs the
  admin bypass (`gh pr merge --admin`): `doctor` says so as information, and `wave` and
  `integrate` say it where they tell the owner to merge. `skills/using-superegm/SKILL.md`, the text
  the hook injects into every session (§6), carries these four rules (U19).

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

One store per target repository, one directory per handoff inside it (U20). The store level
holds what precedes or spans handoffs: `handoffs/<id>.json`, one file per handoff (`id`, `spec`,
`opened_at`, `closed_at`; the index is the directory, so no two sessions share a write);
`approvals/<spec-slug>.json`, the spec's approval history (below: its last entry is the latest
approval, the one `review-spec`, `latest_cycle`, `--amend-units` and `--void` act on, and the
chain is the list's order); the spec reviews (`reviews/spec-<slug>-c<n>/`,
their run cards and judges panels, which precede the handoff they lead to; an integrate review,
`spec-<slug>-integrate-c<n>`, is its handoff's and lives in its directory); and the store's own
`journal.md`. `artifacts_dir/<handoff id>/` holds everything of a handoff from its approval on:
`state.json`, `journal.md`, the plan files, the plan and head reviews, run cards, launches,
worktrees, foreman, `orient/` (the map, the export and graphify's caches, one per handoff, so
two handoffs' sessions never write one export, §9.3), judges panels and brainstorm briefs,
directly under it
(the handoff's approved sha256 is its latest history entry's; no copy is kept there). A
handoff's file is written by its own `approve-spec` (opened; `--void` on a handoff with no filed
unit closes it through `close`'s own write) and `close` (`closed_at`) and by nothing else: a flat 1.0/1.1 store is read in place, its `state.json` and `<6 hex>/` prefixes
naming its handoffs as `legacy: true` rows every read derives in memory, resolving to the flat
paths (`id` and `sha256` from `state.json` and the approval record where they agree, else
null), a `handoffs/<id>.json` written for one the first time `approve-spec` or `close` touches
it, and nothing migrated. Resolution, once, in `__init__.py` (`store()`, which every
subcommand's `Store` comes from, so the flag itself needs no subcommand edit; U20's module
edits are the path forms and the refusals): `--handoff <id>` on every subcommand, `runcard
open` included, names the handoff; a card records the handoff it resolved, and card ids carry it
(`<skill>-<6 hex>-<n>`, counted per handoff: unique across the store with no shared write; a
card that precedes any handoff, `review-spec`'s and its judges' child cards, lives in the
store's `runcards/` as `<skill>-<6 hex of the spec slug>-<n>`, counted per spec); without the flag, a
subcommand given `--runcard` or `--dispatch` takes the card's handoff (the typed skills take
`[--handoff <id>]` after their `<spec-path>` or `--unit` and pass it to `runcard open`; the
foreman's brief carries the handoff id and the foreman passes `--handoff <id>` on every
subcommand it runs); a `--spec` or `--plan` subcommand with no card takes the spec's latest
approval's; a `--unit` subcommand or a unit-keyed card with no handoff takes the one open
handoff whose `state.json` lists the unit as filed, refusing and naming both when two do; a spec
review id resolves to the store level, any other `--review` id through the card; the inbox is the
store-wide read (§11.2), `status` and `report` one handoff's (amendment 11). An older handoff is frozen: `plan`, `review-plan`,
`file`, `graph` and `approve-spec --amend-units | --void` refuse for a handoff whose latest
entry is not the history's last (`<handoff>: not the latest approval: plan the rows in the
latest handoff`); its filed units run (`wave`) and it integrates and closes (§12); a void of a
handoff with no filed unit closes it (`approve-spec --void` runs `close`'s write: `closed_at` in
the handoff file and in `state.json`, journaled `closed: voided`), so the re-approval opens a
fresh one. The
helper is the only program that writes it, and every file has exactly one writing invocation
at a time:

| File | Writer |
| --- | --- |
| `state.json` | the elephant's typed skills (`plan`, `file`, `wave`, `integrate`), one at a time; `close` for `closed_at` (`approve-spec --void` on an unfiled handoff runs it); `notify` for `notified` alone, under a `wave` card (§11.2) |
| `handoffs/<id>.json` | that handoff's `approve-spec` (opened; `--void` closing an unfiled handoff) and `close` (its `closed_at`) |
| `approvals/<spec-slug>.json` | `approve-spec` |
| `handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`, `handoff_bodies.md` | `plan` (`graph --plan <file>`; `decide` re-renders one unfiled unit and leaves a filed one as filed) |
| `reviews/<review-id>/…` | the invocation that opened that review; on a head, also the foreman dispatch the round records (`review record`, `collect`, `review post`); `review ingest --pr` for `review.json`'s `ingested[]` (amendment 6, §8) |
| `judges/<id>/…` | the invocation that opened that panel |
| `runcards/<id>.json` | the skill that opened the card; `card_add` for later facts; a handoff's open `wave` card marked `interrupted` by `driver tick` (on its launch's exit file, or on the boot-id proof: a launch's or a typed card's recorded boot id that is not the machine's) or `driver reset` (§11.2) |
| `launches/<unit>.json`, `launches/<unit>_r<n>_prompt.md`, `launches/<unit>_r<n>_bin/`, `launches/<unit>_r<n>_plugins.json` and `launches/<unit>_r<n>_mcp.json` (amendment 7: the plugins passed at the launch with their versions, directories and hook events, the profile's managed plugins, and the MCP file passed, superseding the `_managed.json` of 1.1.2's fix-k) | the elephant (`launch-builder`, `record-launch`, `interrupt --launch`); `driver tick`, `launch-builder` and `runcard open` for `interrupted (reboot)` alone (§11.2); `launch-builder` for the `running` entry, once (amendment 10), and `record-launch --exit stalled` for `exited (stalled)` and `kill_failed` (amendment 10, §11; the entry re-read before the write, an `interrupted` it finds kept) |
| `worktrees/<unit>/` | the elephant (`launch-builder`, `/superegm:clean`) |
| `foreman/<unit>.json`, `review/<unit>/pr<n>/` | the foreman dispatch whose `dispatch_id` the round records (`prepare --dispatch`, `collect`, `review post`); between dispatches `foreman dispatch`, `interrupt --round`, `/superegm:clean`, `review settle` (a head's `outcome`, §11), `review ingest` (`ingested[]`, and a `clean` outcome rewritten `revise`, §8) and `decision open\|rule` (`decisions[]`, `rulings[]`); `r<n>/dod/<item>.txt` by `collect` (§11) |
| `wave_<n>_report.md` | `wave` (`superegm report`, after every batch) |
| `foreman/<unit>-<decision id>.brainstorm.md` | `decision rule` on a `redesign` ruling (§11) |
| `driver/<handoff>.json` | `driver tick` (`launches[]`; `notified` through a tick's `notify`), `driver reset`, and `runcard open` for `interrupted (reboot)` alone (§11.2) |
| `~/.superegm/registry.json` (the registry, outside every store) | `register [--remove]` alone; `inbox --all` and `driver tick` read it (§11.2) |
| `orient/map.md`, `orient/export/`, `orient/graphify-out/`, `orient/<unit>.md` (all under the handoff directory, §9.3) | `orient` (`superegm orient`, typed, and run by `plan`, `review-plan` and `launch-builder`; §9.3); `orient/export/` and `graphify-out/` are written by `git archive` and graphify through `orient`, one invocation at a time, the two writes not made through `atomic_write` |
| `journal.md` | append-only, `O_APPEND`, one line per fact, written by the subcommand that wrote the fact |

The unit-keyed kinds `unit`, `foreman`, `launches`, `worktrees`, `review` and `orient_unit` live
directly under the handoff directory, and under `<6 hex>/` (the handoff label's
hex, which the tables above leave implied) in a legacy flat store, where that layer kept two
handoffs apart; `Store.path(kind, …)` maps a kind and its parts to the path, `Store.kind_of(path)` back. All
writes go through a temp file and `os.replace`, graphify's own output and `orient`'s export
excepted (§9.3). No lock file.

- `.superegm/config.json` — committed in the target repo; created by `superegm init` (run by the
  first typed skill when it is missing; it prints the owner's by-hand steps: the builder account
  and profile, the branch protection of §11) and committed by `approve-spec` with the spec (§8).
  Keys, all with defaults `init` writes: `repo`, `base` (the default branch; `init` refuses
  another), `artifacts_dir` (absolute, outside the working tree), `mode` (`normal |
  leavemealone`), `max_in_flight` (5), `labels` (EGM's set with prefix `superegm:` plus
  `stopped`), `issue_template`, `tracking_issue_title`, `banned_terms`, `fix_request_mention`,
  `allowed_mentions`, `reviewers` (`spec`, `plan`, `head`, `integrate`: ordered reviewer lists;
  `head` is `change-review, astra` by default, the `astra` entry informational, §8; from
  amendment 8 `model` and `effort`, every review goldfish dispatch of the four kinds (the judges
  have their members' values), `opus` / `xhigh` in the Agent tool's own alias and level forms
  (`sonnet`, `opus`, `haiku`, `fable`; `low` to `max`), passed as the adapter's per-dispatch
  override, §8), `astra`
  (`enabled`, `model`, `effort`, `heads`: true, the lane on head reviews; a config without the
  key reads it as true, §8, §11; from amendment 8 `heads_effort`, the foreman's lane, `high`,
  `effort` staying the elephant's lanes'), `judges` (`min_vendors` 1; `members`, from amendment
  8: `fable` through the adapter at `xhigh`, `astra` through the runner at `xhigh`, recorded
  `not run` when the runner is absent, `opus` through the adapter at `max`; an adapter member's
  `model`, when set, is the tool's alias too, a runner member's `astra.model`), `builder`
  (`profile_dir`, `model` = `claude-opus-5-5` and `effort` = `medium` from amendment 8 (a full
  model id, since `claude -p --model` takes one; the elephant is the session's model, never in
  config); a config written before U28 reads the keys amendment 8 adds (`builder.effort`,
  `reviewers.model`, `reviewers.effort`, `astra.heads_effort`) as `init`'s defaults, the loader
  filling a missing nested key from `DEFAULT_CONFIG` as it reads `astra.heads` (U28 extends the
  landed `astra` merge to `builder` and `reviewers`, which the loader replaces wholesale today); a member's
  `effort` and `builder.model` are landed, their written values stand and only `init`'s
  defaults change,
  `permission_mode` = `acceptEdits`, `gh_token_env` =
  `SUPEREGM_BUILDER_TOKEN`, `app` = `null` (or `app_id`, `slug`, `private_key_env`, §11),
  `allowed_tools`: the read/edit tools, `git add|commit|status|diff|log|
  mv|rm`, `gh pr create|edit|comment|view`, `gh issue comment` and the test runner (`pytest`, the Step
  default's first word, §9.1; the default `init` writes; the owner edits it), `gh pr view` and the runner from
  amendment 11 (the owner's item; the per-launch grant below covers every Step's own command, so the default adds a grant only to a body whose Steps all carry explicit `Run` lines), each as a prefix pattern; the push
  prefix for the unit's own branch is added per launch; from amendment 7 also `Skill(<name>)`,
  `Skill(<name> *)`, `mcp__<server>__<tool>` and `mcp__<server>__*` rules, §4; `plugins`, the
  plugin ids `<name>@<marketplace>` passed to the builder, each resolved to the directory and
  version of its `user`-scope entry in the elephant profile's `plugins/installed_plugins.json`
  (the elephant profile: the one `CLAUDE_CONFIG_DIR` names in the session running the helper,
  the env file's under the driver, §11.2, else `~/.claude`; the entry is read, its enablement
  never: the owner keeps the listed plugins installed and disabled there, so no goldfish or
  foreman that profile dispatches gets their hooks), `init` writes
  `[]`; `mcp`, the builder's MCP servers in `.mcp.json`'s `mcpServers` form (a secret by `${VAR}`
  reference, never literal: the config is committed), `init` writes `{}`; `builder.stall_minutes` (30,
  amendment 10: the watchdog's bound, §11), `ci_wait_minutes` (30), `commit_trailer` (the empty string, §8), `owners` (the
  GitHub logins that may update `<base>`; `init` writes the login `gh api user` returns; a config
  without the key loads as `[]`, and `launch` and `doctor` refuse naming the key), `owner_team`
  (optional, `<org>/<slug>`: the team a ruleset's bypass actors may name) and `pr_block_file`
  (optional: a path in the repository, relative to its root like `issue_template`, whose text
  every builder PR body carries) (§11); and, from amendment 5, `ingest` (`severity_words`, a
  word → severity map; `init` writes Devin's known words `bug → high`, `issue → medium`, `nit →
  low`, `suggestion → low`; `human_role`, default `write`), `notify_timeout_seconds` (30; the
  hook itself is `~/.superegm/notify`, outside the repository, §11.2) and `foreman`
  (`run_timeout_minutes`, 8) (§8, §11, §11.2); the driver's interval and environment are the
  machine's, never a repository's keys (`install --interval`, `~/.superegm/env`, §11.2). Unknown
  keys stop.
- Under `artifacts_dir/<handoff id>/` (the store-level files above at `artifacts_dir` itself), never committed:
  - `state.json` — EGM's handoff state with EGM's keys, minus `approval`, `pending_approval`,
    `gate_unreviewed_diff` and `decisions[…].published`, plus `plan` (the path of the elephant's
    plan file outside the store, from `--plan` on the first `graph`; EGM's `plan` named the store
    copy), `base_at_start`, per unit `body_sha256`, `filings[]` (the confirmed write list of every
    filing that ran `apply`, appended by `apply` before its first write, once per write-list
    hash; EGM's `confirmed` is the pending one), `closed_at` (written by `close`), `notified`
    (the fingerprints of every inbox line current at `notify`'s last call, sent then or before,
    written by `notify` alone, §11.2), and from amendment 10 `board_changed_at` (written by `status`
    at the splice's write, the board's header time, U30). A unit
    with a filed issue number is **frozen**: `graph` reads its section from the store
    (`handoff_plan.md`), never from the plan file, and refuses when the file's section differs;
    `graph` and `dry-run` re-render and re-hash unfiled units only; `apply` and `verify` act on
    the current filing's confirmed write list, `verify` reading back every issue that list names
    and comparing the stored body, never a re-render, and expecting in its obsolete-link pass the
    union of every list in `filings[]`; the tracking issue belongs to the latest filing's list
    only (a later filing rewrites its body, an issue edit EGM's `apply` never made; from
    amendment 10 the body also carries the board, U30, §11: `status` rewrites it between
    `<!-- superegm:board -->` and `<!-- /superegm:board -->` on every pass under a `wave` card
    (`integrate`'s pass stays a read; a tick's session renders it at its first pass; a later
    filing's rewrite drops the block and the next pass appends it again, the accepted transient), through one
    splice function (replace the text between the markers, append the block once to a body
    without them, write only on change: in a module of the plan's choosing that no other 1.2 unit
edits, `apply.py` beside `edit_issue` the natural one, called by `status`
    and by `verify`, which compares the body outside the markers) and `apply.edit_issue` (an owner's hand edit landing between that read and the write of a row change is overwritten, the accepted window as the filing transient is), one read of the body per pass at the splice, compared and written in
    the same step, one GitHub write per pass and none when the fresh rows match the block read,
    whose header time is then kept), earlier lists
    being compared on their unit issues. One check, `require_frozen_units(handoff)` in U03 (py),
    replaces EGM's whole-plan checks in `status`, `launch` and `prepare`: for every filed unit,
    the plan file's section equals the stored one and the body its filing's list in `filings[]`
    stores equals the one `unit_<id>.md` carries (EGM's unit file holds the body in a fence);
    any difference refuses.
  - `runcards/<id>.json` — `skill, artifact, artifact_sha256, reviewers, tiering, mode, parent,
    opened_at, closed_at | interrupted_at, produced[]` and, from amendment 5, `boot_id` on every `wave` card and, on one opened under
    `SUPEREGM_ROLE=driver`, `driver_card` (both written by `runcard open`, the latter from
    `SUPEREGM_RUNCARD`; a record, not a parent: the driver card is closed by then, §11.2).
  - `approvals/<spec-slug>.json` (at the store level, above) — the spec's approval history:
    `path` and `entries[]`, one per approval in order, each `sha256, commit, runcard, review,
    approved_at, handoff_id, kind (opening | amend-units | after-void), voided_by, escalated[]`
    (the `<review id>:<finding id>` pairs §8's approval records); entries are appended, never
    rewritten (`voided_by` excepted); the last entry is the latest approval; a handoff's approved
    sha256 is its latest entry's; the chain is the order: a later link is any later entry, and
    §8's scope rule diffs against the last entry's `commit` (the 1.1 record's single approval
    reads as a one-entry history). `<spec-slug>` is the spec file's stem. `handoff_id` is
    `<EGM's 20-character slug of the stem>-<first 6 hex of the opening approval's sha256>`, set by
    the opening approval and kept by `--amend-units` and by a re-approval after a void of this
    handoff's approval while any unit is filed (each a later entry with the same `handoff_id`, the
    one rule, which §5 and §8 cite); any other approval of the spec (an amendment, a new review
    cycle) opens a new handoff with its own id beside the earlier ones, open or closed (U20). The
    handoff label is `superegm:handoff-<6 hex>`; markers and branches carry the full id.
  - `handoff_plan.md`, `handoff_units.json`, `unit_<id>.md`, `handoff_bodies.md` — EGM's files
    with the new sections; `handoff_units.json` carries `body_sha256` per unit.
  - `reviews/<review-id>/review.json` (`kind, artifact, cycle, reviewers, runcard, converged,
    converged_round, rulings[], scope` and, from amendment 6, `ingested[]` (the root comment ids
    `review ingest --pr` recorded in this cycle; the reader skips every cycle's of the spec, §8) (kind `spec`: `auto`, `whole` or the headings named, §8); a
    spec review's directory at the store level, above) and `round-<n>.json` (`runcard`, the
    top-level card the round's first `review record` carried; `artifact_sha256`; `scope`, the
    round's headings with their line ranges, stored by the round's first record (amendment 11's
    wording), and `out_of_scope[]`, the finding lines
    `review record` refused, verbatim (§8); findings per reviewer with id, severity,
    location, `regression: yes|no`, disposition, ruling; `builder_contested[]` of `{fid, reason}`
    on a head; each dispatch's isolation, model and effort requested → effective; `what_ran`,
    derived as §8 says and stored with the round). Review ids carry a cycle:
    `spec-<spec-slug>-c<n>`, `spec-<spec-slug>-integrate-c<n>`, `plan-<unit>-c<n>`,
    `head-<unit>-c<n>`; `review open` on an artifact whose latest cycle is closed (`accept`,
    `stop`, or a spec edit after the approval that names this cycle (`approvals/<slug>.json`'s
    `review` equals the cycle's id and the bytes differ from its `sha256`), §5, and for an
    integrate cycle also the `--amend-units` re-record that ends its pass; never a clean
    round whose bytes moved,
    which is the same cycle's `fixed:` state, §8) starts the next cycle, and "the review" of an
    artifact means its latest cycle; `latest_cycle` asks `evaluate` and reads `approvals/<slug>.json` for that, not a
    stored field (U16).
  - `launches/<unit>.json` — `launches[]` with `round` (the launch count), `worktree`, `branch`,
    `started_at`, `boot_id` (amendment 5, written by `launch-builder` at the launch), `pid` (amendment 10: the wrapper's, the process-group leader `launch-builder` spawned, the watchdog's kill target, §11; from amendment 10 `launch-builder` writes the whole `running` entry once at the launch, every field of this list but the exit's, the command line it ran among them, and `record-launch` keeps `--exit` alone), `status` ∈ `running | exited <code> | exited (stalled) | interrupted | interrupted (reboot)` (the
    last amendment 5's, `exited (stalled)` amendment 10's; `last_commit_at`, the launch's own newest commit time (one newer than `started_at`) or none, written by every `--exit` from amendment 10, the carve-out's one field; both terminal for `launch-builder` and `clean` as `interrupted` is), `kill_failed` (amendment 10: its reason, `no exit file` when none followed the signal within 30 s, or `pid reused` when the guard, run before any signal, found the group's present leader another's, or `no process` when it found no member living, no signal sent; the launch stays `running` and is signalled no more, the unit idle and in the inbox for the owner's interrupt; a later exit file clears it, §11), `result_file`,
    `prompt_sha256`, `command` (amendment 10: the launched command line, the record of what ran), and from amendment 8 `model` and `effort` (requested, written with
    the entry; the effective model and, from amendment 10, `total_cost_usd` (the board's cost) read by `record-launch
    --exit` from the result file's `modelUsage` and `total_cost_usd` keys, the field U28's one run confirms, every
    key when there are several, else `requested only`).
  - `foreman/<unit>.json` — `dispatch_id`, `rounds[]` (`round` (the review's round number),
    `runcard` (the wave card the dispatch ran under), `launch` (the launch count at dispatch),
    `head` (the tip `prepare` fetched), `phase ∈ fetched | prepared | collected | posted | kept |
    cleaned`, `dispatch_id`, `outcome` (the return word for a posted round, written by `review
    post`; else `not run (<reason>)`), `posted_at`, and from amendment 5 `dod_runs` (`{<item>:
    {exit, summary, paste_summary, timed_out}}`) and `test_delta` (`[{file, line, base_line, kind: removed |
    weakened, base_commit}]`), §11), `ingested[]` (the root comment ids of the PR review threads
    `review ingest` recorded, ids only: the findings are the record, §8), `decisions[]` (`id, point, question,
    asked_at`), `rulings[]` (`decision, ruling, by, posted_at`); a decision is pending from its
    `decisions[]` entry until its `rulings[]` entry. On kind `head` the review's rounds are
    these entries; a `round-<n>.json` exists only for a round whose panel was dispatched.
  - `worktrees/<unit>/` and `review/<unit>/pr<n>/`; `foreman/<unit>-<decision id>.brainstorm.md`
    (§11); `judges/<id>/question.md`,
    `round-<n>/<judge>.md`, `verdict.json`; `wave_<n>_report.md`; `journal.md`; under
    `review/<unit>/pr<n>/r<n>/dod/`, one `<item>.txt` per DoD `Run` item the foreman re-ran
    (`exit: <code>`, `summary: <line>`, `timed_out: yes|no`, §11); `driver/<handoff>.json` (the
    `driver` kind: `launches[]` with `started_at`, `boot_id`, `pid` (the wrapper's), `exit_file`,
    `result_file`, `status`, as `launches/` has them from amendment 5, and `notified`, §11.2).
- Outside every store, `~/.superegm/registry.json` is the registry (§2, §11.2): one entry per
  store, `{repo, root, artifacts_dir}` (no copy of the config's `base` or `mode`: nothing would
  read it, anti-goal 1), written by `register` alone; the rule that
  every file has one writer holds there too. Unknown keys stop.

## 8. Spec review (phase 1) and the one review loop

`/superegm:review-spec <spec-path> [--reviewers design,zoom-out,…] [--astra on|off] [--leavemealone]`

The review loop below is implemented once, in U04, as helper subcommands plus
`skills/review-spec/references/review_loop.md`, and is consumed unchanged by `review-plan` and
by the foreman. The helper records and judges; the dispatching session dispatches.

- `superegm review open --kind spec|plan|head|integrate --artifact <path or unit id>
  [--sha256 <hex>] [--scope auto|whole|<section list>] --reviewers a,b,c --runcard <id>` records
  the review id (with its cycle), the scope (kind `spec`; the specifics below), the
  panel (1–6 reviewer ids from `design`, `zoom-out`, `comprehension`, `readiness`, `structural`,
  `style`, `codebase-details`, `change-review`, `set`; the kind's fixed first reviewer must be
  first) and the Astra lane state (the one control of the lane's seat: `astra` is appended for kinds
  `spec`, `plan` and `integrate` when `astra.enabled` is true and the preflight passes, else the
  review opens `--astra off`; for kind `head` when `astra.enabled` and `astra.heads` are both
  true, installed or not, an absent runner being recorded `not run (not installed)` on every
  head (§11); a config without `astra.heads` reads it as `init`'s default, true, and an `astra`
  entry in a `reviewers` list is informational, read by nothing: amendment 4 reverses the 1.0
  ruling `q-wave` Q1, which kept the lane off heads). The panel cannot change after this. Later rounds review the artifact's
  **current** bytes; each round records the sha256 it reviewed (the helper hashes a spec; the
  caller passes `--sha256` for a plan body or a head).
- Each round the dispatching session dispatches the whole panel **concurrently** through the
  adapters, each goldfish receiving only the artifact, the standards the kind names, and from
  round 2 the prior round's report with the fixes marked; the Astra lane runs alongside through
  the runner's `review` mode, launched by the elephant (by the foreman on a head, §11), fresh in
  round 1 and resumed after (on a head, fresh every round, §11). The dispatching session records each reviewer,
  the lane included, with `superegm review record --review <id> --round <n> [--sha256 <hex>]
  --reviewer <id> --findings <file> --isolation clean|exposed:<what> --model
  <requested>:<effective> --effort <requested>:<effective> --runcard <id>`, or `--not-run
  "<reason>"` when the dispatch did not complete. A reviewer with no findings is recorded with an
  empty file; a dispatch that did not complete is re-dispatched once within the round and then
  recorded `--not-run`; the Astra lane is never retried within a round and is stopped for the
  review after two incomplete runs (`not installed` is not one: on a head the lane stays seated
  and records `not run (not installed)` each round; a stopped lane records `not run (stopped:
  two incomplete runs)` each later round (on a head, `prepare --dispatch` prints `astra: stopped`
  from the helper's count and the foreman skips the launch), so `what_ran` completes on a panel
  that cannot change). `--reviewer set` takes the `set` reviewer's whole file and
  keeps the findings whose `<location>` names the review's unit or no unit. On kind `head`,
  `--reviewer foreman` is accepted outside the panel for the helper's own findings (§11) and
  never counts toward every-reviewer-ran; so is `--reviewer external:<login>` (amendment 5), the
  id `review ingest` records a PR review thread under, on kinds `head` and `spec` (§8's two
  ingest bullets; its location is the thread's own, outside the scope rule below). Every persona's output section is re-worded to the
  findings line below and its severity words (U01; each a changed Apache file). A round's
  `what_ran` is **derived** by the helper from the round's reviewer records and, on a head,
  from its `rounds[]` entry's `phase` and `outcome`; no caller sets it, and it is stored with
  the round: `completed` when every panel reviewer has a findings record for the round (an
  empty file counts; for the Astra lane a `--not-run` record counts too) and, on a head, the
  entry's `phase` is `posted`; otherwise `not run (<reason>)`, the reason being the first
  reviewer without a record or the entry's own `not run` reason (a head round with no reviewer
  record at all is `not run` with that reason). Only a `completed` round counts toward the cap
  or can converge; the findings of any other round settle nothing and block nothing. A round
  **converges** only when it records no unsettled high or medium finding **and** its
  `artifact_sha256` equals the artifact's current bytes, one predicate: a round whose fixes
  moved the bytes is not convergence, and the next round is recorded on the fixed bytes. On
  kinds `spec`, `plan` and `integrate` `review settle --disposition fixed` is refused while the
  artifact's bytes still equal the round's `artifact_sha256` (`review settle: fixed needs
  changed bytes`): an unchanged artifact's honest dispositions are `escalated`, `declined` or
  `contested`, so no round converges on a fix no goldfish saw (anti-goal 6). The current bytes are, for kinds `spec` and
  `integrate`, the spec file's, hashed by `review status` itself; for kind `plan`, the unit's
  stored body (`unit_<id>.md`'s fence, hashed by `review status` itself, so both sides of the
  predicate are helper-read; `handoff_units.json`'s `body_sha256` is that hash) (a `set` finding that `review record --reviewer set` copied to several units is one finding:
  the one `review settle --disposition fixed` on the unit whose bytes moved writes `fixed` on
  every sibling copy, matched by id and claim among the copies recorded under the same
  `--runcard` round (the set file is recorded once per round under one card); a sibling's round
  then converges at its unchanged bytes, which is right, since the fix was not on its body, and
  the next round's `set` read over the whole set reopens it if the fix broke it, U16); kind `head` has no byte test (its `fixed` dispositions
  are the builder's replies, which `collect` carries, and the next round is on the next head). A review
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
  [--owner | --judges <judges-id>]`; `review settle --review <id> --file <dispositions> --runcard
  <id> [--owner | --judges <judges-id>]` settles every finding of a round in one call, one line per
  finding `<fid> | <disposition> | <note>`, under the same refusals and all or nothing (a refused
  line writes nothing and is named), the per-finding form staying (U19). For a high or medium `contested` or `declined` the helper
  refuses without `--owner` in normal mode and without `--judges` in leavemealone-mode. The
  `foreman` finding that records CI not green is settled by no one: `collect` records it afresh
  each round from the CI file and omits it when CI is green, `review settle` refuses it, a
  builder's reply to it is ignored, and `judges question` never renders it. `escalated` means
  moved to a new unit or a decision point, and is settled. `fix-design` means the defect is in
  the spec and is refused on kind `head` and on a frozen handoff's integrate (§7; the finding is
  settled `escalated` to the latest handoff instead). A ruling that overrules a finding settles it
  `contested`; one that upholds it leaves it unsettled, and on a head `collect` carries an upheld
  finding forward as a `foreman` high until a later builder reply marks it `fixed`. A
  `test-delta` finding (§11, amendment 5) is the owner's alone: `review settle` on it takes
  `--owner` only, never `--judges`; `collect` ignores a `fixed` reply to it unless the head's
  assertion is back; the one ruling that clears it is the owner's `**Ruling:** <fid> allowed —
  <reason>` (§13.2; the point-1 form `finding overruled — <reason>` on its fid is read as the same;
  recorded as `declined --owner`, the five dispositions being the only ones);
  in leavemealone-mode it stays until a head restores the assertion or the
  owner rules (the inbox lists it from the round that records it, §11.2): a round whose only
  unsettled high or medium findings are the owner's alone puts the unit `pending a decision`
  (`review post` writes the outcome `owner: <ids>`, the foreman returns that word, and the wave
  runs `decision open` with the `allowed` form as its option, no slot, §11.1) instead of a
  relaunch,
  and the owner's ruling releases it (a pending decision holds the unit from dispatch, §11.1, so
  no head is reviewed meanwhile): `**Ruling:** <fid> allowed — <reason>` settles it and the unit
  proceeds by `review status` as point 1 does; `**Ruling:** <fid> finding upheld` relaunches the
  builder with the review to restore the assertion (the `revise` path), and the next round
  re-derives the delta; at the review's cap (`review status` exit 2) the word stays `owner: <ids>` while every unsettled
  finding is the owner's alone (the judges never see it; `allowed` clears it and the unit proceeds
  by `review status`), and is `cap-reached` otherwise (§11); an upheld owner-only finding at the
  cap goes to point 2 as a `cap-reached` (one more round or stop); the cap is never spent on a
  finding the judges cannot settle. The owner
  may write a point-1 ruling as a comment on the unit's issue in §13.2's form (`**Ruling:** <fid>
  finding upheld` | `**Ruling:** <fid> finding overruled — <reason>`): the wave reads it as a
  `ruling` event (§11) and applies it through `review settle --owner` and `decision rule --by
  <login>`, so the record is the same whichever way it was ruled. On a head,
  whichever of `review post` and `review settle` leaves `review status` at exit 0 writes `clean`
  into the latest posted round's `outcome` and journals `<unit> awaiting merge`.
- **External review** (amendment 5, U21). A review thread a person or a bot leaves on a unit's PR
  is evidence the foreman would otherwise never read. `superegm review ingest --unit U<n>
  --runcard <id>` reads the PR's reviews and review comments (`gh api`, under the elephant's
  token, reads only); a thread is a review comment with no `in_reply_to` (its replies are its
  text), or a review body when it is non-empty, the review has no inline comments and its state
  is not `APPROVED` (an approval's summary is not a finding), except a review whose body carries
  `review post`'s own header: that is the foreman's, never a thread, whatever login posted it (the
  elephant's token is the owner's, who also reviews by hand under it); it records every thread not yet ingested as one finding line,
  `<reviewer>-<round>-<n> | <severity> | <file:line or PR> | regression: no | <the thread's first line, 200 chars, a `|` in it written `/`, a `@` written `@ ` and a `config.banned_terms` entry masked the same way, so the raw-text scan passes>`,
  through `review record --reviewer external:<login>` into the unit's latest posted round,
  `--sha256` that round's head (the thread's own `commit_id` goes in the finding's location); it prints `<n> ingested`, exit 0, and posts the ingested lines
  as one review comment in `review post`'s form (the record the next builder's prompt carries,
  §11: the builder sees posted review comments and nothing else), a thread from a human below
  `config.ingest.human_role` recorded and never posted (a passer-by's text is not re-published
  under the owner's login nor placed in a builder's prompt); `collect` carries an external
  high or medium with no `**Reply <fid>:**` forward as it carries an upheld one, so a round that
  never saw it cannot post `clean`. One thread is one finding:
  its key is the root comment's id, kept in `foreman/<unit>.json.ingested[]` (§7, ids only); an
  edited thread is re-read for its text, and a recorded finding's severity never changes. The
  severity: a human below `config.ingest.human_role` (the repository permission
  `collaborators/<login>/permission`, read once per wave; default `write`) is `low` whatever the
  words, so a public repository's passer-by never blocks `clean`; a review body from a bot (a login ending `[bot]`) is `low`, never the word map's, since a
  bot's no-findings summary carries the map's words; a review body from a human at the role or
  above is `medium` only when its first line carries a severity word or a mapped word, else
  `low` (an owner's `LGTM, merging tomorrow` is not a finding); an
  inline thread from a bot or from a human at the role is the thread's own word when its first
  line starts with, or carries in a bold or bracketed marker, `high`, `medium` or `low` or a word
  `config.ingest.severity_words` maps to one (so `not an issue` maps to nothing)
  (`init` writes Devin's: `bug → high`, `issue → medium`, `nit → low`, `suggestion → low`), else
  `low` for both (an owner's inline question or praise is not a finding; a word raises it). A thread on a head later than the latest posted round's waits:
  the batch's `review ingest` records it once the round that reviews that head is posted
  (`collect` reads no thread: its call has one budget, §11). A thread whose author is in
  `config.owners` and whose body is in a ruling form (§13.2) is skipped, never a finding, and
  rules nothing there: a ruling is read on the unit's issue alone, where the inbox's action
  points. An ingest is
  never a counted round and never moves the cap; an unsettled external high or medium blocks
  `clean` exactly as a `foreman` finding does, and settles through the existing paths and no
  other (the builder's `**Reply <fid>:** fixed | contested`, `review settle`, a point-1 ruling: a
  contested external high or medium is a point-1 question like any other); a thread's GitHub
  "resolved" state settles nothing. When an ingest leaves `review status` at exit 3 on a unit
  whose latest posted round's `outcome` is `clean`, `review ingest` rewrites that `outcome` to
  `revise` (the mirror of the `clean` write above; the unit is ready again, not in flight, and its
  relaunch waits for a slot as a ready unit does, §11), and at exit 2 (a review at its cap, the usual
  end of a contested unit) to `cap-reached`, which the wave routes to decision point 2 as a posted
  `cap-reached`; either journals `<unit> ready again (external:<login>)`; §11 says what the
  wave does with it.
- **External review on the elephant's own PR** (amendment 6, U26). The elephant's own PR is the
  spec PR: `review-spec`'s preflight refuses on `<base>` (start on a branch, §5), commits the spec
  by path (an empty commit when nothing changed, so a commit ahead of `<base>` exists), pushes the
  branch, and opens the PR ready for review (a bot may skip drafts) on the elephant's branch when
  `gh pr list --head` finds none (a `github-write`, §14, so
  the ingest never reads nothing by forgetfulness),
  `review-spec` pushes the branch after each fix commit and after the approval commit (a
  `remote-branch` effect, §14; never `<base>`, §5) so a reviewer such as Devin reads every round's
  bytes and the PR's head is the approved commit, and the owner's one human step (§5's push of the
  approval to `<base>`) is what GitHub records as that PR's merge.
  No other PR of the review workflow's exists: the plan is never committed and `file` opens none
  (the PR `finishing-a-development-branch` opens is the owner's to read by hand).
  `superegm review ingest --pr <n> --runcard <id>` (kind `spec`) reads that PR's review threads
  with U21's reader, severity map and bot/human rules, and records them as `external:<login>`
  findings into the latest round of the spec's latest cycle, the one `latest_cycle` returns,
  closed by an `accept` or not (one predicate, §7); the thread's root comment id is kept in that
  cycle's `review.json.ingested[]`, and the reader skips every id in any cycle's list of the spec
  (the PR outlives a cycle), and carries every unsettled external high or medium of an earlier
  cycle of the spec forward into the latest round, as `collect` carries one on a head (§11), so the
  next round marks it and no closed cycle's finding is settled unseen; the carried copy and the
  original are one finding, a disposition written on both (as a `set` copy's is), and the check
  below reads the latest round alone. An unsettled external high or medium there refuses
  `approve-spec` (`approve-spec: external:<login> <fid> unsettled on PR
  <n>`, exit 1; one check beside the landed refusal of an unconverged review, since `converged:
  by ruling` reads nothing settled and a `stop` opens the next cycle over the same PR).
  The elephant settles them through the existing paths: `fixed` by an edit alone (the next round
  reviews the new bytes and the push shows the reviewer the fix: the cost of a fix, a round, or a
  cycle with a fresh cap when the edit follows an `accept`, paid for a thread a round already
  answered too, since the elephant settles nothing on its own spec unseen, anti-goal 6; the owner
  weighs `declined` with that cost in view), `contested` as decision point 1 of the review like any finding (the judges in
  leavemealone-mode, the owner in the session otherwise), `declined` or `escalated` as §8 defines
  them; `review ingest --pr` posts `**Reply <fid>:** fixed` on each thread settled `fixed` since
  its last run, under the elephant's token (its own PR; a `github-write` of `review-spec`, §14).
  `approve-spec` runs the ingest once, before its refusals, on the open PR whose head is the
  current branch (`gh pr list --head`; none means nothing to read; never under `--amend-units`,
  which takes no review round); a thread that arrives after the approval is the next cycle's
  `approve-spec`'s while the PR is unmerged, else the owner's to read; a thread's GitHub
  "resolved" state settles nothing.
- `superegm review status --review <id> --runcard <id>` prints `round <n>: <clean|not clean>,
  regressions <k>, converged <yes|no|by ruling>, cap <yes|no>, stalled <yes|no>, sha256 <hex of
  the converged round>` and the trend line; exits 0 when converged, 5 when stalled, 2 at the cap
  without an `accept` ruling (and for ever after `stop`, until a new cycle), 4 when any finding
  is `fix-design`, 3 otherwise or when the review is not yet opened. When the latest completed
  round is clean but its `artifact_sha256` differs from the current bytes, it prints `fixed:
  re-review on the current bytes` and exits 3 (the continue state), never `converged`; at the
  cap in that state it exits 2 as every cap does, and the rulings are `continue` (one round on
  the current bytes) or `stop` (the next cycle): `review rule` refuses `accept` while the latest
  completed round's bytes moved (`review rule: the reviewed bytes moved: continue or stop`), and
  `judges question --cap` offers only those two then; whenever `accept` and `continue` are both refused
  (`continue` spent and the latest completed round's bytes moved, clean or not), `stop` is the
  one option left: `judges question --cap` says so (`question: one option: stop`) and `review
  rule --ruling stop` is accepted with no ruler then (journaled `stop: the one option`), so
  the invocation ends with the record (a journaled ending, not a pause, anti-goal 7; §1.2 lists a
  review ended at its cap among what the owner wakes to) and the next typed invocation opens
  cycle n+1 on the fixed bytes with a fresh cap, which bounds the night; the elephant's other exit
  is to restore the clean round's bytes (the predicate hashes the file), after which `review
  status` exits 0 and `approve-spec` follows, and the ruler-free `stop` is written only by
  `review rule`, never by `review status`. The cap and stall
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
- Model tiering (amendment 8), one rule: panel goldfish run on `config.reviewers.model` at
  `config.reviewers.effort` (`opus` / `xhigh`, the Agent tool's alias and level), passed on
  each dispatch as the adapter's `model` and `effort` override (§4: the adapters stay `model:
  inherit`), and the round record stores requested → effective (`review record`'s `--model` and
  `--effort`); `SUPEREGM_GOLDFISH_MODEL` and `SUPEREGM_GOLDFISH_EFFORT`, when set, override the
  config's values for the session, `inherit` meaning pass nothing, and an exported
  `CLAUDE_CODE_EFFORT_LEVEL` is the effective effort of every goldfish, and with
  `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` on no per-call `model` is passed and the forced model is
  the effective one, which the record says in both cases (the landed `printenv` read) (`review_loop.md` carries this rule and the foreman brief's
  `<GOLDFISH_MODEL>, <GOLDFISH_EFFORT>` placeholders are filled from it); judges use their member's model and effort (§13); builders use `config.builder` (§11); the
  foreman's Astra lane runs at `astra.heads_effort` (§11). The elephant is the session's model,
  never in config. The run card shows requested → effective.

Spec review specifics:
- `review-spec` opens a run card and the review `spec-<spec-slug>-c<n>` with
  `config.reviewers.spec` unless `--reviewers` is given; `design` is first.
- **An amendment is reviewed in scope** (U19). `review open --kind spec` takes `--scope
  auto|whole|<section list>`, default `auto`, and the review record stores that form (`auto`,
  `whole`, or the headings named verbatim). Under `auto` the helper derives the scope afresh at
  every round from the current bytes: when the store holds a previous approval of this spec, the
  changed sections are those whose lines differ between the bytes that approval names (its
  `commit`, or when that is unreachable any commit on the branch's history whose spec hashes to
  the entry's `sha256`, §11's content read; `whole`, said in one line, only when no commit holds
  those bytes) and the current bytes (the helper diffs the two texts and maps each changed line to
  its heading: an H2 or H3, or the preamble above the first H2, a section of its own), so a
  section a between-round fix touched joins the next round's scope and no edited bytes reach
  `approve-spec` unreviewed; each changed section has as neighbours, for fit, the one section
  before and after it (a changed H3: the sibling H3 before and after it, else its parent H2 and
  the next H2); with no previous approval the scope is the whole spec; `whole` forces a full
  review; a section list adds the headings it names, verbatim and without neighbours, to
  `auto`'s scope (so a fix outside the list joins as under `auto`), and is refused with no
  previous approval to diff against (`--scope <list>: no approval: use whole`). The round file stores
  the round's scope as headings with their line ranges, stored by the round's first record;
  from amendment 11 a scoped finding whose location carries no line number joins
  `out_of_scope[]` by the same path (section `none`, the journal line `<fid>: no line number`; a line the spec
  does not hold or a path not the spec's takes the same path; the record proceeds), so the rule cannot be bypassed by a bare path (a `whole` round has no scope to bypass: no refusal; U32). The brief the skill
  dispatches names them and says: "findings only inside the changed sections and, on a
  neighbour, only on its fit with them; a finding on any other section is out of scope".
  `review record` accepts a finding whose cited line falls in a changed section or a neighbour,
  refuses any other (`record: <fid> out of scope (<section>): not recorded`) and stores the
  refused lines verbatim in the round's `out_of_scope[]` (no disposition, never counted, one
  journal line each, so no fix round is spent on them and the record says what the goldfish
  wanted to say); regressions and the cap count recorded findings only, and `judges question
  --cap` names the scope. A plan review and a head review are scoped by their artifact already
  (one unit, one head); `integrate` stays whole by design (§12).
- On convergence, `superegm approve-spec --spec <path> --runcard <id> [--leavemealone]` (EGM's
  `approve` with its heading check replaced by the `Units` check, its at-HEAD check by the commit
  it makes, `--evidence` dropped, and its tracked and clean checks removed, since it adds and
  commits by path): the spec's working-tree bytes must hash to the converged round's sha256 (for
  `--amend-units`, to the amended bytes), and its last H2 must read `Units` after any numeric
  prefix. It refuses while the bytes differ. The `escalated` findings of the spec review the
  approval records (`spec-<slug>-c<n>`; `--amend-units` records none and keeps the field as it keeps `handoff_id`) are the owner's
  by definition and stay `escalated`: in normal mode the line `approve-spec: <n> escalated
  finding(s) await the owner: <ids>` is printed with the one question and the owner's Approve
  (`--yes`) is the sight; in leavemealone-mode the converged record is the approval; in both
  modes the `<review id>:<finding id>` pairs go into the record's `escalated[]` and the journal
  line, and no decision point
  is added to §13.2; `escalated[]` has one reader: `graph` refuses the plan unless every id in
  it appears in the spec's `## Units` section (a row that takes the finding and names the pair,
  review id and finding id, since ids restart every cycle) or in a `blocking: yes` `D<n>` line of the plan file that names the same pair and carries the
  finding's claim verbatim as its question (so `decide` asks the owner or the judges, on the
  reviewer's words and not the elephant's, before the body passes `scan`; both branches match
  on the pair), so an escalated finding is built or decided by a ruler, never
  frozen unseen (anti-goal 6). `approve-spec`
  then adds and commits the spec and
  `.superegm/config.json` by path, ignoring other changes in the tree, on the owner's current
  branch with the message `superegm: approve <spec-slug> at review <id>`, with
  `config.commit_trailer` (an optional string; `init` writes it empty; the owner sets this
  repository's to `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` once the release
  carrying U16 is installed, since an unknown key refuses every helper call before; the
  builders' commits carry the orders' subjects and no trailer, by intent) appended as the last
  paragraph by `approve_spec.commit_by_path`, the one place the helper commits, and
  writes the record
  (an entry appended to the spec's approval history, `commit`, `sha256`, `handoff_id`, `kind`:
  the chain is the history's order, §7), refusing unless the current branch's history holds the spec at the last entry's `sha256`
  (`git log -- <path>` over the branch, a content check as `launch`'s is: a rebase or an amend
  that keeps the bytes passes, a branch that never folded the last approval fails with
  `approve-spec: fold <base> first: approval <sha7> is not in this branch`), so every approval
  descends from the one before by content and the base's spec is the last entry's bytes after
  the push; the owner
  pushes it to the base branch (§5). `superegm
  approve-spec --void --review <id>` sets `voided_by` when a `fix-design` finding is recorded;
  `graph` refuses a voided approval; a re-approval after a void keeps the `handoff_id` whenever
  `state.json` lists a filed unit (§7's one rule). `approve-spec --amend-units` is §12's.

## 9. Plan (phase 2) and plan review (phase 3)

### 9.1 The plan is the issue body
`/superegm:plan <spec-path> [--handoff <id>]` opens a run card, then `superegm graph` refuses
unless the resolved handoff's approved sha256 (§7: `--handoff`, else the spec's latest approval)
matches the spec's current bytes: one handoff per opening approval, and a spec's handoffs, each
at its link of the approval chain, run beside one another in their own directories, open or
closed (U20). The
elephant composes the plan text in a plan file outside the store, named by `--plan` on the first
`graph` and by `state.json.plan` after (EGM's layout: title, `Design:` line, `## 1. Issue
template`, `## 2. Units`), keeping every unit's section and adding one `### U<nn>: <title>`
section per row of the spec's `## Units` not yet in it, except a row the section's `Landed:` line
names (a unit that landed in an earlier handoff) or a row another handoff of this spec has
filed, open or closed, stopped units included (their `state.json`, found through `handoffs/`,
§7: `graph` lists them in `handoff_units.json` as `filed_elsewhere[]` and refuses a section for
one, and `review-plan` names them in the `set` reviewer's brief beside the `Landed:` rows, so it
counts them covered), and runs `superegm graph --plan <file>`
(copies the text into the store as `handoff_plan.md`, parses, derives waves, prints the
`wave <n>:` lines and, from amendment 9, a `width:` line (the shared-file chains alone: each
chain, its length and its forcing edge, the `after` item into its third unit; the units per wave
stand in the `wave <n>:` lines), derived from
`handoff_units.json`'s `units[*].shared` as `set-input` derives the same line (§9.2), which
the plan skill reads before `scan` and reshapes the plan on, splitting or
re-scoping until every wave holds two or more units where the spec allows it (a split that needs
a row the spec lacks appends it to `## Units` and re-approves through `approve-spec
--amend-units`, §12, typed by the owner outside the skill, so such a split ends `plan` and
restarts it after the re-approval, before `graph --plan` accepts the section); renders and
hashes the **unfiled** bodies) then `superegm scan`. Filed units are frozen (§7): their sections in the
plan file must equal the stored ones. Nothing is committed under `docs/…/plans`. Two handoffs of
one spec whose units edit one file conflict at the owner's merge, resolved by hand at the fold
(§5): the shared-file rule orders units within one plan, and that conflict is the cost of
handoffs beside one another.

Each unit section carries EGM's fields and the superpowers additions:

| Field | Rule |
| --- | --- |
| Objective | one sentence |
| Scope paths | `` `path` (create\|modify\|delete) ``, comma-separated; a path may be a directory |
| Design range | `` `path:start-end (heading)` `` into the frozen spec |
| Blocked by | `none` or unit ids |
| Shared files | `none` or `` `path`: after U01, before U05 `` items |
| Risk | `low\|medium\|high: reason` |
| Size | `S\|M\|L` by scope-path count (`S` up to three paths, `M` up to eight; `L` the size the parser gives a Scope over eight paths, which the per-unit check reports as a split candidate, amendment 9) |
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

Plan rules from amendment 9 (the helper never splits a unit itself, and `max_in_flight` is
unchanged). A unit's Scope stays within one subsystem, one module family: a helper module with
the skill folder, references and tests that drive it (the docs are the sweep's). A unit whose
Scope would cross two is written as two units, with a `Blocked by` edge only where one consumes
the other's interface and the Shared files order for any file both edit, or split so that no
file is shared; the two exceptions are the release's closing sweep, `Blocked by` the unit
before it so that it closes the release, and the docs sweep's notes (below). A cross-cutting file leaves the chains:
`README.md` and `docs/claude.md` are edited by a release's closing units alone (a docs sweep and,
after it, the release's last unit for its own rows; 1.2: U29, then U32) and never by the others, which, where they would have edited them,
append a `docs: see U<n>` note to their Objective's one sentence instead (the DoD grammar is unchanged; the note is the docs sweep's `Blocked by` edge on that unit, the second interface-free edge, the closing sweep's the first); shared test helpers are split
per module (a unit adds its own test file, never a line in `test_helper.py` unless it owns it);
and the helper's registry lines (`DEFAULT_CONFIG` and `SUBCOMMANDS` in `__init__.py`, `init`'s
key text, `doctor`'s line) are cross-cutting too: module self-registration (each subcommand
module exposes its parser registration, its config defaults, its `init` step text and its
`doctor` check, discovered by import, so a unit adds a module without editing a registry)
removes them, the work of this release's closing sweep U32 (amendment 11; its row states the
mechanism, not this rule); the wave skill is no registry, its per-unit steps an ordinary
shared-file edge. Later releases' width comes from the subsystem
rule's splits, the registry edge gone. The plan is shaped for wave width: the
author reads the `width:` line `graph --plan` prints and splits or re-scopes until every wave
holds two or more units where the spec allows it, and the plan's header states the wave plan
and why any wave is a singleton. The checkers: the per-unit split check (Steps, bytes, paths,
subsystems) is the `proportion` reviewer's and the chain check the `set` reviewer's (§9.2); the
header's wave plan and the singleton reasons are the author's alone (`set` reads them to grade a named chain `low`, amendment 11, and checks them not). Wave width is set by file
overlap alone (1.1.3: U19 and U20 serialised behind each other on shared files, U20 at 15 Steps
and 37 KB forcing a chain of its own).

Rules `graph` and `scan` enforce (each a test; `graph` owns plan-shape rules, `scan` owns body
rules; there is no third checker):
- Body ≤ 49,152 bytes; a larger unit is refused with "split it".
- `scan` reports per unit, as a stdout table and as `plan/scan/<unit>.json` in the store: `bytes`,
  `fenced_share` (bytes inside fences / bytes), `steps`, `spec_range_bytes` (the Design range's
  bytes in the frozen spec) and `ratio` (bytes / spec_range_bytes). It warns (exit 0;
  `warnings[]` in the json) when bytes > 24,576, or steps > 10 (amendment 9's values; 32,768 and
  20 before), or fenced_share > 0.40. Warnings
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
- The raw-text mention and banned-term scan with `allowed_mentions` (EGM's `scan`), with one
  rule and no other Markdown awareness (anti-goal 9): `scan_text`, one function in
  `superegm/__init__.py` that `scan.py`'s body scan and `review post`'s comment scan both call
  (today two copies, anti-goal 1; U16 leaves one), skips a fenced code block and an inline code
  span, so a `@` inside either (`@pytest.mark.parametrize`) is never a mention.
  The grammar is CommonMark's smallest: a fence opens at a line whose first non-blank text is
  three or more backticks or tildes with, for backticks, no further backtick on that line (a
  one-line span opened and closed by three backticks is no opener; the indent is not bounded,
  since a Step's fence sits under its number and a body carries no indented code block) and
  closes at the next line of at least as many of the same character, so a nested shorter fence
  stays inside it, and an unclosed fence runs to the end; a span is the text between a backtick
  run and the next run of equal length on the same line, paired left to right and never
  overlapping (CommonMark's pairing: in `` `a` @user `b` `` the `@user` stands outside every span
  and is a mention), since the one safe direction of the exception is never to skip. Everything
  else stays raw text; the allow-list is unchanged.

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
  only, and, from amendment 9, the `width:` line `set-input` derives from `handoff_units.json`
  (`units[*].shared`, each path with its `after` and `before` units, §9.1) with the plan
  header's wave plan and singleton reasons (amendment 11), on which it reports the shared-file
  chains longer than two units with their forcing edges (`medium`), the chains ending at one
  unit folded into one finding whose location names that unit and whose claim carries them,
  and a chain the header names with its reason as `low`: a kept chain is one decision, settled
  once (the copy rule below keeps it for that unit alone). Its one findings file is given to every unit's `review record --reviewer set`, which
  keeps the findings for that unit (§8). Any reviewer other than `set` and `proportion` receives one body, the approved spec
  at its hash, every sibling's Interfaces block and, for `readiness`, the unit's
  `orient/<unit>.md` when it exists (§9.3). Units run **concurrently**, and the goldfish
  within a unit's panel concurrently.
- The reviewer id `proportion` is the zoom-out persona (`agents/zoom-out.md`, adapter
  `.claude-plugin/agents/zoom-out.md`) dispatched with the plan brief
  `skills/review-plan/references/proportion.md`: it receives the body, that unit's
  `plan/scan/<unit>.json` (§9.1) and the unit's spec range at the frozen hash, and answers
  question 11 and, from amendment 9, the per-unit split check written into `proportion.md`: a
  unit over 10 Steps or 24 KB, over eight Scope paths, or whose Scope crosses subsystems (§9.1's
  families) is reported as a split candidate (`medium`), `scan`'s `warnings[]` at those values
  its evidence; the chain check is the `set` reviewer's (above). A proportion finding names the
  Step and the bytes it would remove, or the split; its severity is `medium` at most.
  `readiness` is unchanged. Dispositions follow §8 unchanged.
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
is run in at `--ref` (default `HEAD`), exported with `git archive <ref>` into the handoff's
`orient/export/` (emptied first; one fixed path per handoff, so graphify's caches key the same
files every call and no two handoffs share an export, §7; `orient` refuses, `orient: <skill> card
<id> is open`, while another card of the handoff whose skill runs it is open), so an uncommitted edit, an untracked or an ignored file never reaches it or graphify.
Every call exports and, with graphify, builds afresh. Without `--unit` it writes `orient/map.md`
and, when the resolved handoff (§7) is open (its `state.json` has no `closed_at`), every unfiled
unit's file; with `--unit` it writes the named units' files only. With `--unit`,
`orient` writes the unit files only and leaves `orient/map.md` untouched; the map is written by
a run without `--unit`. A unit whose
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

**The two files.** Two store kinds, both under the handoff directory (§7): `orient`
(`orient/map.md`, `orient/export/`, `orient/graphify-out/`; `Store.path("orient", "map.md")`)
and `orient_unit`,
handoff-keyed like every unit file (`orient/<unit>.md` under the handoff directory, `<6 hex>/`
in a legacy flat store, §7; `Store.path("orient_unit", "<unit>.md")`; `Store` maps that kind to
the directory `orient` under the handoff's); never under
the working tree, never committed. Each file's first line is its record:
`orient: tree <sha> · graphify: <graph.json sha256 | not installed | failed: <reason>> · trimmed:
<what was cut | nothing>` (the map's cuts read `communities <n>, depth <d>`; a unit file's name
its trimmed items). A dispatch that is handed a unit file is recorded `exposed:orient <tree
sha>` (the callers table below), so the round record names what its reader saw.

| File | Contents, in order | Cap and trimming |
| --- | --- | --- |
| `orient/map.md` | with graphify: `graph.json`'s summary (nodes, edges, communities, the EXTRACTED share) and the 40 largest communities by node count, each by its id with the five files holding most of its nodes; then the repository map: one line per directory to depth 4 over the tracked files, skipping `dist`, `build`, `vendor`, `target` and `scratchpad`; each line the path, file count, dominant extension, entry points (`__init__.py`, `main.*`, `index.*`, `mod.rs`, `__main__.py`) and the first heading or first sentence of any `README.md`, `AGENTS.md`, `CLAUDE.md` or `context.md` there (one line, ≤160 chars) | 24,576 bytes: the community list is cut to what fits beside the map, then the depth is reduced until the map fits; the first line says so |
| `orient/<unit>.md` | for every Scope path of the unit (a directory path contributes each file under it): an existing file's module docstring (first paragraph), its public signatures (`def`/`class` lines not starting with `_` for Python; exported `function`/`class`/`export` lines for JS/TS; the first 40 lines otherwise) and the test files that name it, wherever they live (the test-file name rule: under a `test`, `tests`, `__tests__` or `spec` directory, a `test_` prefix, a `_test`, `.test`, `_spec` or `.spec` suffix, or the basename `conftest.py`, over the walk with the map's skips `dist`, `build`, `vendor`, `target` and `scratchpad`); for a path to be created, the sibling files' public signatures; with graphify, a `## Graph` section per Scope path: the nodes whose `source_file` (relative to the export, compared with the Scope path relative to the repository root) is the path or under it, every EXTRACTED edge touching them with the neighbour's `source_file` and `source_location` (callers and callees, one hop), the other edges apart with their confidence, and each node's community id; then `## Read first`: every heading-delimited section of the `README.md`, `AGENTS.md`, `CLAUDE.md` and `context.md` files at the repository root and in the Scope paths' own directories (walking up to the root) that names the unit, verbatim, each section once. "Names" means, as whole words: a Scope path as written, its basename, its directory, or for Python its dotted module name | 16,384 bytes, trimmed in this sequence until it fits: (1) the tests lists, (2) the sibling signatures, (3) `## Read first`, (4) the `## Graph` edges whose neighbour is outside the Scope, (5) the `## Graph` edges between Scope files, (6) the `## Graph` node lines, (7) the docstrings and Scope signatures, path by path in Scope order; the first line says what was trimmed |

**Callers**, each a small change in an existing skill body or module; nothing else runs or
reads the files:

| Caller | What it does |
| --- | --- |
| `plan` | runs `orient --spec <path>` under its card before drafting and after every `graph --plan` (the map, and every unfiled unit's file once a handoff is open); the elephant reads `orient/map.md` before drafting |
| `review-plan` | runs `orient --spec <path>` under its card when it starts and after every `graph --plan` it runs (a fix re-rendered the bodies), names `orient/<unit>.md` in the `readiness` goldfish's brief (`skills/review-plan/SKILL.md` Step 2) and records that dispatch `--isolation exposed:orient <tree sha>` (with whatever else the goldfish reports); when the file is absent the brief says so; `review-plan` reruns `orient --unit U<id>` after each `graph --plan` re-render of a unit, so a round reads a fresh unit file |
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
  <option> — <reason>` from a login in `config.owners` (amendment 5; §13.2's one grammar), naming
  that comment's id; until then it is a `foreman` high (§11).

## 11. Wave, foreman, builder (phase 5): the contracts

`/superegm:wave <spec-path> [--leavemealone]`

This section states what the wave guarantees and what each actor may do. How the elephant's loop
observes events, orders a batch, folds a builder's exit with its status comment, retries an
`error`, resumes after a compaction, assembles a prompt file or reads a GitHub protection is the
U09, U09b, U10 and U10b plans' content, written as tests against these contracts. §11.1 is the
wave as 1.0.0 built it; §11.2 (amendment 5) is the fleet layer over it: rulings by comment, the
inbox, the notify hook, the registry and the driver.

### 11.1 The wave, the builder and the foreman

**The repository's protection (checked by `launch`, recorded in the wave card).** Before any
builder is launched, `launch` fetches and refuses unless: the spec at `origin/<base>` hashes to
the handoff's approved `sha256` or to a later entry of the spec's approval history (the chain,
§7), and is refused when it is neither (owner ruling
2026-11-05: with one store per handoff several handoffs of one spec run in parallel and every
amendment moves the spec's hash, so a handoff approved at an earlier link of the chain must
still launch; U20), with the frozen range read at the sha the body cites, never from the checkout:
`launch-builder` copies the body's cited range from the spec at the sha256 the body's marker
names (`git show <commit>:<path>` at the history entry's commit, or at any commit on `<base>`'s
history whose spec hashes to that sha when the entry's was rewritten: a content read) into the
prompt file under a `# Spec range` heading, and `prepare --dispatch` writes it as
`spec_range.md` beside the diff for the head's goldfish, so a later link's bytes in the base
move nothing; when no commit holds those bytes `launch-builder` refuses the launch and `prepare`
fails, the foreman recording the round `not run (error: spec range: no commit holds <sha7>)`
through `collect --not-run`, never a fallback to the checkout (U20), and
`.superegm/config.json` exists there; `origin/<base>` carries a
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
login, the bypassing role or team, or the team the builder belongs to. When the builder is a
GitHub App (below), the App must not be a bypass actor on the base rule: the check reads the
ruleset's `bypass_actors` for `actor_type: Integration` with the App's id and refuses when
present, and the classic-restriction path refuses when the App appears in `apps`; the
`superegm/**` rule is unchanged. When
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
that step. README step 1 and `init`'s STEPS carry the App alternative (the registration
settings: name, no webhook, visibility `Only on this account` when the owner's installations are on that account alone,
public when several accounts are to install it (a private App installs on its owner account
only; a public one is installable by anyone and the key would mint for any installation, so the
owner reviews the App's installations list by hand: `doctor` checks this repository's
installation, not the others), the four permissions `doctor` checks (Contents
write, Pull requests write, Issues write, Metadata read, no Workflows), install on the
repository and on whatever other accounts the owner chooses (an installation that includes the
repository is the requirement, owner ruling 2026-11-05: the App may be installed on several
accounts), note the
App ID and slug, generate the key and keep its file at the path the
variable `private_key_env` names (`SUPEREGM_APP_KEY` by default)) as the recommended path for an organisation, the machine account as the
quick path for a personal repository. Under that
protection the builder account can open PRs and never merge them; the owner, who alone updates
`<base>`, merges by hand (with the admin bypass, `gh pr merge --admin`, where the base ruleset
restricts updates to the owners: `doctor` prints that line as information, and `wave` and
`integrate` say it where they tell the owner to merge, §5); the plugin ships no approve or merge
path, and the elephant and the
foreman hold no GitHub write but the review comment, the ruling and decision comments, the
`superegm:stopped` label, from amendment 10 the board in the tracking issue's body (U30) and, from amendment 11, `close`'s issue closes (U32). `launch` also skips units labelled `superegm:stopped`, and counts a
unit in flight from its first launch until its latest round's `outcome` is `clean` (and, from
amendment 5, not again when an ingest rewrites that outcome `revise`: the unit is then ready and
takes a slot when `launch` marks it, U21's `launch.py`), it has
landed, it carries that label, the elephant names it idle (`launch --idle U07,U08`: the units
this invocation found stalled or CI-waiting hold no slot) or, from amendment 5, it is pending a
decision (§11.2, U24).

**The builder as a GitHub App.** The builder's credential is one of two: the machine account
above (`builder.gh_token_env`) or a GitHub App, `builder.app` = `{app_id: <int>, slug: <the
App's slug>, private_key_env: "SUPEREGM_APP_KEY"}` (default `null`), the variable holding the
path to the `.pem` file; the key's text is never in the repository, the config or the
environment. One identity per repository: `builder.app` null, the machine account, whose
variable must be set; `builder.app` set, the App, and `launch` and `doctor` refuse when
`builder.gh_token_env`'s variable is also set (the refusal names both variables), so every
ruling, decision and close read keeps excluding one builder login. Minting adds no Python
dependency: a JWT (RS256; `iat` now − 60 s, `exp` now + 9 min, `iss` the app id) signed through
`openssl dgst -sha256 -sign <key path>` (`openssl` is on macOS and Linux; `doctor` checks it);
`GET /repos/<repo>/installation` with the JWT gives the installation id, resolved on every mint
(nothing is cached: a token in the store would break the U15 risk line, and GitHub's secondary
limit on content-creating requests, 80 a minute and 500 an hour per App, bounds a wave to about
250 `gh` writes and pushes an hour across its builders, each a mint plus the write, the shim
minting for the credential helper's `get` alone while `store` and `erase` pass the sentinel,
which `gh` ignores: above a wave's need, a builder making a few dozen; `builder-token` reports
the limit's refusal verbatim; each minted token lives its hour unrevoked, a residual §4.1
names); `POST /app/installations/<id>/access_tokens` gives a one-hour token with
the installed permissions. The three calls are made with `urllib.request` (standard library;
never `gh`, which refuses `api` with no token configured and would be the shim itself in the
builder's environment); the tests fake that transport, and `doctor`'s App lines use the same
client. `superegm builder-token [--repo <owner/name>] [--app-id <int> --key-env <name>]`
prints that token on stdout, exit 0, or exit 1 with the refusal; the flags default to the
config and the per-launch script below passes all three, so no config is read at mint time
(the worktree's config is the ref's, not the owner's). A mint is a read in §2's sense (it
creates no GitHub resource a person can see or delete and writes nothing to the store), so
`builder-token` and `doctor` take no run card. The builder session never holds a static token
and nothing on this path depends on `PATH`: `launch-builder` writes, per launch and outside the
repository, `launches/<unit>_r<n>_bin/` (§7) holding `superegm-token` (runs `superegm
builder-token` through the `python3` and plugin root the launching helper runs under, with the
repo, app id and key variable baked in, and prints a fresh token on stdout, its one protocol)
and a `gh` shim that sets `GH_TOKEN` from it and execs the real `gh` by the absolute path
`launch-builder` resolved on the launching machine (`shutil.which("gh")`) and baked in, failing
closed: when the mint fails it exits 1 with the refusal and execs nothing. The orders carry one
placeholder, `{{gh}}`, in every `gh` call; `launch-builder` fills it with the shim's absolute
path on this path and with the real `gh`'s (`shutil.which("gh")` at launch) on the
machine-account path, and on both paths the launched allow-list carries the `gh` prefixes of
`config.builder.allowed_tools` rewritten to that path (`Bash(<bin>/gh pr create:*)`) and not
the bare ones, and the credential-helper entry names the same absolute path, so a bare `gh …`
is refused by the allow-list and no `PATH` order is assumed on either path (§4). The launched command sets `GH_TOKEN` to a sentinel that is no token (`superegm-no-token`), as
the machine-account path's `GH_TOKEN` masks the keyring today: the shim overrides it with the
mint, and a real `gh` reached by any other route sends the sentinel and fails with 401 instead
of the owner's keyring login (`GITHUB_TOKEN` unset). On both paths (the machine-account path
had none of this in 1.1.0, and Apple's git ships `credential.helper=osxkeychain` in its system
gitconfig ahead of the launched entry) the builder's git reads none of the owner's
configuration: `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` at `/dev/null`,
`GIT_SSH_COMMAND=false` (every SSH transport fails closed, an owner's `pushInsteadOf` to SSH
included), `GIT_ASKPASS` and `SSH_ASKPASS` unset, `GIT_TERMINAL_PROMPT=0` and `core.askPass`
empty (a failing helper ends the search); the credential helper is the launched `gh`'s
(the shim, or the real `gh` on the machine-account path) `auth git-credential` by absolute
path behind the empty reset entry
(`credential.https://github.com.helper=` then `!<bin>/gh auth git-credential`, the form
`gh auth setup-git` writes), which clears a helper the repository's own `.git/config` names;
the `GIT_CONFIG_KEY_n` pairs of the launched command's environment carry those entries, the
HTTPS `insteadOf` rewrites, and `user.name` and `user.email` (the identity below on the App path; on the
machine-account path the token's login and `<id>+<login>@users.noreply.github.com` from
`gh api user`, which `launch` reads once per wave beside `builder_login`), and no git config
file is written (§4). `superegm-token` runs `openssl` by the absolute path
`launch-builder` resolved (`shutil.which("openssl")`, refusing the launch when there is none),
as the shim runs `gh`; the scripts quote every path they bake in (`python3`, the plugin root, the key, `openssl`,
`gh`), and `doctor` and `launch-builder` refuse an `artifacts_dir` with whitespace on this path,
the one path that reaches the unquotable allow-list prefix and the orders. On this path `launch` and `launch-builder` replace the token
predicates (the token set, its login not an owner, the collaborator role) with `doctor`'s App
lines below, of which `launch` repeats at every wave the reads that can change under it: the
installed permissions, the installation that includes the repository, the `GET /app` slug and
id, and the App as a bypass actor. Tokens expire hourly and the helper mints on demand, so a builder that runs for
hours never fails on expiry. The exposure this buys: the builder session can read the key file
the path names (it mints in the builder's environment), so the App's reach is the
installations the owner chose (`doctor` reads `GET /repos/<repo>/installation` with the JWT and
refuses unless an installation includes `config.repo`; several accounts are allowed, owner
ruling 2026-11-05, and a builder that mints reaches every repository they include, §4.1), and a builder that commits a token
is stopped by GitHub's push protection where the repository has it, and one that commits the
key by its non-provider pattern scanning where that is on as well (a private key is a generic
pattern; `doctor` reports `secret_scanning_push_protection` and
`secret_scanning_non_provider_patterns` from `GET /repos/<repo>`'s `security_and_analysis`,
informationally; both free on a public repository), otherwise either is seen by the owner's
eyes on the diff, after which the owner rotates the key or the token; the plugin scans no content itself (two rounds of this review
showed a scanner of its own to be a surface of false stops and republished secrets); §4.1 and
the U15 row say so. Identity: the builder login is
`<slug>[bot]` (`GET /app` with the JWT confirms the configured slug and id); commits are
authored `"<slug>[bot]" <<bot user id>+<slug>[bot]@users.noreply.github.com>`, the id being the
bot user's (`GET /users/<slug>[bot]`, a public read `launch` makes once per wave and records
with `builder_login`), not the App's; `launch` records `builder_login` in the slug form, and
every reader of the builder login (`launch`, `launch-builder`, `prepare`'s `comments.md` line,
`decision`) derives it from the config on this path (`<slug>[bot]`, no token needed) and from
the token on the machine-account path as today; the audit-trail line is unchanged (it names
the human launcher).

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
profile exists and is empty of `CLAUDE.md`, hooks (a `settings.json` with a `hooks` key;
`profile_problem` gains that check, so `launch-builder` refuses it too) and plugins of its own
(a managed plugin is policy and passes; a synced or installed one is refused) and, from
amendment 7, of a `skills/` or `commands/` directory, and its `settings.json` sets
`disableClaudeAiConnectors` true; and every id in `config.builder.plugins` resolves to an
installed `user`-scope entry in the elephant profile's `plugins/installed_plugins.json` (§7) and
is none of the builder profile's managed plugins (it would load twice; `profile_problem`'s lines,
so `launch-builder` refuses too), the set printed (`plugins: <id>
<version> [<hook events>]... | none`, `mcp: <names> | none`); and, from amendment 8, the role
table, one `model:` line per role, each value as configured (`model: builder <model> <effort>`,
`model: goldfish <alias> <effort>`, `model: astra lanes <model> <effort>`, `model: astra head
lane <model> <heads_effort>`, `model: judge <member> <model> <effort>` per member; informational,
as the `astra:` line is; the elephant is the session's, not printed). Its own lines, which `launch` does not check: `stall: <builder.stall_minutes> min` (amendment 10, informational); `gh` resolves on this machine
(`shutil.which`, the path the launch bakes in, both paths); the `gh auth`
login is in `config.owners`; the builder's role on the repository
(`repos/<repo>/collaborators/<login>/permission`) is `write` exactly, the role found named
otherwise; the token's kind and scopes, from the `X-OAuth-Scopes` header of `gh api -i user`
with the token (a classic token must carry `repo` and not `workflow`; a fine-grained token sends
no scopes header and is reported `fine-grained: permissions not probed`); and, informationally
and never a failure, that `graphify` is on `PATH`, the Astra runner (`astra: ok (<runner path>)`
or `astra: not installed (heads will record not run)`, U17) and the admin-bypass merge line
above. On the App path (`builder.app` set) its
lines are instead: the credential path in use (a refusal naming both variables when the
machine account's is also set); the variable `private_key_env` names (`SUPEREGM_APP_KEY` by
default) set and the key file readable; `openssl` and `gh` resolve on this machine (the paths
the launch bakes in); `artifacts_dir` holds no whitespace; under the launched environment minus
the shim, `gh auth token` prints the sentinel, `git remote get-url --push origin` starts with
`https://`, and `git credential fill` for `https://github.com` with a failing helper fails (no
askpass, no terminal and no owner helper answers); the JWT mints (`GET /app` answers with the configured slug and id); the App is
installed with an installation that includes the repository (`GET /repos/<repo>/installation`
with the JWT answers 200; the App may be installed on several accounts, owner ruling
2026-11-05, and `doctor` lists every installation, account and repository count, as
information) whose permissions are Contents write, Pull requests write, Issues write (builders
comment on their issue), Metadata read and nothing beyond those four (`administration` and
`organization_administration` first among the refused, since a key that can edit a ruleset can
drop the fence; `workflows` with them), read from that installation's own
`permissions`, never from the repository's `permissions` object, which answers `push: false` to
an installation token; a token mints; the App's id is
not a bypass actor (the `bypass_actors` field the protection check reads).
The machine-account path keeps the lines above and gains the two git probes (the push URL
under the launched environment starts with `https://`; `git credential fill` with a failing
helper fails), which run on both paths.

**The driver loop** runs in the main conversation (typed by the owner, or launched by the
owner's timer, §11.2, one session per store at a time), is the only long-lived actor, and is
event-driven: `superegm launch` marks the ready units up to `max_in_flight`; the elephant launches
a builder per marked unit; `superegm status --wait <s> --runcard <id>` (EGM's loop, reading
only and saving once on return, the board's GitHub write and its `board_changed_at` save aside (amendment 10, §7), extended to
read exit files and each unit's issue and PR comments) returns **every** unreported change since its last save, one event line each, or
`deadline` when nothing changed. The event kinds are `head` (with its CI state), `status` (a
builder status comment), `exit` (a builder exit), `landed`, `closed` (a PR or issue closed by
hand, with its actor), `deadline` and, from amendment 5, `ruling` (an owner's comment in §13.2's
form: the unit, the author, the decision or finding it names, the comment id); the line form is
U09b's, the seventh kind's U22's. From amendment 10 every `status` pass of a `wave` session,
`--wait` included, does two more things. The watchdog (U31), one predicate and one clock: a
`running` launch without the `kill_failed` mark, no exit file, whose branch shows no commit newer than the launch's own newest
commit (or than its `started_at` when it has none) for `config.builder.stall_minutes` (30) is
stalled (the launch sense of §2's row, amendment 10); the pass, a reader,
reports it as the event line `U<n> stalled (<minutes> min; last commit <time | none>) pr=<n or none> status=<word or none>` from a
local read of the worktree `HEAD` and `started_at`, derived afresh at every pass while the launch
is `running` and unmarked (the predicate, no fingerprint: a session that ended before step 3 sees
it again), and the skill's step 3 records it through
`record-launch --exit stalled`, which re-reads the entry (an `interrupted` it finds is kept),
checks that the group the `pid` names is the launch's own (a live group with no leader is: the
wrapper died, its `claude -p` lives on, the signal ends it and the record is `kill_failed (no exit file)` by
construction, the owner's interrupt the close; a present leader must be the launch's wrapper, the proof
the plan's, the entry's `command` one; `kill_failed (pid reused)` when it is another's,
`kill_failed (no process)` when no member lives, no signal either way),
signals the process group through the `pid` the entry carries (the wrapper `launch-builder`
spawned as the group's leader, below; U25's `kill_group`, the helper's one, sends SIGTERM, the
signal the wrapper traps, and never escalates: the wait is `record-launch`'s own), waits for the wrapper's exit
file `stalled` (the wrapper traps the signal and the trap's write ends it, no code written after;
the one proof, §4; a file reading a code instead is refused, the next pass's `exit` line recording it), records `exited (stalled)`
with the last commit time (`last_commit_at`, the launch's own newest commit, one newer than
`started_at`, which every `--exit` writes, or none: the one field the carve-out reads for an exit or a stall) and journals it (the stalled line is that
launch's exit line: `status` masks the `exit` and `builder_status` fingerprints of an `exited (stalled)` launch, so no
`exit` or `status` event follows, the folded word reaching the stall's question; a `kill_failed` launch's late exit file still flows, below), the unit going to decision point 3 with the stall facts (below); no exit file within 30 s is recorded `kill_failed` instead, the launch
`running` and signalled no more, the unit idle with that reason and in the inbox for the
owner's typed interrupt, and a later pass that finds its exit file reports the exit as it
reads, `--exit <code>` as for any launch or `--exit stalled` recording with no guard and no
signal when the file already exists, either clearing the mark. The session's pass is the one
reporter and `record-launch` the one writer: the driver tick reads and launches, and the
session it launches reports at its first pass (§11.2); no foreman and no goldfish is killed,
there is no per-step timer, and no web UI. The board (U30), for the owner away from the store,
the tracking issue being the one page GitHub shows them: the report's `## Units` line per unit,
from amendment 10 with the new columns (unit · state word, `report.py`'s `unit_state`
(`active` is the ruling's in flight; a cap shows as `pending` with `waits on` naming the
decision; a `kill_failed` launch still `running` reads `idle` by one more clause of
`unit_state` over that field, the owner's interrupt ending it as any launch) plus `ready` for an unlaunched unit in the saved `status.ready` set less the card's `idle[]` (those read `idle`, the refusal the reason) and `waiting` for any other
unlaunched unit (the point-3 word `blocked` is a case, not a state), derived once there ·
round · launch · head, 7 hex · PR · waits on, the units or the decision it is blocked by, or `ci` for a head whose CI is pending or absent · next
action, `word_action`'s verb for a posted round newer than the latest launch, none while a
launch runs, `foreman dispatch` for a terminal launch (it refuses or acts: the predicate's one
place, below), the idle reason's action for
`idle` (the interrupt for a `kill_failed` one), the decision for `pending`, `launch-builder` for
`ready`,
none for `waiting`, `landed` and `stopped` · cost, the
launches' `total_cost_usd` summed from the entries, where `record-launch --exit` writes it from
the result file's read it makes for the model, none until then, U28; a killed launch's result file is partial: its entry records the cost as unrecorded and the cell marks the sum partial), one table in the report
file, on stdout and in the issue, under a header line (the handoff id, `<base>`, the spec
sha256's first 12 hex, the waves, the time of the last change, which `status` saves in
`state.json` at the splice's write and `report` prints), written by `status` into the
tracking issue's body between its two markers (§7) through the one splice function and
`apply.edit_issue`: a writing pass reads the body once at the splice, compares the fresh rows
with the block's, sets `board_changed_at` to the pass time when they differ (kept otherwise: the
one copy, saved to `state.json` at that write and printed into the header) and writes in the same step, a failed write journaled and
never failing the pass (as a failing notify hook, §11.2); the
inbox stays the action list (§11.2); per-round history stays in the store; no unit issue is
written. Invariants the U10b plan must pin,
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
- At every batch, before any `foreman dispatch`, the wave runs `review ingest` (§8) for every unit
  with an open PR, awaiting-merge units included and stopped units excluded; a unit whose `clean` outcome the ingest
  rewrote `revise` is handled as a `revise` word (the next builder is launched with the review),
  its slot having been freed at `clean`: it is ready, not in flight, until `launch` marks it again
  (§8; the in-flight predicate above says so).
  A thread that arrives after the loop ended is ingested by the next `wave`, typed or
  timer-typed.
- A `ruling` line is applied as the point's own subcommand says below (`decision rule --by
  <login>` with `review settle --owner`, `review rule --owner`, or the deviation's record) and
  journaled `Ruling (<login>, comment <id>): …`; an edited comment is re-read, a recorded ruling
  never changes (a later edit journals `ruling edited after record, ignored`), and a `ruling`
  whose decision is already ruled, or that names no open decision or finding, is journaled and
  dropped (the whole-file `test-delta <file> allowed` form names every open decision whose
  `test_delta` entry is in that file, a point-2 form the unit's open point-2 decision, and `redesign` its open point-1
  and point-2 decisions, §13.2) (the `dod-<n>`, `test-delta`, deviation and `tdd-order` rulings reach `collect` from
  the comments whatever the event's fate). A re-typed `wave` reads them before
  its first batch, as it reads pending decisions.
- A builder's `exit` and its `**Builder status:**` comment are one decision, never two.
- Lines for a stopped unit are ignored except `landed` and, from amendment 10, `stalled` (step 3
  records it the same: the kill is the one thing left to do for a stopped unit's launch, U31). A launched unit whose PR is closed
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
  want of a slot, every pending decision, every stopped unit and its unlanded dependants), whose
  `## Units` line per unit is, from amendment 10, the board's row with the new columns, one
  table in the file, on stdout and in the issue (U30), and
  at the end closes the run card. The skill is re-typeable and resumes from the store without a
  second launch, ruling or review of anything already recorded. A pause at a decision point
  ends the loop; builders keep running; the next `wave` handles what they reported.

**Launching a builder** (`superegm launch-builder --unit U07 --round <n> --runcard <id>`, where
`--round` is the launch count). It refuses unless the unit is marked by `launch`, every earlier
launch is terminal, the builder token and profile pass §4's checks, and the issue body read back
equals the body the write list of the filing that created the unit's issue (`state.json.filings[]`)
stores for it, filled and normalised as `verify` compares. Every launch adds a fresh worktree
under `worktrees/U07/` on branch `superegm/<handoff-id>/U07` (round 1 from `origin/<base>`,
later rounds at the PR tip), then detaches the earlier launch's worktree from the branch
(`git switch --detach`; nothing in it is removed; from amendment 11 the invariants of a re-run: a failed re-run
leaves the earlier launch's worktree on its branch and the round's own never on it before the
spawn; a re-run reuses its detached `r<n>` and refuses one on the branch, a launched builder or
the window before the spawn, which the owner's hand clears once they have checked no builder
runs there (`clean` keeps what no launch records; the catch below kept); the step order is the plan's, U32), and leaves earlier worktrees for
`/superegm:clean`. It writes the prompt file, which holds exactly: the issue body,
`references/builder_orders.md`, the `pr_block_file` text under a `# PR block` heading when the key
is set, the unit's orient text under a `# Orient` heading (§9.3), the body's cited spec range
under a `# Spec range` heading (above), every `**Deviation**` comment,
every `**Decision D<n>:**` and `**Ruling:**` issue comment **whose author is in
`config.owners`** (a `**Ruling:**` comment only when `ruling_of` parses it or it carries the
judges' panel marker; a `**Decision D<n>:**` comment by its heading and author; amendment 5; an
inexact ruling form binds nothing; 1.0.0 took any non-builder author, which on a public repository
let a passer-by's ruling-form comment order the builder, anti-goal 10; the judges' posts are under
the elephant's token and pass), and from round 2 the foreman's review comments on the PR (the platform passes it as one
argument, §4; a prompt past the platform's limit fails the launch, which `record-launch --exit`
records). The launched command carries: the builder profile; `--plugin-dir <dir>` for each plugin
`config.builder.plugins` names (the directory and version of its `user`-scope entry in the
elephant profile's `installed_plugins.json`, §7, enabled there or not; a listed plugin's hooks,
skills and bundled servers come with it) and
`--mcp-config launches/<unit>_r<n>_mcp.json --strict-mcp-config`, the file written from
`config.builder.mcp` at the launch, so no other MCP configuration loads (whether the flag keeps a
listed plugin's bundled servers is the platform's, pinned by U27's plan with one run; the
servers the builder sees are the file's and those, no other); the set recorded in
`launches/<unit>_r<n>_plugins.json` (each plugin's id, version, directory and hook events; the
managed plugins; the MCP file's server names) at the launch, §7;
`GH_TOKEN` from `builder.gh_token_env` (on the App path, the sentinel `GH_TOKEN` and `<bin>/gh auth git-credential` instead; on both
paths the owner's git configuration, SSH and askpass shut out and the helper reset, §11), with the HTTPS push rewrite and credential helper in its
environment; `ENABLE_CLAUDEAI_MCP_SERVERS=false` (belt and braces over the profile's
`disableClaudeAiConnectors`, §4); `SUPEREGM_ROLE=builder` and `SUPEREGM_RUNCARD`; `claude -p` with the prompt file's
content, the configured model, effort (amendment 8: `--effort <builder.effort>`, the session
flag `-p` honours, U28's one-run case; `CLAUDE_CODE_EFFORT_LEVEL`, which would beat the flag, is
unset in the launched environment beside the askpass and token names) and permission mode; the allow-list (its `Skill(...)` and `mcp__*` rules among them, amendment 7) plus a push prefix for the
unit's own branch and `Bash(<first word>:*)` for every command `run_commands` returns from the
body; `--output-format json` into the result file; and the exit file on exit. From amendment 10
starting the launch is `launch-builder`'s one behaviour, U24's (amendment 5's `--start` flag is
gone; the typed wave skill and the tick's session both call it, and the command line it would
have printed goes into the entry as the record, the journal line `<unit> launch <n> running (pid <pid>)`), a Popen in a new session with
the wrapper the process-group leader, and `launch-builder` appends the `running` entry itself,
once, after the spawn (`started_at` taken then; a crash between
the spawn and the write leaves a builder with no entry, the accepted window, git's refusal on
the unit's existing worktree path the catch against a second builder), with its full field set
(§7: `round`, `worktree`, `branch`, `started_at`, `boot_id`, `pid`, `command`,
`prompt_sha256`, `result_file`, and U28's requested `model` and `effort`), `record-launch`
keeping its `--exit` role alone (`--exit <code | stalled>`; the flagless form is refused from
U24 on; `--exit stalled` the watchdog's, U31's: the signal, the 30 s wait and the record or
`kill_failed`, §11). An
allow-list containing `Agent`, `Skill` or bare `Bash` is refused.

**The builder orders** (`references/builder_orders.md`, absorbing superpowers' implementer prompt
and the discipline of its receiving-code-review and test-driven-development skills): the skills
the builder may invoke are the ones its allow-list's `Skill` rules name, written into the orders
at the launch (amendment 7; none when the list has no rule); a detached `HEAD` in its worktree
stops it with `BLOCKED` (amendment 11); follow the
Steps in order, test first, one `test(S<n>)` commit then one `feat(S<n>)` commit per Step; run
every DoD `Run` command and paste each item's output in the PR body under its item number, refreshing the body with
`gh pr edit --body-file` before each round's push (amendment 11: the `--body-file` form written into the
orders' existing before-push refresh line, the one such line once the push paragraph's after-push clause is dropped with it, U27), as a
fenced block; push with `git push origin <branch>` and never to any other branch; open a
**draft** PR against `<base>` whose body is the unit id, the prompt's `# PR block` section when it has
one (verbatim, right after the audit-trail line), the DoD results in that form and
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
its scope paths, never merges. The PR body's first line after the title block is `Launched by <owner
login> · run card <id> · unit U<n> · handoff <handoff id>`: the login of the human whose session ran
`launch` (what `gh api user` returns there), written without an `@` so it mentions nobody; the
orders say the line is kept verbatim.

**The foreman** is a named subagent (`name: foreman-U07-<dispatch_id>`) dispatched through the
`superegm:foreman` adapter (`omitClaudeMd: true`; tools `[Agent, Bash, Read, Grep, Glob]`) in the
foreground, with `references/foreman_brief.md`, the unit id, the handoff id (passed as
`--handoff <id>` on every subcommand it runs, §7), the wave run card, a child card and
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
  record --sha256 <head>`. The Astra lane sits on the head's panel whenever the lane is on
  (`astra.enabled`, which `init` writes false and the owner turns on once, for every kind, with
  `astra.heads`, true from `init`; `astra.heads` false drops it; `reviewers.head`,
  `change-review, astra` from `init`, lists it for the record and decides nothing, §8's append
  rule being the one control; the 1.0 ruling `q-wave` Q1 kept the lane to specs and plans, and
  the owner reversed it on 2026-11-04, U17): the foreman runs it as `review-spec` runs it on a
  spec, the claudex-loop runner in `review` mode (`resources/astra_lane.md`'s command) over a
  brief file `prepare --dispatch` writes as `review/<unit>/pr<n>/r<n>/astra_brief.md` beside the
  diff and CI files (the helper the writer, §7; `collect` records the file's sha256 with the
  lane's record) carrying what the Claude goldfish receive (the unit
  body, the frozen spec range, `git diff <base>...<head>` in the review worktree at the head cut
  at 400 KB with a note, the CI file, `pr_body.md`, `comments.md`, and the last posted round's
  findings with the builder's replies and, on Astra's own, their dispositions), once per head
  per round, after CI concludes and after the Claude panel returned, fresh every round (no
  `--resume` on a head: the foreman keeps no session handle), as one foreground Bash call with
  the runner's `--timeout 540` (and, from amendment 8, the lane's effort `astra.heads_effort`,
  `high`, read by the foreman from the config file as its brief's step 2b directs, `high` the
  brief's own fallback for a key the file lacks; the Astra judge member's `effort` is its own,
  §13) and the tool's timeout at 600 s (the platform caps a foreground
  call there, §4; a head's diff is small, and the brief says so): no background command, no
  wait, the call returns with the run's end (the one session the foreman starts, §4; a batch
  waits for its foremen, so the lane adds at most 600 s to a batch), and
  records its `result.json` through the existing path (collected and mapped as `astra_lane.md`
  says, then `review record --reviewer astra`); Astra's findings carry §8's form and
  dispositions, and `clean` counts an unsettled high or medium of Astra's like any other. When
  claudex-loop is absent on the machine running the wave, the runner refuses or returns no
  `result.json`, or the call returns at its timeout without one, the round records
  `astra: not run (<reason>)` (`not installed`, `failed: <error>`, `killed`, `timeout`) and
  completes on the Claude reviewers: the returned call is an exit the foreman observed,
  never silence read as death (anti-goal 8); `clean` never waits for a lane that did not run,
  and the foreman's word is given when every seated lane has recorded or is `not run`.
- `collect --dispatch <id>` records, through one `review record --reviewer foreman` call, as
  high findings: CI not green on this head; an `Exists` DoD item whose path is absent, or a `Run`
  item without its fenced output in `pr_body.md` (`dod_items`); a changed path outside the unit's
  Scope paths (read from the frozen section, §9.1); a `tdd-order` failure (over the PR's commits,
  base to head with a merge's both parents, in order: for each Step n the first `test(S<n>)` commit
  touching that Step's test path precedes the first `feat(S<n>)` commit touching its implementation
  path, wherever in that range either sits; and every `test(S<n>)` commit touches only test files,
  the test paths the body's Steps name or files the §9.3 test-file name rule names (a `conftest.py`
  anywhere; fixtures under a test-named directory); a commit with any other subject, an adopted branch's own `test(…)`
  history among them, is read by neither clause) not overruled by a later `**Ruling:**` from a login in `config.owners`
  (`ruling_of`, §11.2; amendment 5, which 1.0.0 read from any non-builder author); a deviation of
  kind `interface`, `dod` or `test` not yet ruled (ruled when such a `**Ruling:**` names its
  comment id, §10); and every finding of the last posted round the
  builder replied `contested` to, which is unsettled until a ruling. It reads `**Reply <fid>:**
  contested — <reason>` lines into `builder_contested[]` as `{fid, reason}`, ignoring a reply to
  the CI finding (the external threads held for this head are the batch's `review ingest`'s,
  §8, never this call's). From amendment 5 (U25) it verifies and never trusts, two gates before
  the word. **The DoD re-run**: `collect`
  reads every input it judges first (the CI JSON, the diff, `pr_body.md`, `comments.md`, the
  round's record and `foreman/<unit>.json`, and the test files of both commits from git objects,
  never from the worktree), holds them in memory, and only then runs every DoD `Run` item of the
  unit body (`dod_items`: the body's lines as written, through `/bin/sh`, never `$SHELL`, whose
  `~/.zshenv` would re-export what the allow-list dropped, each naming its own
  interpreter or runner; the builder's paste is compared, never run; `doctor`'s `python3.12` line
  is this repository's own prerequisite, not the gate's) in the review worktree at the head sha
  (which `prepare` removes by force before it adds the next round's, the worktree being the
  store's and never a person's, since a `Run` line may leave it dirty),
  the whole `collect` call bounded by `config.foreman.run_timeout_minutes` (8; at most 9, under the
  Bash tool's 10-minute foreground cap it runs under, §4, which the foreman brief asks for on the
  `collect` call, `timeout: 600000`, the tool's default being 2 minutes, pinned by a test of the
  brief's text: the reads and the write-back come first and last, the runs get what remains), each item started in its own process group and the group
  killed when the item returns or at the bound, before the tool's, in a fixed environment (`PATH`, `HOME`, `LANG`, `TMPDIR`, the sentinel
  `GH_TOKEN`, and the builder's git shut-out carried over: `GIT_CONFIG_GLOBAL` and
  `GIT_CONFIG_SYSTEM` at `/dev/null`, `GIT_SSH_COMMAND=false`, `GIT_TERMINAL_PROMPT=0`, no
  `GIT_ASKPASS` or `SSH_ASKPASS`, the builder's `GIT_CONFIG_KEY_n` pairs that empty
  `credential.helper` and `core.askPass` (the review worktree shares the checkout's `.git/config`),
  and `PIP_REQUIRE_VIRTUALENV=1` with `npm_config_prefix` at the worktree, so a bare install
  cannot land in the owner's prefix; an allow-list, not the session's variables minus a deny-list,
  so no `SUPEREGM_APP_KEY` or `SUPEREGM_BUILDER_TOKEN`; pinned by the builder's own test): the
  variables are gone, the filesystem is not (§4.1's residual). A `Run` line that needs
  dependencies installs them into the worktree (a venv or `node_modules` there, never a global
  site-packages) on the same line (whether the builder's allow-list prefix admits a `&&`-chained
  line is the U25 plan's probe; the fallback is `run_commands` returning every segment's first
  word); a line that needs a service the worktree lacks reads `ran
  red`, the plan's defect. After the last run it writes the round's record,
  `foreman/<unit>.json` and the checkout's `.git/config` (the next fetch would honour a helper or
  an `insteadOf` a run wrote there), those three files, back whole from what it read, so an edit a run made to
  them is overwritten (two `collect` calls overlapping on one checkout, the normal batch of several ready heads, can
  re-persist a run's `.git/config` edit between them, and an `insteadOf` or `include.path` no
  `-c` can unset: the overlap is in §4.1's window beside the left-behind process); every other file of the store (`state.json`, `launches/`, a sibling's exit
  file, the journal) stays as a run left it, §4.1's residual, with a process the run leaves
  behind. It records the
  exit code and the summary line under
  `review/<unit>/pr<n>/r<n>/dod/<item>.txt` (`exit: <code>`, `summary: <line>`, `timed_out:
  yes|no`) and in the round's `dod_runs` (§7). An item whose exit is non-zero is a `foreman` high
  `dod-<n>: ran red (<line>)`, one cut by the bound `dod-<n>: ran red (timeout)` (the items after
  it `not run (timeout)`), and an item whose summary line (pytest's; a runner whose output carries no pass or fail
  counts compares on the exit code alone) differs from the builder's paste in its pass or fail
  counts is a high `dod-<n>: paste differs from the run`; the fenced-output check
  stays. A `dod-<n>` high is re-derived every round for that item number until a head turns it
  green or a ruling names it: the owner's `**Ruling:** dod-<n> allowed — <reason>` (§13.2, as
  `test-delta`'s does), or a point-1 overrule of the builder's contest, the judges' or the
  owner's, which persists on the item number too: a line the worktree cannot run (a service, a
  suite longer than the bound) is ruled once, not once per round, and never spends the cap. **The test delta**: for every test file a commit of the PR's range touches (the commit walk of
  the `tdd-order` rule above, so a file created then deleted in the range is among them; a file
  the §9.3 test-file name rule names) that no `Write` line of the unit's own body names (a test the plan set out to rewrite is
  the owner's approved change; the gate guards the files the unit did not plan to touch, and a
  named file's other assertions are the change-review goldfish's to see, a residual; paths
  paired by git's rename
  detection, so a renamed file compares with its old path and a split or merge compares each new
  file with the source of its rename pair), it compares the file at its base (the range's base for a file that exists there: a base
  file's assertions are the baseline, whatever commit removes them; its first appearance in the
  range, the commit that creates it whatever its subject, for a file the range creates;
  `base_commit` in the record) with the head, where a file absent at the head (deleted, or created
  then deleted in the range; a rename is paired above) reads as zero assertions, so every baseline
  assertion counts as removed: every removed or loosened assertion,
  assertions paired across the change as git pairs them (a removed line with the added line at
  its position in the same hunk, the rest unpaired) so a changed value (`== 3` to `== 4`, the
  usual review fix) is never flagged (an `assert`, `pytest.raises` or
  `parametrize` row with no pair at the head; a pair whose `==`, `in` or `raises` turned into
  something weaker; a `def test_` deleted; a `skip` or `xfail` marker added) is a `foreman`
  high `test-delta: <file>:<line> removed | weakened`, recorded in the round's `test_delta` (§7)
  and re-derived every round until a head restores it or the owner's `**Ruling:** <fid> allowed —
  <reason>` (or `finding overruled — <reason>`, read as `allowed`) names it (§8's settle rule): the ruling settles the entry (`file`, `base_commit`,
  `base_line`, the assertion's line at the base, stable while the head's line moves, `kind`), not
  the round's copy, so `collect` skips an allowed entry in later rounds, and
  `**Ruling:** test-delta <file> allowed — <reason>` settles every entry of that file at once. The grammar is pytest's: on a repository whose tests are
  not Python the gate records `test_delta: []`, said in the foreman brief, and CI stays the
  evidence; a `conftest.py`, `addopts` or `testpaths` change that hides tests from every run is
  the change-review goldfish's to see, not the gate's; a body with no `Run` item records `dod_runs: {}`. The word is given only after both
  gates ran, mechanically: `review post` refuses a round whose entry lacks either key (`post:
  gates not run`; empty is not absent), and the foreman brief says so.
  `collect --dispatch <id> --not-run "<reason>"` (EGM's) records a round the
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
  return that is none of those seven words (`owner: <ids>` included, written by `review post`
  before `revise` and, below the cap, before `cap-reached`, since the cap is never spent on it; at
  the cap, `review status` exit 2, `cap-reached` comes first unless the remainder is owner-only, §8) is read as the
  round's `outcome` when the round is
  `posted`, and as `error` otherwise; the elephant records nothing itself, and the next
  `foreman dispatch` supersedes a round left non-terminal.
- It never merges, never approves, never edits the owner's working tree, never removes a
  worktree, never launches a session (the head's Astra lane excepted: one bounded foreground runner
  call, above), never convenes the judges, never infers that a builder died.

**What the elephant does with a word.** `clean`: the unit awaits merge and its slot is refilled.
`revise`: the next builder is launched (its prompt carries the review). `owner: <ids>` (amendment
5): every unsettled high or medium is the owner's alone (§8): `decision open` on each, no
relaunch, no slot, the inbox lists them. `contested`: decision
point 1 (`decision open --point 1`), then the ruling is recorded with `review settle` and
`decision rule` and posted on the issue as `**Ruling:** <fid> finding upheld (fix it) | finding
overruled — <reason>`, and the unit proceeds by `review status` (converged → awaiting merge; at
the cap → as `cap-reached`; else the next builder). `cap-reached`: decision point 2 (`decision
open --point 2`), **one more round** (once; recorded with `review rule` and `decision rule`; the
next builder is launched with the review) or **stop**. At point 1 or 2 on a head a third ruling is **redesign** (§13.2, U18):
`decision rule --unit U<n> --decision <id> --ruling "redesign — <one sentence why>"` records it
(the judges' question file for such a point lists it with the sentence filled, §13.2), and the
unit is stopped as below with a brainstorm brief; in leavemealone-mode (amendment 11, U23) a
judges' `redesign` needs a `high` finding behind it or the owner's confirmation: without a high
`decision rule --by judges:<panel-id>` refuses, so no ruling is written (the panel's answer stays in its record, as an `owner: <ids>` round's does,
§8; the leavemealone table's cap row runs its `review rule stop` only after that call accepts, U23's edit of the row), the decision stays pending, listed by the inbox with the point's own forms (point 1 `<fid>
finding upheld`, `<fid> finding overruled` or `redesign`; point 2 `one more round`, `stop` or
`redesign`, §13.2) and re-convening no panel, and nothing is stopped until the owner's
`**Ruling:**`: the one case of goal 5 and §2's leavemealone row where a converged answer reaches the owner. `error`, `target-moved`: the head is
reviewed again at the next batch, unless `review status --runcard` reports the review stalled
(exit 5), which makes the unit idle. `blocked` (a `BLOCKED` or `NEEDS_CONTEXT` status, a builder
exit with no PR, an interrupted launch, a stalled launch (amendment 10, with its stall facts:
the minutes, the last commit time or none), a `closed` by the builder account, or a third
`blocked` on one unit without an intervening head): decision point 3 (`decision open --point 3`), whose
ruling is recorded with `decision rule` and posted on the issue as `**Ruling:** (<comment-id>)
<option> — <reason>` quoting the question, then the next builder or `stop`; for an exit with no
PR, an interrupted launch, a stalled launch, a builder's `closed` or a third `blocked` the
options are `relaunch`, offered once per unit, and `stop the unit`, and once `relaunch` has been
used the case is `stop` without a question; a launch with no commit of its own spends no
relaunch, whether it exited with no PR or stalled, and a second such launch on one unit is
`stop` (amendment 10's one rule for both cases). A by-hand `**Ruling:**` is honoured at every decision point of a unit from a
login in `config.owners` and from no one else, in §13.2's one grammar (the owner's one `**Ruling:** (<comment-id>) <option> — <reason>` naming
the builder's one `BLOCKED` status comment that folded several `**Deviation**` headings under one option list rules each of them with that option, `collect` reading every heading, amendment 11, U22; amendment 5; 1.0.0
honoured any non-builder author, and only on a BLOCKED comment, a deviation or a `tdd-order`
finding): the wave reads it as a `ruling` event and records it with `decision rule --by
<login>`. `stop` (from any ruling or from the owner's by-hand close): the issue is labelled
`superegm:stopped`, kept open unless the owner closed it, the branch kept, the unit never
relaunched; it is listed in the wave report with its unlanded dependants; the owner lands it by
hand or closes it with those dependants and re-appends what is still wanted (§12). A `redesign`
ruling is `stop` by the same path, all through the helper, plus: the store gains
`foreman/<unit>-<decision id>.brainstorm.md` (the finding(s) verbatim, the unit body, whose `Spec:` line cites the
range (the text is read at that sha by the brainstorm, §11's content read; the brief copies no
range), the head's `r<n>/diff` summary (the changed paths and the first 200 lines of the diff,
the whole diff when under 40 KB), the deviations posted on the issue, and one line "what the
owner asked": the ruling sentence), store-only and never committed (the plugin scans no content,
above: a secret the diff carries is on the PR already, where the owner's eyes met it); the
`**Ruling:**` comment on the issue says the unit is stopped for redesign and names the brief;
`report` lists it under `## Stopped` with the brief's path, and `integrate` refuses to close the
handoff while its issue is open (§12). The road back is existing
phases only, each typed and nothing chained (§5): the next elephant session runs
`/superegm:brainstorming` from that brief (the skill's dispatcher text says: when any open handoff's `foreman/` holds a brainstorm brief
for a unit stopped for redesign whose issue is still open, start from it, naming the handoff; a
brief whose issue is closed is left in place and never offered); the outcome is
the amended spec at a new hash (`approve-spec --amend-units`, under its own card, when only `## Units` rows change
and the unit's handoff is the latest; the rows appended in the latest handoff's worktree when
it is not, §12; a scoped spec review when more changes, §5), then `plan` for the amended or new units, `review-plan` and
`file`, which files the re-planned unit, a new `## Units` row with a new id (the stopped id
stays frozen in its handoff), as a new issue (§10's adopt path is not used: a stopped unit's
issue carries `superegm:` labels and a `**Ruling:**` comment, which `dry-run` refuses);
the owner closes the stopped issue by hand, as the `**Ruling:**` comment asks (the plugin edits
no issue it did not file in this handoff); then the wave relaunches.

**Landing.** A unit has landed when its watched PR is merged into `<base>` and its issue is
closed as completed, whoever closed it. Landing makes dependants ready. `/superegm:clean --unit
U07` (EGM's `prepare --clean` looped over the unit's review rounds, plus the removal of every
builder worktree whose launches are all terminal, dirty or not: the typed skill is the owner's
decision; from amendment 5 a review worktree whose rounds are all terminal is removed whatever
its tree holds too, since a DoD `Run` line may install into it, §11) is typed, `destructive-local`,
refuses while any launch or round is not terminal, and keeps what it cannot prove.
`/superegm:interrupt --unit U07 (--launch <n> | --round <n>)` is typed and records
`interrupted` on a launch, or marks a prepared round `collected (not run (interrupted: owner))`;
an owner's decision is not a guess.

### 11.2 The fleet layer

Amendment 5 (U21–U25). The wave of §11.1 needs an owner in the room: to read what a reviewer
outside the plugin wrote on a PR, to rule, to type the next `wave`. The fleet layer removes the
room and keeps the owner: every external review is ingested as findings (§8), every ruling can be
one comment from a phone, the inbox lists what needs the owner and nothing else, a hook tells
them, and a timer on their machine re-types `wave`. Merge stays human (goal 6); nothing here
approves, merges or chains a phase (§3).

**One ruling grammar.** `decision.ruling_of(comment, owners) -> Ruling | None` is the one parser
(anti-goal 1), used by `status --wait` for the `ruling` event, by `collect` for deviations,
`tdd-order`, `dod-<n>` and `test-delta` (beside the `rulings[]` entries recorded `--by judges:<panel>`, which `collect`
honours as it honours the owner's comment: the judges' posted copy carries the panel marker the
parser skips, §13.2), and by `decision rule --by <login>` for the record. A comment is a ruling only when
its author's login is in `config.owners` and its body matches one of §13.2's forms exactly;
anything else is text. GitHub's author field is the authentication; there is no token in the
comment (it would make a phone ruling harder and guard against little the login check misses).
The orders quote the forms a builder may see on its issue.

**The inbox.** `superegm inbox [--all] [--json] [--handoff <id>]` is read-only and needs no run
card, as `doctor` is; `skills/inbox/SKILL.md` (`effects: none`) is auto-invokable, with `doctor`'s
line in `using-superegm`. Without `--all` it reads the current repository's store, every open
handoff of its `handoffs/` index (§7) unless `--handoff` names one; `--all` reads every store
the registry lists (`registry: none`, and the one store, while nothing is registered). It lists
only what needs the owner: open decision points (`decisions[]` without a `rulings[]` entry), cap
rulings (`review status` exit 2 with no `stop` ruled), contested findings (point 1 pending), merge-ready PRs (the
latest round's `outcome: clean`), stalled units (exit 5), a `running` launch recorded `kill_failed`
(amendment 10, §11: the line carries the reason and, for `no exit file` alone, the recorded pid, the group id the owner
signals as a group and whose leader may be gone already, as `driver status` prints a tick launch's, and the action is the owner's `/superegm:interrupt --unit <U> --launch <n>` once they
have ended the process, then a re-typed `wave`, whose Entry raises point 3 for an `interrupted`
launch with no decision on it, from `launches[].status` (U31; an `interrupted` launch wakes no tick)), escalations
(`approvals/<slug>.json.escalated[]` awaiting the owner; an integrate round's `escalated`
findings), units stopped for redesign with their brief's path (§13.2's `redesign` ruling),
`test-delta` findings from the round that records them (the owner's alone, §8: the action is the
`**Ruling:** <fid> allowed — <reason>` form), a handoff whose last tick refused (§11.2: a repeating failure, a bad `root`; the action is
`driver status`, for the owner's re-typed `wave` or `driver reset`), the
owner-only findings a unit waits on (`owner: <ids>`, §8) and the driver's `stale` state
(`doctor`'s line, §11.2); a finding on the spec PR (amendment 6, §8) is the spec review's own,
settled in the session or by the judges, and never an inbox item. As information, never an action: an open `wave` card, typed or a tick's, and a tick launch
without an exit file, each with its age (`driver status` shows them; `notify` sends each once,
its fingerprint the card's or launch's id without the age, so a tick that crashed at the first
tick of the night is seen and a healthy night costs one line per launch). Never:
builders running (a `kill_failed` launch excepted, above), rounds in progress, heads waiting on CI, lows, or the judges' converged
rulings, which stay in the journal and the posted `**Ruling:**` comments (§13.2); the feed
carries the unconverged alone. One line per item, `<repo> <unit or review> | <kind> | <action>`,
the action being the exact comment to post (§13.2's form, copyable from a phone, with the
issue's URL), the command to type, or the PR's URL to merge.

**The notify hook.** `~/.superegm/notify`, an executable the owner writes outside every
repository (absent means no hook; a command line in the committed config would let any commit
that reaches `<base>` choose what runs as the owner), is run by `wave`, typed or timer-typed,
after each batch's `report`, and by a tick with inbox lines new since its last (below), through `superegm notify
--runcard <id>`: it computes the card's handoff's inbox lines (`inbox --handoff <id>`) new since both of that
handoff's `notified` sets (the line fingerprints: a line is new when neither holds it) and
writes its caller's set alone
(`state.json.notified` under a `wave` card, `driver/<handoff>.json.notified` under a `driver`
card, so a tick never writes the file a live session may hold), writes them to the hook's
stdin, waits `config.notify_timeout_seconds` (30, a
number: it runs no code), journals the exit code and updates `notified` whatever the exit (a failing hook is the owner's to
fix; the lines stay in the inbox, never re-sent); a failing or slow hook never stops the wave. The hook runs under the caller's run card as one more of that invocation's
effects (anti-goal 4); `inbox` typed alone prints and never notifies. The lines carry unit ids,
forms and URLs, never a token or a diff. The owner's script runs with the owner's environment,
bounded by the timeout.

**The registry.** `~/.superegm/registry.json` lives outside every store and is written by the
helper alone (§7's rule extended): `superegm register [--remove] --runcard <id>`, typed from a
repository through `/superegm:driver register`, adds `{repo, root, artifacts_dir}`
for the current store, or removes it; `inbox --all` and the driver read it. Unknown keys stop. An
entry is keyed on `artifacts_dir`: two worktrees of one repository share the committed store, so
`register` from another worktree of a listed store updates its `root` (journaled `registry:
<store> root <old> → <new>`), never adds a second entry, and the entry's `root` is the one checkout a
tick's sessions run in, every handoff of the store's: the latest `register` names it (§5's one
worktree per handoff moves it when a handoff is filed). It is a list of stores, not a graph: a store's handoffs are its own index's (§7), and a prerequisite
in another repository is prose and `Landed:` rows in the second spec (§9.1, §17), typed by the
owner after the first lands; no `Repo:` field and no cross-store `Blocked by` exist.

**The driver.** It runs on the owner's machine and nowhere else: a fleet box is a second exposure
story nobody priced, and the owner's login never leaves the machine. `/superegm:driver install |
uninstall | status | register | reset` is typed (`effects: external`, kinds `start-session,
state-store`: the plist and the registry are `state-store` writes by §7's extension, outside the
working tree; its card's artifact is the U24 plan's to name under §6's rule). `install [--interval <minutes>]` (15; the machine's, never a
repository's key) writes a launchd agent (`~/Library/LaunchAgents/com.superegm.driver.plist`; on
Linux a systemd user timer, which needs `loginctl enable-linger`, a by-hand step the skill names)
that runs `superegm driver tick` through the absolute interpreter and the installed plugin root
it names (`ProgramArguments`: the root installed under the env file's `CLAUDE_CONFIG_DIR`
profile, the one the session's own helper calls resolve to), bootstrapped at once (`launchctl bootstrap gui/<uid>`), so `install`
is re-typed after every plugin update (the root is versioned: §5's new-session rule, one line more).
A timer has no shell: the tick reads `~/.superegm/env`, `KEY=value` lines the owner writes (mode
0600): `PATH` (where `claude`, `gh`, `python3.12` and `openssl` resolve), `CLAUDE_CONFIG_DIR` (the
profile the session runs under: one without SubagentStart hooks, §4's rule for reviews, which
`doctor`'s `env:` line reports) and the credential the owner's shell holds today, `SUPEREGM_APP_KEY` (a path; the App is the driver's credential of
choice) or `SUPEREGM_BUILDER_TOKEN` (a token there is §4.1's residual, the same the shell holds);
the session and the notify hook run in that environment, and the plist carries no secret and no
environment of its own. `uninstall` removes the agent; `doctor` prints `driver: installed
(<interval>) at <root> | stale (<plist root>; the env profile's root <root>) | not installed`, `sleep: <pmset
setting>`, `root: ok | not a worktree of <repo>` and `env: ok | missing <key> | readable by
others` as information. A tick types one phase and chains nothing (§3): for each open handoff
of each registered store with a filed unit that is neither landed nor stopped (a handoff with no
launch yet included), and whose previous tick launch has an exit file, it opens a `driver` card,
records the launch in `driver/<handoff>.json` before starting it (`launches[]` with `started_at`,
`exit_file`, `status`, as `launches/` has them, §7: the list before the first write, as `apply`,
§4.1, so a tick that crashes between the two leaves a launch without an exit file, which the next
tick skips and `driver status` shows, below), launches `claude -p` with
`/superegm:wave <spec> --handoff <id> --leavemealone` (the typed skills' form, §7) in the
repository root under the profile the env file names, with
`SUPEREGM_ROLE=driver` (a third role value: the hook prints its text for it, as for any role but
`goldfish` and `builder`, §6), in its own session and process group (the wrapper below, Python's
`start_new_session=True`; the plist sets `AbandonProcessGroup`, the systemd unit
`KillMode=process`, so the supervisor's reaping of the exited tick leaves the session alive; the
U24 plan pins both keys by a test), and closes the card: the session is that card's one effect,
and the wave it types opens its own. A tick launches nothing when there is nothing to do: before
the launch it runs one read (`status`, no `--wait`, saving no fingerprint, so the next session's
first `status --wait` still reports every event; from amendment 10 the read counts the watchdog predicate over the running launches as a
trigger, kills nothing and renders no board: the session it launches kills and renders at its first pass, §11.1, U31;
extended for the tick to count the review threads not in
`ingested[]` on the latest posted round's head of each open PR (the ones U21's reader would record above `low`, by that
reader and no restated rule, §8; a thread on a later head waits for that
head's round, a stranger's buys no session) and the CI state of each idle head,
`status.py`) and, when the
previous session ended with every unit clean, landed, stopped, idle or pending and no event of the
seven kinds, un-ingested thread or idle head's CI conclusion is newer than that session's last
fingerprint (a comment that makes no event is no trigger: a public repository's stranger buys no
session), it writes nothing (no card, no journal line, no store write: anti-goal 4; `driver status` derives
idleness from the last launch's exit file) and ends (a stalled unit
is idle: the owner's re-typed `wave`, a new run card, is its one retry, §8; a tick's session is
no such retry: its dispatch predicate reads the stall through `review status --runcard <id>` with the
handoff's `wave` cards since the last posted round as the card set, U24's form in `review.py`); a tick that launches costs one
session, one that finds nothing costs one read. The tick and `launch-builder` (below) are the two helper calls that start a session
themselves, the tick having no elephant to hand the command line to;
the permission mode and allow-list it passes are the U24 plan's, pinned by a test that a tick's
session never prompts; whether `claude -p` expands a prompt beginning `/superegm:wave` as the
owner's typed command is the U24 plan's first probe (§4 records no such fact; `wave` is
`disable-model-invocation`, so the `Skill` tool is no route), the fallback being the skill's body
passed as the prompt; the second probe is the Agent tool under `claude -p` (the session's
foremen and their goldfish, §11.1), with no fallback: a head is reviewed by a typed `wave` until
it passes. The session ends when the loop ends (§11.1: every unit clean, landed,
stopped, pending or idle); its exit file is the shell wrapper's, written
on any exit as a builder's is (§4), the wrapper being the process the tick detaches, and its
result file is named in `driver/<handoff>.json` as `launches/` names a builder's (§7). It never types
`integrate`, `plan`, `review-plan` or `file`. Under `SUPEREGM_ROLE=driver` the `wave` skill never
asks: a decision the judges did not converge on is a journal line and an inbox line, and its unit
is `pending a decision` (no slot: from amendment 5 `launch` excludes a unit with a pending
decision from the in-flight count, `launch.py`, U24's) while the batch goes on; the session ends on §11.1's condition
alone, and the next tick resumes the rest. Liveness is never guessed (anti-goal 8): a tick
launches a handoff only when no handoff of the store has an open `wave` card or a launch of its
own without an exit file (the one `.git`, §9.3) and that handoff has no open `plan`, `file`,
`integrate`, `review-plan` or `orient` card (its own `state.json`, §7; another handoff's typed
phases run beside a tick's session, the parallel case §7's approval chain allows); otherwise it
skips, silently, as below. A `wave` card opened under
`SUPEREGM_ROLE=driver` records its driver card (`SUPEREGM_RUNCARD`, §4); a typed `wave`'s card,
live or dead, is the owner's, shown by `driver status` and the inbox with its age (information,
sent by `notify` once, by its id) and cleared by the owner's re-typed `wave`, by `driver reset`, or by the boot-id proof on its
recorded id (below). A launch of its own
whose exit file exists while its `wave` card is still open is a session that ended without
closing its card (an API error, a turn limit): the exit file is the proof, and the tick marks
that card, and no other, `interrupted` as the `wave` skill starting again would (§6) and
launches. A launch of its own without an exit file is the normal state of a live overnight
session and is never reasoned about: the tick skips it (no journal line), and `driver status`
and the inbox show it as information with its age, which `notify` sends once by the launch's id
(the age is not in the fingerprint); a tick runs `notify`
only when `notify`'s own predicate holds (a line neither `notified` set holds, above; each
`notify` rewrites its caller's set as every current line's fingerprint, sent now or before, so a
persistent line is never re-sent; a fingerprint carries the round or decision it names, so a
line that recurs after a later round is new), under a `driver` card it opens for that alone. One proof is allowed,
since no process survives a reboot: every launch and every `wave` card records the machine's boot
id at its start (`kern.bootsessionuuid`; `/proc/sys/kernel/random/boot_id`; never the boot time,
which a clock step moves), and a launch whose recorded id is not the current one is recorded
`interrupted (reboot)`, journaled, its open `wave` card marked `interrupted` as the exit-file
proof marks one (a typed `wave`'s card too, by its own recorded id, §7), and the tick launches; the same proof, applied by the tick before it launches, and by `launch-builder`'s
terminal check and `runcard open`'s refusal when the owner types `wave` first after a reboot
(one `sysctl`, no by-hand interrupt), records the builders that session had in flight (`launches/<unit>.json`: no exit file, a boot id not the current one)
`interrupted (reboot)` too, so `launch-builder`'s terminal check passes and the new session
relaunches them with no decision (§4's terminal rule, one more proof beside the exit file; not
§11.1's point-3 interrupted launch, whose `relaunch` is the owner's once per unit). Two consecutive launches of its own that failed before the loop ran, read from
`driver/<handoff>.json`'s own record (a non-zero exit, no `wave` card opened, or a card closed
or left open before its first `report` or `status --wait`: an expired login, a spent quota, a
`launch` refusal, an outage; a session that read a new comment, found nothing to do and
reported is not one, nor a long session the tick marked after hours of rounds), are a failure
that repeats: the tick refuses until
the owner's re-typed `wave` (a later typed `wave` card that reached `report`, read from
`runcards/`, is the intervening success) or `driver reset`, so a night never pays 96 sessions to one failure.
The refusal, journaled `tick: refused (<handoff>: <reason>)` and carried by `notify`, is for a
repeating failure and a registered `root` that is not a worktree of the store's repository
alone. A store runs one session at a time (two waves would fetch into
one `.git`'s `refs/superegm/base`, §9.3): a second handoff waits its turn, a silent skip like
the live launch above, never a refusal or an inbox action, and the next free tick serves the
handoff that has waited longest. `driver status`
prints, per handoff, the last launch, its
`started_at`, the wrapper's `pid` (a kill target, never a liveness guess), whether its exit file exists, the open `wave` card's id and age, and the last
refusal; the owner's typed `/superegm:driver reset` is the interrupt for a launch the owner knows
is dead (a reboot, a kill), never a timeout and never an inbox action: it records the launch
`interrupted` and marks the handoff's open `wave` card
`interrupted` (§7's writer row for `runcards/` names both). The same rule binds a typed `wave`:
outside `SUPEREGM_ROLE=driver`, `runcard open` for `wave` refuses, marking the card it wrote `interrupted` (below),
while any handoff of the store has a tick launch without an exit file in its
`driver/<handoff>.json` (the one `.git`'s `refs/superegm/base`, §9.3), and for `plan`, `file`,
`integrate` and `review-plan` (a typed `/superegm:orient` the same way) while that handoff's own
tick launch has none (its `state.json`, §7; another handoff's are free), with the one message
`driver: a tick's session may be live; /superegm:driver reset is the owner's interrupt`, so a
store never has two waves and a handoff never two writers, but for the window between one side's
read and its write (no lock, §3.1): the tick records its launch before it reads for a card and
`runcard open` writes its card before it reads for a launch, so a collision leaves each side's
mark for the other to see at its next step, and the side that then finds the other's mark backs off: the tick marks its own launch
`interrupted` and ends, `runcard open` marks its own card `interrupted` and refuses (an
`interrupted` launch or card is terminal for every predicate above, as §4 says of a builder's);
the residual is one wasted session. A
tick runs `superegm notify --runcard <driver card>` itself when it has new lines (a refusal, a
launch without an exit file, a typed `wave` card, a stale root), so the inbox's driver line reaches the hook. Builders launched by a tick's session are started in their own session
and process group: `launch-builder` (from amendment 10 its one behaviour; amendment 5's
`--start` flag on U09's interface, since gone) starts the wrapper itself, detached (Python's `start_new_session=True`, never `setsid(1)`, which macOS
lacks; stdin from `/dev/null`, stdout and stderr into the launch's log file, so the tool's pipe is
not held open for the builder's hours), and returns at once, the session's Bash tool calling it
in place of the wrapper; the detached
process is the shell wrapper that writes the exit file (§4), never `claude -p` alone; pinned by a
test, since a `claude -p` session ends when its loop ends and its builders must not (§4). The driver never
merges: the inbox lists merge-ready PRs. `notify` runs inside the tick's wave.

## 12. Merge and integration (phases 6–7)

- **Merge is human.** The absorbed `finishing-a-development-branch` offers two options: push and
  open a pull request as the owner, for a colleague's review (the owner's own branches need no
  PR: only the owner updates `<base>`); keep the branch as-is. Discard stays behind the typed
  word `discard`. "Merge back locally" is removed. A forced push is never offered.
- `/superegm:integrate <spec-path>` runs after every unit has landed, has its PR merged with its issue still open (`close`'s to close, amendment 11) or been closed by the owner
  (who closes a stopped unit's unlanded dependants with it): one round of the review
  `spec-<spec-slug>-integrate-c<n>` (kind `integrate`, `config.reviewers.integrate`) of the
  frozen spec against the handoff's own merged PRs' diffs (`gh pr diff <n>` for each, concatenated
  by the skill; `<base_at_start>..<base>` stays the record of the window), so another handoff's
  hunks, on shared files included, are never in the round. Each high or medium is settled
  `escalated` with a new unit's id: the elephant appends rows to the spec's `## Units` with the
  note `(from integrate, review <id>)`, runs `superegm approve-spec --amend-units` (which
  re-records the spec's latest approval at the new bytes without a review round, keeps that
  handoff's id and refuses if any line outside `## Units` changed); for a handoff that is not
  the latest (§7) `integrate`, typed in that handoff's worktree, records the round's ids
  `escalated` with the note `(to the latest handoff)` and closes the handoff (nothing is
  escalated into itself: one round and a close, under its own card and on its own branch); the
  owner then, in the latest handoff's worktree, appends the rows with the same note and runs
  `approve-spec --amend-units` there (a second typed step, §5: no skill switches branches;
  typed outside a skill, `--amend-units` opens and closes its own card, `approve-spec-<6
  hex>-<n>`, as the by-hand re-append path below always did); the owner pushes it (§5) and then types `plan`
  → `review-plan` → `file` → `wave` for the new units only. The owner uses the same path by hand
  to re-append what a stopped unit still owed. `report` lists a unit stopped for redesign (§11)
  under `## Stopped` with its brief's path, and `superegm close` (`--close` included) refuses
  while such a unit's issue is open, read once from GitHub at `close` (`gh api` under the
  elephant's token, a read in §2's sense; the owner closes it by hand once the re-planned unit
  is filed, §11) and journaled with the read's answer (U18). The handoff closes (`superegm close`, which writes
  `closed_at` and, from amendment 11, closes any unit issue whose PR merged while it stayed open (the unit then landed; the round path's gate admits such a unit,
amendment 11, so the clause serves it and `--close` alike; a unit the owner closed unmerged leaves the tracking issue open on either path)
and, when every unit then landed, the tracking issue as completed, the one issue no PR closes,
journaling each; with units unlanded the tracking issue stays open to the owner, who is closing
the stopped issues by hand already (a give-up's usual end: the condition's consequence, not a
rule of `--close`); a `github-write` of `integrate` (§14), takes `--note <text>` into the journal as `runcard close
--note` (U32's too) does, U32; `/superegm:integrate --close --patch`, the owner's typed statement that the
handoff is a patch release, runs `close --note "patch release"` without the integrate round, the
note the reason, no helper flag and no release plan: the owner's word is the source, U32) when an integrate round has nothing to escalate. `/superegm:integrate --close` is
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
  --round <n> --judge <id> --verdict <file> --isolation …`. A verdict file may close (as the judge persona asks) or open with the
  `saw: <isolation note>` line: the parser skips it wherever it stands and `judges record`
  stores its text as the judge's `saw` beside the validated `--isolation`, which stays required
  and is the record; blank lines before the first `Q<n>` are ignored, as they are today.
- The question file's grammar: `## Q<n> <question>` followed by two or more `- (a) <option>`
  lines; a file may hold several questions; judges answer each by option id and may add a short
  reason and "what would change my mind". `superegm judges diff --panel <id> --round <n>`
  compares option ids and writes the neutral list of where positions differ; no one adds
  arguments between rounds.
- Three models from two vendors, each a goldfish through the `superegm:judge` adapter
  (`omitClaudeMd: true`, tools `[Read, Grep, Glob]`, `model: inherit`) with a per-dispatch model and effort
  override read per judge from the panel file `judges open` writes (`judges/<id>/panel.json`,
  each member of `config.judges.members` resolved there by `judge_members` once; amendment 8:
  `fable` at `xhigh`, `opus` at `max`; an adapter member's `model`, when set, is the Agent tool's
  alias; a runner member's `effort` is the source, the landed fallback to `astra.effort` serving a
  member without one; the dispatch takes the effective pair as §8's one rule gives every
  goldfish, `CLAUDE_CODE_EFFORT_LEVEL`'s and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`'s overrides read
  and said in the record, pointed at and not restated; the session pair `SUPEREGM_GOLDFISH_MODEL`
  and `SUPEREGM_GOLDFISH_EFFORT` stops at the review panels), plus
  GPT-6 Astra through the claudex-loop runner's `review` mode on the question file at the
  member's own effort (`xhigh`) when the runner is installed and reachable, recorded `not run`
  otherwise.
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
   `contested` reply on a PR head and a contested external finding (§8) (options: `finding upheld`,
   `finding overruled`, and on a head `redesign — <one sentence why>`, as at point 2, the sentence
   the owner's when typed or ruled by comment and, in a judges' question file, filled by `judges
   question` (the finding's claim at point 1; at point 2 `the head is at its cap after <n> rounds`
   with the unsettled findings' claims); the
   elephant's or the builder's reason is copied verbatim as the overrule option's text; every
   such finding of a round is one question of one panel; the CI finding is never one, and a
   `test-delta` finding (§11) is the owner's alone: the judges never settle it, so in
   leavemealone-mode the unit waits `pending a decision` on it, §8, never a cap round);
2. a review at its cap: for a spec, plan or integrate review, continue one bounded round (once)
   / accept the remainder (not while the latest completed round's bytes moved, §8) / stop, and
   `stop` alone, ruled by the helper, whenever `accept` and `continue` are both refused (§8), the
   question naming a spec review's scope (§8); for a head, one more round (once) / stop /
   `redesign — <one sentence why>`, the last also an option at point 1 on a head, recorded by
   `decision rule` and with §11's effect
   (the unit stopped with a brainstorm brief; U18);
3. an open question the elephant cannot answer from the frozen spec: a `blocking: yes` decision
   during `plan` (the options are the item's own); a builder's `BLOCKED` / `NEEDS_CONTEXT`
   status (the comment's own `- (a)` lines, plus `stop the unit`); a builder exit with no PR, an
   interrupted launch, a stalled launch (amendment 10, §11), a `closed` by the builder account,
   or a third `blocked` without an intervening head (`relaunch`, offered once per unit, a launch
   with no commit of its own spending none, §11's rule; `stop the unit`);
4. the owner's approval of a converged spec in normal mode, and "Create" in normal mode.

In normal mode every point pauses for the owner. In leavemealone-mode (`--leavemealone` or
`config.mode`), at points 1–3 the skill runs `superegm judges question (--review <id> --round <n>
[--reason <fid>=<text>]… | --review <id> --cap | --unit <U> --decision D<n> | --unit <U>
--blocked (<comment-id> | launch <n> | closed <n>)) → <path>` to render the question file from
the record with the options named above, one panel per review round, runs `judges open --parent
<its run card>`, dispatches the judges as §13.1 says, and applies each converged answer (subject
to `min_vendors`; a `redesign` with no high finding behind it excepted, amendment 11, §11) through `review settle --judges`, `review rule --judges`, `decide --judges`,
or `decision rule --by judges:<panel-id>` and a `**Ruling:**` comment the skill posts with `gh
issue comment` under the elephant's token, journaled as `Ruling (judges <id>, leavemealone): …`
so the owner can read and overturn it; the unconverged questions pause the owner with the
record. A ruling that chooses a deviation of kind `interface` is also posted as `**Ruling:**` on
every filed issue whose body consumes that name (`consumes`, §9.1). Point 4 is mechanical in
leavemealone-mode (§8, §10). A foreman never convenes the judges; the elephant does. **Merge is
excluded**: no mode makes a machine approve or merge.

**Rulings by comment** (amendment 5, U22). At points 1–3 of a unit, and on a deviation, a
`tdd-order`, a `test-delta` or a `dod-<n>` finding, the owner may rule from anywhere by one comment on the
unit's issue, in these forms and no other (the one grammar, §11.2): point 1 `**Ruling:** <fid>
finding upheld` | `**Ruling:** <fid> finding overruled — <reason>`; point 2, a head,
`**Ruling:** one more round` | `**Ruling:** stop`; point 3, and a deviation, whose own lines are its options (§10), `**Ruling:** (<comment-id>)
<option> — <reason>` (a point-3 decision opened on a launch or a close, with no comment, takes
the id `decision open` printed, the one the inbox line carries, in the parenthesis:
`**Ruling:** (<decision id>) <option> — <reason>`); `tdd-order`,
`test-delta` and `dod-<n>` `**Ruling:** <fid> allowed — <reason>` (a point-1 `finding overruled` on
such a fid is read as `allowed`; the `dod-<n>` one keyed on
the item number and the `test-delta` one on its entry, both persisting across rounds;
`**Ruling:** test-delta <file> allowed — <reason>` for a whole file); the `redesign` ruling (amendment 4)
`**Ruling:** redesign — <reason>`, read at a head's points 1 and 2 alone (§11: the brief needs
the head's diff), where it rules every open decision of the unit at once (the unit stops); at
point 3 it is text, and the inbox shows the decision still open. A comment is a ruling only when its author's login is in
`config.owners` and its body matches one form exactly; a trailing word makes it text, so a typo
is silence, which the inbox (§11.2) shows as the still-open decision. The wave applies it as the
point's own subcommand says (§11) and the record is the one a ruling typed in the session
leaves. Spec and plan reviews have no issue: their cap rulings stay typed. In leavemealone-mode
the judges' converged rulings are posted in the same form under the elephant's token (above),
where the owner reads them, after the record and with the journal's `judges <panel>` marker in
the text, which `ruling_of` skips, so a wave never records the panel's post as the owner's; a
recorded ruling is never changed by a later comment (§11), and the inbox lists only what nobody
has ruled.

## 14. Skill and adapter disposition

Naming: adapter file `.claude-plugin/agents/<id>.md`, frontmatter `name: <id>`, persona
`agents/<id>.md`, invoked `superegm:<id>`, reviewer list entry `<id>`.

| Source | In SuperEGM as | Effects | Invocation | Caller | Change |
| --- | --- | --- | --- | --- | --- |
| brainstorming (sp) | `brainstorming` | working-tree | auto | owner, phase 0 | writes `docs/specs/YYYY-MM-DD-<topic>-design.md` (path changed from `docs/superpowers/specs/`) ending in `## Units`; the gate's next step is `/superegm:review-spec`; the builder check and the visual companion removed |
| egm-draft (egm) | `draft` | working-tree | typed | owner, phase 0 | "draft a spec from a brief when brainstorming was skipped"; template ends in `## Units` |
| egm-review + egm-review-loop + egm-resolve (egm) | `review-spec` (+ `references/review_loop.md`, `references/resolve.md`) | external: state-store, start-session, github-write, remote-branch (amendment 6: the preflight's PR, the `**Reply <fid>:** fixed` post of `review ingest --pr`, and the push of the elephant's branch after each fix commit and the approval commit) | typed | owner, phase 1 | §8; the stage skills become references; "max 1 re-audit" goes; owns the Astra review lane on specs (the foreman runs it on heads, §11) |
| new | `orient` | external: state-store | typed (and run by `plan`, `review-plan` and `launch-builder`) | elephant, before planning on an existing repository; the readiness goldfish and every builder through its callers | §9.3; `orient/map.md`, `orient/<unit>.md` in the store |
| egm-handoff planning half + writing-plans (sp) | `plan` | external: state-store, start-session, github-write | typed | owner, phase 2 | §9.1; `github-write` for the decision comment on a filed unit |
| new | `review-plan` | external: state-store, start-session | typed | owner, phase 3 | §9.2 |
| egm-handoff filing half | `file` | external: github-write, state-store | typed | owner, phase 4 | §10 |
| egm-wave + SDD implementer prompt (sp) | `wave` (+ `references/foreman_brief.md`, `references/builder_orders.md`) | external: start-session, github-write, remote-branch, state-store, destructive-local (amendment 10: the watchdog's kill, U31) | typed | owner, phase 5 | §11; the head panel: Claude goldfish and, from amendment 4, the Astra lane run by the foreman |
| new | `interrupt` | external: state-store | typed | owner, phase 5 | §11 |
| new | `clean` | external: destructive-local, state-store | typed | owner, phase 5 | §11 |
| new | `inbox` | none | auto | owner, any time; `wave` through `notify` | §11.2; reads the store(s), no run card, as `doctor` |
| new | `driver` | external: start-session, state-store | typed | owner, once per machine and after every plugin update (`install`), once per store (`register`); the timer it installs | §11.2; `register`, `driver tick\|install\|uninstall\|status\|reset` |
| finishing-a-development-branch (sp) | same name | external: github-write, remote-branch, state-store | typed | owner, outside a wave | no local merge, no forced push; the PR as the owner |
| new | `integrate` | external: state-store, start-session, github-write (amendment 11: `close`'s issue closes, U32) | typed | owner, phase 7 | §12; `--close` |
| new | `judges` | external: start-session, state-store, github-write | typed | owner (leavemealone skills call the `judges` helper subcommands directly) | §13 |
| test-driven-development, systematic-debugging, verification-before-completion (sp) | same names | working-tree | auto, phase-gated | owner fixes on a filed unit's branch (a builder invokes only the skills its `Skill` rules name, amendment 7; this repository lists ponytail alone, §17; the orders carry the discipline) | the phase sentence |
| writing-skills (sp) | same name | working-tree | auto | owner, maintaining this plugin | |
| using-superpowers (sp) | `using-superegm` | none | hook + auto | every elephant session (a builder loads the plugins `config.builder.plugins` names, amendment 7; this repository lists ponytail alone, §17) | the dispatcher text; one platform reference |
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
  `superpowers@claude-plugins-official` first; to create the builder account, its token and a
  builder profile that is the login alone, `syncClaudeAiPlugins` false and
  `disableClaudeAiConnectors` true set before the login (step 1 is the token recipe of §11; the
  plugins `config.builder.plugins` names are installed once into the elephant profile (§7) and
  disabled there (`enabledPlugins` false in its `settings.json`, which keeps the entry and the
  cache directory), where the launch resolves them, amendment 7; `owner_team` is documented in
  `docs/getting_started.md`); to set the branch protection of §11 (updates to the
  base branch restricted to the owner with no bypass for the builder account; `superegm/**`
  protected from force-push and deletion) and a workflow triggered on `pull_request`; to run
  `superegm doctor` before the first wave; and to run reviews from a profile without
  SubagentStart hooks.

## 16. What is left to the builder

- The helper's argparse surface beyond the names and contracts in §17: `init`, `runcard
  open|close`, `approve-spec [--amend-units | --void | --leavemealone]`, `graph`, `scan`, `orient`, `doctor`,
  `review open|record|settle|status|rule|post|ingest`, `review-plan due|set-input|proportion-input`,
  `gate`, `dry-run`, `apply`, `verify`, `status [--wait]`, `launch [--idle]`, `launch-builder`, `record-launch [--exit]`, `foreman dispatch`,
  `collect [--not-run]`, `prepare`, `tdd-order`, `decide`, `decision open|rule`, `interrupt`,
  `clean`, `report`, `close`, `judges open|diff|record|verdict|question`, `builder-token
  [--repo] [--app-id --key-env]`, `inbox [--all] [--json] [--handoff]`, `notify`, `register
  [--remove]`, `driver tick|install|uninstall|status|reset`.
- The hook script's exact text, as long as it carries the dispatcher rule and the phase rule.
- Journal line formats, as long as every line is written by the subcommand that wrote the fact.
- The judge persona's wording.
- Every mechanism §11 names as the plans' content: the event grammar's line form, the batch
  order, the folding, the retries, the resume derivation, the prompt file's assembly, the
  protection reads' field forms.

## 17. Units

The unit graph for building SuperEGM 1.0.0 (thirteen units), from amendment 2, 1.1.0 (U12–U14) and, from amendment 3, 1.1.1 (U15–U16) and, from amendment 4, 1.1.2 (U17–U20) and, from amendments 5–11, 1.2 (U21–U32). Each unit's plan must fit 48 KB.
Interfaces are subcommand contracts and file keys unless marked `py`. A Consumes producer may be
a transitive blocker. After U01 every 1.0.0 skill folder and adapter of §14 exists (the new ones
as stubs), so the later 1.0.0 units modify and never create skill folders, adapters or personas;
`orient` (amendment 2) is created by U12.

Landed: U01, U02, U03, U04, U05, U06, U07, U08, U09, U09b, U10, U10b, U11 (1.0.0, released at
363dd5e), U12, U13, U14 (1.1.0), U15, U16 (1.1.1), U17, U18, U19, U20 (1.1.2, landing before the 1.2
handoff is planned; the amendment-4 paragraph below); a later handoff on this spec drafts no section for a landed row
(§9.1).

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
| U15 | The builder as a GitHub App (§11, §16; one identity per repository: `builder.app` null, the machine account; set, the App, with `launch` and `doctor` refusing when the machine account's variable is also set; the per-launch `<unit>_r<n>_bin/` with `superegm-token` and the `gh` shim at an absolute path (the orders' `{{gh}}` placeholder, the rewritten allow-list prefixes, no `PATH`), the git identity and the credential-helper reset through the launched command's environment, the mint over `urllib`, `builder_login` as `<slug>[bot]`, the App as a bypass actor refused, `doctor`'s App lines; the key read by path only, its exposure to the builder session named in §4.1): `skills/plan/scripts/superegm/builder_token.py` (create), `launch_builder.py`, `launch.py`, `prepare.py`, `decision.py`, `doctor.py`, `init.py`, `__init__.py` (modify: `DEFAULT_CONFIG.builder.app`, `SUBCOMMANDS`, the `launches` kind's directory form for `<unit>_r<n>_bin/` and `kind_of`'s inverse), `README.md`, `docs/claude.md`, `docs/faq.md`, `docs/privacy.md`, `skills/plan/references/handoff_config.md`, `skills/wave/references/builder_orders.md` (modify), `tests/unit/test_builder_token.py` (create), `tests/unit/test_builders.py`, `test_doctor.py`, `test_foreman.py`, `test_wave.py`, `test_helper.py`, `test_leavemealone_finish.py`, `test_packaging.py` (modify); tests fake the mint's `urllib.request` transport and use conftest's fake `gh` for the rest, with a test RSA key generated by `openssl genrsa` in a tmp dir (skipped with a reason when `openssl` is absent) | — (U14 landed) | L |
| U16 | The five 1.0.0 defects: the convergence rule with its byte predicate, `review status`'s `fixed:` line and the `review settle` and `review rule` refusals in that state, `approve-spec`'s `escalated[]` line and record and `config.commit_trailer` (§8), `scan_text` over fences and spans (§9.1), `judges record`'s `saw:` line (§13.1): `skills/plan/scripts/superegm/review.py` (modify: the byte predicate, `latest_cycle` through `evaluate` and the approval's `review`, the two refusals, the `set` copies' `fixed`), `judges.py`, `approve_spec.py` (modify: the `escalated[]` line and record, the trailer in `commit_by_path`), `graph.py` (modify: the `escalated[]` check), `scan.py` (modify: the body scan through `core.scan_text`, its own copy removed), `__init__.py` (modify: `scan_text`, its uncalled `scan_handoff` copy removed, `DEFAULT_CONFIG.commit_trailer`), `skills/review-spec/references/review_loop.md`, `skills/review-spec/SKILL.md`, `skills/review-plan/SKILL.md`, `skills/judges/SKILL.md`, `skills/plan/references/handoff_config.md` (modify: the wording, the cap options, the key), `tests/unit/test_review.py`, `test_judges.py`, `test_plan.py`, `test_helper.py` (modify) | — | M |
| U17 | Astra on every head review (§8, §11): `reviewers.head` default `change-review, astra` and `astra.heads`, both written by `init`; the astra-append rule for kind `head`; the foreman's Astra lane over the brief file `prepare --dispatch` writes (`r<n>/astra_brief.md`: what the Claude goldfish receive, the diff cut at 400 KB; its sha256 in the lane's record), one bounded foreground run (`--timeout 540`) after the Claude panel, fresh every round, recorded through the existing path; the degrade to `astra: not run (<reason>)` (`not installed`, `failed`, `killed`, `timeout`) with the round completing on the Claude reviewers; `doctor`'s informational `astra:` line: `skills/plan/scripts/superegm/foreman.py`, `prepare.py`, `collect.py`, `review.py`, `doctor.py`, `init.py`, `__init__.py` (modify: `DEFAULT_CONFIG`), `skills/wave/references/foreman_brief.md`, `resources/astra_lane.md`, `resources/review_panels.md`, `docs/claude.md` (modify), `tests/unit/test_foreman.py`, `test_review.py`, `test_doctor.py`, `test_helper.py` (modify) | — (U15, U16 landed by then) | M |
| U18 | The `redesign` ruling (§11, §12, §13.2): `decision rule … --ruling "redesign — <one sentence why>"` at a head's points 1 and 2, the judges' question file listing it, the stop through the `superegm:stopped` path, the store's `foreman/<unit>-<decision id>.brainstorm.md` (store-only, never committed; a file of the `foreman` kind's directory, no new store kind), the `**Ruling:**` comment naming the brief, `report`'s `## Stopped` with the brief's path, `close`'s refusal while such a unit's issue is open (one GitHub read), the brainstorming skill's brief-first paragraph: `skills/plan/scripts/superegm/decision.py`, `judges.py` (modify: the `redesign` option, its sentence filled, at a head's points 1 and 2), `report.py`, `close.py` (modify), `skills/judges/references/leavemealone.md`, `skills/brainstorming/SKILL.md` (modify: the brief-first paragraph), `skills/wave/SKILL.md` (modify: the ruling's effect in Step 3), `skills/integrate/SKILL.md` (modify), `tests/unit/test_wave.py`, `test_leavemealone_finish.py` (modify) | — (U10b, U11 landed) | M |
| U19 | Amendment-scoped spec review by default (§5, §8), batch dispositions and the four driving rules: `review open --kind spec --scope auto\|whole\|<sections>` (default `auto`: the sections changed since the last approval with their neighbours, re-derived every round from the current bytes; whole when none), the scope's form in the review record and the round's headings with line ranges, the brief wording, `review record`'s out-of-scope refusal and the round's `out_of_scope[]` lines, regressions and the cap over recorded findings, the cap question naming the scope; `review settle --file <dispositions>`; the four rules of §5 (a fresh session per phase, skills never switch branches, the admin-bypass merge line in `doctor`, `wave` and `integrate`, a new session after a plugin update): `skills/plan/scripts/superegm/review.py`, `doctor.py` (modify), `skills/review-spec/SKILL.md`, `skills/review-spec/references/review_loop.md` (modify: the scope rule and the brief wording), `skills/using-superegm/SKILL.md`, `skills/wave/SKILL.md`, `skills/integrate/SKILL.md` (modify), `tests/unit/test_review.py`, `test_doctor.py` (modify) | — (U16 landed by then) | M |
| U20 | One store per handoff (§7, §8, §9.1, §11): `artifacts_dir/<handoff id>/` as the handoff's root for everything from its approval on (`state.json`, `journal.md`, the plan files, plan and head reviews, run cards, launches, worktrees, foreman, orient unit files, judges, brainstorm briefs, directly under it: no `<6 hex>/` layer inside a handoff directory), the store level keeping `handoffs/<id>.json` (one file per handoff: `id`, `spec`, `opened_at`, `closed_at`, written by that handoff's `approve-spec` and `close`), `approvals/<slug>.json` as the append-only approval history (`entries[]` with `sha256`, `commit`, `handoff_id`, `kind`; the 1.1 single record read as one entry), the spec reviews and its journal (`orient/` moves under the handoff directory); `--amend-units` and `--void` on the latest entry alone (a void of a handoff with no filed unit closes it); `approve-spec`'s descent refusal (the branch's history must hold the spec at the last entry's bytes); one handoff per opening approval, a re-approval after a void keeping it, any other approval opening a new one beside the earlier; `launch`'s chain check (the base spec at the handoff's approved bytes or at a later entry, else refused; owner ruling 2026-11-05) with the cited range read at the entry the body's marker names (`launch-builder`'s `# Spec range`, `prepare`'s `spec_range.md`: the entry's commit or any commit holding its bytes, else a refusal); `--handoff <id>` on every subcommand, `runcard open` included, resolved once in `__init__.py`'s `store()` with §7's defaults (the card's handoff, the latest approval's, the filed unit's), card ids `<skill>-<6 hex>-<n>`, the typed skills passing `[--handoff <id>]` and the foreman's brief carrying it, `status` and `report` showing all without it (corrected by amendment 11: the inbox shows all, these one, §11.2); an older handoff frozen (`plan`, `review-plan`, `file`, `graph`, `--amend-units` and `--void` refuse; `wave`, `integrate` and `close` run; the integrate diff restricted to the handoff's own PRs); `graph`'s `filed_elsewhere[]` and the `set` brief line; a flat 1.0/1.1 store read in place as the handoffs it names, `legacy: true`, no migration script: `skills/plan/scripts/superegm/__init__.py` (modify: `Store`, `store()`), `approve_spec.py` (modify: the history, the handoff file, the card of a by-hand `--amend-units`), `review.py` (modify: `fix-design` refused on a frozen handoff's integrate), `launch.py` (modify: the chain check), `launch_builder.py`, `prepare.py` (modify: the range copy), `graph.py`, `gate.py`, `dry_run.py`, `apply.py`, `verify.py`, `status.py`, `report.py`, `close.py` (modify: path resolution and the refusals), `skills/plan/SKILL.md`, `skills/review-plan/SKILL.md`, `skills/file/SKILL.md`, `skills/wave/SKILL.md`, `skills/integrate/SKILL.md`, `skills/clean/SKILL.md`, `skills/interrupt/SKILL.md`, `skills/wave/references/foreman_brief.md` (modify: `[--handoff <id>]`; the `set` brief line; the foreman's handoff id), `docs/claude.md` (modify), `tests/unit/test_helper.py` and one test per touched module (modify) | — (U16 landed by then) | M |
| U21 | External-review ingest (§8): `review ingest`, the `external:<login>` reviewer id in `review record`, `foreman/<unit>.json.ingested[]`, `config.ingest` (`severity_words`, `human_role`), the `clean` → `revise` rewrite and its journal line, the wave's batch step: `skills/plan/scripts/superegm/review.py` (modify: `review ingest`, the id, the posted lines, the rewrite), `collect.py` (modify: an unreplied external high or medium carried forward), `launch.py` (modify: a rewritten outcome makes the unit ready, not in flight), `__init__.py` (modify: `DEFAULT_CONFIG.ingest`, `SUBCOMMANDS`), `init.py`, `skills/wave/SKILL.md` (modify: the batch step), `resources/review_panels.md` (modify), a `docs: see U29` Objective note, `tests/unit/test_review.py`, `test_foreman.py`, `test_wave.py` (modify; conftest's fake `gh` gains the review-thread endpoints) | — (U17–U20 landed) | M |
| U22 | Rulings by GitHub comment (§11.2, §13.2): the one grammar and its parser `ruling_of`, owners only, the seventh event kind `ruling` and its line, `decision rule --by <login>` from a comment, `collect`'s deviation and `tdd-order` reads through the parser; from amendment 11 one ruling on a status comment that folded several deviations rules each with its option: `skills/plan/scripts/superegm/decision.py` (modify: the parser, `--by` from a comment), `status.py` (modify: the `ruling` event), `collect.py` (modify: every `**Deviation**` heading of a status comment read), `launch_builder.py` (modify: the prompt's rulings and decisions from `config.owners` alone), `skills/wave/SKILL.md`, `skills/wave/references/builder_orders.md` (modify: the orders quote the forms a builder may see), a `docs: see U29` Objective note, `tests/unit/test_events.py`, `test_wave.py`, `test_foreman.py` (modify), `test_u22.py` (create: its own keys) | U21 | M |
| U23 | The inbox and the notify hook (§11.2): `inbox [--all] [--json] [--handoff]` and its line form, `notify --runcard <id>`, the `~/.superegm/notify` hook, `config.notify_timeout_seconds`, `state.json.notified`, the `inbox` skill; from amendment 11 the leavemealone redesign bar (a judges' `redesign` without a high finding is refused by `decision rule --by judges:<panel-id>` and waits as a pending decision the inbox lists until the owner's `**Ruling:**`, §11): `skills/plan/scripts/superegm/inbox.py` (create: `inbox`, `notify`), `__init__.py` (modify: the two keys, `SUBCOMMANDS`), `init.py` (modify), `skills/inbox/SKILL.md` (create: `effects: none`, auto-invokable like `doctor`'s line in `using-superegm`, with `assets/icon.svg` and `test_scenarios.yaml`), `skills/wave/SKILL.md` (modify: the notify step), `decision.py` (modify: the bar's refusal, after U22), `skills/judges/references/leavemealone.md` (modify: the two `redesign` rows point at it, the cap row's `review rule stop` held until `decision rule` accepts), `skills/using-superegm/SKILL.md` (modify), a `docs: see U29` Objective note, `tests/unit/test_inbox.py`, `test_u23.py` (create: its own keys), `test_wave.py`, `test_packaging.py`, `test_effects.py`, `test_skeleton.py` (modify) | U22 | M |
| U24 | The headless driver and the registry (§11.2): `register [--remove]`, `~/.superegm/registry.json`, `driver tick\|install\|uninstall\|status\|reset`, the launchd agent with `AbandonProcessGroup` (on Linux a systemd user timer, `KillMode=process`), `install --interval`, `~/.superegm/env`, `driver/<handoff>.json`, `inbox --all`, `SUPEREGM_ROLE=driver`, the `driver` skill, `doctor`'s driver line, the typed `wave`'s refusal while a tick's launch has no exit file: `skills/plan/scripts/superegm/driver.py` (create), `inbox.py` (modify: `--all`; the driver items; `notify` under a `driver` card), `status.py` (modify: the tick's read), `review.py` (modify: the stall read across `wave` cards), `launch.py` (modify: a pending unit holds no slot), `launch_builder.py` (modify: starting the launch as its one behaviour, from amendment 10 with no flag: the Popen in a new session, the wrapper the detached process-group leader, the `running` entry it writes once with `pid`, `started_at`, the prompt hash, `boot_id` and `command`; the reboot proof in the terminal check), `__init__.py` (modify: `runcard open`'s refusal for `wave`, `plan`, `file`, `integrate`, `review-plan` and `orient`, its `driver_card` write and its reboot proof, the `driver` store kind, `SUBCOMMANDS`), `doctor.py` (modify: the `driver:`, `env:` and notify-hook-sha lines, information only), `skills/driver/SKILL.md` (create, with `assets/icon.svg` and `test_scenarios.yaml`), `skills/wave/SKILL.md` (modify: the `SUPEREGM_ROLE=driver` paragraph: never ask, journal and end; step 5's launch through `launch-builder` alone, the rule reaching every launch the skill makes: the `revise` row and the `What it does` line too), `record_launch.py` (modify: the flagless form refused, `--exit` required), `skills/using-superegm/SKILL.md` (modify), a `docs: see U29` Objective note, `tests/unit/test_driver.py`, `test_u24.py` (create: its own keys), the start's test in `test_builders.py` beside U09's launch tests (the launch's one behaviour, the entry's fields, the flagless `record-launch` refused), `test_inbox.py`, `test_doctor.py`, `test_packaging.py`, `test_effects.py`, `test_skeleton.py` (modify) | U23; after U25 on shared files | L |
| U25 | The foreman verifies (§11, §8): the DoD re-run gate and the test-delta gate in `collect`, `r<n>/dod/<item>.txt`, `rounds[].dod_runs`, `rounds[].test_delta`, the finding ids `dod-<n>` and `test-delta`, `config.foreman.run_timeout_minutes`, the `test-delta` settle rule and the `allowed` rulings of `test-delta` and `dod-<n>`, `doctor`'s `python3.12` line: `skills/plan/scripts/superegm/collect.py` (modify: both gates, inputs read before the first run), `review.py` (modify: the settle rule; `review post`'s `gates not run` refusal and `owner: <ids>` outcome), `prepare.py` (modify: the review worktree removed by force; the hook-free git calls), `launch_builder.py` (modify: the hook-free git calls), `doctor.py` (modify: the `python3.12` line, the hooks-directory and `core.hooksPath` lines), `__init__.py` (modify: `DEFAULT_CONFIG.foreman`; `kill_group`, the process-group kill by SIGTERM with no escalation, the wait its caller's: `collect`'s at its bound, waiting no longer than the bound after the signal before it writes back (a survivor §4.1's residual), and from amendment 10 U31's, whose wrapper traps it), `init.py` (modify), `skills/wave/references/foreman_brief.md` (modify: the word is given only after both gates ran; the `owner` word), `skills/wave/SKILL.md` (modify: the `owner` word's row), `resources/review_panels.md` (modify: the foreman list gains both ids), `tests/unit/test_foreman.py`, `test_review.py`, `test_wave.py`, `test_doctor.py` (modify), `test_u25.py` (create: its own keys) | U22 (`ruling_of`; U17 landed); after U21 and U23 on shared files | M |
| U26 | External review on the elephant's own PR (§8): `review ingest --pr <n>` (kind `spec`), U21's reader, severity map and bot/human rules reused, findings into the spec's latest cycle, closed by `accept` or not, `review.json`'s `ingested[]`, the `**Reply <fid>:** fixed` post on the thread under the elephant's token, `approve-spec`'s one ingest before its refusals and its one check (an unsettled external high or medium in the latest round, after the carry-forward, refuses, `by ruling` or not), `review-spec`'s `github-write` and `remote-branch`, the PR opened by the skill's preflight (refusing on `<base>`, committing the spec by path, pushing first) and the push after each fix and the approval commit, step 4's path back to step 3 on the refusal: `skills/plan/scripts/superegm/review.py` (modify: `--pr`, the review-level `ingested[]`, the reply post), `approve_spec.py` (modify: the one ingest call and the one check), `skills/review-spec/SKILL.md` (modify: the preflight's PR, the per-round fix commit §5 assumes and the push after it and after the approval commit, step 4's path back to step 3 on the ingest's refusal; the frontmatter's `github-write` and `remote-branch`), a `docs: see U29` Objective note, `tests/unit/test_review.py`, `test_effects.py` (modify), `test_u26.py` (create: its own keys) | U21; after U24 on shared files | M |
| U27 | The builder's plugins and MCP servers, passed per launch (§4, §7, §11, §15): `config.builder.plugins` (`<name>@<marketplace>`; `init` writes `[]`), each resolved through the elephant profile's `plugins/installed_plugins.json` to `--plugin-dir <dir>`, and `config.builder.mcp` (`mcpServers` form; `init` writes `{}`), written to `launches/<unit>_r<n>_mcp.json` and passed with `--mcp-config --strict-mcp-config`; the per-launch record `launches/<unit>_r<n>_plugins.json` (id, version, directory, hook events per plugin; the managed plugins; the MCP server names; superseding `_managed.json`); `launch-builder`'s and `doctor`'s refusals (a listed plugin not installed or among the builder profile's managed plugins; a profile `skills/` or `commands/` directory or without `disableClaudeAiConnectors`, beside the landed login-only checks); `ENABLE_CLAUDEAI_MCP_SERVERS=false` in the launched environment; `doctor`'s `plugins:` and `mcp:` lines; `Skill(<name>)` / `Skill(<name> *)` and `mcp__<server>__<tool>` / `mcp__<server>__*` rules in `allowed_tools`; the skills named in the builder orders at the launch; from amendment 11 `gh pr view` and the test runner in `allowed_tools`' defaults and the orders' PR-body refresh line's `--body-file` form: `skills/plan/scripts/superegm/launch_builder.py` (modify: the flags, the MCP file, the record, the checks, the orders' skill line), `doctor.py` (modify: the two lines), `__init__.py` (modify: `DEFAULT_CONFIG.builder.plugins` and `.mcp`; `.allowed_tools`' two entries), `init.py` (modify), `skills/wave/references/builder_orders.md` (modify: the skills line; the refresh line's `--body-file` form, the push paragraph's after-push clause dropped), `skills/using-superegm/references/claude-code-tools.md` (modify: the `--allowedTools` sentence and the two flags), `docs/getting_started.md` (modify: the config's plugins and servers; the profile step), a `docs: see U29` Objective note, `tests/unit/test_builders.py`, `test_doctor.py` (modify), `test_u27.py` (create: its own keys) | — (U14, U15 landed); after U24 on `launch_builder.py` and `doctor.py` | M |
| U28 | The default models and efforts per role (§7, §8, §11, §13): `builder.model` `claude-opus-5-5` (a full id) and `builder.effort` `medium`, passed to the launched `claude -p` as `--effort <level>` with `CLAUDE_CODE_EFFORT_LEVEL` unset, and written with the effective model into `launches/<unit>.json`; `reviewers.model` / `reviewers.effort` `opus` / `xhigh` (the Agent tool's alias and level), passed on every review goldfish dispatch as the adapter's override (the adapters stay `model: inherit`), the two session variables overriding them and `inherit` passing nothing; `astra.heads_effort` `high` for the foreman's lane; `judges.members` default `fable` (adapter, `xhigh`), `astra` (runner, `xhigh`, `not run` when absent), `opus` (adapter, `max`), an adapter member's `model` an alias; the elephant never in config; the four added keys read as `init`'s defaults in a pre-U28 config, the landed `builder.model` and member `effort` values standing; `doctor`'s role table: `skills/plan/scripts/superegm/__init__.py` (modify: `DEFAULT_CONFIG`, which `init` writes verbatim; the loader's `astra` merge extended to `builder` and `reviewers`, so a missing nested key reads from it), `launch_builder.py` (modify: `--effort`, the unset name, the entry's requested `model` and `effort`), `record_launch.py` (modify: the effective model from the result file's `modelUsage` and, amendment 10, `total_cost_usd` from the same read, the board's cost), `judges.py` (modify: the members' efforts; its `DEFAULT_MEMBERS` copy dropped for `DEFAULT_CONFIG.judges.members`, the one source), `doctor.py` (modify: the table, the members read through `judge_members`), `skills/review-spec/references/review_loop.md` (modify: the one rule), `skills/wave/references/foreman_brief.md` (modify: the placeholders filled from the config; step 2b's `astra.heads_effort` read and its `high` fallback), `skills/judges/SKILL.md` (modify: the override read per judge from the panel file; the effective pair by `review_loop.md`'s rule), `skills/judges/references/astra_judge.md` (modify: `<ASTRA_EFFORT>` from the panel file's member effort), `resources/review_panels.md` (modify: section 6 points at `review_loop.md`'s rule; section 1's table and `printenv` line untouched), a `docs: see U29` Objective note, `tests/unit/test_u28.py` (create: its own keys), `test_doctor.py`, `test_builders.py`, `test_judges.py`, `test_foreman.py`, `test_review.py` and `test_astra_fork.py` (modify: the pins on `review_loop.md` and `review_panels.md`) | — (landed units); after U27 and every earlier unit on the files its row shares | M |
| U29 | Split units for parallel waves (§9.1, §9.2): the plan rules (a unit's Scope within one subsystem; a crossing unit written as two, a `Blocked by` edge only where one consumes the other's interface and the Shared files order for any file both edit; the cross-cutting rule for `README.md`, `docs/claude.md` and `test_helper.py`; Size `L` a split candidate; the plan shaped for wave width, its header stating the wave plan and why any wave is a singleton; a split's rows through `--amend-units`), `graph --plan`'s `width:` line derived from `handoff_units.json`, read by the plan skill before `scan`, `set-input` deriving the same line, the `set` reviewer's chain check (a chain longer than two units → its forcing edge, `medium`, once; from amendment 11 the header's wave plan and singleton reasons handed to `set`, the chains ending at one unit folded into one finding, a chain the header names `low`) and the `proportion` persona's per-unit split check (over 10 Steps, 24 KB or eight paths, or crossing subsystems → split candidate, `medium`), `scan`'s warnings at those values: `skills/plan/scripts/superegm/graph.py` (modify: the `width:` line), `review_plan.py` (modify: `set-input` derives it), `scan.py` (modify: the warning values), `skills/plan/SKILL.md` (modify: the rules; the `width:` read before `scan`; the header's wave plan), `skills/plan/references/handoff_plan.md` (modify: the Size row; the `graph` row's `width:` line), `skills/plan/references/issue_template.md` (modify: the limits paragraph at the amendment's values), `skills/review-plan/SKILL.md` (modify: the line handed to `set`), `skills/review-plan/references/proportion.md` (modify: the per-unit split check), `docs/claude.md`, `README.md` (modify: the 1.2 docs sweep, every unit's `docs: see U29` note resolved here), `tests/unit/test_plan.py`, `test_review_plan.py` (modify) | U28, U30, U31 (the docs sweep after the rows it sweeps: their `docs: see U29` notes are its edges, §9.1) | S |
| U30 | The board (§7, §11): every `status` pass of a `wave` session, `--wait` included, writes the report's `## Units` table, with the new columns (state word from `report.py`'s `unit_state` plus `ready` and `waiting`, derived once there · round · launch · head · PR · waits on · next action, `word_action`'s for a posted round, else by state · cost from `total_cost_usd`), under its header line (the time of the last change) into the tracking issue's body between `<!-- superegm:board -->` and `<!-- /superegm:board -->` through one splice function (replace between the markers, append once, write only on change; a module of the plan's choosing) and `apply.edit_issue`, one GitHub write per pass and none when the fresh rows match the block read back; one table in the file, on stdout and in the issue; `verify` compares the body outside the markers through the same splice; the inbox stays the action list; from amendment 11 U20's row's "showing all without `--handoff`" is corrected, not the helper: the inbox is the store-wide read (§11.2), `status` and `report` one handoff's, a carded call taking the card's handoff: `skills/plan/scripts/superegm/report.py` (modify: the words `ready` and `waiting`; the new columns of the `## Units` line), the splice's module (the plan's choice among modules no other 1.2 unit edits, `apply.py` beside `edit_issue` the natural one: the one function), `status.py` (modify: the one write through it), `verify.py` (modify: the comparison outside the markers through it), `skills/wave/SKILL.md` (modify: the status step names the board), a `docs: see U29` Objective note, `tests/unit/test_wave.py` (modify) | — (landed units); after U22 and U24 on `status.py`, U24 on `skills/wave/SKILL.md`, U25 on `test_wave.py` | S |
| U31 | The watchdog (§4, §7, §11, §11.2): `config.builder.stall_minutes` (30); a `running` launch without the `kill_failed` mark, no exit file, whose branch shows no commit newer than its own newest commit (or its `started_at`) for that long is stalled; the launch `launch-builder` starts (U24's one behaviour, §11) carries the wrapper's trap; the `wave` session's `status` pass, a reader, reports `U<n> stalled (<minutes> min; last commit <time | none>) pr=<n or none> status=<word or none>`, and the skill's step 3 records it through `record-launch --exit stalled`, which signals the group, waits 30 s for the wrapper's exit file `stalled` (the one proof) and records `exited (stalled)` with `last_commit_at` (the launch's own newest commit or none, written on every `--exit` from amendment 10, the one field the carve-out reads for an exit or a stall) or `kill_failed` (the launch signalled no more, the unit idle by one clause of `unit_state` and in the inbox for the owner's interrupt; a later exit file clears it), journals it and routes the unit to point 3 with the stall facts, where a launch with no commit of its own spends no relaunch, exit or stall, and a second is `stop`; `doctor`'s `stall:` line; the wave skill's step 3 records the stalled line: `skills/plan/scripts/superegm/launch_builder.py` (modify: the wrapper's trap), `status.py` (modify: the check, the event line and the mask; the tick's read counting the predicate as a trigger), `record_launch.py` (modify: `--exit stalled`: the signal and the wait through U25's `kill_group`, the record or `kill_failed`; the entry re-read; `last_commit_at` on every `--exit`), `report.py` (modify: the `kill_failed` clause of `unit_state`), `inbox.py` (modify: the `kill_failed` kind), `decision.py` (modify: the carve-out), `judges.py` (modify: `question --unit <U> --blocked launch <n>` renders the options from the pending decision's record, where `decision open` applied the carve-out once, and the stall facts from the launch entry; its own `relaunch already used` refusal dropped, so leavemealone-mode gets the panel where normal mode gets the question), `doctor.py` (modify: the line), `__init__.py` (modify: `DEFAULT_CONFIG.builder.stall_minutes`), `skills/wave/SKILL.md` (modify: step 3's stalled line; the Entry's resume raising point 3 for an `interrupted` launch with no decision on it; the leavemealone paragraph's reading of a refused question dropped with the refusal; the frontmatter's `destructive-local` for the kill), a `docs: see U29` Objective note, `tests/unit/test_wave.py`, `test_doctor.py`, `test_builders.py`, `test_judges.py`, `test_effects.py` (modify), `test_u31.py` (create: its own keys) | U24, U25 (`kill_group`); after U30 on `status.py`, `report.py` and `skills/wave/SKILL.md`, after U28 on `__init__.py`, `doctor.py`, `launch_builder.py`, `record_launch.py` and `judges.py` (module files; the test files follow the Shared files chains below) | M |
| U32 | 1.1.3's carried findings (§8, §11, §12): `close` closes the tracking issue and any merged unit's open issue as completed, `--note` on `close` and `runcard close`, the integrate skill's `--patch` closing without the integrate round on the owner's typed word, a `close --note`; `launch-builder`'s idempotent re-run and the orders' detached-`HEAD` stop; the by-hand `approve-spec --amend-units` card (`approve-spec-<6 hex>-<n>`, which §12 states and the landed helper lacks); a scoped finding with no line number out of scope by the landed path; the ruling's `review status` `rounds:` item moot (a head gains no second cycle: `foreman dispatch` opens a head review only when none exists and `stop` ends the unit), nothing to build; and a sweep of the accepted cleanups (the three copies of the spec-blob hash search and of the chain selection folded into one helper; the `STORE`/`CURRENT_ARGS` coupling; the stale one-handoff prose in `handoff_plan.md`, `orient`, `issue_template` and `review_loop.md`; the brainstorming brief lookup): `skills/plan/scripts/superegm/close.py` (modify: the issue closes, `--note`), `runcard.py` (modify: `--note`), `launch_builder.py` (modify: the idempotent re-run), `approve_spec.py` (modify: the by-hand card), `review.py` (modify: the lineless finding out of scope), `skills/plan/scripts/superegm/` as one directory path with `init.py` and `doctor.py` (modify: module self-registration, each subcommand module exposing its parser registration, its config defaults, its `init` step text and its `doctor` check, discovered by import, the registry lines `DEFAULT_CONFIG`, `SUBCOMMANDS`, `init`'s key text and `doctor`'s line gone; the sweep's one helper), `skills/wave/references/builder_orders.md` (modify: the detached-`HEAD` stop), `skills/integrate/SKILL.md` (modify: Step 1's gate admitting a unit whose PR merged with its issue open and Step 2's diff set every merged PR of the handoff, that unit's included; the `--patch` path; the frontmatter's `github-write`), `skills/review-spec/references/review_loop.md` (modify: the sweep's prose; section 5's lineless-location sentence, §8's path), `skills/plan/references/handoff_plan.md`, `skills/plan/references/issue_template.md`, `skills/orient/SKILL.md`, `skills/brainstorming/SKILL.md` (modify: the sweep's prose), `README.md`, `docs/claude.md` (modify: U32's own docs after U29, the release's last unit, §9.1), `tests/unit/test_leavemealone_finish.py`, `test_review.py`, `test_builders.py`, `test_effects.py` (modify), `test_u32.py` (create: its own keys) | U29 (the docs sweep; U32 is the release's closing sweep, §9.1's one exception, after the rows it sweeps); after every unit on the package it rewrites | M |

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

Amendment 3 units (1.1.1): U15 and U16 are filed from this spec as a third handoff
(id `2026-11-03-superegm-<6 hex of its approval>`, the helper's one form; the owner's name for
it, `2026-11-04-superegm-1.1.1`, is the tracking issue's title and nothing else), under the
same landed-row rule (a plan for it carries sections for
U15 and U16 only). U15 is blocked by nothing (U14, whose files it edits, landed; a landed row is
no plan unit, so a `Blocked by` never names it); U16 consumes nothing from U15 but edits three
files after it: `skills/plan/scripts/superegm/__init__.py`, `tests/unit/test_helper.py` and
`skills/plan/references/handoff_config.md` are U15's, then U16's, so the shared-file chain puts U16 in the wave after U15 (§5's readiness
rule; the regions are disjoint, which the helper does not know). Risk: U15 high (credentials:
the `<unit>_r<n>_bin/` scripts hold no token and live in the store, outside the repository;
the token is never written to the store or a prompt file, and the builder session can read the App's key by its path, §4.1); U16 medium
(the convergence rule changes when a review is converged; the in-flight self-build cycle's
records keep their state, no migration: a converged, unapproved review whose bytes moved before
the upgrade resumes as the same cycle in the `fixed:` state with its round count and cap).

Amendment 4 units (1.1.2): U17–U20 are filed from this spec as a fourth handoff (id
`2026-11-03-superegm-<6 hex of its approval>`; the owner's name, `2026-11-05-superegm-1.1.2`, is
the tracking issue's title), after U15 and U16 land, under the same landed-row rule (a plan for
it carries sections for U17–U20 only, and no `Blocked by` names a landed row). U17 and U18 share
no file (the brainstorm brief is a file of the existing `foreman` kind's directory: U18 adds no
store kind and edits no `__init__.py`). U19 edits
`skills/plan/scripts/superegm/review.py`, `doctor.py`, `tests/unit/test_review.py` and
`test_doctor.py` after U17 and `skills/wave/SKILL.md` and `skills/integrate/SKILL.md` after U18;
U20 edits `__init__.py`, `prepare.py`, `docs/claude.md`, `tests/unit/test_helper.py`,
`test_foreman.py` and `skills/wave/references/foreman_brief.md` after U17, `report.py`, `close.py`, `tests/unit/test_wave.py` and
`test_leavemealone_finish.py` after U18, and `review.py`, `skills/wave/SKILL.md`, `skills/integrate/SKILL.md`
and `tests/unit/test_review.py` (where `approve_spec.py`'s tests live) after U19, so the
shared-file chain puts U20 in the wave after U19 (§5's readiness rule) and the waves are
{U17, U18} → {U19} → {U20} (U19's four rules are stated in `using-superegm`, their one text, and
the admin-bypass line in `doctor`, `wave` and `integrate`, none in `docs/claude.md`, §5). This
amendment's own review runs on the installed helper (1.1.0 at review time; 1.1.1 lands U15 and
U16 before the handoff is planned), which has no `--scope`: its scope is applied by hand through
the brief, as the amendment-2 paragraph applied the landed-row rule, and in a store of its own
(`artifacts_dir` set in its worktree's config and taken out of the approval commit by a by-hand
amend that keeps the spec's bytes, which §8's and §11's content checks accept, as the 1.1.1 and
1.2 handoffs do), since that helper's flat store holds one
open handoff at a time (until U20). Risk: U17
medium (the runner's `result.json` field names come from `astra_lane.md`, not a schema; a changed
field degrades to `not run`, never to a wrong verdict); U18 medium (the brief copies a head's diff
into the store, outside the repository and never committed; the plugin scans no content, §11, so
a secret in the diff is the one the owner's eyes already met on the PR); U19 low (a mis-mapped
heading narrows or widens the scope; the tests pin the mapping on a fixture spec); U20 medium (path resolution touches every module; the tests pin
that a legacy flat store still reads and that `launch` refuses a base spec off the chain). The version bump to 1.1.2, the tag and the release are the
owner's by-hand steps after all four merge, as before.

Amendment 5–11 units (1.2): U21–U32 are filed from this spec as a fifth handoff (the helper's id
form; the owner's name for it, `2026-11-05-superegm-1.2`, is the tracking issue's title and
nothing else), through the installed 1.1.2 (`orient`, `review-spec --reviewers design`, approve,
`plan`, `review-plan --reviewers readiness,proportion`, `file`, then `wave` through SuperEGM
itself: the App builder, Astra on heads, `redesign` available), under the landed-row rule (a plan
for it carries sections for U21–U32 only; U17–U20 landed, so no `Blocked by` names them; the
plan satisfies amendment 9's wave-width clause as far as 1.2 can: its header states the wave
plan below, each wave but {U26, U27, U30} a singleton forced by a named `Blocked by` or module-file
edge (`doctor.py`, `review.py`, `launch_builder.py`, the wave skill's steps, the shared tests;
the docs and `test_helper.py` edges gone by amendment 9's cross-cutting rule; the registry lines
`DEFAULT_CONFIG`, `SUBCOMMANDS`, `init`'s key text and `doctor`'s line add one edge per unit,
accepted by the owner, which U32's self-registration, the release's closing sweep, removes for
later releases, whose width comes from the subsystem rule's splits), U30 beside U26 and U27 (after U22 and U24 on `status.py` and `skills/wave/SKILL.md` and
U25 on `test_wave.py`, no file shared with them), U31 after U30 on `status.py`, `report.py` and
`skills/wave/SKILL.md` and U28 on `__init__.py`, `doctor.py`, `launch_builder.py`,
`record_launch.py` and `judges.py`, by its blockers U24 and U25 (`kill_group`, landed four waves earlier), and U29, the docs sweep, after U28, U30 and U31, the
rows it sweeps, and U32 last, the release's closing sweep, `Blocked by` U29 and after every unit on the
package it rewrites (the ruling placed it beside U31, blocked by no 1.2 unit; §9.1's closing-sweep
exception and `__init__.py` and `doctor.py` shared with U31 move it two waves later); the 1.2 rows are exempt from the split
checks as a set, reviewed under 1.1.2's `proportion.md`, which has none; their plan sections
carry the size the path count gives, as the parser requires). Once
U21 lands and the plugin is updated from the tree, the next `wave`, typed in a new session (§5: a
wave is one invocation, and an update takes a new session), ingests Devin's reviews of the later
1.2 PRs, and the next amendment's spec PR, opened by the review's preflight, is the first
`review ingest --pr` reads once U26 lands (amendment 6; this repository's handoffs amend the
approval commit by hand to drop `artifacts_dir`, then push the branch again with `--force-with-lease`,
the elephant's own branch being outside the `superegm/**` rule, so the PR's head is the commit
`<base>` receives): the dogfood. The
order is the panel's (`1.2-questions-e8857c`, two rounds, Claude-only, every question converged;
the owner accepted every verdict and amended the test-suite non-goal on their own word): ingest
and rulings first, then the inbox, then the driver; U25 sits where its shared files put it, and
U26 (amendment 6) after U21 by its blocker and after U24 on `review.py`, U27 (amendment 7) beside U26, after U24 on `launch_builder.py` and `doctor.py`, and U28 (amendment 8) last, after
U27 and every earlier unit on the files its row shares (the chains below), U30 (amendment 10)
beside U26 and U27 (no file shared; U30 after U22 and U24 on `status.py` and
`skills/wave/SKILL.md` and U25 on `test_wave.py`), U31 (amendment 10) after U30 on `status.py`, `report.py` and
`skills/wave/SKILL.md` and after U28 on `__init__.py`, `doctor.py`, `launch_builder.py`,
`record_launch.py` and `judges.py`, U29 (amendment 9) the docs sweep, `Blocked by` U28, U30 and U31 (the rows it sweeps), and U32
(amendment 11) last, the release's closing sweep, `Blocked by` U29 (§9.1's one exception) and
after every unit on the package it rewrites.
Shared files: `collect.py` is U21's, then U22's, then U25's; `review.py` U21's, then U25's, U24's, U26's;
`skills/wave/SKILL.md` U21's, then U22's, U23's, U25's, U24's, U30's, U31's; `__init__.py` U21's, U23's, U25's, U24's, U27's, U28's and U31's, `init.py` U21's, U23's, U25's and U27's, and
`test_helper.py` no 1.2 unit's (amendment 9: each unit's own test file; U25 still follows U23
on `skills/wave/SKILL.md` and U24 follows U25 on `doctor.py`); `inbox.py` U23's, U24's, then U31's; `test_inbox.py`
U23's, then U24's; `launch.py` U21's, then U24's; `doctor.py` and `test_doctor.py` U25's, then U24's, U27's, U28's, U31's; `launch_builder.py` U22's, then U25's, U24's, U27's, U28's, U31's; `status.py` U22's, U24's, U30's, then U31's; `record_launch.py` U24's, U28's, then U31's; `judges.py` and `test_judges.py` U28's, then U31's; `test_effects.py` U23's, U24's, U26's, U31's, then U32's; `skills/plan/references/handoff_plan.md` and `issue_template.md` U29's, then U32's; `decision.py` U22's, U23's, then U31's; `test_wave.py` U21's, U22's, U23's, U25's, U30's, then U31's; `report.py` U30's, then U31's; `test_builders.py` U24's, U27's, U28's, U31's, then U32's; `resources/review_panels.md` U21's, U25's, then U28's; `foreman_brief.md` U25's, then U28's; `test_foreman.py` U21's, U22's, U25's, then U28's; `test_review.py` U21's, U25's, U26's, U28's, then U32's; `skills/wave/references/builder_orders.md` U22's, U27's, then U32's; `skills/review-spec/references/review_loop.md` U28's, then U32's; `docs/claude.md` and `README.md` U29's (the 1.2 docs sweep), then U32's (the release's last unit, §9.1)
(amendment 9: the units whose approved rows edited the docs carry a `docs: see U29` Objective note). Waves: {U21} → {U22} →
{U23} → {U25} → {U24} → {U26, U27, U30} → {U28} → {U31} → {U29} → {U32}; version 1.2.0 after all twelve merge (manifests, `docs/releases.md`, tag,
release, plugin update: the owner's by-hand steps), after which `superegm driver install` (re-typed
after every later update), `~/.superegm/env`, `register` from each handoff's worktree, a machine kept awake
(`pmset`/`caffeinate`) and the builder's tooling configured (amendment 7, this repository's
choice: `config.builder.plugins` `["ponytail@ponytail"]` alone (never `superegm@superegm`),
installed and disabled in the elephant profile, its SessionStart, SubagentStart and
UserPromptSubmit hooks admitted and recorded; `config.builder.mcp` `{"context7": {"type":
"http", "url": "https://mcp.context7.com/mcp"}}`, no key: the unauthenticated rate limit is
accepted;
`allowed_tools` gaining `Skill(ponytail:ponytail)`, `Skill(ponytail:ponytail *)`,
`mcp__context7__resolve-library-id` and `mcp__context7__query-docs`, the names this platform
gives them; and, when U28 lands, this repository's committed config edited to the ruled values:
`builder` `claude-opus-5-5` at `medium`, `reviewers` `opus` at `xhigh`, the judges `fable` at
`xhigh`, `astra` at `xhigh`, `opus` at `max`, `astra.heads_effort` `high`) are the owner's
by-hand steps, as the App
registration was for 1.1.1. Risk: U21 medium (a human medium
returns an awaiting-merge unit to flight, which is the owner's wish; a flood of bot lows never
blocks; the elephant's token reads, and posts the one review comment); U22 medium (a compromised owner login is a
compromised owner, outside the spec; the form check is exact, so a typo is silence, which the
inbox shows as the still-open decision); U23 low for `inbox` (reads) and medium for `notify`
(the owner's script runs with the owner's environment, bounded by the timeout); U24 high
(unattended owner credentials and comment text in an unattended foreman, §4.1; two sessions on
one handoff are prevented on both sides, the tick's (the exit file and the open `wave` card) and a
typed `wave`'s (`runcard open`'s refusal);
the plist runs only what the plugin root names); U25 medium (the head's code runs on the owner's
machine, §4.1); U26 low (reads; opens the spec PR and posts replies on it under the owner's token; pushes
the elephant's branch after each fix and the approval commit, never `<base>`); U27 medium (a
listed plugin, hooks included, runs in the builder's context with the builder's token: the
owner's named set alone, passed by flag, managed plugins policy, the set with each plugin's
version and hook events on the record per launch: the hook events are the record's bound, not
the plugin's component inventory; its mods and its own settings ride on the version); U28 low
(defaults: an alias or effort the platform refuses is refused at the dispatch, recorded
`--not-run`, or fails the launch, which `record-launch --exit` records); U29 low (plan rules and
two reviewer checks; the helper splits nothing); U30 low (one issue-body write per pass, between
the markers, never a unit issue); U31 medium (a process group killed by a recorded pid: the
wrapper's own, read from the record, never guessed, and never signalled when the group is
another's or gone (`kill_failed (pid reused)`, `kill_failed (no process)`), the exit file the one
proof; a
live builder between commits, a long `Run` suite or a large first read, is killed at the bound
and its unpushed commits left in the detached worktree, the relaunch starting at the PR tip,
the config value the mitigation and the cost stated; a stall with commits spends the relaunch as
an exit does); U32 medium (discovery by import replaces how every subcommand loads and how `init` composes
the config it writes: a module that fails to import or exposes no defaults breaks every command,
and the import order sets the written config's key order; beside it a GitHub close of a merged unit's open issue
whenever `close` runs and of the tracking issue when every unit then landed, a journal note, and `--patch` skipping a review on the
owner's typed word; the plan's fit against the 48 KB bound is the stated risk, the self-registration one mechanical pattern per module).
Plan-review focus: U21 a PR with 200 bot threads
and one human medium, and a thread on a head not yet reviewed; U22 a comment one character off
the form, and an owner's edit after the record; U23 a store with no open handoff, and the inbox's `test-delta` and `owner: <ids>` kinds built against §7's schema with fixture data (U25 lands after U23); U24 a reboot
mid-wave (no exit file), a session that exited without closing its card, a typed `wave` during a
tick's session, a tick during a typed `wave`, a plugin update under an installed timer, and two
worktrees registering one store; U25 a `Run` item that needs a service,
a `Run` line that installs, a suite longer than the bound, and a parametrize row moved rather
than dropped; U26 a thread an earlier round already answered, and a thread arriving after an
`accept`; U27 a listed plugin not installed, one installed but disabled (passes), a profile `skills/` directory, and whether
`--strict-mcp-config` keeps a listed plugin's bundled servers (a `Skill` rule naming no loaded
skill is inert on the platform: no check); U28 `--effort` honoured by `claude -p` and the result file's `modelUsage` field (one run)
and an effort a member's model lacks; U29 a unit of 11 Steps, a Scope crossing two subsystems,
and a chain of three units; U30 a body without the markers and a byte-identical table (no
write); U31 a launch with commits but no newer one at the bound, a host-caused stall (no commit
newer than the launch) and its second, no exit file within 30 s of the signal (`kill_failed`,
skipped after), a present leader that is another's and no member living (the two refusals, `pid reused` and
`no process`, and the proof the plan chose), a live group with no leader (signalled, `kill_failed (no exit file)`), a typed launch through `launch-builder`, and one run proving `claude -p`, signalled mid-command, exits on the
wrapper's signal within the bound (a shell runs its trap after its foreground child returns); U32 a `close` with a unit whose PR is unmerged
(journaled, its issue and the tracking issue left open), a unit whose PR merged with its issue open (admitted at Step 1, its PR in the round's diff, the issue closed), `--patch` journaled as the close's reason, a `launch-builder`
re-run after a failure before the switch, a scoped finding with a bare path, a module without defaults, a
module that fails to import, `init`'s written config key set equal before and after the
self-registration (the order the discovery's). Not in 1.2: cross-repository handoffs
(the lib-core and financial-twin inputs are one handoff per repository; the second spec states
its prerequisite in prose and `Landed:` rows, §9.1, and the owner types its phases after the
first lands; neither a `Repo:` field nor a cross-store `Blocked by` is built; the registry is a
list of stores, not a graph). `redesign` is U18's (amendment 4), which 1.2 builds on: a
contested external finding can be ruled `redesign`, by comment, and the inbox lists the stopped
unit with its brief.

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
  --runcard <id> → the launch started and its `running` entry written (amendment 10, U24: the
  one behaviour; amendment 5's `--start` flag and the printed command line gone, §11); exit 1
  with the refusal`; `record-launch --unit <U> --exit <code | stalled>`
  (from amendment 10 the flagless form is refused: the `running` entry is `launch-builder`'s); `launches/<unit>.json` per §7 (`launches[].round`, `launches[].status`,
  `launches[].result_file`, `launches[].prompt_sha256`); the `**Deviation**`, `**Reply <fid>:**`,
  `**Ruling:**` and `**Builder status:**` headings, the option-line form and the PR body's
  DoD-results form.
- U09b → U10b: `status --wait <s> --runcard <id> → one or more event lines`; the six event kinds.
- U10 → U10b, U11: `foreman dispatch --unit <U> --runcard <id> → <dispatch_id> <child-card>;
  exit 1 when the dispatch predicate fails`; `foreman-<unit>-<dispatch_id>` returns `clean |
  revise | contested: <ids> | owner: <ids> (amendment 5) | cap-reached | target-moved | error`; `review post … → exit 0 posted
  / 3 target-moved`.
- U10b → U11: `report`; `decision open --unit <U> --point <1|2|3> --question <file> → <id>`;
  `decision rule --unit <U> --decision <id> --ruling <text> --by <login | judges:<panel-id>>`;
  the `wave` skill's decision-point hooks.
- U12 → the owner: `superegm orient --spec <path> [--unit U<id>]... [--ref <ref>] --runcard <id>
  → one line per file written: <store path> <bytes>; exit 0 / 1 with "orient: <reason>"`; `orient/map.md` and
  `orient/<unit>.md` with their first line; py: `Store.path("orient", …)`,
  `Store.path("orient_unit", …)`.
- U13 → the owner: the write list's `issue` entry with its two trailing fields (the adopted
  number, the old body's sha256); `dry-run`'s `### edit #<n> <unit> (old body sha256 <hex>)` heading.
- U14 → the owner: `superegm doctor → one line per prerequisite; exit 0 / 1`; the config keys
  `owners`, `owner_team`, `pr_block_file`.
- U15 → the owner: `superegm builder-token [--repo <owner/name>] [--app-id <int> --key-env <name>] →
  the token on stdout; exit 0 / 1 with the refusal`; the config key `builder.app` (`app_id`, `slug`, `private_key_env`);
  `builder_login` in the form `<slug>[bot]`.
- U16 → the owner: `review status`'s line `fixed: re-review on the current bytes` (exit 3);
  `approve-spec: <n> escalated finding(s) await the owner: <ids>`; the config key
  `commit_trailer`; `judges record`'s `saw:` line.
- U17 → the owner: the config key `astra.heads` and `reviewers.head`'s default `change-review,
  astra`; `review record --reviewer astra` on a head; the round's `astra: not run (<reason>)`;
  `doctor`'s `astra:` line.
- U18 → the owner: `decision rule … --ruling "redesign — <one sentence why>"`;
  `foreman/<unit>-<decision id>.brainstorm.md`; `report`'s `## Stopped`; `close`'s refusal.
- U19 → the owner: `review open --kind spec --scope auto|whole|<sections>`; `review.json`'s
  `scope` and `round-<n>.json`'s `scope` and `out_of_scope[]`; `record: <fid> out of scope
  (<section>): not recorded`; `review settle --file <dispositions>`; `doctor`'s admin-bypass
  line.
- U20 → the owner: `artifacts_dir/<handoff id>/`; `handoffs/<id>.json`; `approvals/<slug>.json`'s
  `entries[]` (`sha256`, `commit`, `handoff_id`, `kind`); `--handoff <id>` on every subcommand
  and `[--handoff <id>]` on the typed skills; `approve-spec`'s descent refusal; `launch`'s
  refusal of a base spec off the handoff's approval chain; the frozen older handoff's refusals;
  `handoff_units.json`'s `filed_elsewhere[]`; the prompt's `# Spec range` and
  `prepare`'s `spec_range.md`.
- U21 → U22, U23, U26: `review ingest --unit <U> --runcard <id> → <n> ingested; exit 0`; the reviewer
  id `external:<login>`; `foreman/<unit>.json.ingested[]`; the journal line `<unit> ready again
  (external:<login>)`; the config key `ingest` (`severity_words`, `human_role`).
- U22 → U23, U24, U25: py: `ruling_of(comment, owners) -> Ruling | None`; the seventh event kind
  `ruling` and its line; the comment forms of §13.2.
- U23 → U24: `inbox [--all] [--json] [--handoff <id>] → one line per item: <repo> <unit or review>
  | <kind> | <action>; exit 0`; `notify --runcard <id>`; `state.json.notified`; the hook path
  `~/.superegm/notify`; the config key `notify_timeout_seconds`.
- U24 → the owner: `register [--remove] --runcard <id>`; the registry's keys `repo, root,
  artifacts_dir`; `driver tick|install|uninstall|status|reset`; `driver/<handoff>.json`;
  the launchd label `com.superegm.driver`; `install --interval`; `~/.superegm/env`; `doctor`'s
  `driver:` and `env:` lines; from amendment 10 `launch-builder`'s start as its one behaviour,
  the `running` entry with `pid`, `boot_id` and `command`.
- U25 → the owner: the `foreman-<round>-<n>` findings whose claims start `dod-<n>: ran red
  (<line>) | paste differs from the run` and `test-delta: <file>:<line> removed | weakened`; the
  three subjects the `allowed` ruling's parser matches: `<fid>`, `dod-<n>`, `test-delta <file>`; `rounds[].dod_runs.<item>.{exit, summary,
  paste_summary, timed_out}`; `rounds[].test_delta[].{file, line, base_line, kind, base_commit}`;
  `r<n>/dod/<item>.txt`; the config key `foreman.run_timeout_minutes`; the ruling form
  `**Ruling:** <fid> allowed — <reason>` for `test-delta` and `dod-<n>`.
- U26 → the owner: `review ingest --pr <n> --runcard <id> → <n> ingested; exit 0`; `review.json`'s
  `ingested[]`; the `**Reply <fid>:** fixed` post; `approve-spec`'s refusal `approve-spec: external:<login> <fid>
  unsettled on PR <n>`, exit 1.
- U27 → the owner: the config keys `builder.plugins`, `builder.mcp`; `launches/<unit>_r<n>_plugins.json`
  (`plugins[]` with `id`, `version`, `dir`, `hooks[]` the event names; `managed[]`; `mcp[]` the server
  names) and `launches/<unit>_r<n>_mcp.json`; `doctor`'s `plugins:` and `mcp:` lines; the refusals
  `launch-builder: plugin <id> not installed | managed in the builder profile` and `builder profile
  <dir> holds skills/ | commands/ | lacks disableClaudeAiConnectors`; `ENABLE_CLAUDEAI_MCP_SERVERS=false`
  in the launched environment.
- U28 → the owner: the config keys `builder.effort`, `reviewers.model`, `reviewers.effort`,
  `astra.heads_effort` and the new `init` defaults of `builder.model` and `judges.members[].effort`;
  `doctor`'s `model:` lines, one per role; every dispatch record's `--model` and `--effort`
  requested → effective; `launches/<unit>.json`'s `model` and `effort` (requested; the effective
  model from the result file's `modelUsage`, else `requested only`).
- U29 → the owner: `graph --plan`'s `width:` line (`width: chains <path>: U<a> > U<b> > … > U<n>
  (after U<b>)…`, the forcing edge the `after` item into the third unit; `none` when no chain
  exceeds two), derived from `handoff_units.json`'s `units[*].shared` as `set-input` derives it;
  the proportion finding form `split candidate: <Steps | bytes | paths | subsystems>`; the `set`
  finding form `chains at U<n>: <path> U<a> > U<b> > … > U<n> (after U<b>); <path> …` at the
  location U<n>, `low` when the header names them.
- U30 → the owner: the board between `<!-- superegm:board -->` and `<!-- /superegm:board -->` in the
  tracking issue (its header line with the time of the last change, and the `## Units` line's
  columns); the one table in `wave_<n>_report.md`, on stdout and in the issue.
- U31 → the owner: the config key `builder.stall_minutes`; the wrapper's trap; the event line `U<n> stalled (<minutes> min; last commit <time |
  none>) pr=<n or none> status=<word or none>`; `record-launch --exit stalled`; `launches[]`'s `pid`, `exited (stalled)`,
  `last_commit_at` and `kill_failed`; the exit file's `stalled`, the one proof; the inbox's
  `kill_failed` kind; the journal line `<unit> launch <n> stalled (<minutes> min; last commit
  <time | none>)`; the point-3 question's stall facts; `doctor`'s `stall:` line.
- U32 → the owner: `close [--note <text>]`, `integrate --close --patch` and `runcard close --note <text>`; the tracking issue and a
  merged unit's open issue closed as completed; `review record`'s out-of-scope line `<fid>: no line number`;
  the by-hand `approve-spec --amend-units` card
  `approve-spec-<6 hex>-<n>` (opened and closed by the command itself when no `--runcard` is given,
  skill `approve-spec`, §7's id form unchanged; effects `state-store`, the push the owner's, §5).

Waves: {U01} → {U02, U03} → {U04, U05, U08, U09} → {U06, U07, U09b, U10} → {U10b} → {U11}; then,
as a second handoff (`2026-11-03-superegm-<6 hex>`), {U12} → {U13} → {U14}, and version 1.1.0
after all three merge; then, as a third handoff (`2026-11-03-superegm-<6 hex>`), {U15} → {U16}, and
version 1.1.1 after both merge; then, as a fourth handoff (`2026-11-03-superegm-<6 hex>`, the
owner's name `2026-11-05-superegm-1.1.2`), {U17, U18} → {U19} → {U20}, and version 1.1.2 after all
four merge; then, as a fifth handoff (`2026-11-03-superegm-<6 hex>`, the owner's name
`2026-11-05-superegm-1.2` on the tracking issue), {U21} → {U22} → {U23} → {U25} → {U24} → {U26, U27, U30} → {U28} → {U31} → {U29} → {U32}, and
version 1.2.0 after all twelve merge.
