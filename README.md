# SuperEGM

<!-- Modified by SuperEGM (gsVAM), 2026: U01's skeleton filled in by U11: the install notes, the by-hand setup, the eight phases and the Licence paragraph. -->

SuperEGM is one Claude Code plugin for the whole workflow, from an idea to a merged pull request: superpowers' unit of work (a brainstormed design, a TDD-shaped plan per unit) inside EGM's orchestration (isolated reviewers, an adversarial gate before anything is written, a dependency graph cut into waves, a foreman per unit reviewing every PR head with CI as evidence, a merge that stays human). The spec is not the plan: the spec is the design document, and the plan belongs to the GitHub issue, one per unit.

## Install

Disable the two plugins SuperEGM absorbs first, then install from the marketplace:

```sh
claude plugin disable egm@egm-astra
claude plugin disable superpowers@claude-plugins-official
```

```sh
claude plugin marketplace add gsVAM/superegm
claude plugin install superegm@superegm
```

The workflow is in [docs/getting_started.md](docs/getting_started.md); the platform facts in [docs/claude.md](docs/claude.md).

## Before the first run

<!-- superegm:u11 -->

`superegm init` (run by the first typed skill when `.superegm/config.json` is missing) writes the config and prints these by-hand steps:

1. Create the **builder account**: its own GitHub login with write access to the repository, and put a token for it in `SUPEREGM_BUILDER_TOKEN` (config key `builder.gh_token_env`). Builders push and open draft pull requests as that account and never merge.
2. Create the builder's empty profile at `config.builder.profile_dir`: no hooks, no plugins and no `CLAUDE.md`, only the login; `launch-builder` refuses anything else.
3. Set the branch protection of design section 11 on the base branch: restrict updates to the owner with no bypass for the builder account's role (classic or ruleset); block force-push and deletion on `superegm/**` with a repository ruleset, the only form `launch` reads for that pattern. `launch` reads the protection and refuses the first wave without it.
4. Add a workflow triggered on `pull_request`, so every builder head gets CI: CI is the foreman's evidence.
5. Commit `.superegm/config.json`; `approve-spec` commits it with the spec.
6. Run reviews from a profile without SubagentStart hooks: such hooks in the owner's own profile reach adapter subagents, and every dispatch record carries what the goldfish reported seeing.

## The eight phases

| # | Phase | Skill | Gate |
| --- | --- | --- | --- |
| 0 | Brainstorm | `/superegm:brainstorming` (auto-invoked) | the owner's opt-in; a spec ending in `## Units` |
| 1 | Spec review | `/superegm:review-spec <spec>` | converged or ruled; the approval freezes the spec at a sha256 |
| 2 | Plan | `/superegm:plan <spec>` | `graph` and `scan` pass |
| 3 | Plan review | `/superegm:review-plan <spec>` | converged or ruled, per unit |
| 4 | File | `/superegm:file <spec>` | a dry run the owner confirms; `verify` reads back |
| 5 | Wave | `/superegm:wave <spec>` | per unit: a clean head, contested findings ruled, no regressions |
| 6 | Merge | the owner | nothing is merged by a machine |
| 7 | Integrate | `/superegm:integrate <spec>` | nothing left to escalate; `--close` gives a handoff up |

One skill per phase, nothing chains; the owner pushes the approval commit between phases 1 and 5. With `--leavemealone` (or `"mode": "leavemealone"` in the config) the judge panel rules at every decision point and the owner wakes to merge-ready draft pull requests.

## Skills

- `/superegm:brainstorming` — turn an idea into a written design that ends in `## Units`
- `/superegm:draft` — draft a spec from a brief when brainstorming was skipped
- `/superegm:review-spec` — the adversarial spec review, run to convergence
- `/superegm:plan` — cut the approved spec into TDD-shaped build units
- `/superegm:review-plan` — review the plan against the spec before anything is filed
- `/superegm:file` — file the confirmed plan as GitHub issues
- `/superegm:wave` — launch, review and land a wave of units
- `/superegm:interrupt` — pause a running wave at the next safe point
- `/superegm:clean` — remove what a wave left behind locally
- `/superegm:finishing-a-development-branch` — finish a branch outside a wave, the PR as the owner
- `/superegm:integrate` — review the spec against everything merged and close the handoff
- `/superegm:judges` — run the judge panel over a question file (advisory when typed)
- `/superegm:test-driven-development` — red, green, commit on a filed unit's branch
- `/superegm:systematic-debugging` — find the root cause before fixing
- `/superegm:verification-before-completion` — prove it works before calling it done
- `/superegm:writing-skills` — write and test a skill for this plugin
- `/superegm:using-superegm` — the dispatcher every session reads first
- `/superegm:drift-report` — check the code against the designs after `integrate`

## Licence

**Licence.** Apache-2.0 (`LICENSE`) for the EGM-derived files and SuperEGM's own, MIT (`LICENSE-MIT`) for the superpowers-derived files. Every file changed from its source carries a notice naming the change, in the source's own form. The Apache files with a notice: `.claude-plugin/agents/change-review.md`, `.claude-plugin/agents/codebase-details.md`, `.claude-plugin/agents/comprehension.md`, `.claude-plugin/agents/design.md`, `.claude-plugin/agents/foreman.md`, `.claude-plugin/agents/readiness.md`, `.claude-plugin/agents/structural.md`, `.claude-plugin/agents/style.md`, `.claude-plugin/agents/zoom-out.md`, `.github/workflows/tests.yml`, `README.md`, `agents/change-review.md`, `agents/codebase-details.md`, `agents/comprehension.md`, `agents/design.md`, `agents/readiness.md`, `agents/structural.md`, `agents/style.md`, `agents/zoom-out.md`, `docs/claude.md`, `docs/faq.md`, `docs/getting_started.md`, `docs/index.md`, `docs/privacy.md`, `docs/releases.md`, `resources/document_standards/handoff-standard.md`, `resources/review_panels.md`, `scripts/pack_plugin.py`, `scripts/prepare_release.py`, `skills/draft/SKILL.md`, `skills/draft/references/design_doc.md`, `skills/draft/test_scenarios.yaml`, `skills/drift-report/SKILL.md`, `skills/drift-report/test_scenarios.yaml`, `skills/file/SKILL.md`, `skills/judges/references/astra_judge.md`, `skills/plan/SKILL.md`, `skills/plan/references/handoff_plan.md`, `skills/plan/references/issue_template.md`, `skills/plan/scripts/superegm.py`, `skills/plan/scripts/superegm/__init__.py`, `skills/plan/scripts/superegm/apply.py`, `skills/plan/scripts/superegm/approve_spec.py`, `skills/plan/scripts/superegm/body.py`, `skills/plan/scripts/superegm/collect.py`, `skills/plan/scripts/superegm/decide.py`, `skills/plan/scripts/superegm/dry_run.py`, `skills/plan/scripts/superegm/gate.py`, `skills/plan/scripts/superegm/graph.py`, `skills/plan/scripts/superegm/launch.py`, `skills/plan/scripts/superegm/prepare.py`, `skills/plan/scripts/superegm/record_launch.py`, `skills/plan/scripts/superegm/scan.py`, `skills/plan/scripts/superegm/status.py`, `skills/plan/scripts/superegm/verify.py`, `skills/plan/test_scenarios.yaml`, `skills/review-plan/SKILL.md`, `skills/review-plan/test_scenarios.yaml`, `skills/review-spec/SKILL.md`, `skills/review-spec/references/resolve.md`, `skills/review-spec/references/review_loop.md`, `skills/review-spec/test_scenarios.yaml`, `skills/wave/SKILL.md`, `skills/wave/references/foreman_brief.md`, `skills/wave/test_scenarios.yaml`, `tests/integration/test_claude.py`, `tests/unit/conftest.py`, `tests/unit/test_astra_fork.py`, `tests/unit/test_events.py`, `tests/unit/test_file.py`, `tests/unit/test_harnesses.py`, `tests/unit/test_helper.py`, `tests/unit/test_packaging.py`, `tests/unit/test_plan.py`, `tests/unit/test_releases.py`, `tests/unit/test_review.py`, `tests/unit/test_review_plan.py`. The superpowers files with a notice: `hooks/session-start`, `skills/brainstorming/SKILL.md`, `skills/finishing-a-development-branch/SKILL.md`, `skills/plan/references/writing_plans.md`, `skills/systematic-debugging/SKILL.md`, `skills/test-driven-development/SKILL.md`, `skills/using-superegm/SKILL.md`, `skills/using-superegm/references/claude-code-tools.md`, `skills/verification-before-completion/SKILL.md`, `skills/wave/references/builder_orders.md`, `skills/writing-skills/SKILL.md`, `skills/writing-skills/references/skill_discovery_optimization.md`, `tests/unit/test_builders.py`, `tests/unit/test_effects.py`.
