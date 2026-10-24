import type { CanvasDocument, FlowNode } from '../types/canvas.ts';

export function createCanvas(conversationId: string, content = ''): CanvasDocument {
  return {
    schema_version: 1,
    nodes: [
      { id: `text_${conversationId}`, type: 'text', title: '视频脚本', x: 160, y: 160, content },
      { id: `image_${conversationId}`, type: 'image', title: '参考图', x: 520, y: 160, url: '' },
    ],
    connections: [], pan: { x: 100, y: 100 }, zoom: 1,
    agent_draft: '', ai_target_node_id: '', referenced_node_ids: [], selected_api_config_id: 'platform',
    generation_node_id: '', generation_source_ids: [], generation_snapshot: [],
    generation_spec_version: 0, generation_review: null, dismissed_job_ids: [],
    video_duration_seconds: null, video_resolution: '', generation_settings: null,
    generation_requested_settings: null, generation_target: null, generation_input: null,
    video_mode: 'auto', video_input_roles: {},
  };
}

export function copy<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }
export function same(a: unknown, b: unknown): boolean {
  const stable = (value: any): any => {
    if (Array.isArray(value)) return value.map(stable);
    if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]));
    return value;
  };
  return JSON.stringify(stable(a)) === JSON.stringify(stable(b));
}

/** Canonical persisted state; transient editor focus/rename flags are excluded. */
export function normalizeCanvas(value: unknown): CanvasDocument {
  if (!value || typeof value !== 'object') throw new Error('画布数据格式无效');
  const raw = value as Partial<CanvasDocument>;
  if (!Array.isArray(raw.nodes) || !Array.isArray(raw.connections)) throw new Error('画布节点或连线数据缺失');
  const result = { ...createCanvas(''), ...copy(raw), schema_version: 1 } as CanvasDocument;
  const ids = new Set<string>();
  result.nodes = result.nodes.map(node => {
    if (!node || !node.id || ids.has(node.id) || !['text', 'image', 'video'].includes(node.type)
      || !Number.isFinite(node.x) || !Number.isFinite(node.y)) throw new Error('画布包含无效或重复节点');
    ids.add(node.id);
    const clean = { ...node };
    delete clean.isRenaming;
    return clean;
  });
  result.connections = result.connections.filter(c => ids.has(c.from) && ids.has(c.to) && c.from !== c.to);
  if (!Number.isFinite(result.pan?.x) || !Number.isFinite(result.pan?.y)) result.pan = { x: 100, y: 100 };
  if (!Number.isFinite(result.zoom) || result.zoom < 0.4 || result.zoom > 2.2) result.zoom = 1;
  result.ai_target_node_id = ids.has(result.ai_target_node_id) ? result.ai_target_node_id : '';
  result.referenced_node_ids = (result.referenced_node_ids || []).filter(id => ids.has(id));
  return result;
}

/** Merge independent edits without letting an older server response erase newer local edits. */
export function mergeCanvas(base: CanvasDocument, local: CanvasDocument, remote: CanvasDocument) {
  const conflicts: string[] = [];
  const mergeValue = (b: any, l: any, r: any, path: string): any => {
    if (same(l, b)) return copyOptional(r);
    if (same(r, b) || same(l, r)) return copyOptional(l);
    if (isObject(l) && isObject(r) && (b === undefined || isObject(b))) {
      const out: Record<string, unknown> = {};
      for (const key of new Set([...Object.keys(b || {}), ...Object.keys(l), ...Object.keys(r)])) {
        const value = mergeValue(b?.[key], l[key], r[key], `${path}.${key}`);
        if (value !== undefined) out[key] = value;
      }
      return out;
    }
    conflicts.push(path);
    return copyOptional(l);
  };
  const mergeList = (key: 'nodes' | 'connections') => {
    const b = new Map(base[key].map(item => [item.id, item]));
    const l = new Map(local[key].map(item => [item.id, item]));
    const r = new Map(remote[key].map(item => [item.id, item]));
    const merged: any[] = [];
    for (const id of new Set([...l.keys(), ...r.keys()])) {
      // An explicit local deletion wins over an AI result for that node.
      if (b.has(id) && !l.has(id)) continue;
      const beforeConflicts = conflicts.length;
      const item = mergeValue(b.get(id), l.get(id), r.get(id), `${key}.${id}`);
      if (!item) continue;
      if (key === 'nodes') {
        const server = r.get(id) as FlowNode | undefined;
        const previous = b.get(id) as FlowNode | undefined;
        const mine = l.get(id) as FlowNode | undefined;
        if (server?.last_ai && server.last_ai.message_id !== previous?.last_ai?.message_id
          && mine?.content !== previous?.content && mine?.content !== server.content) {
          item.content = mine?.content;
          item.pending_ai = {
            content: server.content || '', message_id: server.last_ai.message_id, apply_mode: 'replace',
            original: server.last_ai.before, brief: server.last_ai.brief,
            suggested_prompt: server.last_ai.suggested_prompt,
          };
          const index = conflicts.indexOf(`nodes.${id}.content`, beforeConflicts);
          if (index >= 0) conflicts.splice(index, 1);
        }
      }
      merged.push(item);
    }
    return merged;
  };
  const result = { ...local } as CanvasDocument;
  for (const key of Object.keys(local) as (keyof CanvasDocument)[]) {
    if (key !== 'nodes' && key !== 'connections') (result as any)[key] = mergeValue(base[key], local[key], remote[key], key);
  }
  result.nodes = mergeList('nodes');
  result.connections = mergeList('connections');
  return { document: normalizeCanvas(result), conflicts };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}
function copyOptional(value: any) { return value === undefined ? undefined : copy(value); }
