#!/usr/bin/env python3
"""MediaDistill 跨平台安装引导程序。"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "logs" / ("windows-install.log" if os.name == "nt" else "install.log")


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
        return "winget install -e --id Gyan.FFmpeg（安装后关闭并重新打开 PowerShell）"
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


def run_logged(command: list[str], log_file: Path, cwd: Path = ROOT) -> None:
    """运行命令，并把输出同时写到控制台和本地诊断日志。"""
    child_env = os.environ.copy()
    # Windows 的旧版 PowerShell/CI 控制台可能使用 cp936 或 cp1252；强制 Python
    # 子进程使用 UTF-8，避免 pip 或诊断脚本输出中文时安装被意外中断。
    child_env.setdefault("PYTHONUTF8", "1")
    with log_file.open("a", encoding="utf-8") as log:
        with subprocess.Popen(
            command,
            cwd=cwd,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="")
                log.write(line)
                log.flush()
            returncode = process.wait()
    if returncode:
        raise subprocess.CalledProcessError(returncode, command)


def write_environment_summary(log_file: Path) -> None:
    """记录不含密钥的安装环境，便于远程排查。"""
    summary = [
        "",
        f"=== MediaDistill 安装 {dt.datetime.now().astimezone().isoformat()} ===",
        f"系统：{platform.platform()}",
        f"Python：{sys.version.splitlines()[0]}",
        f"Python 可执行文件：{sys.executable}",
        f"项目目录：{ROOT}",
        f"ffmpeg：{shutil.which('ffmpeg') or '未找到'}",
        f"ffprobe：{shutil.which('ffprobe') or '未找到'}",
    ]
    text = "\n".join(summary) + "\n"
    print(text, end="")
    with log_file.open("a", encoding="utf-8") as log:
        log.write(text)


def install(log_file: Path = DEFAULT_LOG) -> int:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    write_environment_summary(log_file)
    errors = check_prerequisites()
    if errors:
        for error in errors:
            print(f"[错误] {error}")
        print(f"诊断日志：{log_file}")
        return 1

    python = venv_python(ROOT)
    if not python.exists():
        print("正在创建 Python 虚拟环境……")
        venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
    if not python.exists():
        print(f"[错误] 虚拟环境创建后仍找不到：{python}")
        print(f"诊断日志：{log_file}")
        return 1

    print("正在安装 Python 依赖……")
    run_logged(
        [str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")],
        log_file,
    )
    run_logged([str(python), "-c", "import faster_whisper"], log_file)
    print("安装完成。")
    print(f"诊断日志：{log_file}")
    print(f"启动命令：{python} run.py --web --port 8765")
    return 0


def check(log_file: Path = DEFAULT_LOG) -> int:
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
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG, help="安装诊断日志路径")
    args = parser.parse_args()
    try:
        return check(args.log_file) if args.check else install(args.log_file)
    except subprocess.CalledProcessError as exc:
        print(f"[错误] 命令执行失败，退出码：{exc.returncode}")
        print(f"诊断日志：{args.log_file}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
