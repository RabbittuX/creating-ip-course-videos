# IP character lock

The canonical image is the `required-host` entry's `canonicalPath` in the active character registry (`user_config.character_registry_path()`: the user's registry under `$IP_COURSE_HOME/character-reference/registry.json`, or the bundled placeholder before setup). Always include it in Image 2.0 generation and visual review.

If the active registry is the bundled example (`"example": true`), stop before any A-roll generation and ask the user to run `python3 scripts/setup_config.py --init`, fill in their character, then `python3 scripts/setup_config.py`.

## Identity invariants

- The registry's `identityInvariants` for each cast member are the identity contract. Read them before every generation and every review; do not invent extra traits or drop listed ones.
- Describe left/right features in **screen coordinates** (画面左侧 / 画面右侧), never the character's own left/right. Never swap sides.
- Preserve face proportions, the relative size, spacing, and angle of facial features, hair, accessories, outfit colors, and art style exactly as in the canonical image.
- Reject extra limbs or ears, fused fingers, malformed hands, merged characters, inconsistent clothing, or a changed facial style.

## Failure handling

If the face, distinctive features, or hands fail, keep the requested action and scene, attach the canonical reference again, and **重新生成整张图**. Do not recommend local paint-over or crude patching as the default. Limit automatic retries to two; then present candidates and the failure reason for human direction.

Every generated image starts in `assets/arroll/candidates/` with status `REVIEW`. Record one identity check per invariant in `planning/aroll-manifest.json`; any failed or unresolved required check blocks promotion. Automated inspection prepares evidence and may block a candidate, but never grants approval.

## Review package

Show canonical full body, candidate full frame, candidate face crop, any enlarged feature crops listed in `aroll-profile.json` `reviewCrops`, and the previous action frame. The reviewer must explicitly approve the Candidate ID and素材哈希. Only `scripts/promote_aroll.py` may copy the accepted image into `assets/arroll/approved/`.
