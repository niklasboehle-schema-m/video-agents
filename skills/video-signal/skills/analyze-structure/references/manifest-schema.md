# Structure manifest schema

Use schema version `1`. Keep beats ordered and non-overlapping. Express all times in source seconds.

## Root

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | Must be `1` |
| `project` | yes | Name for the new analysis or script |
| `source` | yes | Reference title, provenance, duration, and transcript confidence |
| `strategy` | yes | Whole-video audience, contract, payoff, and retention drivers |
| `beats` | yes | Ordered functional beat records |

## Source

```json
{
  "title": "Reference tutorial",
  "url": "https://example.com/reference",
  "duration": 24.8,
  "transcript_confidence": "verified"
}
```

`url` may be replaced with `provenance` for a local or user-supplied source. Use `verified`, `approximate`, or `partial` for transcript confidence.

## Strategy

| Field | Meaning |
|---|---|
| `audience` | Intended viewer and starting belief |
| `opening_contract` | What the opening promises |
| `payoff` | What the video ultimately delivers |
| `retention_drivers` | One or more allowed driver labels |
| `notes` | Optional strategy qualifications |

## Beat

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique stable identifier |
| `start` / `end` | yes | Source timing |
| `source_text` | yes | Exact transcript for this beat |
| `function` | yes | One allowed functional label |
| `job` | yes | What this passage does |
| `audience_before` | yes | Viewer state entering the beat |
| `audience_after` | yes | Viewer state leaving the beat |
| `information_gain` | yes | New information delivered |
| `handoff` | yes | Why the next beat follows |
| `rewrite` | no | Transfer objective, status, new line, and target duration |

## Rewrite

```json
{
  "status": "approved",
  "objective": "Challenge the audience's default workflow.",
  "line": "Your fastest campaign usually starts before you open the ad manager.",
  "target_duration": 3.0
}
```

Allowed statuses:

- `pending`
- `draft`
- `approved`
- `skipped`

Only approved lines are included in the teleprompter by default.

## Complete example

See `../examples/manifest.example.json`.
