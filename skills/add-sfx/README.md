# Add Sound Effects

A portable AI skill for placing whooshes, pops, clicks, impacts, and other short effects under the moments that actually need them.

Give a skill-compatible agent a finished local video and a sound library you are allowed to use. The agent inspects the visual events, proposes restrained cues, writes a reviewable cue sheet, mixes the effects underneath the voice with FFmpeg, and verifies the final result.

The repository contains no audio files. You bring your own licensed sound pack.

## What it does

- Places pops and clicks under text, overlays, screenshots, icons, and UI actions.
- Places whooshes under deliberate movement and selected transitions.
- Uses scene changes and an optional `$add-zooms` cue sheet to propose candidates.
- Keeps silent stretches instead of sounding every cut.
- Mixes effects below the voice without compressing or ducking speech.
- Stream-copies the video, so only the audio is re-encoded.
- Refuses to overwrite the source unless overwrite behavior is explicitly enabled.

## Included files

- `SKILL.md` — the complete sound-design workflow and placement rules.
- `scripts/suggest_sfx_cues.py` — proposes candidates from scene changes and zoom cues.
- `scripts/render_sfx.py` — validates cue sheets, prints FFmpeg filter graphs, and renders the result.
- `examples/library.example.json` — portable role names for a user-supplied sound pack.
- `examples/cues.example.json` — example visual-event cue sheet.
- `agents/openai.yaml` — optional UI metadata for OpenAI-compatible skill hosts.

## Requirements

- Python 3.10 or newer
- `ffmpeg` and `ffprobe`
- A local sound library with usage rights and a `library.json` manifest

The bundled scripts make no network requests, install no packages, download no audio, and read no credentials.

## Install

Clone the repository:

```bash
git clone https://github.com/RBYHNDRDS/add-sfx.git
```

For Codex and other agents that scan `~/.agents/skills`:

```bash
mkdir -p "${HOME}/.agents/skills"
ln -s "${PWD}/add-sfx" "${HOME}/.agents/skills/add-sfx"
```

For Claude Code:

```bash
mkdir -p "${HOME}/.claude/skills"
ln -s "${PWD}/add-sfx" "${HOME}/.claude/skills/add-sfx"
```

## Use it

Ask in normal language:

```text
Use $add-sfx on this finished video with my sound pack.
Sound the intro text and overlay pops, whoosh the three deliberate transitions,
and leave the middle section dry.
```

The agent should watch the video before finalizing cues. Automatic scene detection is only a starting point; it cannot understand overlays or decide whether a cut should be felt.

## Sound-library manifest

```json
{
  "schema": 1,
  "root": ".",
  "sounds": {
    "pop_soft": {"file": "pops/pop-soft.wav"},
    "whoosh_short": {"file": "whoosh/whoosh-short.wav", "gain_db": -3.0}
  }
}
```

The shared role names let a cue sheet work with different user-owned sound packs.

## Manual renderer

Validate and render an approved cue sheet:

```bash
python3 scripts/render_sfx.py check cues.json --input input.mp4

python3 scripts/render_sfx.py render \
  input.mp4 cues.json output-with-sfx.mp4
```

Use `filter` instead of `render` to inspect the generated FFmpeg graph without modifying media.

## Privacy, rights, and safety

- Video, audio, and cue sheets stay local.
- The repository ships no third-party sounds or media.
- Users must supply a sound library they are permitted to use.
- Source files are not replaced and outputs use a separate path.
- Media, sound packs, work folders, environment files, keys, and tokens are excluded from Git.
- No telemetry or credential reader is included.

## License

MIT. See `LICENSE`.
