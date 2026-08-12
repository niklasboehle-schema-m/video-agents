# B-Roll manifest schema

Use schema version `1`. Keep times in source seconds and keep beats ordered and non-overlapping.

## Root fields

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | Must be `1` |
| `project` | yes | Short project name |
| `source_duration` | yes | Measured source duration in seconds |
| `target` | yes | Output width and height |
| `beats` | yes | Ordered B-roll opportunities |

## Beat fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique stable identifier |
| `start` / `end` | yes | Source-time placement |
| `spoken_text` | yes | Exact words covered |
| `intent` | yes | What the visual must communicate |
| `route` | yes | `person`, `product-ui`, `receipt`, `location-action`, `archival`, `concept`, or `reaction` |
| `queries` | yes | Focused search phrases |
| `status` | yes | `planned`, `candidates`, `approved`, or `skipped` |
| `candidates` | yes | Candidate records; may be empty during planning |
| `selected_candidate` | conditional | Required for `approved` beats |
| `notes` | no | Context, attribution, or edit notes |

## Candidate fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique within the beat |
| `title` | yes | Human-readable candidate title |
| `url` | yes | Original `http` or `https` source |
| `publisher` | yes | Source owner or publisher |
| `captured_at` | yes | Discovery date in `YYYY-MM-DD` form |
| `rights.status` | yes | See rights states below |
| `rights.note` | yes | Evidence, license, attribution, or unresolved issue |
| `scores` | yes | Six numeric component scores |
| `local_path` | conditional | Local image or video path for rendering |

Rights-cleared states:

- `owned`
- `licensed`
- `permission`
- `public-domain`

Review-only states:

- `official-media`
- `editorial-review`
- `unknown`

Official media is authoritative but still needs its reuse terms checked. The renderer blocks all review-only rights states unless the user deliberately passes `--allow-unverified-rights`.

Score limits:

```text
accuracy  0–30
authority 0–20
rights    0–20
clarity   0–15
format    0–10
freshness 0–5
```

The six values add to a 100-point score. The validation tool computes the total; do not store a separate total.

## Complete example

```json
{
  "schema": 1,
  "project": "Product tutorial intro",
  "source_duration": 24.6,
  "target": {"width": 1080, "height": 1920},
  "beats": [
    {
      "id": "beat-01",
      "start": 2.4,
      "end": 5.2,
      "spoken_text": "We built the first draft in Figma.",
      "intent": "Show the actual design canvas rather than a generic logo.",
      "route": "product-ui",
      "queries": ["Figma official product UI design canvas"],
      "status": "approved",
      "candidates": [
        {
          "id": "figma-canvas",
          "title": "Owned screen recording of the project canvas",
          "url": "https://www.figma.com/",
          "publisher": "Project team",
          "captured_at": "2026-07-24",
          "rights": {
            "status": "owned",
            "note": "Recorded by the project team."
          },
          "scores": {
            "accuracy": 30,
            "authority": 20,
            "rights": 20,
            "clarity": 14,
            "format": 9,
            "freshness": 5
          },
          "local_path": "assets/figma-canvas.mp4"
        }
      ],
      "selected_candidate": "figma-canvas",
      "notes": "Start on the word Figma."
    }
  ]
}
```
