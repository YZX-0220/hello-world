# 全片 AI 统筹规划（AI 导演向导）后端设计与接口文档

本文档描述 **全片 AI 统筹规划（AI 导演向导 / Global AI Director）** 的后端架构设计、配置扩展、Prompt 编排机制、数据契约、RESTful API 接口规范以及与现有单点画布协作流程的衔接方式。

---

## 一、背景与定位

升级版「全片 AI 统筹规划（AI 导演向导）」将创作链路从“单点微调”升级为“全片顶层设计 → 秒级分镜拆解 → 画布多节点落盘”的闭环：
1. **Stage 1（总编剧 Agent）**：结合视频总时长与用户创意生成或迭代全片剧本大纲（【核心立意】+【故事脉络】），支持用户手改后结合修改指令定向润色。
2. **Stage 2（执行导演分镜 Agent）**：结合确认剧本、目标片段数、国家文化禁忌/负面词库（`cultural_guidances`）与提示词模板库（`prompt_templates`），结构化输出全局视觉风格、国际传播负面提示词、核心首帧图片素材提示词以及按 `0-5秒 / 5-10秒 / 10-15秒` 切分的片段脚本列表。
3. **零侵入衔接**：所有输出最终由前端在画布上落盘为标准 `FlowNode (type: 'text')` 并自动建立参考连线，直接复用现有的生图面板、`generationSources` 聚合以及 `prepare-video`（AI 审理方案）流程。

---

## 二、后端架构与核心模块

### 2.1 模块清单

| 文件路径 | 职责说明 |
| :--- | :--- |
| `backend/app/core/config.py` | 在 `Settings` 中提供导演 Agent 专属采样与超时配置（复用平台统一文本模型配置 `text_*`） |
| `backend/app/providers/text/base.py` | 扩展 `TextProvider.generate()` 支持可选 `temperature`、`max_tokens`、`timeout` 透传 |
| `backend/app/providers/text/openai_compatible.py` | 实现自定义采样参数透传，复用内置 Markdown 代码围栏剥离与一次 JSON 受控修复 |
| `backend/app/providers/text/fake.py` | 为 `TEXT_PROVIDER=fake` 开发/测试环境提供 Stage 1 大纲与 Stage 2 分镜结构化桩响应 |
| `backend/app/repositories/cultural_guidances.py` | 扩展 `list_by_codes()`，带 `ensure_defaults()` 与空列表防护（避免 SQLite 空 `IN ()` 异常） |
| `backend/app/repositories/prompt_templates.py` | 扩展 `get_accessible_template()`，支持按 `id` 或 `code` 查询且校验 `status='active'` 与归属权 |
| `backend/app/schemas/director.py` | 定义严格带 `ConfigDict(extra="forbid")` 的 Request / Response Pydantic 模型 |
| `backend/app/prompts/director.py` | 封装 Stage 1 / Stage 2 Prompt 构造、中文序号转换（1~99）与尾差时长分配算法 |
| `backend/app/services/director_agent_service.py` | `DirectorAgentService` 编排对话归属校验、数据库聚合、模型调用与结果兜底校准 |
| `backend/app/api/v1/director.py` | 暴露 `/conversations/{conversation_id}/director/outline` 与 `/breakdown` 接口 |
| `backend/app/api/v1/router.py` | 将 `director.router` 注册至 `/api/v1` |
| `backend/tests/test_director.py` | 鉴权、CSRF、对话越权隔离、Schema 校验、尾差时长/序号边界、JSON 围栏与错误格式测试 |

### 2.2 环境变量配置（`app/core/config.py`）

复用平台现有 `TEXT_PROVIDER`、`TEXT_BASE_URL`、`TEXT_API_KEY`、`TEXT_MODEL`，并新增以下可在 `.env` 中覆盖的调优参数：

| 配置字段 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `director_outline_temperature` | `DIRECTOR_OUTLINE_TEMPERATURE` | `0.75` | Stage 1 剧本大纲共创温度（兼顾叙事发散度） |
| `director_outline_max_tokens` | `DIRECTOR_OUTLINE_MAX_TOKENS` | `2500` | Stage 1 最大输出 Token 数 |
| `director_breakdown_temperature` | `DIRECTOR_BREAKDOWN_TEMPERATURE` | `0.3` | Stage 2 分镜拆解温度（保证结构化稳定性） |
| `director_breakdown_max_tokens` | `DIRECTOR_BREAKDOWN_MAX_TOKENS` | `4096` | Stage 2 最大输出 Token 数 |
| `director_timeout` | `DIRECTOR_TIMEOUT` | `120` | 导演 Agent 单次请求超时时间（秒） |

---

## 三、核心工程策略

### 3.1 单片段时长分配与模型约束对齐
现有视频任务校验（`VideoJobService._validate_mode`）要求单次生成视频时长为 `1–15` 秒，且主流模型常用 `5 / 10 / 15` 秒档位。`allocate_segment_durations(total_duration, segment_count)` 按以下规则分配各片段时长：
- 若总时长足够：前 `N - 1` 个片段固定为 `15` 秒，第 `N` 个片段承接剩余时长并向上对齐到 `5 / 10 / 15` 秒档位（例如 `40` 秒拆 `3` 个片段 → `[15, 15, 10]`）。
- 若总时长较短（例如 `20` 秒拆 `2` 段）：按 5 秒档位均分并封顶 `15` 秒。
- Prompt 中会显式下发每个片段对应的精确秒数及时间轴切片要求（`0-5秒`、`0-5秒 / 5-10秒` 或 `0-5秒 / 5-10秒 / 10-15秒`）。

### 3.2 容错与一致性校准（`DirectorAgentService._normalize_breakdown`）
1. **JSON 围栏剥离与受控修复**：由 `OpenAICompatibleTextProvider` 自动剥离 ` ```json ... ``` ` 围栏；若仍解析失败，会自动追加一次纯 JSON 修复重试。
2. **片段数量校验**：模型输出少于请求 `segment_count` 时抛出 `AGENT_OUTPUT_INVALID (502)`；若多于 `segment_count` 则截断至精确数量。
3. **节点命名与序号校准**：通过 `to_cn_index()` 强制覆写 `index` 与 `title`（严格输出 `片段一` ~ `片段二十`，支持 1~99），避免模型输出英文标题或阿拉伯数字。
4. **负面词保底注入**：确保从 `cultural_guidances` 与 `prompt_templates` 查出的负面提示词一定包含在 `cultural_node_content` 中；若模型漏写则自动追加 `【合并负面提示词 (Negative Prompt)】...`。
5. **模板占位符防碰撞**：`build_outline_messages()` 与 `build_breakdown_messages()` 均采用拼接构造而非 `str.format()`，防止用户输入或模板中的 `{subject}` 等花括号引发 `KeyError`。

---

## 四、RESTful API 接口契约

所有接口统一挂载在 `/api/v1` 前缀下，需携带登录会话 Cookie（`hw_session`）以及写接口 CSRF 校验头（`X-CSRF-Token` 与白名单 `Origin`），并在服务端校验 `conversation_id` 属于当前登录用户。

### 4.1 生成与迭代剧本大纲（Step 1）

- **接口**：`POST /api/v1/conversations/{conversation_id}/director/outline`
- **鉴权**：`get_current_user` + `require_csrf`
- **请求体（`DirectorOutlineRequest`，`extra="forbid"`）**：

| 字段 | 类型 | 必填 | 约束 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `total_duration` | `int` | 是 | `5 <= x <= 300` | 视频总时长（秒） |
| `user_idea` | `string` | 是 | 去首尾空白后 `2 ~ 2000` 字符 | 用户初始创意与想表达的核心思想 |
| `current_draft` | `string \| null` | 否 | 最大 `10000` 字符 | 当前剧本草稿（首次为空，迭代时传入用户手改稿） |
| `revision_instruction` | `string \| null` | 否 | 最大 `2000` 字符 | 用户追加的修改方向指令 |

- **请求示例**：
```json
{
  "total_duration": 45,
  "user_idea": "展现中国非遗竹编工艺如何走进现代欧洲家庭，传递环保与东方美学",
  "current_draft": null,
  "revision_instruction": null
}
```

- **响应体（`200 OK`，`DirectorOutlineResponse`）**：
```json
{
  "script_draft": "【核心立意】以光影为媒，展现东方竹艺的温度...\n【故事脉络】\n1. ...",
  "recommended_segments": 3
}
```
> 注：`recommended_segments = max(1, math.ceil(total_duration / 15))`。

---

### 4.2 分镜精细化拆解与提示词生成（Step 2 → Step 3）

- **接口**：`POST /api/v1/conversations/{conversation_id}/director/breakdown`
- **鉴权**：`get_current_user` + `require_csrf`
- **请求体（`DirectorBreakdownRequest`，`extra="forbid"`）**：

| 字段 | 类型 | 必填 | 约束 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `total_duration` | `int` | 是 | `5 <= x <= 300` | 视频总时长（秒） |
| `segment_count` | `int` | 是 | `1 <= x <= 20` | 拆解片段数量 |
| `script_draft` | `string` | 是 | 去首尾空白后 `10 ~ 15000` 字符 | Step 1 确认后的剧本全文 |
| `country_codes` | `list[string]` | 否 | 最多 `20` 项，默认 `[]` | 目标传播国家代码列表（如 `["FR", "DE"]`） |
| `style_template_id` | `string \| null` | 否 | 最大 `64` 字符 | `prompt_templates` 中的模板 `id` 或 `code` |
| `custom_style_desc` | `string \| null` | 否 | 最大 `2000` 字符 | 用户补充的自定义视觉风格描述 |

- **请求示例**：
```json
{
  "total_duration": 40,
  "segment_count": 3,
  "script_draft": "【核心立意】以光影为媒，展现东方竹艺的温度...\n【故事脉络】...",
  "country_codes": ["FR", "DE"],
  "style_template_id": "cinematic_warm_01",
  "custom_style_desc": "4K纪录片质感，丁达尔光效，胶片颗粒感"
}
```

- **响应体（`200 OK`，`DirectorBreakdownResponse`）**：
```json
{
  "style_node_content": "【整体视觉风格】4K纪录片电影质感，暖调自然光，浅景深...",
  "cultural_node_content": "【目标地区】法国、德国\n【传播叙事建议】...\n【合并负面提示词 (Negative Prompt)】工业化流水线塑料感、虚假浮夸...",
  "image_asset_prompts": "【核心图片素材 1（匠人首帧图）】...",
  "segments": [
    {
      "index": 1,
      "title": "片段一",
      "duration": 15,
      "timeline_prompt": "0-5秒：全景镜头缓慢推进...\n5-10秒：切近景...\n10-15秒：特写镜头..."
    },
    {
      "index": 2,
      "title": "片段二",
      "duration": 15,
      "timeline_prompt": "0-5秒：...\n5-10秒：...\n10-15秒：..."
    },
    {
      "index": 3,
      "title": "片段三",
      "duration": 10,
      "timeline_prompt": "0-5秒：...\n5-10秒：..."
    }
  ]
}
```

---

### 4.3 统一错误码说明

沿用平台统一错误响应信封 `{ "error": { "code", "message", "request_id", "details" } }`：

| 错误码 | HTTP 状态码 | 触发场景 |
| :--- | :--- | :--- |
| `AUTH_REQUIRED` | `401` | 未登录或会话已失效 |
| `CSRF_INVALID` | `403` | 缺少或无效的 `X-CSRF-Token` / 非白名单 `Origin` |
| `CONVERSATION_NOT_FOUND` | `404` | `conversation_id` 不存在或不属于当前登录用户 |
| `VALIDATION_ERROR` | `422` | 请求体包含未定义字段（`extra="forbid"`）或参数越界 |
| `AGENT_OUTPUT_INVALID` | `502` | 模型未返回合法 JSON 或分镜片段数量不足 |
| `TEXT_PROVIDER_UNAVAILABLE` | `502` | 文本模型服务不可用或限流 |
| `TEXT_PROVIDER_TIMEOUT` | `504` | 文本模型响应超时 |

---

## 五、测试与验证记录

- **测试文件**：`backend/tests/test_director.py`
- **覆盖场景**：
  1. 未登录（`401`）、缺少 CSRF（`403`）、对话不存在与跨用户访问隔离（`404`）。
  2. `ConfigDict(extra="forbid")` 多余字段拦截与参数边界校验（`422`）。
  3. Step 1 剧本生成、`recommended_segments` 计算、手改稿 + 修改指令二次迭代。
  4. Step 2 → Step 3 联动 `cultural_guidances` 与 `prompt_templates`，验证多国家负面词保底注入、空 `country_codes=[]` 防护、12 片段中文序号（`片段十一`、`片段十二`）以及尾差时长分配（`40s -> [15, 15, 10]`）。
  5. `OpenAICompatibleTextProvider` 的 Markdown 代码围栏解析、`temperature`/`max_tokens` 透传、片段超长截断及片段不足时的 `AGENT_OUTPUT_INVALID` 错误信封。
