"""补齐火山方舟视频生成 Token 消耗记录的运维脚本。

用法示例（在 backend 目录下运行）：
    # 1. 默认：先回填近期未过期的单任务用量，再按 GetInferenceUsage 补齐最近 30 天历史差额
    uv run python scripts/sync_ark_token_usage.py

    # 2. 指定起止日期（自动按 30 天分段，幂等去重）
    uv run python scripts/sync_ark_token_usage.py --start 2026-11-01 --end 2026-11-15

    # 3. 仅拉取单任务明细（不调用 GetInferenceUsage）
    uv run python scripts/sync_ark_token_usage.py --skip-inference-usage
"""

import asyncio
import sys
from argparse import ArgumentParser
from datetime import date, timedelta
from pathlib import Path

# 确保从仓库根目录或 scripts/ 目录直接执行时也能导入 app
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.ark_usage_service import (  # noqa: E402
    backfill_ark_video_usage,
    sync_ark_inference_usage_to_records,
)


def _parse_args():
    today = date.today()
    default_start = (today - timedelta(days=30)).isoformat()
    parser = ArgumentParser(description="补齐火山方舟视频生成 Token 消耗记录")
    parser.add_argument(
        "--start",
        default=default_start,
        help=f"GetInferenceUsage 起始日期 (YYYY-MM-DD)，默认 {default_start}",
    )
    parser.add_argument(
        "--end",
        default=today.isoformat(),
        help=f"GetInferenceUsage 结束日期 (YYYY-MM-DD)，默认 {today.isoformat()}",
    )
    parser.add_argument(
        "--skip-tasks",
        action="store_true",
        help="跳过按单任务 provider_task_id 回填",
    )
    parser.add_argument(
        "--skip-inference-usage",
        action="store_true",
        help="跳过按 GetInferenceUsage 补齐历史差额",
    )
    return parser.parse_args()


async def _run() -> None:
    args = _parse_args()
    async with SessionLocal() as session:
        if not args.skip_tasks:
            task_stats = await backfill_ark_video_usage(session)
            print(f"[backfill_ark_video_usage] {task_stats}")

        if not args.skip_inference_usage:
            if not settings.ark_access_key or not settings.ark_secret_key:
                print(
                    "[sync_ark_inference_usage_to_records] 跳过：未配置 ARK_ACCESS_KEY / ARK_SECRET_KEY"
                )
                return
            sync_stats = await sync_ark_inference_usage_to_records(
                session,
                start_time=args.start,
                end_time=args.end,
            )
            print(f"[sync_ark_inference_usage_to_records] {sync_stats}")


if __name__ == "__main__":
    asyncio.run(_run())
