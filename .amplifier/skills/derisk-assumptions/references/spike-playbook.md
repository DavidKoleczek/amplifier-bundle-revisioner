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

## 2. Pick the spike type that fits the claim

Most assumptions map to one of three. Combine them when useful.

### a. Evidence search (does someone already know?)
Best when the claim is common, studied, or governed by policy/docs you can find.
- Look for empirical results, benchmarks, datasheets, RFCs, standards, vendor limits,
  postmortems, or authoritative internal policy.
- Grade sources: primary measurement > reputable secondary > vendor marketing >
  forum anecdote. Record links/quotes verbatim in `data/<id>/sources.md`.
- Beware "true in the abstract" answers that dodge the vision's specific conditions.

### b. Hands-on trial (just try it)
Best when you can cheaply touch the real thing.
- Run the command, hit the API, check the actual permission/quota/config, wire a
  throwaway prototype, reproduce the workflow end to end on a small scale.
- The output of the real system is stronger evidence than any document. Save the exact
  commands and their raw stdout/stderr into `data/<id>/`.
- A trial that *fails to even set up* is itself evidence — often the "blocked" signal.

### c. Fresh empirical investigation (measure it)
Best when nobody's published it and it can't be settled by a quick trial.
- Generate or download representative data; run the model/benchmark/simulation;
  measure against the kill criterion.
- Note sample size, method, and confounders honestly. One run on toy data is
  *suggestive* (|0.25–0.50|), not proof.
- Keep the dataset, the script, and the raw results in `data/<id>/` so the number is
  reproducible later.

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
  spike-plan.md      # the claim, kill criterion, method, blocked-shape (Step 3)
  sources.md         # links + verbatim quotes, graded (evidence-search spikes)
  run/               # scripts, configs, commands actually executed
  output/            # raw stdout/stderr, logs, generated/downloaded data, screenshots
  findings.md        # evidence -> reasoning -> conclusion -> proposed confidence
  verdict.json       # {id, confidence, [derisking]} — the machine-readable result
```

`findings.md` is the human story; `verdict.json` is what feeds
`update_confidence.py`. Write both. Never inline large data into the ledger — the
ledger holds only the number; the *why* lives here.

---

## 5. From findings to a signed confidence

Magnitude = strength/directness of evidence; sign = which way it points.

| `|confidence|` | Looks like |
|---|---|
| `0.85 – 1.00` | You ran it and watched it happen; authoritative policy states it; strong replicated measurement. |
| `0.55 – 0.80` | One solid trial or one trustworthy primary source; indirect but credible. |
| `0.25 – 0.50` | Suggestive — leans one way but thin, single-sample, or confounded. |
| `0.00 – 0.20` | Inconclusive or (conditionally) unknowable — attach a `derisking:` block. |

Sign: evidence the assumption **holds → positive**; evidence it **does not hold →
negative**. Calibrate against the *vision's* bar, not a generic one.

Honesty rules:
- Don't round a hunch up to certainty. A quick smoke test is ~`0.6`, not `1.0`.
- Confounded or narrow evidence caps the magnitude, whichever way it points.
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
