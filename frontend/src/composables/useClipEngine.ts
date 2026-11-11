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

  // Web Audio API 功率放大管线（支持 0% ~ 200% 真实音量增益与平滑淡入淡出）
  let audioCtx: AudioContext | null = null;
  const gainNodeCache = new Map<string, GainNode>();

  function bindAudioGainNode(clipId: string, mediaEl: HTMLVideoElement | HTMLAudioElement) {
    if (gainNodeCache.has(clipId)) return;
    try {
      const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!audioCtx) {
        audioCtx = new AudioCtxClass();
      }
      const source = audioCtx.createMediaElementSource(mediaEl);
      const gainNode = audioCtx.createGain();
      source.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      gainNodeCache.set(clipId, gainNode);
    } catch (e) {
      // 若浏览器环境或跨域限制则回退到原生 volume
      console.warn('WebAudio 增益节点绑定回退:', e);
    }
  }

  // 设置元素实时音量（支持最高 2.0 即 200% 放大，以及淡入淡出衰减）
  function applyMediaVolume(
    clipId: string,
    mediaEl: HTMLVideoElement | HTMLAudioElement,
    isMuted: boolean,
    baseVolume: number,
    elapsedInClipMs: number,
    clipDurationMs: number,
    fadeInMs: number = 0,
    fadeOutMs: number = 0
  ) {
    if (isMuted || baseVolume <= 0) {
      mediaEl.muted = true;
      return;
    }
    mediaEl.muted = false;

    // 计算淡入淡出线性包络系数 (0.0 ~ 1.0)
    let fadeFactor = 1.0;
    if (fadeInMs > 0 && elapsedInClipMs < fadeInMs) {
      fadeFactor = Math.max(0, elapsedInClipMs / fadeInMs);
    }
    const remainMs = clipDurationMs - elapsedInClipMs;
    if (fadeOutMs > 0 && remainMs < fadeOutMs) {
      fadeFactor = Math.min(fadeFactor, Math.max(0, remainMs / fadeOutMs));
    }

    const finalGain = Math.max(0, Math.min(2.0, baseVolume * fadeFactor));
    const gainNode = gainNodeCache.get(clipId);

    if (gainNode && audioCtx) {
      if (audioCtx.state === 'suspended' && isPlaying.value) {
        void audioCtx.resume();
      }
      mediaEl.volume = 1.0; // 原生开满，交由 GainNode 控制 0 ~ 200%
      gainNode.gain.value = finalGain;
    } else {
      // 兜底：原生 volume 最大为 1.0
      mediaEl.volume = Math.min(1.0, finalGain);
    }
  }

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

          bindAudioGainNode(cacheKey, video);
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

        bindAudioGainNode(cacheKey, audio);
        mediaElementCache.set(cacheKey, audio);
        return audio;
      }
    } finally {
      loadingClips.delete(cacheKey);
    }
    return null;
  }
  // 核心：根据当前片段内的相对时间 elapsedMs，在相邻两个关键帧 A -> B 之间执行平滑线性插值
  function resolveAnimatedProp(clip: any, propName: string, elapsedMs: number, defaultVal: number): number {
    const baseVal = clip[propName] ?? defaultVal;
    const kfs = clip.keyframes;
    if (!Array.isArray(kfs) || kfs.length === 0) return baseVal;

    const sorted = [...kfs].sort((a: any, b: any) => a.offset_ms - b.offset_ms);
    // 只有 1 个关键帧，或在第一个关键帧左侧：保持第一个关键帧的值
    if (sorted.length === 1 || elapsedMs <= sorted[0].offset_ms) {
      return sorted[0][propName] ?? baseVal;
    }
    // 在最后一个关键帧右侧：保持最后一个关键帧的值
    const last = sorted[sorted.length - 1];
    if (elapsedMs >= last.offset_ms) {
      return last[propName] ?? baseVal;
    }

    // 从左往右找到当前所处的 [关键帧 A, 关键帧 B] 区间并线性插值
    for (let i = 0; i < sorted.length - 1; i++) {
      const kfA = sorted[i];
      const kfB = sorted[i + 1];
      if (elapsedMs >= kfA.offset_ms && elapsedMs <= kfB.offset_ms) {
        const span = Math.max(1, kfB.offset_ms - kfA.offset_ms);
        const t = (elapsedMs - kfA.offset_ms) / span;
        const valA = kfA[propName] ?? baseVal;
        const valB = kfB[propName] ?? baseVal;
        return valA + (valB - valA) * t;
      }
    }
    return baseVal;
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

    // 视频画幅区域填充纯黑底色
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, targetW, targetH);

    ctx.clearRect(0, 0, targetW, targetH);

    const tracksToRender = [...timeline.value.tracks].reverse();

    for (const track of tracksToRender) {
      if (track.hidden) continue;

      for (const clip of track.clips) {
        const clipStart = clip.start_ms;
        const clipEnd = clip.start_ms + clip.duration_ms;

        if (curTime < clipStart || curTime > clipEnd) {
          const cachedEl = mediaElementCache.get(clip.id);
          if ((cachedEl instanceof HTMLVideoElement || cachedEl instanceof HTMLAudioElement) && !cachedEl.paused) {
            cachedEl.pause();
          }
          continue;
        }

        const elapsedMs = curTime - clipStart;
        ctx.save();

        // A. 文本片段实时渲染（支持 X/Y 自由拖拽、字号、颜色、对齐、不透明度）
        if (clip.type === 'text') {
          const textClip = clip as TextClip;
          const animOpacity = resolveAnimatedProp(textClip, 'opacity', elapsedMs, 1.0);
          const animFontSize = resolveAnimatedProp(textClip, 'font_size', elapsedMs, 26) * 2;
          const animPosX = resolveAnimatedProp(textClip, 'position_x', elapsedMs, 0);
          const animPosY = resolveAnimatedProp(textClip, 'position_y', elapsedMs, 0);

          ctx.globalAlpha = animOpacity;
          ctx.font = `bold ${animFontSize}px sans-serif`;
          ctx.textAlign = textClip.align || 'center';
          ctx.textBaseline = 'middle';

          const baseTextX = textClip.align === 'left' ? 120 : textClip.align === 'right' ? targetW - 120 : targetW / 2;
          const textX = baseTextX + animPosX;
          const textY = targetH - 180 + animPosY;

          const lines = (textClip.text || '').split('\n');
          const lineHeight = animFontSize * 1.25;

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
              ctx.fillRect(bgX, lineY - animFontSize / 2 - padY, metrics.width + padX * 2, animFontSize + padY * 2);
            }

            ctx.lineWidth = Math.max(3, Math.round(animFontSize / 10));
            ctx.strokeStyle = 'rgba(0, 0, 0, 0.85)';
            ctx.strokeText(line, textX, lineY);

            ctx.fillStyle = textClip.color || '#FFFFFF';
            ctx.fillText(line, textX, lineY);
          });
        }
        // B. 视频/图片片段实时渲染（含 200% 音量增益与淡入淡出）
        else if (clip.type === 'video') {
          const videoClip = clip as VideoClip;
          const animOpacity = resolveAnimatedProp(videoClip, 'opacity', elapsedMs, 1.0);
          const animScale = resolveAnimatedProp(videoClip, 'scale', elapsedMs, 1.0);
          const animPosX = resolveAnimatedProp(videoClip, 'position_x', elapsedMs, 0);
          const animPosY = resolveAnimatedProp(videoClip, 'position_y', elapsedMs, 0);
          const animVolume = resolveAnimatedProp(videoClip, 'volume', elapsedMs, 1.0);

          ctx.globalAlpha = animOpacity;

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

              applyMediaVolume(
                clip.id,
                element,
                track.muted,
                animVolume, // 使用关键帧插值后的实时音量
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

            const finalW = fitW * animScale;
            const finalH = fitH * animScale;

            const drawX = (targetW - finalW) / 2 + animPosX;
            const drawY = (targetH - finalH) / 2 + animPosY;

            if (element instanceof HTMLImageElement) {
              ctx.drawImage(element, drawX, drawY, finalW, finalH);
            } else if (element instanceof HTMLVideoElement && element.readyState >= 1) {
              ctx.drawImage(element, drawX, drawY, finalW, finalH);
            }
          }
        }
        // C. 独立音频片段实时控制（含 200% 音量增益与淡入淡出）
        else if (clip.type === 'audio') {
          const audioClip = clip as AudioClip;
          const animVolume = resolveAnimatedProp(audioClip, 'volume', elapsedMs, 1.0);
          const element = mediaElementCache.get(clip.id);
          if (!element) {
            void ensureClipMedia(clip);
          } else if (element instanceof HTMLAudioElement) {
            applyMediaVolume(
              clip.id,
              element,
              track.muted,
              animVolume, // 使用关键帧插值后的实时音量
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
                el.play().catch(() => { });
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
    if (audioCtx && audioCtx.state === 'suspended') {
      void audioCtx.resume();
    }
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

  watch(
    () => currentTimeMs.value,
    (newVal) => {
      if (!isPlaying.value && !isSeekingInternally) {
        seekAllMediaTo(newVal);
        renderCurrentFrame();
      }
    }
  );

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
    gainNodeCache.clear();
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