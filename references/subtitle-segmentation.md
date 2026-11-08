# 字幕语义拆分

字幕必须从实际音频的词级对齐结果生成。先按句末语义与真实停顿分段，再在屏幕宽度限制内做短句拆分；不得先按固定字数硬切。

- 不把上一句结尾与下一句开头放在同一条字幕。
- 新的转折、命令或开场句应进入下一条，例如“闲话不多说，我们开始”。
- Skill、references、scripts、assets 等固定术语不得拆断；课程涉及的产品名、术语加到 `config.json` 的 `captions.protectedTerms`，同样不得拆断。
- 字幕不得以标点开头或结尾，不得重叠，必须覆盖对应口播而不抢跑。
- 替换语音、调整速度或剪切音频后，旧字幕和 B-roll 时间线全部失效，必须重新对齐。

章节标题页只允许章节提示音；正文音频和字幕在正文镜头开始后才可出现。用完整父时间线验证，不能只检查章节内部局部时间。

## 轻量执行流程

本流程只读口播文本、词级对齐 JSON、音频哈希和时间线 JSON，不调用模型、不逐帧截图。

```bash
python3 scripts/segment_captions.py \
  --narration chapters/01/audio/narration.txt \
  --alignment chapters/01/audio/alignment.json \
  --audio chapters/01/audio/narration.m4a \
  --output chapters/01/timing/captions.json \
  --chapter-id 01 --offset-ms 2600

python3 scripts/validate_captions.py \
  --captions chapters/01/timing/captions.json \
  --alignment chapters/01/audio/alignment.json \
  --audio chapters/01/audio/narration.m4a \
  --narration chapters/01/audio/narration.txt

python3 scripts/validate_full_timeline.py \
  --timeline timing/full-timeline.json
```

`segment_captions.py` 先按句末和转折词拆分，再按字符上限细分，并从真实词级对齐获取每条字幕时间。输出必须保存 `narrationHash`、`alignmentHash`、`sourceAudioHash`、原文字符范围和首尾 token ID。

`validate_captions.py` 拦截两句完整语义合并、转折词埋在同一字幕、漏字/重叠、超过 80ms 的词级时间偏差、超长/超宽，以及音频或对齐文件替换后未重新生成字幕。它是确定性规则检查，不尝试理解任意复杂语义；疑难拆分仍在预览审核中人工确认。

`validate_full_timeline.py` 检查章节、章节页、提示音、正文口播和字幕在父时间线上的绝对时间。每章可直接内嵌 `captions`，也可通过 `captionTrack` 引用字幕、对齐、音频及 `narrationPath`，并用 `parentOffsetMs` 转为父时间线时间。任何正文口播或字幕与章节页重叠、口播文件变化都必须阻止预览通过。

替换音频、调整语速或裁剪后，先重新生成词级对齐，再依次重跑上述三个脚本；不得手工保留旧时间。
