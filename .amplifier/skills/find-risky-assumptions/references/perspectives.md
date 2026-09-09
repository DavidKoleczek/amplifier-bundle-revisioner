# Perspectives: hunting risky assumptions from every angle

This is the depth behind Step 3. Completeness is not about volume — it is about
**coverage of angles**. A vision re-read through a new lens exposes assumptions the
previous lens was blind to. Work every section below. For each prompt, ask the same
underlying question: *what is the author taking for granted that could be false, and
would matter if it were?*

Record only genuinely risky beliefs. The prompts are a net, not a quota.

---

## 1. Desirability — will anyone actually want this?

The most expensive failure: building something that works and nobody uses.

- Is the problem real and painful enough that someone will act to solve it?
- Are the *intended* users the ones who feel the pain? (Often the buyer, the operator,
  and the sufferer are different people with different wants.)
- Will users change their existing behavior/tooling to adopt this? What do they use
  today, and why would they switch?
- Is the promised value the value users actually perceive? ("Faster" — do they care
  about speed, or about trust/control/effort?)
- Does the workflow fit how people really work, or an idealized version of it?
- Watch for: "users will love", "people want", "this makes it easy" — assertions about
  human preference stated as if proven.

## 2. Feasibility — can it be built and made to work?

- Can the core technology actually do what's claimed, at the required quality?
- Do the depended-on systems/APIs/models exist, and do they behave as assumed
  (limits, latency, accuracy, semantics, edge cases)?
- Will it hold at the required scale / load / concurrency / data volume?
- Is the required data / access / permission / credential actually available?
- Does the team have the skills, and is the effort estimate grounded?
- Are there integration points assumed to "just connect" that may not?
- Watch for work quietly delegated to "the model", "the system", "the framework", or a
  future component — each hand-off is an assumption that it can and will do the job.

## 3. Viability — does it survive cost, policy, and time?

- Is the ongoing cost (compute, tokens, licenses, people) acceptable and sustainable?
- Does it fit organizational, legal, security, privacy, and compliance constraints?
- Are the required permissions/approvals grantable in *this* environment? (Subscription
  policy, tenant rules, admin rights — often assumed, frequently the real blocker.)
- Can it be operated and maintained after launch — monitoring, upgrades, on-call, drift?
- Does the value keep exceeding the cost, or does it decay into a burden?

---

## Cross-cutting dimensions

Sweep these explicitly; they cut across the three primary lenses.

- **Technical** — architecture choices, dependency behavior, performance, failure modes,
  data correctness, security posture.
- **Practical** — buildable with the time/skills/tools on hand; testable; debuggable.
- **Cost** — money and tokens and time, up front and ongoing; hidden costs.
- **Operational** — deploy, run, observe, recover; who owns it; what breaks at 3am.
- **Adoption / change** — training, migration, incentives, resistance, the switching cost.
- **Dependency / external** — third parties, upstream specs, other teams, vendors,
  permissions, anything outside the author's control.
- **Scope / boundary** — is the stated scope achievable, or is something hard hiding in
  an out-of-scope note or a single throwaway clause?

---

## Pre-mortem (inversion)

Assume it is six months later and the vision failed. Write the post-mortem headline,
then several plausible causes. Each cause reverses into an assumption:

> Cause: "Operators never trusted the automated triage and went back to reading logs."
> → Assumption: *Operators will trust the model's triage enough to rely on it.*

Do this for the *most embarrassing* failure, the *most likely* failure, and the
*silent* failure (it technically works but delivers no value).

---

## Language tells — where assumptions hide in the prose

Skim the vision specifically for these; each is usually sitting on an unexamined belief.

- **Minimizers**: "just", "simply", "merely", "only", "obviously", "of course",
  "straightforward", "trivially". They compress an unproven claim into one word.
- **Human-preference claims**: "users will", "people want", "teams love", "naturally".
- **Unquantified magnitudes**: "fast", "cheap", "scalable", "reliable", "secure" — with
  no number or threshold. Each implies a bet on a value that could be wrong.
- **Bare numbers**: any figure ("50% more load", "under 200ms", "within budget") stated
  without a basis — the number itself is the assumption.
- **Passive hand-offs**: "is handled", "will be managed", "gets resolved automatically"
  — who/what does it, and can they?
- **Absolutes**: "always", "never", "any", "all", "guaranteed" — edge cases assumed away.
- **Future-tense certainty**: "will work", "will integrate", "will support" — stated as
  fact about something not yet built or tested.

---

## Converting a candidate into a good entry

Once a lens surfaces something, shape it before recording (see the quality bar in
SKILL.md): make it **atomic**, **declarative** (the belief, not a question),
**falsifiable** (a spike could test it), and confirm it is genuinely **risky**. Then check
it is not already in the file, and score its `risk` by stakes alone — how much the
vision's success depends on it — leaving `confidence` at its untested `0.0` default.
