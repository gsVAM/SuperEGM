---
name: brainstorming
license: MIT
effects: working-tree
description: "You MUST use this before any creative work - creating features, building components, adding functionality, modifying behavior, or planning anything new, in software or out of it (a talk, a business, a renovation)."
---

<!-- From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: spec path docs/specs, the Units section, the review-spec gate, the brainstorm-brief lookup; builder check and the mockups section removed; the brief in the handoff's own directory (U32); the team brainstorm (U34). -->

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
A brief whose issue is closed is left in place and never offered. With no such brief, go on to "Your First Message".

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

**Ground to cover.** This is territory, not a script. Never read these
out as questions:

- what kind of thing this is, and what makes it special
- why now, and what success looks like to them
- goals, non-goals, and anti-goals (what would make this a failure even
  if it technically works)
- prior art: what they've seen elsewhere, loved or hated
- current state: what exists now, what they've tried
- the details they care about

**Questions that work** anchor in specifics: "Walk me through the last
time...", "If it could only do one of these well, which?", "What would
make you wince if I got it wrong?" A guess they can correct ("I'm
guessing this is because X keeps biting you?") often beats a question.

**Offer recon.** Once you have a bit of grounding and looking would help,
offer to go look: their codebase or project, their own files and data,
or the web. Say what you'd look for. They decide whether you go.

**Think wide privately.** Before you propose anything, come up with
several ideas and drop the weak ones, including any that fight what
they've told you about why. Show the comparison only when it helps them
decide.

**Spike to feel things out.** Agentic work is waterfall, but very, very
fast. A quick throwaway build is often the cheapest way to learn what
they want or whether something works. Offer one when it would help.
When they just want to spike, get out of the way. Spikes get no tests
or minimal ones, aren't bulletproof, and skip the plan, implementation,
and review process. Bring what the spike taught you back into the
conversation.

## Think Wide With a Team

This section runs only when the owner asks for it: they typed `/superegm:brainstorming --team`, or `brainstorm.team` is true in `.superegm/config.json`.
Reading the config yourself, a missing key reads false; `false` or a missing key is no ask, and you say nothing.
Only a value neither `true` nor `false` (a string such as `"yes"`, which the helper's `load_config` refuses) is worth a word: tell the owner it is malformed and go on without the team unless they typed `--team`.
A brainstorm not asked for runs neither teammates nor subagents: the skill as above, nothing more.
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
After the cartographer's spawn, tell the owner you are waiting on the cartographer: if its notes are not in, their message ten minutes or more after the spawn takes the fallback, and `fallback` typed takes it at once.
After the three's spawn, tell the owner you are waiting on the three: their message ten minutes or more after the spawn has you ask each silent one once, then write its approach `not reported`; there is no fallback once the three run.
Read your inbox at its next turn, with a second Bash `date` to tell how long it has been: the mailbox shows no arrival time, so a report in your inbox at that turn is merged, whenever it came: ten minutes counts only when the inbox holds none (a report within ten minutes is the ordinary case; one found later still proves the mailbox).
At a next turn less than ten minutes after the `date` with nothing in the inbox, answer what the owner asked, repeat the one-line notice and end your turn again.
`fallback` typed while waiting on the cartographer takes the fallback at once, whatever the time: send it a shutdown request first.
A next turn ten minutes or more after the `date` with no message from the cartographer means the mailbox is not working (a split-pane mode): send it a shutdown request and take the fallback.
After the shutdown request, once you take the fallback, a teammate's later message is not merged: the subagents' returns stand in its place.
A next turn ten minutes or more after the `date` with none from one of the three means one message asking it; still none at the turn after, write that approach `not reported`.
`fallback` typed while waiting on the three counts as the ten minutes passed: ask each silent one once now; it starts no fallback.
Until the design is written, a report found after an approach is written `not reported` replaces that line.
A `name: cartographer` spawn that returns in the same turn ran as a subagent: its return is the fallback's first return, so do not wait; go on with the fallback.

**The fallback.** With teams off, under `-p` or in a split-pane mode, the same four run as subagents with no mailbox: each dispatched without `name`, so no team forms.
The cartographer first; its returned notes go into the other three's prompts, which run in one message and return together.
A question the notes do not answer goes on that subagent's `questions:` lines for the owner; no subagent but the cartographer reads code.

**The merge.** Put the approaches side by side, and make one deduplicated question list ranked by how much the answer changes the build.
Ask the owner those questions one at a time, as the conversation does.
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

## Size the Work

Once you understand what they want, pick a size and say it in plain
words. They can override it.

| Size | The full description | Then |
|------|----------------------|------|
| A quick, clear task | the request itself | do it |
| A small change | in chat | build it through the normal workflow |
| A project with a written design | a written design document | `/superegm:review-spec`, typed by your human partner, then `/superegm:plan` |

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
- a final `## Units` section, the last H2 of the document: one row per
  buildable unit (id, title, blocked by)

**Where it goes:** in a software repo,
`docs/specs/YYYY-MM-DD-<topic>-design.md`, committed.
Otherwise, ask. Your human partner's preferences override both.

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

After a project's document is approved, the next step is
`/superegm:review-spec`, typed by your human partner; invoke no skill.
</HARD-GATE>

## Red Flags

| Thought | Reality |
|---------|---------|
| "I'll offer options to save them effort" | Options steer. Ask them to describe it first. |
| "I'll fill in sensible defaults" | Good. Say them out loud. A default they never heard is one they couldn't reject. |
| "I should explain the process first" | Ask your question. The process shows itself. |
| "They said 'sounds good' to the idea" | Approval covers what you showed them. A description you haven't written isn't approved. |
| "The spike works, I'll keep building on it" | Keeping it is a new request. Back through the gate. |
