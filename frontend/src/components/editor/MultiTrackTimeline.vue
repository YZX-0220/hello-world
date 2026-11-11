<template>
  <div class="multi-track-timeline" @wheel="handleTimelineWheel">
    <!-- 左侧：轨道控制头列表 -->
    <aside class="track-headers-panel">
      <div class="headers-top-bar">
        <span class="tracks-count">轨道 ({{ timeline.tracks.length }})</span>
        <div class="add-track-dropdown">
          <button class="add-track-btn" title="添加新轨道">+</button>
          <div class="dropdown-menu">
            <div class="menu-item" @click="$emit('addTrack', 'video')">🎬 添加视频轨</div>
            <div class="menu-item" @click="$emit('addTrack', 'audio')">🎵 添加音频轨</div>
            <div class="menu-item" @click="$emit('addTrack', 'text')">🔤 添加文本轨</div>
          </div>
        </div>
      </div>

      <div class="track-headers-list" ref="headersListRef">
        <div 
          v-for="track in timeline.tracks" 
          :key="track.id" 
          class="track-header-item"
          :class="[`type-${track.type}`, { 'is-muted': track.muted, 'is-locked': track.locked }]"
        >
          <div class="track-type-pill">{{ track.type.toUpperCase() }}</div>
          <span class="track-name" :title="track.name">{{ track.name }}</span>

          <div class="track-actions">
            <button 
              v-if="track.type !== 'audio'"
              class="ctrl-icon-btn" 
              :class="{ off: track.hidden }"
              @click="track.hidden = !track.hidden"
              title="显示/隐藏轨道画面"
            >
              {{ track.hidden ? '🙈' : '👁' }}
            </button>
            <button 
              v-if="track.type !== 'text'"
              class="ctrl-icon-btn" 
              :class="{ off: track.muted }"
              @click="track.muted = !track.muted"
              title="静音/开启声音"
            >
              {{ track.muted ? '🔇' : '🔊' }}
            </button>
            <button 
              class="ctrl-icon-btn" 
              :class="{ active: track.locked }"
              @click="track.locked = !track.locked"
              title="锁定/解锁轨道"
            >
              {{ track.locked ? '🔒' : '🔓' }}
            </button>
            <button 
              class="ctrl-icon-btn del-btn" 
              @click="$emit('removeTrack', track.id)"
              title="删除轨道"
            >
              ×
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧：时间刻度标尺 + 多轨道滚动泳道区 -->
    <div class="timeline-tracks-scroll-area" ref="scrollAreaRef" @scroll="handleScrollSync">
      <div class="timeline-canvas-Stage" :style="{ width: `${stageWidthPx}px` }">
        <!-- 1. 顶部时间刻度尺 -->
        <div class="time-ruler" @mousedown="handleRulerMouseDown">
          <div 
            v-for="tick in rulerTicks" 
            :key="tick.timeMs" 
            class="ruler-tick"
            :class="{ major: tick.isMajor }"
            :style="{ left: `${timeToPx(tick.timeMs)}px` }"
          >
            <span v-if="tick.isMajor" class="tick-label">{{ tick.label }}</span>
          </div>

          <!-- 标记点旗帜 -->
          <div 
            v-for="marker in timeline.markers" 
            :key="marker.id" 
            class="timeline-marker-flag"
            :style="{ left: `${timeToPx(marker.timeMs || (marker as any).time_ms)}px` }"
            :title="marker.label"
            @click.stop="$emit('update:currentTimeMs', (marker as any).time_ms ?? 0)"
          >
            🚩
          </div>
        </div>

        <!-- 2. 轨道泳道容器 -->
        <div class="track-lanes-wrapper">
          <div 
            v-for="track in timeline.tracks" 
            :key="track.id" 
            class="track-lane"
            :class="[`lane-${track.type}`, { 'is-locked': track.locked }]"
            @dragover.prevent
            @drop="handleLaneDrop($event, track)"
            @mousedown="handleLaneBackgroundClick($event)"
          >
            <!-- 轨道内的各个剪辑片段 (剪映视觉风格) -->
            <div 
              v-for="clip in track.clips" 
              :key="clip.id" 
              class="timeline-clip-item"
              :class="[
                `clip-${clip.type}`,
                { selected: selectedClipId === clip.id }
              ]"
              :style="{
                left: `${timeToPx(clip.start_ms)}px`,
                width: `${Math.max(18, timeToPx(clip.duration_ms))}px`
              }"
              @mousedown.stop="handleClipMouseDown($event, track, clip)"
            >
              <!-- 左侧裁剪入点把手 -->
              <div 
                class="trim-handle left-handle" 
                title="拖拽裁剪起始入点"
                @mousedown.stop="handleTrimStart($event, track, clip, 'left')"
              ></div>

              <!-- 片段主体内容层 -->
              <div class="clip-inner-body">
                <!-- ================= A. 视频片段：顶部标题栏 + 中部连续缩略图帧 + 底部内嵌音频波形 ================= -->
                <template v-if="clip.type === 'video'">
                  <div class="clip-top-label-bar">
                    <span class="clip-title-text">{{ (clip as any).file_name || '视频片段' }}</span>
                    <span class="clip-dur-text">{{ formatClipTimecode(clip.duration_ms) }}</span>
                    <span v-if="(clip as any).playback_rate && (clip as any).playback_rate !== 1" class="speed-tag">
                      {{ (clip as any).playback_rate }}x
                    </span>
                  </div>

                  <!-- 连续抽帧缩略图胶片条 -->
                  <div class="video-filmstrip-row">
                    <template v-if="getClipThumbnails(clip).length > 0">
                      <div 
                        v-for="(thumbUrl, tIdx) in getVisibleFilmstripFrames(clip)" 
                        :key="tIdx" 
                        class="film-frame-cell"
                        :style="{ backgroundImage: `url(${thumbUrl})` }"
                      ></div>
                    </template>
                    <div v-else class="filmstrip-loading">
                      <span>正在生成帧预览...</span>
                    </div>
                  </div>

                  <!-- 视频底部附带的音频波形条（图片素材除外） -->
                  <div v-if="!(clip as any).is_image_source" class="video-attached-waveform">
                    <svg 
                      class="waveform-svg" 
                      preserveAspectRatio="none" 
                      :viewBox="`0 0 100 30`"
                    >
                      <path 
                        :d="buildWaveformSvgPath(clip, 100, 30, track.muted)" 
                        class="waveform-fill-path video-wave"
                      />
                    </svg>
                  </div>
                </template>

                <!-- ================= B. 音频片段：顶部文件名 + 下方动态高密度声波图 ================= -->
                <template v-else-if="clip.type === 'audio'">
                  <div class="clip-top-label-bar audio-bar">
                    <span class="clip-title-text">🎵 {{ (clip as any).file_name || '音频' }}</span>
                    <span class="clip-dur-text">{{ formatClipTimecode(clip.duration_ms) }}</span>
                  </div>

                  <div class="audio-waveform-area">
                    <!-- 音量基准辅助线 -->
                    <div 
                      class="volume-level-line" 
                      :style="{ bottom: `${Math.min(100, ((clip as any).volume ?? 1) * 80)}%` }"
                    ></div>
                    <svg 
                      class="waveform-svg" 
                      preserveAspectRatio="none" 
                      :viewBox="`0 0 120 40`"
                    >
                      <path 
                        :d="buildWaveformSvgPath(clip, 120, 40, track.muted)" 
                        class="waveform-fill-path audio-wave"
                      />
                    </svg>
                  </div>
                </template>

                <!-- ================= C. 文本字幕片段 ================= -->
                <template v-else-if="clip.type === 'text'">
                  <div class="text-clip-body">
                    <span class="text-badge">T</span>
                    <span class="clip-title-text">{{ (clip as any).text || '字幕文本' }}</span>
                  </div>
                </template>
              </div>

              <!-- 右侧裁剪出点把手 -->
              <div 
                class="trim-handle right-handle" 
                title="拖拽裁剪结束出点"
                @mousedown.stop="handleTrimStart($event, track, clip, 'right')"
              ></div>
            </div>
          </div>

          <!-- 底部快捷拖放新建轨道虚线区 -->
          <div 
            class="drop-new-track-zone"
            @dragover.prevent
            @drop="handleNewZoneDrop($event)"
          >
            <span>+ 拖入此处自动追加到对应轨道</span>
          </div>
        </div>

        <!-- 3. 全局红色播放指针 (Playhead) -->
        <div 
          class="playhead-line" 
          :style="{ left: `${timeToPx(currentTimeMs)}px` }"
          @mousedown.stop="handleRulerMouseDown"
        >
          <div class="playhead-cap"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue';
import type { TimelineDocument, TimelineTrack, TimelineClip, TrackType } from '../../types/clip';

const props = defineProps<{
  timeline: TimelineDocument;
  currentTimeMs: number;
  selectedClipId: string | null;
  zoomScale: number;
}>();

const emit = defineEmits<{
  (e: 'update:currentTimeMs', val: number): void;
  (e: 'selectClip', id: string | null): void;
  (e: 'addTrack', type: TrackType): void;
  (e: 'removeTrack', trackId: string): void;
  (e: 'appendClip', trackId: string, clipData: any): void;
}>();

const scrollAreaRef = ref<HTMLElement | null>(null);
const headersListRef = ref<HTMLElement | null>(null);

// 基础比例：1 秒 = 60px * zoomScale
const pxPerMs = computed(() => (60 * props.zoomScale) / 1000);

function timeToPx(ms: number): number {
  return Math.round(ms * pxPerMs.value);
}

function pxToTime(px: number): number {
  return Math.max(0, Math.round(px / pxPerMs.value));
}

// 画布总宽度（至少留出 60 秒余量）
const stageWidthPx = computed(() => {
  const minDurationMs = Math.max(props.timeline.duration_ms + 15000, 45000);
  return Math.max(1200, timeToPx(minDurationMs));
});

// 生成顶部时间标尺刻度
const rulerTicks = computed(() => {
  const totalMs = Math.max(props.timeline.duration_ms + 15000, 45000);
  // 根据缩放比例动态调整主刻度间隔
  let stepMs = 1000;
  if (props.zoomScale < 0.4) stepMs = 5000;
  else if (props.zoomScale < 0.8) stepMs = 2000;
  else if (props.zoomScale >= 2.2) stepMs = 500;

  const ticks: Array<{ timeMs: number; isMajor: boolean; label: string }> = [];
  for (let t = 0; t <= totalMs; t += stepMs) {
    const isMajor = t % (stepMs * 5) === 0 || t === 0;
    const totalSec = Math.floor(t / 1000);
    const m = Math.floor(totalSec / 60).toString().padStart(2, '0');
    const s = (totalSec % 60).toString().padStart(2, '0');
    ticks.push({
      timeMs: t,
      isMajor,
      label: `${m}:${s}`
    });
  }
  return ticks;
});

function formatClipTimecode(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(totalSec / 60).toString().padStart(2, '0');
  const s = (totalSec % 60).toString().padStart(2, '0');
  const f = Math.floor((ms % 1000) / 33.3).toString().padStart(2, '0');
  return `${m}:${s}:${f}`;
}

// ============================================================================
// 1. 视频连续帧缩略图提取引擎 (Offscreen Video -> Canvas DataURLs)
// ============================================================================
const thumbnailCache = reactive<Record<string, string[]>>({});
const extractingThumbSet = new Set<string>();

function getMediaKey(clip: any): string {
  return clip.source_url || clip.asset_id || clip.id;
}

async function extractVideoThumbnails(clip: any) {
  const url = clip.source_url;
  if (!url) return;
  const key = getMediaKey(clip);
  if (thumbnailCache[key] || extractingThumbSet.has(key)) return;

  // 如果是静态图片，直接用自身 URL 作为胶片帧
  if (clip.is_image_source) {
    thumbnailCache[key] = [url];
    return;
  }

  extractingThumbSet.add(key);
  try {
    const video = document.createElement('video');
    video.crossOrigin = 'anonymous';
    video.src = url;
    video.muted = true;
    video.preload = 'auto';

    await new Promise<void>((resolve, reject) => {
      video.onloadedmetadata = () => resolve();
      video.onerror = () => reject(new Error('视频元数据加载失败'));
      setTimeout(() => reject(new Error('视频缩略图加载超时')), 8000);
    });

    const durationSec = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : (clip.duration_ms || 5000) / 1000;
    // 每个视频均匀提取 16 张关键帧缩略图供时间轴任意缩放平铺
    const sampleCount = Math.min(20, Math.max(8, Math.ceil(durationSec / 1.5)));
    const canvas = document.createElement('canvas');
    const thumbW = 96;
    const thumbH = 54;
    canvas.width = thumbW;
    canvas.height = thumbH;
    const ctx = canvas.getContext('2d');
    const frames: string[] = [];

    if (ctx) {
      for (let i = 0; i < sampleCount; i++) {
        const targetSec = Math.min(durationSec - 0.05, Math.max(0, (i / sampleCount) * durationSec));
        video.currentTime = targetSec;
        await new Promise<void>((res) => {
          const onSeeked = () => {
            video.removeEventListener('seeked', onSeeked);
            res();
          };
          video.addEventListener('seeked', onSeeked);
          setTimeout(res, 350);
        });
        ctx.drawImage(video, 0, 0, thumbW, thumbH);
        frames.push(canvas.toDataURL('image/jpeg', 0.6));
      }
    }

    if (frames.length > 0) {
      thumbnailCache[key] = frames;
    }
    video.src = '';
  } catch (err) {
    console.warn('提取视频轨道缩略图失败:', err);
  } finally {
    extractingThumbSet.delete(key);
  }
}

function getClipThumbnails(clip: any): string[] {
  const key = getMediaKey(clip);
  return thumbnailCache[key] || [];
}

// 根据当前片段在时间轴上的像素宽度，计算应该平铺展示多少格缩略图，并映射入点/出点区间
function getVisibleFilmstripFrames(clip: any): string[] {
  const allFrames = getClipThumbnails(clip);
  if (allFrames.length === 0) return [];

  const clipWidthPx = Math.max(36, timeToPx(clip.duration_ms));
  const cellWidthPx = 48; // 每格缩略图宽度约 48px
  const cellsCount = Math.max(1, Math.min(60, Math.ceil(clipWidthPx / cellWidthPx)));

  const result: string[] = [];
  for (let i = 0; i < cellsCount; i++) {
    const ratio = cellsCount === 1 ? 0 : i / (cellsCount - 1);
    const frameIdx = Math.min(allFrames.length - 1, Math.floor(ratio * allFrames.length));
    result.push(allFrames[frameIdx]);
  }
  return result;
}

// ============================================================================
// 2. 真实音频波形解码引擎 (Web Audio API -> Normalized Peaks + 动态音量联动)
// ============================================================================
const waveformCache = reactive<Record<string, number[]>>({});
const extractingWaveSet = new Set<string>();
let sharedAudioCtx: AudioContext | null = null;

async function extractAudioWaveform(clip: any) {
  const url = clip.source_url;
  if (!url || clip.is_image_source) return;
  const key = getMediaKey(clip);
  if (waveformCache[key] || extractingWaveSet.has(key)) return;

  extractingWaveSet.add(key);
  try {
    const response = await fetch(url);
    const arrayBuffer = await response.arrayBuffer();

    if (!sharedAudioCtx) {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      sharedAudioCtx = new AudioContextClass();
    }

    const audioBuffer = await sharedAudioCtx.decodeAudioData(arrayBuffer);
    const rawData = audioBuffer.getChannelData(0);
    const samples = 80; // 采样 80 个波峰节点
    const blockSize = Math.max(1, Math.floor(rawData.length / samples));
    const peaks: number[] = [];

    let maxPeak = 0.01;
    for (let i = 0; i < samples; i++) {
      const start = i * blockSize;
      let sum = 0;
      for (let j = 0; j < blockSize; j++) {
        const val = Math.abs(rawData[start + j] || 0);
        if (val > sum) sum = val;
      }
      peaks.push(sum);
      if (sum > maxPeak) maxPeak = sum;
    }

    // 归一化到 0.08 ~ 1.0 之间
    waveformCache[key] = peaks.map(p => Math.max(0.08, Number((p / maxPeak).toFixed(3))));
  } catch (err) {
    // 兜底：若跨域或无音轨解码失败，根据文件名生成确定性的伪声波特征包络
    const fallback: number[] = [];
    const seedStr = clip.file_name || clip.id || 'wave';
    for (let i = 0; i < 80; i++) {
      const code = seedStr.charCodeAt(i % seedStr.length);
      const val = 0.2 + 0.65 * Math.abs(Math.sin(i * 0.45 + code));
      fallback.push(Number(val.toFixed(2)));
    }
    waveformCache[key] = fallback;
  } finally {
    extractingWaveSet.delete(key);
  }
}

// 构建随音量 (volume)、静音 (muted)、淡入 (fade_in_ms)、淡出 (fade_out_ms) 实时变化的 SVG 声波路径
function buildWaveformSvgPath(clip: any, width: number, height: number, isTrackMuted: boolean): string {
  const key = getMediaKey(clip);
  const peaks = waveformCache[key];
  if (!peaks || peaks.length === 0) {
    return `M 0 ${height} L ${width} ${height} Z`;
  }

  // 核心联动：获取片段当前音量（0 ~ 2.0），若轨道静音或音量为 0，则波形压平
  const rawVolume = isTrackMuted ? 0 : (clip.volume ?? 1.0);
  const durationMs = Math.max(1, clip.duration_ms || 3000);
  const fadeInMs = clip.fade_in_ms || 0;
  const fadeOutMs = clip.fade_out_ms || 0;

  const points: string[] = [`M 0 ${height}`];
  const count = peaks.length;

  for (let i = 0; i < count; i++) {
    const progress = i / (count - 1);
    const curTimeInClip = progress * durationMs;

    // 计算当前点的淡入淡出衰减系数
    let fadeFactor = 1.0;
    if (fadeInMs > 0 && curTimeInClip < fadeInMs) {
      fadeFactor = curTimeInClip / fadeInMs;
    }
    const remainMs = durationMs - curTimeInClip;
    if (fadeOutMs > 0 && remainMs < fadeOutMs) {
      fadeFactor = Math.min(fadeFactor, remainMs / fadeOutMs);
    }

    // 最终波峰振幅 = 原始声波峰值 * 音量增益 * 淡入淡出系数
    const effectiveAmp = Math.min(1.0, peaks[i] * rawVolume * Math.max(0, fadeFactor));
    const x = (progress * width).toFixed(1);
    const y = (height - effectiveAmp * (height * 0.88)).toFixed(1);
    points.push(`L ${x} ${y}`);
  }

  points.push(`L ${width} ${height} Z`);
  return points.join(' ');
}

// 监听轨道内所有片段变化，自动触发缩略图抽帧与音频波形提取
watch(
  () => props.timeline.tracks,
  (tracks) => {
    for (const track of tracks) {
      for (const clip of track.clips) {
        if (clip.type === 'video') {
          void extractVideoThumbnails(clip);
          if (!(clip as any).is_image_source) {
            void extractAudioWaveform(clip);
          }
        } else if (clip.type === 'audio') {
          void extractAudioWaveform(clip);
        }
      }
    }
  },
  { deep: true, immediate: true }
);

// ============================================================================
// 3. 时间轴交互：指针拖拽、片段左右平移、首尾入出点裁剪、素材拖放
// ============================================================================
function handleScrollSync() {
  if (scrollAreaRef.value && headersListRef.value) {
    headersListRef.value.scrollTop = scrollAreaRef.value.scrollTop;
  }
}

function handleTimelineWheel(e: WheelEvent) {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
  }
}

// 点击或拖拽时间标尺移动红色指针
function handleRulerMouseDown(e: MouseEvent) {
  if (!scrollAreaRef.value) return;
  const updateTimeFromMouse = (clientX: number) => {
    if (!scrollAreaRef.value) return;
    const rect = scrollAreaRef.value.getBoundingClientRect();
    const offsetX = clientX - rect.left + scrollAreaRef.value.scrollLeft;
    emit('update:currentTimeMs', pxToTime(offsetX));
  };

  updateTimeFromMouse(e.clientX);

  const onMove = (moveEvt: MouseEvent) => updateTimeFromMouse(moveEvt.clientX);
  const onUp = () => {
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
  };
  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
}

function handleLaneBackgroundClick(e: MouseEvent) {
  emit('selectClip', null);
  handleRulerMouseDown(e);
}

// 选中并在轨道上左右拖拽移动片段位置
function handleClipMouseDown(e: MouseEvent, track: TimelineTrack, clip: TimelineClip) {
  emit('selectClip', clip.id);
  if (track.locked) return;

  const startX = e.clientX;
  const initialStartMs = clip.start_ms;

  const onMove = (moveEvt: MouseEvent) => {
    const deltaPx = moveEvt.clientX - startX;
    const deltaMs = Math.round(deltaPx / pxPerMs.value);
    clip.start_ms = Math.max(0, initialStartMs + deltaMs);
  };

  const onUp = () => {
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
  };

  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
}

// 左右边缘拖拽裁剪片段时长与入出点
function handleTrimStart(e: MouseEvent, track: TimelineTrack, clip: TimelineClip, side: 'left' | 'right') {
  emit('selectClip', clip.id);
  if (track.locked) return;

  const startX = e.clientX;
  const initialStartMs = clip.start_ms;
  const initialDurationMs = clip.duration_ms;
  const initialInPointMs = clip.in_point_ms || 0;

  const onMove = (moveEvt: MouseEvent) => {
    const deltaPx = moveEvt.clientX - startX;
    const deltaMs = Math.round(deltaPx / pxPerMs.value);

    if (side === 'left') {
      const maxTrim = initialDurationMs - 300;
      const clampedDelta = Math.max(-initialStartMs, Math.min(maxTrim, deltaMs));
      clip.start_ms = initialStartMs + clampedDelta;
      clip.duration_ms = initialDurationMs - clampedDelta;
      clip.in_point_ms = Math.max(0, initialInPointMs + clampedDelta);
    } else {
      clip.duration_ms = Math.max(300, initialDurationMs + deltaMs);
      clip.out_point_ms = (clip.in_point_ms || 0) + clip.duration_ms;
    }
  };

  const onUp = () => {
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
  };

  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
}

// 从左侧素材库拖入具体轨道
function handleLaneDrop(e: DragEvent, track: TimelineTrack) {
  if (track.locked || !e.dataTransfer) return;
  const raw = e.dataTransfer.getData('application/json');
  if (!raw) return;

  try {
    const data = JSON.parse(raw);
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const dropPx = e.clientX - rect.left;
    const dropTimeMs = pxToTime(dropPx);

    if (data.sourceType === 'text' && track.type === 'text') {
      emit('appendClip', track.id, {
        type: 'text',
        text: data.text || '字幕内容',
        font_size: data.fontSize || 26,
        color: data.color || '#FFFFFF',
        align: 'center',
        opacity: 1.0,
        start_ms: dropTimeMs,
        duration_ms: 3000
      });
    } else if (data.sourceType === 'asset') {
      const compatibleType: TrackType = data.kind === 'audio' ? 'audio' : 'video';
      if (track.type !== compatibleType) return;

      emit('appendClip', track.id, {
        type: compatibleType,
        asset_id: data.assetId,
        sha256: data.sha256,
        file_name: data.fileName,
        source_url: data.url,
        start_ms: dropTimeMs,
        duration_ms: data.durationMs || 5000,
        is_image_source: data.isImageSource,
        playback_rate: 1.0,
        volume: 1.0,
        opacity: 1.0,
        scale: 1.0,
        position_x: 0,
        position_y: 0,
        fade_in_ms: 0,
        fade_out_ms: 0
      });
    }
  } catch (err) {
    console.warn('解析拖放素材失败:', err);
  }
}

// 拖入底部虚线区自动匹配轨道追加
function handleNewZoneDrop(e: DragEvent) {
  if (!e.dataTransfer) return;
  const raw = e.dataTransfer.getData('application/json');
  if (!raw) return;

  try {
    const data = JSON.parse(raw);
    const targetType: TrackType = data.sourceType === 'text' ? 'text' : data.kind === 'audio' ? 'audio' : 'video';
    const targetTrack = props.timeline.tracks.find(t => t.type === targetType && !t.locked);
    if (!targetTrack) return;

    const lastEnd = targetTrack.clips.reduce((max, c) => Math.max(max, c.start_ms + c.duration_ms), 0);

    if (targetType === 'text') {
      emit('appendClip', targetTrack.id, {
        type: 'text',
        text: data.text || '字幕内容',
        font_size: data.fontSize || 26,
        color: data.color || '#FFFFFF',
        align: 'center',
        opacity: 1.0,
        start_ms: lastEnd,
        duration_ms: 3000
      });
    } else {
      emit('appendClip', targetTrack.id, {
        type: targetType,
        asset_id: data.assetId,
        sha256: data.sha256,
        file_name: data.fileName,
        source_url: data.url,
        start_ms: lastEnd,
        duration_ms: data.durationMs || 5000,
        is_image_source: data.isImageSource,
        playback_rate: 1.0,
        volume: 1.0,
        opacity: 1.0,
        scale: 1.0,
        position_x: 0,
        position_y: 0,
        fade_in_ms: 0,
        fade_out_ms: 0
      });
    }
  } catch (err) {
    console.warn('自动追加拖放失败:', err);
  }
}
</script>

<style scoped>
.multi-track-timeline {
  display: flex;
  width: 100%;
  height: 100%;
  background-color: #111016;
  user-select: none;
  overflow: hidden;
}

/* 左侧轨道头控制栏 */
.track-headers-panel {
  width: 180px;
  flex-shrink: 0;
  background-color: #16151d;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  z-index: 20;
}

.headers-top-bar {
  height: 28px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 11px;
  color: #71717a;
}

.add-track-dropdown {
  position: relative;
}

.add-track-btn {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #e4e4e7;
  cursor: pointer;
  line-height: 1;
}

.add-track-dropdown:hover .dropdown-menu {
  display: flex;
}

.dropdown-menu {
  display: none;
  position: absolute;
  top: 22px;
  left: 0;
  width: 120px;
  background: #1f1d29;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  flex-direction: column;
  padding: 4px;
  z-index: 100;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.6);
}

.menu-item {
  padding: 6px 8px;
  font-size: 11px;
  color: #cbd5e1;
  border-radius: 4px;
  cursor: pointer;
}

.menu-item:hover {
  background: #6366f1;
  color: #fff;
}

.track-headers-list {
  flex: 1;
  overflow: hidden;
  padding-top: 6px;
}

.track-header-item {
  height: 64px;
  margin-bottom: 6px;
  padding: 0 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.02);
  border-left: 3px solid #6366f1;
}

.track-header-item.type-video { border-left-color: #14b8a6; height: 74px; }
.track-header-item.type-audio { border-left-color: #3b82f6; height: 56px; }
.track-header-item.type-text { border-left-color: #a855f7; height: 42px; }

.track-type-pill {
  font-size: 9px;
  padding: 2px 4px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.07);
  color: #a1a1aa;
  font-family: monospace;
}

.track-name {
  flex: 1;
  font-size: 11px;
  color: #d4d4d8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.track-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.ctrl-icon-btn {
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 11px;
  padding: 2px 3px;
  cursor: pointer;
  border-radius: 3px;
}

.ctrl-icon-btn:hover { background: rgba(255, 255, 255, 0.1); color: #fff; }
.ctrl-icon-btn.off { opacity: 0.35; }
.ctrl-icon-btn.del-btn:hover { color: #ef4444; }

/* 右侧滚动泳道区 */
.timeline-tracks-scroll-area {
  flex: 1;
  overflow: auto;
  position: relative;
}

.timeline-canvas-Stage {
  position: relative;
  min-height: 100%;
}

/* 顶部时间标尺 */
.time-ruler {
  position: sticky;
  top: 0;
  height: 28px;
  background-color: #14131b;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  z-index: 15;
  cursor: pointer;
}

.ruler-tick {
  position: absolute;
  bottom: 0;
  width: 1px;
  height: 5px;
  background: rgba(255, 255, 255, 0.18);
}

.ruler-tick.major {
  height: 11px;
  background: rgba(255, 255, 255, 0.45);
}

.tick-label {
  position: absolute;
  top: -14px;
  left: 3px;
  font-size: 10px;
  font-family: monospace;
  color: #71717a;
}

.timeline-marker-flag {
  position: absolute;
  top: 4px;
  transform: translateX(-50%);
  font-size: 12px;
  cursor: pointer;
  z-index: 5;
}

/* 轨道泳道列表 */
.track-lanes-wrapper {
  padding-top: 6px;
  position: relative;
}

.track-lane {
  position: relative;
  height: 64px;
  margin-bottom: 6px;
  background-color: rgba(255, 255, 255, 0.018);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.track-lane.lane-video { height: 74px; }
.track-lane.lane-audio { height: 56px; }
.track-lane.lane-text { height: 42px; }

/* ================= 剪映风格片段容器 ================= */
.timeline-clip-item {
  position: absolute;
  top: 2px;
  bottom: 2px;
  border-radius: 6px;
  overflow: hidden;
  cursor: grab;
  display: flex;
  align-items: stretch;
  border: 1.5px solid rgba(255, 255, 255, 0.18);
  box-sizing: border-box;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.timeline-clip-item:active {
  cursor: grabbing;
}

.timeline-clip-item.selected {
  border-color: #ffffff;
  box-shadow: 0 0 0 1.5px #ffffff, 0 4px 14px rgba(0, 0, 0, 0.6);
  z-index: 10;
}

/* 视频片段底色（剪映青绿暗底） */
.timeline-clip-item.clip-video {
  background-color: #0d3b3e;
  border-color: #14b8a6;
}

/* 音频片段底色（剪映深海蓝底） */
.timeline-clip-item.clip-audio {
  background-color: #0c2b4e;
  border-color: #0ea5e9;
}

/* 文本片段底色 */
.timeline-clip-item.clip-text {
  background: linear-gradient(90deg, #6d28d9, #7c3aed);
  border-color: #c084fc;
}

.clip-inner-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  pointer-events: none;
}

/* 片段顶部文件名与时长小条 */
.clip-top-label-bar {
  height: 15px;
  padding: 0 6px;
  background: rgba(9, 45, 48, 0.88);
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: #e2e8f0;
  z-index: 3;
  flex-shrink: 0;
}

.clip-top-label-bar.audio-bar {
  background: rgba(8, 35, 68, 0.85);
}

.clip-title-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}

.clip-dur-text {
  color: rgba(255, 255, 255, 0.65);
  font-family: monospace;
  font-size: 9px;
}

.speed-tag {
  background: #f59e0b;
  color: #000;
  font-weight: 700;
  padding: 0 3px;
  border-radius: 2px;
  font-size: 9px;
}

/* 视频连续缩略图帧胶片条 */
.video-filmstrip-row {
  flex: 1;
  display: flex;
  align-items: stretch;
  overflow: hidden;
  background: #000;
}

.film-frame-cell {
  flex: 1;
  min-width: 36px;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  border-right: 1px solid rgba(0, 0, 0, 0.35);
}

.filmstrip-loading {
  flex: 1;
  display: flex;
  align-items: center;
  padding-left: 10px;
  font-size: 10px;
  color: #94a3b8;
}

/* 视频底部内嵌声波条 */
.video-attached-waveform {
  height: 14px;
  background: #082f32;
  border-top: 1px solid rgba(20, 184, 166, 0.3);
  flex-shrink: 0;
  position: relative;
}

/* 独立音频波形区 */
.audio-waveform-area {
  flex: 1;
  position: relative;
  background: rgba(7, 29, 54, 0.9);
  overflow: hidden;
}

.volume-level-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.35);
  z-index: 2;
}

.waveform-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.waveform-fill-path.video-wave {
  fill: #2dd4bf;
  opacity: 0.85;
}

.waveform-fill-path.audio-wave {
  fill: #38bdf8;
  opacity: 0.9;
}

/* 文本轨样式 */
.text-clip-body {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  font-size: 11px;
  color: #fff;
}

.text-badge {
  background: rgba(0, 0, 0, 0.3);
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: bold;
  font-size: 10px;
}

/* 左右修剪把手 */
.trim-handle {
  width: 7px;
  background: rgba(255, 255, 255, 0.15);
  cursor: ew-resize;
  z-index: 5;
  transition: background-color 0.15s;
}

.timeline-clip-item.selected .trim-handle,
.trim-handle:hover {
  background: #ffffff;
}

.drop-new-track-zone {
  height: 36px;
  margin: 6px 12px;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #52525b;
}

/* 红色播放时间指针 */
.playhead-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1.5px;
  background-color: #ffffff;
  z-index: 30;
  pointer-events: auto;
  cursor: ew-resize;
}

.playhead-cap {
  position: absolute;
  top: 0;
  left: -5px;
  width: 11px;
  height: 12px;
  background: #ffffff;
  clip-path: polygon(0 0, 100% 0, 100% 60%, 50% 100%, 0 60%);
}
</style>