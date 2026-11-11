import { ref, computed, watch } from 'vue';
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

  // 记录上一次已稳定的时间轴序列化快照，用于自动捕获右侧属性面板的修改
  let lastCommittedJson = JSON.stringify(timeline.value);
  let isRestoringHistory = false;
  let lastMutationTimestamp = 0;

  // 显式压入历史栈（用于添加、分割、删除等离散操作）
  function pushHistory() {
    const currentJson = JSON.stringify(timeline.value);
    if (undoStack.value.length === 0 || undoStack.value[undoStack.value.length - 1] !== currentJson) {
      undoStack.value.push(currentJson);
      if (undoStack.value.length > 50) undoStack.value.shift();
    }
    redoStack.value = [];
  }

  // 监听 timeline 内部任何属性的细微变化（如倍速 1x->2x、缩放、位置拖拽、字幕修改、音量调节）
  watch(
    () => timeline.value,
    (newVal) => {
      if (isRestoringHistory) return;
      const newJson = JSON.stringify(newVal);
      if (newJson === lastCommittedJson) return;

      const now = Date.now();
      // 如果距离上一次修改超过 600ms（说明是一次新的修改动作，如点击 2x 倍速或新拖动滑块），
      // 且之前没有被显式 pushHistory 记录过，则把修改前的状态 lastCommittedJson 压入撤销栈
      if (now - lastMutationTimestamp > 600) {
        if (undoStack.value.length === 0 || undoStack.value[undoStack.value.length - 1] !== lastCommittedJson) {
          undoStack.value.push(lastCommittedJson);
          if (undoStack.value.length > 50) undoStack.value.shift();
          redoStack.value = [];
        }
      }

      lastMutationTimestamp = now;
      lastCommittedJson = newJson;
    },
    { deep: true }
  );

  function undo() {
    if (!undoStack.value.length) return;
    isRestoringHistory = true;
    try {
      const currentJson = JSON.stringify(timeline.value);
      redoStack.value.push(currentJson);

      const prevJson = undoStack.value.pop()!;
      timeline.value = JSON.parse(prevJson);
      lastCommittedJson = prevJson;
      lastMutationTimestamp = 0;
      recalculateDuration();
    } finally {
      setTimeout(() => {
        isRestoringHistory = false;
      }, 0);
    }
  }

  function redo() {
    if (!redoStack.value.length) return;
    isRestoringHistory = true;
    try {
      const currentJson = JSON.stringify(timeline.value);
      undoStack.value.push(currentJson);

      const nextJson = redoStack.value.pop()!;
      timeline.value = JSON.parse(nextJson);
      lastCommittedJson = nextJson;
      lastMutationTimestamp = 0;
      recalculateDuration();
    } finally {
      setTimeout(() => {
        isRestoringHistory = false;
      }, 0);
    }
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

  // 当选中某个片段时，若播放指针不在该片段范围内，自动跳到片段开头以便实时预览修改效果
  watch(selectedClipId, (newId) => {
    if (!newId || isRestoringHistory) return;
    const clip = activeSelectedClip.value;
    if (clip && (currentTimeMs.value < clip.start_ms || currentTimeMs.value > clip.start_ms + clip.duration_ms)) {
      currentTimeMs.value = clip.start_ms;
    }
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

    if (type === 'text') {
      timeline.value.tracks.unshift(newTrack);
    } else if (type === 'video') {
      const lastVideoIdx = timeline.value.tracks.map(t => t.type).lastIndexOf('video');
      timeline.value.tracks.splice(lastVideoIdx + 1, 0, newTrack);
    } else {
      timeline.value.tracks.push(newTrack);
    }
    lastCommittedJson = JSON.stringify(timeline.value);
  }

  // 移除轨道
  function removeTrack(trackId: string) {
    pushHistory();
    timeline.value.tracks = timeline.value.tracks.filter(t => t.id !== trackId);
    recalculateDuration();
    lastCommittedJson = JSON.stringify(timeline.value);
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
    lastCommittedJson = JSON.stringify(timeline.value);
    lastMutationTimestamp = 0; // 重置冷却时间，确保紧接着修改属性（如倍速）时必定作为新的一步记录
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
    lastCommittedJson = JSON.stringify(timeline.value);
    lastMutationTimestamp = 0;
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
    lastCommittedJson = JSON.stringify(timeline.value);
    lastMutationTimestamp = 0;
  }

  // 添加时间标记 (M 键)
  function addMarker(label: string = '标记') {
    pushHistory();
    timeline.value.markers.push({
      id: `marker_${newId()}`,
      time_ms: currentTimeMs.value,
      label
    });
    lastCommittedJson = JSON.stringify(timeline.value);
    lastMutationTimestamp = 0;
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
    lastCommittedJson = JSON.stringify(timeline.value);
    lastMutationTimestamp = 0;
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