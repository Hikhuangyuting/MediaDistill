#!/usr/bin/env python3
"""MediaDistill 跨平台安装引导程序。"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure_console_encoding() -> None:
    """在 Windows 等非 UTF-8 控制台中稳定输出中文。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


configure_console_encoding()


def venv_python(root: Path, windows: bool | None = None) -> Path:
    """返回当前平台虚拟环境中的 Python 路径。"""
    windows = os.name == "nt" if windows is None else windows
    return root / ".venv" / ("Scripts/python.exe" if windows else "bin/python")


def ffmpeg_install_hint(system: str | None = None) -> str:
    """返回当前系统安装 ffmpeg 的推荐命令。"""
    system = system or platform.system()
    if system == "Darwin":
        return "brew install ffmpeg"
    if system == "Windows":
        return "winget install -e --id Gyan.FFmpeg"
    return "请使用系统包管理器安装 ffmpeg（例如 sudo apt install ffmpeg）"


def check_prerequisites() -> list[str]:
    """检查运行安装程序所需的 Python 与 ffmpeg。"""
    errors: list[str] = []
    if sys.version_info < (3, 10):
        errors.append("Python 版本低于 3.10")
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        errors.append(f"缺少 {', '.join(missing)}；安装命令：{ffmpeg_install_hint()}")
    return errors


def install() -> int:
    errors = check_prerequisites()
    if errors:
        for error in errors:
            print(f"[错误] {error}")
        return 1

    python = venv_python(ROOT)
    if not python.exists():
        print("正在创建 Python 虚拟环境……")
        venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")

    print("正在安装 Python 依赖……")
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")],
        cwd=ROOT,
        check=True,
    )
    print("安装完成。")
    print(f"启动命令：{python} run.py --web --port 8765")
    return 0


def check() -> int:
    errors = check_prerequisites()
    python = venv_python(ROOT)
    if not python.exists():
        errors.append("尚未创建 .venv 虚拟环境")
    if errors:
        for error in errors:
            print(f"[错误] {error}")
        return 1
    subprocess.run([str(python), "-c", "import faster_whisper"], check=True)
    print("Python、ffmpeg、ffprobe、虚拟环境与 faster-whisper 均可用。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MediaDistill 跨平台安装引导程序")
    parser.add_argument("--check", action="store_true", help="只检查环境，不执行安装")
    args = parser.parse_args()
    try:
        return check() if args.check else install()
    except subprocess.CalledProcessError as exc:
        print(f"[错误] 命令执行失败，退出码：{exc.returncode}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
