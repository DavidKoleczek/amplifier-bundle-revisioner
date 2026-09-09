# Interaction playbook

The three check-in conversations, in detail. The classifier (`scripts/classify.py`)
names the recommended mode; this is how to run each one. A real ledger often contains
ingredients of more than one — always lead with the highest priority
(**pivot > unblock > in_progress > all-clear**), but you may fold in the others as a
brief tail ("...and separately, two spikes are still running").

Throughout: **you read state and steer.** You never set `risk` or `confidence` yourself.
Confidence moves only through `derisk-assumptions`; risk only through
`find-risky-assumptions`.

---

## Mode: all-clear

**Fires when** every high-risk (`risk ≥ 0.7`) assumption holds (`confidence ≥ +0.7`).

**Goal:** confirm the load-bearing bets are de-risked and hand the user a clean bill.

1. State it plainly: the vision's load-bearing assumptions have held up under evidence.
2. For each, cite `confidence` and point at `data/<id>/findings.md` so the claim is
   auditable, not asserted.
3. Note any **low-risk residuals** still open or blocked, and frame them as optional —
   the user can accept them without another spike.
4. Nothing to do. Do not manufacture further work.

> All five load-bearing bets now hold (conf +0.72 … +0.91; evidence in each
> `data/<id>/findings.md`). Two low-risk assumptions remain untested (RA-…, RA-…) — not
> worth a spike unless you want the completeness. I'd call this vision de-risked.

---

## Mode: unblock

**Fires when** a high-risk assumption is **blocked** — its spike could not resolve
without something the de-risker didn't have. Unknowability is *conditional*: the
`derisking` block already names what would resolve it.

**Goal:** get that missing thing from the user, or route around it, then resume spikes.

1. For each blocked assumption, surface the **exact `needs:`** from its `derisking` block
   (the classifier prints these). Do not paraphrase away the specificity.
2. Ask the user to supply it — repo access, a credential, a dataset, the missing number,
   a decision — **or** offer an **alternative spike** that sidesteps the block (a cheaper
   proxy, a different data source, a narrower claim).
3. **Blocked ≠ false.** Never assign a confidence to a blocked assumption. It is unknown.

**On supplied input — resume immediately, scoped to those ids:**

```
load_skill(skill_name="derisk-assumptions")
```

Then de-risk only the named ids, passing the user's input as spike context (e.g. "the
repo is now at ../work-tracker; inspect the real `bd` acquire path"). The derisk skill
re-stamps `status.json` to `running`, re-scores confidence from the new evidence, and
this skill's next snapshot will show the result.

> RA-Tk6etS (atomic hold + custody, risk 0.95) is **blocked**: it needs the real
> `amplifier-work-tracker` repo to confirm the `bd` acquire path is one transaction.
> Point me at a checkout and I'll resume that spike. Otherwise I can spike Dolt's
> transaction semantics against a stand-in schema — weaker evidence, but unblocked.

---

## Mode: pivot

**Fires when** a high-risk assumption **fails** (`confidence ≤ −0.7`) — the risk has been
realized. The vision was leaning on a bet that evidence says is false.

**Goal:** change the vision so it no longer depends on the false bet — with the user's
explicit approval, never silently.

1. Lead with the realized risk. Explain **what the evidence showed**, pointing at
   `data/<id>/findings.md`. Be concrete about *why* the bet failed.
2. Propose one or more concrete ways the vision could change to stop depending on it —
   a scope cut, a different mechanism, an added constraint, a dropped goal.
3. Present the change as a **diff against `vision.md`** and **wait for approval.** Never
   rewrite the vision on your own authority.

**On an approved pivot — three moves, in order:**

1. **Archive** the now-stale bets (keeps their evidence, drops them from the live set):

   ```bash
   python3 .amplifier/skills/vision-check-in/scripts/archive_assumptions.py \
     --file ./.amplifier/revisioner/risky-assumptions.yaml \
     --ids RA-aaaaaa,RA-bbbbbb --note "pivot: <one line why>"
   ```

   Move the assumptions the *old* vision rested on that the *new* one no longer makes.
   Ones still live under the new wording stay in the current section. Their
   `data/<id>/` evidence is untouched — archiving is a ledger move, not a delete.

2. **Edit `vision.md`** to the approved wording (apply the diff the user OK'd).

3. **Re-run the pipeline** on the changed vision:

   ```
   load_skill(skill_name="find-risky-assumptions")   # surface the new vision's bets
   load_skill(skill_name="derisk-assumptions")       # spike them
   ```

   The new vision makes new bets; the loop begins again. The next check-in reports on
   the fresh set.

> RA-TT3fup (one operator supervises the whole fleet, risk 0.85) came back **negative**
> (conf −0.78): span-of-control evidence says a single ambient surface misses events past
> ~N concurrent agents (`data/RA-TT3fup/findings.md`). Two ways to pivot the vision —
> (a) cap supervised fleet size, or (b) add a triage tier below the operator. Here's the
> diff for option (a); say the word and I'll archive the old bet and re-run the pipeline.

---

## Mode: in_progress (no human needed yet)

**Fires when** nothing is blocked or failed, but spikes are still **in flight** or
assumptions remain **open** (untested / inconclusive).

**Goal:** report the heartbeat and keep momentum, without inventing a decision.

1. Report what is running now (from `status.json: running`) and what is still open.
2. Offer to launch or continue `derisk-assumptions` on the open ids.
3. Remind the user a check-in is a snapshot — re-run this skill to see the board move.

> 3 spikes in flight, 6 assumptions still untested, nothing blocked or failed yet. Want
> me to launch the next batch of spikes, or check back once the running ones land?
