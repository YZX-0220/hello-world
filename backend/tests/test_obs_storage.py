"""OBS 存储层与直传/秒传链路集成测试。"""

import uuid

import pytest
from app.providers.email.fake import fake_instance
from app.storage.obs import ObsStorage
from httpx import AsyncClient

ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "password123"


async def _register(client: AsyncClient, tag: str) -> None:
    email = f"obs-{tag}-{uuid.uuid4().hex[:8]}@test.com"
    await client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    code = fake_instance.sent[-1]["code"]
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "code": code, "password": PASSWORD}
    )
    assert resp.status_code == 201, resp.text


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("hw_csrf") or "", "Origin": ORIGIN}


@pytest.fixture
def mock_obs(monkeypatch):
    from unittest.mock import MagicMock, patch
    from app.core.config import settings

    monkeypatch.setattr(settings, "huawei_cloud_obs_bucket", "mock-bucket")
    monkeypatch.setattr(settings, "huawei_cloud_obs_endpoint", "obs.cn-east-5.myhuaweicloud.com")
    monkeypatch.setattr(settings, "huawei_cloud_obs_access_key", "mock-ak")
    monkeypatch.setattr(settings, "huawei_cloud_obs_secret_key", "mock-sk")

    with patch("app.storage.obs.ObsClient") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client

        # Mock createSignedUrl
        signed_mock = MagicMock()
        signed_mock.signedUrl = "https://mock-bucket.obs.cn-east-5.myhuaweicloud.com/mock-url"
        client.createSignedUrl.return_value = signed_mock

        # Mock getObjectMetadata
        meta_mock = MagicMock()
        meta_mock.status = 200
        meta_mock.header = [
            ("etag", '"7f45f1e9a7e9ac4c71b8483cd773f344"'),
            ("content-length", "1024"),
            ("content-type", "image/png"),
        ]
        client.getObjectMetadata.return_value = meta_mock

        # Mock putContent
        put_mock = MagicMock()
        put_mock.status = 200
        client.putContent.return_value = put_mock

        # Mock setBucketFetchJob
        fetch_mock = MagicMock()
        fetch_mock.status = 200
        fetch_mock.body = MagicMock(id="job-fetch-123")
        client.setBucketFetchJob.return_value = fetch_mock

        yield client


@pytest.mark.asyncio
async def test_obs_storage_methods(mock_obs):
    """测试 ObsStorage 驱动的基础方法。"""
    storage = ObsStorage(
        endpoint="obs.cn-east-5.myhuaweicloud.com",
        bucket="test-bucket",
        access_key="test-ak",
        secret_key="test-sk",
    )

    # 1. 预签名上传
    upload_url = storage.generate_presigned_upload_url("test.png", "image/png")
    assert "mock-url" in upload_url

    # 2. 预签名下载
    download_url = storage.generate_presigned_download_url("test.png", filename="demo.png")
    assert "mock-url" in download_url

    # 3. 查元数据
    meta = storage.get_object_metadata("test.png")
    assert meta["etag"] == "7f45f1e9a7e9ac4c71b8483cd773f344"
    assert meta["size_bytes"] == 1024

    # 4. 写入
    stored = storage.write_stream(b"hello", "test.txt", final_key="test.txt")
    assert stored.size_bytes == 5

    # 5. 异步转存外部 URL
    job_id = storage.async_fetch_object("https://example.com/video.mp4", "outputs/test.mp4")
    assert job_id == "job-fetch-123"


@pytest.mark.asyncio
async def test_upload_intent_and_complete_flow(client: AsyncClient, mock_obs):
    """测试 POST /assets/upload-intent ➔ /assets/{id}/complete 完整两阶段链路与秒传。"""
    await _register(client, "obs-user")
    headers = _csrf(client)

    # 1. 申请直传凭证
    intent_payload = {
        "filename": "banner.png",
        "purpose": "reference",
        "kind": "image",
        "byte_size": 1024,
        "content_type": "image/png",
        "file_hash": "7f45f1e9a7e9ac4c71b8483cd773f344",
    }
    resp = await client.post("/api/v1/assets/upload-intent", json=intent_payload, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["is_duplicate"] is False
    assert "upload_url" in data
    assert data["upload_url"] is not None
    asset_id = data["asset_id"]

    # 2. 通知直传完成并核验入库
    complete_resp = await client.post(
        f"/api/v1/assets/{asset_id}/complete",
        json={"file_hash": "7f45f1e9a7e9ac4c71b8483cd773f344"},
        headers=headers,
    )
    assert complete_resp.status_code == 200, complete_resp.text
    asset_view = complete_resp.json()
    assert asset_view["status"] == "ready"
    assert asset_view["size_bytes"] == 1024

    # 3. 秒传测试：再次申请相同 Hash 的直传意图
    duplicate_resp = await client.post(
        "/api/v1/assets/upload-intent", json=intent_payload, headers=headers
    )
    assert duplicate_resp.status_code == 200
    dup_data = duplicate_resp.json()
    assert dup_data["is_duplicate"] is True
    assert dup_data["asset_id"] == asset_id
    assert dup_data["upload_url"] is None  # 秒传跳过实际上传

    # 4. 获取直链
    direct_url_resp = await client.get(f"/api/v1/assets/{asset_id}/direct-url")
    assert direct_url_resp.status_code == 200
    assert "direct_url" in direct_url_resp.json()
