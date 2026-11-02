import { ref, shallowRef, watch, onUnmounted, type Ref } from 'vue';
import type { TimelineDocument, TimelineClip, VideoClip, TextClip } from '../types/clip';

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

  // 2. 预加载媒体资源
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
          file_name: (clip as any).file_name || 'video.mp4',
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
          video.volume = typeof videoClip.volume === 'number' ? Math.min(1.0, videoClip.volume) : 1.0;
          video.playsInline = true;

          await new Promise((res) => {
            video.onloadeddata = res;
            video.onerror = res;
          });

          mediaElementCache.set(cacheKey, video);
          renderCurrentFrame();
          return video;
        }
      }
    } finally {
      loadingClips.delete(cacheKey);
    }
    return null;
  }

  // 3. 核心单向渲染函数（仅读取，不反向 Seek，杜绝回跳）
  function renderCurrentFrame() {
    const canvas = canvasRef.value;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const targetW = canvas.width;
    const targetH = canvas.height;
    const curTime = currentTimeMs.value;

    // 清空画布（透明清底，消除黑色边界）
    ctx.clearRect(0, 0, targetW, targetH);

    // 逆序遍历轨道保证图层先后
    const tracksToRender = [...timeline.value.tracks].reverse();

    for (const track of tracksToRender) {
      if (track.hidden) continue;

      for (const clip of track.clips) {
        const clipStart = clip.start_ms;
        const clipEnd = clip.start_ms + clip.duration_ms;

        // 不在当前时段
        if (curTime < clipStart || curTime > clipEnd) {
          const cachedEl = mediaElementCache.get(clip.id);
          if (cachedEl instanceof HTMLVideoElement && !cachedEl.paused) {
            cachedEl.pause();
          }
          continue;
        }

        ctx.save();

        if (clip.type === 'text') {
          const textClip = clip as TextClip;
          ctx.globalAlpha = textClip.opacity ?? 1.0;
          ctx.font = `bold ${textClip.font_size * 2}px sans-serif`;
          ctx.textAlign = textClip.align || 'center';
          ctx.textBaseline = 'middle';

          const textX = textClip.align === 'left' ? 80 : textClip.align === 'right' ? targetW - 80 : targetW / 2;
          const textY = targetH - 180;

          if (textClip.background_color) {
            ctx.fillStyle = textClip.background_color;
            const textMetrics = ctx.measureText(textClip.text);
            const pad = 16;
            ctx.fillRect(textX - textMetrics.width / 2 - pad, textY - 30 - pad, textMetrics.width + pad * 2, 60 + pad * 2);
          }

          ctx.fillStyle = textClip.color || '#FFFFFF';
          ctx.fillText(textClip.text, textX, textY);
        } else if (clip.type === 'video') {
          const videoClip = clip as VideoClip;
          ctx.globalAlpha = videoClip.opacity ?? 1.0;

          const element = mediaElementCache.get(clip.id);
          if (!element) {
            void ensureClipMedia(clip);
          } else {
            const elemW = (element instanceof HTMLVideoElement ? element.videoWidth : (element as HTMLImageElement).naturalWidth) || 1920;
            const elemH = (element instanceof HTMLVideoElement ? element.videoHeight : (element as HTMLImageElement).naturalHeight) || 1080;

            if (element instanceof HTMLVideoElement) {
              element.muted = track.muted;
              element.volume = Math.min(1.0, videoClip.volume ?? 1.0);

              // 仅在暂停状态且手动拖动进度条时才执行精确定位
              if (!isPlaying.value) {
                const targetSec = (curTime - clipStart + videoClip.in_point_ms) / 1000 * (videoClip.playback_rate || 1.0);
                if (Math.abs(element.currentTime - targetSec) > 0.05) {
                  element.currentTime = targetSec;
                }
              }
            }

            // 自适应居中与缩放平移
            const scaleFactor = Math.min(targetW / elemW, targetH / elemH);
            const fitW = elemW * scaleFactor;
            const fitH = elemH * scaleFactor;

            const userScale = (videoClip as any).scale ?? 1.0;
            const finalW = fitW * userScale;
            const finalH = fitH * userScale;

            const posX = ((videoClip as any).position_x ?? 0);
            const posY = ((videoClip as any).position_y ?? 0);

            const drawX = (targetW - finalW) / 2 + posX;
            const drawY = (targetH - finalH) / 2 + posY;

            if (element instanceof HTMLImageElement) {
              ctx.drawImage(element, drawX, drawY, finalW, finalH);
            } else if (element instanceof HTMLVideoElement && element.readyState >= 1) {
              ctx.drawImage(element, drawX, drawY, finalW, finalH);
            }
          }
        }
        ctx.restore();
      }
    }
  }

  // 4. 彻底解耦的播放调度时钟（单向驱动，杜绝重入和鬼畜循环）
  function playTick(timestamp: number) {
    if (!isPlaying.value) return;

    if (!lastTimestamp) lastTimestamp = timestamp;
    const deltaMs = timestamp - lastTimestamp;
    lastTimestamp = timestamp;

    const nextTime = currentTimeMs.value + deltaMs;

    // 播放越界判定
    if (nextTime >= timeline.value.duration_ms) {
      if (timeline.value.duration_ms > 0) {
        pausePlayback();
        currentTimeMs.value = 0;
        seekAllVideosTo(0);
        renderCurrentFrame();
      }
      return;
    }

    isSeekingInternally = true;
    currentTimeMs.value = nextTime;
    isSeekingInternally = false;

    renderCurrentFrame();
    animationFrameId = requestAnimationFrame(playTick);
  }

  // 同步所有音视频对象的真实播放
  function syncPlayAllActiveClips() {
    const cur = currentTimeMs.value;
    timeline.value.tracks.forEach(track => {
      track.clips.forEach(clip => {
        if (clip.type === 'video') {
          const el = mediaElementCache.get(clip.id);
          if (el instanceof HTMLVideoElement) {
            const inRange = cur >= clip.start_ms && cur < clip.start_ms + clip.duration_ms;
            if (inRange) {
              const targetSec = (cur - clip.start_ms + clip.in_point_ms) / 1000;
              if (Math.abs(el.currentTime - targetSec) > 0.15) {
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

  function seekAllVideosTo(targetMs: number) {
    timeline.value.tracks.forEach(track => {
      track.clips.forEach(clip => {
        if (clip.type === 'video') {
          const el = mediaElementCache.get(clip.id);
          if (el instanceof HTMLVideoElement) {
            const inRange = targetMs >= clip.start_ms && targetMs < clip.start_ms + clip.duration_ms;
            if (inRange) {
              el.currentTime = (targetMs - clip.start_ms + clip.in_point_ms) / 1000;
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
      if (el instanceof HTMLVideoElement && !el.paused) {
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
    seekAllVideosTo(currentTimeMs.value);
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
        seekAllVideosTo(simulatedTime);
        renderCurrentFrame();
        exportProgress.value = Math.min(100, Math.floor((simulatedTime / totalDuration) * 100));

        if (simulatedTime >= totalDuration) {
          clearInterval(recordInterval);
          mediaRecorder.stop();
        }
      }, stepMs);
    });
  }

  // 监听画幅分辨率
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

  // 关键优化：屏蔽播放时的 watch 冗余重绘，仅在外部手动拖动时间轴时更新画面
  watch(
    () => currentTimeMs.value,
    (newVal) => {
      if (!isPlaying.value && !isSeekingInternally) {
        seekAllVideosTo(newVal);
        renderCurrentFrame();
      }
    }
  );

  onUnmounted(() => {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    mediaElementCache.forEach((el) => {
      if (el instanceof HTMLVideoElement) el.pause();
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