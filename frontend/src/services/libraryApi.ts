import request from '../utils/request';
import type {
  ClipProjectView,
  LibraryAssetView,
  StorageQuotaView
} from '../types/clip';

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export const libraryApi = {
  // 1. 获取当前用户存储配额使用情况（1GB 配额与 Redis 缓存聚合）
  async getStorageQuota(): Promise<StorageQuotaView> {
    return request.get<StorageQuotaView, StorageQuotaView>('/api/v1/library/quota');
  },

  // 2. 检索资料库素材（支持按类型、来源筛选）
  async listAssets(params?: {
    kind?: 'video' | 'image' | 'audio';
    purpose?: 'all' | 'source_video' | 'ai_generated' | 'clip_export';
    q?: string;
    limit?: number;
    cursor?: string;
  }): Promise<PageResponse<LibraryAssetView>> {
    return request.get<PageResponse<LibraryAssetView>, PageResponse<LibraryAssetView>>(
      '/api/v1/library/assets',
      { params: { limit: 20, ...params } }
    );
  },

  // 3. 获取所有草稿工程列表
  async listProjects(): Promise<ClipProjectView[]> {
    const res = await request.get<ClipProjectView[] | PageResponse<ClipProjectView>, any>(
      '/api/v1/clip-projects'
    );
    return Array.isArray(res) ? res : (res?.items || []);
  },

  // 4. 创建剪辑工程草稿
  async createProject(payload: {
    title: string;
    width?: number;
    height?: number;
    fps?: number;
  }): Promise<ClipProjectView> {
    return request.post<ClipProjectView, ClipProjectView>('/api/v1/clip-projects', {
      title: payload.title || '未命名剪辑草稿',
      width: payload.width || 1080,
      height: payload.height || 1920,
      fps: payload.fps || 30
    });
  },

  // 5. 获取指定草稿的时间线详情
  async getProject(projectId: string): Promise<ClipProjectView> {
    return request.get<ClipProjectView, ClipProjectView>(`/api/v1/clip-projects/${projectId}`);
  },

  // 6. 保存/同步时间线草稿（带乐观锁版本校验）
  async updateProject(
    projectId: string,
    payload: {
      title: string;
      timeline_json: string;
      duration_ms: number;
      expected_version: number;
    }
  ): Promise<ClipProjectView> {
    return request.put<ClipProjectView, ClipProjectView>(
      `/api/v1/clip-projects/${projectId}`,
      payload
    );
  },

  // 7. 删除草稿工程（仅删除工程元数据，已导出至资料库的成片不受影响）
  async deleteProject(projectId: string): Promise<void> {
    return request.delete(`/api/v1/clip-projects/${projectId}`);
  },

  // 8. 预检云端直传意图（检查配额并获取华为云 OBS 预签名 PUT 链接）
  async requestUploadIntent(payload: {
    file_name: string;
    byte_size: number;
    mime_type: string;
    sha256: string;
    purpose: 'source_video' | 'clip_export';
  }): Promise<{ asset_id: string; upload_url: string }> {
    return request.post('/api/v1/assets/upload-intent', payload);
  },

  // 9. OBS 直传完成后回执通知
  async completeUpload(assetId: string): Promise<LibraryAssetView> {
    return request.post(`/api/v1/assets/${assetId}/complete`);
  }
};