<template>
  <div class="timeline-container" ref="timelineRootRef">
    <!-- 1. 轨道控制器头部列表 (左侧固定列) -->
    <div class="track-headers-column">
      <div class="ruler-corner-block">
        <span class="track-count-text">轨道 ({{ timeline.tracks.length }})</span>
        <button class="quick-add-track-btn" @click="showAddTrackMenu = !showAddTrackMenu" title="手动增加轨道">+</button>

        <!-- 增轨下拉菜单 -->
        <div v-if="showAddTrackMenu" class="add-track-dropdown">
          <div class="dropdown-item" @click="handleManualAddTrack('text')">＋ 文本轨道</div>
          <div class="dropdown-item" @click="handleManualAddTrack('video')">＋ 视频/画中画轨道</div>
          <div class="dropdown-item" @click="handleManualAddTrack('audio')">＋ 音频轨道</div>
        </div>
      </div>

      <!-- 单个轨道头控制面板 -->
      <div v-for="track in timeline.tracks" :key="'head_' + track.id" class="track-header-row" :class="track.type">
        <span class="track-badge">{{ track.type.toUpperCase() }}</span>
        <span class="track-name" :title="track.name">{{ track.name }}</span>

        <div class="track-controls">
          <!-- 视频/文本：显示/隐藏 -->
          <button v-if="track.type !== 'audio'" class="ctrl-icon-btn" :class="{ active: track.hidden }"
            @click="track.hidden = !track.hidden" :title="track.hidden ? '取消隐藏' : '隐藏画面'">
            {{ track.hidden ? '🚫' : '👁' }}
          </button>

          <!-- 视频/音频：静音 -->
          <button v-if="track.type !== 'text'" class="ctrl-icon-btn" :class="{ active: track.muted }"
            @click="track.muted = !track.muted" :title="track.muted ? '取消静音' : '静音轨道'">
            {{ track.muted ? '🔇' : '🔊' }}
          </button>

          <!-- 锁定轨道 -->
          <button class="ctrl-icon-btn" :class="{ active: track.locked }" @click="track.locked = !track.locked"
            :title="track.locked ? '解锁轨道' : '锁定防误触'">
            {{ track.locked ? '🔒' : '🔓' }}
          </button>

          <!-- 删除空轨道 -->
          <button class="ctrl-icon-btn del-track-btn" @click="$emit('removeTrack', track.id)" title="删除轨道">
            ×
          </button>
        </div>
      </div>
    </div>

    <!-- 2. 时间刻度标尺与轨道内容滚动区域 (右侧) -->
    <div class="tracks-scroll-area" ref="scrollAreaRef" @scroll="handleTimelineScroll">
      <div class="timeline-viewport" :style="{ width: `${timelineCanvasWidth}px` }">

        <!-- 时间刻度标尺栏 -->
        <div class="time-ruler-bar" @click="handleRulerClick">
          <div v-for="tick in rulerTicks" :key="tick.timeMs" class="ruler-tick-mark"
            :style="{ left: `${tick.leftPx}px` }">
            <div class="tick-line" :class="{ major: tick.isMajor }"></div>
            <span v-if="tick.isMajor" class="tick-time-label">{{ tick.label }}</span>
          </div>

          <!-- 标记点渲染 -->
          <div v-for="marker in timeline.markers" :key="marker.id" class="marker-indicator"
            :style="{ left: `${msToPx(marker.time_ms)}px` }" :title="marker.label">
            <span class="marker-flag">🔖</span>
          </div>
        </div>

        <!-- 垂直时间游标指针 Playhead -->
        <div class="playhead-line" :style="{ transform: `translateX(${msToPx(currentTimeMs)}px)` }">
          <div class="playhead-handle" @mousedown.stop="startScrubbing">
            <div class="handle-diamond"></div>
          </div>
        </div>

        <!-- 各轨道内容泳道容器 -->
        <!-- 各轨道内容泳道容器 -->
        <div class="track-lanes-wrapper">
          <div v-for="track in timeline.tracks" :key="'lane_' + track.id" class="track-lane-row"
            :class="[track.type, { locked: track.locked }]" @dragover.prevent="handleLaneDragOver"
            @drop="handleLaneDrop($event, track)">
            <!-- 泳道内片段列表：每个片段为一个完整的 clip-card -->
            <div v-for="clip in track.clips" :key="clip.id" class="clip-card"
              :class="[clip.type, { selected: selectedClipId === clip.id }]" :style="{
                left: `${msToPx(clip.start_ms)}px`,
                width: `${Math.max(24, msToPx(clip.duration_ms))}px`
              }" @mousedown.stop="startDragClip($event, clip, track)">
              <!-- 1. 左边缘修剪手柄 (调整入点) -->
              <div class="clip-trim-handle left-handle" @mousedown.stop="startTrim($event, clip, 'in')"></div>

              <!-- 2. 片段卡片本体内容 -->
              <div class="clip-content-box">
                <span class="clip-tag-icon">
                  {{ clip.type === 'text' ? 'T' : clip.type === 'video' ? '🎬' : '🎵' }}
                </span>
                <span class="clip-label">
                  {{ clip.type === 'text' ? (clip as any).text : (clip as any).file_name }}
                </span>
              </div>

              <!-- 3. 右边缘修剪手柄 (调整出点) -->
              <div class="clip-trim-handle right-handle" @mousedown.stop="startTrim($event, clip, 'out')"></div>
            </div>
          </div>

          <!-- 底部吸附放手新建轨道区域 (自适应加轨) -->
          <div class="drop-to-new-track-zone" @dragover.prevent @drop="handleDropToNewTrack">
            <span>+ 拖拽素材至此空白区域以自适应新建专属轨道</span>
          </div>
        </div>
      </div>
    </div>
  </div>

</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { TimelineDocument, TimelineTrack, TimelineClip, TrackType } from '../../types/clip';

const props = defineProps<{
  timeline: TimelineDocument;
  currentTimeMs: number;
  selectedClipId: string | null;
  zoomScale: number;
}>();

const emit = defineEmits<{
  (e: 'update:currentTimeMs', val: number): void;
  (e: 'selectClip', clipId: string | null): void;
  (e: 'addTrack', type: TrackType): void;
  (e: 'removeTrack', trackId: string): void;
  (e: 'appendClip', trackId: string, clipData: any): void;
}>();

const timelineRootRef = ref<HTMLElement | null>(null);
const scrollAreaRef = ref<HTMLElement | null>(null);
const showAddTrackMenu = ref(false);

// 1. 坐标与时间转换工具（基于 1 秒 = 60px * zoomScale）
function msToPx(ms: number): number {
  return (ms / 1000) * 60 * props.zoomScale;
}

function pxToMs(px: number): number {
  return (px / (60 * props.zoomScale)) * 1000;
}

// 时间轴总画布宽度（至少铺满 1200px）
const timelineCanvasWidth = computed(() => {
  const durationPx = msToPx(props.timeline.duration_ms + 10000);
  return Math.max(1400, durationPx);
});

// 计算刻度线列表
const rulerTicks = computed(() => {
  const ticks = [];
  const totalMs = Math.max(props.timeline.duration_ms + 10000, 30000);
  const stepMs = props.zoomScale < 0.6 ? 5000 : props.zoomScale > 2.0 ? 500 : 1000;

  for (let ms = 0; ms <= totalMs; ms += stepMs) {
    const isMajor = ms % (stepMs * 5) === 0;
    const sec = Math.floor(ms / 1000);
    const m = Math.floor(sec / 60).toString().padStart(2, '0');
    const s = (sec % 60).toString().padStart(2, '0');
    ticks.push({
      timeMs: ms,
      leftPx: msToPx(ms),
      isMajor,
      label: `${m}:${s}`
    });
  }
  return ticks;
});

// 手动增轨
function handleManualAddTrack(type: TrackType) {
  emit('addTrack', type);
  showAddTrackMenu.value = false;
}

// 点击标尺跳转指针
function handleRulerClick(e: MouseEvent) {
  const target = e.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  emit('update:currentTimeMs', Math.max(0, pxToMs(clickX)));
}

// 拖拽指针游标 Scrubbing
function startScrubbing(e: MouseEvent) {
  const startX = e.clientX;
  const initialMs = props.currentTimeMs;

  function onMouseMove(moveEvent: MouseEvent) {
    const deltaX = moveEvent.clientX - startX;
    const newMs = Math.max(0, initialMs + pxToMs(deltaX));
    emit('update:currentTimeMs', newMs);
  }

  function onMouseUp() {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}

// 选中片段
function handleClipSelect(clipId: string) {
  emit('selectClip', clipId);
}

// 拖拽素材放入现有轨道 (严格校验轨道类型与隔离原则)
function handleLaneDragOver(e: DragEvent) {
  e.dataTransfer!.dropEffect = 'copy';
}

function handleLaneDrop(e: DragEvent, track: TimelineTrack) {
  if (track.locked) return;
  const raw = e.dataTransfer?.getData('application/json');
  if (!raw) return;

  try {
    const data = JSON.parse(raw);
    const dropX = e.offsetX;
    const startMs = Math.max(0, pxToMs(dropX));

    if (data.sourceType === 'text') {
      if (track.type !== 'text') {
        alert('文本素材只能放入文本轨道！');
        return;
      }
      emit('appendClip', track.id, {
        type: 'text',
        start_ms: startMs,
        duration_ms: 3000,
        text: data.text,
        color: data.color,
        font_size: data.fontSize
      });
    } else if (data.sourceType === 'asset') {
      // 图片与视频均归入视频轨，音频放入音频轨
      const compatibleType: TrackType = data.kind === 'audio' ? 'audio' : 'video';
      if (track.type !== compatibleType) {
        alert(`${data.kind === 'audio' ? '音频' : '视频/图片'} 素材只能放入对应专属轨道！`);
        return;
      }

      emit('appendClip', track.id, {
        type: compatibleType,
        asset_id: data.assetId,
        sha256: data.sha256,
        file_name: data.fileName,
        source_url: data.url, // 👈 确保这里有值！
        start_ms: startMs,
        duration_ms: data.durationMs,
        is_image_source: data.isImageSource
      });
    }
  } catch (err) {
    console.error('拖拽入轨解析失败', err);
  }
}

// 拖入空白区域，自适应新建对应类型的专属轨道
function handleDropToNewTrack(e: DragEvent) {
  const raw = e.dataTransfer?.getData('application/json');
  if (!raw) return;
  try {
    const data = JSON.parse(raw);
    const targetType: TrackType = data.sourceType === 'text' ? 'text' : data.kind === 'audio' ? 'audio' : 'video';
    emit('addTrack', targetType);
  } catch (err) {
    console.warn(err);
  }
}

// 片段入点/出点伸缩修剪
function startTrim(e: MouseEvent, clip: TimelineClip, edge: 'in' | 'out') {
  const startX = e.clientX;
  const initialDuration = clip.duration_ms;
  const initialStart = clip.start_ms;

  function onMouseMove(moveEvent: MouseEvent) {
    const deltaMs = pxToMs(moveEvent.clientX - startX);
    if (edge === 'out') {
      clip.duration_ms = Math.max(500, initialDuration + deltaMs);
      clip.out_point_ms = clip.in_point_ms + clip.duration_ms;
    } else {
      const clampedDelta = Math.min(deltaMs, initialDuration - 500);
      clip.start_ms = Math.max(0, initialStart + clampedDelta);
      clip.duration_ms = initialDuration - clampedDelta;
      clip.in_point_ms = Math.max(0, clip.in_point_ms + clampedDelta);
    }
  }

  function onMouseUp() {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
  }

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}

function handleTimelineScroll() { }
// 触发片段选择与左右拖拽平移
function startDragClip(e: MouseEvent, clip: TimelineClip, track: TimelineTrack) {
  if (track.locked) return;
  emit('selectClip', clip.id);

  const startX = e.clientX;
  const initialStartMs = clip.start_ms;
  let hasMoved = false;

  function onMouseMove(moveEvent: MouseEvent) {
    const deltaX = moveEvent.clientX - startX;
    if (Math.abs(deltaX) > 2) {
      hasMoved = true;
    }
    const deltaMs = pxToMs(deltaX);
    // 片段起始时间不能小于 0
    let targetStartMs = Math.max(0, initialStartMs + deltaMs);

    // 简单磁吸吸附（若接近 0 则自动贴齐起始点）
    if (targetStartMs < 200) {
      targetStartMs = 0;
    }

    clip.start_ms = Math.round(targetStartMs);
  }

  function onMouseUp() {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);

    // 拖动完成后通知父组件更新时长与状态
    if (hasMoved) {
      // 触发时长重新计算
      props.timeline.duration_ms = Math.max(
        ...props.timeline.tracks.flatMap(t => t.clips.map(c => c.start_ms + c.duration_ms)),
        0
      );
    }
  }

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}
</script>

<style scoped>
.clip-card {
  /* ... 原有属性保持 ... */
  cursor: grab;
  /* 变为可抓取手势 */
}

.clip-card:active {
  cursor: grabbing;
  /* 抓取中手势 */
}

.timeline-container {
  display: flex;
  height: 260px;
  background-color: #0e0d13;
  overflow: hidden;
  position: relative;
  user-select: none;
}

/* 左侧轨道控制头部 */
.track-headers-column {
  width: 200px;
  background-color: #15131c;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  z-index: 20;
}

.ruler-corner-block {
  height: 32px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  font-size: 11px;
  color: #71717a;
  position: relative;
}

.quick-add-track-btn {
  background: rgba(255, 255, 255, 0.08);
  border: none;
  color: #cbd5e1;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  cursor: pointer;
}

.add-track-dropdown {
  position: absolute;
  top: 32px;
  left: 12px;
  background: #24222f;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  z-index: 50;
  width: 140px;
}

.dropdown-item {
  padding: 6px 12px;
  font-size: 11px;
  color: #cbd5e1;
  cursor: pointer;
}

.dropdown-item:hover {
  background: #6366f1;
  color: #fff;
}

.track-header-row {
  height: 48px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  align-items: center;
  padding: 0 10px;
  gap: 8px;
}

.track-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 2px 4px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  color: #a1a1aa;
}

.track-name {
  flex: 1;
  font-size: 11px;
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.track-controls {
  display: flex;
  gap: 4px;
}

.ctrl-icon-btn {
  background: transparent;
  border: none;
  color: #71717a;
  font-size: 11px;
  cursor: pointer;
  padding: 2px;
}

.ctrl-icon-btn:hover {
  color: #fff;
}

.ctrl-icon-btn.active {
  color: #f43f5e;
}

.del-track-btn:hover {
  color: #ef4444;
}

/* 右侧滚动泳道与标尺 */
.tracks-scroll-area {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  position: relative;
  background-color: #0b0a0f;
}

.timeline-viewport {
  position: relative;
  height: 100%;
}

.time-ruler-bar {
  height: 32px;
  background: #14121b;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  position: relative;
  cursor: pointer;
}

.ruler-tick-mark {
  position: absolute;
  top: 0;
  height: 100%;
  pointer-events: none;
}

.tick-line {
  position: absolute;
  bottom: 0;
  width: 1px;
  height: 8px;
  background: rgba(255, 255, 255, 0.15);
}

.tick-line.major {
  height: 14px;
  background: rgba(255, 255, 255, 0.35);
}

.tick-time-label {
  position: absolute;
  top: 4px;
  left: 4px;
  font-family: monospace;
  font-size: 9px;
  color: #71717a;
}

.marker-indicator {
  position: absolute;
  top: 6px;
  font-size: 12px;
  transform: translateX(-50%);
}

/* 垂直时间指示线 */
.playhead-line {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 1px;
  background-color: #f43f5e;
  z-index: 30;
  pointer-events: none;
}

.playhead-handle {
  position: absolute;
  top: 0;
  left: -8px;
  width: 16px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: ew-resize;
  pointer-events: auto;
}

.handle-diamond {
  width: 10px;
  height: 14px;
  background: #f43f5e;
  clip-path: polygon(0% 0%, 100% 0%, 100% 60%, 50% 100%, 0% 60%);
}

.track-lanes-wrapper {
  display: flex;
  flex-direction: column;
}

.track-lane-row {
  height: 48px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  position: relative;
  background: rgba(255, 255, 255, 0.01);
}

.track-lane-row.locked {
  opacity: 0.5;
  pointer-events: none;
}

/* 时间线片段卡片 */
.clip-card {
  position: absolute;
  top: 4px;
  height: 40px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  border: 1px solid rgba(255, 255, 255, 0.15);
  cursor: pointer;
  overflow: hidden;
  box-sizing: border-box;
}

.clip-card.selected {
  border-color: #ffffff;
  box-shadow: 0 0 0 1px #fff;
}

.clip-card.text {
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
}

.clip-card.video {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
}

.clip-card.audio {
  background: linear-gradient(135deg, #059669, #047857);
}

.clip-trim-handle {
  width: 8px;
  height: 100%;
  position: absolute;
  top: 0;
  cursor: ew-resize;
  z-index: 10;
}

.left-handle {
  left: 0;
}

.right-handle {
  right: 0;
}

.clip-trim-handle:hover {
  background: rgba(255, 255, 255, 0.4);
}

.clip-content-box {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.clip-tag-icon {
  font-size: 11px;
}

.clip-label {
  font-size: 11px;
  color: #fff;
  font-weight: 500;
}

.drop-to-new-track-zone {
  height: 38px;
  margin: 6px 12px;
  border: 1px dashed rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #71717a;
  font-size: 11px;
}
</style>