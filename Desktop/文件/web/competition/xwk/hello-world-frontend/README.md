# Vue 3 + TypeScript + Vite

This template should help get you started developing with Vue 3 and TypeScript in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about the recommended Project Setup and IDE Support in the [Vue Docs TypeScript Guide](https://vuejs.org/guide/typescript/overview.html#project-setup).

## 模型适配审理（2026-10-15）

本轮在 `frontend-yzx` 的 `3864236` 基础上修改。生成区仍为“AI审理方案 → 查看方案及调整 → 生成视频”，
通道和模式选择放在审理之前，支持首帧、首尾帧、参考图。后端必须同步更新并执行 `alembic upgrade head`。

- `useWorkspace.ts` 从 `GET /video-generation-target` 读取真实目标，取消平台模型硬编码和前端重复规则引擎。
- 审理请求携带通道、模式、素材角色。原始设置与后端建议的最终参数分别保存；点击生成即采用展示方案。
- `generationState.ts` 比较来源、原始参数、模式、素材角色和目标指纹；旧版本、切换模型或审理出错均不能生成。
- `CanvasDocument` 新增 `generation_target/generation_input/generation_requested_settings` 等字段。
  `generation_review.status` 为 ready/blocked，fingerprint 随生成请求提交，生成时不得改写其参数。
- 提交使用冻结的项目、通道、来源和审理参数；同一次失败重试复用幂等编号。实际视频提示词保存在后端，不展示。
- 路由对 `Tv.vue` 使用正确的文件名大小写，确保 Windows 和 Linux 构建一致。

检查：`npm ci`、`npm test`、`npm run build`。本地运行须将
`VITE_API_PROXY_TARGET` 指向本地后端，避免默认代理到远端。

## Seedance 2.5 素材适配（2026-10-15）

- 默认保留自动、文生、首帧、参考图模式；首尾帧放在“高级选项”分组。
  页面说明首帧锁定起始画面、普通参考图只参考主体/风格。后端声明支持时允许同图首尾帧。
- 目标接口的 `profile.duration.allowed_values` 与平台 1–15 秒取交集：
  此模型下用户手动选择 4–15 秒整数，合法的 7 秒保持 7 秒；清晰度按目标能力列出。
- 图片处理在后端审理阶段完成。审理结果只文字说明缩放、补边、格式等实际处理，
  不增加适配图预览和额外确认按钮，画布仍展示原图。生成复用已审理图片。
- 沿用“AI审理方案 → 查看方案及处理说明 → 生成视频”，不增加审理追问；
  实际提交提示词继续隐藏。厂商失败原因经后端处理后显示在现有任务错误区域。
- 需和更新后的后端一起部署。新规则使旧审理失效，需要重新审理，原始画布内容保留。
  完整规则、上传资源上限、官方来源和剩余运行时风险见后端 README 的
  “Seedance 2.5 图片适配与限制核查”。

## 首页累计访问（2026-10-19）

- 主视觉下方只展示“网站已有累计访问 X 次.”，不展示今日数、在线人数或伪造历史数。
- `main.ts` 在首次路由解析前安装匿名统计。成功进入首页、登录、工作台、TV、API 配置页，
  以及隐藏页重新可见时上报；管理页、请求轮询、资源加载不参与。计数由后端的 30 分钟滑动访问窗决定。
- `siteTraffic.ts` 串行报告，先 GET summary 建立 HttpOnly Cookie，再 POST visits；
  请求失败最多重试一次，保留 event_id。Web Locks 可用时串行化跨标签的初始化和报告，
  不可用时使用各标签队列和后端 Cookie 去重；首次无 Cookie 的多标签并行打开仍是尽力识别。
- `useSiteTraffic.ts` 的请求与登录拦截器隔离，五秒超时，不跳转登录或阻止业务导航。
  未取得有效数字时显示加载/暂不可用；已读到的真实累计数在短暂故障时保留。
  不采集屏幕、键盘、鼠标或精确位置；来源只发 origin，路由不发送查询参数/会话 ID。
- 必须先发布后端并执行 `alembic upgrade head`（当前头版本 `b3c4d5e6f7a8`，
  包括统计基础 `a2b3c4d5e6f7` 和原始 IP 补充迁移）。
  统计接口尚未发布时页面正常可用，计数显示暂不可用。
- `npm test`（含 6 项新增统计测试，共 27 项）与 `npm run build` 均通过。
  本地浏览器已验证初次访问、刷新、往返 TV 保持同次访问。
  本地联调务必设置 `VITE_API_PROXY_TARGET` 指向测试后端，默认代理仍指向远程。
