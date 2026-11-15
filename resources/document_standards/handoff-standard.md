<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by the elephant-goldfish-model Astra fork (gsVAM), 2026: the standard
for the handoff plan. Not part of google/elephant-goldfish-model.
Modified by SuperEGM (gsVAM), 2026: questions 8–11, severities high|medium|low, the fix-design path.
Modified by SuperEGM (gsVAM), 2026: the complete Step, the fence's private detail, the blocking question's failure scenario (1.2.1 §6.5). -->

# Handoff Standard

This standard is the bar of `review-plan` (phase 3): the build units derived
from an approved spec and the issue bodies rendered from them (`unit_<id>.md`),
reviewed before any issue is filed. It is applied three ways. Per unit, each
goldfish of the unit's panel reads the unit's rendered body with the approved
spec at its hash and every sibling's Interfaces block. Once per round, the
`set` reviewer reads the spec's `## Units` and, from every unfiled unit, the
Interfaces block and the Scope, Blocked by and Shared files lines. Per unit,
`proportion` reads one body with its `plan/scan/<unit>.json`. The spec is the
reference; the body is the document under review.

## Core Principle

A handoff passes if a builder who has never seen the conversation, given one
issue body and the spec range it names, knows what to build, where, what
counts as done, and what must land first, and if the set of issues together
builds exactly the spec and nothing else.

## The Eleven Questions

Answer each question for the set, or for the one body the reviewer holds. A
failure is a finding at the unit (or the pair of units) where it occurs.

1.  **Coverage, both directions.** Every row of the spec's `## Units` and
    every section a unit's Design range cites maps to that unit's scope paths
    or definition of done. No unit carries scope the spec does not contain. A
    spec requirement that no unit builds is high; a unit that adds scope the
    spec lacks is high.
2.  **Contradictions between units.** Two units that touch the same file with
    different intent, or a definition-of-done item that a later unit makes
    false (a test that the later unit deletes, a behaviour the later unit
    changes), are high.
3.  **Blocked by and order.** A unit that uses a file or symbol another unit
    creates or changes names that unit in `Blocked by`. A `Blocked by` that
    the spec does not require (document order alone) is spurious. Missing
    blockers are high; spurious ones are medium.
4.  **Shared-file order.** Every path in two units' scope has a shared-file
    chain, and the chain agrees with the blockers and with the spec's phase
    order. A chain that contradicts them, or a shared path without one, is
    medium.
5.  **Testability.** Every definition-of-done item names a command, a CI check
    or an observable fact (a file, symbol or behaviour in backticks) that can
    be checked on the PR head, and none depends on a later unit landing. An
    item that cannot be checked on this unit's PR is medium.
6.  **Decisions.** Every `Decide before build` item has an owner and a
    default; every open question of the spec that touches a unit appears as
    one. A missing owner or default is medium; a spec question that no unit
    records is medium.
7.  **Rendered bodies.** Each rendered body says what its unit says and
    nothing else: same scope, same definition of done, same blockers and
    order, same decisions, with placeholder numbers (`#<U01>`) for blockers
    and unit ids for forward references. A body that drifts from its unit is
    high; a body that adds text the plan lacks is medium.
8.  **Interfaces present and consistent.** Every body has an `## Interfaces`
    block; every `Consumes` names a `Produces` of a direct or transitive
    blocker, in the same name form; no name is produced twice. A missing
    block or an unmatched name is high.
9.  **Steps complete, DoD item 1 present.** Every Step group has the `Write`
    line with its test path, the fenced test, the `Implement` line with its
    path, and one command: an explicit `Run` line, or the default design
    section 9.1 derives from the `Write` line. Definition-of-done item 1 is
    the tdd-order sentence. A missing part is high. A Step is complete when
    it has the test name, the behaviour and the expected values; it is not
    incomplete for leaving fixtures, arrange code, helpers or private
    exception types to the builder.
10. **Global constraints and review focus present.** Every body carries the
    plan's `## Global constraints` lines verbatim and a `## Review focus (this
    unit)` block whose every test name appears in its own Steps. Missing or
    altered is medium.
11. **Proportion.** Is the body no longer than the decisions the builder cannot make alone: no fenced test the signature and assertions already determine, no Implement line that restates the test, no Step a parametrized sibling covers, no prose table that should be test data?
    A fence that names unnecessary private or harness detail (a fixture, a
    conftest attribute, a private helper or a monkeypatch target) is a
    proportion finding, `medium`; names the public or shared contract
    requires are exempt.
    A proportion finding names the Step and the bytes it would remove; it is
    `medium` at most.

## Severity

high: the body cannot be filed as written; medium: it must change before
filing; low: optional, and never blocking.

Readiness questions ("what would a builder still ask?") are findings of the
`readiness` reviewer: a question a builder would have to ask before building
is a finding, and a blocking one is high only when its failure scenario
holds. A readiness finding names the requirement it breaks (a spec section,
an Interfaces line or an acceptance value) and a failure scenario; one
without both is low.

Readiness and proportion are an adversarial pair: a conflict between them is
resolved in favour of the shorter form that keeps the test honest, and the
elephant records that disposition.

A finding that the spec itself must change, not the units, is settled
`fix-design`: `review status` exits 4, `review-plan` runs `approve-spec --void`,
and the spec returns to `review-spec` for that range.

## What Is Not a Finding

*   A file a unit will create does not exist yet.
*   A unit's branch or issue number does not exist yet.
*   Wording that a builder can act on, even if it could be shorter.
