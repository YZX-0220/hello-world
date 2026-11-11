import type { FlowNode } from '../types/canvas.ts';
import type { ImageApiType, ImageDraft, ImageJob, ImageModel, ImageReference, ImageSubmission } from '../types/imageGeneration.ts';

export const imageJobActive = (job: ImageJob) => ['queued', 'generating', 'saving'].includes(job.status);
export const imageJobBlocksGeneration = (job: ImageJob) => imageJobActive(job) || job.status === 'unknown';
export const imageJobLabels: Record<ImageJob['status'], string> = {
  queued: '等待生成', generating: '正在生成', saving: '正在保存素材', succeeded: '已完成',
  failed: '生成失败', unknown: '结果待确认', unknown_acknowledged: '已结束等待 · 结果待确认', storage_failed: '生成成功 · 素材保存失败', cancelled: '已取消',
};
export const imageDraftKey = (account: string, conversation: string) => `hw:image-draft:v1:${encodeURIComponent(account)}:${encodeURIComponent(conversation)}`;
export function readImageDraft(raw: string | null): ImageDraft {
  const empty: ImageDraft = { prompt: '', aspect_ratio: '1:1', api_config_id: 'platform', reference_images: [], parent_job_id: null, watermark: false };
  try {
    const value = JSON.parse(raw || 'null');
    if (!value || typeof value.prompt !== 'string') return empty;
    const result: ImageDraft = { prompt: value.prompt, aspect_ratio: typeof value.aspect_ratio === 'string' ? value.aspect_ratio : '1:1',
      api_config_id: typeof value.api_config_id === 'string' ? value.api_config_id : 'platform',
      reference_images: sanitizeImageReferences(value.reference_images), parent_job_id: typeof value.parent_job_id === 'string' ? value.parent_job_id : null,
      watermark: value.watermark === true };
    if (typeof value.source_node_id === 'string') result.source_node_id = value.source_node_id;
    if (typeof value.source_entry?.node_id === 'string' && typeof value.source_entry?.asset_id === 'string') {
      result.source_entry = { node_id: value.source_entry.node_id, asset_id: value.source_entry.asset_id };
    }
    const pending = value.pending;
    if (typeof pending?.key === 'string' && typeof pending.body?.conversation_id === 'string'
      && typeof pending.body?.api_config_id === 'string' && typeof pending.body?.prompt === 'string' && typeof pending.body?.aspect_ratio === 'string') {
      result.pending = { key: pending.key, body: { conversation_id: pending.body.conversation_id,
        api_config_id: pending.body.api_config_id, prompt: pending.body.prompt, aspect_ratio: pending.body.aspect_ratio,
        ...(typeof pending.body.source_node_id === 'string' ? { source_node_id: pending.body.source_node_id } : {}),
        // Old pending requests must replay without newly added defaults changing their fingerprint.
        ...(Array.isArray(pending.body.reference_asset_ids) ? { reference_asset_ids: pending.body.reference_asset_ids.filter((id: unknown) => typeof id === 'string') } : {}),
        ...(typeof pending.body.parent_job_id === 'string' || pending.body.parent_job_id === null ? { parent_job_id: pending.body.parent_job_id } : {}),
        ...(typeof pending.body.watermark === 'boolean' ? { watermark: pending.body.watermark } : {}) } };
    }
    return result;
  } catch { return empty; }
}
export function sanitizeImageReferences(value: unknown, limit = 4): ImageReference[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.filter(item => item && typeof item.asset_id === 'string' && typeof item.content_url === 'string' && !seen.has(item.asset_id) && seen.add(item.asset_id))
    .slice(0, limit).map(item => ({ asset_id: item.asset_id, content_url: item.content_url, original_name: typeof item.original_name === 'string' ? item.original_name : '参考图' }));
}
export function imageSubmission(draft: ImageDraft, conversation: string): ImageSubmission {
  return { conversation_id: conversation, api_config_id: draft.api_config_id, prompt: draft.prompt.trim(), aspect_ratio: draft.aspect_ratio,
    reference_asset_ids: sanitizeImageReferences(draft.reference_images).map(image => image.asset_id), parent_job_id: draft.parent_job_id, watermark: false,
    ...(draft.source_node_id ? { source_node_id: draft.source_node_id } : {}) };
}
/** Build a suggestion request without writing the fallback instruction into the user's draft. */
export function imageSuggestionRequest(draft: ImageDraft, conversation: string): ImageSubmission | null {
  const body = imageSubmission(draft, conversation);
  if (!body.prompt && !body.reference_asset_ids?.length && !body.parent_job_id) return null;
  return { ...body, prompt: body.prompt || '请观察参考图片，给出保留主要内容、构图与风格的生图描述，并说明可改进之处。' };
}
export function imageEditDraft(current: ImageDraft, job: ImageJob): ImageDraft | null {
  if (current.pending || job.status !== 'succeeded' || !job.asset_id || !job.content_url) return null;
  return { ...current, prompt: '', aspect_ratio: job.aspect_ratio, parent_job_id: job.id, source_node_id: undefined,
    reference_images: [{ asset_id: job.asset_id, content_url: job.content_url, original_name: `修改原图 · ${job.prompt.slice(0, 24)}` }] };
}
export function imageTextOnlyDraft(current: ImageDraft): ImageDraft {
  if (current.pending) return current;
  return { ...current, reference_images: [], parent_job_id: null, source_node_id: undefined };
}
export function imageSourceParent(node: FlowNode, jobs: ImageJob[]): string | null {
  return jobs.find(job => job.id === node.job_id && job.asset_id === node.asset_id && job.status === 'succeeded')?.id || null;
}
export function imageSourceDraft(current: ImageDraft, node: FlowNode | undefined, jobs: ImageJob[], force = false): ImageDraft {
  if (current.pending || node?.type !== 'image' || !node.asset_id) return current;
  if (!force && current.source_entry?.node_id === node.id && current.source_entry.asset_id === node.asset_id) return current;
  return { ...current, source_node_id: node.id, source_entry: { node_id: node.id, asset_id: node.asset_id }, parent_job_id: imageSourceParent(node, jobs),
    reference_images: [{ asset_id: node.asset_id, content_url: `/api/v1/assets/${encodeURIComponent(node.asset_id)}/content?thumbnail=raw`, original_name: node.title || '画布参考图' }] };
}
export function imageAlreadyInserted(nodes: FlowNode[], job: ImageJob) {
  return nodes.some(node => node.type === 'image' && (node.job_id === job.id || (!!job.asset_id && node.asset_id === job.asset_id)));
}
/** Match the existing fixed canvas cards (248px wide; 300/280/240px tall). */
export function imageInsertionPoint(nodes: FlowNode[], source?: FlowNode): { x: number; y: number } {
  const width = 248, gap = 72, imageHeight = 280;
  const height = (node: FlowNode) => node.type === 'text' ? 300 : node.type === 'image' ? 280 : 240;
  const y = source?.y ?? (nodes.length ? Math.min(...nodes.map(node => node.y)) : 200);
  let x = source ? source.x + width + gap
    : nodes.length ? Math.max(...nodes.map(node => node.x + width)) + gap : 180;
  // Keep a source-relative insertion near its source, skipping every occupied card on this row.
  for (;;) {
    const collisions = nodes.filter(node => x < node.x + width + gap && x + width + gap > node.x
      && y < node.y + height(node) + gap && y + imageHeight + gap > node.y);
    if (!collisions.length) return { x, y };
    x = Math.max(...collisions.map(node => node.x + width + gap));
  }
}
export function createImageNode(nodes: FlowNode[], job: ImageJob, id: string, source?: FlowNode): FlowNode | null {
  if (job.status !== 'succeeded' || !job.asset_id || !job.content_url || imageAlreadyInserted(nodes, job)) return null;
  return { id, type: 'image', title: `${job.simulation ? '示例图片' : 'AI 生图'} · ${job.prompt.slice(0, 18)}`,
    ...imageInsertionPoint(nodes, source), content: `生图描述（用户提示词，并非看图结论）：\n${job.prompt}`,
    url: job.content_url, asset_id: job.asset_id, job_id: job.id };
}

export function imageModelApiType(models: ImageModel[], id: string): ImageApiType {
  return models.find(model => model.id === id)?.api_type || 'subscription';
}
export function imageModelsForType(models: ImageModel[], type: ImageApiType): ImageModel[] {
  return models.filter(model => (model.api_type || 'subscription') === type);
}
export function imageModelLabel(models: ImageModel[], id: string): string {
  const model = models.find(model => model.id === id);
  if (model) return model.label;
  if (/seedream.*pro/i.test(id)) return 'Seedream 5.0 Pro';
  if (/seedream.*flash/i.test(id)) return 'Seedream 5.0 Flash';
  return id ? 'Seedream 图片模型' : '';
}

export function imageDisplayModel(models: ImageModel[], id: string, channel: string): string {
  return channel === 'platform' ? '平台默认模型' : imageModelLabel(models, id);
}
