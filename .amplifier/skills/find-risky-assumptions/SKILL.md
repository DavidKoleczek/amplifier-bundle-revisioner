---
name: find-risky-assumptions
description: >-
  Surface the risky, unvalidated assumptions hidden inside a vision, product plan,
  proposal, solution write-up, spec, or design doc, and record any NEW ones in the
  project's risky-assumptions file. Use this whenever the user has a vision/plan/
  proposal artifact and wants to know what could be wrong, what is being taken for
  granted, what is risky or shaky, or what the author has not fully thought through —
  or asks to "find/surface/extract risky assumptions", "what are we assuming",
  "poke holes in this", "pre-mortem this", or to run the ReVisioner assumption pass.
  Examines the doc from feasibility, viability, and desirability angles (technical,
  practical, cost, operational, adoption) and appends only assumptions not already
  captured, without ever changing existing risk levels. This skill only FINDS and
  records assumptions; de-risking them happens in a separate skill.
---

# Find Risky Assumptions

A vision document is a bet. It commits to building something, and every commitment
rests on things the author believes are true but has not proven. Those beliefs are
**assumptions**. The dangerous ones, the risky and unvalidated, are what sink a
project six months in. This skill reads a vision and surfaces those assumptions
*before* anyone spends effort building on them, so a later de-risking pass can test
each one.

Your job here is narrow and specific:

1. Read the vision deeply and understand what "success" actually requires.
2. Find the risky assumptions, looking from **many angles** so the set is complete.
3. Record **only the ones not already captured** in the risky-assumptions file, each
   with a fresh unique id and a risk score.

You are **not** de-risking, researching, or testing anything here. You are **not**
re-scoring or editing assumptions that already exist. You add what is missing and stop.

---

## Files and paths

| Purpose | Default path | Notes |
|---|---|---|
| Vision (input) | `./.amplifier/revisioner/vision.md` | The artifact to analyze. If the user names a different doc, use that. |
| Risky assumptions (output) | `./.amplifier/revisioner/risky-assumptions.yaml` | The file you append to. It may not exist yet, or may already hold entries. |
| Template / reference | `./risky-assumptions.yaml` (repo root, if present) | Example of the exact shape. Read only — never write here. |

> The output file is machine-maintained. Its shape is a top-level YAML list of two
> sections — `assumptions_related_to_current_vision` and
> `assumptions_related_to_past_visions`. New assumptions you find from the current
> vision go under **`assumptions_related_to_current_vision`**.

Each entry looks like:

```yaml
- id: RA-K7m2Qx          # "RA-" + 6 base62 chars (0-9 a-z A-Z), unique in the file
  assumption: The current system can handle a 50% increase in load without degradation.
  risk: 0.30             # 0.00–1.00 — importance/stakes only: how much success depends on this
  confidence: 0.0        # −1.00…+1.00 — signed belief it holds; born at 0.0 (untested)
```

Two **independent** axes, and this skill only ever sets the first one meaningfully:

- **`risk`** — *importance/stakes only.* How much the vision's success depends on this
  assumption being true. It does **not** fold in how proven the belief is. `0.00–1.00`.
- **`confidence`** — *signed belief that the assumption holds,* `−1.00…+1.00`: `+1` =
  confident it holds (validated → de-risked), `0` = untested / no evidence, `−1` =
  confident it does **not** hold (invalidated → risk realized). Magnitude is evidence
  strength, sign is direction. **New assumptions are always born at `0.0`**; the separate
  de-risking skill is what moves confidence away from zero.

---

## Workflow

### Step 1 — Read the vision and model "success"

Read the whole vision. Do not skim. Then write yourself a short **success model**: a
few bullets naming what must be true for this vision to succeed — the promised
outcomes, the named mechanisms it relies on, the external systems/people/permissions
it depends on, the numbers it asserts. Every risky assumption is something that, if
false, breaks one of these. Holding the success model in mind is what lets you find
the *underlying* assumptions rather than surface nitpicks.

### Step 2 — Load what's already captured

Read the output file if it exists. Collect the existing `assumption` statements (from
**both** sections). These are off-limits: you will not duplicate them and you will not
touch their `risk` or `confidence` fields. If the file is missing, you are starting
from an empty set. Note existing ids so new ones do not collide (the helper script
handles this automatically).

### Step 3 — Hunt from many perspectives (this is the core)

A single read-through finds the obvious assumptions and misses the ones that matter.
Completeness comes from deliberately re-reading the vision through **different lenses**,
each of which asks a different question. Work through every lens below. For each, ask:
*"What is the author taking for granted here that could turn out to be false?"*

The three primary lenses (every vision should be checked against all three):

- **Desirability** — *Do the intended users actually want this, enough to change what
  they do?* Assumes the problem is real and painful, that this solution fits how people
  work, that anyone will adopt it, that the value is perceived as promised.
- **Feasibility** — *Can it actually be built and made to work?* Assumes the technology
  can do it, the integrations/dependencies exist and behave as needed, performance and
  scale hold, the required access/permissions/data are available, the team has the
  skill and time.
- **Viability** — *Does it survive contact with cost, policy, and time?* Assumes the
  cost is acceptable, it fits organizational/legal/security constraints, it can be
  operated and maintained, and it keeps paying off rather than becoming a burden.

Then sweep the cross-cutting dimensions the user cares about — **technical, practical,
cost, operational, adoption, dependency, and scope** — plus a **pre-mortem** ("it's
six months later and this failed — why?") and a **language-tell** scan (hedges like
"just", "simply", "obviously"; unquantified claims; "users will…"; numbers with no
basis; work quietly handed off to "the system" or "the model").

For the full catalog of angle-by-angle prompting questions and language tells, read
`references/perspectives.md`. Use it — it is what keeps the pass from being shallow.

> For an especially thorough pass on a large or high-stakes vision, you can dispatch
> parallel sub-agents, one per primary lens, then merge and de-dupe their findings.
> Optional — the inline lens sweep above is the default.

### Step 4 — Consolidate, de-duplicate, and filter

From your raw candidates:

- **Merge near-duplicates** into one sharply-worded assumption.
- **Drop** anything already in the file (Step 2), and anything that is not genuinely
  risky — established fact, or so minor its falsity wouldn't matter.
- **Keep** each as an atomic, falsifiable, declarative claim (see the quality bar
  below). If you cannot state it as something a later spike could test, sharpen it.

### Step 5 — Score risk (stakes only)

Set `risk` between `0.00` and `1.00` = **how much the vision's success depends on this
assumption being true.** This is *stakes alone* — do **not** discount it for how likely
you think the assumption is to hold. That belief lives on the separate `confidence` axis
and is the de-risking skill's job. Ask only: *if this turned out false, how much of the
vision collapses?*

Anchors:

| Risk | Meaning |
|---|---|
| `0.85–1.00` | High-risk — if false, the vision largely fails. Core mechanisms and external permissions/policy you don't control often land here. |
| `0.55–0.80` | Important — its failure would seriously threaten the vision. |
| `0.30–0.50` | Matters, but the vision could absorb or route around its failure. |
| `0.05–0.25` | Minor — worth recording, but low consequence if false. |

Judge each assumption on its own stakes; don't force a spread. Do **not** set
`confidence` — the writer stamps every new assumption at `0.0` (untested).

### Step 6 — Write the new assumptions

Use the helper script — it generates collision-free `RA-` + base62 ids, stamps
`confidence: 0.0` (untested), appends under the current-vision section, and leaves
every existing entry (its `risk` and `confidence`) untouched.

Prepare a JSON array and run:

```bash
python3 .amplifier/skills/find-risky-assumptions/scripts/add_assumptions.py \
  --file ./.amplifier/revisioner/risky-assumptions.yaml \
  --input /tmp/new_assumptions.json
```

where `/tmp/new_assumptions.json` is:

```json
[
  {"assumption": "Adding EasyAuth to SWA is allowed in our Azure subscriptions.", "risk": 0.95},
  {"assumption": "Target users will adopt a new CLI over their current dashboard.", "risk": 0.6}
]
```

If there are **no** new assumptions (everything is already captured), do not write —
report that the file is already complete for this vision.

Run `python3 .../scripts/add_assumptions.py --help` for all options (e.g. adding to the
past-visions section). If Python or the script is unavailable, edit the YAML by hand
following the exact shape above — but then you must generate unique base62 ids yourself
and take care not to disturb existing entries.

### Step 6b — Stamp the vision fingerprint

The ledger's assumptions are bets *this* version of the vision makes. Record a hash of
the vision into the ledger so a later check-in can detect that the vision has since
changed and the ledger is stale:

```bash
python3 .amplifier/skills/vision-check-in/scripts/stamp_vision.py \
  --file ./.amplifier/revisioner/risky-assumptions.yaml \
  --vision ./.amplifier/revisioner/vision.md
```

Always run this after any write in Step 6 (and it's harmless to re-run when nothing was
added). Without it, `vision-check-in` cannot tell a fresh ledger from one built against
a since-edited vision.

### Step 7 — Report

Tell the user, briefly: how many new assumptions were added (with their ids and risk),
how many existing ones were left untouched, and — valuably — which lenses surfaced the
new ones. If you deliberately dropped candidates as non-risky or duplicate, say so in a
line. Keep it tight.

---

## What makes a good risky-assumption entry

A strong entry is **atomic, declarative, falsifiable, and risky.**

- **Atomic** — one claim. Split "the API is fast and cheap" into two.
- **Declarative** — a statement taken for granted, not a question. Write the belief the
  author is holding, phrased so it *could* be true or false.
- **Falsifiable** — a later spike could gather evidence for or against it. If it can't
  be tested, it's an opinion, not an assumption.
- **Risky** — its falsity would threaten the vision. Trivia doesn't belong.

**Examples**

Input (from a vision): *"The tool will simply call the model to triage the fleet, and
users will love having triage automated."*

- Good: `The model can reliably classify session state well enough that operators trust its triage.` (feasibility; testable via a spike)
- Good: `Operators want triage automated rather than skimming sessions themselves.` (desirability; the "users will love it" tell)
- Bad: `The tool calls a model.` — not risky; it's a stated design fact, not an unproven belief.
- Bad: `Will the model be accurate?` — a question, not a declarative assumption. Rewrite as the belief above.

Input: *"We'll add EasyAuth to the static web app for login."*

- Good: `Adding EasyAuth to SWA is permitted by our Azure subscription's policies.` (viability/permission; high risk, external and unproven)
- Bad: `EasyAuth is a good idea.` — subjective, not falsifiable.

---

## Guardrails

- **Additive only.** Never modify, re-score, re-word, or reorder existing entries.
  De-risking and re-scoring live in other skills.
- **No duplicates.** Check against both sections before adding.
- **Don't invent to fill a quota.** If a lens yields nothing new, that's fine. A short,
  sharp set beats a padded one.
- **Stay in scope.** You find and record assumptions. You do not research or test them,
  and you never move `confidence` off `0.0` — every new assumption is born untested.
