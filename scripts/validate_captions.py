#!/usr/bin/env python3
"""Validate semantic caption boundaries and current audio/alignment provenance."""

import argparse
import json
import sys
from pathlib import Path

from caption_rules import EDGE_PUNCTUATION, broken_term_at, estimated_width_px, file_hash, has_semantic_join, token_at_char


def validate(captions, alignment, alignment_path, audio_path, narration_path=None):
    errors = []
    narration = str(captions.get("narration", alignment.get("narration", "")))
    tokens = alignment.get("tokens", [])
    offset = int(captions.get("offsetMs", 0) or 0)
    if captions.get("alignmentHash") != file_hash(alignment_path):
        errors.append("词级对齐文件已变化，字幕必须重新生成")
    if narration_path and captions.get("narrationHash") != file_hash(narration_path):
        errors.append("口播稿已经变化，字幕必须重新生成")
    current_audio_hash = file_hash(audio_path)
    if not alignment.get("audioHash"):
        errors.append("词级对齐缺少 audioHash")
    if captions.get("sourceAudioHash") != current_audio_hash or alignment.get("audioHash") != current_audio_hash:
        errors.append("音频已经变化，字幕和词级时间必须重新对齐")
    previous_end_ms = -1
    previous_char_end = 0
    cue_list = captions.get("captions", [])
    if not cue_list:
        errors.append("字幕文件没有 captions")
    for index, cue in enumerate(cue_list, 1):
        label = f"字幕 {index}"
        text = str(cue.get("text", "")).strip()
        start_char = int(cue.get("sourceCharStart", -1))
        end_char = int(cue.get("sourceCharEnd", -1))
        start_ms = int(cue.get("startMs", -1))
        end_ms = int(cue.get("endMs", -1))
        if not text:
            errors.append(f"{label} 为空")
            continue
        if text[0] in EDGE_PUNCTUATION or text[-1] in EDGE_PUNCTUATION:
            errors.append(f"{label} 行首或行尾存在标点")
        semantic_error = has_semantic_join(text)
        if semantic_error:
            errors.append(f"{label} 语义拆分错误：{semantic_error}")
        if start_char < 0 or end_char <= start_char or end_char > len(narration):
            errors.append(f"{label} 原文字符范围无效")
            continue
        broken = broken_term_at(narration, start_char, end_char)
        if broken:
            errors.append(f"{label} 拆断了英文/数字术语“{broken}”")
        if narration[start_char:end_char] != text:
            errors.append(f"{label} 与原始口播字符范围不一致")
        if start_char < previous_char_end:
            errors.append(f"{label} 与上一条原文范围重叠")
        elif any(char not in EDGE_PUNCTUATION for char in narration[previous_char_end:start_char]):
            errors.append(f"{label} 与上一条之间漏掉口播内容")
        first = token_at_char(start_char, tokens)
        last = token_at_char(end_char - 1, tokens)
        if not first or not last:
            errors.append(f"{label} 无法映射到词级对齐")
        else:
            expected_start = int(first["startMs"]) + offset
            expected_end = int(last["endMs"]) + offset
            if abs(start_ms - expected_start) > 80 or abs(end_ms - expected_end) > 80:
                errors.append(f"{label} 与词级时间偏差超过 80ms")
        if end_ms <= start_ms:
            errors.append(f"{label} 时间无效")
        if start_ms < previous_end_ms:
            errors.append(f"{label} 与上一条字幕重叠")
        if len(text) > int(captions.get("maxChars", 22) or 22):
            errors.append(f"{label} 超过字幕字符上限")
        if float(cue.get("renderedWidthPx", 0) or 0) > 1640:
            errors.append(f"{label} 超过 1640px 安全宽度")
        if float(cue.get("estimatedWidthPx", estimated_width_px(text)) or 0) > 1640:
            errors.append(f"{label} 估算宽度超过 1640px 安全宽度")
        previous_end_ms = max(previous_end_ms, end_ms)
        previous_char_end = max(previous_char_end, end_char)
    if previous_char_end < len(narration) and any(char not in EDGE_PUNCTUATION for char in narration[previous_char_end:]):
        errors.append("字幕末尾漏掉口播内容")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--captions", required=True)
    parser.add_argument("--alignment", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--narration")
    args = parser.parse_args()
    captions = json.loads(Path(args.captions).read_text(encoding="utf-8"))
    alignment = json.loads(Path(args.alignment).read_text(encoding="utf-8"))
    errors = validate(captions, alignment, args.alignment, args.audio, args.narration)
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print("字幕语义与音频对齐校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
