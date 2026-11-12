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

     <!-- AI 生成素材卡片 (约第 49 行) -->
        <div 
          v-for="item in aiAssets" 
          :key="item.id" 
          class="asset-card"
          :class="{ 'active-asset': selectedAssetId === item.id }"
          draggable="true"
          @click="handleAssetClick(item)"
          @dragstart="handleDragStart($event, item)"
        >
         <div class="thumb-wrapper">
            <video 
              :src="item.url" 
              class="asset-thumb" 
              muted 
              preload="metadata"
              disablepictureinpicture
              controlslist="nodownload nofullscreen noremoteplayback"
              @loadedmetadata="onMediaMetadataLoaded($event, item)"
            ></video>
            <span class="duration-badge">{{ formatSeconds(item.duration_ms) }}</span>
          </div>
          <div class="asset-title" :title="item.file_name">{{ item.file_name }}</div>
        </div>
    </div>

    <!-- 2. 我的素材 Tab（内置 5s 全黑/全白固定素材 + 多文件夹导入） -->
    <div v-else-if="activeTab === 'library'" class="tab-content">
      <!-- 顶部导入操作栏 -->
      <div class="content-header">
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

      <!-- 素材与文件夹混合网格 -->
      <div class="assets-grid">
        <!-- A. 根目录视图：展示所有已导入的【文件夹卡片】 -->
        <template v-if="!activeFolderId">
          <div 
            v-for="folder in importedFolders" 
            :key="folder.id" 
            class="jianying-folder-card"
            @click="activeFolderId = folder.id"
          >
            <button 
              class="delete-asset-btn" 
              @click.stop="handleDeleteFolder(folder.id)" 
              title="移除此文件夹"
            >
              ×
            </button>

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
              <div class="folder-front-lip">
                <span class="folder-count-tag">{{ folder.items.length }} 项</span>
              </div>
            </div>

            <div class="asset-title" :title="folder.name">{{ folder.name }}</div>
          </div>
        </template>

       <!-- B. 展示当前视图下的【具体媒体素材卡片】 -->
        <div 
          v-for="item in displayedAssets" 
          :key="item.id" 
          class="asset-card"
          :class="{ 'active-asset': selectedAssetId === item.id }"
          draggable="true"
          @click="handleAssetClick(item)"
          @dragstart="handleDragStart($event, item)"
        >
          <!-- 系统内置的黑白场固定素材不显示删除按钮 -->
          <button 
            v-if="!isBuiltinAsset(item.id)"
            class="delete-asset-btn" 
            @click.stop="handleDeleteAsset(item.id)" 
            title="删除此素材"
          >
            ×
          </button>

          <div class="thumb-wrapper" :class="{ 'white-matte-thumb': item.id === 'builtin_white_5s' }">
            <img v-if="item.kind === 'image' || isBuiltinAsset(item.id)" :src="item.url" class="asset-thumb" draggable="false" />
            <video 
              v-else-if="item.kind === 'video'" 
              :src="item.url" 
              class="asset-thumb" 
              muted 
              preload="metadata"
              disablepictureinpicture
              controlslist="nodownload nofullscreen noremoteplayback"
              @loadedmetadata="onMediaMetadataLoaded($event, item)"
            ></video>
            <!-- 剪映风格音频缩略图（蓝底声波卡片） -->
            <div v-else class="audio-wave-thumb">
              <svg viewBox="0 0 100 32" preserveAspectRatio="none" class="mini-wave-svg">
                <path d="M0 32 L0 26 L8 22 L14 10 L20 25 L28 28 L35 24 L42 12 L48 27 L56 29 L65 8 L72 24 L80 28 L88 16 L94 24 L100 22 L100 32 Z" fill="#38bdf8" opacity="0.85" />
              </svg>
            </div>

            <span class="builtin-badge" v-if="isBuiltinAsset(item.id)">内置</span>
            <span class="duration-badge" v-if="item.kind !== 'image' || isBuiltinAsset(item.id)">{{ formatSeconds(item.duration_ms) }}</span>
            <span class="kind-tag" v-else>图片</span>
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
import { ref, computed, watch, onMounted } from 'vue';
import { libraryApi } from '../../services/libraryApi';
import type { LibraryAssetView, StorageQuotaView } from '../../types/clip';
// 当卡片上的 <video> 加载完元数据时，自动将真实时长回填到 item.duration_ms
function onMediaMetadataLoaded(e: Event, item: LibraryAssetView) {
  const el = e.target as HTMLMediaElement;
  if (el && Number.isFinite(el.duration) && el.duration > 0) {
    const realMs = Math.round(el.duration * 1000);
    if (item.duration_ms !== realMs) {
      item.duration_ms = realMs;
    }
  }
}

// 针对云端拉取的音频素材（无 <video> 标签），后台静默探测其真实时长
function probeRemoteAssetsDuration(list: LibraryAssetView[]) {
  list.forEach((item) => {
    if ((!item.duration_ms || item.duration_ms <= 0) && item.url && item.kind === 'audio') {
      const audio = document.createElement('audio');
      audio.preload = 'metadata';
      audio.src = item.url;
      audio.onloadedmetadata = () => {
        if (Number.isFinite(audio.duration) && audio.duration > 0) {
          item.duration_ms = Math.round(audio.duration * 1000);
        }
        audio.src = '';
      };
    }
  });
}
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

const emit = defineEmits<{
  (e: 'mountWorkspace'): void;
  (e: 'previewAsset', asset: LibraryAssetView): void;
}>();

const selectedAssetId = ref<string | null>(null);

function handleAssetClick(item: LibraryAssetView) {
  selectedAssetId.value = item.id;
  emit('previewAsset', item);
}
const activeTab = ref<'ai' | 'library' | 'text'>('library');
const isLoading = ref(false);
const isScanning = ref(false);

// 生成纯黑/纯白 16:9 幕布 DataURL（用于内置 5 秒全黑/全白视频素材，0 网络依赖、100% 稳定渲染）
function createSolidMatteDataUrl(hexColor: string): string {
  const canvas = document.createElement('canvas');
  canvas.width = 640;
  canvas.height = 360;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.fillStyle = hexColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
  return canvas.toDataURL('image/png');
}

// 每名用户固定自带的 5 秒全黑视频与 5 秒全白视频素材
const builtinMatteAssets: LibraryAssetView[] = [
  {
    id: 'builtin_black_5s',
    file_name: '全黑视频 (5s).mp4',
    size_bytes: 0,
    mime_type: 'video/mp4',
    kind: 'video',
    purpose: 'source_video',
    sha256: 'builtin_black_5s_sha256',
    duration_ms: 5000,
    url: createSolidMatteDataUrl('#000000'),
    created_at: new Date(0).toISOString()
  },
  {
    id: 'builtin_white_5s',
    file_name: '全白视频 (5s).mp4',
    size_bytes: 0,
    mime_type: 'video/mp4',
    kind: 'video',
    purpose: 'source_video',
    sha256: 'builtin_white_5s_sha256',
    duration_ms: 5000,
    url: createSolidMatteDataUrl('#FFFFFF'),
    created_at: new Date(0).toISOString()
  }
];

function isBuiltinAsset(id: string): boolean {
  return id === 'builtin_black_5s' || id === 'builtin_white_5s';
}

const aiAssets = ref<LibraryAssetView[]>([]);
const userAssets = ref<LibraryAssetView[]>([]);
const importedFolders = ref<ImportedFolderGroup[]>([]);
const activeFolderId = ref<string | null>(null);

const currentOpenFolder = computed(() => {
  if (!activeFolderId.value) return null;
  return importedFolders.value.find(f => f.id === activeFolderId.value) || null;
});

// 当前网格中应显示的媒体卡片（根层级下始终将 5 秒全黑视频与 5 秒全白视频固定排在最前面）
const displayedAssets = computed(() => {
  if (currentOpenFolder.value) {
    return currentOpenFolder.value.items;
  }
  const filteredUser = userAssets.value.filter(a => !isBuiltinAsset(a.id));
  return [...builtinMatteAssets, ...filteredUser];
});

const textTemplates = [
  { title: '默认解说字幕', text: '点击输入字幕内容', color: '#FFFFFF', fontSize: 26, desc: '白色常规居中字幕' },
  { title: '醒目大标题', text: '重点标题展示', color: '#FACC15', fontSize: 36, desc: '黄色加粗主题字' },
  { title: '背景底栏字幕', text: '带半透明背景的文案', color: '#FFFFFF', fontSize: 24, desc: '深色遮罩高可读性' }
];

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

async function calculateFileSha256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

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

async function handleFolderInputImport(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = input.files;
  if (!files || files.length === 0) return;

  isScanning.value = true;
  try {
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

    activeFolderId.value = null;
  } catch (err) {
    console.error('导入并扫描文件夹失败:', err);
  } finally {
    isScanning.value = false;
    input.value = '';
  }
}

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

function handleDeleteFolder(folderId: string) {
  if (confirm('确定要从素材库移除此文件夹及其包含的素材吗？')) {
    importedFolders.value = importedFolders.value.filter(f => f.id !== folderId);
    if (activeFolderId.value === folderId) {
      activeFolderId.value = null;
    }
  }
}

function handleDeleteAsset(assetId: string) {
  if (isBuiltinAsset(assetId)) return;
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
    probeRemoteAssetsDuration(aiAssets.value);
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
    probeRemoteAssetsDuration(userAssets.value);
  } catch (err) {
    console.warn('获取素材列表失败', err);
  }
}

function handleDragStart(e: DragEvent, asset: LibraryAssetView) {
  if (!e.dataTransfer) return;
  // 内置的 5 秒全黑/全白视频在底层使用无损静态帧模式驱动，既具备 5000ms 完整视频时长与关键帧能力，又免去视频解码开销
  const isMatte = isBuiltinAsset(asset.id);
  const payload = {
    sourceType: 'asset',
    assetId: asset.id,
    fileName: asset.file_name,
    kind: asset.kind,
    sha256: asset.sha256,
    url: asset.url,
    durationMs: asset.duration_ms || (asset.kind === 'image' ? 3000 : 5000),
    isImageSource: asset.kind === 'image' || isMatte
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
  if (!ms || ms <= 0) return '--:--';
  const sec = Math.round(ms / 1000);
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

.breadcrumb-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  font-size: 12px;
}

.crumb-link { color: #818cf8; cursor: pointer; font-weight: 500; }
.crumb-link:hover { text-decoration: underline; }
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

.quota-fill { height: 100%; background: #6366f1; }

.assets-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.jianying-folder-card {
  position: relative;
  cursor: pointer;
  border-radius: 8px;
  transition: transform 0.2s;
}

.jianying-folder-card:hover { transform: translateY(-2px); }
.jianying-folder-card:hover .delete-asset-btn { display: flex; }

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

.folder-cover-media { width: 100%; height: 100%; object-fit: cover; }
.folder-empty-cover { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 20px; }

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

.folder-count-tag { font-size: 9px; color: rgba(255, 255, 255, 0.9); font-weight: 600; }

.asset-card {
  position: relative;
  background: #1a1824;
  border: 1px solid rgba(255, 255, 255, 0.08);
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

.asset-card:hover .delete-asset-btn { display: flex; }
.delete-asset-btn:hover { background: #ef4444; }

.thumb-wrapper {
  position: relative;
  width: 100%;
  height: 76px;
  background-color: #000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumb-wrapper.white-matte-thumb {
  background-color: #ffffff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
}

.asset-card.active-asset {
  border-color: #00e5ff;
  box-shadow: 0 0 0 1.5px #00e5ff;
}

.asset-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none; /* 关键：禁止 video/img 拦截鼠标悬浮与拖拽事件，彻底杜绝画中画弹窗 */
}

.audio-wave-thumb {
  width: 100%;
  height: 100%;
  background: #0c2b4e;
  display: flex;
  align-items: flex-end;
  pointer-events: none;
}

.mini-wave-svg {
  width: 100%;
  height: 75%;
}
.builtin-badge {
  position: absolute;
  top: 4px;
  left: 6px;
  background: rgba(99, 102, 241, 0.85);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 9px;
  color: #fff;
  font-weight: 600;
}

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
  padding: 6px 6px 4px;
  font-size: 11px;
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.text-templates-list { display: flex; flex-direction: column; gap: 8px; }

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