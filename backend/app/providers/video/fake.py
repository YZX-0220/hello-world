"""Fake 视频厂商：返回可控状态序列（排队 → 运行 → 成功），供开发/演示与 Contract Test。

不进行任何真实调用；result_url 为占位地址，阶段 8 只验证状态机流转，阶段 9 才做下载/双轨。
"""

import secrets

from app.providers.video.base import (
    AdapterContext,
    VideoProvider,
    VideoSubmitResult,
    VideoTaskStatus,
)

_STATUS_SEQUENCE = ["queued", "running", "running", "succeeded"]


class FakeVideoProvider(VideoProvider):
    code = "fake"

    def __init__(self) -> None:
        self._steps: dict[str, int] = {}

    async def submit(self, request: dict, ctx: AdapterContext) -> VideoSubmitResult:
        task_id = f"fake-{secrets.token_hex(4)}"
        self._steps[task_id] = 0
        return VideoSubmitResult(provider_task_id=task_id, provider_context_id=None)

    async def poll(self, task_id: str, ctx: AdapterContext) -> VideoTaskStatus:
        step = self._steps.get(task_id, 0)
        self._steps[task_id] = step + 1
        raw = _STATUS_SEQUENCE[min(step, len(_STATUS_SEQUENCE) - 1)]
        progress = None if raw != "running" else min(95, 5 + step * 20)
        return VideoTaskStatus(raw_status=raw, progress=progress)

    async def fetch_result_url(self, task_id: str, ctx: AdapterContext) -> str | None:
        return f"https://fake.example.com/results/{task_id}.mp4"

    async def download_result(self, task_id: str, ctx: AdapterContext) -> bytes | None:
        return b"FAKE_VIDEO_BYTES"

    async def cancel(self, task_id: str, ctx: AdapterContext) -> bool:
        return True


fake_video_instance = FakeVideoProvider()
