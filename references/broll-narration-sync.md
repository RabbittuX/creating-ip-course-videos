# B-roll 口播映射与状态同步

流程型、对比型、清单型 B-roll 必须在生成梗概的同时保存“原始口播 → 梗概项”的映射，再从真实音频词级对齐结果生成时间线。禁止按项目数平均分配时间。整个过程是本地字符和数字计算，不新增模型调用。

## 映射文件

保存到 `chapters/<id>/planning/broll-narration-map.json`。视觉梗概获批后运行 `prepare_broll_sync.py --project-root <project>`；它读取每个 `narration-driven` B-roll 项的 `sourceText` 并调用同一映射逻辑，自动写入 `sceneId`、`sourceCharStart`、`sourceCharEnd`、`switchAtChar` 和便于人工查看的 `triggerText`。字符位置是最终依据，因此相同短语不会互相误匹配；旧项目单独迁移时才直接调用 `build_broll_narration_map.py`。

用 `resolve_broll_timeline.py` 将映射和实际词级对齐文件解析为 `chapters/<id>/timing/broll-state-timeline.json`。`switchAtChar` 对应 token 的开始时间是 `activeAtMs`；下一项开始时上一项完成；最后一项保持黄色直到 `sourceCharEnd` 对应 token 结束。

## 状态规则

- 触发前保持灰色，不能提前变黄。
- 说到触发信号时，当前项与 IP 指针同时移动并变黄。
- 下一项触发时，上一项变绿，下一项变黄。
- 全部讲完后所有已讲项保持绿色，黄色焦点和指针隐藏。
- 对每个流程组合运行 `wire_broll_progress.py --composition <html> --timeline <json> --scene-id <id> --origin-ms <scene-start-ms>`。脚本嵌入共享控制器并用 `bindGsap(...)` 绑定被播放器 seek 的 GSAP 时间线；模板原有入场动画可以保留，但固定秒数状态动画不再拥有最终状态。

只做四项轻量校验：映射/时间线文件存在、项目顺序与时间递增、每个 B-roll 明确声明 `progressMode`、口播驱动画面已写入运行时接线标记。不要求逐触发点截图或 AI 视觉检测。使用 `approval_gate.py ... mark-ready --milestone broll-sync --project-root <project>`；门禁通过后再记录 `BROLL_SYNC_READY`。
