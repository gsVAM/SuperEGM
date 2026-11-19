---
name: brainstorming
license: MIT
effects: working-tree
description: "You MUST use this before any creative work - creating features, building components, adding functionality, modifying behavior, or planning anything new, in software or out of it (a talk, a business, a renovation)."
---

<!-- From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: spec path docs/specs, the builder check, the Units section, the review-spec gate, the brainstorm-brief lookup; the brief in the handoff's own directory (U32); the team brainstorm (U34); the triage section offered (U39); the SDLC workflow step (U64); the chain offered after doctor passes, nothing written outside the repository (U71); the reference documents offered once in the SDLC workflow step (U75); the visual companion restored, its session directory .superegm/brainstorm/ (U83); the triage fields, the red flags and the conversation examples moved whole into references/ (U83). -->

# Brainstorming

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

You are very good at building. You build what you believe your human
partner wants, and that belief is usually thinner than it feels. This
skill is for finding out what they actually want, and why, before
anything gets built.

People often haven't finished working out what they want. Good questions
help them think it through. When you understand the why, you make the
hundred decisions they never mention the way they would have made them.

## First: What Do You Actually Know?

Before you reply, ask yourself: what do I know about what they want, and
why?

- **Everything that matters is in the request** ("make the icon cornflower
  blue"). This is a quick, clear task. Do it, and say what you did.
- **Something non-trivial is missing.** Start the conversation.

## First: Is There a Brainstorm Brief?

In a repository with `.superegm/config.json`, look before you ask anything. Read `artifacts_dir` from that file. Every handoff in that store whose `state.json` has no `closed_at` may hold `foreman/*.brainstorm.md` files, in the handoff's own directory. Each is the brainstorm brief of a unit the owner stopped for redesign.
For each brief, take the unit id from its file name (`<unit>-<decision id>.brainstorm.md`); the brief counts only when `foreman/<unit>.json` carries `stopped.brief` naming it. Take the unit's issue number from that handoff's `state.json` and read the issue's `state` with `gh api repos/<repo>/issues/<n>`, `<repo>` being `repo` in `.superegm/config.json`.
For a brief of a unit stopped for redesign whose issue is still open, start from the brief: say so in one line, naming the handoff and the unit, and read what the owner asked, the findings and the deviations before your first question; the brief carries no range, so read the unit body's `Spec:` range at the sha that line cites (the `Spec:` range, never the checkout's bytes).
A brief whose issue is closed is left in place and never offered.
If `.superegm/brainstorm.md` exists, read it at the start too, before you go on, with or without a brief: the owner's questions for every brainstorm, not the per-decision brief. Work them in one at a time as your questions after the first message.
With no such brief, go on to "Your First Message".

## Your First Message

Your first message is two things, in this order:

1. One line letting them know that if they'd rather skip the questions and
   have you just start, they can say so. If they take you up on it, this
   skill is done: state any significant how-it-gets-made choice
   (platform, language, medium) in one plain line, then do what they
   asked through the normal workflow.
2. One open question that gets them describing. Ask about a real moment
   or a concrete picture: "What's the moment you find yourself wishing
   this existed?" or "Tell me about the people who'll be in the room."

That's the whole message.

## The Conversation

Each message ends with one question: a single sentence with no list of
example answers hanging off it. Use plain language, pitched just a little
above where your human partner is. Match their vocabulary; never use
process jargon.

Be clear and concise. Lead with what matters. Avoid jargon. When you
report what you found, give them the most important findings and offer
the rest.

**Get them describing.** Open questions come first. Their own words carry
intent that your options can't. Offer a short menu only when they're
stuck. When they say "just guess" or "what do you think?", propose
something concrete.

**How it gets made.** Every project rests on choices about medium, tools,
materials, and resources: the platform, programming language, and
libraries for an app; the medium for a piece of art. Find out early which
of those choices they want to make, which they're handing to you, and what
they already have to work with. Someone with strong views or skills will
want to talk it through. Someone counting on you needs sensible defaults,
said in plain words. When there's existing work, build on what it already
uses. Any choice you make goes in the design as your call, never as
something they agreed to.

**Ground to cover.** Territory, not a script, never read out as
questions: what it is, why now, goals and anti-goals, prior art, the
current state, the details they care about; the list is in
`references/conversation-craft.md`.

**Questions that work** anchor in specifics; examples are in
`references/conversation-craft.md`. A guess they can correct often beats
a question.

**Offer recon** once looking would help; they decide whether you go
(`references/conversation-craft.md`).

**Think wide privately.** Before you propose anything, come up with
several ideas and drop the weak ones, including any that fight what
they've told you about why. Show the comparison only when it helps them
decide.

**Show, don't tell.** Offer the visual companion (below) whenever seeing
would help more than reading: something they'll look at (a screen, a
page, a printout, a sign), a layout or arrangement, a flow or sequence of
steps, options that would look different from each other, a structure
easier to see than read (a diagram, a timeline, a map). Once they've
accepted, use it for mockups to react to, side-by-side options, and
throwaway prototypes they can click.

**Spike to feel things out.** A quick throwaway build is often the
cheapest way to learn what they want. Offer one when it would help; how
a spike runs is in `references/conversation-craft.md`.

## Think Wide With a Team

This section runs only when the owner asks for it: they typed `/superegm:brainstorming --team`, or `brainstorm.team` is true in `.superegm/config.json`.
Reading the config yourself, a missing key reads false; `false` or a missing key is no ask, and you say nothing.
Only a value neither `true` nor `false` (a string such as `"yes"`, which the helper's `load_config` refuses) is worth a word: tell the owner it is malformed and go on without the team unless they typed `--team`.
A brainstorm not asked for runs neither teammates nor subagents: the skill as above, nothing more; the builder check below is its own single dispatch and runs in every project brainstorm, team or not.
Run it once you know the topic well enough to state it in one line, before you propose anything.

**Teams or the fallback.** Read the variable with one Bash `echo "$CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"`.
The owner sets `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` for the brainstorm session alone, never in `settings.json`; you never set it.
Teams are on when it reads `1` in an interactive session; a headless session gets none (teams spawn no teammate under `-p`), and a split-pane teammate mode gives the teammates no mailbox.
Teams on: spawn the four as teammates. Teams off, under `-p`, or a split-pane mode that leaves you waiting: take the fallback below.

**The spawn.** Brief each as `references/teammates.md` says: the topic, the owner's words so far, the message form and its role's section.
First the cartographer: the Agent tool with `superegm:cartographer` and `name: cartographer`; it reads the code and sends you its notes.
Once the cartographer's notes are in, spawn the three in one message, the cartographer's notes in each prompt, each in `Mode: BRAINSTORM`:
the architect as `superegm:design` with `name: architect`, the skeptic as `superegm:zoom-out` with `name: skeptic`, the advocate as `superegm:comprehension` with `name: advocate`.
Each works one approach in its own context and reports it to you by message; they may message each other to challenge a claim, and ask the cartographer, never the code.

**The wait.** The same for each spawn: note one Bash `date` at the spawn and end your turn, with no `sleep`.
Before ending it, tell the owner what you are waiting on: a split-pane mode sends you nothing, so only the owner's message starts your next turn.
After the cartographer's spawn, tell the owner you are waiting on the cartographer: if it has sent you nothing at all, their message ten minutes or more after the spawn takes the fallback; if it has written but its notes are late, you ask it once and keep waiting; `fallback` typed takes it at once.
After the three's spawn, tell the owner you are waiting on the three: their message ten minutes or more after the spawn has you ask each silent one once, then write its approach `not reported`; there is no fallback once the three run.
Read your inbox at its next turn, with a second Bash `date` to tell how long it has been: the mailbox shows no arrival time, so a report in your inbox at that turn is merged, whenever it came: ten minutes counts per teammate, only for one whose report is not in (a report within ten minutes is the ordinary case; one found later still proves the mailbox).
At a next turn less than ten minutes after the `date` with nothing in the inbox, answer what the owner asked, repeat the one-line notice and end your turn again.
At such a turn with some of the three's reports in, merge the reports that are in, repeat the notice naming the silent ones, and end your turn again.
That partial merge only holds the reports side by side: rank no question and ask the owner nothing until all three are in or written `not reported`.
While you wait, a cartographer message that is not its notes (a question, a progress line) is no report: answer it if it asks, and keep waiting on its notes as above.
`fallback` typed while waiting on the cartographer takes the fallback at once, whatever the time, if its notes are not in your inbox: send it a shutdown request first.
The cartographer's notes already in your inbox win over `fallback` typed: merge them and spawn the three, and tell the owner the mailbox works.
A next turn ten minutes or more after the `date` with no message of any kind from the cartographer means the mailbox is not working (a split-pane mode): send it a shutdown request and take the fallback.
A next turn ten minutes or more after the `date` with the cartographer's notes not in but another message from it received: the mailbox works, so ask it once for its notes and keep waiting, with no fallback but `fallback` typed; tell the owner so.
After the shutdown request, once you take the fallback, a teammate's later message is not merged: the subagents' returns stand in its place.
A next turn ten minutes or more after the `date` with none from one of the three means one message asking it; still none at the turn after, write that approach `not reported`.
Then, after the asking message, tell the owner again: you have asked the silent ones, and their next message writes each still silent `not reported`; then end your turn.
`fallback` typed while waiting on the three counts as the ten minutes passed: ask each silent one once now; it starts no fallback.
Until the design is written, a report found after an approach is written `not reported` replaces that line.
A `name: cartographer` spawn that returns in the same turn ran as a subagent: its return is the fallback's first return, so do not wait; go on with the fallback.

**The fallback.** With teams off, under `-p` or in a split-pane mode, the same four run as subagents with no mailbox: each dispatched without `name`, so no team forms.
The cartographer first; its returned notes go into the other three's prompts, which run in one message and return together.
A question the notes do not answer goes on that subagent's `questions:` lines for the owner; no subagent but the cartographer reads code.

**The merge.** Put the approaches side by side, and make one deduplicated question list ranked by how much the answer changes the build.
Ask the owner those questions one at a time, as the conversation does; the written design records the owner's answers to the ranked questions beside the approaches.
The written design records the approaches under its `## Alternatives Considered`, with one line there: `team: on` or `team: off (subagents)`, and what the teammates or subagents reported seeing from their `saw:` lines.
Under `team: on` the cartographer's `saw:` line answers the probe: whether a teammate sees the project context and this plugin's SessionStart hook; write what it reported.
The cartographer's notes go in the design's current-state ground; the approach the owner chooses is the design's input.
When the brainstorm closes, send each teammate a shutdown request; a teammate may reject it, and the session's end ends it then. A resumed session has no teammates.
No teammate or subagent writes a file: the design is yours to write.

## Play It Back

Play back as you go. As soon as you understand one part well enough to
describe it (what it's for and who it serves, say, or how one piece
behaves), describe that part back in about 200-300 words, then return to
questions about the next part. Playback and questions alternate through
the whole conversation; the last chunk covers whatever is left.

Mark anything you're guessing as your guess; only what they said goes in
as theirs. End each chunk by asking what's wrong or missing.

Before you send a chunk, check it: does it describe something they'll
look at, like a page, a screen, a schedule, or a printout? If so, and
they haven't seen the visual companion offer yet, send the offer instead
(its own message, below) and hold the chunk for the next message. Once
they've accepted, put a mockup next to the description.

## Size the Work

Once you understand what they want, pick a size and say it in plain
words. They can override it.

| Size | The full description | Then |
|------|----------------------|------|
| A quick, clear task | the request itself | do it |
| A small change | in chat | build it through the normal workflow |
| A project with a written design | a written design document | run the builder check, design the SDLC workflow, then `/superegm:review-spec`, typed by your human partner, then `/superegm:plan` |

If it grows mid-task, stop, say so, and step up a size.

If this is really several independent projects, say so, agree on an
order, and brainstorm them one at a time.

## The Written Design

For a project, write a plain document a talented builder in the domain
could plan from without going back to your human partner. Cover:

- intent and the why
- goals, non-goals, anti-goals
- constraints
- the parts of the how they decided, as they decided them
- what's left to the builder
- the current state: what exists now, with the cartographer's notes
  when the team or its fallback ran
- `## Alternatives Considered`, ahead of `## Units`: the approaches weighed
  and why the chosen one won, with the `team:` line
  when the team or its fallback ran
- the owner's answers to the team's questions, under `## Alternatives Considered`,
  when the team or its fallback ran
- a final `## Units` section, the last H2 of the document: one row per
  buildable unit (id, title, blocked by)
- optionally, a `## Triage` section, its heading written exactly `## Triage`: offer it
  to your human partner and write it with them, never alone. It says which
  medium findings may stop blocking the wave. Without it triage is off and
  a high or medium blocks until fixed or ruled. It holds one `Unblock:`
  line and the run of `- ` lines directly after it; each line is one
  pattern, `field: value` pairs separated by `, ` that must all hold, and a
  pattern applies to mediums only. The fields are `reach`, `later`,
  `critical` and `verified`: their values and meanings, and a fenced
  example, are in `references/triage.md`; read it before you write one.
  Ask what they would be content to see deferred, and write only the
  patterns they say. Approval parses the section, refuses a malformed one
  with its line and freezes the patterns; editing it later needs a new
  approval.

**Where it goes:** in a software repo,
`docs/specs/YYYY-MM-DD-<topic>-design.md`, committed.
Otherwise, ask. Your human partner's preferences override both.

**Builder check:** once the design is written (after the team's synthesis,
in a team brainstorm), dispatch one fresh subagent with
`references/builder-check-prompt.md`, its `[DOMAIN]` and `[DOCUMENT_PATH]`
filled. Say a reviewer will read it first and you may come back once with
a few questions. Don't hand over the document until the check is back.
Sort what the builder asks into three piles:

- **Answered already** by the conversation or the project: put the answer
  in the document.
- **Minor:** a sensible builder could settle it without changing what gets
  built. Settle it yourself and mark it in the document as your call.
- **Theirs:** only your human partner can answer it, and the answer changes
  what gets built.
Bring the "theirs" pile in one message, most important first. Update the
document with their answers, then hand it over with a short list of calls
you made. One dispatch, never a loop. Commit the document's edits by path before the
SDLC workflow step and `/superegm:review-spec`, so the reviewers read the
checked text at `HEAD`. Without a subagent tool, read the document as that
builder yourself.

## Design the SDLC Workflow

Once a project's document is written and saved in git, with any edits
the builder check made, and before you name `/superegm:review-spec`,
design with your human partner the workflow that will review and build
it. It comes after the spec because most of the choices follow from it:
which reviewers it needs, which rules every agent carries, how many
rounds a review gets. A quick, clear task skips this step, as does a
brainstorm that ended without a spec. In Cowork, where the helper cannot
run, skip the walk and say only what the last paragraph says.

With no `.superegm/config.json`, offer `superegm init`; once they agree,
run it and walk them through the by-hand steps it prints. Then take the
areas one at a time, in this order. Each question is led by its
suggestion drawn from the spec and shows the current value, and the walk
changes only what the owner agrees to:

1. Reviewers: `reviewers.spec`, `reviewers.plan`, `reviewers.head` and
   `reviewers.integrate`, and any custom reviewer the spec calls for,
   written as `.superegm/reviewers/<id>.md` and shown to them before it is
   written.
2. Instructions: the `instructions` entries, then the reference documents.
   Reference documents (invariants, an architecture note, a glossary) are
   offered once, never required: offer once to draft or update the ones
   the spec's design implies (for example `invariants.md`,
   `architecture.md`), in this same session, under the configured `dir`
   or, with none, under `docs/reference/` with a `dir` entry added to
   `instructions` addressed to all four roles (`builder`, `foreman`,
   `reviewers`, `judges`). On their yes, draft each document from the
   spec and the code you already read and show each; area 5 saves them
   with the rest, so the approval freezes them. A no, or
   silence, records nothing and the step goes on; nothing later checks
   that the documents exist.
3. The round cap: `review.rounds`, or a `Rounds:` line in the spec.
4. The mode: normal or leavemealone (`mode`).
5. The builder: first show the MCP server names they already have, from
   the three places the helper reads (the repository's local scope and the
   user scope of `.claude.json`, and the repository's `.mcp.json`; a name
   in none of them is refused), then ask which the builder needs and which
   commands it may run. Then `superegm builder-setup`, each server name
   passed as `--mcp` and each command as `--allow`. Now commit the config, reviewer and
   reference-document changes of areas 1 to 5 on the current branch, so
   that doctor and the probe read what `HEAD` will freeze with the spec;
   the reference documents the owner said yes to at area 2 go in the
   same way: this session commits them with the step's commit.
6. `superegm doctor`: an exit of 0 passes. Otherwise show the failing
   lines, work through each with them, and commit each fix by path
   before you run doctor or the probe again. Then offer `doctor --probe`
   once: the probe makes a model call, so run it
   only when the owner agrees.
7. The chain, offered once, after doctor passes: on their yes, set `driver.chain` to
   `true` and commit it, so the checkout stays clean (no approval freezes
   it; the driver reads it live). Without their yes, leave it unset: an
   absent `driver.chain` reads `false`. The same question
   offers the driver's setup: it names the env file it would write
   (`~/.superegm/env`, mode `0600`, literal `KEY=value` lines: `PATH`,
   `CLAUDE_CONFIG_DIR` and the credentials the shell holds) and the root a
   tick's sessions would run in (the repository's checkout on the base
   branch), and one yes covers both. List every credential name, never a
   value: with `builder.app` its `private_key_env` alone, otherwise
   `builder.gh_token_env` alone, plus every `${NAME}` a `builder.mcp`
   server's `env` or `headers` values name.
   This step writes nothing outside the repository (`effects: working-tree`): the env file,
   `register` and `driver install` need a `driver` card on an approved
   spec, so they run at `/superegm:review-spec`'s approval step.

The owner may skip any area, or the whole step. A skipped area
records nothing, and you say once that `plan` and `wave`
refuse until doctor passes. In Cowork, say only, once, that `plan` and `wave` need `superegm doctor` to pass.

## The Gate

<HARD-GATE>
Nothing gets built until your human partner approves the full
description: in chat for a small change, the document for a project.
Building includes writing product code, scaffolding, installing
dependencies, creating projects, and invoking an implementation skill.
Reading and exploring are fine.

Two exceptions. If they opted out of the questions, the skill is done
and the gate goes with it. A spike they said yes to may be built; it
stays labeled throwaway, and keeping what it produced is a new request
that comes back through this gate.

After a project's document is approved, the next step is the
SDLC workflow design above (or its skip), then `/superegm:review-spec`,
typed by your human partner; invoke no skill.
</HARD-GATE>

## Red Flags

The thoughts that mean you are about to skip a step, each with the reality
that answers it, are in `references/red-flags.md`; read it when you catch
yourself rationalising.

## Visual Companion

A browser tab for showing mockups, diagrams, and prototypes: a tool, not
a mode. **Offer it just-in-time**, the first time one of the moments above
comes up, never upfront, as its own message with nothing else in it:

> "This might be easier if I show you. Want me to open a browser tab with some mockups?"

If they decline, stay in text and don't offer again unless they raise it.
Start the server only on their yes; when the brainstorm ends run
`bash scripts/stop-server.sh <session_dir>`, the session directory being
the parent of the `screen_dir` and `state_dir` that start-server.sh
printed. Where the helper cannot run (Cowork), loopback cannot be
reached (a remote or containerised session) or no browser opens, say so
once and stay in text.

**Per question, ask: would they understand this better by seeing it?**
If they accept, read `references/visual-companion.md` before starting the
server.
