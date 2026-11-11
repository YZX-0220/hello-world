<template>
  <div class="player-preview-pane">
    <!-- 顶部状态与画幅切换栏 -->
    <div class="pane-top-header">
      <span class="view-indicator">播放器视窗 ({{ timeline.width }} × {{ timeline.height }})</span>
      
      <div class="aspect-badges">
        <!-- 比例切换按钮 -->
        <span 
          class="badge" 
          :class="{ active: timeline.width === 1920 && timeline.height === 1080 }" 
          @click="$emit('changeAspect', '16:9')"
        >
          16:9 (横屏)
        </span>
        <span 
          class="badge" 
          :class="{ active: timeline.width === 1080 && timeline.height === 1920 }" 
          @click="$emit('changeAspect', '9:16')"
        >
          9:16 (竖屏)
        </span>
        <span class="badge" @click="toggleFullscreen" title="视窗全屏">⛶</span>
      </div>
    </div>

    <!-- 中间 Canvas 渲染视窗 -->
    <div class="canvas-viewport" ref="viewportRef">
      <canvas 
        ref="canvasElRef" 
        class="preview-canvas"
        :class="{ 'aspect-16-9': timeline.width >= timeline.height, 'aspect-9-16': timeline.width < timeline.height }"
        @mousedown="handleCanvasDragStart"
      ></canvas>

      <!-- 导出合成时的进度遮罩 -->
      <div v-if="isExporting" class="export-overlay">
        <div class="spinner"></div>
        <span>正在纯前端合成 MP4... {{ exportProgress }}%</span>
      </div>
    </div>

    <!-- 底部播放控制器与时间码 -->
    <div class="player-controls-bar">
      <div class="timecode-display">
        <span class="cur-time">{{ formatTimecode(currentTimeMs) }}</span>
        <span class="sep">/</span>
        <span class="total-time">{{ formatTimecode(timeline.duration_ms) }}</span>
      </div>

      <div class="playback-buttons">
        <button class="step-btn" @click="$emit('step', -1)" title="上一帧">⏮</button>
        <button class="play-main-btn" @click="$emit('togglePlay')" :title="isPlaying ? '暂停 (空格)' : '播放 (空格)'">
          <svg v-if="!isPlaying" viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M8 5v14l11-7z"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
          </svg>
        </button>
        <button class="step-btn" @click="$emit('step', 1)" title="下一帧">⏭</button>
      </div>

      <div class="right-aux-status">
        <span class="engine-tag">● WebAV {{ timeline.fps }}fps</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { TimelineDocument, VideoClip } from '../../types/clip';

// 只保留唯一一次 defineProps 声明
const props = defineProps<{
  timeline: TimelineDocument;
  currentTimeMs: number;
  isPlaying: boolean;
  isExporting: boolean;
  exportProgress: number;
  activeClip?: any;
}>();

// 只保留唯一一次 defineEmits 声明
const emit = defineEmits<{
  (e: 'setCanvas', canvas: HTMLCanvasElement): void;
  (e: 'togglePlay'): void;
  (e: 'step', frameCount: number): void;
  (e: 'changeAspect', ratio: '16:9' | '9:16' | '1:1'): void;
}>();

const canvasElRef = ref<HTMLCanvasElement | null>(null);
const viewportRef = ref<HTMLElement | null>(null);

// 格式化时间码 00:00:00.00
function formatTimecode(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) ms = 0;
  const totalSeconds = Math.floor(ms / 1000);
  const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
  const s = (totalSeconds % 60).toString().padStart(2, '0');
  const f = Math.floor((ms % 1000) / 10).toString().padStart(2, '0');
  return `00:${m}:${s}.${f}`;
}

// 全屏控制
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    viewportRef.value?.requestFullscreen?.();
  } else {
    document.exitFullscreen?.();
  }
}

// 画布上按住鼠标左键自由拖动【视频画面】或【文本字幕】的 position_x 和 position_y
function handleCanvasDragStart(e: MouseEvent) {
  if (!props.activeClip || (props.activeClip.type !== 'video' && props.activeClip.type !== 'text')) return;

  const clip = props.activeClip as any;
  const startMouseX = e.clientX;
  const startMouseY = e.clientY;
  const initialX = clip.position_x || 0;
  const initialY = clip.position_y || 0;

  // 根据预览画布的显示尺寸与实际分辨率换算拖拽比例，确保鼠标跟手
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

onMounted(() => {
  if (canvasElRef.value) {
    emit('setCanvas', canvasElRef.value);
  }
});
</script>

<style scoped>
.player-preview-pane {
  display: flex;
  flex-direction: column;
  background-color: #0b0a0f;
  height: 100%;
  min-height: 0; /* 关键修复 */
  position: relative;
  overflow: hidden;
  user-select: none;
}

.pane-top-header {
  height: 38px;
  flex-shrink: 0; /* 禁止顶部栏被挤压 */
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background-color: #121118;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 11px;
  color: #71717a;
}

.canvas-viewport {
  flex: 1;
  min-height: 0; /* 关键修复：允许画布容器随剩余空间自适应缩放，绝不把底部播放栏顶出去 */
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

.player-controls-bar {
  height: 48px;
  flex-shrink: 0; /* 关键修复：锁死底部播放控制条高度，任何情况下都不允许被挤没 */
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background-color: #121118;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  z-index: 10;
}

.aspect-badges {
  display: flex;
  gap: 8px;
  align-items: center;
}

.aspect-badges .badge {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  color: #a1a1aa;
  font-size: 11px;
  transition: all 0.2s;
}

.aspect-badges .badge:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.aspect-badges .badge.active {
  background: #6366f1;
  border-color: #818cf8;
  color: #fff;
}




/* 核心画布：内部视频展示区域改为全黑背景，外部工作台保持棋盘格 */
.preview-canvas {
  background-color: #000000 !important;
  border: 1px solid rgba(255, 255, 255, 0.18);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.75);
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  cursor: crosshair;
}

.preview-canvas.aspect-16-9 {
  aspect-ratio: 16 / 9;
}

.preview-canvas.aspect-9-16 {
  aspect-ratio: 9 / 16;
}

.export-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #fff;
  font-size: 13px;
  z-index: 50;
  backdrop-filter: blur(4px);
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(255, 255, 255, 0.15);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  100% { transform: rotate(360deg); }
}


.timecode-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: monospace;
  font-size: 13px;
}

.cur-time { color: #f43f5e; font-weight: 600; }
.sep { color: #52525b; }
.total-time { color: #a1a1aa; }

.playback-buttons {
  display: flex;
  align-items: center;
  gap: 14px;
}

.step-btn {
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.15s;
}

.step-btn:hover { color: #fff; }

.play-main-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #6366f1;
  border: none;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s, background-color 0.2s;
}

.play-main-btn:hover {
  background: #4f46e5;
  transform: scale(1.08);
}

.right-aux-status {
  font-size: 11px;
}

.engine-tag {
  color: #10b981;
  font-family: monospace;
}
</style>