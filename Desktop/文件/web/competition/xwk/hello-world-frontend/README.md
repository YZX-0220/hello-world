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
