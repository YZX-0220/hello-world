// 用户视图 (UserView)
export interface UserView {
  id: string;
  email: string;
  email_verified_at: string;
  status: 'active' | 'disabled';
  created_at: string;
}

// 消息角色与状态
export type MessageRole = 'user' | 'assistant' | 'tool' | 'system';
export type MessageStatus = 'pending' | 'running' | 'completed' | 'succeeded' | 'failed';

// 消息视图 (MessageView)
export interface MessageView {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  reply_to_message_id: string | null;
  client_request_id: string | null;
  model_name: string | null;
  citations: Array<{
    title: string;
    url: string;
    snippet: string;
    published_at: string | null;
    retrieved_at: string;
  }>;
  error_code: string | null;
  created_at: string;
}

// 结构化视频方案 (VideoBrief) - 国际传播核心特化
export interface VideoBrief {
  objective: string | null;        // 视频目标
  audience: string | null;         // 目标受众（如青年游客、国际受众）
  language: string | null;         // 内容语言（如 zh-CN, en-US）
  duration_seconds: number | null; // 时长
  aspect_ratio: string | null;     // 画幅 16:9, 9:16 等
  mode: string | null;             // text_to_video, first_last_frame_to_video 等
  visual_style: string | null;     // 视觉风格
  subject: string | null;          // 主体
  scene: string | null;            // 场景描述
  camera: string | null;           // 镜头设计/运镜
  motion: string | null;           // 动作设计
  lighting: string | null;         // 光线设计
  narration: string | null;        // 旁白
  negative_prompt: string | null;  // 负面提示
  first_frame_asset_id: string | null;
  last_frame_asset_id: string | null;
  reference_asset_ids: string[];
  source_video_asset_id: string | null;
  audio_asset_id: string | null;
}

// 视频项目视图 (VideoProjectView)
export interface VideoProjectView {
  id: string;
  conversation_id: string;
  current_spec: VideoBrief;
  current_spec_version: number;
  suggested_prompt: string | null;
  confirmed_spec_version: number | null;
  confirmed_at: string | null;
  is_current_version_confirmed: boolean;
  created_at: string;
  updated_at: string;
}

// 视频任务视图 (VideoJobView)
export interface VideoJobView {
  id: string;
  conversation_id: string;
  project_id: string;
  project_version: number;
  api_config_id: string;
  api_config_revision: number;
  previous_job_id: string | null;
  protocol_code: string;
  remote_model_id: string;
  mode: string;
  status: 'created' | 'submitting' | 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  progress: number | null;
  generation_options: Record<string, any>;
  download_status: 'not_started' | 'pending' | 'downloading' | 'stored' | 'failed';
  result_asset_id: string | null;
  error: { code: string; message: string; retryable: boolean } | null;
  poll_after_seconds: number | null;
  submitted_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}
// 历史对话视图 (ConversationView)
export interface ConversationView {
  id: string;
  title: string;
  status: 'active' | 'archived' | 'deleted';
  last_message_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

// 视频 API 配置视图 (VideoApiConfigView)
export interface VideoApiConfigView {
  id: string;
  display_name: string;
  source_type: 'official' | 'relay';
  protocol_code: string;
  protocol_label: string;
  template_code: string | null;
  template_label: string | null;
  base_url: string;
  remote_model_id: string;
  current_revision: number;
  options: Record<string, any>;
  capability_profile_code: string | null;
  capabilities: string[];
  capability_source: 'registry' | 'user_declared' | 'runtime_confirmed';
  verification_status: 'verified' | 'invalid' | 'unverified';
  key_hints: Record<string, string>;
  status: 'active' | 'disabled' | 'deleted';
  last_verified_at: string | null;
  last_error_code: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}