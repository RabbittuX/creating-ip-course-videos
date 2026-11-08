# Fixed opening A-roll system

Resolve these roles before any A-roll image generation. They are single registered templates, not members of a random library.

## `opening-title`

- Use `assets/arroll/fixed/opening-title.html` directly.
- Preserve the source scene, paper background, rounded stage, IP assets, positions, pose sequence, camera motion, timing, and effects.
- 只允许修改 `backgroundTitle` 这一个字段。Replace its text with the current video's title (default from `config.json` `brand.courseTitle`); do not move it, restyle it, or modify character assets.
- Narration captions are supplied by the standard external caption layer. They are not editable fields of this template.

## `opening-transition`

- Use `assets/arroll/fixed/opening-transition.html` directly at the end of the opening section.
- Preserve the IP shrug sequence, optional sidekick, portal, optional mascot movement, stage geometry, timing, and effects.
- 这套模板是零可变字段。Do not add content inside the portal and do not regenerate any character.
- The standard external caption layer may display the locked narration cues such as “闲话不多说 / 我们开始”; it does not mutate the template.

## Source and reuse rules

Character images are read from the project's `assets/ip-reference/<slot>.png` (see `assets/character-slots.json`); unset optional slots render transparent. 不使用浏览器或播放器截图作为源素材；in particular, do not use the screenshot's black player surround, playback controls, zoom indicator, or subtitle rail as part of either template.

Do not send fixed A-roll to Image 2.0, create visual variants, randomly select alternatives, or re-render character images. Include the templates in A-roll review so the title and placement can be confirmed, and include the exact build again in browser preview review.
