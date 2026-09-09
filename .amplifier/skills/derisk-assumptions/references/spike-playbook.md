# Spike playbook: turning an assumption into evidence

This is the depth behind Steps 3–5. A **spike** is the cheapest piece of real work
that produces evidence for or against one assumption. Cheap first: the goal is a
decisive signal, not a finished implementation. Prefer the smallest thing that could
change your belief.

---

## 1. Frame the claim before touching tools

For the assumption, write down (into `data/<id>/spike-plan.md`):

- **The claim, sharpened.** State it as something the world can prove false. "It'll
  scale" is not testable; "a single node sustains 500 req/s at p95 < 200 ms on our
  payload" is.
- **The kill criterion.** What observation would make you say *invalidated*? What
  would make you say *validated*? Decide both **before** you look, so the result can't
  be rationalized after the fact.
- **The relevance to the vision.** What does the vision actually need from this? An
  assumption can be true in general yet false at the scale/latency/budget the vision
  requires. Test it at the level the vision needs.
- **The blocked shape.** What access, tool, data, or credential could you be missing?
  Naming it up front is what lets you report *conditional unknowability* cleanly.

---

## 2. The evidence hierarchy — observe reality, don't collect opinions

Derisking earns confidence from **first-hand contact with reality**, not from what
sources *say* about reality. Grade every piece of evidence before it moves a number:

| Grade | What it is | Confidence ceiling |
|---|---|---|
| **A — Primary, first-hand** | You ran it on real/representative data and measured it; a replicated study whose method+data you inspected; authoritative policy read at its source. | `1.00` |
| **B — Primary, single/indirect** | One solid first-hand trial; one primary source with a stated, checkable method; a hard vendor limit from the datasheet. | `0.80` |
| **C — Secondary** | A reputable *summary* of primary work (survey paper, docs citing a study), or thin/single-sample/confounded first-hand data. | `0.50` |
| **D — Opinion / hearsay** | Blog posts, marketing, analyst/consulting reports, forum anecdotes, LLM say-so, "everyone knows". | `0.20` |

**The ceilings are hard.** Grade D and C cannot be stacked into certainty — ten blog
posts that agree are still grade D. To cross `|0.55|` you need grade A or B evidence you
obtained yourself. Grade D is a **lead**, never a verdict: its only legitimate use is to
point you at a primary source you then verify. Record each item's grade in
`data/<id>/sources.md` (or `findings.md`).

This is why the spike *types* below are ordered strongest-first — pick the highest grade
you can afford for the claim, and drop to a lower one only with a stated reason.

### a. Fresh empirical investigation (measure it) — reaches grade A
Best, and the default when the claim is quantitative or unpublished at the vision's
conditions.
- Generate or download representative data; run the model/benchmark/simulation;
  measure against the kill criterion.
- Note sample size, method, and confounders honestly. One run on toy data is grade C
  (*suggestive*, |0.25–0.50|), not proof — real/representative data at the vision's
  scale is what earns grade A.
- Keep the dataset, the script, and the raw results in `data/<id>/` so the number is
  reproducible later.

### b. Hands-on trial (just try it) — reaches grade A/B
Best when you can cheaply touch the real thing.
- Run the command, hit the API, check the actual permission/quota/config, wire a
  throwaway prototype, reproduce the workflow end to end on a small scale.
- The output of the real system is stronger evidence than any document. Save the exact
  commands and their raw stdout/stderr into `data/<id>/`.
- A trial that *fails to even set up* is itself evidence — often the "blocked" signal.

### c. Evidence search (does someone already know?) — grade A only if primary
Legitimate **only** when it surfaces primary evidence you can inspect: peer-reviewed
results with data/method, standards, RFCs, datasheets, hard vendor limits.
- A search that returns summaries, blogs, or reports has produced grade C/D — a lead to
  chase to its primary source, not a result. Don't score off it.
- Beware "true in the abstract" answers that dodge the vision's specific conditions.
- Record links/quotes verbatim and graded in `data/<id>/sources.md`.

---

## 3. Isolate every spike

Spikes run in parallel and must not collide.

- **Needs this repo's code** → git worktree:
  ```bash
  git worktree add ../revisioner-spike-<id> HEAD
  # ...run the spike inside it...
  git worktree remove ../revisioner-spike-<id> --force
  ```
  A worktree is a separate working dir on its own throwaway checkout — builds, edits,
  and dirty state stay off the main tree and off sibling spikes.
- **Self-contained** (research, data gen, model runs) → a fresh temp dir:
  ```bash
  work="$(mktemp -d)"      # scratch; copy keepers into data/<id>/
  ```
  or a `work/` subdir *inside* the data dir if you want the scratch kept too.
- One spike = one workspace = one `data/<id>/`. Never share scratch between spikes.
- Always clean up worktrees; leftover worktrees wedge later `git` operations.

---

## 4. What lands in `data/<id>/`

Keep everything — this dir is the audit trail and the input to any future re-scoring.

```
.amplifier/revisioner/data/<id>/
  spike-plan.md      # the claim, kill criterion, method, target grade, blocked-shape (Step 3)
  sources.md         # links + verbatim quotes, each tagged with its grade (A/B/C/D, §2)
  run/               # scripts, configs, commands actually executed
  output/            # raw stdout/stderr, logs, generated/downloaded data, screenshots
  findings.md        # evidence -> reasoning -> conclusion -> proposed confidence
  verdict.json       # {id, confidence, [derisking]} — the machine-readable result
```

`findings.md` is the human story; `verdict.json` is what feeds
`update_confidence.py`. Write both. **`findings.md` must state the evidence grade the
confidence rests on** (§2) — the number is only auditable if the grade behind it is on
the record. Never inline large data into the ledger — the ledger holds only the number;
the *why* lives here.

---

## 5. From findings to a signed confidence

Magnitude = strength/directness of evidence; sign = which way it points. **Magnitude is
bounded by the evidence grade from §2** — the grade sets the ceiling, the specifics of
the spike set where you land under it.

| `|confidence|` | Looks like | Min grade |
|---|---|---|
| `0.85 – 1.00` | You ran it on real data and watched it happen; authoritative policy read at source; replicated measurement you inspected. | A |
| `0.55 – 0.80` | One solid first-hand trial, or one primary source with a checkable method. | B |
| `0.25 – 0.50` | Suggestive — a reputable secondary summary, or thin/single-sample/confounded first-hand data. | C |
| `0.00 – 0.20` | Inconclusive, opinion/hearsay only, or (conditionally) unknowable — attach a `derisking:` block. | D |

Sign: evidence the assumption **holds → positive**; evidence it **does not hold →
negative**. Calibrate against the *vision's* bar, not a generic one.

Honesty rules:
- **The grade is a hard ceiling.** Grade C/D evidence cannot reach `|0.55|` no matter
  how much of it agrees — hearsay does not compound into proof. Cross `|0.55|` only on
  grade A/B evidence you obtained first-hand.
- Don't round a hunch up to certainty. A quick smoke test is ~`0.6`, not `1.0`.
- Confounded or narrow evidence caps the magnitude further, whichever way it points.
- If the only support is grade D, the honest score is `≤ |0.20|` with a `derisking:`
  block naming the primary check that would settle it — not a confident number.
- **Invalidation is a win.** Negative confidence means you caught a realized risk
  before it cost the project — report it as loudly as a validation.

---

## 6. Conditional unknowability — never a dead end

"Unknowable" almost always means *unknowable with what we have right now*. Capture the
condition, not a verdict of despair. Leave `confidence` near `0.0` and list each
approach with what would unblock it:

```json
{"id": "RA-45aB21", "confidence": 0.1,
 "derisking": [
   {"approach": "Query subscription policy assignments for EasyAuth",
    "needs": "read access to the subscription policy scope", "blocked": true},
   {"approach": "Ask the platform team whether EasyAuth is permitted",
    "needs": "a response from the platform team", "blocked": true}
 ]}
```

An assumption is **conditionally unknowable** when every listed approach is
`blocked: true`. The `needs:` fields are the shopping list that turns it knowable —
grant the access, add the tool, get the data, and the spike can be re-run.
