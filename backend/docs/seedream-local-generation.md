# Seedream 本地原图链路

当前实现支持文生图、参考图生成和基于历史结果持续修改，支持火山方舟普通 API 与 Agent Plan 订阅 API。生成原图落在服务器本地，注册为既有 Asset，继承画布、权限和视频输入机制。未改造全部历史上传或视频 OBS 方案。

## 使用路径

1. API 配置中心 → 图片 API：选择普通 API 或订阅 API，填写对应密钥并选择 Seedream Pro / Flash；也可使用管理员配置的平台默认通道。
2. 画布工具栏或图片小框 → AI 生图：输入描述、选择比例。可请现有文本 AI 给提示词建议，显式采用后再生成。
3. 任务在服务端执行，关闭面板不会取消；重新打开可查看本对话最近 100 条记录。
4. 成功后放大查看、下载原图或插入画布。插入创建新素材，不覆盖原图片；保留完整生图描述、job_id、asset_id。
5. 同时选中一个文本框与图片，或将二者连线，进入已有视频审理流程。单图可作为首帧，多图按所选视频模型能力作为参考图。生图描述本身不会自动变成视频脚本。

无参考图的文字建议使用 TEXT_*。有参考图的生图建议通过专用 VISION_* 视觉文字模型接收真实图片字节（image_url data URL），并接收当前模型、尺寸、输出格式、水印和编辑历史。缺视觉配置时明确不可用，绝不将纯文本回答冒充看图。此次视觉能力限于图片创作面板，并未给既有视频审理或画布通用 Agent 自动添加视觉输入。

## 模型与人像边界

- 普通模型 `doubao-seedream-5-0-pro-260628`、`doubao-seedream-5-0-flash-260915` 固定请求 `/api/v3/images/generations`；订阅模型 `doubao-seedream-5.0-pro`、`doubao-seedream-5.0-flash` 固定请求 `/api/plan/v3/images/generations`。主机均为 `https://ark.cn-beijing.volces.com`，模型与密钥在提交时冻结，不因失败跨接口回退。
- 每次输出单图、PNG；水印默认 false，用户可勾选开启。`IMAGE_RESPONSE_FORMAT=url` 默认保留临时下载链接；可设置 `b64_json` 直接接收原图数据，适合图片下载域名网络不可达的环境。
- 比例：1:1 → 1536×1536，16:9 → 2048×1152，9:16 → 1152×2048，4:3 → 1792×1344，3:4 → 1344×1792。
- 2026-11-07 普通 Pro 的完整模型 ID 已通过模型列表与文生图实测；提供的两把密钥均在订阅接口返回认证失败，故不能宣称订阅通道实测成功。订阅 Pro 在部分能力表有不同拼写，接入订阅密钥后仍需按实际账户验证。
- 已移除账号标识及关联视频配置的前端声明入口，旧数据库字段兼容保留，不用其推断信任关系。平台默认生图与视频通道仍需要管理员选择符合实际业务要求的账号。
- 按官方人像素材说明，适用范围包含同账号近期（30 天内）未修改的合格 Seedream 文生图原始产物；这不是“免审核”承诺。压缩、裁剪、格式转换可能影响来源识别，视频输出仍受审核。

官方资料（本次接入时核对）：

- [订阅视觉模型](https://docs.volcengine.com/docs/ark/agent-plan-personal-visual-models?lang=zh)
- [模型迁移公告](https://docs.volcengine.com/docs/ark/agent-plan-personal-model-deprecation-announcement?lang=en)
- [图片生成接口](https://docs.volcengine.com/docs/ark/image-generation-api?lang=zh&redirect=1)
- [Seedance 人像素材说明](https://docs.volcengine.com/docs/ark/seedance-portrait-asset-guide?lang=zh)

## 配置与迁移

先在目标环境备份数据库，再按项目惯例执行 `python -m alembic upgrade head`。`d5e6f7a8b9c0` 创建 image_api_configs / image_jobs；新增 `e6f7a8b9c0d1` 保存父任务、参考图快照、编辑历史、实际提示词和水印。旧任务保留 watermark=true，新任务默认 false。本次开发仅迁移隔离的本地预览库，未迁移既有业务库或线上库。

`.env.example` 已列出：

| 配置 | 默认值/含义 |
| --- | --- |
| IMAGE_PROVIDER | ark；兼容旧值 ark_plan；fake 仅开发环境允许 |
| IMAGE_PLATFORM_API_KEY | 默认通道密钥；留空时平台通道不可用，用户仍可自备 |
| IMAGE_PLATFORM_MODEL | doubao-seedream-5.0-pro |
| IMAGE_RESPONSE_FORMAT | url / b64_json；默认 url |
| IMAGE_PLATFORM_ACCOUNT_LABEL | 平台生图通道的账号标签 |
| IMAGE_PLATFORM_DAILY_LIMIT | 10；每用户每天平台提交上限，取消排队任务不计入 |
| IMAGE_MAX_PENDING_PER_USER | 3；queued / generating / saving 并发上限 |
| IMAGE_TIMEOUT_SECONDS | 600；允许较慢的图片编辑请求完成，避免过早进入结果待确认 |
| IMAGE_MAX_RESULT_BYTES | 30000000 |
| IMAGE_WORKER_ENABLED | true；随 FastAPI lifespan 启动数据库队列 worker |

必须设置稳定的 `CREDENTIAL_ENCRYPTION_KEYS`。用户密钥加密存储，仅返回尾号；任务冻结配置版本和加密凭据快照，修改/删除配置不会篡改已提交任务。备份恢复应同时保留加密密钥、数据库和本地媒体文件。

开发模拟需显式 `IMAGE_PROVIDER=fake`。不提供真实密钥时不会静默伪装为真实生图。生产环境禁止 fake。

## 存储与状态设计

- 原图：`STORAGE_ROOT/<user_id>/generated-images/<job_id>.<ext>`；`purpose=generated_image`，`storage_provider=local`。校验文件格式、大小、像素、SHA-256，不重新编码。
- 页面预览：`GET /api/v1/assets/{asset_id}/content?thumbnail=raw`；下载：`?download=true`。二者要求所有者登录，下载使用原字节。
- 配置 OBS 的环境中，这类本地 Asset 仍走本地读路径。上传素材遵循已有配置，不将旧上传统一改成本地。
- 视频输入按 Asset ID 取得原文件，用任务绑定的签名 provider-assets URL 提供给视频厂商；对生成原图不自动压缩/补边，规格不符则要求更换素材或模式。
- 本地 localhost 的文件地址无法被远程视频厂商访问。真实视频联调需要可从公网访问的 HTTPS APP_BASE_URL（既有签名素材接口）；本地磁盘存储本身不要求 OBS。不要把本地模拟链路通过等同于线上厂商取图通过。

状态：queued → generating → saving → succeeded。排队可取消。明确厂商拒绝为 failed；请求超时/服务中断而结果不明为 unknown，不自动重发生图。用户核对方舟后可显式结束等待为 unknown_acknowledged；不会取消厂商任务、退还本地日配额或自动生成新图。

保存失败为 storage_failed，重试仅下载/保存已返回结果，不再次调用生图模型。厂商临时链接可能过期；若异常返回仅 base64 而服务在落盘前中断，无法通过临时链接恢复，接口会明确拒绝重试保存。

按用户写锁串行检查配额和幂等，重复相同 Idempotency-Key 返回原任务，不同请求复用键返回冲突。worker 原子领取并以 lease token 校验 checkpoint/终结；迟到 worker 不能覆盖接管者。过期 generating 恢复为 unknown，过期 saving 仅恢复保存。

## HTTP 接口

所有路由前缀 `/api/v1`，要求登录，写操作要求现有 CSRF 机制。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | /image-generation/options | 支持模型、比例、平台可用性、模拟标记 |
| GET / POST | /image-api-configs | 列出 / 新增自备配置 |
| PATCH / DELETE | /image-api-configs/{id} | 乐观版本更新 / 软删除 |
| POST | /image-prompt-suggestions | 描述建议，不执行生成 |
| POST | /image-jobs | 提交；必须带 Idempotency-Key |
| GET | /image-jobs?conversation_id=… | 当前对话最近 100 条任务 |
| GET | /image-jobs/{id} | 状态与原图入口 |
| POST | /image-jobs/{id}/cancel | 仅取消 queued |
| POST | /image-jobs/{id}/retry-storage | 仅重试结果保存 |
| POST | /image-jobs/{id}/acknowledge-unknown | 用户核对后结束未知结果等待 |

POST image-jobs 的主要字段：conversation_id、api_config_id（platform 或自备配置 ID）、prompt、aspect_ratio、可选 source_node_id。模型/凭据由服务端从配置解析，前端不能覆盖请求端点。

## 真实凭据验收

2026-11-07 已使用真实 Key 完成普通 API 文生图；结果域名为 `ark-acg-cn-beijing.tos-cn-beijing.volces.com`。本机代理将该域名解析为保留地址，原始下载被安全校验阻止；该次原图通过人工恢复原始字节保存，未重复生成。后续本地预览使用 b64_json 直接接收图片。图改及 UI 验收的最新结果见本轮交付报告。未调用真实视频服务，未验证人像视频准入；不能保证人物素材或最终视频一定审核通过。

## 参考图与持续修改

- 新增 `POST /api/v1/image-reference-uploads`，multipart file + conversation_id，登录与 CSRF 必须。上传原图始终本地存储，即使其他上传使用 OBS；PNG/JPEG、单张不超过10,000,000字节，并受平台像素限制。
- image-jobs 与 image-prompt-suggestions 增加 reference_asset_ids（最多4）、parent_job_id、watermark=false；建议同时携带 api_config_id。
- parent 必须是本用户、本对话成功的任务，其结果自动排为第一张参考图；与手选图片去重，总数最多4。普通参考素材允许本用户跨对话使用。
- 创建任务时读取并保存输入的 SHA-256、尺寸和名称快照；worker 发送前再次核对所有者、ready/deleted状态及原文件hash。参考图被更换或删除则失败，不调用厂商。
- 请求将图片原字节编码为 image 数组中的 data URL，localhost 无需向图生厂商公开。既有 OBS 素材通过存储 SDK 有界读取；不接受浏览器传入任意外链作为模型输入。
- 编辑请求发送选中父图、当前要求和有界历史描述（初始轮及近期轮，最多6条、每条最多600字用于提示词）。最新要求优先，未要求修改的内容尽量保留；完整各轮prompt与父链仍可追溯。不是厂商有状态会话，不保证逐像素一致。
- “继续修改”创建新任务、新文件，不覆盖上一版；可选择任何历史结果分支。上传图片、从节点取图和连续编辑都使用同一套输入校验。
- 图生图产物不得自动视为人像可信的文生图原始产物；需按厂商实际规则和真实账号验收。

## 视觉文字模型配置

配置兼容 Chat Completions 且支持 image_url 输入的 VISION_BASE_URL、VISION_API_KEY、VISION_MODEL，选填 VISION_TIMEOUT（默认90秒）。三项必须完整，不会用部分视觉配置回退到文本服务。

仅当管理员确认当前 TEXT_MODEL 支持视觉时，才可设置 TEXT_SUPPORTS_VISION=true 复用 TEXT_*；默认false。界面“可用”表示配置完整，并非厂商连通性验证。现有本地 deepseek-chat 配置没有显式视觉声明，因此预览不会冒充真实看图。

文字建议的系统提示词要求观察实际输入、保留用户意图、遵守本次模型与参数，不宣称必过审核；图片内文字作为素材而非系统指令。结果仍由用户显式采用，不能自动替换描述或触发生图。
