<template>
  <div class="tv-shell" ref="containerRef">
    <div class="tv-ambient" aria-hidden="true" />

    <header class="tv-top">
      <div class="top-side">
        <button class="pill-btn" @click="handleGoBack" title="返回创作项目空间">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          <span>返回</span>
        </button>
        <button v-if="isAdmin" class="pill-btn" @click="goToAdminPanel" title="进入 TV 素材管理控制台">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <circle cx="12" cy="12" r="3" stroke-width="2" />
          </svg>
          <span>素材管理</span>
        </button>
      </div>

      <div class="top-center">
        <div class="channel-line">
          <span class="live-dot" />
          <span>HELLO WORLD · TV 频道</span>
        </div>
        <h1 class="journal-title" :title="currentItem?.title">
          <span class="title-name">影像手账</span>
          <template v-if="currentItem">
            <span class="title-dot">·</span>
            <span class="title-item">{{ currentItem.title }}</span>
          </template>
        </h1>
        <button
          class="info-btn info-top"
          :disabled="!currentItem"
          @click="toggleInfo"
          :aria-expanded="infoOpen"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6h16M4 12h10M4 18h7" />
          </svg>
          <span>提示词与参数</span>
        </button>
      </div>

      <div class="top-side top-side-right">
        <div v-if="items.length" class="page-counter">
          <span class="counter-now">{{ String(currentIndex + 1).padStart(2, '0') }}</span>
          <span class="counter-sep">/</span>
          <span class="counter-all">{{ String(items.length).padStart(2, '0') }}</span>
        </div>
      </div>
    </header>

    <main class="tv-main">
      <div v-if="loading && !items.length" class="stage-state">
        <div class="spinner" />
        <span>正在装订这一期的影像手账…</span>
      </div>

      <div v-else-if="!items.length" class="stage-state">
        <div class="blank-spread" aria-hidden="true">
          <div class="blank-page">
            <span class="blank-mark">＋</span>
            <span class="blank-note">第一页还空着</span>
          </div>
          <div class="blank-page">
            <div class="blank-lines"><i /><i /><i /><i /></div>
            <span class="blank-hint">在管理端发布作品后，这里会自动装订成册</span>
          </div>
        </div>
        <div class="empty-actions">
          <button class="pill-btn" @click="router.push('/workspace')">去工作台创作</button>
          <button v-if="isAdmin" class="pill-btn" @click="goToAdminPanel">录入第一则作品</button>
        </div>
      </div>

      <WarpRing
        v-else
        :items="items"
        v-model:index="currentIndex"
        @spinstart="onFlipStart"
        @spinend="onFlipEnd"
      >
        <template #card="{ item, index, active, near }">
          <div class="ring-face" :class="`tone-${index % 4}`">
            <img
              v-if="item.cover?.content_url"
              class="ring-poster"
              :src="item.cover.content_url"
              alt=""
              aria-hidden="true"
            />
            <video
              v-if="near && item.video?.content_url"
              class="ring-video"
              :class="{ 'is-active': active }"
              :src="item.video.content_url"
              crossorigin="use-credentials"
              preload="auto"
              :muted="isMuted"
              playsinline
              @canplay="markReady(item.id)"
              @playing="onVideoPlaying"
              @pause="onVideoPause"
              @ended="onVideoEnded"
              @click="togglePlay"
            />
            <span class="ring-caption">{{ item.title }}</span>
            <span class="ring-folio">{{ String(index + 1).padStart(2, '0') }}</span>
          </div>
        </template>
      </WarpRing>
    </main>

    <footer class="tv-bottom">
      <div class="bottom-bar">
        <span class="bar-hint">拖动翻页 · ← → 切换 · 横向滚轮</span>

        <div class="bar-controls">
          <button class="round-btn" :disabled="!items.length" @click="prevItem" aria-label="上一页">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M15 19l-7-7 7-7" /></svg>
          </button>
          <button class="round-btn is-primary" :disabled="!items.length" @click="togglePlay" :aria-label="isPlaying ? '暂停' : '播放'">
            <svg v-if="isPlaying" viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="5" width="3.6" height="14" rx="1.2" /><rect x="13.4" y="5" width="3.6" height="14" rx="1.2" /></svg>
            <svg v-else viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13a1 1 0 001.53.85l10-6.5a1 1 0 000-1.7l-10-6.5A1 1 0 008 5.5z" /></svg>
          </button>
          <button class="round-btn" :disabled="!items.length" @click="nextItem" aria-label="下一页">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.2" d="M9 5l7 7-7 7" /></svg>
          </button>
        </div>

        <div class="bar-tools">
          <button class="round-btn is-ghost" @click="toggleMute" :aria-label="isMuted ? '开启声音' : '静音'" :title="isMuted ? '开启声音' : '静音'">
            <svg v-if="isMuted" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.9" d="M11 5L6.5 9H3v6h3.5L11 19V5z" />
              <path stroke-linecap="round" stroke-width="1.9" d="M16 9.5l5 5M21 9.5l-5 5" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.9" d="M11 5L6.5 9H3v6h3.5L11 19V5z" />
              <path stroke-linecap="round" stroke-width="1.9" d="M15.5 8.6a5 5 0 010 6.8M18.4 6a8.6 8.6 0 010 12" />
            </svg>
          </button>
          <button class="round-btn is-ghost" @click="toggleFullscreen" aria-label="全屏" title="全屏">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.9" d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
            </svg>
          </button>
        </div>
      </div>
    </footer>

    <transition name="sheet">
      <div v-if="infoOpen" class="info-layer" @click.self="closeInfo">
        <section class="info-sheet" role="dialog" aria-modal="true" aria-label="作品信息">
          <button class="sheet-close" aria-label="关闭" @click="closeInfo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-width="2" d="M6 6l12 12M18 6L6 18" /></svg>
          </button>

          <header class="sheet-head">
            <span class="sheet-kicker">THIS VIDEO</span>
            <h2 class="sheet-title">{{ currentItem?.title }}</h2>
            <div class="sheet-meta">
              <span class="model-chip">{{ currentItem?.model_name || '模型未标注' }}</span>
              <span v-if="currentItem?.updated_at" class="meta-item">{{ dateLabel(currentItem?.updated_at) }}</span>
              <button
                v-if="currentItem"
                class="copy-inline"
                :class="{ 'is-done': copied }"
                @click="copyPrompt(currentItem)"
              >
                {{ copied ? '已复制' : '复制提示词' }}
              </button>
            </div>
          </header>

          <div class="sheet-prompt">
            <span class="prompt-label">提示词</span>
            <p class="prompt-text">{{ currentItem ? promptOf(currentItem) : '' }}</p>
          </div>
        </section>
      </div>
    </transition>
  </div>
</template>


<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import WarpRing from '@/components/tv/WarpRing.vue';

const router = useRouter();

interface LibraryFile {
  asset_id: string;
  mime_type: string;
  size_bytes?: number;
  width?: number | null;
  height?: number | null;
  duration_ms?: number | null;
  content_url: string;
}

interface MaterialItem {
  id: string;
  title: string;
  description: string;
  model_name: string;
  status?: string;
  updated_at?: string;
  video: LibraryFile;
  cover?: LibraryFile | null;
}

const items = ref<MaterialItem[]>([]);
const currentIndex = ref(0);
const loading = ref(false);
const nextCursor = ref<string | null>(null);
const copied = ref(false);
const isAdmin = ref(false);
const isPlaying = ref(false);
const isMuted = ref(true);
const infoOpen = ref(false);
const flipping = ref(false);


const containerRef = ref<HTMLElement | null>(null);
const ready = reactive(new Set<string>());

function markReady(id: string) {
  ready.add(id);
  if (currentItem.value?.id === id) void syncPlayback();
}

function activeVideo(): HTMLVideoElement | null {
  return (
    containerRef.value?.querySelector<HTMLVideoElement>('.ring-video.is-active') ??
    containerRef.value?.querySelector<HTMLVideoElement>('.ring-video') ??
    null
  );
}

function onVideoPlaying() {
  if (!flipping.value) isPlaying.value = true;
}

function onVideoPause() {
  isPlaying.value = false;
}

/** 翻页瞬间把画面冻结成一张图，贴在翻动的纸正面，避免纸面突然变白 */
function captureTurnFrame(): string | null {
  const video = activeVideo();
  if (!video || !video.videoWidth || !video.videoHeight) return null;
  const box = video.parentElement?.getBoundingClientRect();
  if (!box || !box.width || !box.height) return null;

  // 纸面左半边从书脊开始，正好是整幅画面的右二分之一
  const pageW = box.width / 2;
  const pageH = box.height;
  const scale = Math.max(box.width / video.videoWidth, box.height / video.videoHeight);
  const offsetX = (box.width - video.videoWidth * scale) / 2;
  const offsetY = (box.height - video.videoHeight * scale) / 2;

  const sx = Math.max(0, (box.width / 2 - offsetX) / scale);
  const sy = Math.max(0, -offsetY / scale);
  const sw = Math.min(video.videoWidth - sx, pageW / scale);
  const sh = Math.min(video.videoHeight - sy, pageH / scale);
  if (sw <= 0 || sh <= 0) return null;

  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(2, Math.round(pageW * dpr));
  canvas.height = Math.max(2, Math.round(pageH * dpr));
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;
  try {
    ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.86);
  } catch {
    return null;
  }
}

function onFlipStart() {
  flipping.value = true;
  isPlaying.value = false;
  activeVideo()?.pause();
}

function onFlipEnd() {
  flipping.value = false;
  void syncPlayback();
}


const currentItem = computed(() => items.value[currentIndex.value] || null);

const stackVideos = computed(() => {
  const n = items.value.length;
  if (!n) return [] as MaterialItem[];
  const out: MaterialItem[] = [];
  for (let off = -1; off <= 1; off += 1) {
    const i = currentIndex.value + off;
    if (i >= 0 && i < n) out.push(items.value[i]);
  }
  return out;
});

const preloadCovers = computed(() =>
  items.value
    .slice(Math.max(0, currentIndex.value - 1), currentIndex.value + 3)
    .map((it) => it.cover?.content_url || '')
    .filter(Boolean),
);

function promptOf(item: MaterialItem) {
  const raw = (item.description || '').replace(/^#+\s+/gm, '').trim();
  return raw || '作者没有留下这一页的提示词。';
}

function dateLabel(value?: string) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

function durationLabel(item: MaterialItem) {
  const ms = item.video?.duration_ms;
  if (!ms) return '循环播放';
  const total = Math.round(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function handleGoBack() {
  // TV 频道固定回到创作项目空间，不走浏览器历史（避免从编辑器/管理端进来后回退到别处）
  router.push('/workspace');
}

function goToAdminPanel() {
  router.push('/tv/admin');
}

async function checkAdminPermission() {
  try {
    const res = await fetch('/api/v1/admin/material-library?limit=1', {
      method: 'GET',
      credentials: 'include',
    });
    isAdmin.value = res.ok;
  } catch {
    isAdmin.value = false;
  }
}

async function fetchMaterials(cursor?: string) {
  loading.value = true;
  try {
    const url = new URL('/api/v1/material-library', window.location.origin);
    url.searchParams.set('limit', '20');
    if (cursor) url.searchParams.set('cursor', cursor);

    const res = await fetch(url.toString(), { method: 'GET', credentials: 'include' });
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
  const n = items.value.length;
  if (!n) return;
  currentIndex.value = (currentIndex.value - 1 + n) % n;
}

async function nextItem() {
  const n = items.value.length;
  if (!n) return;
  if (currentIndex.value >= n - 2 && nextCursor.value && !loading.value) {
    await fetchMaterials(nextCursor.value);
  }
  const total = items.value.length;
  if (!total) return;
  currentIndex.value = (currentIndex.value + 1) % total;
}

function onVideoEnded() {
  if (flipping.value) return;
  void nextItem();
}

function togglePlay() {
  const video = activeVideo();
  if (!video) return;
  if (video.paused) {
    void video.play().catch(() => undefined);
    isPlaying.value = true;
  } else {
    video.pause();
    isPlaying.value = false;
  }
}

async function copyPrompt(item: MaterialItem) {
  try {
    await navigator.clipboard.writeText(promptOf(item));
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 1800);
  } catch (e) {
    console.error('复制失败', e);
  }
}

function toggleMute() {
  const video = activeVideo();
  isMuted.value = !isMuted.value;
  if (video) video.muted = isMuted.value;
}

async function toggleFullscreen() {
  // 全屏的是当前这条视频，不是整个页面
  if (document.fullscreenElement) {
    try {
      await document.exitFullscreen?.();
    } catch {
      /* 用户或浏览器拒绝，忽略 */
    }
    return;
  }
  const video = activeVideo();
  const target: HTMLElement | null = video ?? containerRef.value;
  if (!target?.requestFullscreen) return;
  try {
    await target.requestFullscreen();
    if (target === video) (video as HTMLVideoElement).controls = true;
  } catch {
    /* 浏览器可能因非用户手势拒绝，忽略 */
  }
}

function toggleInfo() {
  infoOpen.value = !infoOpen.value;
}

function closeInfo() {
  infoOpen.value = false;
}

function onWindowKey(e: KeyboardEvent) {
  if (e.defaultPrevented) return;
  const target = e.target as HTMLElement | null;
  if (target && ['INPUT', 'TEXTAREA'].includes(target.tagName)) return;
  if (e.key === 'Escape' && infoOpen.value) {
    closeInfo();
    return;
  }
  if (infoOpen.value) return;
  if (e.key === 'ArrowRight') {
    e.preventDefault();
    nextItem();
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    prevItem();
  } else if (e.key === ' ') {
    e.preventDefault();
    togglePlay();
  }
}

async function syncPlayback() {
  const all = containerRef.value?.querySelectorAll<HTMLVideoElement>('.ring-video') ?? [];
  const active = activeVideo();
  all.forEach((v) => {
    if (v !== active && !v.paused) v.pause();
  });
  if (!active) {
    isPlaying.value = false;
    return;
  }
  active.muted = isMuted.value;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      await active.play();
      if (!active.paused) {
        isPlaying.value = true;
        return;
      }
    } catch {
      // 尚未缓冲好，稍后再试
    }
    await new Promise((resolve) => setTimeout(resolve, 140));
  }
  isPlaying.value = false;
}

watch(currentIndex, async () => {
  infoOpen.value = false;
  await nextTick();
  // 等翻页的位移先跑起来，再切播放，避免和镜头抢帧
  window.setTimeout(() => {
    void syncPlayback();
  }, 90);
});

function onFullscreenChange() {
  const v = activeVideo();
  if (v) v.controls = document.fullscreenElement === v;
}

onMounted(async () => {
  await fetchMaterials();
  await nextTick();
  await syncPlayback();
  checkAdminPermission();
  window.addEventListener('keydown', onWindowKey);
  document.addEventListener('fullscreenchange', onFullscreenChange);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onWindowKey);
  document.removeEventListener('fullscreenchange', onFullscreenChange);
});
</script>

<style scoped>
.tv-shell {
  position: relative;
  height: 100dvh;
  min-height: 560px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  overflow: hidden;
  background: radial-gradient(130% 90% at 50% 14%, #171922 0%, #0c0d13 46%, #030305 100%);
  color: #f4f2ee;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.tv-ambient {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(58% 42% at 18% 10%, rgba(139, 127, 245, 0.1), transparent 70%),
    radial-gradient(48% 38% at 82% 80%, rgba(240, 214, 176, 0.05), transparent 70%);
}

/* ============ 顶栏 ============ */
.tv-top {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: start;
  gap: 16px;
  padding: 20px 28px 0;
}

.top-side {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.top-side-right {
  justify-content: flex-end;
}

.pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #f4f2ee;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}
.pill-btn:hover {
  background: rgba(255, 255, 255, 0.14);
  border-color: rgba(255, 255, 255, 0.28);
}
.pill-btn svg {
  width: 15px;
  height: 15px;
}
.pill-btn.is-ghost {
  background: rgba(255, 255, 255, 0.05);
}
.pill-btn.is-done {
  border-color: rgba(160, 220, 190, 0.55);
  color: #b8ecd4;
}

.top-center {
  text-align: center;
  min-width: 0;
}

.channel-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(244, 242, 238, 0.62);
}

.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ff5d5d;
  box-shadow: 0 0 0 3px rgba(255, 93, 93, 0.18);
}

.journal-title {
  margin: 8px 0 0;
  font-family: 'Songti SC', 'Noto Serif SC', 'STSong', Georgia, serif;
  font-size: clamp(24px, 2.5vw, 34px);
  font-weight: 700;
  letter-spacing: 0.04em;
}

.journal-sub {
  margin: 6px 0 0;
  font-size: 12px;
  color: rgba(244, 242, 238, 0.56);
}

.page-counter {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  font-variant-numeric: tabular-nums;
  font-family: 'SF Mono', 'JetBrains Mono', ui-monospace, monospace;
}
.counter-now {
  font-size: 20px;
  color: #f4f2ee;
}
.counter-sep,
.counter-all {
  font-size: 13px;
  color: rgba(244, 242, 238, 0.5);
}

/* ============ 舞台 ============ */
.tv-main {
  position: relative;
  z-index: 1;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(90deg, transparent 0, #000 3.5%, #000 96.5%, transparent 100%);
  mask-image: linear-gradient(90deg, transparent 0, #000 3.5%, #000 96.5%, transparent 100%);
}

.stage-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  color: rgba(244, 242, 238, 0.68);
  font-size: 13px;
}

.spinner {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.18);
  border-top-color: rgba(255, 255, 255, 0.7);
  animation: spin 0.9s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.blank-spread {
  display: flex;
  width: min(78vw, 760px);
  aspect-ratio: 1.62;
  border-radius: 6px;
  overflow: hidden;
  background: #ece7dc;
  box-shadow: 0 30px 70px rgba(10, 12, 24, 0.45);
}
.blank-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #8c8578;
  font-size: 13px;
  position: relative;
}
.blank-page + .blank-page {
  border-left: 1px solid rgba(120, 110, 95, 0.18);
  box-shadow: inset 14px 0 22px -16px rgba(80, 70, 55, 0.5);
}
.blank-mark {
  font-size: 26px;
  color: #b3ab9c;
}
.blank-lines {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 62%;
}
.blank-lines i {
  height: 1px;
  background: rgba(140, 133, 120, 0.35);
}
.blank-hint {
  max-width: 68%;
  text-align: center;
  line-height: 1.7;
}
.empty-actions {
  display: flex;
  gap: 10px;
}

/* ============ 书页 ============ */
.page-left {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  color: #3d3646;
}
.page-kicker {
  margin: 0;
  font-family: 'SF Mono', ui-monospace, monospace;
  font-size: 10px;
  letter-spacing: 0.34em;
  color: #8b7d96;
}
.page-title {
  margin: 10px 0 0;
  font-family: 'Songti SC', 'Noto Serif SC', serif;
  font-size: clamp(20px, 2.4vw, 32px);
  font-weight: 600;
  line-height: 1.28;
  color: #2e2836;
}
.page-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.page-chip {
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(129, 140, 248, 0.16);
  color: #5b5bd6;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.page-date,
.page-loop {
  font-size: 11px;
  color: #8a8093;
}
.page-desc {
  margin: 16px 0 0;
  font-size: 13px;
  line-height: 1.95;
  color: #57506a;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 8;
  -webkit-box-orient: vertical;
}
.page-right {
  position: absolute;
  inset: 0;
  overflow: hidden;
  background: #ece7dc;
}
.page-print {
  position: absolute;
  left: 8%;
  right: 8%;
  top: 50%;
  aspect-ratio: 16 / 9;
  transform: translateY(-50%);
  border-radius: 3px;
  overflow: hidden;
  background: #0e1018;
  box-shadow:
    0 0 0 1px rgba(40, 34, 26, 0.28),
    0 14px 30px rgba(8, 10, 18, 0.34);
}
.page-poster,
.page-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  opacity: 0;
  transition: opacity 0.24s ease;
  pointer-events: none;
}
.page-video.is-current {
  pointer-events: auto;
}
.page-video.is-current.is-ready {
  opacity: 1;
}
.page-blank {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(236, 231, 220, 0.3);
  font-family: 'SF Mono', ui-monospace, monospace;
  letter-spacing: 0.2em;
}
.page-no {
  position: absolute;
  left: 0;
  bottom: 0;
  font-family: 'SF Mono', ui-monospace, monospace;
  font-size: 10px;
  letter-spacing: 0.24em;
  color: #a99fb2;
}
.page-poster,
.page-video {
  opacity: 0;
  transition: opacity 0.3s ease;
}
.page-video.is-current.is-ready {
  opacity: 1;
}
.page-blank {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(236, 231, 220, 0.3);
  font-family: 'SF Mono', ui-monospace, monospace;
  letter-spacing: 0.2em;
}
.page-no-right {
  left: auto;
  right: 14px;
  bottom: 12px;
  color: #a99fb2;
}

/* ============ 底栏 ============ */
.tv-bottom {
  position: relative;
  z-index: 2;
  padding: 0 28px 22px;
}

.bottom-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 12px;
}

.bar-hint {
  font-size: 11px;
  color: rgba(244, 242, 238, 0.42);
  white-space: nowrap;
}

.bar-controls {
  display: flex;
  align-items: center;
  gap: 14px;
}

.round-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.07);
  color: #f4f2ee;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease, opacity 0.2s ease;
}
.round-btn svg {
  width: 18px;
  height: 18px;
}
.round-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}
.round-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
.round-btn.is-primary {
  width: 50px;
  height: 50px;
  background: #f4f2ee;
  color: #23283c;
  border-color: transparent;
  box-shadow: 0 10px 26px rgba(8, 10, 18, 0.4);
}
.round-btn.is-primary:hover:not(:disabled) {
  background: #ffffff;
}

.info-btn {
  justify-self: end;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 16px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.08);
  color: #f4f2ee;
  font-size: 12.5px;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}
.info-btn svg {
  width: 15px;
  height: 15px;
}
.info-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(255, 255, 255, 0.32);
}
.info-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

/* ============ 信息抽屉 ============ */
.info-layer {
  position: fixed;
  inset: 0;
  z-index: 30;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: clamp(142px, 17vh, 172px) 20px 22px;
  background: rgba(8, 10, 18, 0.42);
  backdrop-filter: blur(2px);
}

.info-sheet {
  position: relative;
  width: min(720px, 100%);
  max-height: min(62vh, 520px);
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 26px 26px 22px;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: linear-gradient(180deg, rgba(38, 42, 60, 0.96), rgba(26, 29, 43, 0.98));
  box-shadow: 0 28px 70px rgba(4, 6, 14, 0.6);
  color: #eae7e0;
  transform-origin: 50% 0;
}

.sheet-close {
  position: absolute;
  top: 16px;
  right: 16px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(244, 242, 238, 0.8);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.sheet-close svg {
  width: 14px;
  height: 14px;
}

.sheet-kicker {
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(210, 205, 230, 0.55);
}

.sheet-title {
  margin: 8px 0 0;
  font-family: 'Songti SC', 'Noto Serif SC', 'STSong', Georgia, serif;
  font-size: clamp(20px, 2.2vw, 26px);
  font-weight: 700;
  letter-spacing: 0.02em;
}

.sheet-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}
.model-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(139, 127, 245, 0.18);
  border: 1px solid rgba(139, 127, 245, 0.32);
  color: #cfc8ff;
  font-size: 11.5px;
  font-family: 'SF Mono', ui-monospace, monospace;
}
.meta-item {
  font-size: 11.5px;
  color: rgba(234, 231, 224, 0.55);
}

.sheet-prompt {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}
.prompt-label {
  font-size: 11px;
  letter-spacing: 0.14em;
  color: rgba(210, 205, 230, 0.55);
}
.prompt-text {
  margin: 0;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(12, 14, 22, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 13px;
  line-height: 1.85;
  color: rgba(236, 233, 226, 0.86);
  overflow-y: auto;
  max-height: 180px;
  scrollbar-width: none;
}
.prompt-text::-webkit-scrollbar {
  display: none;
}

.sheet-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.22s ease;
}
.sheet-enter-active .info-sheet,
.sheet-leave-active .info-sheet {
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.24s ease;
}
.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}
.sheet-enter-from .info-sheet,
.sheet-leave-to .info-sheet {
  transform: translateY(-14px) scale(0.96);
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .sheet-enter-active,
  .sheet-leave-active,
  .sheet-enter-active .info-sheet,
  .sheet-leave-active .info-sheet {
    transition: none;
  }
}

@media (max-width: 860px) {
  .tv-top {
    padding: 14px 16px 0;
    grid-template-columns: auto 1fr auto;
  }
  .journal-title {
    font-size: 22px;
  }
  .journal-sub,
  .pill-btn span,
  .bar-hint {
    display: none;
  }
  .tv-bottom {
    padding: 0 16px 18px;
  }
  .bottom-bar {
    grid-template-columns: auto 1fr auto;
  }
  .info-btn span {
    display: none;
  }
  .info-btn {
    width: 42px;
    padding: 0;
    justify-content: center;
  }
  .info-sheet {
    max-height: 72vh;
    padding: 22px 18px 18px;
  }
}

/* ===== 环形卡片 ===== */
.ring-face {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background:
    radial-gradient(90% 70% at 20% 8%, rgba(168, 150, 255, 0.22) 0%, rgba(84, 68, 190, 0.08) 38%, transparent 68%),
    radial-gradient(120% 120% at 80% 100%, rgba(56, 189, 248, 0.14) 0%, transparent 60%),
    linear-gradient(160deg, #14131f 0%, #0b0a12 55%, #050409 100%);
}
.ring-face.tone-1 {
  background:
    radial-gradient(90% 70% at 20% 8%, rgba(120, 226, 255, 0.2) 0%, rgba(28, 140, 190, 0.08) 40%, transparent 70%),
    radial-gradient(120% 120% at 80% 100%, rgba(120, 255, 214, 0.12) 0%, transparent 62%),
    linear-gradient(160deg, #101c22 0%, #081218 55%, #03080b 100%);
}
.ring-face.tone-2 {
  background:
    radial-gradient(90% 70% at 20% 8%, rgba(255, 170, 214, 0.2) 0%, rgba(190, 70, 140, 0.08) 40%, transparent 70%),
    radial-gradient(120% 120% at 80% 100%, rgba(255, 196, 120, 0.12) 0%, transparent 62%),
    linear-gradient(160deg, #1c101d 0%, #110813 55%, #060308 100%);
}
.ring-face.tone-3 {
  background:
    radial-gradient(90% 70% at 20% 8%, rgba(255, 226, 150, 0.18) 0%, rgba(190, 140, 40, 0.08) 40%, transparent 70%),
    radial-gradient(120% 120% at 80% 100%, rgba(255, 140, 90, 0.1) 0%, transparent 62%),
    linear-gradient(160deg, #1b170c 0%, #100d06 55%, #050402 100%);
}
.ring-caption {
  position: absolute;
  left: 16px;
  bottom: 12px;
  max-width: 70%;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.78);
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.7);
  z-index: 2;
  opacity: 0;
  transition: opacity 0.3s ease;
}
.ring-card[data-active] .ring-caption {
  opacity: 1;
}
.ring-poster {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ring-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.42;
  filter: saturate(0.75) brightness(0.8);
  transition: opacity 0.32s ease;
}
.ring-video.is-active {
  opacity: 1;
  filter: none;
}
.ring-folio {
  position: absolute;
  right: 16px;
  bottom: 12px;
  font-family: 'SF Mono', ui-monospace, monospace;
  font-size: 10px;
  letter-spacing: 0.18em;
  color: rgba(255, 255, 255, 0.62);
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.7);
  z-index: 2;
}

/* ===== 跨页视频 + 顶部信息按钮（2026-11-14） ===== */
.bar-tools {
  justify-self: end;
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.round-btn.is-ghost {
  width: 38px;
  height: 38px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: rgba(244, 242, 238, 0.9);
}
.round-btn.is-ghost:hover {
  background: rgba(255, 255, 255, 0.16);
}
.round-btn.is-ghost svg {
  width: 18px;
  height: 18px;
}
.copy-inline {
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(234, 231, 224, 0.86);
  font-size: 11.5px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}
.copy-inline:hover {
  background: rgba(255, 255, 255, 0.14);
}
.copy-inline.is-done {
  color: #9be7c4;
  border-color: rgba(155, 231, 196, 0.4);
}
.video-preload {
  position: fixed;
  left: -9999px;
  top: -9999px;
  width: 2px;
  height: 2px;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}
.journal-title {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 8px;
  max-width: min(74vw, 860px);
  white-space: nowrap;
}
.journal-title .title-name {
  flex: 0 0 auto;
}
.journal-title .title-dot {
  color: rgba(244, 242, 238, 0.42);
}
.journal-title .title-item {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.62em;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: rgba(244, 242, 238, 0.9);
}

.info-btn.info-top {
  display: flex;
  justify-self: center;
  margin: 10px auto 0;
  height: 30px;
  padding: 0 14px;
  font-size: 11.5px;
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.16);
}
.info-btn.info-top:hover {
  background: rgba(255, 255, 255, 0.12);
}

.bar-spacer {
  justify-self: end;
  width: 1px;
  height: 1px;
}

.spread-media {
  position: absolute;
  left: 0;
  top: 0;
  width: 200%;
  height: 100%;
  z-index: 2;
  overflow: hidden;
  background: #0e1018;
}
.spread-media::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 30px;
  transform: translateX(-50%);
  pointer-events: none;
  background: linear-gradient(
    90deg,
    rgba(24, 19, 12, 0) 0%,
    rgba(24, 19, 12, 0.16) 42%,
    rgba(24, 19, 12, 0.26) 50%,
    rgba(24, 19, 12, 0.16) 58%,
    rgba(24, 19, 12, 0) 100%
  );
}
.spread-media.is-turning {
  /* 翻页时画面保持冻结，纸张从右页掀开；不做半幅裁切以免露出空白 */
  filter: saturate(0.98);
}
.media-poster {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.spread-media .page-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.page-folio {
  position: absolute;
  right: clamp(14px, 2.2vw, 28px);
  bottom: clamp(12px, 2vh, 20px);
  font-family: 'SF Mono', ui-monospace, monospace;
  font-size: 10px;
  letter-spacing: 0.18em;
  color: rgba(255, 255, 255, 0.62);
  text-shadow: 0 1px 6px rgba(0, 0, 0, 0.65);
  z-index: 4;
}

</style>
