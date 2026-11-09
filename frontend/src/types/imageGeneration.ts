export type ImageApiType = 'standard' | 'subscription';
export interface ImageModel { id: string; label: string; api_type?: ImageApiType }
export interface ImageApiConfig {
  id: string; display_name: string; model: string; key_hint: string; account_label: string;
  linked_video_api_config_id: string | null; revision: number; created_at: string;
}
export interface ImageOptions {
  models: ImageModel[]; aspect_ratios: string[];
  platform: { id: string; display_name: string; available: boolean; reason: string; model: string; account_label: string; linked_video_api_config_id: string | null };
  simulation: boolean; notice: string;
  vision: { available: boolean; reason: string }; max_reference_images: number;
}
export interface ImageReference { asset_id: string; content_url: string; original_name: string }
export interface ImageReferenceUpload { id: string; content_url: string; original_name: string; width: number; height: number }
export interface ImageJob {
  id: string; conversation_id: string; api_config_id: string; prompt: string; aspect_ratio: string;
  model: string; channel_label: string; account_label: string; linked_video_api_config_id: string | null;
  config_revision: number; status: 'queued' | 'generating' | 'saving' | 'succeeded' | 'failed' | 'unknown' | 'unknown_acknowledged' | 'storage_failed' | 'cancelled';
  asset_id: string | null; content_url: string | null; download_url: string | null;
  error_message: string | null; created_at: string; updated_at: string; simulation: boolean;
  reference_images?: ImageReference[]; parent_job_id?: string | null; watermark?: boolean;
}
export interface ImageSubmission {
  conversation_id: string; api_config_id: string; prompt: string; aspect_ratio: string; source_node_id?: string;
  reference_asset_ids?: string[]; parent_job_id?: string | null; watermark?: boolean;
}
export interface ImageDraft {
  prompt: string; aspect_ratio: string; api_config_id: string; source_node_id?: string;
  reference_images: ImageReference[]; parent_job_id: string | null; watermark: boolean;
  source_entry?: { node_id: string; asset_id: string };
  pending?: { key: string; body: ImageSubmission };
}
