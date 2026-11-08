# 背景、参演人物与视觉梗概审核

## 背景与参演人物

完整阅读口播后，先用 `index_narration.py` 固化 `planning/narration-manifest.json`，再写 `planning/environment-cast-plan.json`。每章记录的真实口播必须完整匹配唯一主口播；记录主背景、是否与相邻章节共用、参演角色 ID、角色资产版本、连续动作链和换景理由。`sceneBible` 必须锁定场景背景、屏幕背景、镜头位置、人物站位和连续性说明，审核页必须直接展示这些字段。

在提取纯口播前另存源稿的标题层级，按 [secondary-title-system.md](secondary-title-system.md) 建立 `planning/heading-ledger.json`。不要因为二级标题不参与 TTS，就把它从视觉梗概中丢掉。

尽量一个章节一个主背景；短章节在地点和叙事情境一致时可共用。只有地点、时间或叙事功能明显变化时才增加背景。IP 人物通常必须出现；吉祥物、配角、群众等其他角色只在内容需要且已在角色登记表中批准时加入。生成精简审核页并停止，用户批准后记录 `ENVIRONMENT_CAST_APPROVED`。

区分三层“背景”：固定外层纸面和内层屏幕壳是版式，不是待设计的场景；此阶段需要设计并审核的是**内屏 A-roll 场景背景**，包括地点、色彩、透视、角色站位与章节间连续性；固定片头模板是例外，只替换其允许字段。审核页应显示作品进入屏幕壳后的实际构图，不能只展示孤立素材或把整张生成图铺满画幅。

## A/B-roll 精简梗概

背景与人物批准后写 `planning/visual-outline.json`。每个镜头必须包含：稳定 ID、章节、A/B 类型、20–40 字梗概、真实口播起止句及字符范围、计划时长、选择该类型的理由。A-roll 还要记录背景、角色和动作；B-roll 要记录 `designOrigin: template|custom` 和 `progressMode: static|narration-driven`。流程型、清单型或逐项对比型画面用 `narration-driven`，其每个梗概项必须同时保存 `itemId`、`label`、对应原口播 `sourceText`，必要时添加 `switchText`；单屏同时呈现且不随口播推进的画面用 `static`。

- 模板 B-roll：保存模板 ID、版本、预览路径和哈希。
- 自定义 B-roll：在审核前保存静态设计预览、布局规格路径和哈希。

所有镜头的字符范围必须按口播顺序无空洞、无重叠地覆盖整章。审核页按章精简展示镜头列表，并统计每章与全片 A/B-roll 的计划时长和占比。音频生成后运行 `build_actual_duration_report.py`；若单镜头偏差超过 1 秒或章节占比变化超过 5 个百分点，脚本撤销视觉梗概及下游状态并返回审核。

二级标题卡是零口播字符的独立区间，不计入上述口播覆盖率，也不能占用相邻镜头的口播字符。视觉审核页逐章列出标题卡及其前后口播锚点，并核对数量、顺序、文案和固定模板来源。

批准后立即运行 `prepare_broll_sync.py --project-root <project>`。它直接从已批准梗概生成各章映射，避免在音频阶段重新凭记忆抄写或遗漏映射。
