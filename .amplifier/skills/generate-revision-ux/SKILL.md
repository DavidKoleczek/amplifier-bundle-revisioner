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

Set up the bundled dashboard from state already on disk, validate it, and serve it
for the user. The template owns the UI; this skill does not design or customize it.

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

A ledger with entries but no `data/` directories is fine. The classifier still uses
recorded confidence and approaches; missing spike files do not imply an open verdict.

Before building, compare the actual state with `references/state-contract.md`:

- Inspect the ledger's section shapes, entry counts, IDs, axis ranges, and optional
  fields such as `derisking` and past-vision notes. Do not assume a fixed assumption
  count or require every spike to have evidence.
- Inventory spike directories and artifact names, extensions, and byte sizes, including
  nested paths. Summarize totals and at most 30 file entries; do not read raw artifacts
  wholesale. Sample up to three spike directories with different available fields.
  Read at most 80 lines per sampled plan/findings file and inspect status/verdict
  objects under 16 KiB for their keys and types; otherwise inspect size only and let
  the builder validate them. Missing files and empty files are different states.
- Do not invent evidence, convert the ledger, or alter classifier categories.
- If sections, scales, or required field types are incompatible, stop and name the
  file, field, expected shape/range, and owning skill that must resolve it. Do not guess
  a conversion. Review builder warnings for optional unreadable documents; malformed
  status is a build error, while a malformed verdict retains a raw artifact link.
  Stop on permission errors rather than treating inaccessible files as absent.

### Step 2 - Build

```bash
python3 .amplifier/skills/generate-revision-ux/scripts/build_ux.py
```

This reads the ledger and the vision, shells out to the check-in classifier so the
buckets and recommended mode match exactly what `vision-check-in` reports, pulls in each
spike's `spike-plan.md`, `findings.md`, and `verdict.json`, indexes the remaining raw
artifacts, and writes everything to `./.amplifier/revisioner/ux/public/revision-state.json`.
The bundled template is copied alongside it.

Review builder warnings and compare the generated data with the source ledger and
classifier output: entries, axes, buckets, and recommended mode must agree. Use bounded
reads when investigating discrepancies; do not repair source state in this skill.

Useful flags (`--help` lists all of them):

```bash
--out <dir>        # target directory, default ./.amplifier/revisioner/ux
--data-only        # refresh revision-state.json without re-copying the template
--file <path>      # a ledger somewhere other than the default
```

Reach for `--data-only` when spikes have finished since the last build and the user
already has the dev server running. The page picks up the new state on reload.

### Step 3 - Validate and serve it

Finish the job. A user who asked to see the state should not have to install
dependencies and start a dev server to get there, so run it for them and hand back a URL.

The app is a Vite + React project with no backend. Install with `pnpm` when it is on
PATH, otherwise `npm`. Run the generated app's tests and production build after install
(use the equivalent `pnpm` commands when selected):

```bash
cd .amplifier/revisioner/ux && npm install && npm test && npm run build
```

If any check fails, stop and report it. After checks pass, start the server from the
generated app directory in the background so it outlives the turn:

```bash
setsid nohup npm run dev > /tmp/revision-ux.log 2>&1 < /dev/null & disown
```

`setsid` matters. A plain background job stays in the shell's process group and dies
with it, so the server disappears the moment the command that launched it returns, and
the URL you hand over is already dead.

Let Vite automatically select an available port starting at `5183`, falling back to
the next free port when it is taken. Do not ask the user to choose a port, stop unrelated
listeners, or enable `strictPort`.

Poll `/tmp/revision-ux.log` until Vite prints its `Local:` line, then read the actual URL
from there rather than assuming a port.

Confirm it actually serves before claiming it works:

```bash
curl -sf -o /dev/null -w '%{http_code}\n' <url> && \
curl -sf -o /dev/null -w '%{http_code}\n' <url>/revision-state.json
```

Two 200s means the page and its data are reachable, not that the UI renders correctly.
If browser automation is available, verify rendering and evidence navigation against
the actual generated data. Otherwise disclose that browser validation was not performed.
Do not open a browser for the user, and do not assume the host has one.

For a version that can be handed to someone who will not run a dev server, `npm run build`
emits a static bundle under `dist/` that any static file host can serve.

### Step 4 - Hand back the dashboard

Lead with the actual URL and briefly report the checks performed, warnings, and any
validation not completed. Leave the server running; give a stop command scoped to that
server and its log path, `/tmp/revision-ux.log`.

---

## Guardrails

- **Render, never author.** This skill does not set `risk` or `confidence`, does not
  write to the ledger, and does not edit `vision.md`. If the picture is wrong, the fix is
  upstream in whichever skill owns that axis.
- **The generated directory is disposable.** Treat `ux/` as build output. Never store
  anything there that is not reproducible from `.amplifier/revisioner/`.
