from __future__ import annotations

import unittest
from pathlib import Path
from urllib.parse import quote

from src.web.server import _safe_asset_id, _safe_filename, _status


class WebValidationTests(unittest.TestCase):
    def test_safe_asset_id_accepts_expected_ids(self) -> None:
        self.assertEqual(_safe_asset_id("ai-%E5%8C%BB%E7%96%97-v2"), "ai-医疗-v2")

    def test_safe_asset_id_rejects_traversal_and_special_characters(self) -> None:
        invalid = ["../secret", quote("../secret", safe=""), "a/b", ".", "a.md", ""]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                _safe_asset_id(value)

    def test_safe_filename_strips_directory_components(self) -> None:
        self.assertEqual(_safe_filename("../../demo.mp4"), "demo.mp4")
        self.assertEqual(_safe_filename("demo%20video.mp4"), "demo video.mp4")

    def test_status_prioritizes_failure_and_agent_wait(self) -> None:
        missing = Path("/path/that/does/not/exist.md")
        self.assertEqual(_status({"speech": "failed"}, missing), "failed")
        self.assertEqual(_status({"knowledge": "waiting_agent"}, missing), "needs_ai")
        self.assertEqual(_status({}, missing), "new")


if __name__ == "__main__":
    unittest.main()
