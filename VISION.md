# VISION

The desired end state this repo converges toward, written as though already
true. This page is never edited to record what shipped — status belongs in the
issue queue, not here. Amendments carry evidence (a failure this framing would
have caught, or a cost it retires) and land in the dated changelog at the
bottom. A drifted tree is debt on arrival, never grounds to edit this page into
agreement.

## What ReVisioner is

An assumption tester for vision documents. You point it at a vision and it
finds the assumptions that carry risk, spikes each one — research, a probe, a
throwaway experiment — and returns a verdict backed by data: **resolved**,
**needs unblocking**, or **unknowable**, the last carrying a concrete
suggestion for what would make it knowable. The state of the assumptions is kept
within the repo and this can be run against a project where just the vision is defined,
or previous assumptions have already been created and we now want to perform an update.

## Why this exists

Creating vision documents is a helpful way for people to get aligned on what to
build, and they serve as the way for agents to stay grounded against the things
you want to build. But throughout creating these, our own understanding of the
problem might be skewed, wrong, or misaligned with what is possible.

A vision written on a bad assumption does not fail loudly. It grounds
everything built against it, and the cost surfaces much later as work that was
never possible in the shape it was described.

## Principles

### 1. The repository is the workspace; the vision document is the entry point

ReVisioner reads the artifact the team already writes. It
does not ask for a separate assumption register, a questionnaire, or a
restatement of the vision in some machine format. If the assumption is not
recoverable from the document, that itself is a finding.

Everything ReVisioner learns lives in the repo alongside that document: the
assumptions it has identified, the evidence gathered for each, the verdicts
reached, and what is still open. A run against a repo that has only a vision
starts from nothing; a run against a repo it has seen before is an update, not a
restart. It re-tests what the vision changed, leaves settled assumptions settled,
and the accumulated state is committed with the project, readable by a human and
by the next agent.

### 2. Diverse assumptions are found, not supplied

The system generates proposals for assumptions that are important to validated.
It should do so in a way where it is diverse and finds a swath of risks. 

### 3. A spike produces data, not an opinion

Every verdict is backed by something that was actually run, read, researched or measured.
A confident restatement of the assumption is not evidence. Where a spike
produced code, that code is a probe and is thrown away; it is not the first
increment of the implementation. When research is conducted, it is done through
authoritative and reputable sources only.

### 4. The user is only notified when an assumption does not hold or an assumption has a blocker

Risky assumption -> It has been derisked or it is not risky therefore the user does not need to know about it

Risky assumption does not hold -> There is a risky assumption that has been verified and the tool must tell the user their vision should be amended.

Blocked -> The tool needs something that it, itself cannot do or access. For example, it needs the user to collect data or to give access to some system.

### 5. ReVisioner reports; the user amends

Findings never edit the vision in place. The original artifact's are the user's, and a
tool that rewrites it removes the moment of judgment that makes the vision worth
grounding against. ReVisioner produces the evidence; amending the page must only be done with user approval. 

### 6. The user's attention is precious. Only the most important and truly blocking items must be presented

The user must only be alerted of risks tbat truly cannot be de-risked or if the tool is truly blocked on things like data or access that it cannot resolve itself. 

## Changelog

- **2026-09-09** — Initial vision.
