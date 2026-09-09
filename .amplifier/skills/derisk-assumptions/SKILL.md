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

For each target, design the cheapest spike that yields decisive evidence. Pick the
kind that fits the claim (see `references/spike-playbook.md` for depth):

- **Evidence search** — find existing empirical results, benchmarks, docs, prior art,
  or authoritative policy that settle it.
- **Hands-on trial** — actually try the thing: run the command, hit the API, build a
  throwaway prototype, check the real permission/quota/config.
- **Fresh empirical investigation** — generate or download data, run a model or
  benchmark, measure. Whatever it takes to produce a real observation.

Write each plan to `./.amplifier/revisioner/data/<id>/spike-plan.md` **before**
running it: the claim, what evidence would confirm vs refute, the method, and what
"blocked" would look like (what access/tool/data you'd be missing).

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

### Step 5 — Score confidence from the evidence

Convert each spike's findings into a **signed** confidence. Sign = direction the
evidence points; magnitude = how strong/direct it is:

| `|confidence|` | Evidence quality |
|---|---|
| `0.85 – 1.00` | Direct, decisive proof (you ran it and saw it; authoritative policy; strong replicated results). |
| `0.55 – 0.80` | Solid but indirect, or a single trustworthy source/trial. |
| `0.25 – 0.50` | Suggestive — leans one way but thin or confounded. |
| `0.00 – 0.20` | Inconclusive / (conditionally) unknowable — attach a `derisking:` block. |

Then apply the sign: evidence the assumption **holds → positive**; evidence it **does
not hold → negative**. Do not overstate: a quick trial is not `1.0`.

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
- **Keep all the data.** Everything a spike touches lands under
  `.amplifier/revisioner/data/<id>/` so it can be audited and drilled into later.
- **Isolate every spike.** Separate worktree or temp dir per spike; clean up worktrees
  afterward. No spike may depend on or clobber another's workspace.
- **Sign honestly.** Negative confidence (invalidated) is a success of the process —
  report it as prominently as validation.
- **Unknowable is conditional.** Never write it off as a dead end; record the
  `approach`/`needs`/`blocked` path that would make it knowable.
