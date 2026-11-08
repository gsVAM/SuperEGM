<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0. Added by SuperEGM (gsVAM), 2026: the team brainstorm's four briefs and their message form (spec section 6, amendment 13, U34). -->

# The Team Brainstorm's Briefs

Read from the brainstorming skill's `## Think Wide With a Team`. The lead (the owner's session) pastes
the dispatch below, the message form and one role's section into each of the four prompts; the same
prompts serve both modes, teammates with a mailbox and subagents without one.

## The dispatch

The lead hands each of the four the same four things, in this order:

1. the topic in one line;
2. the owner's words so far, verbatim, from the conversation that led here;
3. the message form below;
4. the role's section below.

The four run through their adapters, in this order:

- the cartographer: `superegm:cartographer`, first, alone; its prompt carries the four things above, with no `Mode`.
- the architect: `superegm:design` with `Mode: BRAINSTORM`.
- the skeptic: `superegm:zoom-out` with `Mode: BRAINSTORM`.
- the advocate: `superegm:comprehension` with `Mode: BRAINSTORM`.

The architect, the skeptic and the advocate are spawned only once the cartographer's notes are in, and
the cartographer's notes go into their spawn prompt verbatim, after the owner's words.

Each of the three prompts also carries this override, which wins over the persona and its adapter:
there is no target file to read and no standard to read first; there is no incomplete review to report: this is no review;
skip the persona's codebase search step and read no code: ask the cartographer (by message as a teammate; as a subagent, put the question on a `questions:` line);
report one approach in the message form, not the findings line: no severity, no finding ids;
the role's lenses below replace the persona's `Mode: BRAINSTORM` list where they differ.

The adapter's body sits in the system prompt and tells the agent to follow its persona, read the target and return findings;
so the override names the instructions it overrides, each by its words, and says this task sets them aside:
the adapter's "Before returning findings, read the target and every supplied standard" and "report an incomplete review instead of a verdict";
the persona's codebase searches (the zoom-out persona's "Perform codebase searches", its `Mode: BRAINSTORM` step 2, becomes an `ask cartographer:` message);
the persona's findings-line output. The spec puts this override in the brief, so the lead pastes it whole, word for word, into each of the three prompts.
The lead checks each report: a report not in the message form (a findings line, a severity, a finding id) gets one message asking for the approach in the message form;
as a subagent, or still not in the form after that message, the lead writes the approach it can read from the report and marks it `not in the message form`.

Every teammate writes no file: the helper is the store's one writer and the draft is the lead's.
A teammate may message another teammate to challenge a claim; it reports to the lead alone.

## The message form

One report per teammate, sent to the lead by message as a teammate, or as its return when run as a subagent:

```
approach: <one paragraph: the approach this role would build, and why>
costs: <one line: what it costs to build and to run, and what it gives up>
questions: <one question the owner must answer; one per line, as many lines as needed>
saw: <one line: whether you saw the project's CLAUDE.md, and whether you saw the SuperEGM SessionStart text (the using-superegm skill injected at your start)>
```

The cartographer sends no `approach:` or `costs:` lines: its report is `notes:` followed by its five headings (Concerns, Calls, Tests, Docs, Surprises), then its `saw:` line.
A teammate's question to the cartographer is one message opening `ask cartographer:` and one question; the cartographer answers each in one line, with the file and line.
As a subagent the cartographer's notes are its return, and the lead hands them on; there is no mailbox, so a question for it goes on `questions:` instead.

## Cartographer

You read the code; the other three do not. Read the newest handoff's `orient/map.md` first, when the store holds one for this tree, as your persona says.
Make no `orient` call: orient needs an approved spec and a run card, and a brainstorm precedes both.
Then report the five notes: where the topic's concerns live today, what calls what, what tests pin, what the repository's own docs say,
and the three things that would surprise a newcomer.
After your notes, stay for questions: answer "who calls X", "what covers Y" and the like, one line each, from the code.

## Architect

The architect designs against the notes: the shape of the build that fits the code as the cartographer found it.
Lenses: the components and their boundaries, the data and where it lives, what changes where the notes say the concerns live, what stays untouched,
and the scaling and cost limits of the persona's brainstorm mode. Where the notes are silent, ask the cartographer; never guess at the code.

## Skeptic

The skeptic is the zoom-out persona's brainstorm mode turned forward. Lenses: the failure modes of building this at all,
what the owner will regret in six months, and the cheapest alternative that gets most of the value (an existing tool, a smaller change, or nothing).
Its approach is that alternative, argued; its questions are the ones whose answers would kill or shrink the build.

## Advocate

The advocate takes the user's and the operator's day: what they see, type, wait for, at each step the build adds or changes.
Lenses: the first run and the hundredth, the error a person meets and what it tells them, and the operator's day: install, upgrade, failure and recovery.
Its approach is the one that makes that day shortest; its questions are the ones only the owner's users could answer.
