"""存量本地资产同步迁移到华为云 OBS 脚本。

读取 SQLite 数据库中所有 storage_provider == 'local' 或指向本地 data/ 的素材，
逐个上传至华为云 OBS 存储桶对应路径，并更新数据库记录。
支持幂等重复运行（已上传的跳过）。
"""

import asyncio
import sys
from pathlib import Path

# 确保 backend 根目录在 Python 模块搜索路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.db.models.asset import Asset
from app.db.session import SessionLocal
from app.storage.obs import ObsStorage
from sqlmodel import col, select


async def migrate_local_to_obs() -> None:
    print("=== 开始存量本地素材向华为云 OBS 同步迁移 ===")
    if not (
        settings.huawei_cloud_obs_endpoint
        and settings.huawei_cloud_obs_bucket
        and settings.huawei_cloud_obs_access_key
        and settings.huawei_cloud_obs_secret_key
    ):
        print("错误: 华为云 OBS 配置缺失，请检查 .env")
        return

    obs = ObsStorage()
    migrated_count = 0
    skipped_count = 0
    failed_count = 0

    async with SessionLocal() as session:
        statement = select(Asset).where(
            col(Asset.status) != "deleted",
            col(Asset.storage_provider) == "local",
        )
        assets = (await session.exec(statement)).all()
        print(f"扫描到待迁移本地资产数: {len(assets)}")

        for asset in assets:
            local_path = Path(settings.storage_root) / asset.storage_key
            if not local_path.is_file():
                # 尝试直连绝对/相对路径
                local_path = Path(asset.storage_key)
            if not local_path.is_file():
                print(f"⚠️ 文件丢失跳过: asset_id={asset.id}, path={asset.storage_key}")
                skipped_count += 1
                continue

            # 规范化目标 OBS Object Key
            ext = local_path.suffix.lstrip(".") or "bin"
            target_key = f"assets/{asset.user_id}/{asset.kind}s/{asset.id}.{ext}"

            try:
                # 检查 OBS 是否已有该文件
                if not obs.exists(target_key):
                    data = local_path.read_bytes()
                    obs.write_stream(data, target_key, final_key=target_key)
                    print(f"已上传: {asset.id} -> {target_key}")
                else:
                    print(f"云端已存在: {target_key}")

                # 更新数据库记录
                asset.storage_provider = "obs"
                asset.storage_key = target_key
                migrated_count += 1
            except Exception as exc:
                print(f"❌ 上传失败 asset_id={asset.id}: {exc}")
                failed_count += 1

        await session.commit()

    print("\n=== 迁移完成汇总 ===")
    print(f"成功迁移: {migrated_count}")
    print(f"跳过/丢失: {skipped_count}")
    print(f"失败数: {failed_count}")


if __name__ == "__main__":
    asyncio.run(migrate_local_to_obs())
