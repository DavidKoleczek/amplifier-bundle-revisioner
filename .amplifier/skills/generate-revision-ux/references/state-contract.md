# revision-state.json contract

`build_ux.py` reads `.amplifier/revisioner/` and emits one JSON file the template loads
at runtime from `/revision-state.json`. There is no backend. Everything the UI can show
is in this file or in the artifacts copied beside it.

## Source layout it reads

```
.amplifier/revisioner/
  vision.md                        # the artifact the bets serve
  risky-assumptions.yaml           # the ledger, two top-level sections
  data/<id>/
    spike-plan.md                  # written before the spike ran
    findings.md                    # evidence -> reasoning -> conclusion
    verdict.json                   # the spike's returned verdict, when present
    status.json                    # {"state": "running|done|blocked", "updated": "..."}
    <anything else>                # raw sources, scripts, logs, generated data
```

Every file above is optional except the ledger. A spike that captured nothing but a
`status.json` is a real state and renders as such.

The ledger is a YAML list of section mappings. Recognized sections are
`assumptions_related_to_current_vision` and `assumptions_related_to_past_visions`,
each a list of assumption mappings; either can be omitted, but at least one must exist.
IDs are unique across both sections, nonempty strings using letters, digits, `_`, `-`,
and `.` (not starting with `.`). No `RA-` prefix is required. Assumption text is nonempty.
Present axes are finite numbers: `risk` in [0, 1], `confidence` in [-1, 1].
Missing or null axes retain the classifier's zero default without changing the ledger.
`derisking` can be absent, null, or a list of mappings; present `approach` and `needs`
are strings, and present `blocked` is boolean. Unknown additive fields are accepted.

## Emitted shape

```jsonc
{
  "generated_at": "2026-09-09T18:22:04Z",
  "repo": "amplifier-bundle-revisioner",          // basename of the repo root
  "vision": {
    "path": ".amplifier/revisioner/vision.md",
    "markdown": "# VISION\n..."                    // null when the file is absent
  },

  // Verbatim output of vision-check-in/scripts/classify.py --json.
  // Do not recompute any of this in the builder or the template: the check-in
  // conversation and the UI must never disagree about what is blocked.
  "classification": {
    "recommended_mode": "unblock",                 // stale | pivot | unblock | in_progress | all_clear
    "counts": {"holds": 0, "fails": 0, "blocked": 3, "in_flight": 0, "open": 11},
    "high_risk_total": 7,
    "high_risk_holding": 0,
    "vision_drift": {                              // stale outranks every other mode
      "checked": false,                            // false when the ledger predates vision stamping
      "stale": false,                              // true only on a positive sha256 mismatch
      "stored": null,
      "current": "4a633ff2...",
      "vision_path": ".amplifier/revisioner/vision.md"
    },
    "buckets": {"holds": [], "fails": [], "blocked": [], "in_flight": [], "open": []},
    "rows": [
      {
        "id": "RA-LniKzX",
        "assumption": "Agent-issued 'resolved' verdicts are correct often enough ...",
        "risk": 0.85,                              // 0.00 .. 1.00, stakes only
        "confidence": 0.05,                        // -1.00 .. +1.00, signed belief
        "high_risk": true,                         // risk >= 0.7
        "status": "blocked",                       // status.json state, or "unset"
        "category": "blocked",                     // holds|fails|blocked|in_flight|open
        "lean": "positive",                        // positive|neutral|negative
        "has_blocked_residual": true,
        "needs": ["an independent grader outside the pipeline, and ..."]
      }
    ]
  },

  // One entry per current-vision assumption, keyed by the same id as classification.rows.
  // This is the drill-down payload; the template joins on id.
  "evidence": {
    "RA-LniKzX": {
      "spike_plan": "## Claim\n...",               // null when absent
      "findings": "## Evidence\n...",              // null when absent
      "verdict": {"id": "RA-LniKzX", "confidence": 0.05, "derisking": [/* ... */]},
      "status": {"state": "blocked", "updated": "2026-09-09T17:58:11Z"},
      "derisking": [                               // from the ledger entry, not the verdict
        {"approach": "...", "needs": "...", "blocked": true}
      ],
      "artifacts": [
        {"path": "data/RA-LniKzX/sources.md", "bytes": 4210}
      ]
    }
  },

  // The ledger's assumptions_related_to_past_visions section, unclassified.
  // Kept so a pivot's history stays visible.
  "past_assumptions": [
    {"id": "RA-xxxxxx", "assumption": "...", "risk": 0.6, "confidence": -0.8,
     "archived_note": "pivot: ..."}
  ],

  // Optional, only emitted when a document could not be inlined.
  // Paths are relative to the source state directory.
  "warnings": [
    {"path": "data/RA-xxxxxx/verdict.json", "message": "Cannot inline verdict: expected a JSON object"}
  ]
}
```

## Rules the builder holds to

**Classification is delegated, never reimplemented.** `build_ux.py` invokes
`.amplifier/skills/vision-check-in/scripts/classify.py --json` and embeds the result
unchanged. Thresholds live in one place. If the classifier is missing the build fails
loudly rather than guessing at buckets.

**Validate before writing output.** Invalid ledger sections, IDs, axes, or approach
types stop the build. Classifier output must have the documented renderable structure
and row IDs matching the current ledger; it is validated, never recategorized.
Serialization rejects non-finite numbers rather than emitting `NaN`.

**Absence is data.** A missing `findings.md` emits `null`, not an empty string and not a
placeholder sentence. The template distinguishes "this spike produced no write-up" from
"this spike wrote nothing down", and it can only do that if the builder does not paper
over the gap.

**Malformed is not missing.** A present `status.json` must be an object with `state`
equal to `running`, `done`, or `blocked` and a string `updated` when present; otherwise
the build stops with a file-specific error before writing output. A malformed or
non-object verdict emits `null` and a warning, with `verdict.json` indexed for raw
retrieval. Unreadable optional text emits `null` and a warning; existing empty text
stays `""`. Permission errors always stop the build. Valid verdict objects retain their
fields without requiring one fixed verdict shape.

**Artifacts are indexed, not inlined.** `spike_plan`, `findings`, `status`, and `verdict` are
inlined because the UI always shows them. Everything else in `data/<id>/` is listed with
a path relative to `public/`, and the whole `data/` tree is copied to `public/data/` so
those paths resolve as ordinary links. Binary and large files stay on disk where they do
not bloat the JSON. Optional spike documents that could not be inlined also keep raw links.

**Labels do not change data.** The UI presents `risk` as **Priority**, meaning stakes
for the vision, not urgency. Confidence is signed evidence strength, not probability:
-1 is strong evidence against, 0 is unknown/inconclusive, and +1 is strong evidence
supporting the assumption. Presentation adapts to optional evidence without inventing it.

**Paths are relative and posix.** Nothing absolute reaches the browser, so the generated
directory can be moved or served from anywhere.

## Extending it

The template reads a narrow subset of this file and ignores the rest, so adding a field
breaks nothing. Removing or renaming one does. When the ledger grows a field, add it to
`evidence.<id>` rather than reshaping `classification`, which belongs to `classify.py`.
