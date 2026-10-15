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
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
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
   <!-- 顶部导航栏 -->
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
          <!-- 精致电视天线 SVG 标识 -->
          <span class="tv-icon-wrapper">
            <svg class="tv-svg" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M7 3L11.5 7.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              <path d="M17 3L12.5 7.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              <rect x="2.5" y="7.5" width="19" height="13.5" rx="3" stroke="currentColor" stroke-width="1.8" />
              <path d="M6 11.5H14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-opacity="0.8" />
              <path d="M6 14.5H11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-opacity="0.4" />
              <circle cx="18" cy="11.5" r="1.1" fill="currentColor" />
              <circle cx="18" cy="15.5" r="1.1" fill="currentColor" />
            </svg>
            <span class="live-dot"></span>
          </span>
          <span class="tv-btn-label">TV 频道</span>
        </router-link>
      </div>

      <div class="nav-actions">
        <!-- 原有保存状态、API配置、退出登录等按钮保持不变 -->
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
              :aria-disabled="!initialized || isCreatingConv || loading" @keydown.enter="createNewConversation"
              @click="createNewConversation">
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
                <h3 class="card-project-title">{{ conv.title || '新创作对话' }}</h3>
                <span class="version-tag">版本 v{{ conv.version || 0 }}</span>
              </div>

              <div class="card-bottom">
                <span>点击进入工作台 →</span>
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
            <span class="canvas-project-title">{{ activeConversation?.title || '新创作工作流' }}</span>
          </div>

          <!-- 左侧居中悬浮工具栏：素材库与国际传播指导 -->
          <div class="floating-left-bar">
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
         <div 
  class="canvas-plane" 
  :class="{ 'is-panning': isPanning }"
  :style="{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }"
>
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
                <!-- 宽隐形响应区方便点击 -->
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

                <!-- 节点命名（双击修改） -->
                <div class="node-title-wrap">
                  <input v-if="node.isRenaming" v-model="node.title" class="node-title-input" v-autofocus
                    maxlength="200" aria-label="小框名称" @mousedown.stop @click.stop @blur="node.isRenaming = false"
                    @keydown.enter="node.isRenaming = false" />
                  <span v-else class="node-title" @dblclick.stop="node.isRenaming = true" title="双击进行重命名">
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
              <button role="tab" :aria-selected="agentTab === 'video'" @click="agentTab = 'video'">生成视频</button>
            </div>

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
                <small>自由讨论不会改动小框。点击“确定并写入小框”后，待写入正文才会替换小框文字，可撤销。</small>
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
                    <div v-if="msg.model_name === 'local-preview'" class="message-source">历史模拟回复 · 江南旅行示例</div>
                    <div v-else-if="msg.model_name" class="message-source">{{ msg.model_name }}</div>
                    <div class="msg-content" v-html="renderMd(msg.content)"></div>
                    <div v-if="aiTargetNode?.pending_ai?.message_id === msg.id" class="pending-content-card">
                      <div class="pending-content-title">待写入正文 · {{ aiTargetNode.title }}</div>
                      <p v-if="aiTargetNode.pending_ai.source_model === 'local-preview'" class="proposal-help">
                        这是之前的模拟测试内容。发送消息后，真实 AI 会为你重新创作。</p>
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
                  <div class="bubble thinking"><span class="loading-spinner"></span><span>AI 正在回复，小框原文已保留…</span></div>
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
                <small class="generation-help">Ctrl 点击或拖动画布框选可选择多个小框。</small>
                <p v-if="videoSourceNodes.some(n => n.pending_ai)" class="generation-help">部分小框有尚未采用的 AI
                  正文。视频只使用小框当前文字；需要采用时，请先回到“AI 协作”写入。</p>
                <div class="spec-field-mini"><label for="video-api">视频生成通道</label>
                  <select id="video-api" v-model="selectedApiConfigId" :disabled="isSubmittingJob">
                    <option value="platform">平台体验通道（每日限 1 次）</option>
                    <option v-for="cfg in apiConfigs" :key="cfg.id" :value="cfg.id">{{ cfg.display_name }} ({{ cfg.remote_model_id }})</option>
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
                    <select id="video-first-frame" v-model="canvas.video_input_roles.first_frame_node_id" :disabled="isSubmittingJob">
                      <option value="">按画布顺序使用第一张图片</option>
                      <option v-for="image in videoImageNodes" :key="image.id" :value="image.id">{{ image.title }}</option>
                    </select>
                  </div>
                  <div class="spec-field-mini"><label for="video-last-frame">尾帧图片</label>
                    <select id="video-last-frame" v-model="canvas.video_input_roles.last_frame_node_id" :disabled="isSubmittingJob">
                      <option value="">按画布顺序使用第二张；仅一张时沿用首帧（模型支持时）</option>
                      <option v-for="image in videoImageNodes" :key="image.id" :value="image.id">{{ image.title }}</option>
                    </select>
                  </div>
                </div>
                <div class="video-generation-settings">
                  <div class="spec-field-mini"><label for="video-duration">视频时长（秒，必填）</label>
                    <select v-if="selectedGenerationTarget?.profile?.image_constraints" id="video-duration"
                      v-model="canvas.video_duration_seconds" required :disabled="isSubmittingJob">
                      <option disabled :value="null">请选择时长</option>
                      <option v-for="duration in videoDurationOptions" :key="duration" :value="duration">{{ duration }} 秒</option>
                    </select>
                    <input v-else id="video-duration" v-model="videoDurationInput" type="number" min="1" max="15" step="1"
                      required placeholder="填写 1–15 秒" :disabled="isSubmittingJob" />
                  </div>
                  <div class="spec-field-mini"><label for="video-resolution">视频清晰度（必选）</label>
                    <select id="video-resolution" v-model="canvas.video_resolution" required
                      :disabled="isSubmittingJob">
                      <option disabled value="">请选择清晰度</option>
                      <option v-for="resolution in videoResolutionOptions" :key="resolution" :value="resolution">{{ resolution }}</option>
                    </select>
                  </div>
                </div>
                <p v-if="videoSettingsReason" class="generation-help" role="status">{{ videoSettingsReason }}</p>
                <p class="generation-help">AI 会按当前模型与设置审理，说明必要的参数调整和图片处理。点击生成即采用审理结果，画布原图保留。修改内容、通道、模式或参数后需重新审理。</p>
                <button class="prepare-video-btn"
                  :disabled="!videoSourceNodes.length || !!videoSettingsReason || targetLoading || isPreparingVideo || isAgentResponding || isSubmittingJob || isConfirming"
                  @click="prepareVideo">{{ isPreparingVideo ? 'AI 正在审理…' : 'AI审理方案' }}</button>
                <div v-if="videoReview" class="video-review-feedback" :class="videoReview.kind" role="status"
                  aria-live="polite">
                  <div class="review-heading">{{ videoReview.kind === 'loading' ? 'AI审理中' :
                    !videoReviewFresh ? '上次审理结果（内容、模型或设置已变化）' : 'AI审理结果' }}</div>
                  <div class="msg-content" v-html="renderMd(videoReview.content)"></div>
                </div>
                <div v-if="project?.compiled_prompt && canvas.generation_source_ids.length && canvas.generation_review?.status === 'ready'"
                  class="video-prompt-preview">
                  <div class="prompt-status">{{ videoSelectionReady ? '方案已准备好，可直接生成' : '生成来源或参数已变化，请重新审理方案' }}</div>
                  <div class="prompt-settings">{{ project.current_spec.duration_seconds }} 秒 · {{
                    project.current_spec.aspect_ratio === 'adaptive' ? '随素材自适应' : project.current_spec.aspect_ratio }} · {{ canvas.generation_settings?.resolution || '清晰度未确认' }} · {{
                    generationModeLabel }}</div>
                  <small>生成使用审理结果中的最终参数。原始小框和上方输入保留；如需修改，请调整后重新审理。</small>
                </div>
               <button class="create-video-btn" :disabled="!!videoGenerationDisabledReason || isJobRunning"
                  :aria-describedby="videoGenerationDisabledReason ? 'video-generation-reason' : undefined"
                  @click="submitVideoJob">{{ isSubmittingJob ? '正在提交生成…' : isJobRunning ? '视频生成中…' : '2. 确认并生成视频' }}</button>
                <p v-if="videoGenerationDisabledReason" id="video-generation-reason" class="generation-help"
                  role="status">{{ videoGenerationDisabledReason }}</p>
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
                </div>
              </div>
            </div>
          </aside>
        </div>
      </Transition>
    </div>

    <!-- ================= 国际传播指引弹窗 ================= -->
    <div v-if="showGuideModal" class="guide-modal-mask" @click.self="closeGuideModal">
      <div class="guide-modal-box">
        <div class="guide-modal-header">
          <div class="modal-title-group">
            <span class="modal-badge">CULTURAL GUIDANCE</span>
            <h3 class="modal-title">国际传播叙事指引与受众偏好</h3>
          </div>
          <button class="cancel-action-btn" @click="closeGuideModal">算了</button>
        </div>

        <div class="countries-tab-bar">
          <button v-for="country in countryList" :key="country.code" class="country-tab"
            :class="{ active: selectedCountryCode === country.code }" @click="selectCountry(country.code)">
            <span class="flag-icon">{{ country.flag }}</span>
            <span>{{ country.name }}</span>
          </button>
        </div>

        <div class="guidance-content-box">
          <div class="guidance-header">
            <h4 class="country-target-name">{{ currentCountryGuide.name }}受众视听特征与叙事建议</h4>
            <span class="lang-pill">{{ currentCountryGuide.lang }}</span>
          </div>

          <div class="guidance-detail-card">
            <div class="guide-block">
              <span class="block-label">审美喜好与节奏：</span>
              <p class="block-desc">{{ currentCountryGuide.aesthetic }}</p>
            </div>
            <div class="guide-block">
              <span class="block-label">叙事共情逻辑：</span>
              <p class="block-desc">{{ currentCountryGuide.narrative }}</p>
            </div>
            <div class="guide-block highlight-block">
              <span class="block-label">避免踩雷与文化禁忌：</span>
              <p class="block-desc">{{ currentCountryGuide.taboo }}</p>
            </div>
          </div>

          <div class="prompt-snippet-box">
            <div class="snippet-label">可注入节点的特化创作指令：</div>
            <div class="snippet-text">{{ currentCountryGuide.promptText }}</div>
          </div>
        </div>

        <div class="guide-modal-footer">
          <span class="footer-tip desktop-only">点击下方按钮可直接把建议放入当前文本节点</span>
          <button class="apply-to-chat-btn" @click="applyGuidanceToNode">
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
import type { FlowNode, FlowConnection } from '@/types/canvas';
import { renderMd } from '@/utils/markdown';
import { generationContextMatches, generationMatches, generationSources, videoDurationChoices, videoGenerationBlockReason, videoSettingsBlockReason } from '@/services/generationState';


import { useRouter, useRoute } from 'vue-router'; // 确保引入了 useRoute

const route = useRoute();

onMounted(async () => {
  // 如果通过跳转带入了 conv_id，直接自动切换至该对话进入 B 页面
  if (route.query.conv_id) {
    await switchConversation(String(route.query.conv_id));
  } else if (!currentConvId.value && conversations.value.length > 0) {
    // 若希望每次直接进入 B 页面，可默认激活最近的一个会话
    // await switchConversation(conversations.value[0].id);
  }
});
const workspace = useWorkspace();
const {
  canvas, nodes, connections, pan, zoom, conversations, currentConvId, messages, inputContent,
  project, apiConfigs, selectedApiConfigId, isSubmittingJob, isConfirming, isAgentResponding,
  selectedGenerationTarget, targetLoading, targetError,
  isCreatingConv, isAgentDrawerOpen, referencedNodeIds, aiTargetNodeId, activeJob,
  generationReady, isPreparingVideo, videoReview, initialized, loading, notice, saveState, saveLabel, uploading,
  switchConversation, createNewConversation, backToProjectSpace, retrySave, resolveConflict,
  restoreBeforeAi, handleLogout,
} = workspace;
const viewportRef = ref<HTMLElement | null>(null);
const messagesContainerRef = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const agentTab = ref<'chat' | 'video'>('chat');
const isAgentExpanded = ref(false);
const activeNodeId = ref('');
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
  // 判断当前是否有正在进行中的视频生成任务
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
const deletedNode = ref<{ node: FlowNode; connections: FlowConnection[] } | null>(null);
const vAutofocus = { mounted: (element: HTMLInputElement) => { element.focus({ preventScroll: true }); element.select(); } };

const referencedNodes = computed(() => {
  const ids = referencedNodeIds.value.length ? referencedNodeIds.value : [...selectedNodeIds.value, activeNodeId.value];
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
  activeNodeId.value = ''; selectedNodeIds.value = []; connectingSource.value = null;
  contextMenu.visible = false; deletedNode.value = null; handleCanvasMouseUp();
});
watch(() => messages.value.length, scrollToBottom);
watch(() => aiTargetNode.value?.pending_ai?.message_id, scrollToBottom);
watch(agentTab, tab => { if (tab === 'chat') scrollToBottom(); });

// ==================== 3. 国际传播文化配置 ====================
const showGuideModal = ref(false);
const selectedCountryCode = ref('US');
const countryList = [
  { code: 'US', name: '美国', flag: '🇺🇸' },
  { code: 'FR', name: '法国', flag: '🇫🇷' },
  { code: 'JP', name: '日本', flag: '🇯🇵' },
  { code: 'IN', name: '印度', flag: '🇮🇳' },
  { code: 'DE', name: '德国', flag: '🇩🇪' },
  { code: 'GB', name: '英国', flag: '🇬🇧' },
];

const countryGuideMap: Record<string, {
  name: string; lang: string; aesthetic: string; narrative: string; taboo: string; promptText: string;
}> = {
  US: {
    name: '美国', lang: '英语 (en-US)',
    aesthetic: '偏好高对比度动态视觉、明快紧凑的运镜剪辑与强烈的视觉奇观冲击；喜欢自然抓人眼球的开门见山式镜头。',
    narrative: '侧重个人英雄主义、个体真实经历与温情日常叙事，避免空洞说教，强调平等交流与自然共鸣。',
    taboo: '注意避免任何形式的刻板印象、种族敏感符号或过度主旋律视角的宏大叙事灌输。',
    promptText: '【国际传播受众：美国】请采用写实电影画质、高动态光影与明快节奏推进。注重以生动微观的个体视角展开，弱化宏大概念，重点强调真实烟火气与情感共鸣。'
  },
  FR: {
    name: '法国', lang: '法语 / 英语 (fr-FR)',
    aesthetic: '极为看重画面诗意、自然光影质感与艺术构图。偏好低饱和度、胶片颗粒感及留白的浪漫慢镜头。',
    narrative: '偏爱思辨性与哲学深意，喜欢讲述人与自然、传统工艺或慢生活的意境美，崇尚原生态与个性化表达。',
    taboo: '反感工业化流水线感过重或过于喧闹刺眼的塑料 CG 感；避免直接灌输式说理。',
    promptText: '【国际传播受众：法国】请运用胶片质感、柔和自然光与富有诗意的长镜头推拉。镜头语言需具有艺术留白与慢生活审美，呈现兼具哲思与优雅的文化意境。'
  },
  JP: {
    name: '日本', lang: '日语 (ja-JP)',
    aesthetic: '追求“物哀”与细腻治愈审美。偏好清新微暖的色调、柔光运镜、对季节流转与细微声画动作（如水滴、风吹落叶）的捕捉。',
    narrative: '长于以小见大，从生活细节、人情羁绊与匠人精神中展现文化底蕴，容易被纯粹专注、平和克制的情感打动。',
    taboo: '避免夸张喧嚣的肢体冲突与生硬的情绪宣泄；慎用容易引发历史语境争议的图腾符号。',
    promptText: '【国际传播受众：日本】请采用日系清新胶片色调与柔美漫射光，运镜平稳细腻。重点捕捉微观场景细节与人情温暖，营造内敛治愈的视听共情体验。'
  },
  IN: {
    name: '印度', lang: '印地语 / 英语 (hi-IN / en-IN)',
    aesthetic: '热爱浓郁明丽的高饱和色彩（暖黄、翠绿、朱红等），青睐富有韵律感、富丽堂皇且充满生命力的镜头动势。',
    narrative: '极为看重家庭团聚、传统节日氛围与富有感染力的生活仪式感，偏向乐观向上、热烈欢快的叙事弧线。',
    taboo: '避免冷色调或沉闷压抑的灰暗构图；注意规避宗教习俗与特定饮食层面的文化冒犯。',
    promptText: '【国际传播受众：印度】请采用高饱和度暖色调与富丽光影，运镜富有节奏与活力。突出热烈欢快的节日氛围或家庭人际温情，展现充满蓬勃生命力的视听画面。'
  },
  DE: {
    name: '德国', lang: '德语 / 英语 (de-DE)',
    aesthetic: '崇尚极简主义与理性几何构图。偏爱冷峻清晰的工业秩序感、冷色系自然光线与一丝不苟的透视对称。',
    narrative: '重视事实逻辑、精密工艺原理与生态可持续理念，对结构清晰、严谨真实的叙事接受度最高。',
    taboo: '排斥虚假浮夸、逻辑前后矛盾或逻辑煽情的画面设计；注重规则与严谨度。',
    promptText: '【国际传播受众：德国】请采用严谨的几何对称构图与低饱和冷色调电影光影。运镜克制平稳，强调画面主体的结构质感与逻辑严密性。'
  },
  GB: {
    name: '英国', lang: '英式英语 (en-GB)',
    aesthetic: '偏好古典优雅、阴雨朦胧的氛围光影（油画质感、历史厚重感、冷色调雾气感与复古色泽）。',
    narrative: '青睐英式幽默、含蓄克制以及对历史文化遗产、古老街区与人与自然共生的细腻呈现。',
    taboo: '避免用力过猛的浮躁炫技和过于直白露骨的情绪宣泄。',
    promptText: '【国际传播受众：英国】请采用复古油画质感与阴雨冷雾电影氛围光。镜头缓慢深沉推进，展现兼具古典底蕴与内敛克制的人文故事。'
  }
};

const currentCountryGuide = computed(() => countryGuideMap[selectedCountryCode.value]);
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

// 记录当前正在按下的方向键集合
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

// 每一帧执行的画布平滑位移（无停顿、零延迟）
function updateKeyPanLoop() {
  if (!currentConvId.value || loading.value || pressedArrowKeys.size === 0) {
    keyPanRafId = null;
    return;
  }

  // 每帧移动像素速度（60Hz下约每秒840px，可根据手感调大或调小，例如 12 ~ 18）
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
  if (isEditableTarget(event.target)) return;

  if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
    event.preventDefault();
    pressedArrowKeys.add(event.key);
    // 按下瞬间立即启动帧循环，彻底消除系统长按停顿
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

onMounted(() => {
  window.addEventListener('mousemove', handleCanvasMouseMove);
  window.addEventListener('mouseup', handleCanvasMouseUp);
  window.addEventListener('keydown', handleKeydown);
  window.addEventListener('keyup', handleKeyup);
  window.addEventListener('blur', stopKeyPan); // 切换窗口失焦时自动停止移动
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
// 点击端口：首次点击作为起点拉线，再次点击目标端口完成连接
// 3. 点击加号端点拉线
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

// 画布鼠标移动：更新跟随鼠标的临时线末端坐标
function handleCanvasMouseMove(e: MouseEvent) {
  if (isPanning.value) {
    pan.value.x = e.clientX - startPan.x;
    pan.value.y = e.clientY - startPan.y;
  } else if (draggingNode) {
    // 计算当前鼠标在画布里的坐标
    const { x: currentCanvasX, y: currentCanvasY } = canvasPoint(e);

    // 计算鼠标平移的相对差值
    const deltaX = currentCanvasX - mouseStartCanvasPos.x;
    const deltaY = currentCanvasY - mouseStartCanvasPos.y;

    // 所有选中的节点同时平移相同距离
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

// 画布空白处按下：取消选中；若拉线中则随时取消；若 Agent 面板打开则自动收回
function handleCanvasMouseDown(e: MouseEvent) {
  if (loading.value || (e.target as HTMLElement).closest('button,input,textarea,select,.floating-top-left,.floating-left-bar,.floating-bottom-right')) return;
  if (contextMenu.visible) {
    contextMenu.visible = false;
    return;
  }

  // 移除或注释掉此处的关闭逻辑：
  // if (isAgentDrawerOpen.value) {
  //   isAgentDrawerOpen.value = false;
  // }

  // 点击空白处取消节点高亮单选和多选
  activeNodeId.value = '';
  selectedNodeIds.value = [];

  // 若正处于拉线状态，点击空白处取消连线
  if (connectingSource.value) {
    connectingSource.value = null;
    return;
  }

  // 左键(button === 0)点击空白处：开启矩形拉框多选
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
    // 鼠标中键平移画布
    isPanning.value = true;
    startPan.x = e.clientX - pan.value.x;
    startPan.y = e.clientY - pan.value.y;
  }
}
// 4. 修改 handleCanvasMouseUp：结束框选
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
  contextMenu.canvasX = 160 + nodes.value.length * 35; contextMenu.canvasY = 160 + nodes.value.length * 35;
  createNodeFromContext(type);
}

function createNodeFromContext(type: 'text' | 'image') {
  const id = newId();
  const newNode: FlowNode = {
    id,
    type,
    title: type === 'text' ? '文本节点' : '图片节点',
    x: contextMenu.canvasX,
    y: contextMenu.canvasY,
    content: type === 'text' ? '' : undefined,
    url: type === 'image' ? '' : undefined
  };
  nodes.value.push(newNode);
  activeNodeId.value = id;
  contextMenu.visible = false;
}

function deleteNode(id: string) {
  const node = nodes.value.find(n => n.id === id);
  if (!node) return;
  const removed = connections.value.filter(c => c.from === id || c.to === id);
  deletedNode.value = { node: JSON.parse(JSON.stringify(node)), connections: removed };
  if (node.job_id) canvas.value.dismissed_job_ids.push(node.job_id);
  nodes.value = nodes.value.filter(n => n.id !== id);
  connections.value = connections.value.filter(c => c.from !== id && c.to !== id);
  referencedNodeIds.value = referencedNodeIds.value.filter(value => value !== id);
  selectedNodeIds.value = selectedNodeIds.value.filter(value => value !== id);
  if (activeNodeId.value === id) activeNodeId.value = '';
  if (aiTargetNodeId.value === id) aiTargetNodeId.value = '';
  if (connectingSource.value?.id === id) connectingSource.value = null;
  notice.value = '小框已删除，可以撤销。';
}
function undoDeleteNode() {
  const removed = deletedNode.value;
  if (!removed || nodes.value.some(n => n.id === removed.node.id)) return;
  nodes.value.push(removed.node);
  connections.value.push(...removed.connections.filter(c => nodes.value.some(n => n.id === c.from) && nodes.value.some(n => n.id === c.to)));
  if (removed.node.job_id) canvas.value.dismissed_job_ids = canvas.value.dismissed_job_ids.filter(id => id !== removed.node.job_id);
  activeNodeId.value = removed.node.id; deletedNode.value = null; notice.value = '已恢复删除的小框。';
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
// 记录拖拽开始时，所有选中节点的初始坐标
let dragStartNodePos: Record<string, { x: number; y: number }> = {};
let mouseStartCanvasPos = { x: 0, y: 0 };

function startDragNode(e: MouseEvent, node: FlowNode) {
  if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || (e.target as HTMLElement).closest('button,textarea,input,label,video,[draggable="true"]')) return;
  draggingNode = node;

  // 如果点击拖拽的节点不在已多选的列表里，则将当前节点设为唯一选中
  if (!selectedNodeIds.value.includes(node.id) && activeNodeId.value !== node.id) {
    activeNodeId.value = node.id;
    selectedNodeIds.value = [node.id];
  } else if (!selectedNodeIds.value.includes(node.id)) {
    selectedNodeIds.value.push(node.id);
  }

  // 记录按下时的画布实际坐标
  Object.assign(mouseStartCanvasPos, canvasPoint(e));

  // 记录所有当前选中节点的初始位置，用于多选同步位移
  dragStartNodePos = {};
  const allSelectedIds = new Set([...selectedNodeIds.value, activeNodeId.value].filter(Boolean));
  nodes.value.forEach(n => {
    if (allSelectedIds.has(n.id)) {
      dragStartNodePos[n.id] = { x: n.x, y: n.y };
    }
  });
}

// 辅助函数：精准获取节点端口圆心的相对偏移坐标
function getNodePortPos(node: FlowNode, type: 'in' | 'out') {
  // 根据节点类型精准获取卡片高度的中点（图片卡片高约280px，文本卡片高约240px）
  const cardHeight = node.type === 'image' ? 280 : node.type === 'text' ? 300 : 240;
  const centerY = node.y + cardHeight / 2;

  return {
    // 左端点(In)：x 在节点左边界；右端点(Out)：x 在节点右边界(宽248px)
    x: type === 'in' ? node.x : node.x + 248,
    y: centerY
  };
}
// 1. 修正 SVG 路径拼接（各坐标参数之间必须有空格分隔）
function calculateBezierPath(fromId: string, toId: string): string {
  const fromNode = nodes.value.find(n => n.id === fromId);
  const toNode = nodes.value.find(n => n.id === toId);
  if (!fromNode || !toNode) return '';

  // 起点：源节点右侧加号中心 (Out)
  const p1 = getNodePortPos(fromNode, 'out');
  // 终点：目标节点左侧加号中心 (In)
  const p2 = getNodePortPos(toNode, 'in');

  const dx = Math.max(Math.abs(p2.x - p1.x) * 0.5, 60);
  return `M ${p1.x} ${p1.y} C ${p1.x + dx} ${p1.y}, ${p2.x - dx} ${p2.y}, ${p2.x} ${p2.y}`;
}

// 2. 临时跟随鼠标的虚线：起点也严格对准加号中心
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

// 国际传播建议应用到节点
function applyGuidanceToNode() {
  const guideText = currentCountryGuide.value.promptText;
  if (activeNode.value && activeNode.value.type === 'text') {
    activeNode.value.content = activeNode.value.content
      ? `${activeNode.value.content}\n\n${guideText}`
      : guideText;
  } else {
    const newNodeId = newId();
    nodes.value.push({
      id: newNodeId,
      type: 'text',
      title: `${currentCountryGuide.value.name} 文化定向`,
      x: 200,
      y: 300,
      content: guideText
    });
    activeNodeId.value = newNodeId;
  }
  closeGuideModal();
}

function openGuideModal() { showGuideModal.value = true; }
function closeGuideModal() { showGuideModal.value = false; }
function selectCountry(code: string) { selectedCountryCode.value = code; }
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
onMounted(async () => {


  // 关键：检查 URL 参数或已有会话，直接进入视图 B
  const queryConvId = route.query.conv_id as string;
  if (queryConvId) {
    // 优先进入指定的会话
    await switchConversation(queryConvId);
  } else if (!currentConvId.value) {
    // 如果没有指定参数且当前没进入任何会话，直接自动打开最新的对话进入视图 B
    if (conversations.value.length > 0) {
      await switchConversation(conversations.value[0].id);
    } else {
      // 如果一个历史对话都没有，自动新建一个对话进入视图 B
      await createNewConversation();
    }
  }
});
</script>

<style scoped>
.video-review-feedback.blocked {
  border-color: rgba(234, 179, 8, .35);
  background: rgba(234, 179, 8, .06);
}
/* TV 频道导航交互按钮 */
/* 新增：左侧包裹容器，使 Logo 与 TV 按钮紧挨在一起 */
.nav-left {
  display: flex;
  align-items: center;
  gap: 16px; /* 控制两者之间的间距，如需更紧凑可调整为 12px ~ 14px */
}

/* TV 频道导航交互按钮：删除原有 left: 2vw; */
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

/* 电视图标容器 */
.tv-icon-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 电视 SVG */
.tv-svg {
  width: 18px;
  height: 18px;
  color: #94a3b8;
  transition: all 0.25s ease;
}

/* 模拟信号接收/正在连线小红点 */
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

  0%,
  100% {
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

/* 鼠标悬停动效：浮起、渐变外边框发光、天线与图标上跳 */
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

/* 点击激活状态 */
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
.node-title-input {
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

/* 参考节点标签排版 */
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

/* 拖拽释放提示区域 */
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

/* 鼠标拖拽出的蓝色透明选框 */
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

/* 顶部导航 */
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

/* 切换动效容器 */
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

/* ================= 视图 A：项目空间看板 ================= */
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

.project-card .version-tag {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.card-bottom {
  font-size: 11px;
  color: #94a3b8;
  text-align: right;
  font-weight: 500;
}

/* ================= 视图 B：暗色点阵网格画布 ================= */
/* 画布容器：平时是常规指针，只有中键/拖动画布时才显示小手 */
.canvas-viewport {
  flex: 1;
  width: 100%;
  height: 100%;
  position: relative;
  overflow: clip;
  user-select: none;
  cursor: default;
  /* 改为平时是默认指针，不再常驻小手 */
  background-color: #07090e;
  background-image: radial-gradient(rgba(255, 255, 255, 0.12) 1px, transparent 1px);
  background-size: 24px 24px;
}

/* 仅在按住拖动画布时显示抓取手势 */
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
  will-change: transform; /* 开启硬件加速，确保节点多时依然满帧跟手 */
}

/* 鼠标拖拽画布时关闭过渡动画，保证实时跟手 */
.canvas-plane.is-panning {
  transition: none;
}

/* 贝塞尔曲线与光点流动动画 */
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

/* 正在拉出的临时贝塞尔曲线（跟随鼠标） */
.connection-temp-path {
  fill: none;
  stroke: #818cf8;
  stroke-width: 2.5px;
  stroke-dasharray: 6 6;
  pointer-events: none;
  /* 关键：禁止阻挡鼠标点击目标节点加号 */
}

/* 作为起点的激活正圆（蓝紫色正圆高亮，不拉长） */
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

/* 目标待连接端点（柔和呼吸高亮，保持正圆） */
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

@keyframes pulseTarget {
  from {
    transform: translateY(-50%) scale(1);
  }

  to {
    transform: translateY(-50%) scale(1.25);
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

/* 节点通用卡片 */
/* 固定卡片尺寸与垂直居中参考系 */
/* 节点：鼠标放到节点卡片上时显示移动指针 move */
.canvas-node {
  position: absolute;
  width: 248px;
  background: #18191c;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.6);
  cursor: move;
  /* 鼠标悬浮到节点上呈现可拖拽手势 */
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

/* 节点内部文本区和输入框保留文字选择指针，避免误判 */
.text-body textarea,
.node-title-input {
  cursor: text;
}

/* 统一节点卡片的高度，确保端点严格在 50% 居中位置 */
.canvas-node.text {
  height: 300px;
}

.canvas-node.image {
  height: 280px;
}

.canvas-node.video {
  height: 240px;
}

/* 仅在被选中时显示发光边框 */
.canvas-node.selected {
  border-color: #818cf8 !important;
  box-shadow: 0 0 0 1.5px #818cf8, 0 12px 30px rgba(0, 0, 0, 0.7) !important;
}

/* 左右加号端口：严格在边框中线上居中 */
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

/* 左侧加号：圆心精确落在 x=0 */
.in-port {
  left: 0;
  transform: translate(-50%, -50%);
}

/* 右侧加号：圆心精确落在 x=248px */
.out-port {
  right: 0;
  transform: translate(50%, -50%);
}

/* 鼠标悬停显示 */
.canvas-node:hover .node-port {
  opacity: 1;
  pointer-events: auto;
}

/* 圆形外观保持正圆 */
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

/* 里面的加号字体与居中 */
.port-inner .plus-icon {
  font-size: 13px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 彻底删除之前重复添加的 ::after 伪元素，防止撑开变形 */
.in-port .port-inner::after,
.out-port .port-inner::after {
  content: none !important;
}

/* 悬停微高亮（保持正圆放大） */
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
  padding: 2px 4px;
  font-size: 12px;
  width: 90%;
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

/* 文本节点 */
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

/* 图片节点 */
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

/* 悬停滑出的上传胶囊按钮 */
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

/* 右键唤出快捷菜单 */
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

/* 悬浮控制按钮组 */
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

/* 右下角 Agent 悬浮球 */
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

/* 侧边滑出：Agent 对话与生成面板（严格固定在屏幕视口最右侧） */
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
  /* 提升层级，浮于所有节点和连线之上 */
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transform: translateX(100%);
  /* 默认隐藏在屏幕右侧外面 */
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.agent-flyout-drawer.open {
  transform: translateX(0);
  /* 展开时完美贴紧屏幕最右边缘滑出 */
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

.node-binding-banner {
  background: rgba(99, 102, 241, 0.12);
  padding: 6px 14px;
  font-size: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #a5b4fc;
}

.clear-bind {
  background: none;
  border: none;
  color: #818cf8;
  cursor: pointer;
  font-size: 15px;
}

.drawer-scroll-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.drawer-scroll-area>.ai-target-picker,
.drawer-scroll-area>.node-binding-banner,
.drawer-scroll-area>.drawer-spec-panel {
  flex-shrink: 0;
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

/* 生成完成：100% 满格绿色 */
.progress-bar-inner.succeeded {
  width: 100%;
  background: #10b981;
}

/* 失败或取消：100% 警示色 */
.progress-bar-inner.failed {
  width: 100%;
  background: #ef4444;
}

/* 生成中：不确定滚动条动画 */
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

/* 消息输入区域（增大整体高度与内边距） */
.drawer-input-box {
  flex-shrink: 0;
  padding: 12px 18px 14px;
  background: #0c0e12;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

/* 输入框本体放大：高度增加到 110px，字号提升至 14px，行高更宽松 */
.drawer-input-box textarea {
  width: 100%;
  height: clamp(80px, 14vh, 120px);
  background: #161820;
  border: 1px solid #282c37;
  border-radius: 10px;
  padding: 12px 14px;
  color: #fff;
  font-size: 14px;
  /* 原先为 12px */
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

/* 底部操作栏与发送按钮微调放大 */
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
  /* 增大按钮点击区域 */
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

.countries-tab-bar {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.country-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #172033;
  border: 1px solid #28374f;
  color: #cbd5e1;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}

.country-tab.active {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  border-color: #818cf8;
  color: #fff;
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
  width: 14px;
  height: 14px;
  border: 2px solid #64748b;
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
/* ================= 移动端暂不支持提示层 ================= */
.mobile-block-overlay {
  display: none; /* 桌面端默认完全隐藏 */
}

@media (max-width: 768px) {
  /* 移动端全屏弹层高优先级覆盖 */
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

  /* 移动端下隐藏原有工作台主体及导航，避免背景依然可滚动或接收手势 */
  .top-nav,
  .workspace-body,
  .floating-bottom-right,
  .guide-modal-mask {
    display: none !important;
  }
  /* 按钮组合容器 */
  .mobile-actions-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    margin-top: 28px;
  }

  /* 通用按钮胶囊质感 */
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

  /* 返回首页：低调微光边框 */
  .mobile-btn.home-btn {
    background: rgba(30, 41, 59, 0.7);
    color: #e2e8f0;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  /* TV 频道：主色高亮与霓虹渐变效果 */
  .mobile-btn.tv-btn {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(79, 70, 229, 0.45));
    border: 1px solid rgba(129, 140, 248, 0.5);
    color: #ffffff;
    box-shadow: 0 4px 20px -2px rgba(99, 102, 241, 0.35);
  }

  /* TV 图标与直播小红点 */
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
</style>
