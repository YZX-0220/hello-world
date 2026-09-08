<template>
  <div class="workspace-layout">
    <!-- 顶部导航栏 -->
    <header class="top-nav">
      <div class="brand">
        <div class="brand-avatar">H</div>
        <span class="brand-name">Hello World</span>
        <span class="sub-badge">国际传播特化 AI 视频工作台</span>
      </div>
      <div class="nav-actions">
        <router-link to="/settings/api" class="nav-link">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          API 配置中心
        </router-link>
        <button class="logout-btn" @click="handleLogout">退出登录</button>
      </div>
    </header>

    <!-- 三栏核心工作区 -->
    <div class="workspace-main">
      <!-- 左栏：对话列表 (侧边栏) -->
      <aside class="conversations-sidebar">
        <div class="sidebar-action">
          <button class="new-chat-btn" @click="createNewConversation">
            <span>+ 新建创作对话</span>
          </button>
        </div>
        <div class="conversation-list">
          <div 
            v-for="conv in conversations" 
            :key="conv.id" 
            class="conversation-item"
            :class="{ active: currentConvId === conv.id }"
            @click="switchConversation(conv.id)"
          >
            <div class="conv-title">{{ conv.title || '新对话' }}</div>
            <div class="conv-time">{{ formatTime(conv.updated_at) }}</div>
          </div>
        </div>
      </aside>

      <!-- 中间：Agent 对话流 -->
      <section class="chat-section">
        <div class="chat-header">
          <div class="chat-header-info">
            <h2 class="chat-title">{{ activeConversation?.title || '新创作对话' }}</h2>
            <p class="chat-sub">输入跨文化叙事想法，Agent 会自动润色提示词并组装右侧分镜方案</p>
          </div>
          <div class="chat-options">
            <label class="toggle-label">
              <input type="checkbox" v-model="webSearchEnabled" />
              <span>海外热点联网搜索</span>
            </label>
          </div>
        </div>

        <!-- 消息列表区 -->
        <div class="messages-container" ref="messagesContainerRef">
          <div v-for="msg in messages" :key="msg.id" :class="['message-row', msg.role]">
            <div class="avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
            <div class="bubble">
              <div class="msg-content">{{ msg.content }}</div>
              <!-- 联网资料引用展示 -->
              <div v-if="msg.citations && msg.citations.length > 0" class="citations-box">
                <div class="citations-title">参考海外资讯/热点：</div>
                <div v-for="(cite, cIdx) in msg.citations" :key="cIdx" class="citation-item">
                  <a :href="cite.url" target="_blank" rel="noopener">[{{ cIdx + 1 }}] {{ cite.title }}</a>
                  <p>{{ cite.snippet }}</p>
                </div>
              </div>
              <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
            </div>
          </div>

          <div v-if="isAgentResponding" class="message-row assistant">
            <div class="avatar">AI</div>
            <div class="bubble thinking">
              <span class="loading-spinner"></span>
              <span>正在分析国际传播受众偏好与镜头语言...</span>
            </div>
          </div>
        </div>

        <!-- 输入控制台 -->
        <div class="chat-input-area">
          <textarea 
            v-model="inputContent" 
            placeholder="描述你想表达的文化故事或视觉构想（如：向青年游客展示雨夜古城门，电影感缓慢推进）..."
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>
          <div class="input-actions">
            <span class="input-hint">Enter 发送，Shift + Enter 换行</span>
            <button 
              class="send-btn" 
              :disabled="!inputContent.trim() || isAgentResponding"
              @click="sendMessage"
            >
              发送给 Agent
            </button>
          </div>
        </div>
      </section>

      <!-- 右栏：结构化视频方案 & 视频任务生成 -->
      <aside class="brief-panel">
        <div class="panel-tab-title">
          <h3>分镜与视频方案</h3>
          <span class="version-tag">v{{ project?.current_spec_version || 0 }}</span>
        </div>

        <!-- 方案状态提示与确认按钮 -->
        <div class="spec-status-bar">
          <div class="status-indicator">
            <span class="dot" :class="{ confirmed: project?.is_current_version_confirmed }"></span>
            <span>{{ project?.is_current_version_confirmed ? '方案已确认可生成' : '方案有变更，待确认' }}</span>
          </div>
          <button 
            class="confirm-btn" 
            :disabled="project?.is_current_version_confirmed"
            @click="confirmProjectSpec"
          >
            确认当前方案
          </button>
        </div>

        <!-- 方案字段详情展示 -->
        <div class="spec-details-list">
          <div class="spec-field-item">
            <label>传播目标 / 受众</label>
            <div class="spec-val">
              {{ spec.objective || '暂未指定目标' }} · {{ spec.audience || '大众' }} ({{ spec.language || 'zh-CN' }})
            </div>
          </div>

          <div class="spec-field-item">
            <label>生成模式 & 规格</label>
            <div class="spec-val">
              模式: {{ spec.mode || 'text_to_video' }} | 画幅: {{ spec.aspect_ratio || '16:9' }} | 时长: {{ spec.duration_seconds || 5 }}s
            </div>
          </div>

          <div class="spec-field-item">
            <label>视觉主体与场景</label>
            <div class="spec-val">
              <strong>主体：</strong>{{ spec.subject || '无' }}<br />
              <strong>场景：</strong>{{ spec.scene || '无' }}
            </div>
          </div>

          <div class="spec-field-item">
            <label>镜头与光影设计</label>
            <div class="spec-val">
              <strong>运镜：</strong>{{ spec.camera || '默认推进' }}<br />
              <strong>光线：</strong>{{ spec.lighting || '电影质感' }}
            </div>
          </div>

          <div class="spec-field-item">
            <label>推荐视频提示词 (Suggested Prompt)</label>
            <div class="prompt-code-box">{{ project?.suggested_prompt || '等待 Agent 润色生成...' }}</div>
          </div>
        </div>

        <!-- 视频生成任务面板 -->
        <div class="job-action-card">
          <div class="card-inner-title">创建渲染任务</div>
          <div class="job-field">
            <label>选用视频 API 配置：</label>
            <select v-model="selectedApiConfigId">
              <option v-for="cfg in apiConfigs" :key="cfg.id" :value="cfg.id">
                {{ cfg.display_name }} ({{ cfg.remote_model_id }})
              </option>
            </select>
          </div>

          <button 
            class="create-job-btn" 
            :disabled="!project?.is_current_version_confirmed || isSubmittingJob || !selectedApiConfigId"
            @click="submitVideoJob"
          >
            {{ isSubmittingJob ? '正在提交给视频厂商...' : '一键调用视频底模生成' }}
          </button>
        </div>

        <!-- 任务结果/进度状态展示 -->
        <div v-if="activeJob" class="active-job-preview">
          <div class="preview-header">
            <span>任务状态: <strong :class="'job-' + activeJob.status">{{ activeJob.status }}</strong></span>
            <span v-if="activeJob.progress !== null">{{ activeJob.progress }}%</span>
          </div>

          <!-- 视频就绪：直接播放 -->
          <div v-if="activeJob.result_asset_id" class="video-container">
            <video 
              controls 
              autoplay 
              loop
              :src="`/api/v1/assets/${activeJob.result_asset_id}/content`"
            ></video>
          </div>

          <!-- 渲染中：进度显示 -->
          <div v-else class="job-progress-panel">
            <div class="progress-bar-bg">
              <div class="progress-bar-inner" :style="{ width: (activeJob.progress || 20) + '%' }"></div>
            </div>
            <p class="progress-desc">
              {{ activeJob.download_status === 'stored' ? '渲染完成' : '厂商正在生成，系统正自动退避轮询...' }}
            </p>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import request from '@/utils/request';
import type { 
  ConversationView, 
  MessageView, 
  VideoProjectView, 
  VideoBrief, 
  VideoJobView, 
  VideoApiConfigView 
} from '@/types/api';

const router = useRouter();

// 1. 状态定义
const conversations = ref<ConversationView[]>([]);
const currentConvId = ref<string>('');
const messages = ref<MessageView[]>([]);
const inputContent = ref('');
const webSearchEnabled = ref(false);
const isAgentResponding = ref(false);
const messagesContainerRef = ref<HTMLElement | null>(null);

// 项目与方案状态
const project = ref<VideoProjectView | null>(null);
const spec = computed<VideoBrief>(() => project.value?.current_spec || ({} as VideoBrief));

// 视频接口配置与任务
const apiConfigs = ref<VideoApiConfigView[]>([]);
const selectedApiConfigId = ref('');
const isSubmittingJob = ref(false);
const activeJob = ref<VideoJobView | null>(null);
let pollTimer: number | null = null;

const activeConversation = computed(() => 
  conversations.value.find(c => c.id === currentConvId.value)
);

// 2. 初始化加载
onMounted(async () => {
  await loadConversations();
  await loadApiConfigs();
});

// 加载历史对话
async function loadConversations() {
  try {
    const res: any = await request.get('/conversations');
    conversations.value = res.items || [];
    if (conversations.value.length > 0) {
      await switchConversation(conversations.value[0].id);
    } else {
      await createNewConversation();
    }
  } catch (err: any) {
    console.error('加载对话失败', err);
  }
}

// 加载用户保存的可用视频配置
async function loadApiConfigs() {
  try {
    const res: any = await request.get('/video-api-configs');
    apiConfigs.value = res.items || [];
    if (apiConfigs.value.length > 0) {
      selectedApiConfigId.value = apiConfigs.value[0].id;
    }
  } catch (err) {
    console.warn('暂无可用 API 配置');
  }
}

// 切换当前对话
async function switchConversation(convId: string) {
  currentConvId.value = convId;
  activeJob.value = null;
  if (pollTimer) clearInterval(pollTimer);

  // 1. 获取消息历史
  try {
    const msgRes: any = await request.get(`/conversations/${convId}/messages`);
    messages.value = msgRes.items || [];
    scrollToBottom();
  } catch (err) {
    messages.value = [];
  }

  // 2. 获取当前视频项目与最新方案
  try {
    const projRes: any = await request.get(`/conversations/${convId}/project`);
    project.value = projRes;
  } catch (err) {
    project.value = null;
  }
}

// 新建对话
async function createNewConversation() {
  try {
    const res: any = await request.post('/conversations', {
      title: '新创作对话'
    });
    conversations.value.unshift(res.conversation);
    currentConvId.value = res.conversation.id;
    project.value = res.project;
    messages.value = [];
  } catch (err: any) {
    alert(err.message || '新建对话失败');
  }
}

// 3. 发送消息并调用后端 Agent 润色
async function sendMessage() {
  if (!inputContent.value.trim() || isAgentResponding.value || !currentConvId.value) return;

  const content = inputContent.value;
  inputContent.value = '';
  isAgentResponding.value = true;

  // 生成客户端消息请求编号 (UUID 规范)
  const clientRequestId = crypto.randomUUID();

  try {
    const res: any = await request.post(`/conversations/${currentConvId.value}/messages`, {
      content,
      client_request_id: clientRequestId,
      web_search_enabled: webSearchEnabled.value,
      retry_failed: false
    });

    // 成功完成，插入用户消息和 AI 消息
    if (res.user_message) messages.value.push(res.user_message);
    if (res.assistant_message) messages.value.push(res.assistant_message);
    
    // 方案已由 Agent 自动根据国际传播叙事规则修改并升版
    if (res.project) {
      project.value = res.project;
    }
    scrollToBottom();
  } catch (err: any) {
    alert(err.message || '文本 Agent 处理异常，请重试');
  } finally {
    isAgentResponding.value = false;
  }
}

// 4. 确认视频方案版本（生成前必须由用户明确确认）
async function confirmProjectSpec() {
  if (!currentConvId.value || !project.value) return;
  try {
    const res: any = await request.post(`/conversations/${currentConvId.value}/project/confirm`, {
      spec_version: project.value.current_spec_version
    });
    project.value = res;
  } catch (err: any) {
    alert(err.message || '确认版本失败，请刷新获取最新版本');
  }
}

// 5. 提交视频生成任务（带幂等编号与自备 API Key 配置）
async function submitVideoJob() {
  if (!project.value || !project.value.is_current_version_confirmed) {
    alert('请先确认当前方案版本！');
    return;
  }
  if (!selectedApiConfigId.value) {
    alert('请选择用于调用的视频 API 配置');
    return;
  }

  isSubmittingJob.value = true;
  const idempotencyKey = crypto.randomUUID(); // 防重复点击幂等编号

  try {
    const res: any = await request.post(
      '/video-jobs',
      {
        conversation_id: currentConvId.value,
        project_id: project.value.id,
        spec_version: project.value.current_spec_version,
        api_config_id: selectedApiConfigId.value,
        mode: spec.value.mode || 'text_to_video',
        generation_options: {
          resolution: '1080p',
          generate_audio: false
        },
        previous_job_id: null
      },
      {
        headers: {
          'Idempotency-Key': idempotencyKey
        }
      }
    );

    activeJob.value = res;
    // 启动退避轮询监控生成进度
    startPollingJob(res.id, res.poll_after_seconds || 4);
  } catch (err: any) {
    alert(err.message || '视频任务提交失败');
  } finally {
    isSubmittingJob.value = false;
  }
}

// 6. 按照契约 poll_after_seconds 进行智能轮询
function startPollingJob(jobId: string, intervalSec: number) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = window.setInterval(async () => {
    try {
      const res: any = await request.get(`/video-jobs/${jobId}`);
      activeJob.value = res;

      // 如果已到达终态（成功或失败），停止轮询
      if (['succeeded', 'failed', 'cancelled'].includes(res.status)) {
        if (pollTimer) clearInterval(pollTimer);
      }
    } catch (e) {
      console.warn('查询任务状态临时异常，继续退避轮询');
    }
  }, Math.max(intervalSec, 3) * 1000);
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainerRef.value) {
      messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight;
    }
  });
}

function formatTime(isoStr?: string | null) {
  if (!isoStr) return '';
  return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

async function handleLogout() {
  try {
    await request.post('/auth/logout');
  } finally {
    router.push('/login');
  }
}
</script>

<style scoped>
/* 全屏工作区主框架 */
.workspace-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  background-color: #090c14;
  color: #f1f5f9;
  font-size: 15px;
  overflow: hidden;
}

/* 顶部导航：高度撑起到 64px */
.top-nav {
  height: 64px;
  min-height: 64px;
  border-bottom: 1px solid #1e2638;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background-color: #0f1422;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-avatar {
  width: 32px;
  height: 32px;
  background-color: #6366f1;
  color: #fff;
  font-weight: bold;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}
.brand-name {
  font-weight: 600;
  color: #ffffff;
  font-size: 18px;
}
.sub-badge {
  font-size: 13px;
  background-color: #1e293b;
  color: #94a3b8;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid #334155;
}
.nav-actions {
  display: flex;
  align-items: center;
  gap: 20px;
}
.nav-link {
  color: #cbd5e1;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  padding: 6px 12px;
  border-radius: 6px;
  transition: all 0.15s;
}
.nav-link:hover {
  background-color: #1e293b;
  color: #ffffff;
}
.nav-link .icon { width: 18px; height: 18px; }
.logout-btn {
  background: transparent;
  border: 1px solid #334155;
  color: #cbd5e1;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}
.logout-btn:hover {
  background-color: #1e293b;
  color: #f8fafc;
  border-color: #64748b;
}

/* 三栏主容器 */
.workspace-main {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* 1. 左栏：历史对话列表（加宽至 280px） */
.conversations-sidebar {
  width: 280px;
  min-width: 280px;
  border-right: 1px solid #1a2233;
  display: flex;
  flex-direction: column;
  background-color: #0b0f19;
}
.sidebar-action {
  padding: 16px;
}
.new-chat-btn {
  width: 100%;
  padding: 12px;
  background-color: #1e2738;
  color: #f8fafc;
  border: 1px solid #2d3b55;
  border-radius: 8px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 500;
  transition: all 0.2s;
}
.new-chat-btn:hover {
  background-color: #2b3852;
  border-color: #6366f1;
}
.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px;
}
.conversation-item {
  padding: 14px 16px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 6px;
  transition: background 0.15s;
}
.conversation-item:hover { background-color: #161e2e; }
.conversation-item.active {
  background-color: #1c263b;
  border-left: 4px solid #6366f1;
}
.conv-title {
  color: #f1f5f9;
  font-size: 15px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conv-time {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

/* 2. 中间：聊天交互区 */
.chat-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  background-color: #0d121f;
  border-right: 1px solid #1a2233;
}
.chat-header {
  padding: 16px 24px;
  border-bottom: 1px solid #1a2233;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #0f1524;
}
.chat-title {
  font-size: 18px;
  font-weight: 600;
  color: #f8fafc;
}
.chat-sub {
  font-size: 13px;
  color: #94a3b8;
  margin-top: 2px;
}
.toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #cbd5e1;
  cursor: pointer;
}
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.message-row {
  display: flex;
  gap: 14px;
  max-width: 80%;
}
.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  flex-shrink: 0;
}
.user .avatar { background-color: #4f46e5; color: #fff; }
.assistant .avatar { background-color: #059669; color: #fff; }
.bubble {
  background-color: #172033;
  padding: 14px 18px;
  border-radius: 10px;
  color: #f1f5f9;
  font-size: 15px;
  line-height: 1.6;
}
.user .bubble { background-color: #263654; }
.bubble.thinking {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #94a3b8;
}
.msg-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 6px;
  text-align: right;
}
.citations-box {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #334155;
  font-size: 13px;
}
.citations-title { color: #38bdf8; margin-bottom: 6px; font-weight: 500; }
.citation-item { margin-bottom: 6px; }
.citation-item a { color: #60a5fa; text-decoration: none; font-weight: 500; }

/* 聊天输入框区域（加大加高） */
.chat-input-area {
  padding: 20px 28px;
  border-top: 1px solid #1a2233;
  background-color: #0b0f19;
}
.chat-input-area textarea {
  width: 100%;
  height: 90px;
  background-color: #141b2a;
  border: 1px solid #243147;
  border-radius: 8px;
  padding: 12px 16px;
  color: #fff;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  outline: none;
}
.chat-input-area textarea:focus { border-color: #6366f1; }
.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}
.input-hint { font-size: 13px; color: #94a3b8; }
.send-btn {
  background-color: #6366f1;
  color: #fff;
  border: none;
  padding: 10px 22px;
  border-radius: 6px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
}
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* 3. 右栏：分镜方案与生成面板（加宽至 460px） */
.brief-panel {
  width: 460px;
  min-width: 460px;
  background-color: #0b0f19;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.panel-tab-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-tab-title h3 {
  font-size: 17px;
  color: #f8fafc;
}
.version-tag {
  background-color: #1e293b;
  color: #38bdf8;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
}
.spec-status-bar {
  background-color: #131b2c;
  border: 1px solid #1f2b44;
  padding: 12px 16px;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #cbd5e1;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #eab308;
}
.dot.confirmed { background-color: #10b981; }
.confirm-btn {
  background-color: #1e293b;
  color: #38bdf8;
  border: 1px solid #334155;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}
.confirm-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.spec-details-list {
  background-color: #121827;
  border: 1px solid #1e273d;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.spec-field-item label {
  display: block;
  font-size: 13px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.spec-val {
  font-size: 14px;
  color: #e2e8f0;
  line-height: 1.5;
}
.prompt-code-box {
  background-color: #0b0e17;
  border: 1px solid #1c2639;
  padding: 12px;
  border-radius: 6px;
  font-family: monospace;
  font-size: 13px;
  color: #a5f3fc;
  max-height: 120px;
  overflow-y: auto;
  word-break: break-all;
  line-height: 1.4;
}

/* 任务卡片 */
.job-action-card {
  background-color: #121827;
  border: 1px solid #1e273d;
  border-radius: 10px;
  padding: 18px;
}
.card-inner-title {
  font-size: 16px;
  font-weight: 600;
  color: #f8fafc;
  margin-bottom: 14px;
}
.job-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}
.job-field label {
  font-size: 14px;
  color: #cbd5e1;
}
.job-field select {
  background-color: #1a2336;
  border: 1px solid #2d3b55;
  padding: 10px 12px;
  color: #fff;
  border-radius: 6px;
  font-size: 14px;
}
.create-job-btn {
  width: 100%;
  background-color: #10b981;
  color: #fff;
  border: none;
  padding: 12px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  font-size: 15px;
}
.create-job-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* 任务结果 */
.active-job-preview {
  background-color: #121827;
  border: 1px solid #1e273d;
  border-radius: 10px;
  padding: 16px;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  margin-bottom: 12px;
}
.job-succeeded { color: #10b981; }
.job-running, .job-queued { color: #38bdf8; }
.job-failed { color: #ef4444; }

.video-container video {
  width: 100%;
  border-radius: 8px;
  background-color: #000;
}
.progress-bar-bg {
  width: 100%;
  height: 8px;
  background-color: #1e293b;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}
.progress-bar-inner {
  height: 100%;
  background-color: #38bdf8;
  transition: width 0.3s;
}
.progress-desc {
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
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
  to { transform: rotate(360deg); }
}
</style>