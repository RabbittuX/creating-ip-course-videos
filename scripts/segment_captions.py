#!/usr/bin/env python3
"""Create semantic captions from narration and actual word alignment."""

import argparse
import json
import sys
from pathlib import Path

from caption_rules import estimated_width_px, file_hash, protected_spans, semantic_spans, token_at_char, trim_span


def split_at_pauses(narration, spans, tokens, threshold_ms):
    cuts = []
    for previous, current in zip(tokens, tokens[1:]):
        gap = int(current.get("startMs", 0)) - int(previous.get("endMs", 0))
        position = int(current.get("charStart", -1))
        if gap >= threshold_ms and position > 0:
            cuts.append(position)
    result = []
    for start, end in spans:
        boundaries = [start] + [cut for cut in cuts if start < cut < end and not any(left < cut < right for left, right in protected_spans(narration, start, end))] + [end]
        for left, right in zip(boundaries, boundaries[1:]):
            piece = trim_span(narration, left, right)
            if piece[0] < piece[1]:
                result.append(piece)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--narration", required=True, help="UTF-8 narration text file")
    parser.add_argument("--alignment", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chapter-id")
    parser.add_argument("--offset-ms", type=int, default=0)
    parser.add_argument("--max-chars", type=int, default=22)
    parser.add_argument("--pause-threshold-ms", type=int, default=320)
    args = parser.parse_args()
    narration = Path(args.narration).read_text(encoding="utf-8").strip()
    alignment = json.loads(Path(args.alignment).read_text(encoding="utf-8"))
    audio_hash = file_hash(args.audio)
    if not alignment.get("audioHash"):
        print("错误：词级对齐缺少 audioHash，无法证明它来自当前音频", file=sys.stderr)
        return 2
    if alignment.get("audioHash") != audio_hash:
        print("错误：词级对齐文件对应的音频已经变化，必须重新对齐", file=sys.stderr)
        return 2
    tokens = alignment.get("tokens", [])
    captions = []
    spans = split_at_pauses(narration, semantic_spans(narration, args.max_chars), tokens, args.pause_threshold_ms)
    for index, (start, end) in enumerate(spans, 1):
        first = token_at_char(start, tokens)
        last = token_at_char(end - 1, tokens)
        if not first or not last:
            print(f"错误：字幕 {index} 无法映射到词级时间", file=sys.stderr)
            return 2
        captions.append({
            "id": f"{args.chapter_id or 'chapter'}-caption-{index:03d}",
            "text": narration[start:end],
            "sourceCharStart": start,
            "sourceCharEnd": end,
            "startMs": int(first["startMs"]) + args.offset_ms,
            "endMs": int(last["endMs"]) + args.offset_ms,
            "startTokenId": first.get("id"),
            "endTokenId": last.get("id"),
            "estimatedWidthPx": estimated_width_px(narration[start:end]),
        })
    result = {
        "schemaVersion": 1,
        "chapterId": args.chapter_id,
        "narration": narration,
        "narrationHash": file_hash(args.narration),
        "alignmentHash": file_hash(args.alignment),
        "sourceAudioHash": audio_hash,
        "offsetMs": args.offset_ms,
        "maxChars": args.max_chars,
        "pauseThresholdMs": args.pause_threshold_ms,
        "captions": captions,
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 {len(captions)} 条语义字幕")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
