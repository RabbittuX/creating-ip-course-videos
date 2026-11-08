# creating-ip-course-videos

一个给 Claude Code / Codex 用的 Agent Skill：把一份完整的口播稿，做成**带固定 IP 人物**的章节式课程视频。

- 基于 HyperFrames 合成，A-roll 由图像模型生成，B-roll 用内置的 20+ 个动画模板
- 每个阶段都有**人工审批门禁**（背景与角色 → 视觉梗概 → A-roll 图 → 全片预览），未批准不会进入下一步
- IP 人物身份靠**定稿图 + 哈希锁定 + 外观特征清单**保持一致
- 豆包（火山引擎）整章配音、词级对齐字幕、响度检查、交付质检

> 本仓库不包含任何真实 IP 形象或个人配音参数。装好后需要配置你自己的角色和音色。

## 安装

```bash
# Claude Code
git clone https://github.com/RabbittuX/creating-ip-course-videos ~/.claude/skills/creating-ip-course-videos
# Codex
git clone https://github.com/RabbittuX/creating-ip-course-videos ~/.codex/skills/creating-ip-course-videos
```

依赖：Python 3.9+、Node.js 18+、ffmpeg、HyperFrames。

## 配置你的 IP 人物和配音

个人素材和参数都放在 skill 目录**之外**（默认 `~/.config/ip-course-videos/`，可用环境变量 `IP_COURSE_HOME` 修改），更新 skill 不会覆盖。

```bash
cd ~/.claude/skills/creating-ip-course-videos
python3 scripts/setup_config.py --init     # 生成 ~/.config/ip-course-videos/config.json
# 编辑 config.json，然后：
python3 scripts/setup_config.py            # 复制图片、生成哈希锁定的角色登记表
```

`config.json` 里要填的内容：

| 字段 | 说明 |
|---|---|
| `host.images.host-front` | **必填**，IP 人物正面定稿图 |
| `host.images.*` | 可选姿势图（讲解、摊手、指向、确认等），插槽见 `assets/character-slots.json`；没填的自动用正面图代替 |
| `host.identityInvariants` | 3～6 条每次生成都不能变的外观特征，左右按**画面**左右描述 |
| `extraCharacters` | 可选的吉祥物、配角，不配置就不显示 |
| `tts.voiceType` / `ratePercent` | 你在火山引擎控制台开通的音色 ID、语速（百分比） |
| `loudness` | 响度目标，默认 -14 LUFS |
| `brand` | 片头默认标题、输入框里显示的应用名 |
| `captions.protectedTerms` | 字幕断行时不能拆开的产品名、术语 |

豆包密钥**只从环境变量读取**，不要写进任何文件：

```bash
export DOUBAO_APPID=你的AppID
export DOUBAO_TOKEN=你的AccessToken
```

未配置时，skill 会使用自带的占位小人并提示你先完成配置。

## 使用

在 Claude Code 里直接说"把这份口播稿做成课程视频"，或调用 `/creating-ip-course-videos`。完整流程见 [SKILL.md](SKILL.md) 和 [references/workflow.md](references/workflow.md)。

单独合成一章配音：

```bash
python3 scripts/tts_doubao.py --narration-manifest planning/narration-manifest.json --chapter 01 --output audio/01.wav
python3 scripts/tts_doubao.py --text-file ch01.txt --output a.wav --dry-run   # 只打印请求，不调用接口
```

## 测试

```bash
node --test tests/*.test.mjs
```

豆包相关测试全部离线运行（本机模拟服务器 + 假密钥），不会调用真实接口、不消耗额度。

已知问题：`B-roll background normalization is idempotent` 这一项测试目前失败，不影响正常出片。

## 说明

- 豆包配音目前使用 V1 HTTP 接口，单次请求的文本长度上限未经验证；章节很长时如遇报错，可以拆成较短的章节。
- 内置的 `douyin-content-preflight.md` 是针对抖音的口播稿审核规则，发布到其他平台时可以忽略。

## License

[MIT](LICENSE)
