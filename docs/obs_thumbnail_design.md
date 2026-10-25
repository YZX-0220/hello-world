# 华为云 OBS 图片动态缩略图与处理方案设计

## 1. 背景与业务痛点

### 1.1 现状分析
1. **外网流量计费压力**：
   - 当前华为云 OBS 购买的是 **40GB 标准存储包（不含公网下行流量包）**。
   - 用户在浏览器端浏览图片、播放视频产生的外网流出流量需按量扣费（白天约 **0.50 元/GB**）。
   - 用户上传的高清参考图、海报封面动辄 **3MB ~ 15MB**（分辨率 3000x2000 以上）。
2. **前端渲染卡顿与首屏排队**：
   - 在 TV 演示展厅（`/tv`）、素材选择器弹窗、画布节点预览、对话素材卡片中，展示区域仅为 **100px ~ 300px** 的小框。
   - 若直接拉取原图，一次性加载 10 张大图将消耗 **50MB ~ 100MB** 流量，在移动端或弱网下出现明显的从上至下“切片式”白屏与排队卡顿。
3. **零服务器 CPU 开销诉求**：
   - 生产环境服务器仅有低配核心与 3Mbps 带宽，无法在后端通过 Python (Pillow / OpenCV) 执行并发切图与 WebP 转码，必须将图片处理算力外包给云厂商边缘节点。

---

## 2. 核心架构与处理策略

华为云 OBS 原生提供 **On-the-fly（即时动态）图像处理** 能力。原图原样保存在桶内，无需在存储桶生成任何 `thumb_xxx` 冗余小文件；仅在读取时向 OBS 传递 `x-image-process` 查询参数，由华为云边缘节点实时处理并以超高压缩比的 WebP 返回。

```
┌─────────────────────────────────┐
│       前端 Vue / WebApp         │
└────────────────┬────────────────┘
                 │
                 │ ① GET /assets/{id}/content?thumbnail=small
                 ▼
┌─────────────────────────────────┐
│        FastAPI 控制面           │
│ 1. 鉴权 (User/Conversation/公开) │
│ 2. 校验 asset.kind == "image"   │
│ 3. 签署带样式后缀的 OBS 预签名直链│
└────────────────┬────────────────┘
                 │
                 │ ② 302 Found (Location: https://obs.../key?x-image-process=...)
                 ▼
┌─────────────────────────────────┐
│     华为云 OBS 边缘计算节点      │
│ 1. 从桶内载入原图               │
│ 2. 边缘内存即时缩放 (等比限宽)    │
│ 3. 实时转码为 WebP (质量 80%)    │
│ 4. 输出约 25KB 二进制数据流     │
└────────────────┬────────────────┘
                 │
                 │ ③ 快速下发轻量 WebP 媒体流 (零占用业务服务器带宽)
                 ▼
┌─────────────────────────────────┐
│       前端浏览器快速渲染        │
└─────────────────────────────────┘
```

---

## 3. 规格矩阵与处理指令规范

结合项目前端画布、TV、列表的实际像素尺寸，统一定义 3 档图像消费模式：

| 规格档位 | 适用场景 | 目标尺寸约束 | OBS 图像处理指令 (`x-image-process`) | 预估单图体积 | 流量与速度增益 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`small` (默认卡片)** | TV 瀑布流、素材库网格、会话对话小卡片、头像 | 等比缩放，最大宽 320px，高自适应 | `image/resize,m_lfit,w_320,limit_1/format,webp/quality,q_80` | **15 KB ~ 35 KB** | 相比 5MB 原图节约 **99.3%** 流量 |
| **`medium` (节点预览)** | 画布节点卡片展开、编辑弹窗快速预览、平板预览 | 等比缩放，最大宽 800px，高自适应 | `image/resize,m_lfit,w_800,limit_1/format,webp/quality,q_85` | **60 KB ~ 120 KB** | 相比 5MB 原图节约 **98.0%** 流量 |
| **`raw` (原始图)** | 画布全屏放大检查、用户手动点击下载、提交厂商 AI 生成 | 原始像素 | *(不带任何处理参数)* | 原始大小 (3MB~15MB) | 保证 AI 生成与大图展示 100% 原始画质 |

### 关键指令说明：
- `m_lfit`：等比缩放，限制在矩形框内，保持原图纵横比，不拉伸变形。
- `limit_1`：若原图尺寸小于目标尺寸，则不放大原图，避免产生多余噪点。
- `format,webp`：将原本体积庞大的 PNG/JPEG 转换为现代 WebP 格式（体积减少 30%~70%）。
- `quality,q_80`：视觉无损质量标准，平衡清晰度与压缩率。

---

## 4. 后端接口与驱动改造方案

### 4.1 数据模型支撑
后端现有 `Asset` 模型已完整沉淀关键字段，可实现零成本安全识别：
- `asset.kind == "image"`：瞬时精准识别媒体类型，若为 `video` 或 `audio` 则自动忽略缩略图参数，杜绝非法请求。
- `asset.mime_type`：安全校验格式，确保仅对合法位图执行处理。
- `asset.storage_provider == "obs"`：精准分流。若处于本地开发环境（`local`），自动安全降级（直接返回原图），不报错。

### 4.2 驱动层升级 (`app/storage/obs.py`)
扩展 `generate_presigned_download_url` 方法，支持拼接安全的预处理参数：

```python
# 规格别名映射表
THUMBNAIL_PRESETS: dict[str, str] = {
    "small": "image/resize,m_lfit,w_320,limit_1/format,webp/quality,q_80",
    "medium": "image/resize,m_lfit,w_800,limit_1/format,webp/quality,q_85",
}

def generate_presigned_download_url(
    self,
    key: str,
    *,
    expires_in_seconds: int = 3600,
    filename: str | None = None,
    image_process: str | None = None,
) -> str:
    # 1. 华为云 SDK 计算基础预签名 URL
    signed = self._client.createSignedUrl(
        method="GET",
        bucketName=self._bucket,
        objectKey=key.lstrip("/"),
        expires=expires_in_seconds,
    )
    url = str(signed.signedUrl)

    # 2. 若携带图片处理规则，追加 x-image-process
    if image_process:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}x-image-process={image_process}"

    return url
```

### 4.3 接口层改造 (`app/api/v1/assets.py` & `material_library.py`)

#### 1. 用户素材读取接口：`GET /api/v1/assets/{asset_id}/content`
- **新增 Query 参数**：
  `thumbnail: Literal["small", "medium", "raw"] = Query(default="raw")`
- **处理逻辑**：
  - 校验权限后，读取 `asset` 元数据；
  - 若 `asset.kind == "image"` 且 `thumbnail in ("small", "medium")`：
    选取对应规格，签署带处理参数的预签名直链；
  - 返回 `302 Found`（同时带上响应头 `Cache-Control: private, max-age=600`，使客户端 10 分钟内免二次请求）。

#### 2. 平台素材库封面接口：`GET /api/v1/material-library/{item_id}/cover`
- **新增 Query 参数**：
  `thumbnail: Literal["small", "medium", "raw"] = Query(default="small")`
- **处理逻辑**：
  - 默认采用 `small` 缩略图模式，确保 TV 展厅首屏加载封面时全走轻量 WebP；
  - 仅在点击进入详情或查看封面大图时传入 `thumbnail=raw`。

---

## 5. 前端消费规范

前端工程在消费图片时，制定以下统一调用规则：

### 5.1 TV 展厅 / 瀑布流封面 (`Tv.vue` / `MaterialCard.vue`)
```html
<!-- 列表展示：使用 small 规格 -->
<img 
  :src="`/api/v1/material-library/${item.id}/cover?thumbnail=small`" 
  loading="lazy" 
  alt="封面缩略图" 
/>
```

### 5.2 画布工作台 (`CanvasNode.vue`)
```html
<!-- 画布节点卡片缩略图：使用 medium 规格 -->
<img 
  :src="`/api/v1/assets/${node.data.assetId}/content?thumbnail=medium`" 
  alt="参考图预览" 
/>
```

### 5.3 弹窗大图预览 (`ImageModal.vue`)
```html
<!-- 点击放大预览大图：不带参数或传 raw，加载 100% 原始画质 -->
<img 
  :src="`/api/v1/assets/${assetId}/content?thumbnail=raw`" 
  alt="高清原图" 
/>
```

---

## 6. 经济性与安全性评估

### 6.1 成本精算（对比实测）
以平台每月产生 **10,000 次** 图片展示为例：

| 方案 | 处理算力费 | 外网流量消耗 (按 0.50元/GB) | 综合月支出 |
| :--- | :--- | :--- | :--- |
| **未启用缩略图 (直接加载 5MB 原图)** | 0 元 | 50 GB ➔ **25.00 元** | **25.00 元** |
| **启用 OBS 缩略图 (生成 25KB WebP)** | ~0.025 元 (万次算力) | 0.25 GB ➔ **0.13 元** | **0.16 元** |
| **净收益** | — | **节省 99.5% 流量带宽** | **净省 99.4% 费用** |

### 6.2 安全性与边界处理
1. **防恶意参数注入**：
   - 接口只允许客户端传入枚举值（`small`, `medium`, `raw`），绝对不开放任意透传自定义样式字符串，杜绝恶意消耗算力。
2. **非图片格式自动过滤**：
   - 当请求非图片资产（如视频 `kind == "video"`）时，即使带了 `thumbnail=small`，后端强校验后直接忽略，走标准直读，避免向 OBS 发送非法指令。
3. **本地开发环境平滑降级**：
   - 本地开发若未配置华为云 OBS，自动退回 `LocalStorage`，直接返回本地原图文件，单测与本地开发零阻碍。
