from __future__ import annotations

import json
import mimetypes
import re
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from src.core.config import Settings
from src.core.utils import read_json, write_json
from src.ingest.router import run_ingest
from src.ingest.scanner import scan_assets


@dataclass
class Job:
    asset_id: str
    status: str = "queued"
    log: list[str] = field(default_factory=list)
    returncode: int | None = None


class AppState:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.ingest_lock = threading.Lock()
        self.known_asset_ids: set[str] = set()
        self.library_path = settings.paths.workspace / "library.json"

    def _library(self) -> dict:
        if self.library_path.exists():
            data = read_json(self.library_path)
            data.setdefault("groups", ["未分组"])
            return data
        return {"version": 1, "next_order": 1, "groups": ["未分组"], "assets": {}}

    def _save_library(self, data: dict) -> None:
        write_json(self.library_path, data)

    def register_assets(self, assets: list, group: str | None = None) -> dict:
        with self.lock:
            self.known_asset_ids.update(asset.asset_id for asset in assets)
            data = self._library()
            changed = False
            # One-time migration for libraries that existed before import-order
            # metadata was introduced. Workspace meta creation time is the best
            # available historical import signal.
            if not data.get("order_initialized"):
                ordered = sorted(
                    assets,
                    key=lambda asset: (
                        (self.settings.paths.workspace / asset.asset_id / "meta.json")
                        .stat()
                        .st_mtime
                        if (self.settings.paths.workspace / asset.asset_id / "meta.json").exists()
                        else 0,
                        asset.asset_id,
                    ),
                )
                for index, asset in enumerate(ordered, start=1):
                    row = data["assets"].setdefault(asset.asset_id, {})
                    row["order"] = index
                    row.setdefault(
                        "imported_at",
                        datetime.fromtimestamp(
                            (self.settings.paths.workspace / asset.asset_id / "meta.json")
                            .stat()
                            .st_mtime
                            if (
                                self.settings.paths.workspace / asset.asset_id / "meta.json"
                            ).exists()
                            else 0,
                            tz=timezone.utc,
                        ).isoformat(),
                    )
                    row.setdefault("group", "未分组")
                data["next_order"] = len(ordered) + 1
                data["order_initialized"] = True
                changed = True
            for asset in assets:
                if asset.asset_id in data["assets"]:
                    continue
                order = int(data.get("next_order", 1))
                data["assets"][asset.asset_id] = {
                    "order": order,
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                    "group": group or "未分组",
                }
                data["next_order"] = order + 1
                changed = True
            if changed:
                self._save_library(data)
            return data

    def set_group(self, asset_id: str, group: str) -> None:
        group = group.strip()[:60] or "未分组"
        with self.lock:
            data = self._library()
            if asset_id not in data["assets"]:
                raise ValueError("素材不存在")
            if group not in data["groups"]:
                data["groups"].append(group)
            data["assets"][asset_id]["group"] = group
            self._save_library(data)

    def set_groups(self, asset_ids: list[str], group: str) -> int:
        group = group.strip()[:60] or "未分组"
        unique_ids = list(dict.fromkeys(asset_ids))
        with self.lock:
            data = self._library()
            missing = [aid for aid in unique_ids if aid not in data["assets"]]
            if missing:
                raise ValueError(f"有 {len(missing)} 个素材不存在")
            if group not in data["groups"]:
                data["groups"].append(group)
            for aid in unique_ids:
                data["assets"][aid]["group"] = group
            self._save_library(data)
        return len(unique_ids)

    def create_group(self, group: str) -> str:
        group = group.strip()[:60]
        if not group:
            raise ValueError("分组名称不能为空")
        with self.lock:
            data = self._library()
            if group not in data["groups"]:
                data["groups"].append(group)
                self._save_library(data)
        return group

    def groups(self) -> list[str]:
        return self._library().get("groups", ["未分组"])

    def asset_exists(self, asset_id: str) -> bool:
        with self.lock:
            if asset_id in self.known_asset_ids:
                return True
        scanned_ids = {asset.asset_id for asset in scan_assets(self.settings)}
        with self.lock:
            self.known_asset_ids.update(scanned_ids)
        return asset_id in scanned_ids

    def assets(self) -> list[dict]:
        with self.ingest_lock:
            assets = run_ingest(self.settings)
        library = self.register_assets(assets)
        rows = []
        for asset in assets:
            aid = asset.asset_id
            state_path = self.settings.paths.state / f"{aid}.json"
            state = read_json(state_path) if state_path.exists() else {}
            stages = state.get("stages", {})
            markdown = self.settings.paths.output_markdown / f"{aid}.md"
            transcript = self.settings.paths.workspace / aid / "transcript" / "full.json"
            job = self.jobs.get(aid)
            lib = library["assets"].get(aid, {})
            rows.append(
                {
                    "asset_id": aid,
                    "pipeline": asset.pipeline_type.value,
                    "filename": asset.source.filename,
                    "stages": stages,
                    "status": job.status
                    if job and job.status in {"queued", "running"}
                    else _status(stages, markdown),
                    "has_markdown": markdown.exists(),
                    "has_transcript": transcript.exists(),
                    "import_order": lib.get("order", 0),
                    "imported_at": lib.get("imported_at"),
                    "group": lib.get("group", "未分组"),
                }
            )
        return sorted(rows, key=lambda row: row["import_order"])

    def start(self, asset_id: str, force: str | None = None) -> Job:
        with self.lock:
            current = self.jobs.get(asset_id)
            if current and current.status in {"queued", "running"}:
                return current
            job = Job(asset_id=asset_id)
            self.jobs[asset_id] = job
        threading.Thread(target=self._run, args=(job, force), daemon=True).start()
        return job

    def _run(self, job: Job, force: str | None) -> None:
        job.status = "running"
        cmd = [sys.executable, str(self.settings.root / "run.py"), "--asset", job.asset_id]
        if force:
            cmd.extend(["--force", force])
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.settings.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            job.log.append(f"启动处理进程失败：{exc}")
            job.returncode = 1
            job.status = "failed"
            return
        assert process.stdout is not None
        for line in process.stdout:
            job.log.append(line.rstrip())
            if len(job.log) > 500:
                del job.log[:100]
        job.returncode = process.wait()
        if job.returncode != 0:
            job.status = "failed"
            return

        # CLI deliberately exits 0 when an Agent task has been prepared.  That
        # is not pipeline completion: re-read persisted stage state so the web
        # UI can distinguish a finished document from work requiring AI.
        state_path = self.settings.paths.state / f"{job.asset_id}.json"
        stages = read_json(state_path).get("stages", {}) if state_path.exists() else {}
        job.status = _status(
            stages,
            self.settings.paths.output_markdown / f"{job.asset_id}.md",
        )


def _status(stages: dict, markdown: Path) -> str:
    if any(v == "failed" for v in stages.values()):
        return "failed"
    if any(v == "waiting_agent" for v in stages.values()):
        return "needs_ai"
    if markdown.exists():
        return "done"
    if stages:
        return "pending"
    return "new"


def _safe_filename(value: str) -> str:
    name = Path(unquote(value)).name
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "-", name).strip(". ")
    if not name:
        raise ValueError("文件名无效")
    return name


def _safe_asset_id(value: str) -> str:
    asset_id = unquote(value).strip()
    if (
        not asset_id
        or len(asset_id) > 120
        or Path(asset_id).name != asset_id
        or asset_id in {".", ".."}
        or not re.fullmatch(r"[\w\u4e00-\u9fff-]+", asset_id)
    ):
        raise ValueError("素材标识无效")
    return asset_id


class Handler(BaseHTTPRequestHandler):
    server_version = "MediaDistill/0.1"

    @property
    def app(self) -> AppState:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            return self._file("index.html")
        if path.startswith("/static/"):
            return self._file(path.removeprefix("/static/"))
        if path == "/api/assets":
            assets = self.app.assets()
            return self._json({"assets": assets, "groups": self.app.groups()})
        if path.startswith("/api/job/"):
            aid = self._asset_id(path, "/api/job/")
            if aid is None:
                return
            job = self.app.jobs.get(aid)
            return self._json(
                {"status": "idle", "log": []}
                if not job
                else {"status": job.status, "log": job.log, "returncode": job.returncode}
            )
        if path.startswith("/api/markdown/"):
            return self._text_artifact(path, "markdown")
        if path.startswith("/api/transcript/"):
            return self._text_artifact(path, "transcript")
        if path.startswith("/download/"):
            aid = self._asset_id(path, "/download/")
            if aid is None:
                return
            file = self.app.settings.paths.output_markdown / f"{aid}.md"
            if not file.exists():
                return self.send_error(HTTPStatus.NOT_FOUND)
            data = file.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header(
                "Content-Disposition", f"attachment; filename*=UTF-8''{quote(file.name)}"
            )
            self.send_header("Content-Length", str(len(data)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._origin_allowed():
            return self._json(
                {"ok": False, "error": "拒绝来自其他网页的本地请求"},
                HTTPStatus.FORBIDDEN,
            )
        path = urlparse(self.path).path
        if path == "/api/upload":
            return self._upload()
        if path == "/api/groups":
            try:
                payload = self._read_json()
                group = self.app.create_group(str(payload.get("group") or ""))
                return self._json({"ok": True, "group": group})
            except (ValueError, json.JSONDecodeError) as exc:
                return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if path.startswith("/api/process/"):
            aid = self._asset_id(path, "/api/process/")
            if aid is None:
                return
            force = self.headers.get("X-Force-Stage")
            job = self.app.start(aid, force)
            return self._json({"asset_id": aid, "status": job.status}, HTTPStatus.ACCEPTED)
        if path.startswith("/api/group/"):
            aid = self._asset_id(path, "/api/group/")
            if aid is None:
                return
            try:
                payload = self._read_json()
                self.app.set_group(aid, str(payload.get("group") or "未分组"))
                return self._json({"ok": True})
            except (ValueError, json.JSONDecodeError) as exc:
                return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        if path == "/api/group-batch":
            try:
                payload = self._read_json()
                asset_ids = payload.get("asset_ids") or []
                if not isinstance(asset_ids, list) or not asset_ids:
                    raise ValueError("请选择至少一个素材")
                count = self.app.set_groups(
                    [str(x) for x in asset_ids], str(payload.get("group") or "未分组")
                )
                return self._json({"ok": True, "count": count})
            except (ValueError, json.JSONDecodeError) as exc:
                return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        self.send_error(HTTPStatus.NOT_FOUND)

    def _upload(self) -> None:
        target: Path | None = None
        created = False
        try:
            filename = _safe_filename(self.headers.get("X-Filename", ""))
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20 * 1024**3:
                raise ValueError("文件为空或超过 20GB")
            suffix = Path(filename).suffix.lower()
            allowed = set(self.app.settings.video_extensions + self.app.settings.audio_extensions)
            if suffix not in allowed:
                raise ValueError(f"暂不支持 {suffix or '无扩展名'} 文件")
            target_dir = (
                self.app.settings.paths.video_input
                if suffix in self.app.settings.video_extensions
                else self.app.settings.paths.audio_input
            )
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / filename
            remaining = length
            try:
                stream = target.open("xb")
                created = True
            except FileExistsError as exc:
                raise ValueError("同名文件已存在") from exc
            with stream:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("上传中断")
                    stream.write(chunk)
                    remaining -= len(chunk)
            with self.app.ingest_lock:
                assets = run_ingest(self.app.settings)
            match = next((a for a in assets if a.source.filename == filename), None)
            if match:
                group = unquote(self.headers.get("X-Group", "未分组"))
                self.app.register_assets([match], group=group)
            return self._json({"ok": True, "asset_id": match.asset_id if match else None})
        except ValueError as exc:
            if created and target is not None:
                target.unlink(missing_ok=True)
            return self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except OSError as exc:
            if created and target is not None:
                target.unlink(missing_ok=True)
            return self._json(
                {"ok": False, "error": f"写入素材失败：{exc.strerror or exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _text_artifact(self, path: str, kind: str) -> None:
        prefix = f"/api/{kind}/"
        aid = self._asset_id(path, prefix)
        if aid is None:
            return
        if kind == "markdown":
            file = self.app.settings.paths.output_markdown / f"{aid}.md"
            text = file.read_text(encoding="utf-8") if file.exists() else ""
            return self._json({"content": text, "exists": file.exists()})
        file = self.app.settings.paths.workspace / aid / "transcript" / "full.json"
        if not file.exists():
            return self._json({"content": "", "exists": False})
        data = read_json(file)
        return self._json(
            {"content": data.get("text", ""), "segments": data.get("segments", []), "exists": True}
        )

    def _file(self, name: str) -> None:
        root = Path(__file__).parent / "static"
        file = (root / name).resolve()
        if root.resolve() not in file.parents or not file.exists():
            return self.send_error(HTTPStatus.NOT_FOUND)
        data = file.read_bytes()
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _asset_id(self, path: str, prefix: str) -> str | None:
        try:
            asset_id = _safe_asset_id(path.removeprefix(prefix))
            if not self.app.asset_exists(asset_id):
                raise ValueError("素材不存在")
            return asset_id
        except ValueError as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return None

    def _read_json(self, max_bytes: int = 1024 * 1024) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > max_bytes:
            raise ValueError("请求内容过大")
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("请求内容必须是 JSON 对象")
        return payload

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host", "")
        return origin in {f"http://{host}", f"https://{host}"}

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")


def serve(settings: Settings, port: int = 8765) -> None:
    state = AppState(settings)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.app = state  # type: ignore[attr-defined]
    url = f"http://127.0.0.1:{port}"
    print(f"MediaDistill 本地工作台：{url}")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n本地工作台已停止")
    finally:
        server.server_close()
