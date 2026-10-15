import type { CanvasDocument, GenerationSource, GenerationTarget } from '../types/canvas.ts';
import { same } from './canvasState.ts';

export function generationSources(document: CanvasDocument, nodeIds: string[]): GenerationSource[] {
  const ids = new Set(nodeIds);
  for (const connection of document.connections) {
    for (const [from, to] of [[connection.from, connection.to], [connection.to, connection.from]]) {
      if (from && to && ids.has(from)) {
        const image = document.nodes.find(n => n.id === to && n.type === 'image');
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

export function generationContextMatches(document: CanvasDocument, version: number, selectedIds?: string[], targetFingerprint?: string) {
  const ids = document.generation_source_ids || [];
  return ids.length > 0 && document.generation_spec_version === version
    && !!document.generation_target?.fingerprint
    && document.generation_target.api_config_id === document.selected_api_config_id
    && (!targetFingerprint || document.generation_target.fingerprint === targetFingerprint)
    && ids.every(id => document.nodes.some(n => n.id === id))
    && (!selectedIds || same([...new Set(selectedIds)].sort(), [...ids].sort()))
    && same(document.generation_requested_settings, { duration_seconds: document.video_duration_seconds, resolution: document.video_resolution })
    && same(document.generation_input, { mode: document.video_mode, input_roles: document.video_input_roles })
    && same(generationSources(document, ids), document.generation_snapshot);
}

export function generationMatches(document: CanvasDocument, version: number, selectedIds?: string[], targetFingerprint?: string) {
  return document.generation_review?.status === 'ready' && !!document.generation_review.fingerprint
    && generationContextMatches(document, version, selectedIds, targetFingerprint);
}

export function savedVideoReview(document: CanvasDocument, version: number) {
  const review = document.generation_review;
  return review?.spec_version === version && typeof review.content === 'string' && review.content.trim()
    ? { kind: review.status === 'blocked' ? 'blocked' as const : 'success' as const, content: review.content } : undefined;
}

export function videoGenerationBlockReason(document: CanvasDocument, version: number, selectedIds: string[], state: {
  compiledPrompt: boolean; preparing: boolean; submitting: boolean; collaborating: boolean;
  confirming: boolean; channel: string; saveStatus: string;
  targetFingerprint?: string; targetLoading?: boolean; targetError?: string;
  reviewError?: boolean;
  target?: GenerationTarget | null;
}) {
  if (state.submitting) return '视频任务正在提交，请稍候。';
  if (state.preparing) return 'AI 正在整理最终方案，完成后即可生成。';
  if (state.reviewError) return '本次审理未完成，请重新审理后生成。';
  if (state.collaborating || state.confirming) return '请等待 AI 协作或写入完成，再生成视频。';
  if (state.targetLoading) return '正在核对当前通道的模型能力…';
  if (state.targetError) return state.targetError;
  if (!selectedIds.length) return '请先选择需要生成视频的文本小框。';
  const settingsReason = videoSettingsBlockReason(document, state.target);
  if (settingsReason) return settingsReason;
  if (document.generation_review?.status === 'blocked') return '当前方案需要调整，请查看审理区的具体操作说明，调整后重新审理。';
  if (!state.compiledPrompt || !document.generation_source_ids.length) return '请先点击“AI审理方案”，得到可直接生成的最终方案。';
  if (!generationMatches(document, version, selectedIds, state.targetFingerprint)) return '小框、素材、模型、模式或生成参数已变化，请重新点击“AI审理方案”。';
  if (!state.channel) return '请选择视频生成通道。';
  if (state.saveStatus === 'conflict' || state.saveStatus === 'error') return '画布尚未同步，请先处理保存提示，再生成视频。';
  return '';
}

export function videoSettingsBlockReason(document: CanvasDocument, target?: GenerationTarget | null) {
  if (!Number.isInteger(document.video_duration_seconds) || !document.video_duration_seconds
    || document.video_duration_seconds < 1 || document.video_duration_seconds > 15) return '请填写视频时长（1–15 秒的整数）。';
  if (!['480p', '720p', '1080p'].includes(document.video_resolution)) return '请选择视频清晰度。';
  if (target?.profile?.image_constraints) {
    const durations = videoDurationChoices(target);
    if (!durations.includes(document.video_duration_seconds)) return '请手动选择当前模型支持的视频时长（4–15 秒的整数）。';
    if (!target.profile.resolutions.includes(document.video_resolution)) return '请选择当前模型支持的视频清晰度。';
  }
  return '';
}

export function videoDurationChoices(target?: GenerationTarget | null): number[] {
  return (target?.profile?.duration?.allowed_values || []).filter(value => value >= 1 && value <= 15);
}
