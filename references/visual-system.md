# Visual system

Read `assets/presets/brand-tokens.json`; do not duplicate or override its values per chapter.

## Locked canvas

- 1920×1080, 30fps, 16:9.
- A-roll screen base `#f8f7f6`; illustration stage `#fdfaf4` with warm paper treatment.
- B-roll base `#252b31`; card `#394149`; neutral border `#71818e`.
- Accent `#e9a51a`; completed `#55d4b4`; light text `#fff7ec`; dark text `#2d3137`.

## Locked A-roll screen shell

Every generated A-roll is source artwork inside the established screen, never a raw full-canvas replacement. A-roll 必须使用外层 `paper` 画面背景和内层 `ar-stage` 屏幕背景：外层覆盖 1920×1080；内层固定 `left/right:72px; top:70px; height:820px`，使用圆角深色边框、暖白描边与阴影。Approved artwork fills only the inner stage with `object-fit:cover`; subtitles remain in the reserved lower area. 禁止把 A-roll 图片直接全屏铺底，禁止删掉画面背景、屏幕背景或屏幕边框后自行发挥。

## Subtitle safety zone

Reserve the bottom 200px of narrated A-roll and B-roll for the external subtitle layer. Cards, IP pointers, progress bars, footer copy, and result badges must remain above that zone at every sampled state; moving pointer animation may not cross into it. Inspect every timed state, not only one representative frame.

## Locked B-roll grid

Use all three layers, not merely the base color:

```css
background-color:#252b31;
background-image:
  linear-gradient(rgba(132,153,171,.10) 1px,transparent 1px),
  linear-gradient(90deg,rgba(132,153,171,.10) 1px,transparent 1px),
  radial-gradient(circle at 50% 0%,rgba(78,95,109,.18),transparent 60%);
background-size:44px 44px,44px 44px,auto;
```

Every physical B-roll source carries `data-broll-theme="locked-grid-v1"`, a single `data-broll-background="locked-grid-v1"` layer, and the theme style as its final style block so older template CSS cannot override it. This applies to all **24 个注册模板** and **8 个共享组件**, including disabled legacy sources. Run the full audit after any B-roll source or brand-token change:

```bash
python3 scripts/audit_broll_backgrounds.py \
  --registry assets/broll/template-registry.json \
  --tokens assets/presets/brand-tokens.json
```

Use `scripts/normalize_broll_backgrounds.py --root assets/broll --write` only for an intentional library-wide migration. Review the generated contact sheet from `scripts/build_broll_background_review.py`; do not infer visual compliance from source-text matching alone.

Use PingFang SC with Microsoft YaHei fallback. Dark-background character assets need the locked warm-white edge separation/drop shadow so the black cat and black ear do not disappear.

## Locked type

- Chapter title 92px; chapter label 28px.
- Subchapter title 88px.
- General B-roll title 58px.
- Subtitle 42px, weight 850.
