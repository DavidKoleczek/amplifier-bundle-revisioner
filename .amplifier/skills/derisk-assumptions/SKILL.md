---
name: derisk-assumptions
description: >-
  De-risk the risky assumptions in a vision by running spikes. Given the
  revisioner risky-assumptions.yaml, this designs a spike for each open
  assumption (literature/evidence search, hands-on trial, or a fresh empirical
  investigation), runs the spikes in parallel isolated workspaces, captures every
  artifact under .amplifier/revisioner/data/<id>/, and updates each assumption's
  signed confidence from the evidence gathered. Use when the user wants to
  validate/invalidate assumptions, "run spikes", gather evidence, or "de-risk" a
  plan. It never touches the risk (stakes) axis — only confidence.
---

# De-risk assumptions

A risky assumption is an open bet the vision is making. **Risk** is the stakes —
how much the vision's success depends on the bet being true — and it does not move.
This skill moves the *other* axis: **confidence**, the signed belief that the
assumption actually holds, earned from evidence. You de-risk an assumption by
running a **spike**: the cheapest piece of real work that produces evidence for or
against it. Spikes run in parallel, isolated workspaces so one cannot corrupt
another, and every scrap of data they produce is kept for later drill-down.

## The two axes (read once)

| Field | Range | Meaning | Who moves it |
|---|---|---|---|
| `risk` | `0.00 … 1.00` | Stakes only — how much success depends on this being true. | The find skill. **Not this skill.** |
| `confidence` | `−1.00 … +1.00` | Signed belief it holds. `+` holds, `−` does not, magnitude = evidence strength. Born at `0.0`. | **This skill.** |

Outcomes stated in confidence terms:

- **Validated** → push confidence **positive**. The bet looks true; the risk is not
  being taken. The assumption is de-risked.
- **Invalidated** → push confidence **negative**. The bet looks false; **the risk has
  been realized** — surface this loudly, it is the whole point.
- **Inconclusive / (conditionally) unknowable** → leave confidence near `0.0` and
  attach a `derisking:` block naming what was tried and what would unblock it.

## Files & paths

| What | Path |
|---|---|
| Vision (context for what "holds" means) | `./.amplifier/revisioner/vision.md` |
| Ledger (read + update) | `./.amplifier/revisioner/risky-assumptions.yaml` |
| Per-assumption data (all spike artifacts) | `./.amplifier/revisioner/data/<id>/` |
| Per-spike run-state (for the check-in skill) | `./.amplifier/revisioner/data/<id>/status.json` |
| Confidence writer | `scripts/update_confidence.py` |
| Spike design + isolation + scoring depth | `references/spike-playbook.md` |

---

## Workflow

### Step 1 — Load the ledger and the vision

Read `risky-assumptions.yaml` and `vision.md`. If the ledger is missing, stop and
tell the user to run **find-risky-assumptions** first — this skill updates existing
entries, it does not invent them. The vision is essential context: an assumption
only "holds" *relative to what the vision needs from it*.

### Step 2 — Select which assumptions to de-risk

Default target = every **open** assumption: `confidence` at or very near `0.0`
(untested), across **both** sections. Honor an explicit user scope instead when given
(e.g. "just derisk RA-45aB21" or "the top 3 risks").

**Prioritize** by where evidence matters most: sort by `risk` descending, breaking
ties toward assumptions with the least evidence (`|confidence|` smallest). Skip
anything already strongly resolved (`|confidence| ≥ 0.8`) unless the user asks for a
re-spike. Confirm the selected set (ids + one-line each) before spending real work.

### Step 3 — Design a spike per assumption

For each target, design the cheapest spike that yields decisive evidence. **Bias to
first-hand evidence**: the goal is to *observe reality*, not to collect opinions about
it. Prefer, in order:

1. **Fresh empirical investigation** — generate or download real data, run the
   model/benchmark/simulation, measure against the kill criterion. A real observation.
2. **Hands-on trial** — actually try the thing: run the command, hit the API, build a
   throwaway prototype, check the real permission/quota/config. The system's own output.
3. **Evidence search** — only when the claim is already settled by *primary* empirical
   work you can inspect: peer-reviewed results, datasheets/benchmarks with a stated
   method, standards, hard vendor limits. A search spike must surface primary evidence,
   not summaries **about** evidence.

Reach for a lower rung only when a higher one is genuinely too costly or impossible, and
say so in the plan. **Blog posts, marketing, analyst/consulting reports, forum
anecdotes, and LLM say-so are not evidence** — at most they point you toward a primary
source you must then verify yourself. See the evidence hierarchy in
`references/spike-playbook.md §2`.

Write each plan to `./.amplifier/revisioner/data/<id>/spike-plan.md` **before**
running it: the claim, what evidence would confirm vs refute, the method, the
**evidence grade you intend to obtain** (see Step 5), and what "blocked" would look
like (what access/tool/data you'd be missing).

### Step 4 — Run the spikes in parallel, each isolated

Run spikes **concurrently**, one isolated workspace each, so they cannot collide:

- Use a **git worktree** when the spike needs this repo's code
  (`git worktree add ../revisioner-spike-<id> HEAD`), and remove it when done.
- Use a **fresh temp dir** (`mktemp -d`, or a `work/` subdir inside the data dir) for
  self-contained spikes — research, data generation, model runs.

Delegate each spike to its own sub-agent so they truly run in parallel and keep their
noise out of this context. Launch them in a single batch:

```
delegate(agent="self", model_role="research",
  instruction="Run the de-risking spike for assumption <id>.\n"
    "Assumption: <verbatim text>\n"
    "Vision context: <1-3 sentences from vision.md on what this must enable>\n"
    "Spike plan: <the plan from Step 3>\n"
    "Work in an isolated workspace (git worktree off HEAD if you need this repo's "
    "code, else a mktemp -d dir). Do the real work — search, try it, or measure. "
    "Capture EVERYTHING into ./.amplifier/revisioner/data/<id>/: raw sources, "
    "scripts, command output/logs, downloaded or generated data, screenshots. "
    "Then write findings.md (evidence -> reasoning -> conclusion) and return a JSON "
    "verdict: {\"id\":\"<id>\", \"confidence\": <signed -1..1>, "
    "\"derisking\": [ {\"approach\":\"...\",\"needs\":\"...\",\"blocked\":true} ] } "
    "(include derisking ONLY if blocked/inconclusive). Clean up any worktree you add.")
```

Scale concurrency to the host — batch large sets (a handful at a time) rather than
launching dozens at once. Each sub-agent owns exactly one id's data dir; they never
write to the ledger.

**Mark run-state as you go.** Because spikes run concurrently and the **vision-check-in**
skill reports on live progress, stamp each id's run-state to
`./.amplifier/revisioner/data/<id>/status.json` — otherwise `confidence: 0.0` is
ambiguous between *untested*, *running now*, and *blocked*. Write `running` the moment
a spike launches:

```bash
printf '{"state":"running","updated":"%s"}\n' "$(date -u +%FT%TZ)" \
  > ./.amplifier/revisioner/data/<id>/status.json
```

The final state is set in Step 6 from each verdict: `done` when confidence moved on
evidence, `blocked` when every `derisking` approach came back `blocked: true`.

### Step 5 — Score confidence from the evidence

Convert each spike's findings into a **signed** confidence. Sign = direction the
evidence points; magnitude = how strong/direct it is. **Magnitude is capped by the
grade of evidence you actually obtained** — you cannot buy certainty with weak sources:

| `|confidence|` | Evidence grade (the *ceiling* for that grade) |
|---|---|
| `0.85 – 1.00` | **Primary, first-hand:** you ran it on real data and measured it; a replicated study you inspected; authoritative policy read at the source. |
| `0.55 – 0.80` | One solid first-hand trial, or a single primary source with a stated method. |
| `0.25 – 0.50` | **Ceiling for secondary/indirect** — a reputable summary of primary work, or thin/single-sample/confounded first-hand data. |
| `0.00 – 0.20` | Inconclusive, or only weak sources exist (blog/marketing/analyst report/forum/LLM say-so), or (conditionally) unknowable — attach a `derisking:` block. |

Then apply the sign: evidence the assumption **holds → positive**; evidence it **does
not hold → negative**.

**The cap is hard.** Secondary or opinion sources max out at `|0.50|` no matter how
many agree — hearsay does not compound into proof. To cross `|0.55|` you must have
touched the primary evidence yourself (measured it, ran it, or read the authoritative
source). Record the grade in `findings.md`; if the only support is a blog/report/model
opinion, the honest confidence stays `≤ |0.20|` with a `derisking:` block naming the
primary check that would settle it. Do not overstate: a quick trial is not `1.0`.

**Conditional unknowability.** If the spike couldn't resolve it, keep confidence near
`0.0` and record why + the path out. Every unresolved approach names exactly what
would make it knowable:

```json
{"id": "RA-45aB21", "confidence": 0.1,
 "derisking": [
   {"approach": "Query subscription policy assignments for EasyAuth", "needs": "read access to the subscription policy scope", "blocked": true}
 ]}
```

### Step 6 — Update the ledger (confidence only)

Collect the verdicts into one JSON array and write them with the helper. It matches
by `id`, sets `confidence` (and the optional `derisking` block), validates the range,
and **refuses to touch `risk`, `assumption`, ids, order, or section shape**:

```bash
python3 .amplifier/skills/derisk-assumptions/scripts/update_confidence.py \
  --file ./.amplifier/revisioner/risky-assumptions.yaml \
  --json '[{"id":"RA-45aB21","confidence":0.85},
           {"id":"RA-K7m2Qx","confidence":-0.7}]'
```

Verify the diff: only `confidence`/`derisking` on the targeted ids changed.

Then close out each id's run-state so the check-in skill sees it as settled — `done`
for a resolved spike, `blocked` for one whose approaches are all blocked:

```bash
printf '{"state":"done","updated":"%s"}\n' "$(date -u +%FT%TZ)" \
  > ./.amplifier/revisioner/data/<id>/status.json
```

### Step 7 — Report

Summarize per assumption: id, one-line claim, the spike run, confidence **before →
after**, and the headline finding — with a pointer to `data/<id>/findings.md`. Call
out the two things that matter most: assumptions now **invalidated** (risk realized)
and assumptions still **unknowable** (with the `needs:` to unblock them).

---

## Guardrails

- **Confidence only.** Never modify `risk`, `assumption` text, ids, ordering, or the
  section structure. Risk is stakes and belongs to the find skill.
- **Evidence or nothing.** Confidence moves *only* on real evidence a spike produced.
  No guessing a number from intuition; an un-run spike leaves confidence at `0.0`.
- **Empirical over hearsay.** First-hand observation (you measured it, ran it, or read
  the authoritative source) beats anyone's *description* of it. Blog posts, marketing,
  analyst/consulting reports, forum anecdotes, and LLM say-so are leads, not evidence:
  they can only cap confidence at `|0.50|`, and alone they cap it at `|0.20|`. Crossing
  `|0.55|` requires primary evidence you touched yourself. Record the grade in
  `findings.md`.
- **Keep all the data.** Everything a spike touches lands under
  `.amplifier/revisioner/data/<id>/` so it can be audited and drilled into later.
- **Isolate every spike.** Separate worktree or temp dir per spike; clean up worktrees
  afterward. No spike may depend on or clobber another's workspace.
- **Sign honestly.** Negative confidence (invalidated) is a success of the process —
  report it as prominently as validation.
- **Unknowable is conditional.** Never write it off as a dead end; record the
  `approach`/`needs`/`blocked` path that would make it knowable.
