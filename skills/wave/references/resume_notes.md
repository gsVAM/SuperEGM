<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by SuperEGM (gsVAM), 2026: a paragraph of the wave skill's entry, moved out of SKILL.md verbatim to keep its body under the 15,000-byte pin (the owner's ruling on #172, U88); the `unit_state` paragraph, moved out of SKILL.md for the same pin (the owner's ruling on #175, U93), all of it verbatim but its `loop_ended` sentence, which stays in SKILL.md (a test pins it) so that one copy exists; entry step 3's sentence on what `report` derives, moved out of SKILL.md verbatim for the same pin to make room for the entry's `doctor --probe` (U108, 1.3 design section 3.7), and what a failing `probe:` line is. -->

# Resuming: builders left running, and refusals

Open this at the entry, before step 5.

Builders a previous invocation left running report through `status --wait`'s
`exit` lines. Nothing recorded is launched, ruled or reviewed twice (`launch`,
`launch-builder`, `decision rule` and `foreman dispatch` refuse): take a refusal as fact, never retry it.

## A launched unit's state

A launched unit's `unit_state`, in order: `landed`, `stopped`, `pending`,
`idle`, `waiting proceed` (no slot; ask the owner to proceed again), CI-wait
`idle`, `clean`, else `active`; `active`/`clean` with an open respec: `waiting respec`; only `active` is dispatched. CI pending or absent
`ci_wait_minutes` (default 30) after the card saw the head: CI-wait `idle`;
a new head restarts it.

## What `report` derives

Entry step 3's `report`: It derives all from the store, the plan and the spec (refusing as `status` does on a spec changed since its approval); idle units come from this card alone.

## The entry's probe

Entry step 1's `doctor --probe`: a failing `probe:` line is one not ending in `ok` or `connected`; a probe its Bash timeout kills prints no `probe: session ok`, so the wave stops before any launch.
