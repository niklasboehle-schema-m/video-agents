---
name: find-b-roll
description: Plan, research, score, and place accurate B-roll for talking-head videos, interviews, tutorials, explainers, documentaries, and social clips. Use when a user asks to find B-roll, source cutaways, illustrate a transcript, collect visual evidence for spoken claims, make a B-roll plan, prepare candidate footage, create a contact sheet, or time approved images and clips to exact words. Prioritize primary sources, usage rights, human review, and local rendering.
---

# Find B-Roll

Turn a transcript or spoken video into an evidence-backed B-roll plan. Find a small set of accurate candidates, let the user approve the visual choices, and place approved local assets without changing the source.

Use the bundled resources:

- `scripts/broll_manifest.py`: validate, summarize, and score the explicit B-roll manifest.
- `scripts/contact_sheet.py`: turn manifest candidates and local previews into a review page.
- `scripts/render_broll.py`: place approved local images and videos over the source while preserving its audio.
- `references/manifest-schema.md`: read when creating or editing a manifest.

## Guardrails

- Understand the complete message before searching individual words.
- Prefer no cutaway over a misleading cutaway.
- Use primary or authoritative sources for people, products, events, statistics, and claims.
- Record the candidate URL, publisher, capture date, rights status, and score in the manifest.
- Treat a public URL as discoverable, not automatically reusable. Verify licensing, permission, public-domain status, ownership, or official media terms before rendering.
- Do not bypass paywalls, logins, robots controls, download protections, or platform terms.
- Do not download or republish copyrighted video merely because it can be accessed technically.
- Do not install downloaders, transcription models, browsers, or other dependencies without approval.
- Never place an unapproved candidate unless the user explicitly delegates final selection.
- Keep the source unchanged and render to a separate output.
- Do not upload private media or transcripts without authorization.

## Routes

Classify each useful spoken beat before searching:

| Route | Use for | Preferred evidence |
|---|---|---|
| `person` | A named person or role | Official profile, press page, licensed interview, user-owned footage |
| `product-ui` | A tool, company, product, or workflow | Official product media, owned screen recording, press kit |
| `receipt` | A quote, claim, headline, review, or statistic | Original post, primary report, official announcement |
| `location-action` | A place, physical action, or environment | Licensed stock, owned footage, public-domain media |
| `archival` | A historical person, product, or event | Archive with explicit reuse terms or licensed collection |
| `concept` | An abstract process or idea | A simple original graphic, diagram, or user-approved metaphor |
| `reaction` | Humor, contrast, or emotional punctuation | User-owned reaction library or user-selected licensed clip |

## Candidate score

Score every candidate out of 100:

| Dimension | Maximum |
|---|---:|
| Accuracy to the spoken point | 30 |
| Source authority | 20 |
| Rights confidence | 20 |
| Visual clarity | 15 |
| Format and crop fit | 10 |
| Freshness when time-sensitive | 5 |

Reject candidates that are misleading, watermarked, unreadable, deceptively synthetic, needlessly invasive, or have unverified rights. Aim for `75+` before presenting a recommendation.

## Workflow

### 1. Preflight the project

Obtain a transcript with timestamps. If the user supplies media without a transcript, use an already-available local transcription tool and retain word-level timestamps when possible.

Confirm only the choices that change the result:

- target aspect ratio and resolution;
- editing style and desired B-roll density;
- brand or visual constraints;
- allowed source and rights categories;
- must-include or banned visuals;
- whether the user wants a plan only, sourced candidates, or a rendered review copy.

### 2. Read for meaning

State the video’s thesis, audience, and tone in a few lines. Break the transcript into semantic beats rather than isolated keywords.

Choose only beats where a visual adds one of these:

- identity: shows the actual person, product, place, or event;
- evidence: proves or contextualizes a claim;
- comprehension: makes a process or abstract idea easier to understand;
- pacing: creates a deliberate visual reset without distorting the meaning.

Preserve the talking head when the speaker’s delivery is the strongest visual.

### 3. Create the plan

Create `broll_work/manifest.json` using `references/manifest-schema.md`. Each beat must include:

- source start and end time;
- exact spoken text;
- one-sentence visual intent;
- route;
- focused search queries;
- status and notes.

Explain the proposed beats, visual mix, density, and uncertain moments. Obtain approval before broad sourcing unless the user has explicitly asked for an autonomous pass.

### 4. Source candidates

Use the host agent’s current web, search, browser, connected library, or approved media tools. Search in this order:

1. user-owned project files and media library;
2. official or primary sources;
3. licensed libraries available to the user;
4. public-domain archives;
5. reputable stock sources with clear terms;
6. original graphics for concepts that should be drawn rather than filmed.

Open and visually inspect each candidate. Confirm that the visible content matches the title and the intended spoken point. For time-sensitive receipts, verify the date and capture the original source.

Add two to four strong candidates per beat rather than a long unfiltered list. Record evidence, rights status, and component scores in the manifest.

### 5. Present the review

Summarize candidates in transcript order. Include:

- the spoken beat and intended meaning;
- thumbnails or direct source links;
- why each candidate fits;
- rights status and any attribution requirement;
- total score and meaningful tradeoffs.

When local previews exist, create a contact sheet:

```bash
python3 scripts/contact_sheet.py \
  broll_work/manifest.json broll_work/review
```

Wait for the user’s choices. If the user delegates selection, choose only rights-cleared candidates and explain the selection.

### 6. Prepare approved assets

Place approved local files in the project workspace and set each approved beat’s `selected_candidate`. Never make the manifest imply that a URL has been downloaded when no local asset exists.

Validate:

```bash
python3 scripts/broll_manifest.py validate \
  broll_work/manifest.json --render-ready --assets
```

Time the cutaway to the spoken phrase. Do not reveal a named item before it is spoken unless the user requests anticipation. Avoid extremely short flashes; connect adjacent approved beats when that creates a cleaner sequence.

### 7. Render a review copy

```bash
python3 scripts/render_broll.py \
  source.mp4 broll_work/manifest.json output-broll-review.mp4
```

The renderer:

- uses the source dimensions;
- cover-crops each image or clip full-frame;
- ignores all B-roll audio;
- preserves the source audio;
- refuses unsafe rights states and accidental overwrites;
- produces a separate review file.

### 8. Verify

Watch the complete review copy with sound. At every beat:

- confirm the visual proves or illustrates the intended point;
- confirm the cutaway does not appear before the relevant phrase;
- check faces, names, dates, logos, headlines, and claims;
- check crop, legibility, watermarks, burned-in captions, and visual quality;
- confirm no approved beat disappeared;
- confirm the source audio remains synchronized;
- confirm all rights and attribution notes remain in the manifest.

Deliver the output together with the manifest and unresolved rights or sourcing notes.
