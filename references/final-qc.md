# Final QC

## Before render

- HyperFrames check passes; review snapshot midpoints for every fixed/library template.
- Preview server status resolves to the intended project path and visible build ID.
- A-roll and B-roll candidate IDs match approvals.
- `validate_aroll.py --mode preview` passes; every generated A-roll path resolves under `assets/arroll/approved/`, and its hash matches the approved Candidate ID.
- No generated still exceeds the hard cadence limit; camera-only motion is not counted as an action change.
- Fixed A-roll roles resolve to `fixed-aroll-opening-title-v1` and `fixed-aroll-opening-transition-v1`; the opening title has no changed field except `backgroundTitle`, and the transition has no changed field.
- Captions pass text, punctuation, width, overlap, and audio-boundary checks.

## After chapter render

- ffprobe confirms 1920×1080, 30fps, playable H.264 video, AAC 48kHz stereo audio. Chapter TTS may originate at 44.1kHz, but the upload derivative follows the 48kHz delivery profile.
- Loudness matches the profile and true peak ceiling.
- No black frames, missing media, unexpected silence, frozen old assets, player chrome, or chapter-boundary subtitle flashes.
- Save the media report and its hash in `final-qc.json`; mark every required deterministic/manual check explicitly `true`.

## Full-video privacy scan

Sample frames and run OCR/search for `127.0.0.1`, `localhost`, usernames, email addresses, home-directory paths, access tokens, API keys, account names, and unredacted private UI. Report exact time ranges. Do not blur or alter anything until the user authorizes the listed targets.

## Scope integrity

Compare scene IDs and resource hashes against the approved manifest. Unrelated scenes, subtitles, timing, and files must remain unchanged. Concatenate only chapters that passed QC; keep versioned outputs and never overwrite the last approved master.
