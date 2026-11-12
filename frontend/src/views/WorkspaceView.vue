<template>
  <div class="workspace-layout">
    <!-- 手机端专用全屏阻断提示 -->
    <div class="mobile-block-overlay">
      <div class="mobile-block-card">
        <div class="mobile-device-icon">💻</div>
        <h1 class="mobile-block-title">手机端暂不支持</h1>
        <p class="mobile-block-desc">请前往电脑端使用</p>
        <span class="mobile-block-sub">当前工作台专为桌面端复杂节点连线与多模态创作设计</span>

        <!-- 移动端快捷跳转按钮组 -->
        <div class="mobile-actions-group">
          <router-link to="/" class="mobile-btn home-btn">
            <svg class="mobile-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            <span>返回品牌首页</span>
          </router-link>

          <router-link to="/tv" class="mobile-btn tv-btn">
            <span class="mobile-tv-icon-wrap">
              <svg class="mobile-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M7 3L11.5 7.5" stroke-width="1.8" stroke-linecap="round" />
                <path d="M17 3L12.5 7.5" stroke-width="1.8" stroke-linecap="round" />
                <rect x="2.5" y="7.5" width="19" height="13.5" rx="3" stroke-width="1.8" />
                <circle cx="18" cy="11.5" r="1.1" fill="currentColor" />
                <circle cx="18" cy="15.5" r="1.1" fill="currentColor" />
              </svg>
              <span class="live-dot-mini"></span>
            </span>
            <span>浏览 TV 频道</span>
          </router-link>
        </div>
      </div>
    </div>

    <!-- 顶部导航栏 -->
    <header class="top-nav">
      <div class="nav-left">
        <router-link to="/" class="brand-link" title="点击返回品牌首页">
          <div class="brand">
            <div class="brand-avatar">H</div>
            <span class="brand-name">Hello World</span>
            <span class="sub-badge desktop-only">国际传播特化 AI 视频工作台</span>
          </div>
        </router-link>

        <router-link to="/tv" class="nav-tv-btn" title="浏览 TV 频道">
          <span class="tv-icon-wrapper">
            <svg class="tv-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M7 3L11.5 7.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              <path d="M17 3L12.5 7.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              <rect x="2.5" y="7.5" width="19" height="13.5" rx="3" stroke="currentColor" stroke-width="1.8" />
              <path d="M6 11.5H14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
                stroke-opacity="0.8" />
              <path d="M6 14.5H11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
                stroke-opacity="0.4" />
              <circle cx="18" cy="11.5" r="1.1" fill="currentColor" />
              <circle cx="18" cy="15.5" r="1.1" fill="currentColor" />
            </svg>
            <span class="live-dot"></span>
          </span>
          <span class="tv-btn-label">TV 频道</span>
        </router-link>
      </div>

      <div class="nav-actions">
        <span v-if="currentConvId" class="save-indicator" :class="saveState.status" role="status">{{ saveLabel }}</span>
        <button v-if="currentConvId" class="glass-pill-btn" @click="retrySave"
          :disabled="saveState.status === 'saving'">保存</button>
        <router-link to="/settings/api" class="nav-link" title="点击进入 API 配置中心">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <span class="desktop-only">API 配置中心</span>
        </router-link>
        <button class="logout-btn" @click="handleLogout" title="退出当前登录状态">退出登录</button>
      </div>
    </header>

    <div v-if="notice || saveState.status === 'error' || saveState.status === 'conflict'" class="workspace-notice"
      role="status" aria-live="polite">
      <span>{{ saveState.status === 'error' || saveState.status === 'conflict' ? saveState.error : notice }}</span>
      <button v-if="deletedNode" @click="undoDeleteNode">撤销删除</button>
      <button v-if="saveState.status === 'error' && currentConvId" @click="retrySave">重试保存</button>
      <button v-if="saveState.status === 'conflict' && currentConvId"
        @click="resolveConflict('local')">保留并保存我的草稿</button>
      <button v-if="saveState.status === 'conflict' && currentConvId" @click="resolveConflict('remote')">使用云端版本</button>
      <button aria-label="关闭提示" @click="notice = ''">×</button>
    </div>

    <!-- 视图平滑推拉切换容器 -->
    <div class="workspace-body">
      <div v-if="loading" class="workspace-loading" role="status">正在加载项目…</div>
      <Transition name="slide-left" mode="out-in">

        <!-- ================= 视图 A：创作项目空间看板 ================= -->
        <main v-if="!currentConvId" key="view-a" class="board-container">
          <div class="board-header">
            <h2 class="board-title">创作项目空间</h2>
            <p class="board-sub">选择历史对话继续创作，或点击中央加号开启新视听方案</p>
          </div>

          <div class="cards-grid">
            <div class="square-card add-card" role="button" tabindex="0"
              :aria-disabled="!initialized || isCreatingConv || loading" @keydown.enter="handleCreateNewConversation"
              @click="handleCreateNewConversation">
              <div class="plus-icon">+</div>
              <span class="add-text">{{ isCreatingConv ? '正在初始化...' : '开启新创作对话' }}</span>
              <div class="add-glow"></div>
            </div>

            <div v-for="conv in conversations" :key="conv.id" class="square-card project-card"
              :style="getCardColorStyle(conv.id)" @click="switchConversation(conv.id)">
              <div class="card-top-bar">
                <span class="card-time">{{ formatFullTime(conv.created_at) }}</span>
                <button class="del-card-btn" title="删除对话" @click.stop="handleDeleteConversation(conv.id)">
                  ×
                </button>
              </div>

              <div class="card-content">
                <input
                  v-if="renamingConvId === conv.id"
                  v-model="renamingConvTitle"
                  class="card-rename-input"
                  v-autofocus
                  maxlength="120"
                  aria-label="修改项目名称"
                  @click.stop
                  @mousedown.stop
                  @blur="finishRenameConv(conv)"
                  @keydown.enter.prevent="finishRenameConv(conv)"
                  @keydown.esc.stop="cancelRenameConv"
                />
                <h3 v-else class="card-project-title" :title="getConvDisplayTitle(conv)">
                  {{ getConvDisplayTitle(conv) }}
                </h3>
                <span class="version-tag">版本 v{{ conv.version || 0 }}</span>
              </div>

              <!-- 左下角改名按钮 + 右下角进入提示 -->
              <div class="card-bottom">
                <button
                  type="button"
                  class="rename-card-btn"
                  title="修改项目名称"
                  @click.stop="startRenameConv(conv)"
                >
                  ✎ 改名
                </button>
                <span class="enter-text">点击进入工作台 →</span>
              </div>
            </div>
          </div>
        </main>

        <!-- ================= 视图 B：网格节点 AI 视频工作台 ================= -->
        <div v-else key="view-b" class="canvas-viewport" ref="viewportRef" @mousedown="handleCanvasMouseDown"
          @contextmenu="openContextMenu" @wheel="handleCanvasZoom">
          <!-- 左上角悬浮：返回创作项目空间与重置视图 -->
          <div class="floating-top-left">
            <button class="glass-pill-btn" @click="backToProjectSpace" title="返回项目空间看板">
              <svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              <span>项目空间</span>
            </button>
            <button class="glass-pill-btn icon-only" @click="resetCanvasView" title="重置画布视角">
              <svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
            </button>
            <button class="glass-pill-btn" @click.stop="addNode('text')">添加文本</button>
            <button class="glass-pill-btn" @click.stop="addNode('image')">添加图片</button>
            <button class="glass-pill-btn image-generate-entry" @click.stop="openImageGeneration()">✧ AI 生图</button>
            <span class="canvas-project-title">{{ activeConversation ? getConvDisplayTitle(activeConversation) : '新创作工作流' }}</span>
          </div>

          <!-- 左侧居中悬浮工具栏：素材库与国际传播指导 -->
          <div class="floating-left-bar">
            <button class="side-tool-btn" @click="goToEditor" title="视频剪辑">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M14.121 14.121L19 19m-7-7l7-7m-7 7l-2.879 2.879M12 12L9.121 9.121m0 5.758a3 3 0 10-4.243-4.243 3 3 0 004.243 4.243zm0-5.758a3 3 0 10-4.242-4.242 3 3 0 004.242 4.242z" />
              </svg>
              <span class="tool-tip">视频剪辑</span>
            </button>
            <button class="side-tool-btn" @click="openAssetsDrawer" title="素材库">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span class="tool-tip">素材库</span>
            </button>

            <button class="side-tool-btn highlight" @click="openGuideModal" title="国际传播指导">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span class="tool-tip">国际传播指导</span>
            </button>
          </div>

          <!-- 画布缩放/平移内容层 -->
          <div class="canvas-plane" :class="{ 'is-panning': isPanning }"
            :style="{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }">
            <div v-if="selectionBox.visible" class="selection-box" :style="{
              left: selectionBox.x + 'px',
              top: selectionBox.y + 'px',
              width: selectionBox.w + 'px',
              height: selectionBox.h + 'px'
            }"></div>
            <!-- 连线 SVG 层 -->
            <svg class="connections-layer">
              <defs>
                <linearGradient id="flowGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.2" />
                  <stop offset="50%" stop-color="#818cf8" stop-opacity="1" />
                  <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.2" />
                </linearGradient>
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
              </defs>

              <!-- 已确认的连线 (双击连线删除) -->
              <g v-for="conn in connections" :key="conn.id" class="conn-group"
                @dblclick.stop="deleteConnection(conn.id)" title="双击删除此连线">
                <path :d="calculateBezierPath(conn.from, conn.to)" class="connection-hit-path" />
                <path :d="calculateBezierPath(conn.from, conn.to)" class="connection-base-path" />
                <path :d="calculateBezierPath(conn.from, conn.to)" class="connection-flow-path" filter="url(#glow)" />
              </g>

              <!-- 拖拽连接中的临时连线 -->
              <path v-if="connectingSource" :d="calculateTempBezier(connectingSource, tempMousePos)"
                class="connection-temp-path" />
            </svg>

            <!-- 节点列表 -->
            <div v-for="node in nodes" :key="node.id" class="canvas-node"
              :class="[node.type, { selected: activeNodeId === node.id || selectedNodeIds.includes(node.id) }]"
              :style="{ transform: `translate(${node.x}px,${node.y}px)` }" @mousedown.stop="startDragNode($event, node)"
              @click.stop="selectNode(node, $event)">
              <!-- 节点左侧连接点 (In) -->
              <div class="node-port in-port"
                :class="{ 'port-target-active': connectingSource && connectingSource.id !== node.id }" @mousedown.stop
                @click.stop="handlePortClick(node, 'in')" title="点击连接至此节点">
                <div class="port-inner">
                  <span class="plus-icon">+</span>
                </div>
              </div>
              <!-- 节点头部 -->
              <div class="node-header">
                <div class="node-type-icon" draggable="true" title="拖入 Agent 作为参考" @mousedown.stop
                  @dragstart.stop="handleNodeDragStart($event, node)">
                  <span v-if="node.type === 'text'">≡</span>
                  <span v-else-if="node.type === 'image'">🖼</span>
                  <span v-else>🎬</span>
                </div>

                <!-- 节点命名（双击修改，使用受控本地缓冲状态，防止自动保存打断输入） -->
                <div class="node-title-wrap">
                  <input
                    v-if="renamingNodeId === node.id"
                    v-model="renamingNodeTitle"
                    class="node-title-input"
                    v-autofocus
                    maxlength="200"
                    aria-label="小框名称"
                    @mousedown.stop
                    @click.stop
                    @blur="finishRenameNode(node)"
                    @keydown.enter.prevent="finishRenameNode(node)"
                    @keydown.esc.stop="cancelRenameNode"
                  />
                  <span v-else class="node-title" @dblclick.stop="startRenameNode(node)" title="双击进行重命名">
                    {{ node.title }}
                  </span>
                </div>

                <button v-if="node.type === 'text'" class="node-edit-btn" @mousedown.stop
                  :aria-label="(editingNodeId === node.id ? '完成编辑：' : '编辑文本：') + node.title"
                  @click.stop="editingNodeId === node.id ? finishNodeEditing() : beginNodeEditing(node)">{{
                    editingNodeId === node.id ? '完成' : '编辑' }}</button>
                <button class="node-del-btn" @click.stop="deleteNode(node.id)" title="删除节点" aria-label="删除小框"
                  @mousedown.stop>✕</button>
              </div>

              <!-- 文本节点 -->
              <div v-if="node.type === 'text'" class="node-body text-body">
                <textarea v-if="editingNodeId === node.id || !node.content?.trim()"
                  :ref="el => setNodeEditor(node.id, el)" v-model="node.content" placeholder="直接编辑脚本、镜头描述或广告词…"
                  :aria-label="node.title + '内容'" :disabled="loading"
                  @focus="editingNodeId = node.id; activeNodeId = node.id" @mousedown.stop @click.stop
                  @keydown.ctrl.enter.prevent="finishNodeEditing" @keydown.escape.stop="finishNodeEditing"></textarea>
                <div v-else class="node-text-preview msg-content" tabindex="0" :aria-label="node.title + '正文'"
                  title="双击正文或点击“编辑”修改文本" @mousedown.stop @click.stop="selectNode(node, $event)"
                  @dblclick.stop="beginNodeEditing(node)" @keydown.enter.prevent="beginNodeEditing(node)" @wheel.stop
                  v-html="renderMd(node.content || '')"></div>
                <div v-if="node.ai_running || (isAgentResponding && aiTargetNodeId === node.id)" class="node-ai-status"
                  role="status">AI 正在协作，回复后需点击“确定并写入小框”…</div>
                <div v-else-if="node.pending_ai" class="node-ai-status">AI 正文尚未写入，当前文字已保留</div>
                <div v-if="node.ai_error" class="node-ai-status">{{ node.ai_error }}</div>
                <div class="node-footer-actions" @mousedown.stop>
                  <button class="ai-assist-pill" @click.stop="askAgentHelpNode(node)">
                    <span>{{ node.pending_ai ? 'AI 协作 · 待写入' : '✨ AI 协作' }}</span>
                  </button>
                  <button v-if="node.last_ai && node.content === node.last_ai.after" class="ai-assist-pill"
                    @click.stop="restoreBeforeAi(node)">撤销 AI 写入</button>
                </div>
              </div>

              <!-- 图片节点 -->
              <div v-else-if="node.type === 'image'" class="node-body image-body">
                <button class="image-generate-node" @mousedown.stop @click.stop="openImageGeneration(node)">✧ AI 生图</button>
                <label class="image-upload-hover-pill" @click.stop>
                  <input type="file" accept="image/*" class="hidden-file-input" :disabled="uploading.includes(node.id)"
                    @change="handleImageUpload($event, node)" />
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  <span>{{ uploading.includes(node.id) ? '正在上传…' : node.url ? '重新上传' : '上传图片' }}</span>
                </label>

                <div class="image-preview-box">
                  <img v-if="node.url" :src="node.url" alt="preview" />
                  <div v-else class="image-placeholder">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p class="empty-image-portrait-note" @pointerdown.stop @mousedown.stop @click.stop>人像素材请使用 AI 生图，参见<button type="button" @click.stop="portraitNoticeOpen = true">人像素材须知</button>。</p>
                  </div>
                </div>
              </div>

              <!-- 视频节点 -->
              <div v-else-if="node.type === 'video'" class="node-body video-body">
                <video :src="node.url" controls loop playsinline @mousedown.stop @click.stop></video>
              </div>

              <!-- 节点右侧连接点 (Out) -->
              <div class="node-port out-port" :class="{ 'port-source-active': connectingSource?.id === node.id }"
                @mousedown.stop @click.stop="handlePortClick(node, 'out')" title="点击拉出连接线">
                <div class="port-inner">
                  <span class="plus-icon">+</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 右键唤出快捷菜单 -->
          <Transition name="fade-fast">
            <div v-if="contextMenu.visible" class="context-menu-box"
              :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }" @click.stop>
              <div class="menu-title">添加节点</div>
              <div class="menu-item" @click="createNodeFromContext('text')">
                <div class="menu-icon">≡</div>
                <div class="menu-info">
                  <div class="item-name">文本</div>
                  <div class="item-desc">脚本、广告词、品牌文案</div>
                </div>
              </div>
              <div class="menu-item" @click="createNodeFromContext('image')">
                <div class="menu-icon">🖼</div>
                <div class="menu-info">
                  <div class="item-name">图片</div>
                  <div class="item-desc">首帧图、视觉参考、风格控制</div>
                </div>
              </div>
            </div>
          </Transition>

          <!-- 右下角悬浮：Agent 唤出按钮 -->
          <div class="floating-bottom-right">
            <button class="agent-orb-btn"
              :class="{ active: isAgentDrawerOpen, generating: isSubmittingJob || isAgentResponding }"
              @click="toggleAgentDrawer" title="打开 AI 协作" aria-label="打开 AI 协作">
              <div class="orb-inner">
                <div class="orb-logo"></div>
              </div>
            </button>
          </div>

          <aside class="agent-flyout-drawer"
            :class="{ open: isAgentDrawerOpen, expanded: isAgentExpanded, 'drag-over': isDraggingOverAgent }"
            :inert="!isAgentDrawerOpen" :aria-hidden="!isAgentDrawerOpen" @click.stop @mousedown.stop
            @dragover.prevent="handleAgentDragOver" @dragleave="handleAgentDragLeave" @drop.prevent="handleAgentDrop">
            <div class="drawer-top-bar">
              <div class="drawer-brand">
                <div class="orb-mini"></div><span>创作助手</span>
              </div>
              <div class="drawer-header-actions">
                <button class="drawer-expand" @click="isAgentExpanded = !isAgentExpanded">{{ isAgentExpanded ? '收起宽度' :
                  '展开对话' }}</button>
                <button class="drawer-close" aria-label="关闭创作助手" @click="isAgentDrawerOpen = false">✕</button>
              </div>
            </div>
            <div class="drawer-tabs" role="tablist" aria-label="创作步骤">
              <button role="tab" :aria-selected="agentTab === 'chat'" @click="agentTab = 'chat'">AI 协作</button>
              <button role="tab" :aria-selected="agentTab === 'image'" @click="openImageGeneration()">素材生图</button>
              <button role="tab" :aria-selected="agentTab === 'video'" @click="agentTab = 'video'">生成视频</button>
            </div>

            <ImageGenerationPanel embedded :open="imageGenerationOpen" :account-id="accountId" :conversation-id="currentConvId" :nodes="nodes" :canvas-busy="loading" :source-node-id="imageSourceNodeId" @close="isAgentDrawerOpen = false" @insert="insertGeneratedImage" @portrait-notice="portraitNoticeOpen = true" />

            <div v-show="agentTab === 'chat'" class="drawer-conversation">
              <div class="ai-target-picker">
                <div class="target-select-row">
                  <label for="ai-target">正在协作</label>
                  <select id="ai-target" v-model="aiTargetNodeId"
                    :disabled="isAgentResponding || isConfirming || isPreparingVideo">
                    <option value="">新建文本小框</option>
                    <option v-for="node in nodes.filter(n => n.type === 'text')" :key="node.id" :value="node.id">{{
                      node.title }}</option>
                  </select>
                </div>
                <small>选中图片可请 AI 看图，拖入小框可固定参考。自由讨论不会改动小框。点击“确定并写入小框”后，待写入正文才会替换小框文字，可撤销。</small>
              </div>
              <div v-if="referencedNodes.length" class="node-binding-banner">
                <div class="banner-tags"><span class="banner-label">参考：</span><span v-for="node in referencedNodes"
                    :key="node.id" class="ref-pill">{{ node.title }}</span></div>
                <button class="clear-bind" @click="clearReferencedNodes">清空参考</button>
              </div>
              <div v-if="isDraggingOverAgent" class="drag-drop-hint">松开鼠标，将小框添加为参考</div>
              <div class="drawer-messages" ref="messagesContainerRef">
                <div v-if="!messages.length" class="chat-empty">可以从零创作，也可以先在小框写草稿，再请 AI 帮你修改。仅想讨论时，直接提问即可。</div>
                <div v-for="msg in messages" :key="msg.id" :class="['message-row', msg.role]">
                  <div class="avatar">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
                  <div class="bubble">
                    <div v-if="msg.model_name === 'local-preview'" class="message-source">历史示例回复</div>
                    <div v-else-if="msg.model_name" class="message-source">{{ msg.model_name }}</div>
                    <div class="msg-content" v-html="renderMd(msg.content)"></div>
                    <div v-if="aiTargetNode?.pending_ai?.message_id === msg.id" class="pending-content-card">
                      <div class="pending-content-title">待写入正文 · {{ aiTargetNode.title }}</div>
                      <p v-if="aiTargetNode.pending_ai.source_model === 'local-preview'" class="proposal-help">
                        这是历史示例内容。发送新的创作要求，即可获得 AI 回复。</p>
                      <p v-else class="proposal-help">下方正文是点击“确定并写入小框”后实际写入的内容，聊天中的解释不会写入。</p>
                      <div class="msg-content" v-html="renderMd(aiTargetNode.pending_ai.content)"></div>
                      <p v-if="aiTargetNode.pending_ai.original !== undefined && aiTargetNode.pending_ai.original !== (aiTargetNode.content || '')"
                        class="proposal-help">你已修改小框文字。采用这份正文会替换当前文字，可通过“撤销 AI 写入”恢复。</p>
                    </div>
                    <div v-if="msg.citations?.length" class="citations-fold"><span class="citations-tag">已参考 {{
                      msg.citations.length }} 条资料</span></div>
                  </div>
                </div>
                <div v-if="isAgentResponding" class="message-row assistant">
                  <div class="avatar">AI</div>
                  <div class="bubble thinking" role="status" aria-live="polite">
                    <span class="loading-spinner" aria-hidden="true"></span>
                    <span class="thinking-text">AI 正在回复，小框原文已保留…</span>
                  </div>
                </div>
              </div>
              <div class="drawer-input-box">
                <div v-if="aiTargetNode?.pending_ai" class="drawer-confirm-row">
                  <span>写入“{{ aiTargetNode.title }}” · 替换当前文字</span>
                  <button class="confirm-pill"
                    :disabled="!canApplyAiContent || isConfirming || isAgentResponding || isPreparingVideo"
                    @click="confirmProjectSpec">{{ isConfirming ? '正在写入…' : '确定并写入小框' }}</button>
                </div>
                <textarea ref="textareaRef" v-model="inputContent" aria-label="发送给 AI 的消息"
                  placeholder="描述想法、提出问题，或告诉 AI 如何修改…"
                  @keydown.enter.exact="!$event.isComposing && ($event.preventDefault(), sendMessage())"></textarea>
                <div class="input-actions-row"><span class="hint">Enter 发送 · Shift+Enter 换行</span>
                  <button class="send-btn"
                    :disabled="!inputContent.trim() || isAgentResponding || isPreparingVideo || isConfirming"
                    @click="sendMessage">发送</button>
                </div>
              </div>
            </div>

            <div v-show="agentTab === 'video'" class="drawer-video-area">
              <div class="drawer-spec-panel">
                <h3 class="spec-quick-header">把选中的小框生成视频</h3>
                <p class="generation-help">选中一个或多个小框，AI 会先给出可直接生成的最终方案，再提供可选建议。缺少的创作细节会补全并注明。</p>
                <div class="generation-source-list">当前选中：{{videoSourceNodes.map(n => n.title).join('、') || '请先在画布选中小框'
                }}</div>
                <small class="generation-help">Ctrl 点击或拖动画布框选可选择多个小框；选中的图片及连线图片会供 AI 看图审理。</small>
                <p v-if="videoSourceNodes.some(n => n.pending_ai)" class="generation-help">部分小框有尚未采用的 AI
                  正文。视频只使用小框当前文字；需要采用时，请先回到“AI 协作”写入。</p>
                <p class="generation-help portrait-channel-help" @mousedown.stop>使用人像素材时，图片生成通道需与视频生成通道配套同源。<button type="button" @click.stop="portraitNoticeOpen = true">人像素材须知</button></p>
                <div class="spec-field-mini"><label for="video-api">视频生成通道</label>
                  <select id="video-api" v-model="selectedApiConfigId" :disabled="isSubmittingJob">
                    <option value="platform">平台体验通道（每日限 1 次）</option>
                    <option v-for="cfg in apiConfigs" :key="cfg.id" :value="cfg.id">{{ cfg.display_name }} ({{
                      cfg.remote_model_id }})</option>
                  </select>
                </div>
                <p v-if="targetLoading" class="generation-help" role="status">正在读取模型能力…</p>
                <p v-else-if="targetError" class="generation-help" role="status">{{ targetError }}</p>
                <div class="spec-field-mini"><label for="video-mode">生成模式</label>
                  <select id="video-mode" v-model="canvas.video_mode" :disabled="isSubmittingJob">
                    <option value="auto">按所选素材自动判断</option>
                    <option value="text_to_video">文生视频</option>
                    <option value="first_frame_to_video">首帧图生视频</option>
                    <option value="reference_image_to_video">参考图生视频</option>
                    <optgroup label="高级选项">
                      <option value="first_last_frame_to_video">首尾帧生视频</option>
                    </optgroup>
                  </select>
                </div>
                <p class="generation-help">{{ videoModeHelp }}</p>
                <div v-if="canvas.video_mode === 'first_last_frame_to_video'" class="video-generation-settings">
                  <div class="spec-field-mini"><label for="video-first-frame">首帧图片</label>
                    <select id="video-first-frame" v-model="canvas.video_input_roles.first_frame_node_id"
                      :disabled="isSubmittingJob">
                      <option value="">按画布顺序使用第一张图片</option>
                      <option v-for="image in videoImageNodes" :key="image.id" :value="image.id">{{ image.title }}
                      </option>
                    </select>
                  </div>
                  <div class="spec-field-mini"><label for="video-last-frame">尾帧图片</label>
                    <select id="video-last-frame" v-model="canvas.video_input_roles.last_frame_node_id"
                      :disabled="isSubmittingJob">
                      <option value="">按画布顺序使用第二张；仅一张时沿用首帧（模型支持时）</option>
                      <option v-for="image in videoImageNodes" :key="image.id" :value="image.id">{{ image.title }}
                      </option>
                    </select>
                  </div>
                </div>
                <div class="video-generation-settings">
                  <div class="spec-field-mini"><label for="video-duration">视频时长（秒，必填）</label>
                    <select v-if="selectedGenerationTarget?.profile?.image_constraints" id="video-duration"
                      v-model="canvas.video_duration_seconds" required :disabled="isSubmittingJob">
                      <option disabled :value="null">请选择时长</option>
                      <option v-for="duration in videoDurationOptions" :key="duration" :value="duration">{{ duration }}
                        秒</option>
                    </select>
                    <div v-else class="duration-control">
                      <input id="video-duration" v-model="videoDurationInput" type="number" min="1" max="15"
                        step="1" required placeholder="填写 1–15 秒" :disabled="isSubmittingJob" />
                      <div class="duration-stepper">
                        <button type="button" aria-label="减少 1 秒" aria-controls="video-duration"
                          :disabled="isSubmittingJob || (videoDurationInput !== '' && Number(videoDurationInput) <= 1)"
                          @click="adjustVideoDuration(-1)">−</button>
                        <button type="button" aria-label="增加 1 秒" aria-controls="video-duration"
                          :disabled="isSubmittingJob || (videoDurationInput !== '' && Number(videoDurationInput) >= 15)"
                          @click="adjustVideoDuration(1)">+</button>
                      </div>
                    </div>
                  </div>
                  <div class="spec-field-mini"><label for="video-resolution">视频清晰度（必选）</label>
                    <select id="video-resolution" v-model="canvas.video_resolution" required
                      :disabled="isSubmittingJob">
                      <option disabled value="">请选择清晰度</option>
                      <option v-for="resolution in videoResolutionOptions" :key="resolution" :value="resolution">{{
                        resolution }}</option>
                    </select>
                  </div>
                </div>
                <p v-if="videoSettingsReason" class="generation-help" role="status">{{ videoSettingsReason }}</p>
                <p class="generation-help">AI 会按当前模型与设置审理，说明必要的参数调整和图片处理。点击生成即采用审理结果，画布原图保留。修改内容、通道、模式或参数后需重新审理。</p>
                <button class="prepare-video-btn"
                  :disabled="!videoSourceNodes.length || !!videoSettingsReason || targetLoading || isPreparingVideo || isAgentResponding || isSubmittingJob || isConfirming"
                  @click="prepareVideo">{{ isPreparingVideo ? 'AI 正在审理…' : '1. AI审理方案' }}</button>
                <div v-if="videoReview" class="video-review-feedback" :class="videoReview.kind" role="status"
                  aria-live="polite">
                  <div class="review-heading">{{ videoReview.kind === 'loading' ? 'AI审理中' :
                    !videoReviewFresh ? '上次审理结果（内容、模型或设置已变化）' : 'AI审理结果' }}</div>
                  <div class="msg-content" v-html="renderMd(videoReview.content)"></div>
                </div>
                <div
                  v-if="project?.compiled_prompt && canvas.generation_source_ids.length && canvas.generation_review?.status === 'ready'"
                  class="video-prompt-preview">
                  <div class="prompt-status">{{ videoSelectionReady ? '方案已准备好，可直接生成' : '生成来源或参数已变化，请重新审理方案' }}</div>
                  <div class="prompt-settings">{{ project.current_spec.duration_seconds }} 秒 · {{
                    project.current_spec.aspect_ratio === 'adaptive' ? '随素材自适应' : project.current_spec.aspect_ratio }} ·
                    {{ canvas.generation_settings?.resolution || '清晰度未确认' }} · {{
                      generationModeLabel }}</div>
                  <small>生成使用审理结果中的最终参数。原始小框和上方输入保留；如需修改，请调整后重新审理。</small>
                </div>
                <button class="create-video-btn" :disabled="!!videoGenerationDisabledReason || isJobRunning"
                  :aria-describedby="videoGenerationDisabledReason ? 'video-generation-reason' : undefined"
                  @click="submitVideoJob">{{ isSubmittingJob ? '正在提交生成…' : isJobRunning ? '视频生成中…' : '2. 确认并生成视频'
                  }}</button>
                <p v-if="videoGenerationDisabledReason" id="video-generation-reason" class="generation-help"
                  role="status">{{ videoGenerationDisabledReason }}</p>
                <p v-if="videoSubmissionError" class="video-failure-detail" role="status">{{ videoSubmissionError }}</p>
                <div v-if="activeJob" class="active-job-strip">
                  <div class="progress-bar-bg">
                    <div class="progress-bar-inner" :class="{
                      indeterminate: isJobRunning,
                      succeeded: activeJob.status === 'succeeded',
                      failed: activeJob.status === 'failed' || activeJob.status === 'cancelled'
                    }"></div>
                  </div>
                  <span class="status-txt">{{
                    activeJob.status === 'succeeded' ? '生成完成' :
                      activeJob.status === 'failed' ? '视频生成失败' :
                        activeJob.status === 'cancelled' ? '任务已取消' :
                          '生成中…（厂商未提供进度）'
                  }}</span>
                  <p v-if="activeJob.error?.message" class="video-failure-detail">{{ activeJob.error.message }}</p>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </Transition>
    </div>

    <PortraitMaterialNotice :open="portraitNoticeOpen" @close="portraitNoticeOpen = false" />
    <Teleport to="body">
      <div v-if="portraitFailure" class="portrait-failure-mask" @click.self="portraitFailure = null" @keydown.esc.prevent="portraitFailure = null" @keydown.tab.prevent="portraitClose?.focus()">
        <section class="portrait-failure-dialog" role="alertdialog" aria-modal="true" aria-labelledby="portrait-failure-title" aria-describedby="portrait-failure-description">
          <h3 id="portrait-failure-title">人像图片未通过生成要求</h3>
          <p id="portrait-failure-description">{{ portraitFailureMessage }}</p>
          <p v-if="portraitFailure.message" class="portrait-vendor-detail">{{ portraitFailure.message }}</p>
          <button ref="portraitClose" @click="portraitFailure = null">知道了</button>
        </section>
      </div>
    </Teleport>

    <!-- ================= 国际传播指引弹窗（多选 & 后端负面提示词合并） ================= -->
    <div v-if="showGuideModal" class="guide-modal-mask" @click.self="closeGuideModal">
      <div class="guide-modal-box">
        <div class="guide-modal-header">
          <div class="modal-title-group">
            <span class="modal-badge">CULTURAL GUIDANCE</span>
            <h3 class="modal-title">国际传播叙事指引与受众偏好</h3>
            <p class="modal-sub-desc">请选择目标传播国家/地区（支持多选），系统将自动从后端读取并组合对应的负面提示词</p>
          </div>
          <button class="cancel-action-btn" @click="closeGuideModal">算了</button>
        </div>

        <!-- 加载状态 / 错误状态 / 纯国家名称多选按钮组 -->
        <div v-if="isLoadingCountries" class="countries-status-tip">正在从服务端加载国家配置…</div>
        <div v-else-if="countriesLoadError" class="countries-status-tip error">
          <span>{{ countriesLoadError }}</span>
          <button type="button" class="retry-inline-btn" @click="fetchCountryNegativePrompts">重试</button>
        </div>
        <div v-else-if="!countryList.length" class="countries-status-tip">暂无国家配置，请联系后端管理员初始化数据库</div>
        <div v-else class="countries-multi-grid">
          <button
            v-for="country in countryList"
            :key="country.code"
            type="button"
            class="country-select-pill"
            :class="{ active: selectedCountryCodes.includes(country.code) }"
            @click="toggleCountry(country.code)"
          >
            <span>{{ country.name }}</span>
            <span v-if="selectedCountryCodes.includes(country.code)" class="check-mark">✓</span>
          </button>
        </div>

        <!-- 选中国家的详情与合并后的负面提示词预览 -->
        <div class="guidance-content-box">
          <div class="guidance-header">
            <h4 class="country-target-name">
              {{ selectedCountries.length ? `已选：${selectedCountries.map(c => c.name).join('、')}` : '请至少选择一个国家/地区' }}
            </h4>
            <span class="lang-pill" v-if="selectedCountries.length">已选 {{ selectedCountries.length }} 项</span>
          </div>

          <div v-if="selectedCountries.some(c => c.taboo)" class="guidance-detail-card">
            <template v-for="item in selectedCountries" :key="item.code">
              <div v-if="item.taboo" class="guide-block highlight-block">
                <span class="block-label">{{ item.name }} · 文化禁忌与规避：</span>
                <p class="block-desc">{{ item.taboo }}</p>
              </div>
            </template>
          </div>

          <!-- 最终合并生成的负面提示词预览 -->
          <div class="prompt-snippet-box">
            <div class="snippet-label">待注入节点的合并负面提示词（Negative Prompt）：</div>
            <div class="snippet-text">
              {{ combinedNegativePrompt || '未选择国家，暂无负面提示词' }}
            </div>
          </div>
        </div>

        <div class="guide-modal-footer">
          <span class="footer-tip desktop-only">点击右侧按钮将合并后的负面提示词直接写入当前文本节点</span>
          <button
            class="apply-to-chat-btn"
            :disabled="!selectedCountryCodes.length || !combinedNegativePrompt"
            @click="applyGuidanceToNode"
          >
            注入文本节点
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue';
import { useWorkspace, newId } from '@/composables/useWorkspace';
import PortraitMaterialNotice from '@/components/PortraitMaterialNotice.vue';
import ImageGenerationPanel from '@/components/ImageGenerationPanel.vue';
import { collaborationReferenceIds, portraitFailureMessage } from '@/services/workspaceFeedback';
import { createImageNode } from '@/services/imageGeneration';
import type { ImageJob } from '@/types/imageGeneration';
import type { FlowNode, FlowConnection } from '@/types/canvas';
import { renderMd } from '@/utils/markdown';
import { generationContextMatches, generationMatches, generationSources, videoDurationChoices, videoGenerationBlockReason, videoSettingsBlockReason } from '@/services/generationState';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();

function goToEditor() {
  router.push('/editor');
}

const workspace = useWorkspace();
const {
  canvas, nodes, connections, pan, zoom, conversations, currentConvId, accountId, messages, inputContent,
  project, apiConfigs, selectedApiConfigId, isSubmittingJob, isConfirming, isAgentResponding,
  selectedGenerationTarget, targetLoading, targetError,
  isCreatingConv, isAgentDrawerOpen, referencedNodeIds, aiTargetNodeId, activeJob, portraitFailure, videoSubmissionError,
  generationReady, isPreparingVideo, videoReview, initialized, loading, notice, saveState, saveLabel, uploading,
  switchConversation, createNewConversation, backToProjectSpace, retrySave, resolveConflict,
  restoreBeforeAi, handleLogout,
} = workspace;

const viewportRef = ref<HTMLElement | null>(null);
const messagesContainerRef = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const portraitNoticeOpen = ref(false);
watch(currentConvId, () => { portraitNoticeOpen.value = false; });
const portraitClose = ref<HTMLButtonElement | null>(null);
let portraitPreviousFocus: HTMLElement | null = null;
watch(portraitFailure, async value => {
  if (value) { portraitPreviousFocus = document.activeElement as HTMLElement; await nextTick(); portraitClose.value?.focus(); }
  else if (portraitPreviousFocus?.isConnected) portraitPreviousFocus.focus();
});

// ==================== 1. 项目卡片重命名功能（左下角改名按钮） ====================
const renamingConvId = ref('');
const renamingConvTitle = ref('');
// 本地持久化项目自定义名称映射，确保即使后端未提供 PATCH 改名接口也能持久生效
const customConvTitles = reactive<Record<string, string>>(
  JSON.parse(localStorage.getItem('custom_conv_titles') || '{}')
);

function getConvDisplayTitle(conv: { id: string; title?: string | null }) {
  return customConvTitles[conv.id] || conv.title || '新创作对话';
}

function startRenameConv(conv: { id: string; title?: string | null }) {
  renamingConvId.value = conv.id;
  renamingConvTitle.value = getConvDisplayTitle(conv);
}

function cancelRenameConv() {
  renamingConvId.value = '';
  renamingConvTitle.value = '';
}

async function finishRenameConv(conv: { id: string; title?: string | null }) {
  if (renamingConvId.value !== conv.id) return;
  const trimmed = renamingConvTitle.value.trim();
  renamingConvId.value = '';
  if (!trimmed) return;

  // 1. 立即更新前端状态与本地持久化存储
  conv.title = trimmed;
  customConvTitles[conv.id] = trimmed;
  localStorage.setItem('custom_conv_titles', JSON.stringify(customConvTitles));

  // 2. 如果 useWorkspace 提供了 renameConversation / updateConversation 则调用，否则尝试 PATCH 后端接口
  try {
    if (typeof (workspace as any).renameConversation === 'function') {
      await (workspace as any).renameConversation(conv.id, trimmed);
    } else {
      await fetch(`/api/v1/conversations/${encodeURIComponent(conv.id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ title: trimmed })
      }).catch(() => {});
    }
  } catch {
    // 本地已保存，忽略后端未实现该路由时的错误
  }
}

// ==================== 2. 节点重命名修复 & 初始/新增节点命名规则 ====================
// 使用独立 ref 管理正在重命名的节点，避免输入第一个字符触发自动保存重绘时丢失 isRenaming 状态
const renamingNodeId = ref('');
const renamingNodeTitle = ref('');

function startRenameNode(node: FlowNode) {
  if (loading.value) return;
  renamingNodeId.value = node.id;
  renamingNodeTitle.value = node.title || '';
}

function finishRenameNode(node: FlowNode) {
  if (renamingNodeId.value !== node.id) return;
  const nextTitle = renamingNodeTitle.value.trim();
  if (nextTitle) {
    node.title = nextTitle;
  }
  renamingNodeId.value = '';
  renamingNodeTitle.value = '';
}

function cancelRenameNode() {
  renamingNodeId.value = '';
  renamingNodeTitle.value = '';
}

// 将初始默认节点的名字统一设为“文本节点”与“图片节点”
function normalizeInitialNodeTitles() {
  const legacyTextDefaults = new Set(['视频脚本', '视频脚本1', '分镜脚本']);
  const legacyImageDefaults = new Set(['参考图', '参考图1', '首帧图']);

  const textNodes = nodes.value.filter(n => n.type === 'text');
  const imageNodes = nodes.value.filter(n => n.type === 'image');

  // 将初始的第一个默认文本节点名称规范为“文本节点”
  if (textNodes.length > 0 && legacyTextDefaults.has(textNodes[0].title)) {
    textNodes[0].title = '文本节点';
  }
  // 将初始的第一个默认图片节点名称规范为“图片节点”
  if (imageNodes.length > 0 && legacyImageDefaults.has(imageNodes[0].title)) {
    imageNodes[0].title = '图片节点';
  }
}

watch(
  () => [currentConvId.value, nodes.value.length],
  () => {
    normalizeInitialNodeTitles();
  },
  { immediate: true }
);

// 计算新增节点的递增名称：
// 初始节点名为“文本节点”/“图片节点”；后续每次新增依次为“文本节点1”、“文本节点2” / “图片节点1”、“图片节点2”
function getNextNodeTitle(type: 'text' | 'image'): string {
  const baseName = type === 'text' ? '文本节点' : '图片节点';
  const sameTypeNodes = nodes.value.filter(n => n.type === type);

  // 如果画布上还没有该类型节点，作为初始节点直接命名为“文本节点”或“图片节点”
  if (sameTypeNodes.length === 0) {
    return baseName;
  }

  // 找出当前已占用的编号（如 文本节点1, 文本节点2...）
  const usedNumbers = new Set<number>();
  const regex = new RegExp(`^${baseName}\\s*(\\d+)$`);
  for (const n of sameTypeNodes) {
    const match = (n.title || '').trim().match(regex);
    if (match) {
      usedNumbers.add(Number(match[1]));
    }
  }

  let nextNum = 1;
  while (usedNumbers.has(nextNum)) {
    nextNum++;
  }
  return `${baseName}${nextNum}`;
}

const agentTab = ref<'chat' | 'image' | 'video'>('chat');
const isAgentExpanded = ref(false);
const activeNodeId = ref('');
const imageGenerationOpen = computed(() => isAgentDrawerOpen.value && agentTab.value === 'image');
const imageSourceNodeId = ref('');

function openImageGeneration(node?: FlowNode) {
  if (loading.value || !currentConvId.value) return;
  imageSourceNodeId.value = node?.id || '';
  agentTab.value = 'image';
  isAgentDrawerOpen.value = true;
}

function insertGeneratedImage(job: ImageJob) {
  if (loading.value || job.conversation_id !== currentConvId.value) return;
  const source = nodes.value.find(n => n.id === imageSourceNodeId.value);
  const nextTitle = getNextNodeTitle('image');
  const node = createImageNode(nodes.value, job, newId(), source);
  if (!node) return;
  node.title = nextTitle;
  nodes.value.push(node);
  activeNodeId.value = node.id;
  notice.value = '图片已插入画布，可用作参考图或首帧。';
}

watch(currentConvId, () => { imageSourceNodeId.value = ''; });
const editingNodeId = ref('');
const nodeEditors = new Map<string, HTMLTextAreaElement>();

function setNodeEditor(id: string, element: unknown) {
  if (element instanceof HTMLTextAreaElement) nodeEditors.set(id, element);
  else nodeEditors.delete(id);
}

function beginNodeEditing(node: FlowNode) {
  if (loading.value) return;
  editingNodeId.value = node.id;
  activeNodeId.value = node.id;
  nextTick(() => nodeEditors.get(node.id)?.focus({ preventScroll: true }));
}

function finishNodeEditing() { editingNodeId.value = ''; }

const activeNode = computed(() => nodes.value.find(n => n.id === activeNodeId.value));
const selectedNodeIds = ref<string[]>([]);
const aiTargetNode = computed(() => nodes.value.find(n => n.id === aiTargetNodeId.value));
const canApplyAiContent = computed(() => !!aiTargetNode.value?.pending_ai && aiTargetNode.value.pending_ai.source_model !== 'local-preview');

const videoSourceIds = computed(() => {
  const selection = [...new Set([...selectedNodeIds.value, activeNodeId.value].filter(Boolean))]
    .filter(id => nodes.value.some(n => n.id === id));
  if (selection.length) return selection;
  if (aiTargetNode.value) return [aiTargetNode.value.id];
  return canvas.value.generation_source_ids.filter(id => nodes.value.some(n => n.id === id));
});

const videoSourceNodes = computed(() => nodes.value.filter(n => videoSourceIds.value.includes(n.id)));
const videoImageNodes = computed(() => generationSources(canvas.value, videoSourceIds.value).filter(n => n.type === 'image' && n.asset_id));

const videoDurationInput = computed({
  get: () => canvas.value.video_duration_seconds ?? '',
  set: (value: string | number) => { canvas.value.video_duration_seconds = value === '' ? null : Number(value); },
});

function adjustVideoDuration(delta: number) {
  const value = Number(videoDurationInput.value);
  videoDurationInput.value = videoDurationInput.value === '' || !Number.isFinite(value)
    ? 1
    : Math.max(1, Math.min(15, delta > 0 ? Math.floor(value) + 1 : Math.ceil(value) - 1));
}

const videoDurationOptions = computed(() => videoDurationChoices(selectedGenerationTarget.value));
const videoResolutionOptions = computed(() => {
  const resolutions = selectedGenerationTarget.value?.profile?.resolutions;
  return resolutions?.length ? resolutions.filter(value => ['480p', '720p', '1080p'].includes(value)) : ['480p', '720p', '1080p'];
});

const videoModeHelp = computed(() => {
  const adaptive = selectedGenerationTarget.value?.profile?.image_constraints;
  return ({
    auto: '无图片使用文生，一张图片作为首帧，多张图片作为参考图。',
    text_to_video: '根据文字创作视频，不使用图片。',
    first_frame_to_video: '图片作为视频起始画面。' + (adaptive ? '画幅跟随处理后的首帧图片。' : ''),
    reference_image_to_video: '参考图片中的主体或风格，不要求视频从该图片开始。',
    first_last_frame_to_video: '指定起始和结束画面。' + (selectedGenerationTarget.value?.profile?.allows_identical_frames ? '可以使用同一张图片作为首尾帧。' : ''),
  }[canvas.value.video_mode] || '请选择生成模式。');
});

const videoSettingsReason = computed(() => videoSettingsBlockReason(canvas.value, selectedGenerationTarget.value));
const videoSelectionReady = computed(() => generationReady.value && !!project.value
  && generationMatches(canvas.value, project.value.current_spec_version, videoSourceIds.value, selectedGenerationTarget.value?.fingerprint));
const videoReviewFresh = computed(() => !!project.value && !!selectedGenerationTarget.value && !targetLoading.value
  && generationContextMatches(canvas.value, project.value.current_spec_version, videoSourceIds.value, selectedGenerationTarget.value.fingerprint));

const isJobRunning = computed(() =>
  !!activeJob.value && !['succeeded', 'failed', 'cancelled'].includes(activeJob.value.status)
);

const videoGenerationDisabledReason = computed(() => {
  if (isJobRunning.value) return '当前视频正在生成中，请等待完成后再提交';
  return videoGenerationBlockReason(
    canvas.value, project.value?.current_spec_version || 0, videoSourceIds.value, {
    compiledPrompt: !!project.value?.compiled_prompt, preparing: isPreparingVideo.value,
    submitting: isSubmittingJob.value, collaborating: isAgentResponding.value,
    confirming: isConfirming.value, channel: selectedApiConfigId.value, saveStatus: saveState.value.status,
    targetFingerprint: selectedGenerationTarget.value?.fingerprint, targetLoading: targetLoading.value, targetError: targetError.value,
    reviewError: videoReview.value?.kind === 'error',
    target: selectedGenerationTarget.value,
  });
});

const generationModeLabel = computed(() => ({
  text_to_video: '文本生成', first_frame_to_video: '所选或关联图片作为首帧',
  first_last_frame_to_video: '首帧与尾帧生成',
  reference_image_to_video: '多张图片作为参考素材',
}[project.value?.current_spec.mode || 'text_to_video'] || project.value?.current_spec.mode));

const isSelecting = ref(false);
const isPanning = ref(false);
const startPan = reactive({ x: 0, y: 0 });
const startSelectPos = reactive({ x: 0, y: 0 });
const selectionBox = reactive({ visible: false, x: 0, y: 0, w: 0, h: 0 });
const contextMenu = reactive({ visible: false, x: 0, y: 0, canvasX: 0, canvasY: 0 });
const connectingSource = ref<FlowNode | null>(null);
const tempMousePos = reactive({ x: 0, y: 0 });
let draggingNode: FlowNode | null = null;
const isDraggingOverAgent = ref(false);
// 支持记录单个或多个被删除的节点及其连线，方便一键撤销
const deletedNode = ref<{ nodes: FlowNode[]; connections: FlowConnection[] } | null>(null);

const vAutofocus = {
  mounted: (element: HTMLInputElement) => {
    element.focus({ preventScroll: true });
    element.select();
  }
};

const referencedNodes = computed(() => {
  const fallback = referencedNodeIds.value.length ? referencedNodeIds.value : [...selectedNodeIds.value, activeNodeId.value];
  const ids = collaborationReferenceIds(nodes.value, fallback, [...selectedNodeIds.value, activeNodeId.value], aiTargetNodeId.value);
  return nodes.value.filter(n => ids.includes(n.id));
});

function clearReferencedNodes() { referencedNodeIds.value = []; selectedNodeIds.value = []; activeNodeId.value = ''; }

function handleNodeDragStart(e: DragEvent, node: FlowNode) {
  draggingNode = null;
  const ids = selectedNodeIds.value.includes(node.id) ? selectedNodeIds.value : [node.id];
  e.dataTransfer?.setData('application/json', JSON.stringify(ids));
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy';
}

function handleAgentDragOver(_e: DragEvent) { isDraggingOverAgent.value = true; }
function handleAgentDragLeave() { isDraggingOverAgent.value = false; }
function handleAgentDrop(e: DragEvent) {
  isDraggingOverAgent.value = false;
  try {
    const ids = JSON.parse(e.dataTransfer?.getData('application/json') || '[]');
    if (!Array.isArray(ids)) return;
    referencedNodeIds.value = ids.filter(id => nodes.value.some(node => node.id === id));
    isAgentDrawerOpen.value = true;
  } catch { notice.value = '无法识别参考节点，请重新拖入'; }
}

function canvasPoint(e: { clientX: number; clientY: number }) {
  const rect = viewportRef.value?.getBoundingClientRect();
  return {
    x: (e.clientX - (rect?.left || 0) - pan.value.x) / zoom.value,
    y: (e.clientY - (rect?.top || 0) - pan.value.y) / zoom.value
  };
}

watch(currentConvId, () => {
  editingNodeId.value = '';
  renamingNodeId.value = '';
  renamingNodeTitle.value = '';
  activeNodeId.value = ''; selectedNodeIds.value = []; connectingSource.value = null;
  contextMenu.visible = false; deletedNode.value = null; handleCanvasMouseUp();
});
watch(() => messages.value.length, scrollToBottom);
watch(() => aiTargetNode.value?.pending_ai?.message_id, scrollToBottom);
watch(agentTab, tab => { if (tab === 'chat') scrollToBottom(); });

// ==================== 3. 国际传播文化配置（对接后端接口 & 支持增改） ====================
export interface CountryGuideItem {
  id?: string | number;
  code: string;
  name: string;
  negative_prompt: string;
  taboo?: string;
  sort_order?: number;
}

const CULTURAL_API_BASE = '/api/v1/cultural-guidances';
const showGuideModal = ref(false);
const countryList = ref<CountryGuideItem[]>([]);
const selectedCountryCodes = ref<string[]>([]);
const isLoadingCountries = ref(false);
const countriesLoadError = ref('');

async function fetchCountryNegativePrompts() {
  isLoadingCountries.value = true;
  countriesLoadError.value = '';
  try {
    const res = await fetch(CULTURAL_API_BASE, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      credentials: 'include'
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const list: any[] = Array.isArray(data) ? data : (data.items || data.data || []);
    countryList.value = list.map(item => ({
      id: item.id,
      code: String(item.code || ''),
      name: String(item.name || ''),
      negative_prompt: String(item.negative_prompt ?? item.negativePrompt ?? ''),
      taboo: item.taboo ? String(item.taboo) : undefined,
      sort_order: item.sort_order
    }));
  } catch (err: any) {
    countriesLoadError.value = '加载国家负面提示词失败，请检查后端接口是否已启动';
    console.error('fetchCountryNegativePrompts error:', err);
  } finally {
    isLoadingCountries.value = false;
  }
}

async function createCountryGuidance(payload: {
  code: string;
  name: string;
  negative_prompt: string;
  taboo?: string;
  sort_order?: number;
}) {
  const res = await fetch(CULTURAL_API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`新增国家配置失败: HTTP ${res.status}`);
  const created = await res.json();
  await fetchCountryNegativePrompts();
  return created;
}

async function updateCountryGuidance(
  code: string,
  payload: Partial<{ name: string; negative_prompt: string; taboo: string; sort_order: number }>
) {
  const res = await fetch(`${CULTURAL_API_BASE}/${encodeURIComponent(code)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`修改国家配置失败: HTTP ${res.status}`);
  const updated = await res.json();
  await fetchCountryNegativePrompts();
  return updated;
}

defineExpose({
  fetchCountryNegativePrompts,
  createCountryGuidance,
  updateCountryGuidance
});

function toggleCountry(code: string) {
  const idx = selectedCountryCodes.value.indexOf(code);
  if (idx > -1) {
    selectedCountryCodes.value.splice(idx, 1);
  } else {
    selectedCountryCodes.value.push(code);
  }
}

const selectedCountries = computed(() =>
  countryList.value.filter(c => selectedCountryCodes.value.includes(c.code))
);

const combinedNegativePrompt = computed(() =>
  selectedCountries.value.map(c => c.negative_prompt).join('')
);

function applyGuidanceToNode() {
  const promptText = combinedNegativePrompt.value;
  if (!promptText) return;

  if (activeNode.value && activeNode.value.type === 'text') {
    activeNode.value.content = activeNode.value.content
      ? `${activeNode.value.content}\n${promptText}`
      : promptText;
  } else {
    const emptyTextNode = nodes.value.find(n => n.type === 'text' && !n.content?.trim());
    if (emptyTextNode) {
      emptyTextNode.content = promptText;
      activeNodeId.value = emptyTextNode.id;
    } else {
      const newNodeId = newId();
      nodes.value.push({
        id: newNodeId,
        type: 'text',
        title: getNextNodeTitle('text'),
        x: 180,
        y: 220,
        content: promptText
      });
      activeNodeId.value = newNodeId;
    }
  }
  closeGuideModal();
}

function openGuideModal() {
  if (!countryList.value.length && !isLoadingCountries.value) {
    void fetchCountryNegativePrompts();
  }
  showGuideModal.value = true;
}

function closeGuideModal() {
  showGuideModal.value = false;
}

function checkAndOpenGuideForNewConv(convId: string) {
  if (!convId) return;
  const storageKey = `guide_shown_${convId}`;
  if (!localStorage.getItem(storageKey)) {
    localStorage.setItem(storageKey, '1');
    selectedCountryCodes.value = [];
    openGuideModal();
  }
}

async function handleCreateNewConversation() {
  await createNewConversation();
  normalizeInitialNodeTitles();
  if (currentConvId.value) {
    checkAndOpenGuideForNewConv(currentConvId.value);
  }
}

const activeConversation = computed(() => conversations.value.find(c => c.id === currentConvId.value));

// ==================== 4. 看板卡片配色 ====================
const cardThemes = [
  { border: 'rgba(99, 102, 241, 0.5)', bg: 'linear-gradient(145deg, rgba(99, 102, 241, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(99, 102, 241, 0.35)' },
  { border: 'rgba(14, 165, 233, 0.5)', bg: 'linear-gradient(145deg, rgba(14, 165, 233, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(14, 165, 233, 0.35)' },
  { border: 'rgba(16, 185, 129, 0.5)', bg: 'linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(16, 185, 129, 0.35)' },
  { border: 'rgba(244, 63, 94, 0.5)', bg: 'linear-gradient(145deg, rgba(244, 63, 94, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(244, 63, 94, 0.35)' },
  { border: 'rgba(245, 158, 11, 0.5)', bg: 'linear-gradient(145deg, rgba(245, 158, 11, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(245, 158, 11, 0.35)' },
  { border: 'rgba(168, 85, 247, 0.5)', bg: 'linear-gradient(145deg, rgba(168, 85, 247, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(168, 85, 247, 0.35)' },
  { border: 'rgba(20, 184, 166, 0.5)', bg: 'linear-gradient(145deg, rgba(20, 184, 166, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(20, 184, 166, 0.35)' },
];

function getCardColorStyle(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash << 5) - hash + id.charCodeAt(i);
    hash |= 0;
  }
  const themeIndex = Math.abs(hash) % cardThemes.length;
  const theme = cardThemes[themeIndex];
  return {
    borderColor: theme.border,
    background: theme.bg,
    boxShadow: `0 10px 25px -5px ${theme.glow}`
  };
}

function resetCanvasView() { pan.value.x = 100; pan.value.y = 100; zoom.value = 1; }
async function handleDeleteConversation(id: string) {
  if (confirm('确定删除这个创作项目吗？')) await workspace.deleteConversation(id);
}

const pressedArrowKeys = new Set<string>();
let keyPanRafId: number | null = null;

function isEditableTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  return (
    el.tagName === 'INPUT' ||
    el.tagName === 'TEXTAREA' ||
    el.tagName === 'SELECT' ||
    el.isContentEditable
  );
}

function updateKeyPanLoop() {
  if (!currentConvId.value || loading.value || pressedArrowKeys.size === 0) {
    keyPanRafId = null;
    return;
  }
  const speed = 14;
  if (pressedArrowKeys.has('ArrowLeft')) pan.value.x += speed;
  if (pressedArrowKeys.has('ArrowRight')) pan.value.x -= speed;
  if (pressedArrowKeys.has('ArrowUp')) pan.value.y += speed;
  if (pressedArrowKeys.has('ArrowDown')) pan.value.y -= speed;

  keyPanRafId = requestAnimationFrame(updateKeyPanLoop);
}

function stopKeyPan() {
  pressedArrowKeys.clear();
  if (keyPanRafId !== null) {
    cancelAnimationFrame(keyPanRafId);
    keyPanRafId = null;
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    connectingSource.value = null;
    contextMenu.visible = false;
    handleCanvasMouseUp();
    stopKeyPan();
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault();
    void retrySave();
    return;
  }

  if (!currentConvId.value || loading.value) return;
  // 如果当前焦点在输入框、文本框或正在重命名节点/项目，不触发画布快捷键
  if (isEditableTarget(event.target) || editingNodeId.value || renamingNodeId.value || renamingConvId.value) return;

  // 按下 Delete 键（如需同时支持 Mac 退格键可加上 || event.key === 'Backspace'）：删除当前选中的单/多个节点
  if (event.key === 'Delete') {
    const idsToDelete = [...new Set([...selectedNodeIds.value, activeNodeId.value].filter(Boolean))];
    if (idsToDelete.length > 0) {
      event.preventDefault();
      deleteSelectedNodes(idsToDelete);
    }
    return;
  }

  if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
    event.preventDefault();
    pressedArrowKeys.add(event.key);
    if (keyPanRafId === null) {
      keyPanRafId = requestAnimationFrame(updateKeyPanLoop);
    }
  }
}

function handleKeyup(event: KeyboardEvent) {
  if (pressedArrowKeys.has(event.key)) {
    pressedArrowKeys.delete(event.key);
    if (pressedArrowKeys.size === 0 && keyPanRafId !== null) {
      cancelAnimationFrame(keyPanRafId);
      keyPanRafId = null;
    }
  }
}

onMounted(async () => {
  window.addEventListener('mousemove', handleCanvasMouseMove);
  window.addEventListener('mouseup', handleCanvasMouseUp);
  window.addEventListener('keydown', handleKeydown);
  window.addEventListener('keyup', handleKeyup);
  window.addEventListener('blur', stopKeyPan);

  void fetchCountryNegativePrompts();

  const queryConvId = route.query.conv_id as string;
  if (queryConvId) {
    await switchConversation(queryConvId);
    normalizeInitialNodeTitles();
  } else if (!currentConvId.value) {
    if (conversations.value.length > 0) {
      await switchConversation(conversations.value[0].id);
      normalizeInitialNodeTitles();
    } else {
      await handleCreateNewConversation();
    }
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', handleCanvasMouseMove);
  window.removeEventListener('mouseup', handleCanvasMouseUp);
  window.removeEventListener('keydown', handleKeydown);
  window.removeEventListener('keyup', handleKeyup);
  window.removeEventListener('blur', stopKeyPan);
  stopKeyPan();
});

// ==================== 5. 画布拖拽、缩放与连线交互 ====================
function handlePortClick(node: FlowNode, portType: 'in' | 'out') {
  if (!connectingSource.value) {
    if (portType !== 'out') return;
    connectingSource.value = node;
    const p = getNodePortPos(node, 'out');
    tempMousePos.x = p.x;
    tempMousePos.y = p.y;
    return;
  }

  if (portType === 'out') { connectingSource.value = node; return; }
  if (connectingSource.value.id !== node.id) {
    const fromId = connectingSource.value.id;
    const toId = node.id;

    const isExist = connections.value.some(
      c => c.from === fromId && c.to === toId
    );

    if (!isExist) {
      connections.value.push({
        id: newId(),
        from: fromId,
        to: toId
      });
    }
  }

  connectingSource.value = null;
}

function handleCanvasMouseMove(e: MouseEvent) {
  if (isPanning.value) {
    pan.value.x = e.clientX - startPan.x;
    pan.value.y = e.clientY - startPan.y;
  } else if (draggingNode) {
    const { x: currentCanvasX, y: currentCanvasY } = canvasPoint(e);
    const deltaX = currentCanvasX - mouseStartCanvasPos.x;
    const deltaY = currentCanvasY - mouseStartCanvasPos.y;

    const allSelectedIds = new Set([...selectedNodeIds.value, activeNodeId.value].filter(Boolean));
    nodes.value.forEach(n => {
      if (allSelectedIds.has(n.id) && dragStartNodePos[n.id]) {
        n.x = dragStartNodePos[n.id].x + deltaX;
        n.y = dragStartNodePos[n.id].y + deltaY;
      }
    });
  } else if (connectingSource.value) {
    Object.assign(tempMousePos, canvasPoint(e));
  } else if (isSelecting.value) {
    const { x: curX, y: curY } = canvasPoint(e);

    const boxX = Math.min(startSelectPos.x, curX);
    const boxY = Math.min(startSelectPos.y, curY);
    const boxW = Math.abs(curX - startSelectPos.x);
    const boxH = Math.abs(curY - startSelectPos.y);

    selectionBox.x = boxX;
    selectionBox.y = boxY;
    selectionBox.w = boxW;
    selectionBox.h = boxH;

    selectedNodeIds.value = nodes.value
      .filter(node => {
        const nodeW = 248;
        const nodeH = node.type === 'image' ? 280 : node.type === 'text' ? 300 : 240;
        return (
          boxX < node.x + nodeW &&
          boxX + boxW > node.x &&
          boxY < node.y + nodeH &&
          boxY + boxH > node.y
        );
      })
      .map(n => n.id);
  }
}

function handleCanvasMouseDown(e: MouseEvent) {
  if (loading.value || (e.target as HTMLElement).closest('button,input,textarea,select,.floating-top-left,.floating-left-bar,.floating-bottom-right')) return;
  if (contextMenu.visible) {
    contextMenu.visible = false;
    return;
  }

  activeNodeId.value = '';
  selectedNodeIds.value = [];

  if (connectingSource.value) {
    connectingSource.value = null;
    return;
  }

  if (e.button === 0) {
    isSelecting.value = true;
    const { x: canvasMouseX, y: canvasMouseY } = canvasPoint(e);

    startSelectPos.x = canvasMouseX;
    startSelectPos.y = canvasMouseY;

    selectionBox.x = canvasMouseX;
    selectionBox.y = canvasMouseY;
    selectionBox.w = 0;
    selectionBox.h = 0;
    selectionBox.visible = true;
  } else if (e.button === 1) {
    isPanning.value = true;
    startPan.x = e.clientX - pan.value.x;
    startPan.y = e.clientY - pan.value.y;
  }
}

function handleCanvasMouseUp() {
  isPanning.value = false;
  draggingNode = null;
  isSelecting.value = false;
  selectionBox.visible = false;
}

function handleCanvasZoom(e: WheelEvent) {
  if ((e.target as HTMLElement).closest('textarea,input,select,video,.agent-flyout-drawer')) return;
  e.preventDefault();
  const point = canvasPoint(e);
  const next = Math.min(Math.max(zoom.value * (e.deltaY < 0 ? 1.08 : 0.92), 0.4), 2.2);
  pan.value.x += point.x * (zoom.value - next); pan.value.y += point.y * (zoom.value - next); zoom.value = next;
}

function openContextMenu(e: MouseEvent) {
  if ((e.target as HTMLElement).closest('textarea,input,video,.agent-flyout-drawer')) return;
  e.preventDefault();
  const rect = viewportRef.value?.getBoundingClientRect();
  const point = canvasPoint(e);
  contextMenu.visible = true;
  contextMenu.x = Math.min(e.clientX - (rect?.left || 0), Math.max(0, (rect?.width || 800) - 230));
  contextMenu.y = Math.min(e.clientY - (rect?.top || 0), Math.max(0, (rect?.height || 600) - 180));
  contextMenu.canvasX = point.x; contextMenu.canvasY = point.y;
}

function addNode(type: 'text' | 'image') {
  contextMenu.canvasX = 160 + nodes.value.length * 35;
  contextMenu.canvasY = 160 + nodes.value.length * 35;
  createNodeFromContext(type);
}

// 创建新节点时自动使用递增名称：文本节点1、文本节点2 / 图片节点1、图片节点2
function createNodeFromContext(type: 'text' | 'image') {
  const id = newId();
  const newNode: FlowNode = {
    id,
    type,
    title: getNextNodeTitle(type),
    x: contextMenu.canvasX,
    y: contextMenu.canvasY,
    content: type === 'text' ? '' : undefined,
    url: type === 'image' ? '' : undefined
  };
  nodes.value.push(newNode);
  activeNodeId.value = id;
  contextMenu.visible = false;
}

// 删除单个节点（点击节点右上角 ✕ 按钮时调用）
function deleteNode(id: string) {
  deleteSelectedNodes([id]);
}

// 批量或单个删除选中节点（按 Delete 快捷键或点击 ✕ 时调用）
function deleteSelectedNodes(ids: string[]) {
  const targetIds = new Set(ids);
  const targetNodes = nodes.value.filter(n => targetIds.has(n.id));
  if (!targetNodes.length) return;

  const removedConnections = connections.value.filter(
    c => targetIds.has(c.from) || targetIds.has(c.to)
  );

  deletedNode.value = {
    nodes: JSON.parse(JSON.stringify(targetNodes)),
    connections: JSON.parse(JSON.stringify(removedConnections))
  };

  for (const node of targetNodes) {
    if (node.job_id && !canvas.value.dismissed_job_ids.includes(node.job_id)) {
      canvas.value.dismissed_job_ids.push(node.job_id);
    }
  }

  nodes.value = nodes.value.filter(n => !targetIds.has(n.id));
  connections.value = connections.value.filter(c => !targetIds.has(c.from) && !targetIds.has(c.to));
  referencedNodeIds.value = referencedNodeIds.value.filter(id => !targetIds.has(id));
  selectedNodeIds.value = selectedNodeIds.value.filter(id => !targetIds.has(id));

  if (targetIds.has(activeNodeId.value)) activeNodeId.value = '';
  if (targetIds.has(aiTargetNodeId.value)) aiTargetNodeId.value = '';
  if ( targetIds.has(editingNodeId.value)) editingNodeId.value = '';
  if (connectingSource.value && targetIds.has(connectingSource.value.id)) {
    connectingSource.value = null;
  }

  notice.value = targetNodes.length > 1
    ? `已删除 ${targetNodes.length} 个小框，可以撤销。`
    : '小框已删除，可以撤销。';
}

// 撤销删除（恢复刚才删除的单个或多个节点及其连线）
function undoDeleteNode() {
  const removed = deletedNode.value;
  if (!removed || !removed.nodes.length) return;

  const existingNodeIds = new Set(nodes.value.map(n => n.id));
  const nodesToRestore = removed.nodes.filter(n => !existingNodeIds.has(n.id));
  if (!nodesToRestore.length) return;

  nodes.value.push(...nodesToRestore);

  const restoredJobs = new Set(nodesToRestore.map(n => n.job_id).filter(Boolean));
  if (restoredJobs.size > 0) {
    canvas.value.dismissed_job_ids = canvas.value.dismissed_job_ids.filter(id => !restoredJobs.has(id));
  }

  const allNodeIds = new Set(nodes.value.map(n => n.id));
  const existingConnIds = new Set(connections.value.map(c => c.id));
  for (const conn of removed.connections) {
    if (!existingConnIds.has(conn.id) && allNodeIds.has(conn.from) && allNodeIds.has(conn.to)) {
      connections.value.push(conn);
    }
  }

  selectedNodeIds.value = nodesToRestore.map(n => n.id);
  activeNodeId.value = nodesToRestore[nodesToRestore.length - 1].id;
  deletedNode.value = null;
  notice.value = '已恢复删除的小框。';
}
function deleteConnection(id: string) { connections.value = connections.value.filter(c => c.id !== id); }

function selectNode(node: FlowNode, event: MouseEvent) {
  if (event.ctrlKey || event.metaKey || event.shiftKey) {
    const selected = new Set([...selectedNodeIds.value, activeNodeId.value].filter(Boolean));
    if (selected.has(node.id)) selected.delete(node.id); else selected.add(node.id);
    selectedNodeIds.value = [...selected];
    activeNodeId.value = selected.has(node.id) ? node.id : selectedNodeIds.value.at(-1) || '';
    return;
  }
  if (!selectedNodeIds.value.includes(node.id)) selectedNodeIds.value = [node.id];
  activeNodeId.value = node.id;
}

let dragStartNodePos: Record<string, { x: number; y: number }> = {};
let mouseStartCanvasPos = { x: 0, y: 0 };

function startDragNode(e: MouseEvent, node: FlowNode) {
  if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || (e.target as HTMLElement).closest('button,textarea,input,label,video,[draggable="true"]')) return;
  draggingNode = node;

  if (!selectedNodeIds.value.includes(node.id) && activeNodeId.value !== node.id) {
    activeNodeId.value = node.id;
    selectedNodeIds.value = [node.id];
  } else if (!selectedNodeIds.value.includes(node.id)) {
    selectedNodeIds.value.push(node.id);
  }

  Object.assign(mouseStartCanvasPos, canvasPoint(e));

  dragStartNodePos = {};
  const allSelectedIds = new Set([...selectedNodeIds.value, activeNodeId.value].filter(Boolean));
  nodes.value.forEach(n => {
    if (allSelectedIds.has(n.id)) {
      dragStartNodePos[n.id] = { x: n.x, y: n.y };
    }
  });
}

function getNodePortPos(node: FlowNode, type: 'in' | 'out') {
  const cardHeight = node.type === 'image' ? 280 : node.type === 'text' ? 300 : 240;
  const centerY = node.y + cardHeight / 2;

  return {
    x: type === 'in' ? node.x : node.x + 248,
    y: centerY
  };
}

function calculateBezierPath(fromId: string, toId: string): string {
  const fromNode = nodes.value.find(n => n.id === fromId);
  const toNode = nodes.value.find(n => n.id === toId);
  if (!fromNode || !toNode) return '';

  const p1 = getNodePortPos(fromNode, 'out');
  const p2 = getNodePortPos(toNode, 'in');

  const dx = Math.max(Math.abs(p2.x - p1.x) * 0.5, 60);
  return `M ${p1.x} ${p1.y} C ${p1.x + dx} ${p1.y}, ${p2.x - dx} ${p2.y}, ${p2.x} ${p2.y}`;
}

function calculateTempBezier(fromNode: FlowNode, mouse: { x: number; y: number }): string {
  const p1 = getNodePortPos(fromNode, 'out');
  const dx = Math.max(Math.abs(mouse.x - p1.x) * 0.5, 40);
  return `M ${p1.x} ${p1.y} C ${p1.x + dx} ${p1.y}, ${mouse.x - dx} ${mouse.y}, ${mouse.x} ${mouse.y}`;
}

function handleImageUpload(event: Event, node: FlowNode) { void workspace.uploadImage(event, node); }
function toggleAgentDrawer() { agentTab.value = 'chat'; isAgentDrawerOpen.value = !isAgentDrawerOpen.value; }
function askAgentHelpNode(node: FlowNode) {
  agentTab.value = 'chat'; activeNodeId.value = node.id; aiTargetNodeId.value = node.id; isAgentDrawerOpen.value = true;
  if (!inputContent.value.trim()) inputContent.value = '请优化这个小框中的内容，补充可执行的视听细节。';
  nextTick(() => textareaRef.value?.focus({ preventScroll: true }));
}
function sendMessage() {
  const target = nodes.value.find(n => n.id === aiTargetNodeId.value);
  void workspace.sendMessage(target, referencedNodes.value.map(n => n.id));
}
function confirmProjectSpec() { if (canApplyAiContent.value) void workspace.confirmSpec(); }
function prepareVideo() { void workspace.prepareVideo(videoSourceIds.value); }
function submitVideoJob() { void workspace.submitVideoJob(videoSourceIds.value); }
function openAssetsDrawer() { alert('素材库已预留：后续可直接调取历史生成资源！'); }

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainerRef.value) {
      messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight;
    }
  });
}

function formatFullTime(isoStr?: string | null) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}
</script>

<style scoped>
.video-review-feedback.blocked {
  border-color: rgba(234, 179, 8, .35);
  background: rgba(234, 179, 8, .06);
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nav-tv-btn {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 8px 16px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  position: relative;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: blur(8px);
}

.tv-icon-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tv-svg {
  width: 18px;
  height: 18px;
  color: #94a3b8;
  transition: all 0.25s ease;
}

.live-dot {
  position: absolute;
  top: -1px;
  right: -2px;
  width: 5px;
  height: 5px;
  background-color: #ef4444;
  border-radius: 50%;
  box-shadow: 0 0 6px #ef4444;
  animation: tvDotPulse 2s infinite ease-in-out;
}

@keyframes tvDotPulse {
  0%, 100% {
    opacity: 0.5;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
    box-shadow: 0 0 8px #f87171;
  }
}

.tv-btn-label {
  letter-spacing: 0.4px;
  transition: color 0.2s ease;
}

.nav-tv-btn:hover {
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(129, 140, 248, 0.45);
  color: #ffffff;
  transform: translateY(-1.5px);
  box-shadow: 0 6px 20px -4px rgba(99, 102, 241, 0.3);
}

.nav-tv-btn:hover .tv-svg {
  color: #818cf8;
  transform: scale(1.1) rotate(-4deg);
}

.nav-tv-btn:active {
  transform: translateY(0);
}

.workspace-layout :deep(*) {
  scrollbar-width: thin;
  scrollbar-color: #46536a #11151e;
}

.workspace-layout :deep(*::-webkit-scrollbar) {
  width: 8px;
  height: 8px;
}

.workspace-layout :deep(*::-webkit-scrollbar-track) {
  background: #11151e;
  border-radius: 8px;
}

.workspace-layout :deep(*::-webkit-scrollbar-thumb) {
  background: #46536a;
  border: 2px solid #11151e;
  border-radius: 8px;
}

.workspace-layout :deep(*::-webkit-scrollbar-thumb:hover) {
  background: #657590;
}

.workspace-layout :deep(*::-webkit-scrollbar-corner) {
  background: #11151e;
}

.node-text-preview {
  height: 164px;
  overflow: auto;
  color: #cbd5e1;
  box-sizing: border-box;
  user-select: text;
  cursor: text;
}

.node-text-preview:focus-visible {
  outline: 1px solid #818cf8;
  outline-offset: 3px;
  border-radius: 4px;
}

.node-edit-btn {
  flex-shrink: 0;
  border: 0;
  background: transparent;
  color: #a5b4fc;
  font-size: 11px;
  padding: 3px 4px;
  cursor: pointer;
}

.node-edit-btn:hover {
  color: #fff;
}

.video-review-feedback {
  padding: 14px;
  background: #172136;
  border: 1px solid #344665;
  border-radius: 8px;
}

.video-review-feedback.error {
  border-color: #6c5842;
  background: #242127;
}

.video-review-feedback.success {
  border-color: #325b54;
}

.review-heading {
  font-size: 13px;
  font-weight: 600;
  color: #c7d2fe;
  margin-bottom: 9px;
}

.video-review-feedback.error .review-heading {
  color: #e7c9a0;
}

.video-review-feedback.success .review-heading {
  color: #a7dbc7;
}

.drawer-conversation {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.drawer-video-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.agent-flyout-drawer.expanded {
  width: min(1000px, 100%);
}

.drawer-header-actions {
  display: flex;
  gap: 16px;
  align-items: center;
}

.drawer-expand {
  color: #c7d2fe;
  background: #202b41;
  border: 1px solid #3a4967;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.drawer-tabs {
  display: flex;
  flex-shrink: 0;
  padding: 8px 18px;
  gap: 8px;
  border-bottom: 1px solid #263247;
}

.drawer-tabs button {
  flex: 1;
  padding: 9px;
  color: #a5b4cf;
  background: transparent;
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.drawer-tabs button[aria-selected="true"] {
  color: #fff;
  background: #334b78;
}

.target-select-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.target-select-row select {
  flex: 1;
  min-width: 0;
}

.message-source {
  font-size: 11px;
  color: #a5b4cf;
  margin-bottom: 6px;
}

.pending-content-card {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #4d648d;
  background: #172239;
  border-radius: 10px;
  flex-shrink: 0;
}

.pending-content-title {
  color: #c7d2fe;
  font-size: 14px;
  font-weight: 600;
}

.proposal-help,
.chat-empty {
  color: #a5b4cf;
  font-size: 12px;
  line-height: 1.6;
}

.chat-empty {
  margin: auto 12px;
}

.drawer-confirm-row {
  flex-wrap: wrap;
}

.drawer-confirm-row .confirm-pill {
  padding: 8px 12px;
  background: #334b78;
  color: #fff;
}

@media (max-width: 760px) {
  .agent-flyout-drawer {
    width: 100%;
  }
}

.pending-plan-preview summary,
.video-prompt-preview summary {
  cursor: pointer;
  padding: 8px 0;
  color: #c7d2fe;
}

.generation-help,
.generation-source-list {
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.6;
  margin: 8px 0;
}

.prepare-video-btn {
  width: 100%;
  padding: 9px;
  margin: 6px 0 12px;
  background: #243652;
  color: #e2e8f0;
  border: 1px solid #456388;
  border-radius: 8px;
  cursor: pointer;
}

.prepare-video-btn:disabled,
.confirm-pill:disabled {
  opacity: .5;
  cursor: default;
}

.video-prompt-preview {
  padding: 10px;
  background: #101b2d;
  border: 1px solid #324462;
  border-radius: 8px;
  margin-bottom: 12px;
}

.video-prompt-preview pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.7;
  color: #e2e8f0;
}

.video-prompt-preview small {
  font-size: 11px;
  line-height: 1.5;
  color: #94a3b8;
}

.prompt-status {
  color: #c7d2fe;
  font-size: 12px;
}

.prompt-settings {
  color: #94a3b8;
  font-size: 11px;
  margin: 6px 0;
}

.drawer-confirm-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.drawer-confirm-row span {
  font-size: 11px;
  color: #a5b4fc;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-confirm-row .confirm-pill {
  flex-shrink: 0;
}

.msg-content {
  overflow-wrap: anywhere;
  font-size: 14px;
  line-height: 1.75;
  min-width: 0;
}

.msg-content :deep(p) {
  margin: .6em 0;
}

.msg-content :deep(p:first-child) {
  margin-top: 0;
}

.msg-content :deep(p:last-child) {
  margin-bottom: 0;
}

.msg-content :deep(h1),
.msg-content :deep(h2),
.msg-content :deep(h3),
.msg-content :deep(h4) {
  margin: .9em 0 .4em;
  line-height: 1.4;
  font-size: 1.1em;
}

.msg-content :deep(ul),
.msg-content :deep(ol) {
  margin: .5em 0;
  padding-left: 1.6em;
}

.msg-content :deep(li) {
  margin: .25em 0;
}

.msg-content :deep(blockquote) {
  margin: .6em 0;
  padding: 2px 10px;
  border-left: 3px solid #818cf8;
  color: #cbd5e1;
  background: #ffffff08;
}

.msg-content :deep(pre) {
  overflow: auto;
  white-space: pre;
  background: #0a1020;
  padding: 10px;
  border-radius: 6px;
  max-width: 100%;
}

.msg-content :deep(code) {
  font-family: Consolas, monospace;
  background: #0a1020;
  border-radius: 3px;
  padding: 1px 4px;
  font-size: .9em;
}

.msg-content :deep(pre code) {
  padding: 0;
}

.msg-content :deep(table) {
  display: block;
  overflow-x: auto;
  border-collapse: collapse;
  margin: .7em 0;
}

.msg-content :deep(th),
.msg-content :deep(td) {
  border: 1px solid #40516b;
  padding: 5px 8px;
  text-align: left;
}

.msg-content :deep(th) {
  background: #26344c;
}

.msg-content :deep(a) {
  color: #a5b4fc;
  text-decoration: underline;
}

.save-indicator {
  font-size: 12px;
  color: #86efac;
}

.save-indicator.error,
.save-indicator.conflict {
  color: #fbbf24;
}

.save-indicator.pending,
.save-indicator.saving {
  color: #94a3b8;
}

.workspace-notice {
  background: #172033;
  color: #dbeafe;
  padding: 9px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
}

.workspace-notice span {
  flex: 1;
}

.workspace-notice button {
  background: #27344f;
  border: 1px solid #465779;
  border-radius: 6px;
  color: #e2e8f0;
  padding: 5px 9px;
  cursor: pointer;
}

.workspace-loading {
  position: absolute;
  inset: 0;
  z-index: 250;
  background: #07090eea;
  display: grid;
  place-items: center;
  color: #c7d2fe;
}

.ai-target-picker {
  flex-shrink: 0;
  padding: 10px 18px;
  display: grid;
  gap: 6px;
  border-bottom: 1px solid #263247;
}

.ai-target-picker label {
  font-size: 13px;
  color: #cbd5e1;
}

.ai-target-picker select {
  background: #111827;
  color: #e2e8f0;
  border: 1px solid #3a4967;
  border-radius: 6px;
  padding: 7px;
}

.ai-target-picker small,
.node-ai-status {
  font-size: 11px;
  color: #a5b4fc;
}

.node-ai-status {
  padding: 3px 0;
}

.node-footer-actions {
  gap: 6px;
  flex-wrap: wrap;
}

.text-body textarea,
.node-title-input,
.card-rename-input {
  user-select: text;
}

.node-type-icon[draggable] {
  cursor: grab;
}

.node-title {
  display: block;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.floating-top-left {
  flex-wrap: wrap;
  max-width: calc(100% - 60px);
}

.workspace-body {
  min-height: 0;
}

button:disabled {
  opacity: .55;
  cursor: wait;
}

@media(max-width: 720px) {
  .save-indicator {
    max-width: 130px;
  }

  .workspace-notice {
    flex-wrap: wrap;
  }

  .brand-name {
    display: none;
  }
}

.node-binding-banner {
  background: rgba(99, 102, 241, 0.12);
  padding: 8px 14px;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #a5b4fc;
  flex-wrap: wrap;
  gap: 6px;
}

.banner-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.banner-label {
  font-size: 12px;
  color: #94a3b8;
}

.ref-pill {
  background: rgba(99, 102, 241, 0.25);
  border: 1px solid rgba(99, 102, 241, 0.4);
  color: #ffffff;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.agent-flyout-drawer.drag-over {
  border-left: 2px dashed #818cf8 !important;
  box-shadow: -15px 0 35px rgba(99, 102, 241, 0.35) !important;
}

.drag-drop-hint {
  padding: 12px;
  margin: 8px 14px;
  border: 1.5px dashed #818cf8;
  background: rgba(99, 102, 241, 0.15);
  color: #c7d2fe;
  text-align: center;
  border-radius: 8px;
  font-size: 12px;
  animation: pulse 1s infinite alternate;
}

.selection-box {
  position: absolute;
  background: rgba(99, 102, 241, 0.15);
  border: 1.5px solid rgba(129, 140, 248, 0.85);
  border-radius: 4px;
  pointer-events: none;
  z-index: 100;
}

.workspace-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  background-color: #050608;
  color: #f1f5f9;
  font-size: 15px;
  overflow: hidden;
  position: relative;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.desktop-only {
  display: inline-flex;
}

.top-nav {
  height: clamp(60px, 7.5vh, 76px);
  min-height: 60px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 clamp(16px, 2.5vw, 40px);
  background-color: #0d121f;
  box-sizing: border-box;
  z-index: 100;
}

.brand-link {
  text-decoration: none;
  cursor: pointer;
  display: flex;
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-weight: 800;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  box-shadow: 0 0 14px rgba(99, 102, 241, 0.4);
}

.brand-name {
  font-weight: 700;
  color: #ffffff;
  font-size: 18px;
  letter-spacing: 0.5px;
}

.sub-badge {
  font-size: 12px;
  background-color: #172033;
  color: #94a3b8;
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid #28354d;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-link {
  color: #cbd5e1;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  padding: 7px 12px;
  border-radius: 8px;
  background-color: rgba(30, 41, 59, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.2s;
}

.nav-link:hover {
  background-color: rgba(30, 41, 59, 0.8);
  border-color: rgba(99, 102, 241, 0.4);
  color: #fff;
}

.nav-link .icon {
  width: 16px;
  height: 16px;
}

.logout-btn {
  background: rgba(23, 28, 42, 0.6);
  border: 1px solid #2d3748;
  color: #94a3b8;
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background-color: rgba(239, 68, 68, 0.12);
  border-color: #ef4444;
  color: #fca5a5;
}

.workspace-body {
  position: relative;
  flex: 1;
  width: 100vw;
  height: calc(100vh - 64px);
  overflow: hidden;
  display: flex;
}

.slide-left-enter-active,
.slide-left-leave-active {
  transition: transform 0.35s cubic-bezier(0.25, 1, 0.5, 1), opacity 0.35s ease;
  will-change: transform, opacity;
  width: 100%;
}

.slide-left-leave-to {
  transform: translateX(-40px);
  opacity: 0;
}

.slide-left-enter-from {
  transform: translateX(60px);
  opacity: 0;
}

.board-container {
  flex: 1;
  overflow-y: auto;
  padding: 40px 60px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.board-header {
  text-align: center;
  margin-bottom: 32px;
}

.board-title {
  font-size: 26px;
  font-weight: 700;
  color: #f8fafc;
  margin-bottom: 6px;
}

.board-sub {
  font-size: 14px;
  color: #94a3b8;
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 240px));
  gap: 24px;
  width: 100%;
  max-width: 1280px;
  justify-content: center;
}

.square-card {
  aspect-ratio: 1 / 1;
  border-radius: 18px;
  padding: 18px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-sizing: border-box;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
  position: relative;
  overflow: hidden;
}

.square-card:hover {
  transform: translateY(-5px) scale(1.02);
}

.add-card {
  border: 2px dashed rgba(99, 102, 241, 0.5);
  background: rgba(18, 24, 38, 0.4);
  align-items: center;
  justify-content: center;
  gap: 12px;
  transition: all 0.3s ease;
}

.add-card:hover {
  border-color: #818cf8;
  background: rgba(30, 41, 59, 0.6);
  box-shadow: 0 12px 30px -6px rgba(99, 102, 241, 0.4);
}

.plus-icon {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34px;
  font-weight: 300;
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
  transition: transform 0.25s ease;
}

.add-card:hover .plus-icon {
  transform: rotate(90deg) scale(1.1);
}

.add-text {
  font-size: 14px;
  font-weight: 600;
  color: #cbd5e1;
}

.project-card {
  border: 1px solid;
  backdrop-filter: blur(12px);
}

.card-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.card-time {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}

.del-card-btn {
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 18px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.2s;
}

.del-card-btn:hover {
  color: #ef4444;
  background: rgba(255, 255, 255, 0.1);
}

.card-content {
  margin: auto 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.card-project-title {
  font-size: 17px;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-rename-input {
  width: 100%;
  box-sizing: border-box;
  background: rgba(15, 23, 42, 0.9);
  border: 1.5px solid #818cf8;
  border-radius: 6px;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  padding: 5px 8px;
  outline: none;
}

.project-card .version-tag {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.card-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
  gap: 8px;
}

.rename-card-btn {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #cbd5e1;
  padding: 3px 9px;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.rename-card-btn:hover {
  background: rgba(99, 102, 241, 0.28);
  border-color: #818cf8;
  color: #ffffff;
}

.enter-text {
  margin-left: auto;
}

.canvas-viewport {
  flex: 1;
  width: 100%;
  height: 100%;
  position: relative;
  overflow: clip;
  user-select: none;
  cursor: default;
  background-color: #07090e;
  background-image: radial-gradient(rgba(255, 255, 255, 0.12) 1px, transparent 1px);
  background-size: 24px 24px;
}

.canvas-viewport.panning,
.canvas-viewport:active {
  cursor: grabbing;
}

.canvas-plane {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
  will-change: transform;
}

.canvas-plane.is-panning {
  transition: none;
}

.connections-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 6000px;
  height: 6000px;
  pointer-events: none;
  overflow: visible;
}

.conn-group {
  cursor: pointer;
  pointer-events: stroke;
}

.connection-hit-path {
  fill: none;
  stroke: transparent;
  stroke-width: 14px;
}

.connection-base-path {
  fill: none;
  stroke: rgba(255, 255, 255, 0.2);
  stroke-width: 2px;
}

.connection-flow-path {
  fill: none;
  stroke: url(#flowGradient);
  stroke-width: 2.8px;
  stroke-dasharray: 8 16;
  animation: flowLine 1.2s linear infinite;
}

.conn-group:hover .connection-base-path {
  stroke: #ef4444;
}

.connection-temp-path {
  fill: none;
  stroke: #818cf8;
  stroke-width: 2.5px;
  stroke-dasharray: 6 6;
  pointer-events: none;
}

.port-source-active {
  opacity: 1 !important;
  pointer-events: auto !important;
}

.port-source-active .port-inner {
  background: #6366f1 !important;
  border-color: #a5b4fc !important;
  box-shadow: 0 0 10px rgba(99, 102, 241, 0.8) !important;
  transform: scale(1.15);
}

.port-target-active {
  opacity: 1 !important;
  pointer-events: auto !important;
}

.port-target-active .port-inner {
  border-color: #818cf8 !important;
  box-shadow: 0 0 8px rgba(129, 140, 248, 0.6) !important;
  animation: pulseCircle 1.2s infinite alternate ease-in-out;
}

@keyframes pulseCircle {
  from {
    transform: scale(1);
  }
  to {
    transform: scale(1.2);
  }
}

@keyframes flowLine {
  from {
    stroke-dashoffset: 24;
  }
  to {
    stroke-dashoffset: 0;
  }
}

.canvas-node {
  position: absolute;
  width: 248px;
  background: #18191c;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.6);
  cursor: move;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.text-body textarea,
.node-title-input {
  cursor: text;
}

.canvas-node.text {
  height: 300px;
}

.canvas-node.image {
  height: 280px;
}

.canvas-node.video {
  height: 240px;
}

.canvas-node.selected {
  border-color: #818cf8 !important;
  box-shadow: 0 0 0 1.5px #818cf8, 0 12px 30px rgba(0, 0, 0, 0.7) !important;
}

.node-port {
  position: absolute;
  top: 50%;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: crosshair;
  z-index: 10;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.in-port {
  left: 0;
  transform: translate(-50%, -50%);
}

.out-port {
  right: 0;
  transform: translate(50%, -50%);
}

.canvas-node:hover .node-port {
  opacity: 1;
  pointer-events: auto;
}

.port-inner {
  width: 20px;
  height: 20px;
  min-width: 20px;
  min-height: 20px;
  border-radius: 50% !important;
  background: #1e2025;
  border: 1.5px solid rgba(255, 255, 255, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  box-sizing: border-box;
  padding: 0;
  user-select: none;
}

.port-inner .plus-icon {
  font-size: 13px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.in-port .port-inner::after,
.out-port .port-inner::after {
  content: none !important;
}

.node-port:hover .port-inner {
  background: #2a2d36;
  border-color: #818cf8;
  color: #fff;
  transform: scale(1.15);
}

.node-header {
  padding: 12px 14px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.node-type-icon {
  font-size: 13px;
  color: #94a3b8;
}

.node-title-wrap {
  flex: 1;
  min-width: 0;
}

.node-title {
  font-size: 13px;
  font-weight: 600;
  color: #e2e8f0;
  cursor: text;
}

.node-title-input {
  background: #0d0f14;
  border: 1px solid #6366f1;
  border-radius: 4px;
  color: #fff;
  padding: 2px 6px;
  font-size: 12px;
  width: 100%;
  box-sizing: border-box;
  outline: none;
}

.node-del-btn {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 12px;
}

.node-del-btn:hover {
  color: #ef4444;
}

.node-body {
  padding: 12px;
}

.text-body textarea {
  width: 100%;
  height: 164px;
  background: transparent;
  border: none;
  color: #cbd5e1;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  outline: none;
  box-sizing: border-box;
}

.node-footer-actions {
  display: flex;
  justify-content: flex-end;
  padding-top: 6px;
}

.ai-assist-pill {
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #a5b4fc;
  border-radius: 12px;
  font-size: 11px;
  padding: 3px 8px;
  cursor: pointer;
}

.ai-assist-pill:hover {
  background: rgba(99, 102, 241, 0.3);
}

.image-body {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.image-preview-box {
  width: 100%;
  height: 190px;
  border-radius: 12px;
  background: #111216;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-preview-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-placeholder svg {
  width: 48px;
  height: 48px;
  color: #2e3440;
}

.image-upload-hover-pill {
  position: absolute;
  top: -16px;
  background: #2b2d33;
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 5px 14px;
  border-radius: 20px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  opacity: 0;
  transform: translateY(6px);
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
  z-index: 10;
}

.image-generate-entry { color: #c7c8ff; border-color: #605e9666; }
.image-generate-node { position: absolute; right: 9px; bottom: 9px; z-index: 12; border: 1px solid #7874b788; border-radius: 7px; background: #24253ce8; color: #d0ceff; font-size: 11px; padding: 6px 9px; cursor: pointer; box-shadow: 0 3px 10px #0004; }
.image-generate-node:hover { background: #44416a; }

.image-upload-hover-pill svg {
  width: 14px;
  height: 14px;
}

.canvas-node:hover .image-upload-hover-pill {
  opacity: 1;
  transform: translateY(0);
}

.hidden-file-input {
  display: none;
}

.video-body video {
  width: 100%;
  height: 150px;
  border-radius: 12px;
  object-fit: cover;
}

.context-menu-box {
  position: fixed;
  z-index: 200;
  width: 210px;
  background: #18191c;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.7);
  padding: 8px;
}

.menu-title {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
  padding: 6px 10px 4px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.menu-item:hover {
  background: #26282e;
}

.menu-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #2a2d34;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
}

.item-name {
  font-size: 13px;
  font-weight: 600;
  color: #f1f5f9;
}

.item-desc {
  font-size: 10px;
  color: #94a3b8;
}

.floating-top-left {
  position: absolute;
  top: 18px;
  left: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  z-index: 20;
}

.glass-pill-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(24, 27, 36, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.glass-pill-btn.icon-only {
  padding: 6px 10px;
}

.glass-pill-btn:hover {
  background: #2d3345;
  color: #fff;
}

.icon-sm {
  width: 14px;
  height: 14px;
}

.canvas-project-title {
  font-size: 13px;
  color: #64748b;
}

.floating-left-bar {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: rgba(24, 27, 36, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 6px;
  z-index: 20;
}

.side-tool-btn {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: transparent;
  border: none;
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.side-tool-btn svg {
  width: 18px;
  height: 18px;
}

.side-tool-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.side-tool-btn.highlight {
  color: #38bdf8;
}

.tool-tip {
  position: absolute;
  left: 46px;
  background: #0f121a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 3px 8px;
  border-radius: 5px;
  font-size: 11px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s;
}

.side-tool-btn:hover .tool-tip {
  opacity: 1;
}

.floating-bottom-right {
  position: absolute;
  right: 24px;
  bottom: 24px;
  z-index: 30;
}

.agent-orb-btn {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #18191c;
  border: 1px solid rgba(255, 255, 255, 0.15);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.6);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s;
}

.agent-orb-btn:hover {
  transform: scale(1.08);
}

.orb-inner {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.orb-logo {
  width: 22px;
  height: 22px;
  background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10"/></svg>');
  background-size: contain;
}

.agent-orb-btn.generating {
  animation: pulseOrb 1.5s infinite alternate;
}

@keyframes pulseOrb {
  from {
    box-shadow: 0 0 10px #6366f1;
  }
  to {
    box-shadow: 0 0 25px #38bdf8;
  }
}

.agent-flyout-drawer {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: min(680px, 56vw);
  background: #101217;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: -12px 0 35px rgba(0, 0, 0, 0.85);
  z-index: 990;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.agent-flyout-drawer.open {
  transform: translateX(0);
}

.drawer-top-bar {
  flex-shrink: 0;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.drawer-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 18px;
}

.orb-mini {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #38bdf8;
}

.drawer-close {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
}

.clear-bind {
  background: none;
  border: none;
  color: #818cf8;
  cursor: pointer;
  font-size: 15px;
}

.drawer-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-row {
  display: flex;
  gap: 10px;
  font-size: 13px;
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}

.user .avatar {
  background: #4f46e5;
}

.assistant .avatar {
  background: #059669;
}

.bubble {
  background: #191c24;
  padding: 10px 14px;
  border-radius: 10px;
  line-height: 1.5;
  max-width: calc(100% - 42px);
  min-width: 0;
  box-sizing: border-box;
}

.user .bubble {
  background: #26334d;
}

.bubble.thinking {
  display: flex;
  align-items: center;
  gap: 10px;
}

.thinking-text {
  min-width: 0;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.citations-fold {
  margin-top: 4px;
  font-size: 10px;
  color: #38bdf8;
}

.drawer-spec-panel {
  padding: 12px 16px;
  background: #14171f;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.spec-quick-header {
  display: flex;
  justify-content: space-between;
  font-size: 15px;
  color: #94a3b8;
}

.confirm-pill {
  background: #1e293b;
  color: #38bdf8;
  border: 1px solid #334155;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 15px;
  cursor: pointer;
}

.spec-field-mini select {
  width: 100%;
  background: #1a202c;
  border: 1px solid #2d3748;
  color: #fff;
  padding: 6px;
  border-radius: 6px;
  font-size: 15px;
}

.video-generation-settings {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin: 18px 0 8px;
}

.video-generation-settings input {
  box-sizing: border-box;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #2a3446;
  border-radius: 7px;
  background: #1b222e;
  color: #e1e7ef;
  font: inherit;
}

.video-generation-settings input:focus {
  outline: 2px solid #7484f6;
  outline-offset: 1px;
}

.video-generation-settings .spec-field-mini {
  min-width: 0;
}

.duration-control {
  position: relative;
}

.duration-control input[type="number"] {
  padding-right: 82px;
  appearance: textfield;
  -moz-appearance: textfield;
}

.duration-control input::-webkit-inner-spin-button,
.duration-control input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.duration-stepper {
  position: absolute;
  right: 5px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  gap: 4px;
}

.duration-stepper button {
  display: grid;
  place-items: center;
  width: 30px;
  height: 28px;
  padding: 0;
  border: 1px solid #35415a;
  border-radius: 5px;
  background: #253047;
  color: #c7d2fe;
  font: inherit;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.duration-stepper button:hover:not(:disabled) {
  background: #354267;
  border-color: #7484f6;
}

.duration-stepper button:focus-visible {
  outline: 2px solid #7484f6;
  outline-offset: 1px;
}

.duration-stepper button:disabled {
  opacity: .4;
  cursor: not-allowed;
}

.create-video-btn {
  background: #10b981;
  color: #fff;
  border: none;
  padding: 8px;
  border-radius: 6px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.create-video-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.active-job-strip {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.progress-bar-bg {
  position: relative;
  width: 100%;
  height: 5px;
  background: #1e293b;
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-inner {
  height: 100%;
  background: #38bdf8;
  border-radius: 3px;
  transition: width 0.3s ease, background-color 0.3s ease;
}

.progress-bar-inner.succeeded {
  width: 100%;
  background: #10b981;
}

.progress-bar-inner.failed {
  width: 100%;
  background: #ef4444;
}

.progress-bar-inner.indeterminate {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 35%;
  background: linear-gradient(90deg, rgba(56, 189, 248, 0.15), #38bdf8, rgba(56, 189, 248, 0.15));
  animation: indeterminateSlide 1.4s infinite ease-in-out;
}

@keyframes indeterminateSlide {
  0% {
    left: -35%;
  }
  100% {
    left: 100%;
  }
}

.status-txt {
  font-size: 10px;
  color: #94a3b8;
  text-align: center;
}

.drawer-input-box {
  flex-shrink: 0;
  padding: 12px 18px 14px;
  background: #0c0e12;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.drawer-input-box textarea {
  width: 100%;
  height: clamp(80px, 14vh, 120px);
  background: #161820;
  border: 1px solid #282c37;
  border-radius: 10px;
  padding: 12px 14px;
  color: #fff;
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  min-height: 80px;
  max-height: 240px;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.drawer-input-box textarea:focus {
  border-color: #6366f1;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.input-actions-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.input-actions-row .hint {
  font-size: 12px;
  color: #64748b;
}

.send-btn {
  background: #6366f1;
  color: #fff;
  border: none;
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #4f46e5;
}

/* 国际传播指引弹窗 */
.guide-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(4, 6, 12, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.guide-modal-box {
  width: 100%;
  max-width: 680px;
  background: #0f1524;
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 90vh;
  overflow-y: auto;
}

.guide-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.modal-badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: #38bdf8;
}

.modal-title {
  font-size: 18px;
  font-weight: 700;
  color: #f8fafc;
  margin-top: 2px;
}

.cancel-action-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.modal-sub-desc {
  font-size: 12px;
  color: #94a3b8;
  margin: 4px 0 0 0;
}

.countries-status-tip {
  padding: 14px;
  border-radius: 8px;
  background: #141b2c;
  border: 1px solid #1f2b44;
  color: #94a3b8;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.countries-status-tip.error {
  border-color: rgba(239, 68, 68, 0.4);
  color: #fca5a5;
}

.retry-inline-btn {
  background: #27344f;
  border: 1px solid #465779;
  color: #e2e8f0;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.countries-multi-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 4px 0;
}

.country-select-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 76px;
  background: #172033;
  border: 1px solid #28374f;
  color: #cbd5e1;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.country-select-pill:hover {
  border-color: #6366f1;
  color: #ffffff;
  background: #1e2942;
}

.country-select-pill.active {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  border-color: #818cf8;
  color: #ffffff;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
}

.check-mark {
  font-size: 12px;
  font-weight: 700;
}

.apply-to-chat-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.guidance-content-box {
  background: #141b2c;
  border: 1px solid #1f2b44;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.guidance-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.country-target-name {
  font-size: 15px;
  font-weight: 700;
  color: #f8fafc;
}

.lang-pill {
  background: #1e293b;
  color: #38bdf8;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}

.guidance-detail-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.guide-block {
  font-size: 12px;
  line-height: 1.5;
  color: #cbd5e1;
}

.block-label {
  font-weight: 600;
  color: #94a3b8;
}

.guide-block.highlight-block {
  background: rgba(239, 68, 68, 0.08);
  border-left: 3px solid #ef4444;
  padding: 6px 8px;
  border-radius: 0 4px 4px 0;
}

.guide-block.highlight-block .block-label {
  color: #fca5a5;
}

.prompt-snippet-box {
  background: #0b0f19;
  border: 1px solid #1c2639;
  border-radius: 6px;
  padding: 10px;
}

.snippet-label {
  font-size: 11px;
  color: #64748b;
  margin-bottom: 2px;
}

.snippet-text {
  font-size: 12px;
  color: #a5f3fc;
  line-height: 1.45;
  font-family: monospace;
  overflow-wrap: anywhere;
}

.guide-modal-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-tip {
  font-size: 11px;
  color: #64748b;
}

.apply-to-chat-btn {
  background: linear-gradient(135deg, #10b981, #059669);
  color: #ffffff;
  border: none;
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.fade-fast-enter-active,
.fade-fast-leave-active {
  transition: opacity 0.15s;
}

.fade-fast-enter-from,
.fade-fast-leave-to {
  opacity: 0;
}

.loading-spinner {
  box-sizing: border-box;
  flex: 0 0 16px;
  width: 16px;
  height: 16px;
  border: 2px solid #64748b;
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.mobile-block-overlay {
  display: none;
}

@media (max-width: 768px) {
  .mobile-block-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    background: radial-gradient(circle at center, #111827 0%, #030712 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    box-sizing: border-box;
  }

  .mobile-block-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    max-width: 340px;
  }

  .mobile-device-icon {
    font-size: 54px;
    margin-bottom: 20px;
    filter: drop-shadow(0 0 16px rgba(99, 102, 241, 0.45));
    animation: iconBounce 2s infinite ease-in-out;
  }

  .mobile-block-title {
    font-size: 26px;
    font-weight: 800;
    color: #f8fafc;
    letter-spacing: 0.5px;
    margin: 0 0 12px 0;
  }

  .mobile-block-desc {
    font-size: 20px;
    font-weight: 700;
    color: #818cf8;
    margin: 0 0 16px 0;
    letter-spacing: 0.5px;
  }

  .mobile-block-sub {
    font-size: 13px;
    color: #64748b;
    line-height: 1.6;
  }

  @keyframes iconBounce {
    0%, 100% {
      transform: translateY(0);
    }
    50% {
      transform: translateY(-8px);
    }
  }

  .top-nav,
  .workspace-body,
  .floating-bottom-right,
  .guide-modal-mask {
    display: none !important;
  }

  .mobile-actions-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    margin-top: 28px;
  }

  .mobile-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 20px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    box-sizing: border-box;
    transition: transform 0.2s ease, opacity 0.2s ease;
  }

  .mobile-btn:active {
    transform: scale(0.97);
  }

  .mobile-btn-icon {
    width: 18px;
    height: 18px;
  }

  .mobile-btn.home-btn {
    background: rgba(30, 41, 59, 0.7);
    color: #e2e8f0;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .mobile-btn.tv-btn {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(79, 70, 229, 0.45));
    border: 1px solid rgba(129, 140, 248, 0.5);
    color: #ffffff;
    box-shadow: 0 4px 20px -2px rgba(99, 102, 241, 0.35);
  }

  .mobile-tv-icon-wrap {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .live-dot-mini {
    position: absolute;
    top: -1px;
    right: -2px;
    width: 5px;
    height: 5px;
    background-color: #ef4444;
    border-radius: 50%;
    box-shadow: 0 0 6px #ef4444;
  }
}

.video-failure-detail { color: #fca5a5; font-size: 12px; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; margin: 10px 0; }
.portrait-failure-mask { position: fixed; inset: 0; z-index: 1800; display: flex; align-items: center; justify-content: center; background: #020617b8; backdrop-filter: blur(4px); padding: 24px; }
.portrait-failure-dialog { width: min(460px, 100%); padding: 26px; background: #151b29; border: 1px solid #3b465f; border-radius: 15px; color: #e2e8f0; box-shadow: 0 24px 90px #0009; }
.portrait-failure-dialog h3 { margin: 0 0 16px; font-size: 18px; }
.portrait-failure-dialog p { line-height: 1.8; font-size: 14px; overflow-wrap: anywhere; }
.portrait-failure-dialog .portrait-vendor-detail { color: #94a3b8; font-size: 12px; white-space: pre-wrap; }
.portrait-failure-dialog button { display: block; margin: 22px 0 0 auto; border: 1px solid #818cf8; border-radius: 7px; background: #6366f1; padding: 10px 22px; color: white; cursor: pointer; }

.image-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 16px 20px; }
.empty-image-portrait-note { max-width: 180px; margin: 12px 0 0; text-align: center; font-size: 10px; line-height: 1.7; color: #78869e; cursor: default; }
.empty-image-portrait-note button, .portrait-channel-help button { display: inline; border: 0; background: none; padding: 0; color: #a5b4fc; font: inherit; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.portrait-channel-help button { margin-left: 5px; white-space: nowrap; }
.empty-image-portrait-note button:focus-visible, .portrait-channel-help button:focus-visible { outline: 2px solid #a5b4fc; outline-offset: 2px; border-radius: 2px; }
</style>