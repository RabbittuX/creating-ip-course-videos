# A-roll continuity

This reference applies only after checking [fixed-aroll-system.md](fixed-aroll-system.md). Do not generate a replacement for either fixed opening A-roll.

## Scene-world rule

Prefer one scene world per subchapter or continuous semantic sequence. Change location only when narration changes location, time, actor, or conceptual world. Rephrasing the same idea is not a reason to change scenes.

Lock in `scene-bible.yaml`:

- location and background geometry;
- camera height, angle, shot size, and dominant perspective;
- light direction and warm palette;
- main props with color/size/position;
- character wardrobe and starting screen positions;
- action chain and final state.

## Motion through stills

Design an ordered action chain: establish → problem → reaction → action → observation → result. Each image must inherit the prior image's world and visible state. Prefer meaningful hand, gaze, prop, and body changes over unrelated pose changes. Do not make every frame a presenter facing camera.

For Image 2.0, include the locked character reference, approved scene anchor, and previous approved action frame. The generated image must be the source artwork only—no player chrome, browser frame, subtitle, caption card, progress bar, or mock video canvas.

## Enforceable cadence

Read `assets/presets/aroll-profile.json`. 每个有效动作节点目标为 **3–5 秒**。单张图超过 6 秒时产生审核警告；超过 8 秒时阻止预览，除非用户在新的候选图审核中明确批准并记录例外。

Meaningful action changes include hand gesture, gaze target, body direction, actor position, or prop state. Camera zoom, pan, paper jitter, scratches, and lighting pulses do not count. Keep `cameraMovementCountsAsActionChange: false`.

## Structured action chain

Record every sequence in `planning/aroll-manifest.json`. A sequence needs `worldLockId`; every beat needs `id`, `role`, `candidateId`, `narrationCue`, `actorAction`, `gazeTarget`, `propState`, and `durationSeconds`. From the second beat onward, `inheritsFrom` must name the immediately preceding beat.

```yaml
id: login-checkpoint
worldLockId: login-hall-v1
beats:
  - id: beat-01
    role: establish
    candidateId: login-f1-v1
    narrationCue: 准备开始登录
    actorAction: 人物观察登录屏幕
    gazeTarget: 登录屏幕
    propState: 屏幕处于待登录状态
    durationSeconds: 4.2
  - id: beat-02
    role: action
    inheritsFrom: beat-01
    candidateId: login-f2-v1
    narrationCue: 选择自己的账号
    actorAction: 人物伸手选择账号
    gazeTarget: 账号列表
    propState: 账号由待选变为已选
    durationSeconds: 4.5
```

The validator enforces structure, inheritance, asset mapping, and cadence. Human review still decides whether the action meaning and visual continuity are convincing.

## Review

Build the media-backed package in [aroll-review-system.md](aroll-review-system.md). Flag unexplained changes in room structure, camera direction, prop identity, wardrobe, character side, or action state. Human approval is still required; an automated score never grants `AROLL_IMAGES_APPROVED`.
