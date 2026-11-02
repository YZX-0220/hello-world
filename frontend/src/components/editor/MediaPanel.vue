<template>
  <aside class="media-panel">
    <!-- 顶部 Tab 切换 -->
    <div class="panel-tabs">
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'ai' }" 
        @click="activeTab = 'ai'"
      >
        AI 生成
      </button>
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'library' }" 
        @click="activeTab = 'library'"
      >
        我的素材
      </button>
      <button 
        class="tab-btn" 
        :class="{ active: activeTab === 'text' }" 
        @click="activeTab = 'text'"
      >
        文本库
      </button>
    </div>

    <!-- 1. AI 生成素材 Tab (回流当前平台任务产物) -->
    <div v-if="activeTab === 'ai'" class="tab-content">
      <div class="content-header">
        <span class="sub-tip">AI 视频任务生成回流素材</span>
        <button class="refresh-btn" @click="fetchAiAssets" :disabled="isLoading">↻ 刷新</button>
      </div>

      <div v-if="isLoading" class="loading-box">
        <span class="loading-spin"></span>
        <span>加载 AI 成果...</span>
      </div>

      <div v-else-if="aiAssets.length === 0" class="empty-box">
        <span>暂无 AI 生成视频</span>
        <small>在工作台通过底模生成的视频将自动显示在此</small>
      </div>

      <div v-else class="assets-grid">
        <div 
          v-for="item in aiAssets" 
          :key="item.id" 
          class="asset-card"
          draggable="true"
          @dragstart="handleDragStart($event, item)"
        >
          <div class="thumb-wrapper">
            <video :src="item.url" class="asset-thumb" muted preload="metadata"></video>
            <span class="duration-badge">{{ formatSeconds(item.duration_ms) }}</span>
          </div>
          <div class="asset-title" :title="item.file_name">{{ item.file_name }}</div>
        </div>
      </div>
    </div>

    <!-- 2. 用户资料库 / 本地素材 Tab -->
    <div v-else-if="activeTab === 'library'" class="tab-content">
      <div class="content-header">
        <!-- 挂载本地工作目录以实现 0 流量复用 -->
        <button class="mount-folder-btn" @click="$emit('mountWorkspace')">
          📁 {{ isWorkspaceMounted ? `已挂载: ${mountedFolderName}` : '挂载本地资料目录' }}
        </button>
        <label class="import-file-btn">
          <span>+ 导入素材</span>
          <input type="file" multiple accept="video/*,audio/*,image/*" @change="handleLocalImport" hidden />
        </label>
      </div>

      <!-- 配额提示胶囊 -->
      <div class="quota-pill" v-if="quota">
        <span>云端资料库: {{ (quota.used_bytes / (1024 * 1024)).toFixed(1) }}MB / {{ quota.quota_gb }}GB</span>
        <div class="quota-bar">
          <div class="quota-fill" :style="{ width: `${Math.min(100, quota.usage_percent)}%` }"></div>
        </div>
      </div>

      <div class="assets-grid">
        <div 
          v-for="item in userAssets" 
          :key="item.id" 
          class="asset-card"
          draggable="true"
          @dragstart="handleDragStart($event, item)"
        >
        <button 
            class="delete-asset-btn" 
            @click.stop="handleDeleteAsset(item.id)" 
            title="删除此素材"
          >
            ×
          </button>
          <div class="thumb-wrapper">
            <img v-if="item.kind === 'image'" :src="item.url" class="asset-thumb" />
            <video v-else-if="item.kind === 'video'" :src="item.url" class="asset-thumb" muted preload="metadata"></video>
            <div v-else class="audio-thumb">🎵 音频</div>
            <span class="kind-tag">{{ item.kind }}</span>
          </div>
          <div class="asset-title" :title="item.file_name">{{ item.file_name }}</div>
        </div>
      </div>
    </div>

    <!-- 3. 文本素材预设库 -->
    <div v-else class="tab-content">
      <div class="content-header">
        <span class="sub-tip">拖入时间轴添加字幕与花字</span>
      </div>
      <div class="text-templates-list">
        <div 
          v-for="tpl in textTemplates" 
          :key="tpl.title" 
          class="text-tpl-card"
          draggable="true"
          @dragstart="handleTextDragStart($event, tpl)"
        >
          <span class="tpl-title" :style="{ color: tpl.color }">{{ tpl.title }}</span>
          <span class="tpl-desc">{{ tpl.desc }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { libraryApi } from '../../services/libraryApi';
import type { LibraryAssetView, StorageQuotaView } from '../../types/clip';

const props = defineProps<{
  isWorkspaceMounted: boolean;
  mountedFolderName: string;
  quota: StorageQuotaView | null;
  directoryHandle?: any;
}>();

const emit = defineEmits<{
  (e: 'mountWorkspace'): void;
}>();

const activeTab = ref<'ai' | 'library' | 'text'>('ai');
const isLoading = ref(false);
const aiAssets = ref<LibraryAssetView[]>([]);
const userAssets = ref<LibraryAssetView[]>([]);

const textTemplates = [
  { title: '默认解说字幕', text: '点击输入字幕内容', color: '#FFFFFF', fontSize: 26, desc: '白色常规居中字幕' },
  { title: '醒目大标题', text: '重点标题展示', color: '#FACC15', fontSize: 36, desc: '黄色加粗主题字' },
  { title: '背景底栏字幕', text: '带半透明背景的文案', color: '#FFFFFF', fontSize: 24, desc: '深色遮罩高可读性' }
];

async function fetchAiAssets() {
  isLoading.value = true;
  try {
    const res = await libraryApi.listAssets({ purpose: 'ai_generated' });
    aiAssets.value = res.items || [];
  } catch (err) {
    console.warn('获取 AI 资产列表失败', err);
  } finally {
    isLoading.value = false;
  }
}

async function fetchUserAssets() {
  try {
    const res = await libraryApi.listAssets({ purpose: 'source_video' });
    userAssets.value = res.items || [];
  } catch (err) {
    console.warn('获取素材列表失败', err);
  }
}

function handleDragStart(e: DragEvent, asset: LibraryAssetView) {
  if (!e.dataTransfer) return;
  const payload = {
    sourceType: 'asset',
    assetId: asset.id,
    fileName: asset.file_name,
    kind: asset.kind,
    sha256: asset.sha256,
    url: asset.url,
    durationMs: asset.duration_ms || (asset.kind === 'image' ? 3000 : 5000),
    isImageSource: asset.kind === 'image'
  };
  e.dataTransfer.setData('application/json', JSON.stringify(payload));
}

function handleTextDragStart(e: DragEvent, tpl: typeof textTemplates[0]) {
  if (!e.dataTransfer) return;
  const payload = {
    sourceType: 'text',
    text: tpl.text,
    color: tpl.color,
    fontSize: tpl.fontSize
  };
  e.dataTransfer.setData('application/json', JSON.stringify(payload));
}

// 辅助：计算文件 SHA-256
async function calculateFileSha256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

// 探测媒体文件（视频/音频）的真实时长（毫秒）
function detectMediaDuration(file: File, kind: 'video' | 'audio' | 'image'): Promise<number> {
  if (kind === 'image') return Promise.resolve(3000); // 静态图片默认 3 秒

  return new Promise((resolve) => {
    const el = document.createElement(kind === 'video' ? 'video' : 'audio');
    el.preload = 'metadata';
    el.src = URL.createObjectURL(file);
    el.onloadedmetadata = () => {
      URL.revokeObjectURL(el.src);
      const durationMs = Math.round(el.duration * 1000);
      resolve(Number.isFinite(durationMs) && durationMs > 0 ? durationMs : 5000);
    };
    el.onerror = () => {
      URL.revokeObjectURL(el.src);
      resolve(5000);
    };
  });
}

// 删除已导入素材
function handleDeleteAsset(assetId: string) {
  if (confirm('确定要从当前列表中移除该素材吗？')) {
    userAssets.value = userAssets.value.filter(a => a.id !== assetId);
  }
}

// 唯一保留的真正执行本地素材导入函数
async function handleLocalImport(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;

  for (let i = 0; i < files.length; i++) {
    const file = files[i];

    let kind: 'video' | 'image' | 'audio' = 'video';
    if (file.type.startsWith('image/')) kind = 'image';
    else if (file.type.startsWith('audio/')) kind = 'audio';

    try {
      const sha256 = await calculateFileSha256(file);
      const realDurationMs = await detectMediaDuration(file, kind);
      const blobUrl = URL.createObjectURL(file);

      // 若已挂载工作目录，将文件写入目录实现本地复用
      const dirHandle = props.directoryHandle;
      if (dirHandle) {
        try {
          const fileHandle = await dirHandle.getFileHandle(file.name, { create: true });
          const writable = await fileHandle.createWritable();
          await writable.write(file);
          await writable.close();
        } catch (dirErr) {
          console.warn('写入本地目录失败或权限已过期', dirErr);
        }
      }

      // 添加到前端素材列表
      const newAssetItem: LibraryAssetView = {
        id: `local_${Date.now()}_${i}`,
        file_name: file.name,
        size_bytes: file.size,
        mime_type: file.type || 'video/mp4',
        kind,
        purpose: 'source_video',
        sha256,
        duration_ms: realDurationMs,
        url: blobUrl,
        created_at: new Date().toISOString()
      };

      userAssets.value.unshift(newAssetItem);
    } catch (err) {
      console.error(`导入文件 ${file.name} 失败`, err);
    }
  }

  input.value = '';
}

function formatSeconds(ms?: number) {
  if (!ms) return '00:03';
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60).toString().padStart(2, '0');
  const s = (sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

onMounted(() => {
  void fetchAiAssets();
  void fetchUserAssets();
});
</script>
<style scoped>
.asset-card {
  position: relative;
}

.delete-asset-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 10;
  width: 18px;
  height: 18px;
  background: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  line-height: 1;
  display: none;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s;
}

.asset-card:hover .delete-asset-btn {
  display: flex;
}

.delete-asset-btn:hover {
  background: #ef4444;
}
.media-panel {
  display: flex;
  flex-direction: column;
  background-color: #121118;
  height: 100%;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  user-select: none;
}

.panel-tabs {
  display: flex;
  height: 44px;
  background-color: #17151f;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.tab-btn {
  flex: 1;
  background: transparent;
  border: none;
  color: #a1a1aa;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn.active {
  color: #ffffff;
  border-bottom-color: #6366f1;
  background: rgba(99, 102, 241, 0.08);
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sub-tip { font-size: 12px; color: #71717a; }

.refresh-btn {
  background: transparent;
  border: none;
  color: #818cf8;
  font-size: 12px;
  cursor: pointer;
}

.mount-folder-btn, .import-file-btn {
  font-size: 11px;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
  cursor: pointer;
}

.quota-pill {
  background: rgba(255, 255, 255, 0.03);
  padding: 8px;
  border-radius: 6px;
  font-size: 11px;
  color: #71717a;
}

.quota-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  margin-top: 6px;
  overflow: hidden;
}

.quota-fill {
  height: 100%;
  background: #6366f1;
}

.assets-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.asset-card {
  background: #1a1824;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  overflow: hidden;
  cursor: grab;
  transition: transform 0.2s, border-color 0.2s;
}

.asset-card:hover {
  transform: translateY(-2px);
  border-color: #6366f1;
}

.thumb-wrapper {
  position: relative;
  width: 100%;
  height: 72px;
  background-color: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.asset-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.audio-thumb { font-size: 12px; color: #a1a1aa; }

.duration-badge, .kind-tag {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background: rgba(0, 0, 0, 0.7);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 10px;
  color: #fff;
}

.asset-title {
  padding: 6px 8px;
  font-size: 11px;
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.text-templates-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.text-tpl-card {
  padding: 12px;
  background: #1a1824;
  border: 1px dashed rgba(255, 255, 255, 0.15);
  border-radius: 6px;
  cursor: grab;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.text-tpl-card:hover { border-color: #6366f1; }
.tpl-title { font-size: 13px; font-weight: bold; }
.tpl-desc { font-size: 11px; color: #71717a; }

.loading-box, .empty-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 120px;
  gap: 8px;
  color: #71717a;
  font-size: 12px;
  text-align: center;
}
</style>