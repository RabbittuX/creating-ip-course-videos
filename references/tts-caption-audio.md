# TTS, captions, and audio

## Doubao

Voice, speech rate, and loudness targets are user settings: read them from `config.json` (`$IP_COURSE_HOME`, default `~/.config/ip-course-videos`) merged over `assets/presets/audio-profile.json` by `scripts/user_config.py`. Never hard-code a voice ID or rate in project files, and never copy them into shared artifacts.

Synthesize with `python3 scripts/tts_doubao.py --narration-manifest planning/narration-manifest.json --chapter <id> --output audio/<id>.wav`. Send the complete approved narration of one chapter in one request. Never synthesize sentence-by-sentence and concatenate. Read credentials only from `DOUBAO_APPID` and `DOUBAO_TOKEN`; never store or print them. If `tts.voiceType` is unset, stop and ask the user to configure it.

After synthesis, compare normalized chapter narration with forced-alignment/transcription text. Resolve missing words, duplicates, pronunciation directives, and unwanted fallbacks before timing scenes.

## Captions

Read `assets/presets/subtitle-profile.json`. One visual line per cue; 18–22 Chinese characters is the preferred range, while rendered width ≤1640px is the hard limit. Do not start or end a cue with punctuation. Keep English names, numbers with units, and fixed phrases intact. No overlaps, negative durations, or captions beyond chapter audio.

Generate from the current word alignment with `segment_captions.py`, then run `validate_captions.py`. The caption artifact stores the narration, alignment, and source-audio hashes; replacing or retiming audio invalidates it. Before preview approval, populate `timing/full-timeline.json` and run `validate_full_timeline.py` so title-page intervals cannot contain body narration or captions.

## Fixed chapter-title boundary

The fixed chapter-title B-roll is an inserted, non-narrated interval. During it, play only the canonical chapter-title sting: no TTS and no narration subtitle. Start the complete chapter TTS from source time 0 when the title interval ends; offset every forced-aligned caption and narration-driven scene by the same duration, and extend the composition. Mark the title, sting, and narration with `data-chapter-title-broll`, `data-chapter-sting`, and `data-narration-track`, then run `python3 scripts/validate_chapter_boundary.py --composition <chapter>/index.html`.

## Loudness

Match perceptual loudness—not a constant gain multiplier. Targets come from the merged audio profile (`loudness` in `config.json`, falling back to `assets/presets/audio-profile.json`):

- Integrated LUFS within `integratedToleranceLu` of `integratedLufs`.
- LRA within `loudnessRangeToleranceLu` of `loudnessRangeLu`.
- Chapter-to-chapter integrated difference: ≤ `maxChapterDeltaLu`.
- AAC, 44.1kHz, stereo.
- Final true peak ceiling: `truePeakCeilingDbtp` (default -0.3 dBTP).

If the user calibrated targets from a reference video, a reference true peak above the ceiling is not a target. Preserve its perceived loudness while preventing new inter-sample clipping.
