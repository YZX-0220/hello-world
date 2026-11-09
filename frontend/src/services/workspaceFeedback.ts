import type { FlowNode } from '../types/canvas.ts';
export const portraitFailureMessage = '含人像图片来源必须是与视频AI模型同属的图片AI模型，请使用AI素材图片生成。';
export function collaborationReferenceIds(nodes: FlowNode[], pinned: string[], selected: string[], targetId?: string): string[] {
  const selectedImages = selected.filter(id => nodes.some(node => node.id === id && node.type === 'image'));
  return [...new Set([...pinned, ...selectedImages])].filter(id => id !== targetId && nodes.some(node => node.id === id));
}
export function portraitFailureGate() {
  const seen = new Set<string>();
  return (currentConversation: string, conversation: string, key: string, code?: string): boolean => {
    if (!conversation || conversation !== currentConversation || code !== 'VIDEO_PORTRAIT_REJECTED') return false;
    const scopedKey = JSON.stringify([conversation, key]);
    if (seen.has(scopedKey)) return false;
    seen.add(scopedKey); return true;
  };
}
