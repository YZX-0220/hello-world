import type { CanvasDocument, GenerationSource } from '../types/canvas.ts';
import { same } from './canvasState.ts';

export function generationSources(document: CanvasDocument, nodeIds: string[]): GenerationSource[] {
  const ids = new Set(nodeIds);
  for (const connection of document.connections) {
    for (const [from, to] of [[connection.from, connection.to], [connection.to, connection.from]]) {
      if (from && to && ids.has(from)) {
        const image = document.nodes.find(n => n.id === to && n.type === 'image' && n.asset_id);
        if (image) ids.add(image.id);
      }
    }
  }
  return document.nodes.filter(n => ids.has(n.id)).map(n => ({
    id: n.id, type: n.type, title: n.title, content: n.content ?? null,
    asset_id: n.asset_id ?? null,
    ...(n.last_ai?.brief && n.content === n.last_ai.after ? {
      confirmed_brief: n.last_ai.brief, suggested_prompt: n.last_ai.suggested_prompt ?? null,
    } : {}),
  }));
}

export function generationMatches(document: CanvasDocument, version: number, selectedIds?: string[]) {
  const ids = document.generation_source_ids || [];
  return ids.length > 0 && document.generation_spec_version === version
    && ids.every(id => document.nodes.some(n => n.id === id))
    && (!selectedIds || same([...new Set(selectedIds)].sort(), [...ids].sort()))
    && same(document.generation_settings, { duration_seconds: document.video_duration_seconds, resolution: document.video_resolution })
    && same(generationSources(document, ids), document.generation_snapshot);
}

export function savedVideoReview(document: CanvasDocument, version: number) {
  const review = document.generation_review;
  return review?.spec_version === version && typeof review.content === 'string' && review.content.trim()
    ? { kind: 'success' as const, content: review.content } : undefined;
}

export function videoGenerationBlockReason(document: CanvasDocument, version: number, selectedIds: string[], state: {
  compiledPrompt: boolean; preparing: boolean; submitting: boolean; collaborating: boolean;
  confirming: boolean; channel: string; saveStatus: string;
}) {
  if (state.submitting) return '视频任务正在提交，请稍候。';
  if (state.preparing) return 'AI 正在整理最终方案，完成后即可生成。';
  if (state.collaborating || state.confirming) return '请等待 AI 协作或写入完成，再生成视频。';
  if (!selectedIds.length) return '请先选择需要生成视频的文本小框。';
  const settingsReason = videoSettingsBlockReason(document);
  if (settingsReason) return settingsReason;
  if (!state.compiledPrompt || !document.generation_source_ids.length) return '请先点击“AI审理方案”，得到可直接生成的最终方案。';
  if (!generationMatches(document, version, selectedIds)) return '小框内容、素材、选择或生成参数已变化，请重新点击“AI审理方案”。';
  if (!state.channel) return '请选择视频生成通道。';
  if (state.saveStatus === 'conflict' || state.saveStatus === 'error') return '画布尚未同步，请先处理保存提示，再生成视频。';
  return '';
}

export function videoSettingsBlockReason(document: CanvasDocument) {
  if (!Number.isInteger(document.video_duration_seconds) || !document.video_duration_seconds
    || document.video_duration_seconds < 1 || document.video_duration_seconds > 15) return '请填写视频时长（1–15 秒的整数）。';
  if (!['480p', '720p', '1080p'].includes(document.video_resolution)) return '请选择视频清晰度。';
  return '';
}
