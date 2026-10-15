# Hello World Backend

Hello World AI 视频平台后端（比赛演示版 / MVP）。定位是**有状态的 AI 编排与权限控制系统**，不是模型运行服务。它负责保存用户、对话、结构化视频方案（VideoBrief）、素材与视频任务，为文本模型重建上下文、校验结构化输出、提供受控联网搜索、管理用户自己的视频 API 凭据（加密存储），并在用户确认后把方案交给外部视频厂商生成、统一不同厂商能力与状态、把成片下载到本站受控提供。

## 技术栈

- Python 3.12+，FastAPI
- SQLModel（数据层，表使用 `class X(SQLModel, table=True)` + `Field(...)`）
- SQLite + Alembic 迁移 + aiosqlite（业务运行使用异步 AsyncSession；Alembic 迁移使用同步引擎，两者读同一套模型）
- Redis（验证码、限流、短缓存、轮询锁）
- HTTPX（外部文本 / 搜索 / 视频厂商调用）
- pydantic-settings（配置）、ruff（静态检查）、mypy（类型检查）、pytest（测试）
- uv（依赖管理与虚拟环境）

时间约定：所有时间字段一律采用**服务器本地时间**（naive），不做 UTC 转换。

## 目录结构

```
backend/
├─ app/
│  ├─ main.py            # 应用入口、/healthz、/readyz
│  ├─ api/               # 路由、中间件、依赖
│  │  └─ v1/             # /api/v1 业务路由（后继批次加入）
│  ├─ core/              # 配置、常量、枚举、错误、时间、ID、安全、日志
│  ├─ db/
│  │  ├─ session.py      # 异步引擎 + AsyncSession + SQLite PRAGMA
│  │  └─ models/         # 17 张表（SQLModel）
│  ├─ schemas/           # Pydantic 输入/输出
│  ├─ repositories/      # 查询持久化
│  ├─ services/          # 用例编排
│  ├─ providers/         # 外部厂商（text/search/email/video）
│  ├─ storage/           # 文件存储
│  └─ workers/           # 轮询/下载/清理任务
├─ alembic/              # 迁移脚本
├─ tests/                # 单元/集成/契约/E2E/假实现
├─ data/                 # 上传、视频、临时文件（gitignore 排除实体）
├─ scripts/              # 运维脚本（备份、密钥轮换等）
└─ alembic.ini, pyproject.toml, .env.example
```

## 快速开始

前置：安装 [uv](https://docs.astral.sh/uv/)，准备 Redis（可选，未启动时服务仍能运行，`/readyz` 会返回 `degraded`）。

```bash
# 1. 安装依赖（自动创建 .venv 并生成 uv.lock）
uv sync

# 2. 配置环境（可选，未配置时使用默认值）
cp .env.example .env

# 3. 建库（单条迁移命令即可创建全部表）
uv run alembic upgrade head

# 4. 启动开发服务器
uv run python -m uvicorn app.main:app --reload
```

访问：
- 存活检查 `http://127.0.0.1:8000/healthz`
- 就绪检查 `http://127.0.0.1:8000/readyz`
- 接口文档 `http://127.0.0.1:8000/docs`

## 运行检查与测试

```bash
uv run ruff check .
uv run mypy app
uv run pytest
```

## 关键约定

- 主键统一使用 UUID4 字符串。
- 时间采用服务器本地时间（见上文），不使用 UTC。
- 迁移使用 Alembic，不用 `create_all()` 替代。
- 枚举字段存字符串值（`enum.value`），枚举类继承 `str, Enum`。
- 生产环境（`APP_ENV=prod`）启动时会校验 `APP_SECRET` 与 `CREDENTIAL_ENCRYPTION_KEYS`，缺失或仍为示例值将拒绝启动。
- 错误响应统一为 `{ "error": { "code", "message", "request_id", "details" } }`。

## 模型适配审理（2026-10-15）

上线前执行 `uv run alembic upgrade head`，新增迁移 `f1a2b3c4d5e6` 为方案版本保存不可变的
`generation_review_json`。旧审理不包含模型绑定，必须重新审理；原有小框与聊天记录保留。
前后端需要一起部署。

- 用户流程保持“AI审理方案 → 查看最终方案、必要调整和可选建议 → 生成视频”。
  审理为独立的一次性处理，不发起追问；点击生成即采用本次展示的方案，无额外接受按钮。
- `GET /api/v1/video-generation-target?api_config_id=platform` 返回实际模型、配置修订和规则摘要，
  不返回凭据。平台通道从 `VIDEO_PLATFORM_PROTOCOL/MODEL/PROFILE_CODE` 解析，前端不猜模型。
  使用 `ep-*` 接入点时必须显式指定能力档案。未知模型、未实现模式和不合法素材组合会阻止生成。
- `POST /conversations/{id}/canvas/prepare-video` 除原字段外接收 `api_config_id`、
  `mode`（auto/text_to_video/first_frame_to_video/first_last_frame_to_video/reference_image_to_video）
  和 `input_roles`（first_frame_node_id/last_frame_node_id）。自动模式不把两张图默认为首尾帧。
- 原始输入保存在 `video_duration_seconds/video_resolution`，审理采用的候选参数在
  `generation_settings`，两者可以不同；差异和原因在审理结果中展示。每次生成仍限 1–15 秒。
  原始小框不被审理覆盖。无法适配时保存 blocked 结果，给出操作要求，不显示可以生成的结语。
- 后端 `video_generation_policy.py` 是审理和提交共同使用的规则入口；模型登记在
  `video_registry/core_protocols.py`。可用 `ParameterRule` 声明参数枚举、上下界和
  `when` 条件组合，放在模型或模式的 `rules` 中。规则更改会更新内容摘要，使旧审理失效。
  规则用于构造合法候选并传给文本 AI；AI 只创作，不决定参数是否合法。
- 提交 `POST /video-jobs` 必须携带审理的四个 `generation_settings` 值和
  `generation_options.review_fingerprint`，以及原来的来源小框列表。提交、确认都核对不可变版本；
  切换通道、配置修订、规则、模式、素材、正文或原始参数后需要重新审理。
  直接修改画布中的审理内容和参数会被后端恢复，不能绕过校验。
- 新审理从展示的结构化字段统一编译提示词，不拼接可能残留旧参数的自由提示词。
  提示词保存在版本/任务中，前端不展示。自适应画幅的 API 省略策略在审理时确定，
  提交阶段只验证，不临时删改参数。
- 提交、轮询、取消、下载按任务固化的协议选择适配器，用户通道绑定不可变 revision；
  平台任务也固化模型和地址。只有 `VIDEO_PROVIDER=fake` 会统一使用模拟视频适配器。

回归测试：`uv run pytest tests/test_generation_policy.py tests/test_model_bound_review.py tests/test_canvas.py tests/test_video_job.py tests/test_video_adapters.py tests/test_video_api_config.py`。
