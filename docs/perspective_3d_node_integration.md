# 「3D 视角与空间构图节点 (Perspective Node)」前后端联调与前端待改清单

本文档对应前端分支 `frontend-yzx`（提交 `7c86521`：`feat: 新增3D视角节点与空间构图搭建器并修复画布缩放`）与后端 `backend` 分支的联调说明。当前已完成**后端全部改造与测试**，并将**前端仍需调整的点**集中记录于第 2 节。

---

## 1. 后端已完成改动

1. **画布节点 Schema 扩展**（[canvas.py](file:///E:/hello-world/backend/app/schemas/canvas.py)）
   - `CanvasNode.type` 已允许 `"perspective"`，并显式声明 `perspective_data: dict[str, Any] | None = None`（保存 `aspectRatio`、`groundColor`、`objects`、`startCamera`、`endCamera`、`endFrameUrl` 等 3D 场景状态）。
   - `CanvasNode.url` 与 `asset_id` 兼容确认瞬间写入的临时 `data:image/png;base64,...` 以及异步上传完成后的 `/api/v1/assets/{id}/content`。

2. **3D 视口截图上传通道**（[asset_service.py](file:///E:/hello-world/backend/app/services/asset_service.py)）
   - `POST /api/v1/assets` 除已支持的 `purpose="reference"`（当前 `frontend-yzx` 使用的值）外，同时新增 `purpose="perspective_capture"`，均校验并返回标准 `image` 类型 `AssetView`（含 `id` 与 `content_url`）。

3. **画布协作与 AI 视频审理链路**（[canvas_images.py](file:///E:/hello-world/backend/app/services/canvas_images.py)、[canvas_service.py](file:///E:/hello-world/backend/app/services/canvas_service.py)、[canvas_video_service.py](file:///E:/hello-world/backend/app/services/canvas_video_service.py)）
   - **画布 AI 协作 (`CanvasService.begin`)**：引用 `perspective` 节点时，既将 6D 空间/运镜文本传入提示词，也会在节点已存在 `asset_id` 时调用 `load_canvas_images(..., include_perspective=True)` 将 3D 视口截图作为多模态参考传给策划模型；若截图尚未上传完（`asset_id` 为空），仅传递文本描述而不阻断。
   - **AI 视频方案审理 (`CanvasVideoService._prepare`)**：当选中节点（或单选连线自动展开后传入 `node_ids`）包含 `perspective` 节点时，自动将其 6D 空间与运镜正文拼接为 `3D 视角参考小框【...】（type=perspective）` 输入给审理模型并参与画幅比例自动识别（如 `9:16` / `16:9`），同时**不会**把 3D 白模截图误注入视频生成的 `first_frame_asset_id` / `reference_asset_ids` 槽位。

4. **Agent System Prompt 规则注入**（[context_builder.py](file:///E:/hello-world/backend/app/services/context_builder.py)）
   - 新增 `PERSPECTIVE_NODE_INSTRUCTION` 并同时注入 `DEFAULT_SYSTEM_PROMPT` 与 `VIDEO_REVIEW_SYSTEM_PROMPT`：强制锁定机位俯仰/焦段/画幅/运镜与前景遮挡关系，并要求大模型将几何体代称具象化替换、禁止在成片提示词中残留“立方体/球体/白模”等 3D 辅助词。

5. **自动化测试**（[test_perspective_node.py](file:///E:/hello-world/backend/tests/test_perspective_node.py)）
   - 覆盖 `perspective` 节点画布保存/读取、PNG 截图上传、多参考图生图（`3D 截图 + 角色参考图`）、画布协作与视频审理链路。

---

## 2. 前端 (`frontend-yzx`) 需要修改的地方

排查 `origin/frontend-yzx`（提交 `7c86521`）代码后，以下 5 处需要在前端分支补充或修正，以完整跑通全部交互闭环：

### 2.1 生图面板未识别 `type === 'perspective'` 源节点（必须修改）

- **现象**：在画布点击 3D 节点上的「✧ 结合参考图生图」时，`WorkspaceView.vue` 的 `openImageGenFromPerspective(node)` 会把 `perspective` 节点作为 `sourceNodeId` 传入生图面板。但以下两处硬编码了 `node.type === 'image'`，导致生图面板无法自动挂载 3D 截图、参考图与提示词：
  1. `frontend/src/components/ImageGenerationPanel.vue`（约第 76 行）：
     ```ts
     // 现状（仅识别 image，忽略了 perspective）
     const sourceNode = computed(() =>
       props.nodes.find(node => node.id === props.sourceNodeId && node.type === 'image')
     );

     // 建议改为：
     const sourceNode = computed(() =>
       props.nodes.find(
         node => node.id === props.sourceNodeId && (node.type === 'image' || node.type === 'perspective')
       )
     );
     ```
  2. `frontend/src/services/imageGeneration.ts`（`imageSourceDraft`，约第 52-57 行）：
     ```ts
     // 现状：
     if (current.pending || node?.type !== 'image' || !node.asset_id) return current;

     // 建议改为支持 perspective：
     if (current.pending || !node || !['image', 'perspective'].includes(node.type) || !node.asset_id) {
       return current;
     }
     ```

### 2.2 「✧ 结合参考图生图」联动带入连线参考图与 3D 构图提示词（建议补充）

- **现状**：`WorkspaceView.vue` 中 `openImageGenFromPerspective(node)` 虽然计算了 `linkedIds = expandConnectedNodeIds([node.id])` 并提示「已将 3D 视角构图及连线参考图载入生图面板」，但 `openImageGeneration(node)` 仅设置了 `imageSourceNodeId.value = node.id`，并未把与该 `perspective` 节点**连线关联的其他 `image` 参考图节点**的 `asset_id` 写入生图草稿 `draft.reference_images`，也未自动填入 3D 节点的 `content`（或画幅 `perspective_data.aspectRatio`）。
- **建议改动**（`WorkspaceView.vue` / `ImageGenerationPanel.vue` / `imageGeneration.ts`）：
  - 打开生图面板或 `applySourceNode` 时，如果 `sourceNode.type === 'perspective'`：
    1. 将 `[sourceNode, ...连线的 type === 'image' 节点]` 中已上传的 `asset_id`（最多 4 张，去重）填入 `draft.reference_images`（对应后端 `POST /api/v1/image-jobs` 的 `reference_asset_ids`）；
    2. 若 `sourceNode.perspective_data?.aspectRatio` 存在于可用比例列表且用户未手动改过草稿，可同步预设 `draft.aspect_ratio`；
    3. 若 `draft.prompt` 为空且存在 `sourceNode.content`，可自动预填或展示快捷按钮将 6D 空间描述填入画面描述框。

### 2.3 视频生成面板的首尾帧选择器不应列出 3D 白模节点（建议修改）

- **现状**：`frontend/src/views/WorkspaceView.vue`（约第 637-641 行）的 `videoImageNodes` 写了：
  ```ts
  const videoImageNodes = computed(() =>
    generationSources(canvas.value, videoSourceIds.value).filter(
      n => (n.type === 'image' || n.type === 'perspective') && n.asset_id
    )
  );
  ```
- **问题**：视频生成面板里的 `videoImageNodes` 用于渲染**首帧图片 / 尾帧图片**下拉框（`video_input_roles.first_frame_node_id` / `last_frame_node_id`）。3D 节点的截图是纯白模辅助线图，不应被用户选为成片首帧/尾帧；而且后端 `_asset_spec` 仅允许 `type === 'image'` 作为首尾帧素材，如果用户从下拉框选了 `perspective` 节点，后端审理会提示「请指定首帧和尾帧图片」。
- **建议改动**：将 `WorkspaceView.vue` 中 `videoImageNodes` 改回仅过滤真实图片节点：
  ```ts
  const videoImageNodes = computed(() =>
    generationSources(canvas.value, videoSourceIds.value).filter(
      n => n.type === 'image' && n.asset_id
    )
  );
  ```

### 2.4 精准单选模式下的 `perspective` 节点连线同步（视需求决定）

- **现状**：
  - 在默认单击模式（`isManualPreciseSelect === false`）下，`WorkspaceView.vue` 通过 `expandConnectedNodeIds` 会把与当前节点相连的 `perspective` 节点 ID 一并放入 `videoSourceIds`，前端 `generationSources(document, ids)` 与后端 `source_snapshot(data, node_ids)` 均能完整包含该 `perspective` 节点并校验通过。
  - 在双击进入精准单选模式（`isManualPreciseSelect === true`）下，如果只选中了 `text` 节点而未勾选其连线的 `perspective` 节点，前端 `generationState.ts` 第 10 行（`generationSources`）与后端 `source_snapshot` 目前都**只自动拉取 `type === 'image'` 的连线节点**（`perspective` 不会在未选中时静默带入），两者保持严格一致以免触发 `generationContextMatches` 指纹失配。
- **注意**：如果未来希望即使双击单选 `text` 节点也自动带入连线的 `perspective` 节点，**必须同时修改**：
  - 前端 `frontend/src/services/generationState.ts`：`n.type === 'image' || n.type === 'perspective'`
  - 后端 [canvas_video_service.py](file:///E:/hello-world/backend/app/services/canvas_video_service.py#L39)：`linked.get("type") in ("image", "perspective")`
  否则前后两端 `generation_snapshot` 对比会不一致，导致「AI 审理方案」后仍提示「小框、素材、模型、模式或生成参数已变化」。

### 2.5 3D 截图上传建议改用统一的 `request` 客户端（可选优化）

- **现状**：`frontend/src/views/WorkspaceView.vue` 的 `uploadPerspectiveDataUrl`（约第 509-538 行）直接使用原生 `fetch('/api/v1/assets', ...)` 并手动正则提取 `hw_csrf` Cookie。
- **建议**：统一复用 `frontend/src/services/request.ts`（或封装上传方法），可自动继承 `baseURL`（如跨域名部署时的 `VITE_API_BASE`）、统一的 Token 刷新与错误提示；若上传失败（例如网络波动导致 `asset_id` 未写入），建议给用户轻量提示「3D 视口截图上传失败，可点击重进弹窗再次确认」。
