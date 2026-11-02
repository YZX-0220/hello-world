<template>
  <div class="editor-workbench-layout" @keydown="handleGlobalKeydown" tabindex="0">
    <!-- 顶部全局导航栏 -->
    <header class="editor-header">
      <div class="header-left">
        <button class="back-home-btn" @click="goBack" title="返回项目空间">← 返回</button>
        <input 
          type="text" 
          v-model="projectTitle" 
          class="project-title-input" 
          placeholder="未命名剪辑工程"
          @blur="triggerAutoSave" 
        />
        <div class="save-status-pill" :class="persistenceState.status">
          <span class="status-dot"></span>
          <span>{{ persistenceText }}</span>
        </div>
      </div>

      <div class="header-right">
        <!-- 云端存储配额进度小胶囊 -->
        <div class="quota-capsule" v-if="quota">
          <span>云端用量: {{ (quota.used_bytes / (1024 * 1024)).toFixed(0) }}MB / {{ quota.quota_gb }}GB</span>
        </div>

        <button class="export-main-btn" @click="showExportModal = true">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z" />
          </svg>
          <span>导出视频</span>
        </button>
      </div>
    </header>

    <!-- 主工作区：上下两层 -->
    <div class="editor-body">
      <!-- 上半部分：三栏协作区 -->
      <section class="upper-workspace-grid">
        <!-- 左栏：素材面板 -->
        <MediaPanel 
          class="grid-left" 
          :isWorkspaceMounted="isWorkspaceMounted" 
          :mountedFolderName="mountedFolderName"
          :directoryHandle="directoryHandle" 
          :quota="quota" 
          @mountWorkspace="mountLocalWorkspace" 
        />

        <!-- 中栏：实时视窗与播放控制 -->
        <PlayerPreview 
          class="grid-center" 
          :timeline="timeline" 
          :currentTimeMs="currentTimeMs" 
          :isPlaying="isPlaying"
          :isExporting="isExporting" 
          :exportProgress="exportProgress" 
          :activeClip="activeSelectedClip"
          @setCanvas="setCanvasElement"
          @togglePlay="togglePlay" 
          @step="stepFrame" 
          @changeAspect="setAspectRatio" 
        />

        <!-- 右栏：动态属性检查器 -->
        <PropertyInspector 
          class="grid-right" 
          :timeline="timeline" 
          :activeClip="activeSelectedClip" 
        />
      </section>

      <!-- 中置快捷功能工具条 -->
      <TimelineToolbar 
        :hasSelectedClip="!!selectedClipId" 
        :zoomScale="zoomScale" 
        :isSnappingEnabled="isSnappingEnabled"
        @split="splitSelectedClip" 
        @delete="deleteSelectedClip" 
        @undo="undo" 
        @redo="redo" 
        @addMarker="addMarker"
        @toggleSnap="isSnappingEnabled = !isSnappingEnabled" 
        @zoomIn="zoomIn" 
        @zoomOut="zoomOut" 
        @setZoom="setZoom" 
      />

      <!-- 下半部分：多轨道时间轴 -->
      <section class="lower-timeline-section">
        <MultiTrackTimeline 
          :timeline="timeline" 
          :currentTimeMs="currentTimeMs" 
          :selectedClipId="selectedClipId"
          :zoomScale="zoomScale" 
          @update:currentTimeMs="val => currentTimeMs = val"
          @selectClip="id => selectedClipId = id" 
          @addTrack="addTrack" 
          @removeTrack="removeTrack"
          @appendClip="appendClip" 
        />
      </section>
    </div>

    <!-- 成片导出弹窗 -->
    <ExportDialog 
      v-if="showExportModal" 
      :timeline="timeline" 
      :quota="quota" 
      :onSynthesizeMp4="exportMp4"
      @close="showExportModal = false" 
      @exportCompleted="fetchQuota" 
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useTimelineState } from '../composables/useTimelineState';
import { useFileSystemWorkspace } from '../composables/useFileSystemWorkspace';
import { useClipEngine } from '../composables/useClipEngine';
import { ClipProjectPersistence, type PersistenceState } from '../services/clipProjectPersistence';
import { libraryApi } from '../services/libraryApi';
import type { StorageQuotaView, ClipProjectView } from '../types/clip';

import MediaPanel from '../components/editor/MediaPanel.vue';
import PlayerPreview from '../components/editor/PlayerPreview.vue';
import PropertyInspector from '../components/editor/PropertyInspector.vue';
import TimelineToolbar from '../components/editor/TimelineToolbar.vue';
import MultiTrackTimeline from '../components/editor/MultiTrackTimeline.vue';
import ExportDialog from '../components/editor/ExportDialog.vue';

const router = useRouter();
const route = useRoute();

// 1. 时间轴状态机
const {
  timeline,
  currentTimeMs,
  isPlaying,
  selectedClipId,
  activeSelectedClip,
  zoomScale,
  isSnappingEnabled,
  addTrack,
  setAspectRatio,
  removeTrack,
  appendClip,
  splitSelectedClip,
  deleteSelectedClip,
  addMarker,
  zoomIn,
  zoomOut,
  setZoom,
  undo,
  redo
} = useTimelineState();

// 2. 本地工作目录与 0 流量决策链
const {
  directoryHandle,
  isWorkspaceMounted,
  mountedFolderName,
  mountLocalWorkspace,
  resolveAssetMediaUrl
} = useFileSystemWorkspace();

// 3. WebAV 纯前端混流引擎
const {
  isExporting,
  exportProgress,
  setCanvasElement,
  togglePlay,
  stepFrame,
  exportMp4
} = useClipEngine(timeline, currentTimeMs, isPlaying, resolveAssetMediaUrl);

// 4. 工程草稿与持久化
const projectTitle = ref('未命名剪辑工程');
const quota = ref<StorageQuotaView | null>(null);
const showExportModal = ref(false);
let persistenceService: ClipProjectPersistence | null = null;

const persistenceState = ref<PersistenceState>({
  status: 'saved',
  version: 1,
  lastSavedAt: null,
  errorMsg: ''
});

const persistenceText = computed(() => {
  if (persistenceState.value.status === 'saving') return '正在静默保存草稿...';
  if (persistenceState.value.status === 'conflict') return '草稿存在多端冲突';
  if (persistenceState.value.status === 'error') return '保存异常，已暂存本机';
  return persistenceState.value.lastSavedAt ? `已自动保存 (${persistenceState.value.lastSavedAt})` : '已保存';
});

async function fetchQuota() {
  try {
    quota.value = await libraryApi.getStorageQuota();
  } catch (err) {
    console.warn('配额查询失败', err);
  }
}

// 加载指定草稿工程
async function initProject() {
  const projectId = route.query.project_id as string;
  let projectView: ClipProjectView;

  if (projectId) {
    projectView = await libraryApi.getProject(projectId);
    projectTitle.value = projectView.title;
    try {
      const parsed = JSON.parse(projectView.timeline_json);
      if (parsed.tracks) timeline.value = parsed;
    } catch { }
  } else {
    projectView = await libraryApi.createProject({ title: '新剪辑工程' });
    projectTitle.value = projectView.title;
    await router.replace({ query: { project_id: projectView.id } });
  }

  persistenceService = new ClipProjectPersistence(projectView, state => {
    persistenceState.value = state;
  });
}

function triggerAutoSave() {
  persistenceService?.markDirty(projectTitle.value, timeline.value);
}

// 监听时间轴内容变动，防抖保存
watch(
  () => timeline.value,
  () => {
    triggerAutoSave();
  },
  { deep: true }
);

// 键盘快捷键响应 (C 分割, Delete 删除, Ctrl+Z 撤销, 空格播放)
function handleGlobalKeydown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement).tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;

  if (e.code === 'Space') {
    e.preventDefault();
    togglePlay();
  } else if (e.key === 'c' || e.key === 'C') {
    splitSelectedClip();
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    deleteSelectedClip();
  } else if (e.key === 'm' || e.key === 'M') {
    addMarker();
  } else if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
    if (e.shiftKey) redo();
    else undo();
  }
}

// 优化后的返回函数：异步静默尝试保存，同时立即执行路由回退
function goBack() {
  if (persistenceService) {
    persistenceService.flush().catch(() => { });
  }

  if (window.history.length > 1) {
    router.back();
  } else {
    router.push('/workspace');
  }
}

onMounted(() => {
  void fetchQuota();
  void initProject();
});
</script>

<style scoped>
.editor-workbench-layout {
  width: 100vw;
  height: 100vh;
  background-color: #0c0b0e;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: #fff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", sans-serif;
  outline: none;
}

.editor-header {
  height: 50px;
  background-color: #15131c;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  z-index: 100;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.back-home-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.project-title-input {
  background: transparent;
  border: 1px solid transparent;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 4px;
}

.project-title-input:hover,
.project-title-input:focus {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.1);
}

.save-status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #71717a;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
}

.save-status-pill.saving .status-dot {
  background: #6366f1;
}

.save-status-pill.conflict .status-dot {
  background: #f59e0b;
}

.save-status-pill.error .status-dot {
  background: #ef4444;
}

.quota-capsule {
  font-size: 11px;
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 10px;
  border-radius: 20px;
}

.export-main-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  border: none;
  color: #fff;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s;
}

.export-main-btn:hover {
  transform: scale(1.02);
}

.editor-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.upper-workspace-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 280px 1fr 300px;
  overflow: hidden;
}

.lower-timeline-section {
  height: 260px;
  overflow: hidden;
}
</style>