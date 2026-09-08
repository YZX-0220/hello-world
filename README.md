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
