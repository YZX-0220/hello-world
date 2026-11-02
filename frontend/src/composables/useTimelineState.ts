import { ref, computed } from 'vue';
import type { TimelineDocument, TimelineTrack, TimelineClip, TrackType } from '../types/clip';

function newId(): string {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function useTimelineState() {
  const timeline = ref<TimelineDocument>({
    width: 1920,
    height: 1080,
    fps: 30,
    duration_ms: 0,
    tracks: [
      { id: 'track_text_1', type: 'text', name: '文本轨 1', muted: false, hidden: false, locked: false, clips: [] },
      { id: 'track_video_1', type: 'video', name: '主视频轨', muted: false, hidden: false, locked: false, clips: [] },
      { id: 'track_audio_1', type: 'audio', name: '主音频轨', muted: false, hidden: false, locked: false, clips: [] }
    ],
    markers: []
  });

  const currentTimeMs = ref<number>(0);
  const isPlaying = ref<boolean>(false);
  const selectedClipId = ref<string | null>(null);
  const zoomScale = ref<number>(1.0);
  const isSnappingEnabled = ref<boolean>(true);

  // 历史栈 (撤销 / 重做)
  const undoStack = ref<string[]>([]);
  const redoStack = ref<string[]>([]);

  function pushHistory() {
    undoStack.value.push(JSON.stringify(timeline.value));
    if (undoStack.value.length > 50) undoStack.value.shift();
    redoStack.value = [];
  }

  function undo() {
    if (!undoStack.value.length) return;
    redoStack.value.push(JSON.stringify(timeline.value));
    const prev = undoStack.value.pop()!;
    timeline.value = JSON.parse(prev);
    recalculateDuration();
  }

  function redo() {
    if (!redoStack.value.length) return;
    undoStack.value.push(JSON.stringify(timeline.value));
    const next = redoStack.value.pop()!;
    timeline.value = JSON.parse(next);
    recalculateDuration();
  }

  // 重新扫描并更新时间线总时长
  function recalculateDuration() {
    let maxEnd = 0;
    for (const track of timeline.value.tracks) {
      for (const clip of track.clips) {
        const end = clip.start_ms + clip.duration_ms;
        if (end > maxEnd) maxEnd = end;
      }
    }
    timeline.value.duration_ms = maxEnd;
  }

  // 获取当前选中的片段对象
  const activeSelectedClip = computed<TimelineClip | null>(() => {
    if (!selectedClipId.value) return null;
    for (const track of timeline.value.tracks) {
      const found = track.clips.find(c => c.id === selectedClipId.value);
      if (found) return found;
    }
    return null;
  });

  // 添加轨道
  function addTrack(type: TrackType) {
    pushHistory();
    const count = timeline.value.tracks.filter(t => t.type === type).length + 1;
    const nameMap: Record<TrackType, string> = {
      video: `视频轨 ${count}`,
      audio: `音频轨 ${count}`,
      text: `文本轨 ${count}`
    };

    const newTrack: TimelineTrack = {
      id: `track_${type}_${newId()}`,
      type,
      name: nameMap[type],
      muted: false,
      hidden: false,
      locked: false,
      clips: []
    };

    // 文本轨置顶，视频轨居中，音频轨置底
    if (type === 'text') {
      timeline.value.tracks.unshift(newTrack);
    } else if (type === 'video') {
      const lastVideoIdx = timeline.value.tracks.map(t => t.type).lastIndexOf('video');
      timeline.value.tracks.splice(lastVideoIdx + 1, 0, newTrack);
    } else {
      timeline.value.tracks.push(newTrack);
    }
  }

  // 移除轨道
  function removeTrack(trackId: string) {
    pushHistory();
    timeline.value.tracks = timeline.value.tracks.filter(t => t.id !== trackId);
    recalculateDuration();
  }

  // 追加片段到指定轨道
  function appendClip(trackId: string, clipData: any) {
    pushHistory();
    const track = timeline.value.tracks.find(t => t.id === trackId);
    if (!track) return;

    const clip: TimelineClip = {
      ...clipData,
      id: `clip_${newId()}`,
      track_id: trackId,
      in_point_ms: clipData.in_point_ms || 0,
      out_point_ms: clipData.out_point_ms || clipData.duration_ms
    };

    track.clips.push(clip);
    selectedClipId.value = clip.id;
    recalculateDuration();
  }

  // 分割选中片段 (C 键)
  function splitSelectedClip() {
    if (!selectedClipId.value) return;
    const clip = activeSelectedClip.value;
    if (!clip) return;

    const splitPoint = currentTimeMs.value;
    const clipEnd = clip.start_ms + clip.duration_ms;
    if (splitPoint <= clip.start_ms || splitPoint >= clipEnd) return;

    pushHistory();
    const track = timeline.value.tracks.find(t => t.id === clip.track_id);
    if (!track) return;

    const firstDuration = splitPoint - clip.start_ms;
    const secondDuration = clip.duration_ms - firstDuration;

    const secondClip: TimelineClip = {
      ...JSON.parse(JSON.stringify(clip)),
      id: `clip_${newId()}`,
      start_ms: splitPoint,
      duration_ms: secondDuration,
      in_point_ms: clip.in_point_ms + firstDuration,
      out_point_ms: clip.out_point_ms
    };

    clip.duration_ms = firstDuration;
    clip.out_point_ms = clip.in_point_ms + firstDuration;

    track.clips.push(secondClip);
    selectedClipId.value = secondClip.id;
    recalculateDuration();
  }

  // 删除选中片段 (Delete / Backspace 键)
  function deleteSelectedClip() {
    if (!selectedClipId.value) return;
    pushHistory();
    for (const track of timeline.value.tracks) {
      const idx = track.clips.findIndex(c => c.id === selectedClipId.value);
      if (idx !== -1) {
        track.clips.splice(idx, 1);
        selectedClipId.value = null;
        recalculateDuration();
        break;
      }
    }
  }

  // 添加时间标记 (M 键)
  function addMarker(label: string = '标记') {
    pushHistory();
    timeline.value.markers.push({
      id: `marker_${newId()}`,
      time_ms: currentTimeMs.value,
      label
    });
  }

  // 缩放操作
  function zoomIn() {
    zoomScale.value = Math.min(5.0, Number((zoomScale.value + 0.2).toFixed(1)));
  }

  function zoomOut() {
    zoomScale.value = Math.max(0.2, Number((zoomScale.value - 0.2).toFixed(1)));
  }

  function setZoom(val: number) {
    zoomScale.value = Math.max(0.2, Math.min(5.0, val));
  }

  // 画幅切换 (16:9 / 9:16)
  function setAspectRatio(ratio: '16:9' | '9:16' | '1:1') {
    pushHistory();
    if (ratio === '16:9') {
      timeline.value.width = 1920;
      timeline.value.height = 1080;
    } else if (ratio === '9:16') {
      timeline.value.width = 1080;
      timeline.value.height = 1920;
    } else if (ratio === '1:1') {
      timeline.value.width = 1080;
      timeline.value.height = 1080;
    }
  }

  return {
    timeline,
    currentTimeMs,
    isPlaying,
    selectedClipId,
    activeSelectedClip,
    zoomScale,
    isSnappingEnabled,
    addTrack,
    removeTrack,
    appendClip,
    splitSelectedClip,
    deleteSelectedClip,
    addMarker,
    zoomIn,
    zoomOut,
    setZoom,
    setAspectRatio,
    undo,
    redo,
    pushHistory,
    recalculateDuration
  };
}