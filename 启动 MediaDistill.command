#!/bin/bash

set -u
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "MediaDistill · 影音萃取"
echo "正在启动本地工作台……"

if [ ! -x ".venv/bin/python" ]; then
  echo ""
  echo "尚未安装运行环境。请先双击“安装 MediaDistill.command”。"
  echo ""
  read -r -p "按回车键关闭窗口。"
  exit 1
fi

exec .venv/bin/python run.py --web --port 8765
