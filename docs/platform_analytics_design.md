# 平台数据统计与分析指标体系设计方案 (Platform Analytics & Metrics Design)

## 1. 概述与设计背景

随着平台生视频（Video Generation）、AI 生图/修图（Image Generation）、画布协作以及媒体素材库能力的完善，系统需要一套清晰的数据统计体系，用以支撑：
1. **对外品牌展示**：在官网/落地页（Landing Page）展示平台服务规模与创作战绩（如“已累计生成 X 段视频”、“赋能 X 位创作者”），建立用户信任。
2. **内部运营与业务洞察**：分析创作者行为、模型偏好、生成模式分布，指导功能迭代。
3. **成本与运维监控**：监控 OBS/本地存储容量水位、大模型 Token 消耗、厂商生成成功率与耗时。

系统现有的数据库架构已具备完善的状态生命周期（如 `video_jobs`、`image_jobs`、`assets`、`site_visits` 等），本设计方案梳理了可统计的指标维度、底层数据映射、查询实现方案及工程性能优化策略。

---

## 2. 核心统计维度与指标矩阵

### 2.1 创作生产力指标 (Core Generation Metrics)

| 指标项 | 统计口径说明 | 对应数据表及字段 | 业务价值 |
| :--- | :--- | :--- | :--- |
| **视频生成成功总数** | 状态为 `succeeded` 的视频任务总数 | `video_jobs` (`status = 'succeeded'`) | 平台核心成效指标（对外展示） |
| **视频任务提交总数** | 包含所有状态的视频任务总数 | `video_jobs` (所有行) | 评估总创作需求量 |
| **视频生成成功率** | 成功任务数 / 总提交任务数 | `video_jobs.status` | 衡量平台与第三方 API 的整体稳定性 |
| **累计生成视频总时长** | 成功生成视频的播放时长求和 | `video_jobs` 关联 `assets.duration_ms` 求和 | 具象化呈现平台创作成果（如“生成 X 万秒内容”） |
| **图片生成/修改总数** | 状态为 `succeeded` 的图片任务数 | `image_jobs` (`status = 'succeeded'`) | 衡量视觉改图/生图工具使用量 |
| **模型使用分布与排行** | 按厂商/模型聚合的任务数 | `video_jobs.remote_model_id` / `image_jobs.model` 分组 | 洞察用户模型偏好（如 Seedance、Kling 等） |
| **生成模式偏好分布** | 纯文本 / 首帧 / 首尾帧 / 参考图 生成分布 | `video_jobs.mode` 分组 | 了解创作者的使用习惯和素材组织方式 |

### 2.2 用户与活跃度指标 (User & Growth Metrics)

| 指标项 | 统计口径说明 | 对应数据表及字段 | 业务价值 |
| :--- | :--- | :--- | :--- |
| **平台注册用户总数** | 注册账号累计总量 | `users` (`status != 'deleted'`) | 衡量用户基础盘规模 |
| **新增用户趋势** | 按日 / 周 / 月统计新注册用户量 | `users.created_at` 按时间段聚合 | 用户增长拉新趋势 |
| **活跃创作用户 (DAU / MAU)** | 指定时间段内有过生视频/生图行为的去重用户数 | `video_jobs.user_id` 与 `image_jobs.user_id` 的 `DISTINCT` 并集 | 识别真实核心创作者体量 |
| **人均创作产能** | 成功生成总数 / 活跃用户数 | 任务总数 / 去重 `user_id` 数 | 评估用户粘性与创作深度 |
| **全站独立访客与访问量** | PV (Page Views) 与 UV (Unique Visitors) | `site_visits` 与 `site_traffic_totals` | 营销推广与引流转化率分析 |

### 2.3 存储与成本监控指标 (Storage & Cost Metrics)

| 指标项 | 统计口径说明 | 对应数据表及字段 | 业务价值 |
| :--- | :--- | :--- | :--- |
| **媒体总存储量** | 全平台所有就绪素材文件大小累计 | `assets.size_bytes` (`status = 'ready'`) 求和 | 评估华为云 OBS 及磁盘存储成本与容量水位 |
| **存储介质分布** | 按 OBS 与 Local 分布的存储量与文件数 | `assets.storage_provider` 分组聚合 `size_bytes` | 混合存储演进与数据迁移监控 |
| **素材类型占比** | 视频、图片、音频各类型文件数量与容量 | `assets.kind` 分组聚合 | 了解平台媒体资产构成 |
| **对话 Token 消耗量** | 智能体协作、提示词编译消耗的 Token 总量 | `messages.input_tokens` / `output_tokens` 求和 | 大模型 LLM 采购成本监控 |

### 2.4 性能与服务质量指标 (QoS & Reliability Metrics)

| 指标项 | 统计口径说明 | 对应数据表及字段 | 业务价值 |
| :--- | :--- | :--- | :--- |
| **平均视频生成耗时** | 任务完成时间与提交时间的差值均值 | `AVG(completed_at - submitted_at)` | 掌握用户等待时长体验，优化轮询调度策略 |
| **失败原因 TOP 归因** | 失败任务的错误码与错误信息聚类分析 | `video_jobs.error_code` 分组统计 | 快速定位高频问题（如人像风控拦截、超时、通道欠费） |
| **素材下载拉回耗时/成功率** | 厂商结果落盘至本站/OBS 的转存状态 | `video_jobs.download_status` | 评估异步下载拉回与转存专线的可靠性 |

---

## 3. SQL 统计查询参考实现 (SQLite / PostgreSQL 通用)

### 3.1 核心概览大盘 (Overview)
```sql
-- 1. 视频生成成功总数及总体成功率
SELECT 
    COUNT(*) AS total_jobs,
    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS succeeded_jobs,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_jobs,
    ROUND(100.0 * SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) / COUNT(*), 2) AS success_rate_pct
FROM video_jobs;

-- 2. 累计生成视频总时长（秒）
SELECT 
    ROUND(COALESCE(SUM(a.duration_ms), 0) / 1000.0, 1) AS total_duration_seconds
FROM video_jobs vj
JOIN assets a ON vj.local_asset_id = a.id
WHERE vj.status = 'succeeded';

-- 3. 累计生成图片数
SELECT COUNT(*) AS total_images_generated
FROM image_jobs
WHERE status = 'succeeded';
```

### 3.2 模型分布与生成模式偏好
```sql
-- 各模型使用量统计
SELECT 
    remote_model_id,
    COUNT(*) AS job_count,
    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS success_count
FROM video_jobs
GROUP BY remote_model_id
ORDER BY job_count DESC;

-- 生成模式（图生视频/文生视频/参考图等）分布
SELECT 
    mode,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM video_jobs), 2) AS percentage
FROM video_jobs
GROUP BY mode;
```

### 3.3 存储资产用量统计
```sql
-- 素材存储总容量与文件数量（按存储源分组）
SELECT 
    storage_provider,
    kind,
    COUNT(*) AS file_count,
    ROUND(SUM(size_bytes) / (1024.0 * 1024.0 * 1024.0), 3) AS total_gb
FROM assets
WHERE status = 'ready' AND deleted_at IS NULL
GROUP BY storage_provider, kind;
```

---

## 4. 架构设计与性能优化策略

### 4.1 读写分离与展示分级

根据使用场景的吞吐和权限要求，建议划分为两套数据接口：

1. **公开大盘接口 (`GET /api/v1/metrics/public-overview`)**：
   - **面向场景**：官网首页、落地页（Landing Page）对外战绩展示。
   - **指标包含**：累计生成视频数、累计创作时长、注册创作者数、全站访问量。
   - **安全策略**：无需登录认证，数值可适度做安全截断或展示粗粒度（如 `10,000+`）。
   - **缓存机制**：强依赖 Redis 缓存 5~15 分钟，或结合类似 `site_traffic_totals` 的单行递增聚合表，严禁直接全表扫库。

2. **管理端看板接口 (`GET /api/v1/admin/analytics`)**：
   - **面向场景**：管理员后台（TVAdmin 等）图表与多维筛选。
   - **指标包含**：成功率趋势折线图、错误归因 Top 榜、各模型成本消耗、存储水位增长趋势。
   - **权限策略**：需校验管理员鉴权与 CSRF。

### 4.2 性能支撑演进路线

1. **阶段一（当前轻量级阶段）**：
   - 依赖现有数据表索引：`video_jobs.status`、`video_jobs.created_at`、`assets.storage_provider` 已具备索引。
   - 接口层面引入简单的 Redis 缓存键（如 `metrics:overview`，TTL 10 分钟）。
2. **阶段二（高频次与业务增长阶段）**：
   - **原子递增计数表**：参考 `site_traffic_totals`，新建 `platform_metrics_totals` 表。
   - 在任务变更事件中（如 `VideoJob` 变为 `succeeded` 时），触发一次 `total_videos_generated += 1` 的原子更新，读取时时间复杂度达到 $O(1)$。
3. **阶段三（复杂 BI 分析阶段）**：
   - 每日凌晨调度异步定时任务（Cron Worker），跑批量聚合脚本，将每日指标沉淀为 `daily_metric_snapshots` 日快照表，支持快速拉取历史 30 天/一年的趋势图。

---

## 5. 首页公开大盘接口实现落地说明

首页的站点流量与平台统计接口 `GET /api/v1/site-traffic/summary` 现已完成增强，向全站匿名及公开展示开放以下指标字段，供官网落地页及工作台动态读取：

### 5.1 响应字段定义 (`SiteTrafficSummary`)

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `total_visits` | `int` | 平台累计访问量（基于 `site_traffic_totals` 表的严格去重计数） |
| `total_tokens` | `int` | 平台累计消耗 Token 总量（智能体协作、提示词编译及模型推理消耗） |
| `total_creations` | `int` | 平台总创作次数（视频生成任务数 + 图片生成任务数） |
| `creations_breakdown` | `object` | 创作细分明细：`{ "videos": int, "images": int }` |
| `total_users` | `int` | 平台总用户量（活跃/正常状态创作者账号数） |
| `published_works` | `int` | 平台已上架发布的作品总量（TV / 公共展示素材库） |
| `total_assets` | `int` | 平台已就绪的媒体资产总量（`status = 'ready'`） |
| `models_and_templates_count` | `int` | 系统支持接入并开放的能力模型与协议模板总数 |
| `daily_tokens_14d` | `array` | 近 14 天每日 Token 消耗趋势序列：`[{ "date": "YYYY-MM-DD", "tokens": int }]`（连续 14 天日期完整，无消耗自动补 0） |
| `started_at` | `string \| null` | 统计开始记录的时间戳 |
| `session_timeout_minutes` | `int` | 访问合并防抖会话超时时长（默认 30 分钟） |

### 5.2 字段兼容性与无痛迁移
- 基础字段 `total_visits`、`started_at`、`session_timeout_minutes` 与原结构完全兼容，现有前端逻辑读取不受影响。
- 新增指标均具备默认值（0 或空数组），在数据库冷启动或空数据时均保证平稳响应。

