# 渲染与交付参数

读取 `assets/presets/delivery-profile.json`。保留高质量母版，并另外输出适合上传的 1920×1080、30fps H.264 版本；默认 CRF 21、AAC 192kbps、48kHz、`faststart`。除非用户明确要求，不因源工程偶然使用 60fps 而把上传版保持为 60fps。

渲染后运行 `validate_render.py` 和 `validate_state_consistency.py`。每章保存 `renders/<id>/render-ready.json` 与 `final-qc.json`。最终只接受 `renders/final/delivery-ready.json`：章节列表必须与 `project.json` 顺序完全一致，并绑定当前完整父时间线、全片母版、上传版和响度报告。响度报告必须满足 `audio-profile.json` 中锁定的 LUFS、LRA 与 True Peak 容差。任何媒体替换都使原 QC 或交付证据失效。
