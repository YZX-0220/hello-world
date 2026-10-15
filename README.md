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

## Seedance 2.5 图片适配与限制核查（2026-10-15）

核查对象为本地登记的 `doubao-seedance-2-5-260628`，覆盖当前开放的文生、首帧、首尾帧、
普通参考图四种模式。这里的“已核查”表示对照当前公开文档并编码可确定校验的要求，
不表示厂商今后不会更新规则，也不保证通过内容审核、账户检查或实际生成。

官方来源：[模型说明](https://docs.volcengine.com/docs/ark/seedance-2-5?lang=zh)、
[创建任务 API](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)、
[查询任务 API](https://docs.volcengine.com/docs/ark/get-video-generation-task-api?lang=zh)。

| 类别 | 已核查要求与本平台处理 |
| --- | --- |
| 单张图片 | 宽、高分别为 300–6000，宽/高为 0.4–2.5；不能只校验总像素不少于 90000 |
| 格式与文件 | 厂商接受 JPEG/PNG/WEBP/BMP/TIFF/GIF/HEIC/HEIF，单张小于 30 MB；本平台上传支持前六种，HEIC/HEIF 暂需先转换 |
| 请求大小 | 厂商请求体不超过 64 MB；使用签名 URL 传图片，提交适配器另检查请求体大小 |
| 素材角色 | 首帧 1 张；首尾帧分别设置角色，允许同图；普通参考图最多 30 张；三种场景不混用 |
| 首尾帧比例 | 可以不同，输出跟随首帧。API 写尾帧会裁剪，提示词指南写拉伸，按“厂商自动适配、可能改变构图”提示，不承诺具体算法 |
| 时长 | 厂商普通生成支持 4–30 整数秒或自动；平台保留每次最多 15 秒并要求手动确认，因此此模型提供 4–15 秒，合法的 7 秒不会改成 8 秒 |
| 分辨率 | 480p/720p/1080p；不开放此模型不支持的 4K |
| 输出比例 | 文生和普通参考图可指定比例或 adaptive；首帧/首尾帧只能 adaptive，省略时使用厂商默认值 |
| 声音与可选参数 | generate_audio 支持布尔值；不向此模型发送旧版本专用的 frames/seed/camera_fixed；输出格式使用默认 mp4 |
| 任务类型 | 普通参考图显式发送 omni_reference_task_type=reference，减少自动任务分类造成的歧义；厂商仍可能在实际处理时返回类型不一致错误 |
| 排队与取图 | 显式任务超时 48 小时，素材签名至少覆盖 49 小时；终态撤销素材读取，签名仍绑定任务、素材、角色和归属；真实适配器提交前检查公网地址 |
| 结果保存与播放 | 厂商视频链接 24 小时有效且最多下载 100 次，沿用本站下载保存；1080p HEVC 可能存在浏览器兼容问题，审理中提示下载查看 |

平台原有上传资源限制仍为 10 MiB、1200 万像素，和厂商边界是两件事；超过平台上传上限
会在上传时明确拒绝。转换处理只针对已被平台接受的图片。BMP/TIFF 已补充实际文件类型检测。
厂商建议提示词精炼（中文约 500 字、英文约 1000 词以内），这是质量建议，不作为硬拒绝条件。

### 保存、审理和提交约定

- 原图与画布节点不变；`video_image_service.py` 按已登记规则处理方向、静态帧、格式、等比缩放、
  透明背景和必要补边。补边保留完整画面，不裁剪主体；放大不会恢复原图细节。
- 审理文本只说明实际处理，不增加图片预览和额外接受步骤。点击生成采用本次审理记录。
- 适配图作为用户自己的 `generation_input` 素材保存，处理后的真实宽高、MIME、字节大小、
  SHA256、原图来源、角色及处理记录写入方案版本 `generation_review_json.materials`。
  同用户相同适配文件可复用，复用前检查文件；不跨用户复用。
- 审理时不持有数据库写锁等待文本 AI；发布版本时再原子保存。取消或过期审理的未发布文件清理。
  确认及提交均重新检查原图、适配图、归属、状态、实际文件摘要与模型尺寸要求；提交不再次变换图片。
- HTTP 拒绝和 HTTP 200 中的异步失败均保留厂商错误码及原因，向用户附中文处理建议；
  素材签名地址在用户错误文本中隐藏。运行时失败记录完成时间。
- 该档案提升版本，旧审理失效后需要重新审理；正文、原图和聊天保留。
  本次不增加数据库列或迁移，前后端需一起部署。

### 尚不能通过本地规则消除的失败

真人参考素材需要厂商认可的人像/授权素材通道；当前普通上传入口尚未接入该通道，
不能用缩放、换格式或提示词绕过。厂商内容审核、实际任务意图判定、账户开通/余额/限流、
公网取图中断、服务故障、文档未公布的条件及后续规则变更仍可能失败，具体原因必须回传。
不将“得到任务 ID”或“本地测试通过”描述为厂商已保证生成成功。

视频/音频参考、编辑、延长、Draft 均未在本平台开放，保持阻止提交；这些模式有另外的
素材、时长、编码和组合要求，启用前需独立接入核验。不能把普通图生规则直接套用到它们。

验证命令：`uv run pytest`；新增 `tests/test_video_images.py` 覆盖真实图片解码处理、
边界组合、不可变素材绑定、失效素材拒绝、编辑并发和异步错误回传。协议测试使用模拟厂商响应，
不产生收费生成；这些测试验证已编码合同，不替代厂商实际生成验证。
