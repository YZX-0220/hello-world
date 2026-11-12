<template>
  <section class="player-preview-pane">
    <!-- 顶部画幅比例切换与状态头 -->
    <div class="pane-top-header">
      <div class="left-info">
        <span class="preview-title">
          {{ previewingAsset ? `素材预览: ${previewingAsset.file_name}` : `预览视窗 (${timeline.width} × ${timeline.height})` }}
        </span>
        <button 
          v-if="previewingAsset" 
          class="exit-asset-preview-btn" 
          @click="exitAssetPreview"
        >
          ← 返回时间轴画面
        </button>
      </div>

      <div class="aspect-switcher">
        <button 
          class="ratio-btn" 
          :class="{ active: timeline.width === 1920 && timeline.height === 1080 }"
          @click="$emit('changeAspect', '16:9')"
        >
          16:9 (横屏)
        </button>
        <button 
          class="ratio-btn" 
          :class="{ active: timeline.width === 1080 && timeline.height === 1920 }"
          @click="$emit('changeAspect', '9:16')"
        >
          9:16 (竖屏)
        </button>
        <button 
          class="ratio-btn" 
          :class="{ active: timeline.width === 1080 && timeline.height === 1080 }"
          @click="$emit('changeAspect', '1:1')"
        >
          1:1
        </button>
      </div>
    </div>

    <!-- 中间核心画布视窗 -->
    <div class="canvas-viewport">
      <!-- 模式 A：左侧素材独立预览层（单击视频或音频时触发，还原图二、图三） -->
      <div v-if="previewingAsset" class="standalone-asset-stage" @click="toggleAssetPlay">
        <!-- 1. 视频素材直接全画幅播放 -->
        <video 
          v-if="previewingAsset.kind === 'video' && !isBuiltinMatte(previewingAsset.id)"
          ref="standaloneVideoRef"
          :src="previewingAsset.url"
          class="standalone-video-player"
          autoplay
          playsinline
          disablepictureinpicture
          @timeupdate="onStandaloneTimeUpdate"
          @loadedmetadata="onStandaloneMetadata"
          @ended="isAssetPlaying = false"
          @play="isAssetPlaying = true"
          @pause="isAssetPlaying = false"
        ></video>

        <!-- 2. 图片或内置黑白场预览 -->
        <img 
          v-else-if="previewingAsset.kind === 'image' || isBuiltinMatte(previewingAsset.id)"
          :src="previewingAsset.url"
          class="standalone-video-player"
        />

        <!-- 3. 音频素材预览：纯黑背景 + 正中央深灰圆角音符卡片 (还原图二) -->
        <div v-else-if="previewingAsset.kind === 'audio'" class="standalone-audio-stage">
          <div class="music-note-card" :class="{ playing: isAssetPlaying }">
            <svg viewBox="0 0 24 24" fill="currentColor" class="tiktok-note-icon">
              <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
            </svg>
          </div>
          <audio 
            ref="standaloneAudioRef"
            :src="previewingAsset.url"
            autoplay
            @timeupdate="onStandaloneTimeUpdate"
            @loadedmetadata="onStandaloneMetadata"
            @ended="isAssetPlaying = false"
            @play="isAssetPlaying = true"
            @pause="isAssetPlaying = false"
          ></audio>
        </div>

        <!-- 底部独立进度条（类似图三播放器底部的进度滑杆） -->
        <div class="standalone-scrubber-bar" @click.stop="handleStandaloneScrub">
          <div 
            class="scrubber-progress" 
            :style="{ width: `${assetDurationMs > 0 ? Math.min(100, (assetCurrentMs / assetDurationMs) * 100) : 0}%` }"
          ></div>
          <div 
            class="scrubber-thumb"
            :style="{ left: `${assetDurationMs > 0 ? Math.min(100, (assetCurrentMs / assetDurationMs) * 100) : 0}%` }"
          ></div>
        </div>
      </div>

      <!-- 模式 B：时间轴多轨合成 Canvas 画布 -->
      <canvas 
        v-show="!previewingAsset"
        ref="canvasElRef" 
        class="preview-canvas"
        @mousedown="handleCanvasDragStart"
      ></canvas>
    </div>

    <!-- 底部播放控制栏 -->
    <div class="player-controls-bar">
      <!-- 左侧时间码：根据当前是素材预览还是时间轴预览自动切换 -->
      <div class="timecode-box">
        <template v-if="previewingAsset">
          <span class="cur-time asset-mode">{{ formatTimecode(assetCurrentMs) }}</span>
          <span class="sep">/</span>
          <span class="total-time">{{ formatTimecode(assetDurationMs) }}</span>
        </template>
        <template v-else>
          <span class="cur-time">{{ formatTimecode(currentTimeMs) }}</span>
          <span class="sep">/</span>
          <span class="total-time">{{ formatTimecode(timeline.duration_ms) }}</span>
        </template>
      </div>

      <!-- 中间播放/暂停与单帧步进按钮 -->
      <div class="transport-btns">
        <button class="ctrl-btn" title="上一帧" @click="handleStep(-1)">⏮</button>
        <button class="play-main-btn" @click="handleMainPlayToggle">
          {{ (previewingAsset ? isAssetPlaying : isPlaying) ? '⏸' : '▶' }}
        </button>
        <button class="ctrl-btn" title="下一帧" @click="handleStep(1)">⏭</button>
      </div>

      <!-- 右侧状态指示 -->
      <div class="right-status">
        <span class="engine-dot"></span>
        <span>WebAV {{ timeline.fps || 30 }}fps</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue';
import type { TimelineDocument, TimelineClip, LibraryAssetView } from '../../types/clip';

const props = defineProps<{
  timeline: TimelineDocument;
  currentTimeMs: number;
  isPlaying: boolean;
  activeClip?: TimelineClip | null;
  previewingAsset?: LibraryAssetView | null;
}>();

const emit = defineEmits<{
  (e: 'togglePlay'): void;
  (e: 'stepFrame', frames: number): void;
  (e: 'changeAspect', ratio: '16:9' | '9:16' | '1:1'): void;
  (e: 'canvasReady', el: HTMLCanvasElement | null): void;
  (e: 'closeAssetPreview'): void;
}>();

const canvasElRef = ref<HTMLCanvasElement | null>(null);
const standaloneVideoRef = ref<HTMLVideoElement | null>(null);
const standaloneAudioRef = ref<HTMLAudioElement | null>(null);

// 独立素材预览状态
const isAssetPlaying = ref(false);
const assetCurrentMs = ref(0);
const assetDurationMs = ref(0);

function isBuiltinMatte(id?: string): boolean {
  return id === 'builtin_black_5s' || id === 'builtin_white_5s';
}

// 当外部传入新的 previewingAsset 时，立即重置并启动播放
watch(
  () => props.previewingAsset,
  async (newAsset) => {
    if (!newAsset) {
      isAssetPlaying.value = false;
      return;
    }
    assetCurrentMs.value = 0;
    assetDurationMs.value = newAsset.duration_ms || 5000;
    await nextTick();

    const mediaEl = standaloneVideoRef.value || standaloneAudioRef.value;
    if (mediaEl) {
      mediaEl.currentTime = 0;
      mediaEl.play().then(() => {
        isAssetPlaying.value = true;
      }).catch(() => {
        isAssetPlaying.value = false;
      });
    }
  }
);

function onStandaloneTimeUpdate(e: Event) {
  const el = e.target as HTMLMediaElement;
  assetCurrentMs.value = Math.round(el.currentTime * 1000);
}

function onStandaloneMetadata(e: Event) {
  const el = e.target as HTMLMediaElement;
  if (Number.isFinite(el.duration) && el.duration > 0) {
    assetDurationMs.value = Math.round(el.duration * 1000);
  }
}

function toggleAssetPlay() {
  const mediaEl = standaloneVideoRef.value || standaloneAudioRef.value;
  if (!mediaEl) return;
  if (mediaEl.paused) {
    void mediaEl.play();
  } else {
    mediaEl.pause();
  }
}

function handleStandaloneScrub(e: MouseEvent) {
  const bar = e.currentTarget as HTMLElement;
  const rect = bar.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / Math.max(1, rect.width)));
  const targetMs = Math.round(ratio * assetDurationMs.value);
  assetCurrentMs.value = targetMs;

  const mediaEl = standaloneVideoRef.value || standaloneAudioRef.value;
  if (mediaEl) {
    mediaEl.currentTime = targetMs / 1000;
  }
}

function exitAssetPreview() {
  emit('closeAssetPreview');
}

function handleMainPlayToggle() {
  if (props.previewingAsset) {
    toggleAssetPlay();
  } else {
    emit('togglePlay');
  }
}

function handleStep(frames: number) {
  if (props.previewingAsset) {
    const mediaEl = standaloneVideoRef.value || standaloneAudioRef.value;
    if (mediaEl) {
      const stepSec = frames / (props.timeline.fps || 30);
      mediaEl.currentTime = Math.max(0, Math.min(mediaEl.duration || 0, mediaEl.currentTime + stepSec));
    }
  } else {
    emit('stepFrame', frames);
  }
}

// 画布上按住鼠标左键自由拖动【视频画面】或【文本字幕】
function handleCanvasDragStart(e: MouseEvent) {
  if (!props.activeClip || (props.activeClip.type !== 'video' && props.activeClip.type !== 'text')) return;

  const clip = props.activeClip as any;
  const startMouseX = e.clientX;
  const startMouseY = e.clientY;
  const initialX = clip.position_x || 0;
  const initialY = clip.position_y || 0;

  const canvasEl = canvasElRef.value;
  const scaleX = canvasEl ? (props.timeline.width / Math.max(1, canvasEl.clientWidth)) : 2;
  const scaleY = canvasEl ? (props.timeline.height / Math.max(1, canvasEl.clientHeight)) : 2;

  function onMouseMove(moveEvent: MouseEvent) {
    const deltaX = moveEvent.clientX - startMouseX;
    const deltaY = moveEvent.clientY - startMouseY;
    clip.position_x = Math.round(initialX + deltaX * scaleX);
    clip.position_y = Math.round(initialY + deltaY * scaleY);
  }

  function onMouseUp() {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}

function formatTimecode(ms: number) {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(totalSec / 60).toString().padStart(2, '0');
  const s = (totalSec % 60).toString().padStart(2, '0');
  const f = Math.floor((ms % 1000) / (1000 / (props.timeline.fps || 30))).toString().padStart(2, '0');
  return `00:${m}:${s}.${f}`;
}

onMounted(() => {
  emit('canvasReady', canvasElRef.value);
});
</script>

<style scoped>
.player-preview-pane {
  display: flex;
  flex-direction: column;
  background-color: #0b0a0f;
  height: 100%;
  min-height: 0;
  position: relative;
  overflow: hidden;
  user-select: none;
}

.pane-top-header {
  height: 38px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background-color: #121118;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 11px;
  color: #71717a;
}

.left-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.exit-asset-preview-btn {
  background: rgba(0, 229, 255, 0.12);
  border: 1px solid rgba(0, 229, 255, 0.35);
  color: #00e5ff;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.exit-asset-preview-btn:hover {
  background: rgba(0, 229, 255, 0.22);
}

.aspect-switcher {
  display: flex;
  gap: 6px;
}

.ratio-btn {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #a1a1aa;
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
}

.ratio-btn.active {
  background: #6366f1;
  color: #fff;
  border-color: #6366f1;
}

.canvas-viewport {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #141318;
  background-image: 
    linear-gradient(45deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%), 
    linear-gradient(-45deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%), 
    linear-gradient(45deg, transparent 75%, rgba(255, 255, 255, 0.02) 75%), 
    linear-gradient(-45deg, transparent 75%, rgba(255, 255, 255, 0.02) 75%);
  background-size: 20px 20px;
  position: relative;
  overflow: hidden;
  padding: 16px;
  box-sizing: border-box;
}

.preview-canvas {
  background-color: #000000 !important;
  border: 1px solid rgba(255, 255, 255, 0.18);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.75);
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  cursor: crosshair;
}

/* ================= 独立素材预览舞台（还原图二、图三） ================= */
.standalone-asset-stage {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #000000;
  border: 1px solid rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: pointer;
}

.standalone-video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
  pointer-events: none;
}

/* 图二同款：纯黑背景 + 中央深灰圆角音符卡片 */
.standalone-audio-stage {
  width: 100%;
  height: 100%;
  background: #000000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.music-note-card {
  width: 136px;
  height: 136px;
  background-color: #202024;
  border-radius: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #e4e4e7;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6);
  transition: transform 0.3s ease;
}

.music-note-card.playing {
  animation: pulseNote 2s infinite ease-in-out;
}

@keyframes pulseNote {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.04); }
}

.tiktok-note-icon {
  width: 48px;
  height: 48px;
}

/* 底部独立进度条（还原图三） */
.standalone-scrubber-bar {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 8px;
  height: 6px;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 3px;
  cursor: pointer;
  z-index: 20;
}

.scrubber-progress {
  height: 100%;
  background: #00e5ff;
  border-radius: 3px;
}

.scrubber-thumb {
  position: absolute;
  top: 50%;
  width: 4px;
  height: 12px;
  background: #ffffff;
  border-radius: 2px;
  transform: translate(-50%, -50%);
}

.player-controls-bar {
  height: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background-color: #121118;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  z-index: 10;
}

.timecode-box {
  font-family: monospace;
  font-size: 12px;
  display: flex;
  gap: 6px;
}

.cur-time { color: #ef4444; font-weight: 600; }
.cur-time.asset-mode { color: #00e5ff; }
.sep, .total-time { color: #71717a; }

.transport-btns {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ctrl-btn {
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 14px;
  cursor: pointer;
}

.play-main-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: #6366f1;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.right-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #10b981;
  font-family: monospace;
}

.engine-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
}
</style>