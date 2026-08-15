from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from scripts.bootstrap import ffmpeg_install_hint, run_logged, venv_python
from src.core.config import _merge_dicts, load_settings
from src.core.utils import asset_id_from_path, read_json, slugify, write_json


class CoreUtilsTests(unittest.TestCase):
    def test_slugify_preserves_chinese_and_normalizes_spaces(self) -> None:
        self.assertEqual(slugify("  AI 医疗系统_v2!  "), "ai-医疗系统-v2")
        self.assertEqual(asset_id_from_path(Path("我的 视频.MP4")), "我的-视频")

    def test_write_json_is_atomic_under_concurrent_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "state.json"
            barrier = threading.Barrier(8)

            def writer(index: int) -> None:
                barrier.wait()
                write_json(path, {"writer": index, "values": list(range(50))})

            threads = [threading.Thread(target=writer, args=(index,)) for index in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            data = read_json(path)
            self.assertIn(data["writer"], range(8))
            self.assertEqual(data["values"], list(range(50)))
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


class ConfigTests(unittest.TestCase):
    def test_recursive_local_override(self) -> None:
        merged = _merge_dicts(
            {"speech": {"model": "medium", "device": "cpu"}, "enabled": True},
            {"speech": {"model": "small"}},
        )
        self.assertEqual(
            merged,
            {"speech": {"model": "small", "device": "cpu"}, "enabled": True},
        )

    def test_load_settings_uses_project_relative_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            (root / "config" / "settings.json").write_text(
                json.dumps({"speech": {"model": "small"}}),
                encoding="utf-8",
            )
            settings = load_settings(root)
            self.assertEqual(settings.speech.model, "small")
            self.assertEqual(settings.paths.video_input, root / "videos")


class BootstrapTests(unittest.TestCase):
    def test_virtual_environment_python_path_is_platform_specific(self) -> None:
        root = Path("project")
        self.assertEqual(venv_python(root, windows=False), root / ".venv/bin/python")
        self.assertEqual(venv_python(root, windows=True), root / ".venv/Scripts/python.exe")

    def test_ffmpeg_install_hints_are_platform_specific(self) -> None:
        self.assertEqual(ffmpeg_install_hint("Darwin"), "brew install ffmpeg")
        self.assertEqual(
            ffmpeg_install_hint("Windows"),
            "winget install -e --id Gyan.FFmpeg（安装后关闭并重新打开 PowerShell）",
        )

    def test_logged_command_captures_subprocess_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_file = Path(directory) / "install.log"
            run_logged(
                [sys.executable, "-c", "print('依赖安装成功')"],
                log_file,
                Path(directory),
            )
            self.assertIn("依赖安装成功", log_file.read_text(encoding="utf-8"))

    def test_windows_launchers_validate_environment_and_explain_recovery(self) -> None:
        root = Path(__file__).resolve().parents[1]
        installer = (root / "安装 MediaDistill.bat").read_text(encoding="utf-8")
        launcher = (root / "启动 MediaDistill.bat").read_text(encoding="utf-8")
        self.assertIn("scripts\\bootstrap.py --check", installer)
        self.assertIn("logs\\windows-install.log", installer)
        self.assertIn("scripts\\bootstrap.py --check", launcher)
        self.assertIn("python .\\scripts\\bootstrap.py", launcher)


if __name__ == "__main__":
    unittest.main()
