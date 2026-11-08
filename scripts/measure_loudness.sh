#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "用法: $0 <音频或视频文件>" >&2
  exit 2
fi
ffmpeg -hide_banner -nostats -i "$1" -filter_complex ebur128=peak=true -f null - 2>&1 | tail -n 16
