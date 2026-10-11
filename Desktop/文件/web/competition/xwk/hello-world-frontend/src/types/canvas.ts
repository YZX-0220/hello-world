import type { VideoBrief } from './api';

export interface FlowNode {
  id: string;
  type: 'text' | 'image' | 'video';
  title: string;
  x: number;
  y: number;
  content?: string;
  url?: string;
  asset_id?: string;
  job_id?: string;
  isRenaming?: boolean;
  ai_running?: boolean;
  ai_request_id?: string;
  ai_started_at?: string;
  ai_error?: string;
  last_ai?: { before: string; after: string; message_id: string; brief?: VideoBrief; suggested_prompt?: string | null };
  pending_ai?: { source_model?: string; content: string; message_id: string; apply_mode: 'replace' | 'append'; original?: string; brief?: VideoBrief; suggested_prompt?: string | null };
}

export interface FlowConnection { id: string; from: string; to: string }

export interface CanvasDocument {
  schema_version: 1;
  nodes: FlowNode[];
  connections: FlowConnection[];
  pan: { x: number; y: number };
  zoom: number;
  agent_draft: string;
  ai_target_node_id: string;
  referenced_node_ids: string[];
  selected_api_config_id: string;
  generation_node_id: string;
  generation_source_ids: string[];
  generation_snapshot: GenerationSource[];
  generation_spec_version: number;
  generation_review: { spec_version: number; content: string } | null;
  video_duration_seconds: number | null;
  video_resolution: string;
  generation_settings: { duration_seconds: number; resolution: string } | null;
  dismissed_job_ids: string[];
}

export interface GenerationSource {
  id: string;
  type: FlowNode['type'];
  title: string;
  content: string | null;
  asset_id: string | null;
  confirmed_brief?: VideoBrief;
  suggested_prompt?: string | null;
}
