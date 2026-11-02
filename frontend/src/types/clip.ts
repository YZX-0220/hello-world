// 轨道类型与片段类型严格隔离
export type TrackType = 'text' | 'video' | 'audio';

export interface BaseClip {
  id: string;
  track_id: string;
  start_ms: number;       // 在时间轴上的起始时间戳（毫秒）
  duration_ms: number;    // 片段播放时长（毫秒）
  in_point_ms: number;    // 素材裁剪入点（毫秒）
  out_point_ms: number;   // 素材裁剪出点（毫秒）
}

// 文本片段
export interface TextClip extends BaseClip {
  type: 'text';
  text: string;
  font_size: number;
  color: string;
  background_color?: string;
  align: 'left' | 'center' | 'right';
  opacity: number;
}

// 视频片段（包含静态图片拖拽转入的静态视频帧片段）
export interface VideoClip extends BaseClip {
  type: 'video';
  asset_id: string;
  sha256: string;
  source_url?: string;
  file_name: string;
  is_image_source?: boolean;
  playback_rate: number;
  volume: number;
  width?: number;
  height?: number;
  opacity?: number;
  // 👇 补齐以下 3 个几何变换属性
  scale?: number;
  position_x?: number;
  position_y?: number;
}

// 音频片段
export interface AudioClip extends BaseClip {
  type: 'audio';
  asset_id: string;
  sha256: string;
  source_url?: string;
  file_name: string;
  volume: number;            // 音量（0% ~ 200%，默认 1.0）
  fade_in_ms: number;        // 淡入时长（毫秒）
  fade_out_ms: number;       // 淡出时长（毫秒）
}

export type TimelineClip = TextClip | VideoClip | AudioClip;

// 轨道定义（越靠前的轨道渲染层级越高）
export interface TimelineTrack {
  id: string;
  type: TrackType;
  name: string;
  muted: boolean;     // 静音
  hidden: boolean;    // 隐藏画面
  locked: boolean;    // 锁定禁止编辑
  clips: TimelineClip[];
}

// 时间线完整数据（存储于后端 timeline_json）
export interface TimelineDocument {
  width: number;
  height: number;
  fps: number;
  duration_ms: number;
  tracks: TimelineTrack[];
  markers: Array<{ id: string; time_ms: number; label: string; color?: string }>;
}

// 后端持久化工程对象接口
export interface ClipProjectView {
  id: string;
  user_id: string;
  title: string;
  description: string;
  timeline_json: string;
  duration_ms: number;
  fps: number;
  width: number;
  height: number;
  cover_asset_id: string | null;
  exported_asset_id: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

// 用户云端存储配额接口视图
export interface StorageQuotaView {
  quota_bytes: number;
  used_bytes: number;
  available_bytes: number;
  quota_gb: number;
  usage_percent: number;
  asset_count: number;
}

// 资料库素材项视图
export interface LibraryAssetView {
  id: string;
  file_name: string;
  size_bytes: number;
  mime_type: string;
  kind: 'video' | 'image' | 'audio';
  purpose: 'source_video' | 'reference' | 'ai_generated' | 'clip_export';
  sha256: string;
  duration_ms?: number;
  width?: number;
  height?: number;
  url: string;
  created_at: string;
}