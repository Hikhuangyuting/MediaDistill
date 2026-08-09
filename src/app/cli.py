from __future__ import annotations

import argparse
import sys

from src.app.orchestrator import Orchestrator
from src.core.config import load_settings
from src.core.errors import PipelineError
from src.core.logging import PipelineLogger
from src.core.utils import ensure_dir


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run.py",
        description="MediaDistill — 本地影音知识萃取工具",
    )
    p.add_argument("--list", action="store_true", help="列出素材与进度")
    p.add_argument("--status", nargs="?", const="*", metavar="ASSET", help="查看断点状态")
    p.add_argument("--asset", type=str, help="只处理指定 asset_id")
    p.add_argument("--web", action="store_true", help="启动本地网页工作台")
    p.add_argument("--port", type=int, default=8765, help="网页工作台端口（默认 8765）")
    p.add_argument(
        "--through",
        type=str,
        help="跑到指定阶段即停（如 speech / vision / knowledge）",
    )
    p.add_argument(
        "--force",
        type=str,
        action="append",
        default=[],
        help="强制重跑阶段（可重复；或 all）",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    ensure_dir(settings.paths.workspace)
    ensure_dir(settings.paths.logs)
    ensure_dir(settings.paths.output_markdown)

    logger = PipelineLogger(settings.paths.logs / "latest")
    orch = Orchestrator(settings, logger)
    force = set(args.force or [])

    try:
        if args.web:
            from src.web.server import serve

            serve(settings, port=args.port)
            return 0
        if args.list:
            orch.list_assets()
            return 0
        if args.status is not None:
            aid = None if args.status == "*" else args.status
            orch.status(aid)
            return 0

        if args.asset:
            # ensure catalog/meta
            orch.ingest()
            result = orch.run_asset(args.asset, through=args.through, force=force)
            return 0 if result in ("ok", "waiting_agent") else 1

        orch.run_all(through=args.through, force=force)
        return 0

    except PipelineError as err:
        logger.error(err.format())
        return 1
    except FileNotFoundError as err:
        logger.error(
            PipelineError(
                reason=str(err),
                missing="素材 meta 或源文件",
                recovery=["先运行 python run.py --list", "确认 asset_id 正确"],
            ).format()
        )
        return 1
    except KeyboardInterrupt:
        logger.info("已中断")
        return 130
    finally:
        logger.close()


if __name__ == "__main__":
    sys.exit(main())
