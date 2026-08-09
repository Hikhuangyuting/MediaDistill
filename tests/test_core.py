from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
