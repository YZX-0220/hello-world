import { ref } from 'vue';

interface IndexedFileRecord {
  sha256: string;
  filename: string;
  handle: FileSystemFileHandle;
  updatedAt: number;
}

const DB_NAME = 'HelloWorldClipWorkspaceDB';
const STORE_NAME = 'file_handles';

export function useFileSystemWorkspace() {
  const directoryHandle = ref<FileSystemDirectoryHandle | null>(null);
  const isWorkspaceMounted = ref(false);
  const mountedFolderName = ref('');
  const isSyncing = ref(false);

  // 1. 初始化 IndexedDB，用于跨页面持久化存储文件句柄
  async function getDb(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'sha256' });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function saveHandleToIndex(record: IndexedFileRecord) {
    const db = await getDb();
    return new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).put(record);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function getHandleFromIndex(sha256: string): Promise<FileSystemFileHandle | null> {
    const db = await getDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const req = tx.objectStore(STORE_NAME).get(sha256);
      req.onsuccess = () => resolve(req.result?.handle || null);
      req.onerror = () => reject(req.error);
    });
  }

  // 2. 挂载用户本地工作目录
  async function mountLocalWorkspace() {
    if (!('showDirectoryPicker' in window)) {
      alert('当前浏览器不支持 File System Access API，建议使用最新 Chrome 或 Edge 浏览器');
      return false;
    }

    try {
      const dirHandle = await (window as any).showDirectoryPicker({
        mode: 'readwrite'
      });
      directoryHandle.value = dirHandle;
      mountedFolderName.value = dirHandle.name;
      isWorkspaceMounted.value = true;
      return true;
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        console.error('挂载目录失败:', e);
      }
      return false;
    }
  }

  // 3. 计算 ArrayBuffer 的 SHA-256 哈希
  async function calculateSha256(buffer: ArrayBuffer): Promise<string> {
    const digest = await crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(digest))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }

  // 4. 素材消费三级加载决策链
  // 返回可直接交由 WebAV / Video 标签消费的 Blob URL
  async function resolveAssetMediaUrl(asset: {
    sha256: string;
    file_name: string;
    url: string; // 后端下发的 OBS 预签名下载链接
  }): Promise<string> {
    // ---- Level 1 & 2: 校验本地工作目录是否已存在匹配文件 ----
    if (directoryHandle.value) {
      try {
        // 先查 IndexedDB 是否已有句柄
        let fileHandle = await getHandleFromIndex(asset.sha256);

        // 如果没有句柄，尝试直接在本地目录下按文件名查找
        if (!fileHandle) {
          try {
            fileHandle = await directoryHandle.value.getFileHandle(asset.file_name, { create: false });
          } catch {
            fileHandle = null;
          }
        }

        if (fileHandle) {
          // 确认读写权限
          const permission = await (fileHandle as any).queryPermission({ mode: 'read' });
          if (permission === 'granted') {
            const file = await fileHandle.getFile();
            // 直接读取本地磁盘文件，0 流量消耗
            return URL.createObjectURL(file);
          }
        }
      } catch (err) {
        console.warn('本地文件读取异常，降级至网络直连', err);
      }
    }

    // ---- Level 3: 本地未命中，从云端拉取并持久化至本地工作区 ----
    isSyncing.value = true;
    try {
      const res = await fetch(asset.url);
      if (!res.ok) throw new Error(`云端下载失败: ${res.status}`);
      const blob = await res.blob();
      const buffer = await blob.arrayBuffer();

      // 若用户挂载了本地工作区，则将文件写入用户本地目录供后续永久复用
      if (directoryHandle.value) {
        try {
          const newHandle = await directoryHandle.value.getFileHandle(asset.file_name, { create: true });
          const writable = await (newHandle as any).createWritable();
          await writable.write(buffer);
          await writable.close();

          // 记录索引到 IndexedDB
          await saveHandleToIndex({
            sha256: asset.sha256,
            filename: asset.file_name,
            handle: newHandle,
            updatedAt: Date.now()
          });
        } catch (writeErr) {
          console.warn('自动写入本地资料目录失败（可能是权限受限）:', writeErr);
        }
      }

      return URL.createObjectURL(blob);
    } finally {
      isSyncing.value = false;
    }
  }

  return {
    directoryHandle,
    isWorkspaceMounted,
    mountedFolderName,
    isSyncing,
    mountLocalWorkspace,
    resolveAssetMediaUrl,
    calculateSha256
  };
}