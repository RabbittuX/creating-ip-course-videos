# User setup

Personal assets and settings never live in this skill. They live in `$IP_COURSE_HOME` (default `~/.config/ip-course-videos`), so the skill can be shared and updated without leaking or overwriting them.

1. `python3 scripts/setup_config.py --init` writes `config.json` from `config.example.json`.
2. The user fills in:
   - `host.images`: the IP character's canonical front image (`host-front`, required) and optional pose images for the template slots listed in `assets/character-slots.json`. Unset slots fall back to another host image.
   - `host.identityInvariants`: 3–6 traits that must never change, described in screen coordinates.
   - `extraCharacters`: optional mascot / sidekick / crowd. Characters without images are skipped; unset mascot and sidekick slots render transparent.
   - `tts`: `voiceType` (a voice enabled in the user's Volcengine console), `ratePercent`, `cluster`.
   - `loudness`: integrated LUFS / LRA targets and tolerances.
   - `brand`: `courseTitle` (opening title default) and `appName` (prompt-input B-roll).
   - `captions.protectedTerms`: product names or terms captions must not split.
3. `python3 scripts/setup_config.py` copies images into `$IP_COURSE_HOME/ip-reference/<slot>.png`, builds the hash-locked `character-reference/registry.json`, and validates it.
4. TTS credentials are environment variables only: `DOUBAO_APPID`, `DOUBAO_TOKEN`. Never write them into config or project files.

`init_project.py` then records the user's registry in `project.json` and copies every slot image into the project's `assets/ip-reference/`. Re-run `setup_config.py` after changing any image; changed hashes require re-review of affected A-roll.

Never copy anything from `$IP_COURSE_HOME` into the skill directory.
