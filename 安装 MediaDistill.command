#!/bin/bash

set -eu
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "MediaDistill · 首次安装"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 Python 3.10 或更高版本，请先安装 Python。"
  read -r -p "按回车键关闭窗口。"
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "当前 Python 版本低于 3.10，请升级后重试。"
  read -r -p "按回车键关闭窗口。"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "未找到 ffmpeg。macOS 可先安装 Homebrew，再运行：brew install ffmpeg"
  read -r -p "按回车键关闭窗口。"
  exit 1
fi

python3 scripts/bootstrap.py || exit 1

echo ""
echo "安装完成。以后双击“启动 MediaDistill.command”即可使用。"
read -r -p "按回车键关闭窗口。"
