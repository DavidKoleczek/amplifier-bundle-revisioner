---
name: vision-check-in
description: >-
  Check in on where a vision stands once its risky assumptions have been found
  and are being de-risked. Reads the revisioner risky-assumptions.yaml plus the
  live per-spike status.json files, classifies every assumption (holds / fails /
  blocked / in-flight / open), and drives one of three conversations: report
  all-clear when the load-bearing bets hold, ask the user to supply what blocked
  spikes need (then resume de-risking), or propose a vision update/pivot when
  evidence has invalidated a load-bearing assumption. Use when the user asks
  "where do we stand", "check in on the vision", "what's blocked", "are we
  de-risked yet", or after de-risking spikes have run. It reads state and steers;
  it never sets risk or confidence itself.
---

# Vision check-in

This is the **controller** that closes the loop between the two worker skills.
`find-risky-assumptions` surfaces the bets a vision makes and owns **risk** (stakes).
`derisk-assumptions` runs spikes and owns **confidence** (signed belief). This skill
owns *neither axis* — it reads the current state of the ledger, tells the user where
the vision stands, and drives the next human decision. Many spikes may be in flight at
once (multiple agents de-risking in parallel), so a check-in is always a **snapshot**:
report what is settled, name what is still running, and act on what needs a human.

## What a check-in decides

Run the classifier, then have exactly one of three conversations (a real ledger often
has ingredients of all three — lead with the highest-priority one):

| Mode | Fires when | You do |
|---|---|---|
| **all-clear** | every high-risk assumption **holds** | Report success: the load-bearing bets are de-risked. Done. |
| **unblock** | a high-risk assumption is **blocked** | Ask the user for exactly the `needs:` items — or propose an alternative spike — then **resume de-risking** on those ids. |
| **pivot** | a high-risk assumption **fails** (risk realized) | Propose how the vision could change, as a **diff for approval**; on OK, archive the stale bets and **re-run find + derisk** on the new vision. |

When nothing needs a human yet — spikes still running, or open assumptions not spiked —
the mode is **in_progress**: report progress and offer to launch/continue de-risking.

Priority when several apply: **pivot > unblock > (in_progress) > all-clear**. A realized
risk on a load-bearing bet is the most consequential thing on the board; surface it first.

## The axes (this skill reads, never writes)

| Field | Range | Owned by |
|---|---|---|
| `risk` | `0.00 … 1.00` — stakes only | `find-risky-assumptions` |
| `confidence` | `−1.00 … +1.00` — signed belief it holds | `derisk-assumptions` |

Thresholds (defaults, overridable as flags on the classifier): **holds** `confidence ≥ +0.7`,
**fails** `confidence ≤ −0.7`, **high-risk / load-bearing** `risk ≥ 0.7`.

## Files & paths

| What | Path |
|---|---|
| Vision (what the bets serve) | `./.amplifier/revisioner/vision.md` |
| Ledger (read only, here) | `./.amplifier/revisioner/risky-assumptions.yaml` |
| Per-spike run-state | `./.amplifier/revisioner/data/<id>/status.json` |
| Per-assumption evidence | `./.amplifier/revisioner/data/<id>/findings.md` |
| Classifier (read-only) | `scripts/classify.py` |
| Pivot archiver (current → past) | `scripts/archive_assumptions.py` |
| Conversation scripts per mode | `references/interaction-playbook.md` |

---

## Workflow

### Step 1 — Snapshot the state

Run the classifier. It joins the ledger with the live `status.json` files and buckets
every current-vision assumption, then recommends a mode:

```bash
python3 .amplifier/skills/vision-check-in/scripts/classify.py \
  --file ./.amplifier/revisioner/risky-assumptions.yaml
```

Add `--json` when you want to drive logic off the result. The classifier is **read-only**
— it never edits the ledger. If the ledger is missing, tell the user to run
`find-risky-assumptions` first.

### Step 2 — Report the snapshot honestly

Give the user the board before the ask: how many load-bearing bets hold, what is
**in flight** right now (do not misreport a running spike as untested or failed), what is
blocked, and any realized risks. Read `data/<id>/findings.md` for the headline on
anything that flipped. Then move to the conversation for the recommended mode.

### Step 3 — Drive the conversation (see `references/interaction-playbook.md`)

**all-clear.** State plainly that every load-bearing assumption now holds, cite the
confidence + evidence pointer for each, and note any low-risk residuals the user may
choose to ignore. Nothing to do.

**unblock.** For each blocked assumption, surface the exact `needs:` from its `derisking`
block. Ask the user to supply it, or offer an alternative spike that routes around the
block. Do **not** invent a confidence — blocked means unknown.

**pivot.** For each failed load-bearing assumption, explain what the evidence showed
(pointer to `findings.md`), then propose concrete ways the vision could change to stop
depending on the false bet. Present it as a **diff against `vision.md`** and wait for
approval. Never rewrite the vision silently.

### Step 4 — Act on the user's response (close the loop)

**On supplied unblock input** — hand it straight back to `derisk-assumptions`, scoped to
just those ids, so the spikes resume immediately with the new access/data/tool:

```
load_skill(skill_name="derisk-assumptions")
# then de-risk only the named ids, passing the user's input as spike context
```

**On an approved pivot** — three moves, in order:

1. **Archive** the now-stale bets so their evidence is kept, not lost:

   ```bash
   python3 .amplifier/skills/vision-check-in/scripts/archive_assumptions.py \
     --file ./.amplifier/revisioner/risky-assumptions.yaml \
     --ids RA-aaaaaa,RA-bbbbbb --note "pivot: <one line why>"
   ```

2. **Edit `vision.md`** to the approved wording (apply the diff the user OK'd).
3. **Re-run the pipeline** on the changed vision: `find-risky-assumptions` (surfaces the
   new vision's bets) then `derisk-assumptions` (spikes them). The loop begins again.

### Step 5 — Offer the next check-in

Because spikes run asynchronously, end by telling the user how to see the board again
(re-run this skill) and what is still in flight. A check-in is a heartbeat, not a
one-shot gate.

---

## Guardrails

- **Read the axes, never write them.** This skill sets neither `risk` nor `confidence`.
  Confidence changes only by delegating to `derisk-assumptions`; risk only via
  `find-risky-assumptions`.
- **Snapshot honesty.** Report in-flight spikes as in-flight. Never present a running or
  blocked assumption as a settled verdict.
- **Blocked ≠ false.** A blocked spike means *unknown*, and unknowability is conditional —
  always carry its `needs:` so the user can unblock it.
- **Never rewrite the vision silently.** A pivot is proposed as a diff and applied only on
  explicit approval.
- **Pivot archives, never deletes.** Stale assumptions move current → past and their
  `data/<id>/` evidence stays on disk. Nothing is destroyed on a pivot.
- **Lead with the realized risk.** When a load-bearing bet has failed, that is the
  headline — surface it before blocks or all-clears.
