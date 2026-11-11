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

    <!-- 1. AI 生成素材 Tab -->
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

    <!-- 2. 我的素材 Tab（剪映风格：支持多文件夹导入与层级浏览） -->
    <div v-else-if="activeTab === 'library'" class="tab-content">
      <!-- 顶部导入操作栏 -->
      <div class="content-header">
        <!-- 导入整个文件夹（选完立即扫描并生成文件夹卡片） -->
        <label class="import-folder-btn" title="直接导入一个或多个本地文件夹">
          <span>📁 + 导入文件夹</span>
          <input 
            type="file" 
            webkitdirectory 
            directory 
            multiple 
            @change="handleFolderInputImport" 
            hidden 
          />
        </label>

        <!-- 导入散装单文件/多文件 -->
        <label class="import-file-btn" title="导入单个或多个音视频/图片">
          <span>+ 导入素材</span>
          <input 
            type="file" 
            multiple 
            accept="video/*,audio/*,image/*" 
            @change="handleLocalImport" 
            hidden 
          />
        </label>
      </div>

      <!-- 配额提示胶囊 -->
      <div class="quota-pill" v-if="quota">
        <span>云端资料库: {{ (quota.used_bytes / (1024 * 1024)).toFixed(1) }}MB / {{ quota.quota_gb }}GB</span>
        <div class="quota-bar">
          <div class="quota-fill" :style="{ width: `${Math.min(100, quota.usage_percent)}%` }"></div>
        </div>
      </div>

      <!-- 面包屑路径导航（当点进某个文件夹内部时显示） -->
      <div class="breadcrumb-bar" v-if="activeFolderId">
        <span class="crumb-link" @click="activeFolderId = null">← 全部素材</span>
        <span class="crumb-sep">/</span>
        <span class="crumb-current">{{ currentOpenFolder?.name }} ({{ currentOpenFolder?.items.length || 0 }})</span>
      </div>

      <!-- 扫描加载提示 -->
      <div v-if="isScanning" class="scanning-tip">
        <span>正在自动扫描并解析文件夹媒体时长...</span>
      </div>

      <!-- 素材与文件夹混合网格 (剪映同款视图) -->
      <div class="assets-grid">
        <!-- A. 根目录视图：展示所有已导入的【文件夹卡片】 -->
        <template v-if="!activeFolderId">
          <div 
            v-for="folder in importedFolders" 
            :key="folder.id" 
            class="jianying-folder-card"
            @click="activeFolderId = folder.id"
          >
            <!-- 删除整个文件夹按钮 -->
            <button 
              class="delete-asset-btn" 
              @click.stop="handleDeleteFolder(folder.id)" 
              title="移除此文件夹"
            >
              ×
            </button>

            <!-- 剪映风格的堆叠卡片视觉层 -->
            <div class="folder-stack-box">
              <div class="stack-back-layer"></div>
              <div class="stack-preview-layer">
                <video 
                  v-if="folder.coverItem && folder.coverItem.kind === 'video'" 
                  :src="folder.coverItem.url" 
                  class="folder-cover-media" 
                  muted 
                  preload="metadata"
                ></video>
                <img 
                  v-else-if="folder.coverItem && folder.coverItem.kind === 'image'" 
                  :src="folder.coverItem.url" 
                  class="folder-cover-media" 
                />
                <div v-else class="folder-empty-cover">📁</div>
              </div>
              <!-- 前置半透明磨砂文件夹挡板 -->
              <div class="folder-front-lip">
                <span class="folder-count-tag">{{ folder.items.length }} 项</span>
              </div>
            </div>

            <div class="asset-title" :title="folder.name">{{ folder.name }}</div>
          </div>
        </template>

        <!-- B. 展示当前视图下的【具体媒体素材卡片】（根目录散装素材 或 当前打开文件夹内的素材） -->
        <div 
          v-for="item in displayedAssets" 
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
            <video 
              v-else-if="item.kind === 'video'" 
              :src="item.url" 
              class="asset-thumb" 
              muted 
              preload="metadata"
              @mouseenter="($event.target as HTMLVideoElement).play().catch(() => {})"
              @mouseleave="($event.target as HTMLVideoElement).pause(); ($event.target as HTMLVideoElement).currentTime = 0;"
            ></video>
            <div v-else class="audio-thumb">🎵 音频</div>
            <span class="duration-badge" v-if="item.kind !== 'image'">{{ formatSeconds(item.duration_ms) }}</span>
            <span class="kind-tag" v-else>图片</span>
          </div>
          <div class="asset-title" :title="item.file_name">{{ item.file_name }}</div>
        </div>
      </div>

      <!-- 空状态提示 -->
      <div v-if="!isScanning && importedFolders.length === 0 && displayedAssets.length === 0" class="empty-box">
        <span>暂无导入的素材或文件夹</span>
        <small>点击上方“导入文件夹”或“导入素材”即可自动扫描添加</small>
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
import { ref, computed, watch, onMounted } from 'vue';
import { libraryApi } from '../../services/libraryApi';
import type { LibraryAssetView, StorageQuotaView } from '../../types/clip';

// 文件夹数据结构（支持导入无限个文件夹）
interface ImportedFolderGroup {
  id: string;
  name: string;
  items: LibraryAssetView[];
  coverItem?: LibraryAssetView;
}

const props = defineProps<{
  isWorkspaceMounted: boolean;
  mountedFolderName: string;
  quota: StorageQuotaView | null;
  directoryHandle?: any;
}>();

defineEmits<{
  (e: 'mountWorkspace'): void;
}>();

const activeTab = ref<'ai' | 'library' | 'text'>('library');
const isLoading = ref(false);
const isScanning = ref(false);

const aiAssets = ref<LibraryAssetView[]>([]);
// 根目录下的散装单文件素材
const userAssets = ref<LibraryAssetView[]>([]);
// 已导入的多个文件夹列表（如“庄周幻梦”、“目前情况”等）
const importedFolders = ref<ImportedFolderGroup[]>([]);
// 当前点开查看的文件夹 ID（null 表示在根层级看全部）
const activeFolderId = ref<string | null>(null);

const currentOpenFolder = computed(() => {
  if (!activeFolderId.value) return null;
  return importedFolders.value.find(f => f.id === activeFolderId.value) || null;
});

// 当前网格中应显示的媒体卡片（如果在文件夹内则显示文件夹里的素材，否则显示根目录散装素材）
const displayedAssets = computed(() => {
  if (currentOpenFolder.value) {
    return currentOpenFolder.value.items;
  }
  return userAssets.value;
});

const textTemplates = [
  { title: '默认解说字幕', text: '点击输入字幕内容', color: '#FFFFFF', fontSize: 26, desc: '白色常规居中字幕' },
  { title: '醒目大标题', text: '重点标题展示', color: '#FACC15', fontSize: 36, desc: '黄色加粗主题字' },
  { title: '背景底栏字幕', text: '带半透明背景的文案', color: '#FFFFFF', fontSize: 24, desc: '深色遮罩高可读性' }
];

// 辅助：判断并提取媒体分类
function getMediaKind(file: File): 'video' | 'image' | 'audio' | null {
  const lower = file.name.toLowerCase();
  if (file.type.startsWith('video/') || lower.endsWith('.mp4') || lower.endsWith('.webm') || lower.endsWith('.mov') || lower.endsWith('.mkv')) {
    return 'video';
  }
  if (file.type.startsWith('image/') || lower.endsWith('.png') || lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.webp') || lower.endsWith('.gif')) {
    return 'image';
  }
  if (file.type.startsWith('audio/') || lower.endsWith('.mp3') || lower.endsWith('.wav') || lower.endsWith('.aac') || lower.endsWith('.flac')) {
    return 'audio';
  }
  return null;
}

// 辅助：计算文件 SHA-256
async function calculateFileSha256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

// 探测媒体文件（视频/音频）真实时长
function detectMediaDuration(file: File, kind: 'video' | 'audio' | 'image'): Promise<number> {
  if (kind === 'image') return Promise.resolve(3000);

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

// 将单个 File 转换为前端资产对象
async function fileToAssetView(file: File, kind: 'video' | 'image' | 'audio', indexSuffix: string): Promise<LibraryAssetView> {
  const sha256 = await calculateFileSha256(file);
  const realDurationMs = await detectMediaDuration(file, kind);
  const blobUrl = URL.createObjectURL(file);

  return {
    id: `local_${Date.now()}_${indexSuffix}`,
    file_name: file.name,
    size_bytes: file.size,
    mime_type: file.type || (kind === 'image' ? 'image/png' : 'video/mp4'),
    kind,
    purpose: 'source_video',
    sha256,
    duration_ms: realDurationMs,
    url: blobUrl,
    created_at: new Date(file.lastModified || Date.now()).toISOString()
  };
}

// 1. 直接导入整个文件夹（支持导入无限个文件夹，自动扫描分类并生成剪映式文件夹卡片）
async function handleFolderInputImport(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;

  isScanning.value = true;
  try {
    // 按顶层文件夹名称自动归组（例如“庄周幻梦/xxx.mp4”归入“庄周幻梦”）
    const folderMap = new Map<string, File[]>();

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const kind = getMediaKind(file);
      if (!kind) continue;

      const relPath = (file as any).webkitRelativePath || '';
      const folderName = relPath.includes('/') ? relPath.split('/')[0] : '导入文件夹';

      if (!folderMap.has(folderName)) {
        folderMap.set(folderName, []);
      }
      folderMap.get(folderName)!.push(file);
    }

    for (const [folderName, groupFiles] of folderMap.entries()) {
      const parsedItems: LibraryAssetView[] = [];
      for (let i = 0; i < groupFiles.length; i++) {
        const f = groupFiles[i];
        const kind = getMediaKind(f)!;
        const item = await fileToAssetView(f, kind, `${folderName}_${i}`);
        parsedItems.push(item);
      }

      if (parsedItems.length === 0) continue;

      // 如果同名文件夹已存在则合并进去，否则创建新文件夹卡片
      const existingFolder = importedFolders.value.find(fd => fd.name === folderName);
      if (existingFolder) {
        const existNames = new Set(existingFolder.items.map(it => it.file_name));
        const newOnes = parsedItems.filter(it => !existNames.has(it.file_name));
        existingFolder.items.push(...newOnes);
        if (!existingFolder.coverItem) {
          existingFolder.coverItem = existingFolder.items.find(it => it.kind !== 'audio');
        }
      } else {
        importedFolders.value.unshift({
          id: `folder_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
          name: folderName,
          items: parsedItems,
          coverItem: parsedItems.find(it => it.kind !== 'audio') || parsedItems[0]
        });
      }
    }

    // 导入文件夹后自动回到根层级展示新文件夹卡片
    activeFolderId.value = null;
  } catch (err) {
    console.error('导入并扫描文件夹失败:', err);
  } finally {
    isScanning.value = false;
    input.value = '';
  }
}

// 2. 兼容原有的 File System Access API 句柄：一旦传入自动扫描为文件夹卡片
async function scanDirectoryHandleToFolder(dirHandle: any) {
  if (!dirHandle) return;
  isScanning.value = true;
  try {
    const folderName = dirHandle.name || props.mountedFolderName || '本地文件夹';
    const parsedItems: LibraryAssetView[] = [];
    let idx = 0;

    for await (const entry of dirHandle.values()) {
      if (entry.kind === 'file') {
        const file = await entry.getFile();
        const kind = getMediaKind(file);
        if (kind) {
          const item = await fileToAssetView(file, kind, `handle_${idx++}`);
          parsedItems.push(item);
        }
      }
    }

    if (parsedItems.length > 0) {
      const existing = importedFolders.value.find(f => f.name === folderName);
      if (existing) {
        existing.items = parsedItems;
        existing.coverItem = parsedItems.find(it => it.kind !== 'audio') || parsedItems[0];
      } else {
        importedFolders.value.unshift({
          id: `folder_handle_${Date.now()}`,
          name: folderName,
          items: parsedItems,
          coverItem: parsedItems.find(it => it.kind !== 'audio') || parsedItems[0]
        });
      }
    }
  } catch (err) {
    console.warn('自动扫描目录句柄失败:', err);
  } finally {
    isScanning.value = false;
  }
}

watch(
  () => props.directoryHandle,
  (newHandle) => {
    if (newHandle) {
      void scanDirectoryHandleToFolder(newHandle);
    }
  },
  { immediate: true }
);

// 3. 导入单个或多个散装素材（若当前正处于某个文件夹内，则直接导入该文件夹；否则放在根目录与文件夹并列）
async function handleLocalImport(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;

  isScanning.value = true;
  try {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const kind = getMediaKind(file) || 'video';
      const newAssetItem = await fileToAssetView(file, kind, `single_${i}`);

      if (currentOpenFolder.value) {
        currentOpenFolder.value.items.unshift(newAssetItem);
        if (!currentOpenFolder.value.coverItem) {
          currentOpenFolder.value.coverItem = newAssetItem;
        }
      } else {
        userAssets.value.unshift(newAssetItem);
      }
    }
  } catch (err) {
    console.error('导入单文件失败:', err);
  } finally {
    isScanning.value = false;
    input.value = '';
  }
}

// 删除整个文件夹卡片
function handleDeleteFolder(folderId: string) {
  if (confirm('确定要从素材库移除此文件夹及其包含的素材吗？')) {
    importedFolders.value = importedFolders.value.filter(f => f.id !== folderId);
    if (activeFolderId.value === folderId) {
      activeFolderId.value = null;
    }
  }
}

// 删除单个素材卡片
function handleDeleteAsset(assetId: string) {
  if (currentOpenFolder.value) {
    currentOpenFolder.value.items = currentOpenFolder.value.items.filter(a => a.id !== assetId);
    currentOpenFolder.value.coverItem = currentOpenFolder.value.items.find(it => it.kind !== 'audio') || currentOpenFolder.value.items[0];
  } else {
    userAssets.value = userAssets.value.filter(a => a.id !== assetId);
  }
}

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

.import-folder-btn, .import-file-btn {
  flex: 1;
  text-align: center;
  font-size: 11px;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
  color: #e2e8f0;
  cursor: pointer;
  transition: all 0.2s;
}

.import-folder-btn:hover, .import-file-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  border-color: #6366f1;
  color: #fff;
}

/* 面包屑导航条 */
.breadcrumb-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  font-size: 12px;
}

.crumb-link {
  color: #818cf8;
  cursor: pointer;
  font-weight: 500;
}

.crumb-link:hover {
  text-decoration: underline;
}

.crumb-sep { color: #52525b; }
.crumb-current { color: #e4e4e7; font-weight: 600; }

.scanning-tip {
  font-size: 11px;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.1);
  padding: 6px 10px;
  border-radius: 6px;
  text-align: center;
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
  gap: 10px;
}

/* 剪映同款堆叠文件夹卡片样式 */
.jianying-folder-card {
  position: relative;
  cursor: pointer;
  border-radius: 8px;
  transition: transform 0.2s;
}

.jianying-folder-card:hover {
  transform: translateY(-2px);
}

.jianying-folder-card:hover .delete-asset-btn {
  display: flex;
}

.folder-stack-box {
  position: relative;
  width: 100%;
  height: 76px;
  background: #232329;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stack-back-layer {
  position: absolute;
  top: 4px;
  width: 82%;
  height: 60px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 6px;
}

.stack-preview-layer {
  position: absolute;
  top: 8px;
  width: 90%;
  height: 62px;
  background: #000;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
}

.folder-cover-media {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.folder-empty-cover {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

/* 剪映标志性的前置半透明文件夹挡板切角 */
.folder-front-lip {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 28px;
  background: linear-gradient(180deg, rgba(160, 155, 150, 0.78), rgba(120, 115, 110, 0.88));
  backdrop-filter: blur(6px);
  clip-path: polygon(0 0, 42% 0, 50% 22%, 100% 22%, 100% 100%, 0 100%);
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
  padding: 3px 6px;
}

.folder-count-tag {
  font-size: 9px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
}

/* 普通媒体卡片样式 */
.asset-card {
  position: relative;
  background: #1a1824;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  overflow: hidden;
  cursor: grab;
  transition: transform 0.2s, border-color 0.2s;
}

.asset-card:hover {
  transform: translateY(-2px);
  border-color: #22d3ee;
}

.delete-asset-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 15;
  width: 18px;
  height: 18px;
  background: rgba(0, 0, 0, 0.7);
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

.thumb-wrapper {
  position: relative;
  width: 100%;
  height: 76px;
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
  top: 4px;
  right: 6px;
  background: rgba(0, 0, 0, 0.65);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 10px;
  font-family: monospace;
  color: #fff;
}

.asset-title {
  padding: 6px 4px 2px;
  font-size: 11px;
  color: #a1a1aa;
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