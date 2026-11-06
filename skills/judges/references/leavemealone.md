# Leavemealone-mode: the routing of a converged answer (design section 13.2)

The one routing table for `review-spec`, `review-plan`, `plan` and `wave`. Each row is one form of
`superegm judges question`, one option the judges may converge on, the helper command that applies it
(`Apply`) and what the skill does next (`Then`). `superegm` stands for `python3 '<HELPER>'`;
`<card>` is the skill's own run card, `<panel>` the panel id `judges open` printed, `<did>` the id
`decision open` printed for the unit's pending decision. No row approves or merges anything:
merge is human, in every mode.

| Form | Converged option | Apply | Then |
| --- | --- | --- | --- |
| `--review <id> --round <n>` | `finding upheld` | On a head only: `superegm decision rule --unit <U> --decision <did> --ruling "<fid> finding upheld" --by judges:<panel> --runcard <card>` (one call per finding). On a spec or plan review nothing is applied: the elephant fixes the artifact and settles the finding `fixed`. | On a head the `**Ruling:** <fid> finding upheld (fix it)` comment `decision rule` posts on the unit's issue; the builder fixes it in its next launch (`launch-builder`). |
| `--review <id> --round <n>` | `finding overruled` | `superegm review settle --review <id> --finding <fid> --disposition contested --judges <panel> --runcard <card>`; on a head also `superegm decision rule --unit <U> --decision <did> --ruling "<fid> finding overruled — <reason>" --by judges:<panel> --runcard <card>`, the reason the overrule option's text. | `superegm review status --review <id> --runcard <card>`: the next round, or the artifact is converged. On a head the `**Ruling:** <fid> finding overruled — <reason>` comment `decision rule` posts. |
| `--review <id> --cap` | `continue one bounded round` | `superegm review rule --review <id> --ruling continue --judges <panel> --runcard <card>` (once per cycle: the helper refuses a second). | The next round of the same review; at its cap again the panel is asked without this option. |
| `--review <id> --cap` | `one more round` | `superegm review rule --review <id> --ruling continue --judges <panel> --runcard <card>`, then `superegm decision rule --unit <U> --decision <did> --ruling "one more round" --by judges:<panel> --runcard <card>`. | `superegm launch-builder --unit <U> --round <n> --runcard <card>` for the next round (a head only). |
| `--review <id> --cap` | `accept the remainder` | `superegm review rule --review <id> --ruling accept --judges <panel> --runcard <card>` (a spec, plan or integrate review; refused on a head). | The artifact is converged by ruling: the skill's converged path (approve the spec; the unit's body is reviewed at its sha). |
| `--review <id> --cap` | `stop` | `superegm review rule --review <id> --ruling stop --judges <panel> --runcard <card>`; on a head also `superegm decision rule --unit <U> --decision <did> --ruling stop --by judges:<panel> --runcard <card>`, which labels and stops the unit. | End the invocation for that artifact with the record; the next invocation opens the next cycle (a head: the unit stays stopped). |
| `--review <id> --round <n>` | `redesign — <why>` | On a head only: `superegm decision rule --unit <U> --decision <did> --ruling "redesign — <why>" --by judges:<panel> --runcard <card>`, the sentence the option's own. | The unit is stopped for redesign with its brainstorm brief (`foreman/<unit>-<did>.brainstorm.md`); the `**Ruling:** redesign — <why>` comment names the brief and asks the owner to close the issue by hand once the re-planned unit is filed; the road back is the spec's §11: `/superegm:brainstorming` from the brief. |
| `--review <id> --cap` | `redesign — <why>` | On a head only: `superegm review rule --review <id> --ruling stop --judges <panel> --runcard <card>`, then `superegm decision rule --unit <U> --decision <did> --ruling "redesign — <why>" --by judges:<panel> --runcard <card>`, the sentence the option's own. | The unit is stopped for redesign with its brainstorm brief; the comment names it; the road back is §11's, as in the row above. |
| `--unit <U> --decision D<n>` | `(x)` | `superegm decide --unit <U> --decision D<n> --answer "(x)" --judges <panel> --runcard <card>`. | An unfiled unit: its plan line now carries `; answer: (x)` and its body is re-rendered, so `graph` and `scan` again. A filed unit: post the decision comment the helper wrote. |
| `--unit <U> --blocked` | `<option>` | `superegm decision rule --unit <U> --decision <did> --ruling "<option>" --by judges:<panel> --runcard <card>`. | The `**Ruling:** (<comment-id>) <option> — <reason>` comment `decision rule` posts on the unit's issue; for an `interface` deviation, post the same `**Ruling:**` with `gh issue comment` on every issue the `consumers:` line named. `relaunch` → `superegm launch-builder --unit <U> --round <n> --runcard <card>`; `stop the unit` → the wave skill's stop (the unit is labelled, never relaunched). |

## The panel sequence

The same five steps at every decision point of the four skills; the `judges` skill describes the
dispatch in full.

1. `superegm judges question <form> --runcard <card>` prints the question file's path and, for a
   builder's `interface` deviation, a second line `consumers: #<n> …` (every filed unit whose body
   consumes a name of the deviating unit). A refusal `question: <reason>` means there is nothing
   to ask (the CI finding, a low, a used `continue` on a spec or plan review whose bytes moved, or `relaunch`): take
   the one remaining path. A head whose `continue` is spent is asked `stop` and `redesign`, never refused.
2. `superegm judges open --question <path> --evidence <paths> --parent <card>` opens the panel
   under a child card of the skill's card and prints `<panel>`; the evidence is the artifact under
   review (the spec; the unit's body; on a head the round's `comments.md` and diff).
3. Dispatch the judges as the `judges` skill's step 3 says: Astra through the runner, the two
   Claude judges through the `superegm:judge` adapter, each reply recorded with
   `superegm judges record`, each round closed with `superegm judges diff`; no one adds arguments
   between rounds.
4. `superegm judges verdict --panel <panel> --runcard <card>` exits 0 when every question
   converged, 2 otherwise. Apply each converged question's option through its row above as it
   converges (`questions.Q<n>.converged`); a question still open at the cap of 5 rounds, or below
   `min_vendors`, stays with the owner: end the invocation naming the unconverged questions and
   `judges/<panel>/verdict.json`, and the owner rules by hand. A `redesign` converged on any
   question of a point-1 panel is applied last, with the first converged question's sentence, and
   ends the unit's rulings: the unit is stopped, so no other converged question is applied after it.
5. The record: `judges verdict` journals every converged question; `decision rule --by
   judges:<panel>` journals `Ruling (judges <panel>, leavemealone): …`, and `review settle`,
   `review rule` and `decide` journal their `by judges:<panel>` lines, so the owner can read and
   overturn any of them.
