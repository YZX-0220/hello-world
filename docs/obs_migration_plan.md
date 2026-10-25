# 华为云 OBS 存储方案迁移与过渡实施方案

## 1. 迁移目标与总体策略

### 1.1 核心原则
1. **平滑演进，零停机（Zero Downtime）**：迁移期间不中断任何线上用户与正在生成的视频任务。
2. **渐进式过渡（Dual-Track Transition）**：
   - **优先新增 OBS 新规范接口**，提供直传（Intent / Complete）与直链获取。
   - **原有接口继续保留并内部透明改造**：存量前端调用旧上传接口时，后端改走内存流式推送到 OBS；存量前端请求旧下载接口时，后端 302 重定向至 OBS 预签名直链，立即卸载服务器带宽压力。
3. **数据完全入桶**：完成存量历史本地媒体文件（`data/uploads`、`data/videos`）的一键安全同步入桶，保证数据不丢。
4. **前端解耦后清理**：待前端完全适配 OBS 直传 SDK 与直链接口后，统一废弃旧的 `multipart/form-data` 本地磁盘读写逻辑。

---

## 2. 详细演进阶段划分

```
┌────────────────────────────────────────────────────────────────────────┐
│ 阶段一：底层驱动适配与配置就绪 (Backend Storage Layer)                      │
│ - 引入 esdk-obs-python                                                 │
│ - 实现 ObsStorageProvider (继承 StorageProvider)                       │
│ - 支持生成预签名 PUT/GET URL、元数据查询、asyncFetch 异步拉取             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ 阶段二：新旧接口共存与双轨兼容 (API & Service Layer)                      │
│ - 新增 POST /api/v1/assets/upload-intent (预检/秒传)                   │
│ - 新增 POST /api/v1/assets/{id}/complete (确认/ETag比对)               │
│ - 新增 GET  /api/v1/assets/{id}/direct-url (获取 OBS 预签名直链)        │
│ - 改造旧 POST /api/v1/assets (透明流式写入 OBS，不在磁盘落盘)              │
│ - 改造旧 GET  /api/v1/assets/{id} (返回 302 重定向到 OBS 预签名 URL)    │
│ - 改造 VideoDownloadService：采用方式 A (asyncFetchObject) 转存视频     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ 阶段三：存量历史数据单向同步迁移 (Data Migration Script)                   │
│ - 编写 scripts/migrate_local_to_obs.py 脚本                            │
│ - 批量遍历 local 资产，上传至 OBS 对应 Key 并更新数据库 storage_path     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ 阶段四：前端对接与全链路验证 (Frontend Integration & Verification)        │
│ - 前端改造：素材上传改为获取 intent ➔ 直传 OBS ➔ complete 确认          │
│ - 前端剪辑导出：WebAV 导出 MP4 Blob ➔ 直接直传 OBS                     │
│ - 压测与带宽监控：确认 3M 服务器带宽无媒体流尖峰                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ 阶段五：退役清理 (Cleanup)                                             │
│ - 移除旧 multipart 服务端中转上传代码                                    │
│ - 清理 data/uploads 与 data/videos 磁盘历史冗余                         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 详细实施步骤

### 阶段一：底层存储驱动实现 (`app/storage/obs.py`)
1. **依赖确认**：在 `backend/pyproject.toml` 的 dependencies 中固定 `esdk-obs-python>=3.24.0`。
2. **实现驱动类**：
   - 继承 `app/storage/base.py:StorageProvider`。
   - 初始化 `ObsClient`（复用单例会话连接池）。
   - 编写关键方法：
     - `generate_presigned_upload_url(object_key, content_type, expires=1800) -> str`
     - `generate_presigned_download_url(object_key, expires=3600, filename=None) -> str`
     - `object_exists(object_key) -> bool`
     - `get_object_metadata(object_key) -> dict`（提取 ETag, Content-Length, Content-Type）
     - `async_fetch_object(remote_url, object_key) -> str`（方式 A：通知 OBS 异步抓取外部 URL）
     - `delete_object(object_key)`
3. **驱动工厂装配** (`app/storage/__init__.py`)：
   - 依据 `settings.huawei_cloud_obs_endpoint` 是否配置或 `STORAGE_BACKEND` 环境变量自动返回 `ObsStorageProvider`。

---

### 阶段二：API 接口改造与兼容设计

#### 2.1 新增接口（供前端新链路对接）
1. **`POST /api/v1/assets/upload-intent`**
   - **请求参数**：
     ```json
     {
       "filename": "background_music.mp3",
       "kind": "audio",
       "byte_size": 5242880,
       "content_type": "audio/mpeg",
       "file_hash": "7f45f1e9a7e9ac4c71b8483cd773f344"
     }
     ```
   - **业务逻辑**：
     - 校验 `byte_size` 是否超出该 `kind` 限制。
     - **秒传判定**：若 `file_hash` 非空，查询当前用户是否存在相同 Hash 且状态为 `ready` 的资产。
       - 命中：直接返回已有资产视图，`is_duplicate=true`，前端无需发送实际二进制数据。
     - **未命中**：生成新 `asset_id`，拼装 Object Key `assets/{user_id}/{kind}s/{asset_id}.{ext}`；
     - 调用 OBS 签署 PUT URL；
     - 数据库插入一条记录，`status="pending_upload"`，`storage_provider="obs"`，`storage_path=object_key`；
     - 返回 `{ "asset_id": "...", "upload_url": "https://...", "object_key": "...", "is_duplicate": false }`。

2. **`POST /api/v1/assets/{asset_id}/complete`**
   - **请求参数**：`{ "file_hash": "..." }`（可选）
   - **业务逻辑**：
     - 检查资产是否存在且归属当前用户。
     - 调用 OBS `get_object_metadata(asset.storage_path)`。
     - 核对存在性、真实 `byte_size` 与 `ETag`。
     - 写入 `status="ready"`，记录最终 Hash 与元数据，返回完整 `AssetView`。

3. **`GET /api/v1/assets/{asset_id}/direct-url`**
   - **业务逻辑**：鉴权通过后，生成有效时长为 1 小时的 OBS 预签名 GET 链接，支持前端作为 `<video>`、`<audio>` 或图片 `src` 直接消费。

#### 2.2 存量接口透明改造（向下兼容旧前端）
1. **`POST /api/v1/assets` (原文件上传)**：
   - 接收 `UploadFile`，不在本地磁盘创建文件。
   - 直接把输入流通过 `ObsClient.putContent` 或管道推送到 OBS。
   - 数据库记录 `storage_provider="obs"`。
2. **`GET /api/v1/assets/{asset_id}` (原文件流下载)**：
   - 若 `storage_provider == "obs"`，直接返回 `RedirectResponse(url=signed_url, status_code=302)`。
   - 浏览器收到 302 自动向华为云 OBS 拿分段数据，**立即切断对后端 3M 带宽的占用**。

#### 2.3 厂商视频回流改造 (`VideoDownloadService`)
- 废弃原先 `httpx.AsyncClient().get(stream=True)` 下载成片到 `data/videos/` 的逻辑。
- 采用 **方式 A**：
  - 任务状态变成 SUCCEEDED 时，获取厂商原链 `result_url`。
  - 调用 OBS `async_fetch_object(remote_url=result_url, object_key=f"outputs/{user_id}/{job_id}.mp4")`。
  - 创建对应的 `Asset(kind="video", storage_provider="obs", storage_path=...)`。
  - 任务完成后无需服务器出入带宽。

---

### 阶段三：历史存量数据迁移脚本 (`scripts/migrate_local_to_obs.py`)

编写一次性安全迁移脚本：
```python
# 核心逻辑伪代码
async def migrate_all_local_assets():
    # 1. 扫描数据库中所有 storage_provider == 'local' 或 storage_path 包含 data/ 的资产
    assets = await repo.list_local_assets()
    for asset in assets:
        local_file = Path(asset.storage_path)
        if not local_file.exists():
            continue
        
        # 2. 构造规范 OBS Key
        obs_key = f"migrated/{asset.user_id}/{asset.kind}s/{asset.id}{local_file.suffix}"
        
        # 3. 校验并上传到 OBS
        obs_client.putFile(bucketName=bucket, objectKey=obs_key, file_path=str(local_file))
        
        # 4. 更新数据库
        asset.storage_provider = "obs"
        asset.storage_path = obs_key
        await session.commit()
        print(f"Migrated asset {asset.id} -> {obs_key}")
```
*注：脚本支持断点续传（重复运行跳过已迁移记录），并在迁移完毕且核验 ETag 无误后再归档本地物理文件。*

---

### 阶段四：前端对接规范指南

前端在实施对接时只需做两处小调整：

1. **素材上传改造**：
   ```javascript
   // 1. 预检
   const intent = await api.post('/api/v1/assets/upload-intent', {
     filename: file.name,
     kind: 'video',
     byte_size: file.size,
     content_type: file.type
   });
   
   if (intent.is_duplicate) {
     return intent.asset_id; // 秒传成功
   }
   
   // 2. 浏览器直推 OBS (必须保持 Content-Type 与 intent 声明一致)
   await fetch(intent.upload_url, {
     method: 'PUT',
     body: file,
     headers: { 'Content-Type': file.type }
   });
   
   // 3. 确认入库
   const asset = await api.post(`/api/v1/assets/${intent.asset_id}/complete`);
   return asset.id;
   ```

2. **视频播放与剪辑流拉取**：
   - 凡是展示视频、音频或图片，从后端获取 `direct_url`（或直接使用 `/api/v1/assets/{id}` 的 302 重定向能力）。
   - 前端 WebAV / Video 标签直接消费华为云直链，流畅拖拽时间轴。

---

## 4. 故障回滚与应急预案

1. **环境配置开关**：
   - 保留配置项 `STORAGE_BACKEND=local|obs`，默认在配置了 OBS 凭据时启用 OBS；若 OBS 发生云端故障，可配置降级回本地（需预留应急磁盘空间）。
2. **凭据安全**：
   - OBS AK/SK 仅保存在服务器环境变量 `.env`，**绝对不泄露给前端**；前端永远只拿到包含签名参数的受限临时 URL（通常 15~30 分钟过期）。
3. **防刷与限额保护**：
   - `upload-intent` 接口受现有接口统一限流（Rate Limit）与用户资产总数/单文件上限保护，未确认的 `pending_upload` 记录设有 24 小时自动回收机制。
