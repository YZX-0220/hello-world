<template>
  <div class="tv-container" ref="containerRef">
    <!-- 顶部状态栏：左侧返回 + 正中间频道胶囊 + 右侧管理端/计数器 -->
    <header class="tv-header">
      <!-- 左上角返回按钮 -->
      <div class="header-left">
        <button class="back-pill-btn" @click="handleGoBack" title="返回上一页">
          <svg class="back-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          <span class="btn-text">返回</span>
        </button>
      </div>

      <!-- 正中间：红点 + 频道名称胶囊 -->
      <div class="header-center">
        <div class="channel-badge">
          <span class="live-dot"></span>
          <span class="channel-name">HELLO WORLD · TV 频道</span>
        </div>
      </div>

      <!-- 右上角：管理员管理入口 (仅管理员可见) + 素材进度计数 -->
      <div class="header-right">
        <button v-if="isAdmin" class="admin-portal-btn" @click="goToAdminPanel" title="进入 TV 素材管理控制台">
          <svg class="admin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <circle cx="12" cy="12" r="3" stroke-width="2" />
          </svg>
          <span class="btn-text">管理端</span>
        </button>

        <div class="counter" v-if="items.length > 0">
          {{ currentIndex + 1 }} / {{ items.length }}
        </div>
      </div>
    </header>

    <!-- 主展示区：支持左右滑动切换（手机端）以及桌面端按键切换 -->
    <main class="tv-stage" @touchstart="handleTouchStart" @touchend="handleTouchEnd">
      <!-- 左侧切换按钮（桌面端可见，移动端自动隐藏） -->
      <button class="nav-btn prev-btn" :disabled="currentIndex === 0 || loading" @click="prevItem" aria-label="上一个视频">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      <!-- 中间主视频视窗 -->
      <div class="video-wrapper">
        <div v-if="isVideoLoading" class="loading-placeholder">
          <div class="spinner"></div>
          <span>正在加载视频画面...</span>
        </div>

        <div v-else-if="loading && items.length === 0" class="loading-placeholder">
          <div class="spinner"></div>
          <span>正在连接频道素材...</span>
        </div>

        <div v-else-if="items.length === 0" class="empty-placeholder">
          <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <rect x="2" y="7" width="20" height="13" rx="2" stroke-width="1.5" />
            <path d="M17 2l-5 5-5-5" stroke-width="1.5" stroke-linecap="round" />
            <line x1="2" y1="20" x2="22" y2="20" stroke-width="1.5" />
          </svg>
          <span class="empty-title">暂无已发布的示例视频</span>
          <span class="empty-hint">请确保已在管理员后台将素材状态发布为 published，或检查登录状态[cite: 1]</span>
        </div>

        <video v-else ref="videoPlayerRef" class="main-video" :key="currentItem?.id"
          :src="videoBlobUrl || currentItem?.video?.content_url" :poster="currentItem?.cover?.content_url" controls
          autoplay loop playsinline></video>
      </div>

      <!-- 右侧切换按钮（桌面端可见，移动端自动隐藏） -->
      <button class="nav-btn next-btn"
        :disabled="(currentIndex >= items.length - 1 && !nextCursor) || loading || items.length === 0" @click="nextItem"
        aria-label="下一个视频">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </main>

    <!-- 下方胶囊信息条：支持点击向上展开查看完整提示词 -->
    <footer class="tv-footer">
      <div class="console-pill" :class="{ 'is-expanded': isExpanded }" @click="toggleExpand"
        :title="isExpanded ? '点击收起' : '点击向上展开查看完整提示词'">
        <!-- 胶囊左侧：TV 标识图标 -->
        <div class="tv-screen-icon" :title="isExpanded ? '收起详情' : '展开详情'">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <rect x="2" y="7" width="20" height="13" rx="2" stroke-width="2" />
            <path d="M17 2l-5 5-5-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>

        <!-- 胶囊中间主要文本区域：上方标题，下方提示词 -->
        <div class="text-info-area">
          <template v-if="currentItem">
            <div class="title-row">
              <span class="video-title">{{ currentItem.title }}</span>
              <span class="model-badge" v-if="currentItem.model_name">
                {{ currentItem.model_name }}
              </span>
              <!-- 修改后：折叠向上展开 ▲，展开向下收起 ▼ -->
              <span class="expand-tag-hint">
                {{ isExpanded ? '点击收起 ▼' : '点击展开 ▲' }}
              </span>
            </div>

            <!-- 提示词部分：折叠时单行省略，展开时全量显示并支持滚动 -->
            <div class="prompt-container" :class="{ 'expanded-prompt': isExpanded }">
              <p class="prompt-content">
                {{ promptText || '暂无详细提示词描述' }}
              </p>
            </div>
          </template>
          <template v-else>
            <div class="title-row">
              <span class="video-title empty-text">等待信号源接入...</span>
            </div>
            <div class="prompt-container">
              <span class="prompt-content">暂无正在轮播的提示词</span>
            </div>
          </template>
        </div>

        <!-- 胶囊右侧快捷操作（阻止向上冒泡触发折叠） -->
        <div class="actions-area" v-if="currentItem">
          <button class="action-btn" @click.stop="copyPrompt" :title="copied ? '已复制' : '复制提示词'">
            <svg v-if="!copied" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <rect x="9" y="9" width="13" height="13" rx="2" stroke-width="2" />
              <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" stroke-width="2" />
            </svg>
            <span v-else class="copied-indicator">✓</span>
          </button>

          <button class="action-btn" @click.stop="toggleFullscreen" title="全屏视窗">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
          </button>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

interface VideoAsset {
  asset_id: string;
  mime_type: string;
  content_url: string;
}

interface CoverAsset {
  asset_id: string;
  content_url: string;
}

interface MaterialItem {
  id: string;
  title: string;
  description: string;
  model_name: string;
  video: VideoAsset;
  cover?: CoverAsset | null;
}

const items = ref<MaterialItem[]>([]);
const currentIndex = ref(0);
const loading = ref(false);
const nextCursor = ref<string | null>(null);
const copied = ref(false);
const isAdmin = ref(false);

// 控制提示词底栏展开/收起状态
const isExpanded = ref(false);

const videoPlayerRef = ref<HTMLVideoElement | null>(null);
const containerRef = ref<HTMLElement | null>(null);

// 声明响应式计算属性 currentItem
const currentItem = computed(() => items.value[currentIndex.value] || null);

// 视频 Blob URL 及其加载状态
const videoBlobUrl = ref<string>('');
const isVideoLoading = ref(false);

// 切换视频时重置展开状态
watch(currentItem, async (newItem) => {
  isExpanded.value = false;

  if (videoBlobUrl.value) {
    URL.revokeObjectURL(videoBlobUrl.value);
    videoBlobUrl.value = '';
  }

  const targetUrl = newItem?.video?.content_url;
  if (!targetUrl) return;

  isVideoLoading.value = true;
  try {
    const res = await fetch(targetUrl, {
      method: 'GET',
      credentials: 'include' // 携带 hw_session Cookie[cite: 1]
    });

    if (!res.ok) {
      throw new Error(`获取视频流失败: HTTP ${res.status}`);
    }

    const blob = await res.blob();
    videoBlobUrl.value = URL.createObjectURL(blob);
  } catch (err) {
    console.warn('通过受控流加载视频异常，将降级尝试直接播放:', err);
  } finally {
    isVideoLoading.value = false;
  }
}, { immediate: true });

// 切换展开/收起
function toggleExpand() {
  if (!currentItem.value) return;
  isExpanded.value = !isExpanded.value;
}

// 返回上一页
function handleGoBack() {
  if (window.history.length > 1) {
    router.back();
  } else {
    router.push('/workspace');
  }
}

// 跳转到管理界面
function goToAdminPanel() {
  router.push('/tv/admin');
}

// 检查当前用户是否具有素材库管理员权限[cite: 1]
async function checkAdminPermission() {
  try {
    const res = await fetch('/api/v1/admin/material-library?limit=1', {
      method: 'GET',
      credentials: 'include'
    });
    if (res.ok) {
      isAdmin.value = true;
    } else {
      isAdmin.value = false;
    }
  } catch {
    isAdmin.value = false;
  }
}

// 提取提示词文本
const promptText = computed(() => {
  if (!currentItem.value?.description) return '';
  return currentItem.value.description
    .replace(/^#+\s+/gm, '')
    .trim();
});

// 从素材库接口分页拉取已发布示例[cite: 1]
async function fetchMaterials(cursor?: string) {
  loading.value = true;
  try {
    const url = new URL('/api/v1/material-library', window.location.origin);
    url.searchParams.set('limit', '20');
    if (cursor) url.searchParams.set('cursor', cursor);

    const res = await fetch(url.toString(), {
      method: 'GET',
      credentials: 'include'
    });

    if (!res.ok) {
      console.warn(`获取列表状态: ${res.status}`);
      return;
    }
    const data = await res.json();

    if (cursor) {
      items.value.push(...(data.items || []));
    } else {
      items.value = data.items || [];
      currentIndex.value = 0;
    }
    nextCursor.value = data.next_cursor || null;
  } catch (err) {
    console.error('获取频道视频失败:', err);
  } finally {
    loading.value = false;
  }
}

function prevItem() {
  if (currentIndex.value > 0) {
    currentIndex.value--;
  }
}

async function nextItem() {
  if (currentIndex.value >= items.value.length - 2 && nextCursor.value && !loading.value) {
    await fetchMaterials(nextCursor.value);
  }

  if (currentIndex.value < items.value.length - 1) {
    currentIndex.value++;
  }
}

// ================= 手机端左右滑动手势切换 =================
let touchStartX = 0;
let touchStartY = 0;

function handleTouchStart(e: TouchEvent) {
  if (e.touches.length === 1) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  }
}

function handleTouchEnd(e: TouchEvent) {
  if (e.changedTouches.length === 1) {
    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;
    const deltaX = touchEndX - touchStartX;
    const deltaY = touchEndY - touchStartY;

    if (Math.abs(deltaX) > 45 && Math.abs(deltaX) > Math.abs(deltaY) * 1.5) {
      if (deltaX < 0) {
        nextItem();
      } else {
        prevItem();
      }
    }
  }
}

// 复制提示词
async function copyPrompt() {
  if (!promptText.value) return;
  try {
    await navigator.clipboard.writeText(promptText.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 1800);
  } catch (e) {
    console.error('复制失败', e);
  }
}

// 全屏切换
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    containerRef.value?.requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
}

onMounted(() => {
  fetchMaterials();
  checkAdminPermission();
});
</script>

<style scoped>
.tv-container {
  width: 100vw;
  height: 100vh;
  height: 100dvh;
  background-color: #0c0b0e;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  position: relative;
  overflow: hidden;
  user-select: none;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", sans-serif;
  color: #fff;
  box-sizing: border-box;
}

/* 顶部状态栏：三列排布 */
.tv-header {
  width: 100%;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  box-sizing: border-box;
  position: relative;
  z-index: 20;
}

.header-left {
  display: flex;
  align-items: center;
  min-width: 100px;
  z-index: 2;
}

.header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  min-width: 100px;
  z-index: 2;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}

/* 左上角返回胶囊按钮 */
.back-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: blur(8px);
}

.back-pill-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateX(-2px);
}

.back-icon {
  width: 16px;
  height: 16px;
}

/* 右上角管理员端按钮 */
.admin-portal-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(129, 140, 248, 0.35);
  color: #a5b4fc;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s ease;
  backdrop-filter: blur(8px);
}

.admin-portal-btn:hover {
  background: rgba(99, 102, 241, 0.3);
  color: #ffffff;
  border-color: #818cf8;
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
}

.admin-icon {
  width: 15px;
  height: 15px;
}

/* 中间频道胶囊 */
.channel-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.06);
  padding: 7px 18px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  white-space: nowrap;
}

.live-dot {
  width: 8px;
  height: 8px;
  background-color: #ef4444;
  border-radius: 50%;
  box-shadow: 0 0 8px #ef4444;
  flex-shrink: 0;
}

.channel-name {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #e2e8f0;
}

.counter {
  font-size: 13px;
  color: #64748b;
  font-family: monospace;
}

/* 中间主视窗舞台 */
.tv-stage {
  flex: 1;
  width: 100%;
  max-width: 1380px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
  padding: 0 24px;
  box-sizing: border-box;
}

/* 左右切换按钮（桌面端） */
.nav-btn {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  flex-shrink: 0;
}

.nav-btn svg {
  width: 24px;
  height: 24px;
}

.nav-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  transform: scale(1.08);
}

.nav-btn:disabled {
  opacity: 0.2;
  cursor: not-allowed;
}

/* 核心大视频容器 */
.video-wrapper {
  flex: 1;
  max-width: 1000px;
  height: calc(100vh - 210px);
  max-height: 620px;
  background-color: #000;
  border-radius: 20px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  position: relative;
}

.main-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background-color: #000;
}

.loading-placeholder,
.empty-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #94a3b8;
  padding: 24px;
  text-align: center;
}

.empty-icon {
  width: 48px;
  height: 48px;
  color: #475569;
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: #cbd5e1;
}

.empty-hint {
  font-size: 12px;
  color: #64748b;
  max-width: 400px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255, 255, 255, 0.1);
  border-top-color: #818cf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ================= 底部胶囊控制与信息展示栏（带向上展开） ================= */
.tv-footer {
  width: 100%;
  display: flex;
  justify-content: center;
  padding-bottom: 24px;
  z-index: 30;
  position: relative;
}

.console-pill {
  width: min(90vw, 760px);
  background: rgba(23, 21, 26, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 36px;
  padding: 12px 24px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(20px);
  cursor: pointer;
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.console-pill:hover {
  border-color: rgba(129, 140, 248, 0.35);
  box-shadow: 0 16px 45px rgba(99, 102, 241, 0.15);
}

/* 展开激活态样式：向上扩展高度 */
.console-pill.is-expanded {
  border-radius: 20px;
  background: rgba(20, 18, 24, 0.96);
  border-color: rgba(129, 140, 248, 0.45);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.85);
  transform: translateY(-8px);
}

.tv-screen-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a1a1aa;
  flex-shrink: 0;
  margin-top: 2px;
  transition: color 0.2s, background-color 0.2s;
}

.console-pill:hover .tv-screen-icon {
  color: #818cf8;
  background-color: rgba(99, 102, 241, 0.12);
}

.tv-screen-icon svg {
  width: 20px;
  height: 20px;
}

/* 文本信息流 */
.text-info-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.video-title {
  font-size: 15px;
  font-weight: 700;
  color: #f4f4f5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.video-title.empty-text {
  color: #71717a;
  font-weight: 500;
}

.model-badge {
  font-size: 11px;
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.08);
  padding: 2px 8px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.expand-tag-hint {
  font-size: 11px;
  color: #6366f1;
  opacity: 0.8;
  margin-left: auto;
  user-select: none;
  transition: opacity 0.2s;
}

.console-pill:hover .expand-tag-hint {
  opacity: 1;
}

/* 提示词容器：折叠 vs 展开 */
.prompt-container {
  max-height: 20px;
  overflow: hidden;
  transition: max-height 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

.prompt-container.expanded-prompt {
  max-height: 220px;
  overflow-y: auto;
  padding-right: 6px;
  margin-top: 4px;
}

/* 定制滚动条 */
.prompt-container.expanded-prompt::-webkit-scrollbar {
  width: 4px;
}

.prompt-container.expanded-prompt::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.03);
}

.prompt-container.expanded-prompt::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.prompt-content {
  font-size: 12px;
  color: #a1a1aa;
  line-height: 1.6;
  margin: 0;
  word-break: break-word;
  white-space: pre-wrap;
}

/* 折叠时保持单行截断省略 */
.prompt-container:not(.expanded-prompt) .prompt-content {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #71717a;
}

/* 胶囊右侧按键 */
.actions-area {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-top: 2px;
}

.action-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: transparent;
  border: 1px solid transparent;
  color: #a1a1aa;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn svg {
  width: 17px;
  height: 17px;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.copied-indicator {
  color: #10b981;
  font-weight: bold;
  font-size: 14px;
}

/* ================= 移动端适配 (<= 768px) ================= */
@media (max-width: 768px) {
  .tv-container {
    padding: 0;
    justify-content: flex-start;
  }

  /* 顶部状态栏 */
  .tv-header {
    height: 52px;
    padding: 0 12px;
  }

  .header-left,
  .header-right {
    min-width: auto;
  }

  .back-pill-btn {
    padding: 5px 10px;
    gap: 4px;
    font-size: 12px;
  }

  .admin-portal-btn {
    padding: 5px 10px;
    gap: 4px;
    font-size: 12px;
  }

  .channel-badge {
    padding: 4px 10px;
    gap: 6px;
    max-width: 160px;
  }

  .channel-name {
    font-size: 11px;
    letter-spacing: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .counter {
    font-size: 12px;
  }

  /* 主视窗舞台 */
  .tv-stage {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 0 16px;
    gap: 0;
    max-width: 100vw;
  }

  .nav-btn {
    display: none !important;
  }

  .video-wrapper {
    width: 100%;
    max-width: 100%;
    height: auto;
    max-height: 55vh;
    aspect-ratio: 9 / 14;
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
    margin-bottom: 12px;
  }

  .main-video {
    object-fit: cover;
  }

  /* 手机端底部卡片与向上抽屉展开 */
  .tv-footer {
    padding: 0 14px 16px 14px;
    width: 100%;
    box-sizing: border-box;
  }

  .console-pill {
    width: 100%;
    border-radius: 24px;
    padding: 10px 14px;
    gap: 10px;
  }

  .console-pill.is-expanded {
    border-radius: 18px;
    transform: translateY(-4px);
  }

  .prompt-container.expanded-prompt {
    max-height: 180px;
  }

  .tv-screen-icon {
    width: 32px;
    height: 32px;
  }

  .tv-screen-icon svg {
    width: 18px;
    height: 18px;
  }

  .video-title {
    font-size: 14px;
    max-width: 110px;
  }

  .model-badge {
    font-size: 10px;
    padding: 1px 6px;
  }

  .expand-tag-hint {
    font-size: 10px;
  }

  .prompt-content {
    font-size: 11px;
  }

  .action-btn {
    width: 30px;
    height: 30px;
  }

  .action-btn svg {
    width: 15px;
    height: 15px;
  }
}
</style>