<template>
  <div class="workspace-layout">
    <!-- 顶部导航栏 -->
    <header class="top-nav">
      <router-link to="/" class="brand-link" title="点击返回品牌首页">
        <div class="brand">
          <div class="brand-avatar">H</div>
          <span class="brand-name">Hello World</span>
          <span class="sub-badge desktop-only">国际传播特化 AI 视频工作台</span>
        </div>
      </router-link>
      <div class="nav-actions">
        <router-link to="/settings/api" class="nav-link" title="点击进入 API 配置中心">
          <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
          <span class="desktop-only">API 配置中心</span>
        </router-link>
        <button class="logout-btn" @click="handleLogout" title="退出当前登录状态">退出登录</button>
      </div>
    </header>

    <!-- 视图平滑推拉切换容器 -->
    <div class="workspace-body">
      <Transition name="slide-left" mode="out-in">
        
        <!-- ================= 视图 A：创作项目空间看板 ================= -->
        <main v-if="!currentConvId" key="view-a" class="board-container">
          <div class="board-header">
            <h2 class="board-title">创作项目空间</h2>
            <p class="board-sub">选择历史对话继续创作，或点击中央加号开启新视听方案</p>
          </div>

          <div class="cards-grid">
            <!-- 新建正方形卡片 -->
            <div class="square-card add-card" @click="createNewConversation">
              <div class="plus-icon">+</div>
              <span class="add-text">{{ isCreatingConv ? '正在初始化...' : '开启新创作对话' }}</span>
              <div class="add-glow"></div>
            </div>

            <!-- 历史对话正方形卡片列表 (ID 哈希绑定固定颜色) -->
            <div 
              v-for="conv in conversations" 
              :key="conv.id" 
              class="square-card project-card"
              :style="getCardColorStyle(conv.id)"
              @click="switchConversation(conv.id)"
            >
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

        <!-- ================= 视图 B：聚焦对话与方案工作台 ================= -->
        <div v-else key="view-b" class="workspace-main">
          
          <!-- 中间：Agent 叙事工作流 -->
          <section class="chat-section">
            <div class="chat-header">
              <div class="chat-header-main">
                <button class="back-space-btn" title="返回项目空间看板" @click="backToProjectSpace">
                  <svg class="back-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                  </svg>
                  <span>项目空间</span>
                </button>

                <div class="chat-title-group">
                  <h2 class="chat-title">{{ activeConversation?.title || '新创作对话' }}</h2>
                  <p class="chat-sub desktop-only">与国际传播 Agent 深度构思分镜，右侧方案将实时同步更新</p>
                </div>
              </div>

              <div class="chat-actions-group">
                <!-- 手机端专属按钮：点击弹出右侧分镜方案抽屉 -->
                <button class="mobile-brief-toggle mobile-only" @click="openMobileBriefDrawer">
                  <svg class="brief-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span>方案</span>
                  <span class="brief-dot" v-if="!project?.is_current_version_confirmed"></span>
                </button>

                <!-- 国际传播指导按钮 -->
                <button class="global-guide-btn" @click="openGuideModal">
                  <svg class="globe-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>国际传播指导</span>
                </button>
              </div>
            </div>

            <!-- 消息列表 -->
            <div class="messages-container" ref="messagesContainerRef">
              <div v-for="msg in messages" :key="msg.id" :class="['message-row', msg.role]">
                <div class="avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
                <div class="bubble">
                  <div class="msg-content" v-html="renderMd(msg.content)"></div>

                  <div v-if="msg.citations && msg.citations.length > 0" class="citations-fold">
                    <div class="citations-toggle" @click="toggleCitations(msg.id)">
                      <span>🔍 联网参考了 {{ msg.citations.length }} 条海外资讯 (点击{{ openCitations[msg.id] ? '收起' : '查看' }})</span>
                    </div>
                    <div v-if="openCitations[msg.id]" class="citations-body">
                      <div v-for="(cite, cIdx) in msg.citations" :key="cIdx" class="cite-row">
                        <a :href="cite.url" target="_blank" rel="noopener">[{{ cIdx + 1 }}] {{ cite.title }}</a>
                      </div>
                    </div>
                  </div>
                  <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
                </div>
              </div>

              <div v-if="isAgentResponding" class="message-row assistant">
                <div class="avatar">AI</div>
                <div class="bubble thinking">
                  <span class="loading-spinner"></span>
                  <span>正在分析分众文化审美偏好并优化视听语言...</span>
                </div>
              </div>
            </div>

            <!-- 消息发送区 -->
            <div class="chat-input-area">
              <textarea 
                ref="textareaRef"
                v-model="inputContent" 
                placeholder="描述你想表达的故事或视觉构想（可点击上方“国际传播指导”注入分众建议）..."
                @keydown.enter.exact.prevent="sendMessage"
              ></textarea>
              <div class="input-actions">
                <span class="input-hint desktop-only">Enter 发送，Shift + Enter 换行</span>
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

          <!-- 右栏：分镜与视频方案面板（电脑端常驻，手机端作为弹层展示） -->
          <aside 
            class="brief-panel" 
            :class="{ 'mobile-drawer-open': isMobileBriefOpen }"
          >
            <!-- 手机端抽屉顶部关闭头 -->
            <div class="drawer-header mobile-only">
              <span class="drawer-title">分镜与方案配置</span>
              <button class="drawer-close-btn" @click="closeMobileBriefDrawer">✕ 关闭</button>
            </div>

            <div class="panel-tab-title">
              <h3>分镜与视频方案</h3>
              <span class="version-tag">版本 v{{ project?.current_spec_version || 0 }}</span>
            </div>

            <div class="spec-status-bar">
              <div class="status-indicator">
                <span class="dot-fixed"></span>
                <span>{{ project?.is_current_version_confirmed ? '方案已就绪，可创建生成' : '方案有更新，请先确认' }}</span>
              </div>
              <button 
                class="confirm-btn" 
                :disabled="project?.is_current_version_confirmed"
                @click="confirmProjectSpec"
              >
                {{ project?.is_current_version_confirmed ? '已确认方案' : '确认当前方案' }}
              </button>
            </div>

            <div class="spec-details-list">
              <div class="spec-field-item">
                <label>传播目标 / 受众 / 语言</label>
                <div class="spec-val">
                  <strong>目标：</strong>{{ spec.objective || '未指定' }}<br />
                  <strong>受众：</strong>{{ spec.audience || '大众受众' }} · <strong>语言：</strong>{{ spec.language || 'zh-CN' }}
                </div>
              </div>

              <div class="spec-field-item">
                <label>生成规格与视觉风格</label>
                <div class="spec-val">
                  <strong>模式：</strong>{{ spec.mode || 'text_to_video' }} | <strong>画幅：</strong>{{ spec.aspect_ratio || '16:9' }} | <strong>时长：</strong>{{ spec.duration_seconds || 5 }}s<br />
                  <strong>风格：</strong>{{ spec.visual_style || '写实电影质感' }}
                </div>
              </div>

              <div class="spec-field-item">
                <label>视觉主体与场景环境</label>
                <div class="spec-val">
                  <strong>主体：</strong>{{ spec.subject || '无特定主体' }}<br />
                  <strong>场景：</strong>{{ spec.scene || '默认背景' }}
                </div>
              </div>

              <div class="spec-field-item">
                <label>镜头运镜、动作与光影</label>
                <div class="spec-val">
                  <strong>运镜：</strong>{{ spec.camera || '缓慢推进' }}<br />
                  <strong>动作：</strong>{{ spec.motion || '自然动态' }}<br />
                  <strong>光影：</strong>{{ spec.lighting || '电影氛围光' }}
                </div>
              </div>

              <div class="spec-field-item" v-if="spec.narration">
                <label>配音旁白 (Narration)</label>
                <div class="spec-val">{{ spec.narration }}</div>
              </div>

              <div class="spec-field-item" v-if="spec.negative_prompt">
                <label>负面提示词 (Negative)</label>
                <div class="spec-val">{{ spec.negative_prompt }}</div>
              </div>

              <div class="spec-field-item">
                <label>推荐视频提示词 (Suggested Prompt)</label>
                <div class="prompt-code-box">{{ project?.suggested_prompt || '等待 Agent 整理提示词...' }}</div>
              </div>
            </div>

            <!-- 视频生成任务板块 -->
            <div class="job-action-card">
              <div class="card-inner-title">生成视频任务</div>
              <div class="job-field">
                <label>选用视频 API 配置：</label>
                <select v-model="selectedApiConfigId">
                  <option value="platform">⚡ 平台官方体验通道（每用户每日限 1 次）</option>
                  <option v-for="cfg in apiConfigs" :key="cfg.id" :value="cfg.id">
                    🔑 {{ cfg.display_name }} ({{ cfg.remote_model_id }})
                  </option>
                </select>
              </div>

              <button 
                class="create-job-btn" 
                :disabled="!project?.is_current_version_confirmed || isSubmittingJob || !selectedApiConfigId"
                @click="submitVideoJob"
              >
                {{ isSubmittingJob ? '正在提交给底模厂商...' : '一键调用视频底模生成' }}
              </button>
            </div>

            <!-- 任务状态与结果视频展示 -->
            <div v-if="activeJob" class="active-job-preview">
              <div class="preview-header">
                <span>任务状态: <strong :class="'job-' + activeJob.status">{{ activeJob.status }}</strong></span>
                <span v-if="activeJob.progress !== null">{{ activeJob.progress }}%</span>
              </div>

              <div v-if="activeJob.result_asset_id" class="video-container">
                <video 
                  controls 
                  autoplay 
                  loop
                  :src="`/api/v1/assets/${activeJob.result_asset_id}/content`"
                ></video>
              </div>

              <div v-else class="job-progress-panel">
                <div class="progress-bar-bg">
                  <div class="progress-bar-inner" :style="{ width: (activeJob.progress || 25) + '%' }"></div>
                </div>
                <p class="progress-desc">
                  {{ activeJob.download_status === 'stored' ? '视频生成完成' : '视频渲染中，系统智能轮询状态...' }}
                </p>
              </div>
            </div>
          </aside>

          <!-- 手机端抽屉背景遮罩 -->
          <div 
            v-if="isMobileBriefOpen" 
            class="mobile-drawer-mask mobile-only" 
            @click="closeMobileBriefDrawer"
          ></div>

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
          <button 
            v-for="country in countryList" 
            :key="country.code"
            class="country-tab"
            :class="{ active: selectedCountryCode === country.code }"
            @click="selectCountry(country.code)"
          >
            <span class="flag-icon">{{ country.flag }}</span>
            <span>{{ country.name }}</span>
          </button>
        </div>

        <div class="guidance-content-box">
          <div class="guidance-header">
            <h4 class="country-target-name">
              {{ currentCountryGuide.name }}受众视听特征与叙事建议
            </h4>
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
            <div class="snippet-label">可注入对话框的特化创作指令：</div>
            <div class="snippet-text">{{ currentCountryGuide.promptText }}</div>
          </div>
        </div>

        <div class="guide-modal-footer">
          <span class="footer-tip desktop-only">点击下方按钮可直接把针对该国的视听要求填入对话框</span>
          <button class="apply-to-chat-btn" @click="applyGuidanceToInput">
            加入对话框
          </button>
        </div>
      </div>
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

const conversations = ref<ConversationView[]>([]);
const currentConvId = ref<string>('');
const messages = ref<MessageView[]>([]);
const inputContent = ref('');
const isAgentResponding = ref(false);
const isCreatingConv = ref(false);
const isMobileBriefOpen = ref(false); // 手机端分镜方案抽屉状态
const messagesContainerRef = ref<HTMLElement | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);

const project = ref<VideoProjectView | null>(null);
const spec = computed<VideoBrief>(() => project.value?.current_spec || ({} as VideoBrief));

const apiConfigs = ref<VideoApiConfigView[]>([]);
const selectedApiConfigId = ref('platform');
const isSubmittingJob = ref(false);
const activeJob = ref<VideoJobView | null>(null);
let pollTimer: number | null = null;

const openCitations = reactive<Record<string, boolean>>({});

// 国际传播指导数据
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
  name: string;
  lang: string;
  aesthetic: string;
  narrative: string;
  taboo: string;
  promptText: string;
}> = {
  US: {
    name: '美国',
    lang: '英语 (en-US)',
    aesthetic: '偏好高对比度动态视觉、明快紧凑的运镜剪辑与强烈的视觉奇观冲击；喜欢自然抓人眼球的开门见山式镜头。',
    narrative: '侧重个人英雄主义、个体真实经历与温情日常叙事，避免空洞说教，强调平等交流与自然共鸣。',
    taboo: '注意避免任何形式的刻板印象、种族敏感符号或过度主旋律视角的宏大叙事灌输。',
    promptText: '【国际传播受众：美国】请采用写实电影画质、高动态光影与明快节奏推进。注重以生动微观的个体视角展开，弱化宏大概念，重点强调真实烟火气与情感共鸣。'
  },
  FR: {
    name: '法国',
    lang: '法语 / 英语 (fr-FR)',
    aesthetic: '极为看重画面诗意、自然光影质感与艺术构图。偏好低饱和度、胶片颗粒感及留白的浪漫慢镜头。',
    narrative: '偏爱思辨性与哲学深意，喜欢讲述人与自然、传统工艺或慢生活的意境美，崇尚原生态与个性化表达。',
    taboo: '反感工业化流水线感过重或过于喧闹刺眼的塑料 CG 感；避免直接灌输式说理。',
    promptText: '【国际传播受众：法国】请运用胶片质感、柔和自然光与富有诗意的长镜头推拉。镜头语言需具有艺术留白与慢生活审美，呈现兼具哲思与优雅的文化意境。'
  },
  JP: {
    name: '日本',
    lang: '日语 (ja-JP)',
    aesthetic: '追求“物哀”与细腻治愈审美。偏好清新微暖的色调、柔光运镜、对季节流转与细微声画动作（如水滴、风吹落叶）的捕捉。',
    narrative: '长于以小见大，从生活细节、人情羁绊与匠人精神中展现文化底蕴，容易被纯粹专注、平和克制的情感打动。',
    taboo: '避免夸张喧嚣的肢体冲突与生硬的情绪宣泄；慎用容易引发历史语境争议的图腾符号。',
    promptText: '【国际传播受众：日本】请采用日系清新胶片色调与柔美漫射光，运镜平稳细腻。重点捕捉微观场景细节与人情温暖，营造内敛治愈的视听共情体验。'
  },
  IN: {
    name: '印度',
    lang: '印地语 / 英语 (hi-IN / en-IN)',
    aesthetic: '热爱浓郁明丽的高饱和色彩（暖黄、翠绿、朱红等），青睐富有韵律感、富丽堂皇且充满生命力的镜头动势。',
    narrative: '极为看重家庭团聚、传统节日氛围与富有感染力的生活仪式感，偏向乐观向上、热烈欢快的叙事弧线。',
    taboo: '避免冷色调或沉闷压抑的灰暗构图；注意规避宗教习俗与特定饮食层面的文化冒犯。',
    promptText: '【国际传播受众：印度】请采用高饱和度暖色调与富丽光影，运镜富有节奏与活力。突出热烈欢快的节日氛围或家庭人际温情，展现充满蓬勃生命力的视听画面。'
  },
  DE: {
    name: '德国',
    lang: '德语 / 英语 (de-DE)',
    aesthetic: '崇尚极简主义与理性几何构图。偏爱冷峻清晰的工业秩序感、冷色系自然光线与一丝不苟的透视对称。',
    narrative: '重视事实逻辑、精密工艺原理与生态可持续理念，对结构清晰、严谨真实的叙事接受度最高。',
    taboo: '排斥虚假浮夸、逻辑前后矛盾或逻辑煽情的画面设计；注重规则与严谨度。',
    promptText: '【国际传播受众：德国】请采用严谨的几何对称构图与低饱和冷色调电影光影。运镜克制平稳，强调画面主体的结构质感与逻辑严密性。'
  },
  GB: {
    name: '英国',
    lang: '英式英语 (en-GB)',
    aesthetic: '偏好古典优雅、阴雨朦胧的氛围光影（油画质感、历史厚重感、冷色调雾气感与复古色泽）。',
    narrative: '青睐英式幽默、含蓄克制以及对历史文化遗产、古老街区与人与自然共生的细腻呈现。',
    taboo: '避免用力过猛的浮躁炫技和过于直白露骨的情绪宣泄。',
    promptText: '【国际传播受众：英国】请采用复古油画质感与阴雨冷雾电影氛围光。镜头缓慢深沉推进，展现兼具古典底蕴与内敛克制的人文故事。'
  }
};

const currentCountryGuide = computed(() => countryGuideMap[selectedCountryCode.value]);

function openGuideModal() { showGuideModal.value = true; }
function closeGuideModal() { showGuideModal.value = false; }
function selectCountry(code: string) { selectedCountryCode.value = code; }

function openMobileBriefDrawer() { isMobileBriefOpen.value = true; }
function closeMobileBriefDrawer() { isMobileBriefOpen.value = false; }

function applyGuidanceToInput() {
  const guideText = currentCountryGuide.value.promptText;
  if (inputContent.value.trim()) {
    inputContent.value = `${inputContent.value}\n\n${guideText}`;
  } else {
    inputContent.value = guideText;
  }
  closeGuideModal();
  nextTick(() => {
    textareaRef.value?.focus();
  });
}

const activeConversation = computed(() => 
  conversations.value.find(c => c.id === currentConvId.value)
);

const cardThemes = [
  { border: 'rgba(99, 102, 241, 0.5)', bg: 'linear-gradient(145deg, rgba(99, 102, 241, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(99, 102, 241, 0.35)' },
  { border: 'rgba(14, 165, 233, 0.5)', bg: 'linear-gradient(145deg, rgba(14, 165, 233, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(14, 165, 233, 0.35)' },
  { border: 'rgba(16, 185, 129, 0.5)', bg: 'linear-gradient(145deg, rgba(16, 185, 129, 0.15), rgba(15, 23, 42, 0.75))', glow: 'rgba(16, 185, 129, 0.35)' },
  { border: 'rgba(244, 63, 94, 0.5)',  bg: 'linear-gradient(145deg, rgba(244, 63, 94, 0.15), rgba(15, 23, 42, 0.75))',  glow: 'rgba(244, 63, 94, 0.35)' },
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

onMounted(async () => {
  await loadConversations();
  await loadApiConfigs();
});

function backToProjectSpace() {
  currentConvId.value = '';
  activeJob.value = null;
  isMobileBriefOpen.value = false;
  if (pollTimer) clearInterval(pollTimer);
}

async function loadConversations() {
  try {
    const res: any = await request.get('/conversations');
    conversations.value = res.items || [];
  } catch (err) {
    console.error('加载对话失败', err);
  }
}

async function loadApiConfigs() {
  try {
    const res: any = await request.get('/video-api-configs');
    apiConfigs.value = res.items || [];
  } catch (err) {
    console.warn('获取 API 配置失败');
  }
}

async function switchConversation(convId: string) {
  currentConvId.value = convId;
  activeJob.value = null;
  isMobileBriefOpen.value = false;
  if (pollTimer) clearInterval(pollTimer);

  Promise.all([
    request.get(`/conversations/${convId}/messages`).catch(() => ({ items: [] })),
    request.get(`/conversations/${convId}/project`).catch(() => null)
  ]).then(([msgRes, projRes]: any) => {
    messages.value = msgRes.items || [];
    project.value = projRes;
    scrollToBottom();
  });
}

async function createNewConversation() {
  if (isCreatingConv.value) return;
  isCreatingConv.value = true;

  try {
    const res: any = await request.post('/conversations', { title: '新创作对话' });
    if (res.conversation) {
      conversations.value.unshift(res.conversation);
      currentConvId.value = res.conversation.id;
    }
    project.value = res.project || null;
    messages.value = [];
    activeJob.value = null;
    isMobileBriefOpen.value = false;
  } catch (err: any) {
    alert(err.message || '新建对话失败');
  } finally {
    isCreatingConv.value = false;
  }
}

async function handleDeleteConversation(convId: string) {
  if (!confirm('确定删除此创作对话吗？')) return;
  try {
    await request.delete(`/conversations/${convId}`);
    conversations.value = conversations.value.filter(c => c.id !== convId);
    if (currentConvId.value === convId) {
      currentConvId.value = '';
    }
  } catch (err: any) {
    alert(err.message || '删除失败');
  }
}

async function sendMessage() {
  if (!inputContent.value.trim() || isAgentResponding.value || !currentConvId.value) return;

  const content = inputContent.value;
  inputContent.value = '';
  isAgentResponding.value = true;

  const clientRequestId = crypto.randomUUID();

  try {
    const res: any = await request.post(`/conversations/${currentConvId.value}/messages`, {
      content,
      client_request_id: clientRequestId,
      web_search_enabled: true
    });

    if (res.user_message) messages.value.push(res.user_message);
    if (res.assistant_message) messages.value.push(res.assistant_message);
    if (res.project) project.value = res.project;
    scrollToBottom();
  } catch (err: any) {
    alert(err.message || 'Agent 响应失败，请重试');
  } finally {
    isAgentResponding.value = false;
  }
}

async function confirmProjectSpec() {
  if (!currentConvId.value || !project.value) return;
  try {
    const res: any = await request.post(`/conversations/${currentConvId.value}/project/confirm`, {
      spec_version: project.value.current_spec_version
    });
    project.value = res;
    if (isMobileBriefOpen.value) {
      isMobileBriefOpen.value = false; // 手机端确认完自动收起抽屉
    }
  } catch (err: any) {
    alert(err.message || '方案版本冲突，请刷新');
  }
}

async function submitVideoJob() {
  if (!project.value || !project.value.is_current_version_confirmed) {
    alert('请先确认当前方案版本！');
    return;
  }

  isSubmittingJob.value = true;
  const idempotencyKey = crypto.randomUUID();

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
        headers: { 'Idempotency-Key': idempotencyKey }
      }
    );

    activeJob.value = res;
    startPollingJob(res.id, res.poll_after_seconds || 4);
  } catch (err: any) {
    alert(err.message || '视频任务提交失败');
  } finally {
    isSubmittingJob.value = false;
  }
}

function startPollingJob(jobId: string, intervalSec: number) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = window.setInterval(async () => {
    try {
      const res: any = await request.get(`/video-jobs/${jobId}`);
      activeJob.value = res;
      if (['succeeded', 'failed', 'cancelled'].includes(res.status)) {
        if (pollTimer) clearInterval(pollTimer);
      }
    } catch (e) {
      console.warn('轮询中...');
    }
  }, Math.max(intervalSec, 3) * 1000);
}

function toggleCitations(msgId: string) {
  openCitations[msgId] = !openCitations[msgId];
}

function renderMd(text: string): string {
  if (!text) return '';
  let escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
  return escaped;
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

function formatFullTime(isoStr?: string | null) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
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
.workspace-layout {
  display: flex; flex-direction: column; height: 100vh; width: 100vw;
  background-color: #090c14; color: #f1f5f9; font-size: 15px; overflow: hidden;
}

/* 控制移动端与电脑端显隐辅助类 */
.mobile-only { display: none !important; }
.desktop-only { display: inline-flex; }

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
}
.brand-link { text-decoration: none; cursor: pointer; display: flex; align-items: center; }
.brand { display: flex; align-items: center; gap: 12px; }
.brand-avatar {
  width: 36px; height: 36px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; font-weight: 800; border-radius: 9px; display: flex; align-items: center;
  justify-content: center; font-size: 17px; box-shadow: 0 0 14px rgba(99, 102, 241, 0.4);
}
.brand-name { font-weight: 700; color: #ffffff; font-size: 18px; letter-spacing: 0.5px; }
.sub-badge {
  font-size: 12px; background-color: #172033; color: #94a3b8;
  padding: 3px 8px; border-radius: 6px; border: 1px solid #28354d;
}

.nav-actions { display: flex; align-items: center; gap: 12px; }
.nav-link {
  color: #cbd5e1; text-decoration: none; display: flex; align-items: center;
  gap: 6px; font-size: 13px; font-weight: 500; padding: 7px 12px; border-radius: 8px;
  background-color: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.2s;
}
.nav-link:hover { background-color: rgba(30, 41, 59, 0.8); border-color: rgba(99, 102, 241, 0.4); color: #fff; }
.nav-link .icon { width: 16px; height: 16px; }
.logout-btn {
  background: rgba(23, 28, 42, 0.6); border: 1px solid #2d3748; color: #94a3b8;
  padding: 7px 14px; border-radius: 8px; font-size: 13px; cursor: pointer; transition: all 0.2s;
}
.logout-btn:hover { background-color: rgba(239, 68, 68, 0.12); border-color: #ef4444; color: #fca5a5; }

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

/* ================= 视图 A：创作项目空间看板 ================= */
.board-container {
  flex: 1;
  overflow-y: auto;
  padding: 40px 60px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.board-header { text-align: center; margin-bottom: 32px; }
.board-title { font-size: 26px; font-weight: 700; color: #f8fafc; margin-bottom: 6px; }
.board-sub { font-size: 14px; color: #94a3b8; }

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
.square-card:hover { transform: translateY(-5px) scale(1.02); }

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
  width: 52px; height: 52px; border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #ffffff; display: flex; align-items: center; justify-content: center;
  font-size: 34px; font-weight: 300; box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
  transition: transform 0.25s ease;
}
.add-card:hover .plus-icon { transform: rotate(90deg) scale(1.1); }
.add-text { font-size: 14px; font-weight: 600; color: #cbd5e1; }

.project-card { border: 1px solid; backdrop-filter: blur(12px); }
.card-top-bar { display: flex; justify-content: space-between; align-items: center; width: 100%; }
.card-time { font-size: 11px; color: #94a3b8; font-weight: 500; }
.del-card-btn {
  background: transparent; border: none; color: #64748b; font-size: 18px;
  cursor: pointer; padding: 2px 6px; border-radius: 4px; transition: all 0.2s;
}
.del-card-btn:hover { color: #ef4444; background: rgba(255, 255, 255, 0.1); }
.card-content { margin: auto 0; display: flex; flex-direction: column; gap: 8px; }
.card-project-title {
  font-size: 17px; font-weight: 700; color: #f8fafc; line-height: 1.35;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.project-card .version-tag {
  align-self: flex-start; background: rgba(255, 255, 255, 0.1);
  color: #cbd5e1; padding: 2px 8px; border-radius: 4px; font-size: 11px;
}
.card-bottom { font-size: 11px; color: #94a3b8; text-align: right; font-weight: 500; }

/* ================= 视图 B：聚焦工作台 ================= */
.workspace-main { display: flex; flex: 1; overflow: hidden; position: relative; }

.chat-section { flex: 1; display: flex; flex-direction: column; background-color: #0d121f; border-right: 1px solid #1a2233; min-width: 0; }
.chat-header {
  padding: 12px 20px; border-bottom: 1px solid #1a2233; display: flex;
  justify-content: space-between; align-items: center; background-color: #0f1524; gap: 12px;
}
.chat-header-main { display: flex; align-items: center; gap: 12px; min-width: 0; }

.back-space-btn {
  display: flex; align-items: center; gap: 6px; background-color: #1a2336;
  border: 1px solid #28374f; color: #cbd5e1; padding: 6px 12px; border-radius: 8px;
  font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; flex-shrink: 0;
}
.back-space-btn:hover { background-color: #27354d; color: #ffffff; border-color: #6366f1; }
.back-icon { width: 14px; height: 14px; }

.chat-title-group { min-width: 0; }
.chat-title { font-size: 16px; font-weight: 600; color: #f8fafc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chat-sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }

.chat-actions-group { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

/* 国际传播指导按钮 */
.global-guide-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(56, 189, 248, 0.2));
  border: 1px solid rgba(99, 102, 241, 0.4);
  color: #a5f3fc;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s ease;
  white-space: nowrap;
}
.global-guide-btn:hover {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(56, 189, 248, 0.35));
  border-color: #38bdf8;
  color: #ffffff;
}
.globe-icon { width: 15px; height: 15px; color: #38bdf8; }

/* 手机端调出方案抽屉按钮 */
.mobile-brief-toggle {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  background-color: #1e293b;
  border: 1px solid #334155;
  color: #38bdf8;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}
.brief-icon { width: 14px; height: 14px; }
.brief-dot {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #eab308;
}

.messages-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.message-row { display: flex; gap: 12px; max-width: 85%; }
.message-row.user { align-self: flex-end; flex-direction: row-reverse; }
.avatar {
  width: 32px; height: 32px; border-radius: 50%; display: flex;
  align-items: center; justify-content: center; font-size: 13px; font-weight: bold; flex-shrink: 0;
}
.user .avatar { background-color: #4f46e5; color: #fff; }
.assistant .avatar { background-color: #059669; color: #fff; }
.bubble { background-color: #172033; padding: 12px 16px; border-radius: 10px; color: #f1f5f9; font-size: 14px; line-height: 1.55; }
.user .bubble { background-color: #263654; }
.msg-content { white-space: pre-wrap; word-break: break-word; }
.citations-fold { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #334155; }
.citations-toggle { font-size: 12px; color: #38bdf8; cursor: pointer; }
.citations-body { margin-top: 4px; display: flex; flex-direction: column; gap: 3px; }
.cite-row a { color: #60a5fa; text-decoration: none; font-size: 11px; }
.msg-time { font-size: 11px; color: #94a3b8; margin-top: 4px; text-align: right; }

.chat-input-area { padding: 16px 20px; border-top: 1px solid #1a2233; background-color: #0b0f19; }
.chat-input-area textarea {
  width: 100%; height: 72px; background-color: #141b2a; border: 1px solid #243147;
  border-radius: 8px; padding: 10px 14px; color: #fff; font-size: 14px; resize: none; outline: none;
}
.chat-input-area textarea:focus { border-color: #6366f1; }
.input-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.input-hint { font-size: 12px; color: #94a3b8; }
.send-btn { background-color: #6366f1; color: #fff; border: none; padding: 8px 18px; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* 右侧方案面板：电脑端常驻 460px */
.brief-panel {
  width: 440px; min-width: 440px; background-color: #0b0f19;
  overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px;
  border-left: 1px solid #1a2233;
}
.panel-tab-title { display: flex; justify-content: space-between; align-items: center; }
.panel-tab-title h3 { font-size: 16px; color: #f8fafc; }
.version-tag { background-color: #1e293b; color: #38bdf8; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 500; }
.spec-status-bar {
  background-color: #131b2c; border: 1px solid #1f2b44; padding: 10px 14px;
  border-radius: 8px; display: flex; justify-content: space-between; align-items: center;
}
.status-indicator { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #cbd5e1; }
.dot-fixed {
  width: 8px; height: 8px; border-radius: 50%; background-color: #38bdf8;
  box-shadow: 0 0 8px rgba(56, 189, 248, 0.6); flex-shrink: 0;
}
.confirm-btn {
  background-color: #1e293b; color: #38bdf8; border: 1px solid #334155;
  padding: 5px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.2s;
}
.confirm-btn:hover:not(:disabled) { background-color: #27354d; color: #fff; }
.confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.spec-details-list {
  background-color: #121827; border: 1px solid #1e273d; border-radius: 10px;
  padding: 14px; display: flex; flex-direction: column; gap: 12px;
}
.spec-field-item label { display: block; font-size: 11px; color: #94a3b8; margin-bottom: 3px; font-weight: 500; }
.spec-val { font-size: 12px; color: #e2e8f0; line-height: 1.5; }
.prompt-code-box {
  background-color: #0b0e17; border: 1px solid #1c2639; padding: 8px 10px;
  border-radius: 6px; font-family: monospace; font-size: 12px; color: #a5f3fc;
  max-height: 80px; overflow-y: auto; word-break: break-all;
}
.job-action-card { background-color: #121827; border: 1px solid #1e273d; border-radius: 10px; padding: 16px; }
.card-inner-title { font-size: 15px; font-weight: 600; color: #f8fafc; margin-bottom: 10px; }
.job-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
.job-field select { background-color: #1a2336; border: 1px solid #2d3b55; padding: 8px; color: #fff; border-radius: 6px; font-size: 12px; }
.create-job-btn {
  width: 100%; background-color: #10b981; color: #fff; border: none;
  padding: 10px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px;
}
.create-job-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.active-job-preview { background-color: #121827; border: 1px solid #1e273d; border-radius: 10px; padding: 14px; }
.preview-header { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 10px; }
.job-succeeded { color: #10b981; }
.job-running, .job-queued { color: #38bdf8; }
.job-failed { color: #ef4444; }
.video-container video { width: 100%; border-radius: 8px; background-color: #000; }
.progress-bar-bg { width: 100%; height: 6px; background-color: #1e293b; border-radius: 3px; overflow: hidden; margin-bottom: 6px; }
.progress-bar-inner { height: 100%; background-color: #38bdf8; transition: width 0.3s; }
.progress-desc { font-size: 12px; color: #94a3b8; text-align: center; }
.loading-spinner {
  width: 14px; height: 14px; border: 2px solid #64748b;
  border-top-color: #38bdf8; border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ================= 国际传播指引弹窗 ================= */
.guide-modal-mask {
  position: fixed; inset: 0; z-index: 999;
  background: rgba(4, 6, 12, 0.75); backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center; padding: 16px;
}
.guide-modal-box {
  width: 100%; max-width: 680px; background: #0f1524;
  border: 1px solid rgba(99, 102, 241, 0.35); border-radius: 16px;
  padding: 24px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.85);
  display: flex; flex-direction: column; gap: 16px;
  max-height: 90vh; overflow-y: auto;
}
.guide-modal-header { display: flex; justify-content: space-between; align-items: flex-start; }
.modal-badge { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; color: #38bdf8; }
.modal-title { font-size: 18px; font-weight: 700; color: #f8fafc; margin-top: 2px; }
.cancel-action-btn {
  background: rgba(255, 255, 255, 0.05); border: 1px solid #334155;
  color: #94a3b8; padding: 5px 12px; border-radius: 6px; font-size: 12px; cursor: pointer;
}
.countries-tab-bar { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; }
.country-tab {
  display: flex; align-items: center; gap: 4px; background: #172033;
  border: 1px solid #28374f; color: #cbd5e1; padding: 6px 12px; border-radius: 6px;
  font-size: 13px; cursor: pointer; white-space: nowrap;
}
.country-tab.active { background: linear-gradient(135deg, #4f46e5, #6366f1); border-color: #818cf8; color: #fff; }
.guidance-content-box {
  background: #141b2c; border: 1px solid #1f2b44; border-radius: 10px;
  padding: 16px; display: flex; flex-direction: column; gap: 12px;
}
.guidance-header { display: flex; justify-content: space-between; align-items: center; }
.country-target-name { font-size: 15px; font-weight: 700; color: #f8fafc; }
.lang-pill { background: #1e293b; color: #38bdf8; font-size: 11px; padding: 2px 6px; border-radius: 4px; }
.guidance-detail-card { display: flex; flex-direction: column; gap: 8px; }
.guide-block { font-size: 12px; line-height: 1.5; color: #cbd5e1; }
.block-label { font-weight: 600; color: #94a3b8; }
.guide-block.highlight-block { background: rgba(239, 68, 68, 0.08); border-left: 3px solid #ef4444; padding: 6px 8px; border-radius: 0 4px 4px 0; }
.guide-block.highlight-block .block-label { color: #fca5a5; }
.prompt-snippet-box { background: #0b0f19; border: 1px solid #1c2639; border-radius: 6px; padding: 10px; }
.snippet-label { font-size: 11px; color: #64748b; margin-bottom: 2px; }
.snippet-text { font-size: 12px; color: #a5f3fc; line-height: 1.45; font-family: monospace; }
.guide-modal-footer { display: flex; justify-content: space-between; align-items: center; }
.footer-tip { font-size: 11px; color: #64748b; }
.apply-to-chat-btn {
  background: linear-gradient(135deg, #10b981, #059669); color: #ffffff; border: none;
  padding: 8px 20px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer;
}

/* ================= 移动端适配特化 (<= 868px) ================= */
@media (max-width: 868px) {
  .desktop-only { display: none !important; }
  .mobile-only { display: flex !important; }

  /* 顶栏紧凑排布，彻底消除图二的折行错位 */
  .top-nav {
    padding: 0 12px;
    height: 56px;
    min-height: 56px;
  }
  .brand-name { font-size: 16px; }
  .brand-avatar { width: 30px; height: 30px; font-size: 15px; }
  .nav-actions { gap: 8px; }
  .nav-link { padding: 6px 8px; }
  .logout-btn { padding: 5px 10px; font-size: 12px; }

  /* 视图 A 看板：微调内边距，保持图三优良排版 */
  .board-container { padding: 20px 14px; }
  .board-header { margin-bottom: 20px; }
  .board-title { font-size: 22px; }
  .board-sub { font-size: 12px; }
  .cards-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  .square-card {
    border-radius: 14px;
    padding: 14px;
  }
  .plus-icon { width: 44px; height: 44px; font-size: 28px; }
  .add-text { font-size: 13px; }
  .card-project-title { font-size: 15px; }

  /* 视图 B 聊天顶栏：单行平铺，不再换行挤爆 */
  .chat-header {
    padding: 8px 12px;
    gap: 6px;
  }
  .chat-header-main {
    gap: 8px;
  }
  .back-space-btn {
    padding: 5px 8px;
    font-size: 12px;
  }
  .chat-title { font-size: 14px; }
  .global-guide-btn {
    padding: 5px 10px;
    font-size: 12px;
  }
  .mobile-brief-toggle {
    padding: 5px 8px;
    font-size: 12px;
  }

  .messages-container {
    padding: 14px 12px;
    gap: 12px;
  }
  .message-row { max-width: 92%; }
  .bubble { font-size: 13px; padding: 10px 12px; }
  .chat-input-area { padding: 10px 12px; }
  .chat-input-area textarea { height: 60px; font-size: 13px; padding: 8px 10px; }
  .input-actions { justify-content: flex-end; }
  .send-btn { padding: 7px 16px; font-size: 13px; }

  /* 核心需求：手机端彻底隐藏右栏，改为点击抽屉滑出 */
  .brief-panel {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 88vw;
    min-width: unset;
    max-width: 380px;
    z-index: 990;
    box-shadow: -10px 0 30px rgba(0, 0, 0, 0.8);
    transform: translateX(100%);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    border-left: 1px solid rgba(99, 102, 241, 0.3);
  }
  .brief-panel.mobile-drawer-open {
    transform: translateX(0);
  }
  .drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 10px;
    border-bottom: 1px solid #1a2233;
    margin-bottom: 4px;
  }
  .drawer-title { font-size: 15px; font-weight: 700; color: #f8fafc; }
  .drawer-close-btn {
    background: #1e293b;
    border: 1px solid #334155;
    color: #94a3b8;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
  }

  /* 抽屉背景半透明遮罩 */
  .mobile-drawer-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(4px);
    z-index: 980;
  }

  .guide-modal-box { padding: 16px; }
  .guide-modal-footer { justify-content: flex-end; }
  .apply-to-chat-btn { width: 100%; }
}
</style>