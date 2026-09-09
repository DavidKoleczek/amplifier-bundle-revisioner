---
name: generate-revision-ux
description: >-
  Build a browsable web UI showing where a vision stands in the ReVisioner process:
  which risky assumptions need the user's attention right now (amend the vision, or
  unblock a spike), and a drill-down into the evidence behind every verdict. Reads
  .amplifier/revisioner/ (risky-assumptions.yaml plus each data/<id>/ spike directory),
  emits a single revision-state.json, and instantiates a bundled React template the
  user runs with pnpm or npm. Use this whenever someone wants to SEE the state of the
  assumptions rather than read a terminal summary: "show me where we stand",
  "visualize the assumptions", "build a dashboard for this", "is there a UI for the
  revisioner", "I want to click into the evidence", or after a de-risking pass when a
  text report is too dense to reason about. Also use it when the user wants to share
  the current state with someone who will not run the tool themselves.
---

# Generate revision UX

A terminal check-in is a snapshot that scrolls away. Once a vision has more than a
handful of assumptions, and each one has a spike plan, a findings write-up, and a pile
of raw artifacts behind it, the thing a human actually needs is a surface they can scan
and then click into. This skill produces that surface from state already on disk.

The UI answers one question first and everything else second: **what needs the user
right now?** That is the small set of assumptions whose evidence says the vision must
change, plus the ones whose spikes are stuck waiting on access or data only the user
can supply. Everything else is drill-down, available but not competing for attention.

You are not producing findings here, and you are not moving `risk` or `confidence`.
This skill reads state and renders it.

## Files and paths

| What | Path |
|---|---|
| Source state (read) | `./.amplifier/revisioner/` |
| Classifier reused for bucketing | `.amplifier/skills/vision-check-in/scripts/classify.py` |
| Builder | `scripts/build_ux.py` |
| Bundled app template | `assets/template/` |
| Generated app (write) | `./.amplifier/revisioner/ux/` |
| Emitted data contract | `references/state-contract.md` |

The generated app is disposable. It is rebuilt from `.amplifier/revisioner/` every time,
so nothing a user edits inside `ux/` survives, and nothing of value lives only there.

---

## Workflow

### Step 1 - Confirm there is state worth rendering

Check that `./.amplifier/revisioner/risky-assumptions.yaml` exists. If it does not,
stop and point the user at `find-risky-assumptions`: an empty ledger renders an empty
page, which wastes their time and teaches them nothing.

A ledger with entries but no `data/` directories is fine and worth rendering. It shows
every assumption as open, which is an honest picture of a vision whose bets have been
found but not yet tested.

### Step 2 - Build

```bash
python3 .amplifier/skills/generate-revision-ux/scripts/build_ux.py
```

This reads the ledger and the vision, shells out to the check-in classifier so the
buckets and recommended mode match exactly what `vision-check-in` reports, pulls in each
spike's `spike-plan.md`, `findings.md`, and `verdict.json`, indexes the remaining raw
artifacts, and writes everything to `./.amplifier/revisioner/ux/public/revision-state.json`.
The bundled template is copied alongside it.

Useful flags (`--help` lists all of them):

```bash
--out <dir>        # target directory, default ./.amplifier/revisioner/ux
--data-only        # refresh revision-state.json without re-copying the template
--file <path>      # a ledger somewhere other than the default
```

Reach for `--data-only` when spikes have finished since the last build and the user
already has the dev server running. The page picks up the new state on reload.

### Step 3 - Serve it

Finish the job. A user who asked to see the state should not have to install
dependencies and start a dev server to get there, so run it for them and hand back a URL.

The app is a Vite + React project with no backend. Install with `pnpm` when it is on
PATH, otherwise `npm`, then start the server in the background so it outlives the turn:

```bash
cd .amplifier/revisioner/ux && npm install
setsid nohup npm run dev > /tmp/revision-ux.log 2>&1 < /dev/null & disown
```

`setsid` matters. A plain background job stays in the shell's process group and dies
with it, so the server disappears the moment the command that launched it returns, and
the URL you hand over is already dead.

Poll `/tmp/revision-ux.log` until Vite prints its `Local:` line, then read the URL from
there rather than assuming a port. Vite moves to the next free port when the configured
one is taken, so a guessed URL sends the user to whatever else is running.

Confirm it actually serves before claiming it works:

```bash
curl -sf -o /dev/null -w '%{http_code}\n' <url> && \
curl -sf -o /dev/null -w '%{http_code}\n' <url>/revision-state.json
```

Two 200s means the page and its data are both reachable. Do not open a browser for the
user, and do not assume the host has one.

Leave the server running and tell the user how to stop it. Its log path is worth giving
them too, since a dev server that dies later leaves them with a dead tab and no clue why.

For a version that can be handed to someone who will not run a dev server, `npm run build`
emits a static bundle under `dist/` that any static file host can serve.

### Step 4 - Report what they are about to see

Do not make them discover the headline by reading the screen. Lead with the URL, then say
it: the recommended mode, how many high-risk assumptions hold, and specifically which
assumptions are asking for their attention and what each one wants from them. The UI is
where they go to act on that, not where they learn it for the first time.

---

## What the UI shows

The template renders three regions, in priority order, and that order is the point.

**Needs your attention.** Assumptions where evidence has come back against a
high-risk assumption (the vision should change) and assumptions whose spikes are blocked
(the user has something the tool cannot get). Each carries its verbatim `needs:` items,
because "unblock this" without naming what is missing is not actionable.

**The board.** Every current-vision assumption with its risk, signed confidence,
category, and run state. This is the scan surface. It exists so the user can confirm the
attention list is not hiding something, not so they can read fourteen rows carefully.

**Drill-down.** Selecting an assumption opens its spike plan, its findings, its recorded
verdict, and links to every raw artifact the spike captured. This is what makes a verdict
auditable rather than something the user has to take on faith.

Past-vision assumptions render in a separate collapsed region. They are kept so a pivot's
history stays visible, and they are out of the way because they are settled.

## Modifying the template

The template is a starting point, not a fixed product. When a user wants different
framing, edit `assets/template/src/` in the skill so the change survives the next build,
rather than editing the generated copy under `ux/`, which is overwritten.

Read `references/state-contract.md` before changing anything that touches data. It
documents the exact shape of `revision-state.json`, including which fields come straight
from `classify.py` and therefore change only if that classifier changes.

---

## Guardrails

- **Render, never author.** This skill does not set `risk` or `confidence`, does not
  write to the ledger, and does not edit `vision.md`. If the picture is wrong, the fix is
  upstream in whichever skill owns that axis.
- **The generated directory is disposable.** Treat `ux/` as build output. Never store
  anything there that is not reproducible from `.amplifier/revisioner/`.
- **Blocked is not failed.** The UI must keep them visually distinct. A blocked spike
  means unknown, and collapsing it into "failed" invents a verdict the evidence does not
  support.
- **Missing evidence renders as missing.** When a spike wrote no `findings.md`, show that
  absence. Filling the gap with a summary generated at render time would put unsourced
  text where the user expects gathered evidence.
