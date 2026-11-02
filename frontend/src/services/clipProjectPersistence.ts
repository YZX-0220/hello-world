import { libraryApi } from './libraryApi';
import type { TimelineDocument, ClipProjectView } from '../types/clip';

export type SaveStatus = 'saved' | 'saving' | 'conflict' | 'error';

export interface PersistenceState {
  status: SaveStatus;
  version: number;
  lastSavedAt: string | null;
  errorMsg: string;
}

export class ClipProjectPersistence {
  private projectId: string;
  private currentVersion: number;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private onStateChange: (state: PersistenceState) => void;
  private isSaving = false;
  private hasPendingChanges = false;
  private latestTitle: string = '未命名工程';
  private latestTimeline: TimelineDocument | null = null;

  constructor(
    initialProject: ClipProjectView,
    onStateChange: (state: PersistenceState) => void
  ) {
    this.projectId = initialProject.id;
    this.currentVersion = initialProject.version;
    this.latestTitle = initialProject.title;
    this.onStateChange = onStateChange;

    this.notify('saved');
    this.bindUnloadEvents();
  }

  private notify(status: SaveStatus, errorMsg = '') {
    this.onStateChange({
      status,
      version: this.currentVersion,
      lastSavedAt: new Date().toLocaleTimeString(),
      errorMsg
    });
  }

  // 触发时间线改动，启动 5 秒防抖
  public markDirty(title: string, timelineDoc: TimelineDocument) {
    this.latestTitle = title;
    this.latestTimeline = timelineDoc;
    this.hasPendingChanges = true;

    // 先存入浏览器本地 LocalStorage 兜底
    try {
      localStorage.setItem(
        `clip_draft_${this.projectId}`,
        JSON.stringify({
          title,
          timeline: timelineDoc,
          version: this.currentVersion,
          updated_at: Date.now()
        })
      );
    } catch (e) {
      console.warn('本地缓存暂存失败', e);
    }

    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      void this.flush();
    }, 5000);
  }

  // 立即将变更提交保存至云端
  public async flush(): Promise<boolean> {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }

    if (!this.hasPendingChanges || !this.latestTimeline || this.isSaving) {
      return true;
    }

    this.isSaving = true;
    this.notify('saving');

    try {
      const updated = await libraryApi.updateProject(this.projectId, {
        title: this.latestTitle,
        timeline_json: JSON.stringify(this.latestTimeline),
        duration_ms: this.latestTimeline.duration_ms,
        expected_version: this.currentVersion
      });

      this.currentVersion = updated.version;
      this.hasPendingChanges = false;
      this.notify('saved');
      return true;
    } catch (err: any) {
      // 捕获 409 或乐观锁版本冲突
      if (err?.response?.status === 409 || err?.message?.includes('conflict') || err?.message?.includes('版本')) {
        this.notify('conflict', '草稿在其他端被修改，请刷新以同步最新版本');
      } else {
        this.notify('error', err?.message || '草稿自动保存失败，已暂存本机');
      }
      return false;
    } finally {
      this.isSaving = false;
    }
  }

  // 绑定浏览器关闭或刷新事件，使用 keepalive 兜底提交
  private bindUnloadEvents() {
    window.addEventListener('pagehide', () => {
      if (!this.hasPendingChanges || !this.latestTimeline) return;
      const token = document.cookie.match(/(?:^|;\s*)hw_csrf=([^;]+)/)?.[1];
      if (!token) return;

      const body = JSON.stringify({
        title: this.latestTitle,
        timeline_json: JSON.stringify(this.latestTimeline),
        duration_ms: this.latestTimeline.duration_ms,
        expected_version: this.currentVersion
      });

      // 遵循轻量文本规范，限制在 60KB 以内避免丢失
      if (new TextEncoder().encode(body).length <= 60000) {
        void fetch(`/api/v1/clip-projects/${this.projectId}`, {
          method: 'PUT',
          credentials: 'include',
          keepalive: true,
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': decodeURIComponent(token)
          },
          body
        }).catch(() => {});
      }
    });
  }

  public destroy() {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
  }
}