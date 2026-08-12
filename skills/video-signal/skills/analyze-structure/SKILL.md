---
name: analyze-structure
description: Analyze the narrative structure, retention mechanics, pacing, functional beats, and sentence-level jobs in a high-performing reference video, transcript, reel, short, ad, tutorial, or spoken script. Use when the user asks why a video works, wants a viral-video breakdown, beat map, pacing analysis, structure template, original rewrite based on a reference, or teleprompter-ready adaptation. Transfer only abstract functions and timing; prevent copied wording, examples, facts, catchphrases, and creator identity.
---

# Analyze Structure

Explain why a reference holds attention, capture its functional sequence in an explicit manifest, and transfer that sequence to the user’s own topic without copying the creator’s expression.

Use the bundled resources:

- `references/beat-functions.md`: read when choosing beat labels and retention drivers.
- `references/manifest-schema.md`: read when creating or editing the JSON manifest.
- `scripts/structure_manifest.py`: validate, summarize, pace-check, and originality-check the manifest.
- `scripts/make_report.py`: create a local visual analysis report.
- `scripts/make_teleprompter.py`: create a local standalone teleprompter from approved rewrite lines.

## Guardrails

- Analyze function, order, pacing, and audience-state change—not surface wording alone.
- Preserve the source URL or provenance and distinguish exact transcript from inferred speech.
- Do not bypass platform access controls or download protections. Use authorized tools or ask for a transcript or local file.
- Do not install downloaders, transcription models, or packages without approval.
- Do not imitate a living creator’s distinctive voice, catchphrases, persona, recurring metaphors, or signature delivery.
- Do not make a line-by-line paraphrase. Replace the topic, claims, proof, examples, and wording with the user’s material.
- Do not preserve fabricated or unverified claims merely because they appeared in the reference.
- Obtain approval of the structure map before drafting unless the user explicitly requests an autonomous pass.
- Run the bundled originality check before delivering a transferred script.
- Treat automated similarity checks as a minimum safeguard, not proof of legal originality.

## Workflow

### 1. Confirm the deliverable

Determine whether the user wants:

- structure analysis only;
- a reusable abstract template;
- a new script for a supplied topic;
- a visual report;
- a teleprompter export.

Ask only for missing information that changes the result: topic, audience, offer or takeaway, proof, desired duration, and CTA.

### 2. Obtain reliable source material

Prefer a transcript with sentence or word timestamps. Accept:

- a pasted timestamped transcript;
- a local video or audio file;
- an analysis report with transcript evidence;
- a public URL accessed through an authorized host tool.

If only media is available, use an already-configured video-analysis or transcription tool. For exact pacing, verify sentence boundaries against audio rather than trusting approximate model timestamps.

Record the source title, URL or local provenance, measured duration, and transcript confidence. Never invent missing lines.

### 3. State the whole-video strategy

Before labeling individual beats, explain:

- audience and starting belief;
- opening contract: what the viewer expects to receive;
- final payoff;
- central tension or information gap;
- dominant retention drivers;
- tone and delivery constraints.

Use `references/beat-functions.md` for the original taxonomy and decision tests.

### 4. Build the functional beat map

Create `structure_work/manifest.json` using `references/manifest-schema.md`.

For every beat, record:

- exact source start and end;
- source transcript;
- one functional label;
- the job performed by that passage;
- audience state before and after;
- information gained;
- handoff to the next beat;
- optional rewrite objective and target duration.

Do not label by sentence form alone. A question can be a pattern break, problem, open loop, or CTA depending on what it does to the viewer.

### 5. Analyze pacing and retention

Calculate:

- words and words per second per beat;
- duration share by function;
- where information is delayed or delivered;
- where proof arrives;
- changes in sentence length and density;
- transitions that make the next beat necessary;
- beats that could be removed without damaging the argument.

Distinguish useful tension from empty delay. Flag hooks that promise something the video never pays off.

### 6. Present and approve the structure

Summarize the sequence in abstract language, for example:

```text
pattern break → problem → proof → mechanism → steps → reveal → application
```

Explain why each transition works and which parts are topic-specific. Obtain approval before drafting the transfer unless final selection was explicitly delegated.

### 7. Transfer the structure

Keep only:

- the order of rhetorical jobs;
- approximate duration shares;
- the pattern of setup, evidence, explanation, and payoff;
- useful transition logic.

Replace:

- every claim and factual premise;
- every example, anecdote, and proof item;
- all wording and sentence construction;
- the speaker’s persona, catchphrases, and signature metaphors;
- the CTA with the user’s actual next step.

Write every new line from the user’s source material. If the user lacks proof or a factual basis for a beat, mark it as missing instead of borrowing from the reference.

### 8. Validate the transfer

```bash
python3 scripts/structure_manifest.py \
  validate structure_work/manifest.json --require-rewrite

python3 scripts/structure_manifest.py \
  originality structure_work/manifest.json
```

Revise any line that shares a long phrase, uses a suspiciously close sentence shape, or sounds like an imitation even if the script passes mechanically.

### 9. Export

Create a visual report:

```bash
python3 scripts/make_report.py \
  structure_work/manifest.json structure_work/report.html
```

After the user approves the rewrite lines, create a teleprompter:

```bash
python3 scripts/make_teleprompter.py \
  structure_work/manifest.json structure_work/prompter.html
```

The exports are standalone local HTML files with no external scripts, analytics, or network requests.

### 10. Deliver

Return:

- the structure summary;
- pacing and retention findings;
- the original transferred script;
- originality warnings or unresolved evidence gaps;
- requested report and teleprompter paths.
