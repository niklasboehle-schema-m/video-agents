# Video Agent Skills

A public bundle of Ruby Hoenderdos's portable AI skills for understanding, planning, and finishing video.

The collection currently includes five public source repositories and six installable skills. Each skill keeps its own documentation, examples, scripts, and license information inside `skills/`.

## Included skills

| Skill | What it does | Location |
|---|---|---|
| `video-signal` | Analyzes a local video with Gemini and returns an evidence-conscious report | [`skills/video-signal`](skills/video-signal) |
| `analyze-structure` | Maps narrative beats, pacing, and retention mechanics, then supports original structure transfer | [`skills/video-signal/skills/analyze-structure`](skills/video-signal/skills/analyze-structure) |
| `find-b-roll` | Researches, reviews, manifests, and places evidence-backed B-roll | [`skills/find-b-roll`](skills/find-b-roll) |
| `add-zooms` | Adds transcript-timed punch zooms, stepped zooms, and slow pushes with FFmpeg | [`skills/add-zooms`](skills/add-zooms) |
| `match-color` | Matches B-roll or secondary-camera color to a reference shot with local FFmpeg analysis | [`skills/match-color`](skills/match-color) |
| `add-sfx` | Places restrained, event-timed sound effects from a user-supplied sound library | [`skills/add-sfx`](skills/add-sfx) |

`cut-video` is not included because its source repository is private.

## Install

Clone the bundle:

```bash
git clone https://github.com/RBYHNDRDS/video-agent-skills.git
cd video-agent-skills
```

Install only the skills you want. For Codex:

```bash
mkdir -p "${HOME}/.codex/skills"
ln -s "${PWD}/skills/video-signal" "${HOME}/.codex/skills/video-signal"
ln -s "${PWD}/skills/video-signal/skills/analyze-structure" "${HOME}/.codex/skills/analyze-structure"
ln -s "${PWD}/skills/find-b-roll" "${HOME}/.codex/skills/find-b-roll"
ln -s "${PWD}/skills/add-zooms" "${HOME}/.codex/skills/add-zooms"
ln -s "${PWD}/skills/match-color" "${HOME}/.codex/skills/match-color"
ln -s "${PWD}/skills/add-sfx" "${HOME}/.codex/skills/add-sfx"
```

For Claude Code, use the same commands with `${HOME}/.claude/skills` as the destination. Other skill-compatible agents can point their skills directory at any folder containing a `SKILL.md` file.

Read each skill's README before use. Requirements and privacy boundaries differ: most rendering is local, while `video-signal` uploads the explicitly selected video to Gemini.

## Public sources

This repository is a bundled snapshot of these standalone public repositories:

- [`RBYHNDRDS/video-signal`](https://github.com/RBYHNDRDS/video-signal)
- [`RBYHNDRDS/find-b-roll`](https://github.com/RBYHNDRDS/find-b-roll)
- [`RBYHNDRDS/add-zooms`](https://github.com/RBYHNDRDS/add-zooms)
- [`RBYHNDRDS/match-color`](https://github.com/RBYHNDRDS/match-color)
- [`RBYHNDRDS/add-sfx`](https://github.com/RBYHNDRDS/add-sfx)

The standalone repositories remain the canonical development sources. Their original MIT licenses and copyright notices are preserved in their respective directories.

See [`SOURCES.md`](SOURCES.md) for the exact source commits included in this snapshot.

## License

MIT. See [`LICENSE`](LICENSE) and the license included with each skill.
