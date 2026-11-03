---
name: judges
license: Apache-2.0
effects: external
effect_kinds: [start-session, state-store, github-write]
disable-model-invocation: true
description: Runs one judge panel over a review round and posts the settled findings.
---

# judges

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

## What it does

`/superegm:judges <question.md> [--evidence <paths...>]` convenes one judge
panel over a question file: three models from two vendors (`fable` and `opus`
through the `superegm:judge` adapter, GPT-6 Astra through the claudex-loop
runner), each answering every question by option id, in rounds, until every
question converges or the cap of 5 rounds. Typed by the owner, the panel is
**advisory**: you report the verdict and apply nothing. In leavemealone-mode
the calling skills (review-spec, review-plan, plan, wave) run the same helper
subcommands and apply each converged answer themselves; this skill never does.

The helper records and judges; this conversation dispatches. The helper never
dispatches a judge.

## Inputs

*   **`QuestionFile`**: absolute path of the question file. Grammar:
    `## Q<n> <question>` followed by two or more `- (<id>) <option>` lines; a
    file may hold several questions.
*   **`Evidence`** (optional): files the judges may read besides the question
    file. Nothing else is in scope for them.

`<HELPER>` = `${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`; every
`superegm ...` line below runs as `python3 '<HELPER>' ...`, one command per
Bash call, absolute paths in single quotes, no chaining. `<STORE>` is the
config's `artifacts_dir`.

## Steps

1.  **Open the card.** `superegm runcard open --skill judges --artifact
    '<QuestionFile>'` prints `<CARD>`. Every helper call below carries
    `--runcard <CARD>`.
2.  **Open the panel.** `superegm judges open --question '<QuestionFile>'
    --evidence '<path>' ... --runcard <CARD>` checks the grammar, records the
    file's sha256, the evidence hashes and the judges from
    `config.judges.members`, prints the panel id `<PANEL>` and writes
    `<STORE>/judges/<PANEL>/round-1/brief.md`. A refusal (`judges: question
    file: <reason>`) is shown to the user verbatim; fix the file and open again.
3.  **Run one round** (`<n>` = 1, then the next):
    1.  **Astra first**, from this main conversation only, as one Bash
        command with `run_in_background: true`, exactly as
        `references/astra_judge.md` says (preflight, the launch line with
        `SUPEREGM_ROLE=goldfish`, the timeout). When it cannot run, record it
        at once: `superegm judges record --panel <PANEL> --round <n> --judge
        astra --not-run '<reason>' --runcard <CARD>`.
    2.  **The two Claude judges**, dispatched in one message, concurrently,
        each through the `superegm:judge` adapter (`omitClaudeMd: true`,
        tools `[Read, Grep, Glob]`) with the model override `model: fable`
        and `model: opus`, effort `max` where the Agent tool offers it, and
        the prompt: Read `<STORE>/judges/<PANEL>/round-<n>/brief.md` and
        answer as it says. Nothing else goes in the prompt: no summary of
        the question, no opinion, no history.
    3.  **Record each reply** verbatim. Save it to
        `${TMPDIR:-/tmp}/superegm-judges/<PANEL>/r<n>-<judge>.md` (outside
        the store; the helper copies it in) and run `superegm judges record
        --panel <PANEL> --round <n> --judge <judge> --verdict '<that file>'
        --isolation <clean | exposed:<what>> --runcard <CARD>`. The isolation
        comes from the reply's closing `saw:` line: `saw: none` is `clean`,
        anything else is `exposed:<what it saw>`. A reply with no `saw:` line
        is `exposed:no saw line`. The helper refuses a reply that does not
        parse or leaves an open question unanswered; dispatch that judge once
        more with the same prompt, and if it fails again record it with
        `--not-run '<reason>'`.
    4.  **Collect Astra** when its completion notice arrives: `superegm
        judges record --panel <PANEL> --round <n> --judge astra --result
        '<run folder>/result.json' --runcard <CARD>`. The helper decides
        `recorded` or `not run (<reason>)` from the record; never edit
        `result.json`.
    5.  **Diff.** `superegm judges diff --panel <PANEL> --round <n> --runcard
        <CARD>` writes `round-<n>/diff.md` (option ids and judge ids only)
        and, when questions stay open, `round-<n+1>/brief.md` with every
        prior verdict verbatim and every diff. The brief is the whole input
        of the next round: no one adds arguments between rounds, you
        included.
    6.  **Verdict.** `superegm judges verdict --panel <PANEL> --runcard
        <CARD>` prints the verdict JSON and exits 0 when every question
        converged, 2 otherwise. On 2 with `cap_reached` false, run the next
        round for the questions it lists as `open`; on 2 with `cap_reached`
        true, stop: the cap of 5 rounds is reached.
4.  **Report.** Show the user the verdict JSON's `questions` (option and
    round per converged question, positions per open one), `degraded`
    (true when fewer than two vendors answered in some round: say that the
    panel ran Claude-only and why), and each judge's model, effort and
    isolation per round. An `exposed:` isolation is reported as such, never
    hidden. Apply nothing: no settle, no ruling, no comment, no edit.
5.  **Close the card.** `superegm runcard close <CARD>`.

## Rules

*   Every judge reads only the question file and the listed evidence. Do not
    hand a judge the spec, the review reports or this conversation.
*   Round 1 is independent: the judges never see each other's answers before
    they answer. From round 2 the brief carries the prior verdicts and the
    diff, and nothing else is added.
*   `judges open` refuses a panel that exists; one panel per question file.
    A new question needs a new file.
*   `degraded` is a fact of the record, not a failure: the verdict stands,
    and the owner reads it knowing one vendor answered.
*   If the user asks you to apply, settle, post or rule on the verdict, say in
    one line that the panel is advisory and that the record is in
    `<STORE>/judges/<PANEL>/verdict.json`; the owner applies it.
