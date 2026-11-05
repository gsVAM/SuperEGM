# FAQ

<!-- Modified by SuperEGM (gsVAM), 2026: EGM's philosophy questions replaced by SuperEGM's: modes, the builder account, the judges, what stays human. -->

#### Q: What does the owner actually do?

**A**: Type one skill per phase, answer the questions the skills pause on, push the approval
commit, and merge. The elephant drafts, dispatches goldfish, files issues and drives the wave;
builders write code in headless sessions; foremen review every pull request head; the owner owns
the outcomes.

#### Q: What is leavemealone-mode?

**A**: `--leavemealone` on an invocation, or `"mode": "leavemealone"` in `.superegm/config.json`.
At every decision point of design section 13.2 (a contested or declined high or medium finding, a
review at its cap, a blocking decision, a blocked builder) the skill renders the question from the
record, convenes the judge panel (two Claude judges and GPT-6 Astra, two vendors) and applies
each converged answer, journaled as `Ruling (judges <id>, leavemealone): …` so the owner can read
and overturn it. An unconverged question waits for the owner. The panel is never convened by a
foreman, only by the elephant.

#### Q: Who merges?

**A**: The owner. Nothing is merged by a machine, in any mode. Builders open draft pull requests
they cannot merge; the branch protection lets only the owner update the base branch; the wave
ends with merge-ready drafts and a report, and `integrate` runs after the owner has merged.

#### Q: What is the builder account?

**A**: A second GitHub login, with its token in `SUPEREGM_BUILDER_TOKEN`, under which every
builder session pushes its unit branch and opens its draft pull request. Its comments on an
issue are never taken for the owner's: a `**Ruling:**` written by the builder account rules
nothing, and a close by the builder account is a decision point, not a stop.

#### Q: Can the builder be a GitHub App instead of a second login?

**A**: Yes: set `builder.app` (README step 1 says how to register it) and leave `SUPEREGM_BUILDER_TOKEN` unset.
The builder then acts as `<slug>[bot]` under one-hour installation tokens minted per `gh` call from the App's private key, which only the path in `SUPEREGM_APP_KEY` names; `superegm doctor` prints the App's lines.
It is the recommended path for an organization; the machine account is the quick path for a personal repository.

#### Q: Why a fresh session for every builder launch?

**A**: A builder's brief is the issue body, the builder orders, the rulings on its issue and,
from round 2, the foreman's reviews of its own branch: never the planning elephant's context.
The empty builder profile (no plugins, no `CLAUDE.md`) keeps it that way.

#### Q: What if a review never converges?

**A**: Change the thing, not the round. A review at its cap of five rounds pauses for a ruling:
one bounded round more (once), accept the remainder, or stop. Two rounds that regress on the same
area mean the capability should be deleted, the contract narrowed or the surface shrunk.

#### Q: Should I open big pull requests?

**A**: No. The answer is the same as when you built things without AI: one unit, one branch, one
pull request.
