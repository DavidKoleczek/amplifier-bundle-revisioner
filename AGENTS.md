# ReVisioner

`VISION.md` is the entry point for what this project is converging toward. The skills
under `.amplifier/skills/` are the implementation.

## Vocabulary

The project has one word for the thing it works on: a **risky assumption**. Use it, and
the terms below, in skill text, script output, UI copy, and when reporting to the user.
Introducing a synonym costs the reader a translation step every time they meet it, and
the synonyms drift apart as the project grows.

```
risky assumption   a belief the vision depends on that has not been validated
risk               0.00 .. 1.00, stakes only: how much success depends on it
confidence         -1.00 .. +1.00, signed belief it holds; magnitude is evidence strength
high-risk          risk >= 0.7, the threshold that decides what reaches the user
spike              the cheapest piece of real work that produces evidence for or against
verdict            holds / fails / blocked / in-flight / open, as classify.py buckets them
```

Say "high-risk assumption", not "load-bearing bet", "critical assumption", or "key risk".
Say "risk" for stakes and "confidence" for belief; never collapse the two into a single
"score", since the whole design depends on them moving independently and being owned by
different skills.

## Skills

```
find-risky-assumptions   finds assumptions and owns the risk axis
derisk-assumptions       runs spikes and owns the confidence axis
vision-check-in          classifies state and drives the next human decision
generate-revision-ux     renders that state as a browsable web UI
```

Each skill owns exactly one axis or none. A skill that reads state never writes the axes.

State lives in `.amplifier/revisioner/`, which is gitignored: `vision.md`, the
`risky-assumptions.yaml` ledger, and a `data/<id>/` directory per spike.
