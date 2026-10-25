# 华为云 OBS 对象存储设计方案

## 1. 背景与目标

### 1.1 背景瓶颈
当前生产环境部署服务器仅有 **3Mbps 公网带宽**（理论传输峰值约为 350~375 KB/s）。
原存储方案依赖后端本地磁盘（`data/uploads/`、`data/videos/`）：
- 媒体文件（图片、音频、生成视频）的上传与读取均经过 FastAPI 业务中转。
- 单个 20MB 视频下载或播放需要占用 ~1 分钟全部带宽，极易引发业务 API 响应超时与服务不可用。

### 1.2 核心目标
1. **数据零中转 (Zero-Relay)**：所有大体积二进制流（用户素材、剪辑导出成片、AI 生成视频、公共素材库视频）100% 绕过业务服务器，直通华为云 OBS。
2. **业务解耦**：业务服务器仅负责权限鉴权、预签名生成、元数据登记及状态机管理。
3. **秒传与去重**：利用 OBS 对象的 ETag（MD5 指纹）与数据库资产指纹联动，避免重复上传与存储冗余。
4. **外部抓取 (Way-A)**：AI 厂商成片回流直接通过 OBS 异步外部拉取接口（`setBucketFetchJob`）入桶，完全不耗费本地下载带宽。
5. **边缘图像处理 (Image Process)**：利用 OBS 原生图像处理能力提供实时动态缩略图与 WebP 转码，大幅加速前端瀑布流与画布预览。

---

## 2. 总体架构设计

```
                         ┌───────────────────────┐
                         │   前端浏览器 / WebAV   │
                         └───────┬───────┬───────┘
                                 │       │
                 ① 获取直传凭证   │       │ ③ 预签名只读直读 / 播放
                 (仅几 KB JSON)   │       │   (分段 HTTP 206)
                                 ▼       ▼
┌─────────────────────────────────┐     ┌──────────────────────────────────┐
│      FastAPI 业务控制面          │     │        华为云 OBS 存储桶          │
│   (鉴权 / 方案审理 / 状态机)      │     │       (hello-world-yzx)          │
└────────────────┬────────────────┘     └─────────────────▲────────────────┘
                 │                                        │
                 │ ② 确认直传完成 (核验 ETag)               │ ④ 浏览器直传二进制 (PUT)
                 └────────────────────────────────────────┘   (带 Content-Type 校验)
                                                          ▲
                                                          │ ⑤ 厂商视频异步转存入桶
                                                ┌─────────┴────────┐
                                                │ 火山方舟/阿里百炼等 │
                                                │ AI 视频生成服务商 │
                                                └──────────────────┘
```

---

## 3. 详细设计规范

### 3.1 存储桶规划与路径目录约定
- **存储桶**：`hello-world-yzx`
- **地域/Endpoint**：`obs.cn-east-5.myhuaweicloud.com`
- **对象命名规范 (Object Key)**：
  - 用户原始上传素材：`assets/{user_id}/{kind}s/{asset_id}.{ext}`
  - 前端剪辑合成导出成片：`exports/{user_id}/{asset_id}.mp4`
  - AI 视频生成归档：`outputs/{user_id}/{job_id}.mp4`
  - 平台公共素材库：`public-materials/{category}/{material_id}.{ext}`

### 3.2 预签名直传机制 (Two-Phase Commit)
为了避免恶意调用与未完成脏数据，采用两阶段凭据提交：
1. **申请直传 (`POST /api/v1/assets/upload-intent`)**：
   - 前端计算或声明 `byte_size`、`content_type`、可选 `file_hash`（MD5/SHA256）。
   - 后端核验文件大小与配额限制。
   - 若命中已存在相同 Hash 且状态为 `ready` 的资产，触发**秒传**（直接返回既有 `asset_id`，`is_duplicate=true`，前端免传）。
   - 未命中则生成全局 `asset_id`，通过 OBS SDK 签署包含该 `Content-Type` 的临时 PUT 上传地址（有效期 15~30 分钟），落库状态为 `pending_upload`。
2. **前端直推 OBS (`PUT {upload_url}`)**：
   - 前端发送 PUT 请求，Header 中必须携带与签署严格一致的 `Content-Type`。
   - 上传过程直接走华为云骨干网，零消耗服务器带宽。
3. **完成确认 (`POST /api/v1/assets/{asset_id}/complete`)**：
   - 前端直传成功后通知后端。
   - 后端通过 OBS API `getObjectMetadata` 检查文件真实存在性，获取 OBS 返回的 `ETag` 和实际字节数。
   - 资产状态更新为 `ready`，正式对外可用。

### 3.3 媒体资源直读与播放
- 废弃服务端流式代理输出大文件的做法。
- 前端请求素材或视频时，后端返回有时效的 **OBS 预签名 GET URL**（或由 `GET /api/v1/assets/{id}` 返回 `302 Found` 重定向至 OBS 签名直链）。
- 华为云 OBS 已经配置完整的 CORS 规则：
  - 允许源：`https://hello-world.zerohyh.com`, `http://47.99.35.159`, `http://localhost:5173` 等。
  - 暴露响应头：`ETag`, `Content-Length`, `Content-Range`, `Accept-Ranges`。
  - 支持浏览器 `<video>` 及前端剪辑器 `WebAV` 发起 `Range: bytes=x-y` 分段拉取。

### 3.4 厂商视频回流零带宽转存 (Way-A)
当视频任务（`VideoJob`）在外部厂商（如火山方舟）执行成功后：
- 厂商提供临时成果下载 URL（例如 `https://ark-tos.volces.com/.../output.mp4`）。
- **优化前**：服务器 HTTP 下载 30MB 视频，再写入本地或上传，严重堵塞 3M 进出口带宽。
- **优化后**：
  1. 后端调用 OBS `setBucketFetchJob` 接口，下发外部拉取任务：
     ```python
     obs_client.setBucketFetchJob(
         bucketName=bucket,
         job={"url": provider_task_result_url, "object": f"outputs/{user_id}/{job_id}.mp4"}
     )
     ```
  2. 华为云数据中心节点直接通过多线公网拉取厂商视频，直接落入 `hello-world-yzx` 桶中。
  3. 后端将 `VideoJob.download_status` 标记为完成，并记录资产 `Asset` 指向该 OBS Object Key。

### 3.5 平台素材库（TV / Material Library）与直读重定向
- 平台素材库在用户访问演示视频（`/tv`）与封面时，通过 `GET /api/v1/material-library/{id}/{role}` 读取。
- 若资产位于 OBS（`storage_provider == "obs"`），后端响应 `302 Found` 重定向至 OBS 预签名直链，天然支持 HTTPS 并释放全部服务器下行流量。

---

## 4. 文件 Hash 与去重校验设计

### 4.1 ETag 特性与指纹对照
- **单文件 PUT 直传（<5GB）**：华为云 OBS 返回的 `ETag` 格式为去除连字符的标准 MD5 摘要（带双引号，如 `"7f45f1e9a7e9ac4c71b8483cd773f344"`）。
- **指纹比对**：
  - 数据库 `assets` 表保留 `sha256` / `md5` 索引字段。
  - 前端可在选择文件后快速切片或流式计算 MD5（使用 `spark-md5` 或 WebCrypto API）。
  - 在 `upload-intent` 阶段先进行指纹命中检查；在 `complete` 阶段比对 OBS 返回的 ETag 是否与预期一致。

### 4.2 空间与成本优化
- 用户重复上传同一背景音乐或常用 LOGO 图标时，后端直接复用已有 OBS 对象，节约对象存储存储费与上传请求费。

---

## 5. 华为云 OBS 图像处理（图片缩略图）深度评估与应用方案

华为云 OBS 原生支持通过在访问 URL 后追加 `x-image-process` 查询参数实现边缘图片实时缩放、裁剪、格式转换（WebP）和旋转。

### 5.1 对本项目的核心价值
1. **彻底解决前端移动端/看板加载卡顿**：
   - 用户上传的原图通常为手机直拍（5MB~20MB，4000x3000）。
   - 在前端 TV 瀑布流、素材选择器弹窗、画布节点预览中，若直接拉取原图，一次性加载 10 张图会下载 ~100MB 流量。
   - 启用缩略图参数后（如 `?x-image-process=image/resize,m_lfit,w_300/format,webp`），单张图体积直降到 **30KB~80KB**，体积缩减 **98%**，首屏秒开。
2. **零服务器算力开销**：
   - 缩略图生成完全由华为云 OBS 服务端边缘计算节点即时完成，业务服务器无需消耗 CPU/内存运行 Pillow/OpenCV 切图。
3. **免二次存储成本**：
   - 动态处理不需要在存储桶中另存一份 `thumb_xxx.jpg` 文件，极大精简桶内对象数量并节省容量计费。

### 5.2 推荐接入方式
- 后端生成直链或 302 重定向时，针对 `kind == "image"` 且携带 `thumbnail=true`（或 `w=xxx,h=xxx`）的请求，自动拼接华为云样式后缀：
  `https://{bucket}.{endpoint}/{key}?x-image-process=image/resize,m_lfit,w_320,h_240/quality,q_80/format,webp`
- 前端封面组件展示缩略图，用户点击放大/双击预览才加载原图。
