import { ref, shallowRef, watch, onUnmounted, type Ref } from 'vue';
import type { TimelineDocument, TimelineClip, VideoClip, TextClip, AudioClip } from '../types/clip';

export function useClipEngine(
  timeline: Ref<TimelineDocument>,
  currentTimeMs: Ref<number>,
  isPlaying: Ref<boolean>,
  resolveMediaUrl: (asset: { sha256: string; file_name: string; url: string }) => Promise<string>
) {
  const canvasRef = shallowRef<HTMLCanvasElement | null>(null);
  const isExporting = ref(false);
  const exportProgress = ref(0);
  let animationFrameId: number | null = null;
  let lastTimestamp = 0;
  let isSeekingInternally = false;

  // 缓存多媒体元素：key 为 clip.id
  const mediaElementCache = new Map<string, HTMLVideoElement | HTMLImageElement | HTMLAudioElement>();
  const loadingClips = new Set<string>();

  // 1. 初始化绑定 Canvas
  function setCanvasElement(el: HTMLCanvasElement | null) {
    canvasRef.value = el;
    if (el) {
      el.width = timeline.value.width || 1920;
      el.height = timeline.value.height || 1080;
      renderCurrentFrame();
    }
  }

  // 2. 预加载媒体资源（支持 Video / Image / 独立 Audio）
  async function ensureClipMedia(clip: TimelineClip): Promise<HTMLVideoElement | HTMLImageElement | HTMLAudioElement | null> {
    if (clip.type === 'text') return null;

    const cacheKey = clip.id;
    if (mediaElementCache.has(cacheKey)) {
      return mediaElementCache.get(cacheKey)!;
    }

    if (loadingClips.has(cacheKey)) return null;
    loadingClips.add(cacheKey);

    try {
      let realUrl = clip.source_url || '';
      if (!realUrl) {
        realUrl = await resolveMediaUrl({
          sha256: (clip as any).sha256 || '',
          file_name: (clip as any).file_name || 'media',
          url: ''
        });
      }

      if (!realUrl) return null;

      if (clip.type === 'video') {
        const videoClip = clip as VideoClip;
        if (videoClip.is_image_source) {
          const img = new Image();
          img.crossOrigin = 'anonymous';
          await new Promise((res) => {
            img.onload = res;
            img.onerror = res;
            img.src = realUrl;
          });
          mediaElementCache.set(cacheKey, img);
          renderCurrentFrame();
          return img;
        } else {
          const video = document.createElement('video');
          video.crossOrigin = 'anonymous';
          video.src = realUrl;
          video.preload = 'auto';
          video.muted = false;
          video.playsInline = true;

          await new Promise((res) => {
            video.onloadeddata = res;
            video.onerror = res;
          });

          mediaElementCache.set(cacheKey, video);
          renderCurrentFrame();
          return video;
        }
      } else if (clip.type === 'audio') {
        const audio = document.createElement('audio');
        audio.crossOrigin = 'anonymous';
        audio.src = realUrl;
        audio.preload = 'auto';

        await new Promise((res) => {
          audio.onloadeddata = res;
          audio.onerror = res;
        });

        mediaElementCache.set(cacheKey, audio);
        return audio;
      }
    } finally {
      loadingClips.delete(cacheKey);
    }
    return null;
  }

  // 辅助：计算当前时刻的真实音量（含淡入淡出包络）
  function computeEffectiveVolume(
    baseVolume: number,
    elapsedInClipMs: number,
    clipDurationMs: number,
    fadeInMs: number = 0,
    fadeOutMs: number = 0
  ): number {
    let factor = 1.0;
    if (fadeInMs > 0 && elapsedInClipMs < fadeInMs) {
      factor = Math.max(0, elapsedInClipMs / fadeInMs);
    }
    const remainMs = clipDurationMs - elapsedInClipMs;
    if (fadeOutMs > 0 && remainMs < fadeOutMs) {
      factor = Math.min(factor, Math.max(0, remainMs / fadeOutMs));
    }
    return Math.max(0, Math.min(1.0, baseVolume * factor));
  }

  // 3. 核心实时多图层与多音轨合成渲染
  function renderCurrentFrame() {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const targetW = canvas.width;
    const targetH = canvas.height;
    const curTime = currentTimeMs.value;

    // 透明清屏
    ctx.clearRect(0, 0, targetW, targetH);

    // 逆序遍历轨道：保证上方轨道盖在下方轨道之上
    const tracksToRender = [...timeline.value.tracks].reverse();

    for (const track of tracksToRender) {
      if (track.hidden) continue;

      for (const clip of track.clips) {
        const clipStart = clip.start_ms;
        const clipEnd = clip.start_ms + clip.duration_ms;

        // 不在当前播放指针范围内：确保停止发声
        if (curTime < clipStart || curTime > clipEnd) {
          const cachedEl = mediaElementCache.get(clip.id);
          if ((cachedEl instanceof HTMLVideoElement || cachedEl instanceof HTMLAudioElement) && !cachedEl.paused) {
            cachedEl.pause();
          }
          continue;
        }

        const elapsedMs = curTime - clipStart;
        ctx.save();

        // A. 文本片段实时渲染（支持字号、颜色、对齐、不透明度、位置偏移实时响应）
        if (clip.type === 'text') {
          const textClip = clip as TextClip;
          ctx.globalAlpha = textClip.opacity ?? 1.0;
          const fontSize = (textClip.font_size || 26) * 2;
          ctx.font = `bold ${fontSize}px sans-serif`;
          ctx.textAlign = textClip.align || 'center';
          ctx.textBaseline = 'middle';

          const baseTextX = textClip.align === 'left' ? 120 : textClip.align === 'right' ? targetW - 120 : targetW / 2;
          const textX = baseTextX + ((textClip as any).position_x ?? 0);
          const textY = targetH - 180 + ((textClip as any).position_y ?? 0);

          const lines = (textClip.text || '').split('\n');
          const lineHeight = fontSize * 1.25;

          lines.forEach((line, idx) => {
            const lineY = textY + (idx - (lines.length - 1) / 2) * lineHeight;
            if (textClip.background_color) {
              ctx.fillStyle = textClip.background_color;
              const metrics = ctx.measureText(line);
              const padX = 20;
              const padY = 10;
              const bgX =
                textClip.align === 'left'
                  ? textX - padX
                  : textClip.align === 'right'
                  ? textX - metrics.width - padX
                  : textX - metrics.width / 2 - padX;
              ctx.fillRect(bgX, lineY - fontSize / 2 - padY, metrics.width + padX * 2, fontSize + padY * 2);
            }

            // 描边增强可读性
            ctx.lineWidth = Math.max(2, Math.round(fontSize / 12));
            ctx.strokeStyle = 'rgba(0, 0, 0, 0.75)';
            ctx.strokeText(line, textX, lineY);

            ctx.fillStyle = textClip.color || '#FFFFFF';
            ctx.fillText(line, textX, lineY);
          });
        }
        // B. 视频/图片片段实时渲染（支持缩放、XY平移、倍速、音量、不透明度）
        else if (clip.type === 'video') {
          const videoClip = clip as VideoClip;
          ctx.globalAlpha = videoClip.opacity ?? 1.0;

          const element = mediaElementCache.get(clip.id);
          if (!element) {
            void ensureClipMedia(clip);
          } else {
            const elemW = (element instanceof HTMLVideoElement ? element.videoWidth : (element as HTMLImageElement).naturalWidth) || 1920;
            const elemH = (element instanceof HTMLVideoElement ? element.videoHeight : (element as HTMLImageElement).naturalHeight) || 1080;

            if (element instanceof HTMLVideoElement) {
              const rate = videoClip.playback_rate || 1.0;
              if (element.playbackRate !== rate) {
                element.playbackRate = rate;
              }
              element.muted = track.muted || (videoClip.volume ?? 1.0) <= 0;
              element.volume = computeEffectiveVolume(
                videoClip.volume ?? 1.0,
                elapsedMs,
                videoClip.duration_ms,
                (videoClip as any).fade_in_ms || 0,
                (videoClip as any).fade_out_ms || 0
              );

              if (!isPlaying.value) {
                const targetSec = ((elapsedMs * rate) + videoClip.in_point_ms) / 1000;
                if (Math.abs(element.currentTime - targetSec) > 0.04) {
                  element.currentTime = targetSec;
                }
              }
            }

            const scaleFactor = Math.min(targetW / elemW, targetH / elemH);
            const fitW = elemW * scaleFactor;
            const fitH = elemH * scaleFactor;

            const userScale = videoClip.scale ?? 1.0;
            const finalW = fitW * userScale;
            const finalH = fitH * userScale;

            const posX = videoClip.position_x ?? 0;
            const posY = videoClip.position_y ?? 0;

            const drawX = (targetW - finalW) / 2 + posX;
            const drawY = (targetH - finalH) / 2 + posY;

            if (element instanceof HTMLImageElement) {
              ctx.drawImage(element, drawX, drawY, finalW, finalH);
            } else if (element instanceof HTMLVideoElement && element.readyState >= 1) {
              ctx.drawImage(element, drawX, drawY, finalW, finalH);
            }
          }
        }
        // C. 独立音频片段实时控制（音量增益 + 淡入淡出）
        else if (clip.type === 'audio') {
          const audioClip = clip as AudioClip;
          const element = mediaElementCache.get(clip.id);
          if (!element) {
            void ensureClipMedia(clip);
          } else if (element instanceof HTMLAudioElement) {
            element.muted = track.muted || (audioClip.volume ?? 1.0) <= 0;
            element.volume = computeEffectiveVolume(
              audioClip.volume ?? 1.0,
              elapsedMs,
              audioClip.duration_ms,
              audioClip.fade_in_ms || 0,
              audioClip.fade_out_ms || 0
            );

            if (!isPlaying.value) {
              const targetSec = (elapsedMs + audioClip.in_point_ms) / 1000;
              if (Math.abs(element.currentTime - targetSec) > 0.05) {
                element.currentTime = targetSec;
              }
            }
          }
        }

        ctx.restore();
      }
    }
  }

  // 4. 播放时钟调度循环
  function playTick(timestamp: number) {
    if (!isPlaying.value) return;

    if (!lastTimestamp) lastTimestamp = timestamp;
    const deltaMs = timestamp - lastTimestamp;
    lastTimestamp = timestamp;

    const nextTime = currentTimeMs.value + deltaMs;

    if (nextTime >= timeline.value.duration_ms) {
      if (timeline.value.duration_ms > 0) {
        pausePlayback();
        currentTimeMs.value = 0;
        seekAllMediaTo(0);
        renderCurrentFrame();
      }
      return;
    }

    isSeekingInternally = true;
    currentTimeMs.value = nextTime;
    isSeekingInternally = false;

    syncPlayAllActiveClips();
    renderCurrentFrame();
    animationFrameId = requestAnimationFrame(playTick);
  }

  // 同步激活所有处于当前时间片内的音视频
  function syncPlayAllActiveClips() {
    const cur = currentTimeMs.value;
    timeline.value.tracks.forEach(track => {
      track.clips.forEach(clip => {
        if (clip.type === 'video' || clip.type === 'audio') {
          const el = mediaElementCache.get(clip.id);
          if (el instanceof HTMLVideoElement || el instanceof HTMLAudioElement) {
            const inRange = !track.hidden && cur >= clip.start_ms && cur < clip.start_ms + clip.duration_ms;
            if (inRange) {
              const rate = (clip as VideoClip).playback_rate || 1.0;
              if (el.playbackRate !== rate) el.playbackRate = rate;

              const targetSec = (((cur - clip.start_ms) * rate) + clip.in_point_ms) / 1000;
              if (Math.abs(el.currentTime - targetSec) > 0.25) {
                el.currentTime = targetSec;
              }
              if (el.paused) {
                el.play().catch(() => {});
              }
            } else {
              if (!el.paused) el.pause();
            }
          }
        }
      });
    });
  }

  function seekAllMediaTo(targetMs: number) {
    timeline.value.tracks.forEach(track => {
      track.clips.forEach(clip => {
        if (clip.type === 'video' || clip.type === 'audio') {
          const el = mediaElementCache.get(clip.id);
          if (el instanceof HTMLVideoElement || el instanceof HTMLAudioElement) {
            const inRange = targetMs >= clip.start_ms && targetMs <= clip.start_ms + clip.duration_ms;
            if (inRange) {
              const rate = (clip as VideoClip).playback_rate || 1.0;
              el.currentTime = (((targetMs - clip.start_ms) * rate) + clip.in_point_ms) / 1000;
            } else {
              if (!el.paused) el.pause();
            }
          }
        }
      });
    });
  }

  function startPlayback() {
    isPlaying.value = true;
    lastTimestamp = performance.now();
    syncPlayAllActiveClips();
    animationFrameId = requestAnimationFrame(playTick);
  }

  function pausePlayback() {
    isPlaying.value = false;
    lastTimestamp = 0;
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }

    mediaElementCache.forEach((el) => {
      if ((el instanceof HTMLVideoElement || el instanceof HTMLAudioElement) && !el.paused) {
        el.pause();
      }
    });
    renderCurrentFrame();
  }

  function togglePlay() {
    if (isPlaying.value) pausePlayback();
    else startPlayback();
  }

  function seekTo(targetMs: number) {
    currentTimeMs.value = Math.max(0, Math.min(targetMs, timeline.value.duration_ms));
    seekAllMediaTo(currentTimeMs.value);
    renderCurrentFrame();
  }

  function stepFrame(frames: number) {
    const frameDurationMs = 1000 / (timeline.value.fps || 30);
    seekTo(currentTimeMs.value + frames * frameDurationMs);
  }

  // 5. 纯前端打包导出
  async function exportMp4(): Promise<Blob> {
    isExporting.value = true;
    exportProgress.value = 0;
    pausePlayback();

    const canvas = canvasRef.value;
    if (!canvas) throw new Error('渲染画布未就绪');

    const stream = canvas.captureStream(timeline.value.fps || 30);
    const mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'video/webm;codecs=vp9',
      videoBitsPerSecond: 5000000
    });

    const chunks: Blob[] = [];
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    return new Promise((resolve, reject) => {
      mediaRecorder.onstop = () => {
        const finalBlob = new Blob(chunks, { type: 'video/mp4' });
        isExporting.value = false;
        resolve(finalBlob);
      };
      mediaRecorder.onerror = (e) => {
        isExporting.value = false;
        reject(e);
      };

      mediaRecorder.start();

      const totalDuration = timeline.value.duration_ms || 3000;
      const stepMs = 1000 / (timeline.value.fps || 30);
      let simulatedTime = 0;

      const recordInterval = setInterval(() => {
        simulatedTime += stepMs;
        currentTimeMs.value = simulatedTime;
        seekAllMediaTo(simulatedTime);
        renderCurrentFrame();
        exportProgress.value = Math.min(100, Math.floor((simulatedTime / totalDuration) * 100));

        if (simulatedTime >= totalDuration) {
          clearInterval(recordInterval);
          mediaRecorder.stop();
        }
      }, stepMs);
    });
  }

  // 监听画幅宽高切换
  watch(
    () => [timeline.value.width, timeline.value.height],
    ([w, h]) => {
      if (canvasRef.value) {
        canvasRef.value.width = w || 1920;
        canvasRef.value.height = h || 1080;
        renderCurrentFrame();
      }
    }
  );

  // 监听手动拖拽时间指针
  watch(
    () => currentTimeMs.value,
    (newVal) => {
      if (!isPlaying.value && !isSeekingInternally) {
        seekAllMediaTo(newVal);
        renderCurrentFrame();
      }
    }
  );

  // 关键修复：深度监听 tracks 内任何片段属性（文字、颜色、字号、缩放、位置、倍速、音量）的变化，在暂停时立即实时重绘画面！
  watch(
    () => timeline.value.tracks,
    () => {
      for (const t of timeline.value.tracks) {
        for (const c of t.clips) {
          if (c.type === 'video' || c.type === 'audio') {
            void ensureClipMedia(c);
          }
        }
      }
      if (!isPlaying.value) {
        renderCurrentFrame();
      }
    },
    { deep: true, immediate: true }
  );

  onUnmounted(() => {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    mediaElementCache.forEach((el) => {
      if (el instanceof HTMLVideoElement || el instanceof HTMLAudioElement) el.pause();
    });
    mediaElementCache.clear();
  });

  return {
    canvasRef,
    isExporting,
    exportProgress,
    setCanvasElement,
    preloadClipMedia: ensureClipMedia,
    renderCurrentFrame,
    startPlayback,
    pausePlayback,
    togglePlay,
    seekTo,
    stepFrame,
    exportMp4
  };
}