# 纯前端 WebAV 视频剪辑、用户资料库与存储配额后端架构设计方案

## 1. 背景与核心目标

### 1.1 业务场景与瓶颈约束
1. **服务器带宽约束**：后端服务器公网带宽仅有 **3Mbps**（峰值约 350KB/s），严禁任何视频流转码或媒体重编排经过业务服务器。
2. **对象存储计费特征**：华为云 OBS 已购置 40GB 标准存储资源包，但**不包含公网下行流量包**（按量计费约 0.50 元/GB）。用户每次播放或拉取云端视频都会产生成本。
3. **剪辑计算外包**：现代浏览器具备强大的 WebCodecs 与 WebAssembly 算力。采用 **WebAV** 纯前端视频剪辑框架，在客户端完成多轨道音视频混合、文字贴纸合成、滤镜渲染及 MP4 编码打包。
4. **本地资料库协同降本**：利用现代浏览器 **File System Access API** 访问用户本地工作目录。当使用云端素材时，前端下载至本地资料目录永久复用，后续时间线拖拽、多工程复用实现 **0 流量消耗**。

### 1.2 核心设计决策
1. **纯前端剪辑与零服务端负载**：后端不引入任何 `ffmpeg` 进程，仅提供剪辑工程草稿（Timeline JSON）持久化与素材元数据服务。
2. **剪辑导出云端自选（Opt-in Cloud Storage）**：成片在前端合成后，**用户可自由勾选是否保存至云端资料库**。
   - 若不勾选：直接由浏览器触发本地文件保存，不占用云端配额与上传带宽。
   - 若勾选：走两阶段直传通道（`upload-intent` ➔ OBS 直传 ➔ `complete`）归档入库。
3. **配额管理策略（1GB 默认配额 + 动态聚合与 Redis 缓存）**：
   - 默认配额：`DEFAULT_USER_STORAGE_QUOTA_GB = 1.0`（通过配置环境变量注入）。
   - **`storage_used_bytes` 不硬性持久化入 SQL 表**：由数据库有效资产 `Asset.size_bytes` 实时聚合求和，并缓存在 Redis（TTL 30~60 分钟），在资产增删时由事件驱动刷新，保证最终一致性与轻量化。

---

## 2. 总体架构与数据流图

```
                     ┌──────────────────────────────────────────────┐
                     │             前端浏览器 / WebApp              │
                     │  ┌───────────────────┐ ┌──────────────────┐ │
                     │  │ WebAV 剪辑引擎    │ │ 本地文件夹句柄   │ │
                     │  │ (WebCodecs+WebAssembly)│ │ (File System API)│ │
                     │  └─────────┬─────────┘ └────────┬─────────┘ │
                     └────────────┼────────────────────┼───────────┘
                                  │                    │
              ① 保存草稿 / 查配额  │                    │ ③ 下载云端资产并
              (几 KB JSON)        │                    │    本地建立指纹索引
                                  ▼                    ▼
┌──────────────────────────────────────────┐     ┌──────────────────────────────────┐
│             FastAPI 控制面               │     │        华为云 OBS 存储桶          │
│ 1. 剪辑工程草稿持久化 (Timeline JSON)    │     │       (hello-world-yzx)          │
│ 2. 资料库检索与分类                      │     └─────────────────▲────────────────┘
│ 3. 配额校验 (1GB 配额拦截)               │                       │
│ 4. Redis 容量缓存驱动                    │                       │ ④ 可选直传导出成片
└──────────────────┬───────────────────────┘                       │ (PUT 零中转)
                   │                                               │
                   ▼                                               │
┌──────────────────────────────────────────┐                       │
│        Redis 缓存 & SQLite 数据库        │                       │
│ - Redis: user_quota:{uid}:used (String)  │───────────────────────┘
│ - DB: clip_projects / assets 表          │
└──────────────────────────────────────────┘
```

---

## 3. 数据模型设计

### 3.1 剪辑工程表 (`clip_projects`)
用于持久化 WebAV 时间线草稿，支持随时中断、多端漫游或跨天恢复：

```python
class ClipProject(SQLModel, table=True):
    __tablename__ = "clip_projects"

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True, ondelete="CASCADE")
    title: str = Field(default="未命名工程", max_length=100)
    description: str = Field(default="", max_length=500)
    
    # WebAV 时间线草稿结构（JSON 字符串），包含 tracks、clips、effects、transitions 等
    timeline_json: str = Field(default="{}", sa_column=Column(Text))
    
    # 剪辑配置元数据
    duration_ms: int = Field(default=0)  # 总时长（毫秒）
    fps: int = Field(default=30)
    width: int = Field(default=1080)
    height: int = Field(default=1920)
    
    cover_asset_id: str | None = Field(default=None, foreign_key="assets.id", ondelete="SET NULL")
    exported_asset_id: str | None = Field(default=None, foreign_key="assets.id", ondelete="SET NULL")
    
    version: int = Field(default=1)  # 乐观锁版本号
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
```

### 3.2 资产表扩展 (`Asset`)
复用现有 `assets` 模型，在业务语义上支持资料库来源分类与 WebAV 元数据注入：
- `purpose` 扩展：
  - `source_video` / `reference`: 用户原始上传素材
  - `ai_generated`: 平台 AI 生成视频任务回流
  - `clip_export`: 前端 WebAV 剪辑合成导出成片
- `extra_metadata` (可选 JSON 字段)：存放音视频采样率、通道数、精确帧率等，供 WebAV 初始化时快速探测。

---

## 4. 容量配额计算与 Redis 缓存机制

### 4.1 配置项 (`app/core/config.py`)
```python
# 默认用户云端存储配额（GB）
DEFAULT_USER_STORAGE_QUOTA_GB: float = 1.0
```

### 4.2 实时聚合与 Redis 缓存策略
避免在 `users` 关系表中维护冗余易漂移的 `storage_used_bytes`，采用 **Cache-Aside + 延迟失效/原子更新** 机制：

1. **缓存 Key 定义**：
   - `user_quota:{user_id}:used`（存储已用字节数整数）
   - TTL：设置为 3600 秒（1 小时）。
2. **计算流程 (`get_user_storage_used_bytes`)**：
   - **Step 1**：优先查询 Redis `user_quota:{user_id}:used`。
   - **Step 2**：若命中缓存，直接返回；
   - **Step 3**：若未命中（Cache Miss），向 SQLite 数据库执行聚合查询：
     ```sql
     SELECT COALESCE(SUM(size_bytes), 0)
     FROM assets
     WHERE user_id = :uid AND status != 'deleted';
     ```
   - **Step 4**：将聚合结果写回 Redis，并设置 1 小时过期。
3. **缓存失效与增量驱动**：
   - **直传完成 (`POST /assets/{id}/complete`)**：
     调用 `redis.incrby(f"user_quota:{user_id}:used", asset.size_bytes)` 或直接 `redis.delete(...)` 触发重算。
   - **资产删除 (`DELETE /assets/{id}`)**：
     调用 `redis.decrby(f"user_quota:{user_id}:used", asset.size_bytes)` 或清除缓存。

### 4.3 上传预检硬拦截 (`POST /assets/upload-intent`)
在下发预签名 PUT 地址前，强制校验配额：
```python
max_bytes = int(settings.default_user_storage_quota_gb * 1024 * 1024 * 1024)
used_bytes = await quota_service.get_user_storage_used(user.id)

if used_bytes + request.byte_size > max_bytes:
    raise AppError(
        STORAGE_QUOTA_EXCEEDED,
        f"云端资料库空间不足。当前已用 {used_bytes / (1024**2):.1f}MB，配额 {settings.default_user_storage_quota_gb}GB"
    )
```

---

## 5. API 接口定义

### 5.1 用户资料库与配额接口

#### 1. 查询当前用量与配额
- **`GET /api/v1/library/quota`**
- **响应示例**：
  ```json
  {
    "quota_bytes": 1073741824,
    "used_bytes": 314572800,
    "available_bytes": 759169024,
    "quota_gb": 1.0,
    "usage_percent": 29.3,
    "asset_count": 12
  }
  ```

#### 2. 资料库资源列表检索
- **`GET /api/v1/library/assets`**
- **Query 参数**：
  - `kind`: `video` | `image` | `audio`
  - `purpose`: `all` | `source_video` | `ai_generated` | `clip_export`
  - `q`: 搜索原文件名
  - `limit`: 分页大小（默认 20）
  - `cursor`: 分页游标
- **响应内容**：列表项携带 `sha256`、`mime_type`、`duration_ms`、`width`、`height`，以及供前端直接拉取下载的预签名直链。

---

### 5.2 WebAV 剪辑工程管理接口

#### 1. 获取剪辑草稿列表
- **`GET /api/v1/clip-projects`**
- 返回用户的剪辑工程摘要列表（标题、时长、最后更新时间、封面图等）。

#### 2. 创建剪辑草稿
- **`POST /api/v1/clip-projects`**
- **请求体**：
  ```json
  {
    "title": "短视频草稿_20261026",
    "width": 1080,
    "height": 1920,
    "fps": 30
  }
  ```

#### 3. 获取草稿详情及时间线
- **`GET /api/v1/clip-projects/{id}`**
- 返回包含 `timeline_json` 的完整工程数据，前端 WebAV 读取后直接反序列化恢复轨道状态。

#### 4. 自动保存时间线草稿
- **`PUT /api/v1/clip-projects/{id}`**
- 前端 WebAV 设立静默防抖自动保存（如每修改 5 秒自动触发一次）：
  ```json
  {
    "title": "更新后的标题",
    "timeline_json": "{\"tracks\":[...]}",
    "duration_ms": 15000,
    "expected_version": 2
  }
  ```
- 后端采用乐观锁版本号校验，防止多标签页冲突覆盖。

#### 5. 删除剪辑工程
- **`DELETE /api/v1/clip-projects/{id}`**
- 仅删除草稿本身；若该工程曾导出过云端成片，成片资产保留在资料库中，除非用户单独删除资产。

---

## 6. 前端 WebAV 与本地工作区联动规范

前端借助现代浏览器的 **File System Access API** 打造“零流量消耗”工作流：

### 6.1 本地工作区目录挂载
1. 用户在前端剪辑工作台点击“挂载本地资料目录”，浏览器调起：
   ```javascript
   const dirHandle = await window.showDirectoryPicker({ mode: "readwrite" });
   ```
2. 前端在本地 IndexedDB 记录该目录 handle，并维护本地素材索引：`{ sha256, filename, fileHandle }`。

### 6.2 素材消费三级加载决策链
当用户把资料库中的某个素材拖入剪辑轨道时：
```
           用户拖入素材 (携带 asset_id 与 sha256)
                           │
                           ▼
          检查本地挂载目录是否存在匹配的 sha256
                     ┌─────┴─────┐
                     │           │
                存在 │           │ 不存在
                     ▼           ▼
             直接读取本地文件   向后端请求 OBS 直链下载并
             (零网络/零流量)   写入用户本地目录，登记索引
                     │           │
                     └─────┬─────┘
                           ▼
               送入 WebAV 时间线解码播放
```
- **收益**：只有在用户第一次把云端素材拖入本地剪辑时消耗一次下载流量；之后所有的裁剪、反复回放、多次合成，全部走本地磁盘 I/O，**为平台节约上百倍的下行流量费**！

### 6.3 成片导出流程
```
 WebAV 完成本地编码并生成 Output Blob (MP4)
                     │
                     ▼
             弹出导出选项对话框
       [ √ ] 下载到本地电脑 (默认必定执行)
       [ ? ] 同时保存一份至云端资料库 (用户自选)
                     │
         ┌───────────┴───────────┐
  不保存 │                       │ 勾选保存
         ▼                       ▼
直接触发浏览器下载     检查云端配额 (GET /library/quota)
结束流程               走 upload-intent ➔ OBS 直传 ➔ complete
                       关联 clip_projects.exported_asset_id
```

---

## 7. 经济性与运维价值总结

1. **流量成本绝对受控**：
   - 剪辑过程 100% 运行在客户端与本地目录，拖拽重播零流量；
   - 导出成片由用户按需上云，杜绝未确认废片的云端带宽消耗。
2. **轻量健壮的配额控制**：
   - 默认 1GB 配额在满足国际传播比赛短视频制作（通常单片 20MB~50MB）的同时，确保单用户无法刷爆 OBS 存储；
   - 数据库只保留真实资产记录，用量由 Redis 聚合缓存负责，高并发下无锁竞争。
3. **极简服务架构**：
   - 后端免装 ffmpeg、OpenCV 等重型 C 依赖，保持轻量 Python/FastAPI 容器，大幅简化服务器运维部署。
