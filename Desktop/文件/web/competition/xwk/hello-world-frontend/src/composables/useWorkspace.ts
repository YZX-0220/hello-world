import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router';
import request from '../utils/request';
import type { CanvasDocument, FlowNode } from '../types/canvas';
import type { ConversationView, MessageView, UserView, VideoApiConfigView, VideoJobView, VideoProjectView } from '../types/api';
import { CanvasPersistence, type CanvasSession } from '../services/canvasPersistence';
import { createCanvas } from '../services/canvasState';
import { generationMatches, savedVideoReview, videoSettingsBlockReason } from '../services/generationState';

type Page<T> = { items: T[]; next_cursor: string | null };
type MessageResult = { user_message: MessageView | null; assistant_message: MessageView | null; project: VideoProjectView; run_status: string };

// 新增：后端返回的模型能力与模式级约束类型定义
export interface ModeConstraint {
  mode: string;
  ratio?: 'model' | 'adaptive_only' | string;
  duration?: 'model' | 'omit' | string;
  note?: string;
}

export interface VideoModelProfile {
  code: string;
  label: string;
  remote_model_id?: string; // 👈 新增：后端返回的远程模型编号（如 doubao-seedance-2-5-260628）
  modes: string[];
  aspect_ratios?: string[];
  duration?: { allowed_values?: number[] };
  resolutions?: string[];
  mode_constraints?: ModeConstraint[];
}
const MODE_LABELS: Record<string, string> = {
  text_to_video: '文生视频',
  first_frame_to_video: '首帧图生视频',
  first_last_frame_to_video: '首尾帧生视频',
  reference_image_to_video: '参考图生视频',
  video_to_video: '视频重绘',
  video_extend: '视频延长',
  audio_or_performance_to_video: '音频/表演驱动',
};

const runningStatuses = ['created', 'submitting', 'queued', 'running'];
export const newId = () => typeof crypto.randomUUID === 'function' ? crypto.randomUUID()
  : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const n = Math.random() * 16 | 0; return (c === 'x' ? n : n & 3 | 8).toString(16);
  });

export function useWorkspace() {
  const router = useRouter();
  const route = useRoute();
  const canvas = ref<CanvasDocument>(createCanvas(''));
  const currentConvId = ref('');
  const conversations = ref<ConversationView[]>([]);
  const messages = ref<MessageView[]>([]);
  const project = ref<VideoProjectView | null>(null);
  const apiConfigs = ref<VideoApiConfigView[]>([]);
  const modelProfiles = ref<Record<string, VideoModelProfile>>({});
  const loadedProtocols = new Set<string>();
  const jobs = ref<VideoJobView[]>([]);
  const loading = ref(false);
  const initialized = ref(false);
  const isCreatingConv = ref(false);
  const isSubmittingJob = ref(false);
  const isConfirming = ref(false);
  const isPreparingVideo = ref(false);
  const videoReviews = ref<Record<string, { kind: 'loading' | 'success' | 'error'; content: string }>>({});
  const videoReview = computed(() => videoReviews.value[currentConvId.value]
    || (project.value ? savedVideoReview(canvas.value, project.value.current_spec_version) : undefined));
  const isAgentDrawerOpen = ref(false);
  const notice = ref('');
  const saveState = ref({ status: 'saved', error: '', localAvailable: true, dirty: false });
  const sending = ref<string[]>([]);
  const uploading = ref<string[]>([]);
  let store: CanvasPersistence | null = null;
  let applying = false;
  let loadSequence = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let disposed = false;

  function reflect(session: CanvasSession) {
    if (session.id !== currentConvId.value) return;
    applying = true;
    if (canvas.value !== session.document) {
      canvas.value = session.document;
      session.document = canvas.value;
    }
    saveState.value = { status: session.status, error: session.error, localAvailable: session.localAvailable, dirty: session.dirty };
    if (session.error && session.status === 'saved') notice.value = session.error;
    applying = false;
  }

  watch(canvas, () => {
    if (!applying && !loading.value && currentConvId.value) store?.edit(currentConvId.value, canvas.value);
  }, { deep: true, flush: 'sync' });

  const nodes = computed({ get: () => canvas.value.nodes, set: value => { canvas.value.nodes = value; } });
  const connections = computed({ get: () => canvas.value.connections, set: value => { canvas.value.connections = value; } });
  const pan = computed(() => canvas.value.pan);
  const zoom = computed({ get: () => canvas.value.zoom, set: value => { canvas.value.zoom = value; } });
  const inputContent = computed({ get: () => canvas.value.agent_draft, set: value => { canvas.value.agent_draft = value; } });
  const referencedNodeIds = computed({ get: () => canvas.value.referenced_node_ids, set: value => { canvas.value.referenced_node_ids = value; } });
  const aiTargetNodeId = computed({ get: () => canvas.value.ai_target_node_id, set: value => { canvas.value.ai_target_node_id = value; } });
  const selectedApiConfigId = computed({ get: () => canvas.value.selected_api_config_id, set: value => { canvas.value.selected_api_config_id = value; } });
  const isAgentResponding = computed(() => sending.value.includes(currentConvId.value) || nodes.value.some(n => n.ai_running));
  const activeJob = computed(() => jobs.value.find(job => runningStatuses.includes(job.status)) || jobs.value[0] || null);
  const generationReady = computed(() => {
    return !!project.value?.compiled_prompt && generationMatches(canvas.value, project.value.current_spec_version);
  });
  const saveLabel = computed(() => {
    if (!saveState.value.localAvailable && saveState.value.dirty) return '本地草稿不可用 · 请等待云端保存';
    if (saveState.value.status === 'saved') return '已保存到云端';
    if (saveState.value.status === 'saving') return '正在保存…';
    if (saveState.value.status === 'conflict') return '画布版本冲突 · 草稿已保留';
    if (saveState.value.status === 'error') return saveState.value.localAvailable ? '云端保存失败 · 本地草稿已保留' : '保存失败 · 请重试';
    return saveState.value.localAvailable ? '本地草稿已保存 · 等待同步' : '等待云端保存';
  });

  async function listAll<T>(url: string): Promise<T[]> {
    const result: T[] = [];
    let cursor: string | null = null;
    do {
      const page: Page<T> = await request.get<Page<T>, Page<T>>(url, { params: { limit: 100, ...(cursor ? { cursor } : {}) } });
      result.push(...page.items); cursor = page.next_cursor;
    } while (cursor);
    return result;
  }

  // 新增：按协议加载后端的模型约束配置
  async function loadModelProfilesByProtocol(protocolCode: string) {
    if (!protocolCode || loadedProtocols.has(protocolCode)) return;
    try {
      const res = await request.get<VideoModelProfile[] | { items: VideoModelProfile[] }, any>(
        '/video-model-profiles',
        { params: { protocol_code: protocolCode } }
      );
      const list: VideoModelProfile[] = Array.isArray(res) ? res : (res?.items || []);
      const next = { ...modelProfiles.value };
      for (const profile of list) {
        if (profile?.code) next[profile.code] = profile;
      }
      modelProfiles.value = next;
      loadedProtocols.add(protocolCode);
    } catch (err) {
      console.warn(`加载协议 ${protocolCode} 的模型约束失败:`, err);
    }
  }

  async function ensureModelProfiles() {
    const protocols = new Set<string>(['ark_seedance_v1']);
    for (const cfg of apiConfigs.value as any[]) {
      if (cfg?.protocol_code) protocols.add(cfg.protocol_code);
    }
    await Promise.all(Array.from(protocols).map(p => loadModelProfilesByProtocol(p)));
  }

  // 新增：提交前校验真实发送参数与模型约束
  function validateBeforeSubmit(snapshot: VideoProjectView, doc?: CanvasDocument): string | null {
    const configId = selectedApiConfigId.value || 'platform';
    let targetKey = 'doubao-seedance-2-5';
    let remoteModelId = '';
    let channelDisplayName = 'Doubao Seedance 2.5';

    if (configId !== 'platform') {
      const cfg = (apiConfigs.value as any[]).find(c => c.id === configId);
      if (cfg) {
        remoteModelId = cfg.remote_model_id || '';
        targetKey = cfg.capability_profile_code || cfg.model_profile_code || remoteModelId || '';
        channelDisplayName = cfg.display_name || remoteModelId || targetKey;
      }
    }

    // 👉 核心修复：不仅按 key (code) 查，还遍历匹配 code、remote_model_id 以及前缀关系
    const profileList = Object.values(modelProfiles.value);
    const profile = modelProfiles.value[targetKey]
      || profileList.find(p =>
        p.code === targetKey
        || (p.remote_model_id && p.remote_model_id === targetKey)
        || (remoteModelId && (p.remote_model_id === remoteModelId || p.code === remoteModelId))
        || (remoteModelId && p.code && remoteModelId.startsWith(p.code))
      );

    if (!profile) return null; // 若仍未找到对应 profile，交由后端兜底校验

    const modelLabel = profile.label || channelDisplayName;
    const spec: any = snapshot.current_spec || {};
    const genSettings: any = doc?.generation_settings || {};

    // 1. 提取即将发送的真实参数
    const mode: string = spec.mode || 'text_to_video';
    const modeName = MODE_LABELS[mode] || mode;
    const aspectRatio: string | undefined = spec.aspect_ratio;
    const resolution: string | undefined = genSettings.resolution ?? doc?.video_resolution ?? spec.resolution;
    const durationSeconds: number | undefined = genSettings.duration_seconds ?? doc?.video_duration_seconds ?? spec.duration_seconds;

    // 2. 校验模型级支持的生成模式 (modes)
    if (Array.isArray(profile.modes) && profile.modes.length > 0 && !profile.modes.includes(mode)) {
      const supportedModes = profile.modes.map(m => `【${MODE_LABELS[m] || m}】`).join('、');
      return `⚠️ 当前通道【${modelLabel}】不支持「${modeName}」模式。\n你可以：① 改用该模型支持的模式（${supportedModes}）；② 或切换其他支持「${modeName}」的模型通道。`;
    }
    if (mode === 'first_frame_to_video' && !spec.first_frame_asset_id) {
      return `⚠️ 当前方案为「${modeName}」模式，但尚未绑定首帧图片素材。请先上传/指定首帧图，或改用【文生视频】模式。`;
    }
    if (mode === 'first_last_frame_to_video' && (!spec.first_frame_asset_id || !spec.last_frame_asset_id)) {
      return `⚠️ 当前方案为「${modeName}」模式，需要同时提供首帧和尾帧图片素材。请补全图片，或改用其他生成模式。`;
    }
    // 3. 匹配模式级约束 (mode_constraints)
    const modeConstraint = profile.mode_constraints?.find(c => c.mode === mode);

    // 3.1 核心校验：自适应画幅限制 (ratio == "adaptive_only")
    if (modeConstraint?.ratio === 'adaptive_only') {
      if (aspectRatio && aspectRatio !== 'adaptive') {
        const noteText = modeConstraint.note || `该模式画幅由首帧图片自动决定，不能指定具体比例。`;
        return `⚠️ 当前通道【${modelLabel}】的「${modeName}」模式：${noteText}（当前指定了 ${aspectRatio}）。\n你可以：① 去掉方案里的画幅指定（改为自适应）；② 或改用【文生视频】模式；③ 或换用支持指定画幅的模型（如 Seedance 2.0）。`;
      }
    } else if (aspectRatio && aspectRatio !== 'adaptive') {
      // 3.2 模型级画幅校验 (aspect_ratios)
      if (Array.isArray(profile.aspect_ratios) && profile.aspect_ratios.length > 0 && !profile.aspect_ratios.includes(aspectRatio)) {
        return `⚠️ 当前通道【${modelLabel}】不支持画幅比例「${aspectRatio}」。\n请将画幅修改为模型支持的比例：${profile.aspect_ratios.join('、')}，或切换其他模型。`;
      }
    }

    // 4. 模型级清晰度校验 (resolutions)
    if (resolution && Array.isArray(profile.resolutions) && profile.resolutions.length > 0 && !profile.resolutions.includes(resolution)) {
      return `⚠️ 当前通道【${modelLabel}】不支持分辨率「${resolution}」。\n请将清晰度修改为：${profile.resolutions.join(' / ')}。`;
    }

    // 5. 模型级时长校验 (duration.allowed_values)
    const durationRule = modeConstraint?.duration || 'model';
    if (durationRule === 'model' && durationSeconds !== undefined && durationSeconds !== null) {
      const allowedDurations = profile.duration?.allowed_values;
      if (Array.isArray(allowedDurations) && allowedDurations.length > 0 && !allowedDurations.includes(Number(durationSeconds))) {
        return `⚠️ 当前通道【${modelLabel}】不支持生成时长「${durationSeconds} 秒」。\n请将时长修改为模型允许的值：${allowedDurations.join('、')} 秒。`;
      }
    }

    return null;
  }

  async function loadConversations() {
    try { conversations.value = await listAll<ConversationView>('/conversations'); }
    catch (err: any) { notice.value = err.message || '项目列表加载失败，请重试'; }
  }

  async function flushCurrent(): Promise<boolean> {
    if (!store || !currentConvId.value) return true;
    const id = currentConvId.value;
    store.edit(id, canvas.value);
    const saved = await store.flush(id);
    const session = store.sessions.get(id);
    if (!saved) notice.value = session?.error ? `${session.error}；${session.localAvailable ? '草稿已保留在本机。' : '本地草稿也无法保存，请重试后再离开。'}` : '画布尚未同步';
    return saved || !!session?.localAvailable;
  }

  function stopPolling() { if (timer) clearTimeout(timer); timer = null; }

  async function switchConversation(id: string, changeUrl = true) {
    if (!store || (id === currentConvId.value && !loading.value)) return;
    const sequence = ++loadSequence;
    if (!await flushCurrent() || sequence !== loadSequence) return;
    stopPolling(); loading.value = true; isAgentDrawerOpen.value = false;
    try {
      const [remote, history, jobList] = await Promise.all([
        request.get<VideoProjectView, VideoProjectView>(`/conversations/${id}/project`),
        listAll<MessageView>(`/conversations/${id}/messages`),
        listAll<VideoJobView>(`/video-jobs?conversation_id=${encodeURIComponent(id)}`),
      ]);
      if (disposed || sequence !== loadSequence) return;
      currentConvId.value = id; project.value = remote; messages.value = history; jobs.value = jobList;
      const session = store.open(id, remote, createCanvas(id, remote.suggested_prompt || remote.current_spec.subject || ''));
      reflect(session); loading.value = false;
      for (const job of jobList) materializeJob(id, job);
      if (changeUrl) await router.replace({ path: '/workspace', query: { conversation: id } });
      schedulePolling();
    } catch (err: any) {
      if (sequence === loadSequence) notice.value = err.message || '项目加载失败；已有草稿已保留，请重试';
    } finally { if (sequence === loadSequence) loading.value = false; }
  }

  async function createNewConversation() {
    if (!store || isCreatingConv.value || loading.value) return;
    if (!await flushCurrent()) return;
    isCreatingConv.value = true;
    try {
      const result = await request.post<{ conversation: ConversationView; project: VideoProjectView }, { conversation: ConversationView; project: VideoProjectView }>(
        '/conversations', { title: `创作项目 ${new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}` });
      conversations.value.unshift(result.conversation);
      await switchConversation(result.conversation.id);
    } catch (err: any) { notice.value = err.message || '项目创建失败'; }
    finally { isCreatingConv.value = false; }
  }

  async function backToProjectSpace() {
    if (!await flushCurrent()) return;
    ++loadSequence; stopPolling(); currentConvId.value = ''; messages.value = []; project.value = null; jobs.value = [];
    isAgentDrawerOpen.value = false;
    await router.replace({ path: '/workspace' });
    await loadConversations();
  }

  async function deleteConversation(id: string) {
    try {
      const session = store?.sessions.get(id);
      if (session?.pending) await session.pending;
      await request.delete(`/conversations/${id}`);
      store?.remove(id); conversations.value = conversations.value.filter(c => c.id !== id);
      if (currentConvId.value === id) { currentConvId.value = ''; stopPolling(); await router.replace('/workspace'); }
    } catch (err: any) { notice.value = err.message || '删除项目失败'; }
  }

  async function sendMessage(target: FlowNode | undefined, referenceIds: string[]) {
    const id = currentConvId.value;
    const instruction = inputContent.value.trim();
    if (!store || !id || !instruction || isAgentResponding.value || isPreparingVideo.value || isConfirming.value || loading.value) return;
    if (!target || target.type !== 'text') {
      target = { id: newId(), type: 'text', title: 'AI 协作文本', x: 160 + nodes.value.length * 40, y: 160 + nodes.value.length * 32, content: '' };
      nodes.value.push(target);
    }
    const targetId = target.id;
    aiTargetNodeId.value = targetId;
    const requestId = newId();
    const optimisticId = 'sending-' + requestId;
    sending.value = [...sending.value, id];
    try {
      if (!await store.flush(id)) { notice.value = '请先完成画布同步，再发送 AI 协作；输入内容已保留。'; return; }
      inputContent.value = '';
      messages.value.push({
        id: optimisticId, conversation_id: id, role: 'user', content: instruction, status: 'pending',
        reply_to_message_id: null, client_request_id: requestId, model_name: null,
        citations: [], error_code: null, created_at: new Date().toISOString(),
      });
      const response = await request.post<MessageResult, MessageResult>(`/conversations/${id}/messages`, {
        content: instruction, client_request_id: requestId, web_search_enabled: true,
        canvas_collaboration: { target_node_id: targetId, reference_node_ids: referenceIds, apply_mode: 'replace' },
      });
      store.acceptRemote(id, response.project);
      void store.flush(id);
      if (currentConvId.value === id && !disposed) {
        project.value = response.project;
        messages.value = messages.value.filter(message => message.id !== optimisticId);
        for (const message of [response.user_message, response.assistant_message]) {
          if (message && !messages.value.some(m => m.id === message.id)) messages.value.push(message);
        }
        notice.value = nodes.value.find(n => n.id === targetId)?.pending_ai?.message_id === response.assistant_message?.id
          ? 'AI 已准备待写入正文。核对后点击“确定并写入小框”，当前文字会保留到你采用为止。'
          : 'AI 已回复。讨论不会改动小框，已有待写入正文仍保留。';
      }
    } catch (err: any) {
      const session = store.sessions.get(id);
      if (session && !session.document.agent_draft) {
        session.document.agent_draft = instruction; store.edit(id, session.document);
      }
      if (currentConvId.value === id) {
        notice.value = err.message || 'AI 协作失败；原文和输入已保留';
        await refreshProject(id);
      }
    } finally {
      if (currentConvId.value === id) messages.value = messages.value.filter(message => message.id !== optimisticId);
      sending.value = sending.value.filter(value => value !== id);
      if (currentConvId.value === id) schedulePolling();
    }
  }

  async function refreshProject(id: string, reportError = true) {
    if (!store) return;
    try {
      const remote = await request.get<VideoProjectView, VideoProjectView>(`/conversations/${id}/project`, { timeout: 8000 });
      store.acceptRemote(id, remote);
      if (currentConvId.value === id && !disposed) project.value = remote;
      if (!store.sessions.get(id)?.conflicts.length) void store.flush(id);
    } catch (err: any) { if (reportError && currentConvId.value === id) notice.value = err.message || '同步暂时失败，草稿已保留'; }
  }

  async function uploadImage(event: Event, node: FlowNode) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0]; const id = currentConvId.value;
    if (!file || !store || !id) return;
    input.value = '';
    if (file.size > 10 * 1024 * 1024) { notice.value = '图片不能超过 10 MB'; return; }
    const nodeId = node.id;
    uploading.value = [...uploading.value, nodeId];
    try {
      const form = new FormData(); form.append('file', file); form.append('purpose', 'reference'); form.append('conversation_id', id);
      const asset = await request.post<{ id: string; content_url: string }, { id: string; content_url: string }>(
        '/assets', form, { headers: { 'Content-Type': undefined } });
      const session = store.sessions.get(id);
      const target = session?.document.nodes.find(n => n.id === nodeId);
      if (target && session) {
        target.url = asset.content_url; target.asset_id = asset.id;
        store.edit(id, session.document); await store.flush(id);
      }
    } catch (err: any) { notice.value = err.message || '图片上传失败，原图已保留'; }
    finally { uploading.value = uploading.value.filter(value => value !== nodeId); }
  }

  async function confirmSpec() {
    const id = currentConvId.value;
    const target = nodes.value.find(n => n.id === aiTargetNodeId.value);
    if (!target?.pending_ai || !project.value || !store) { notice.value = '请先在目标小框进行 AI 协作，收到回复后再确定并写入小框。'; return; }
    if (isConfirming.value || isPreparingVideo.value) return;
    const targetId = target.id;
    const messageId = target.pending_ai.message_id;
    isConfirming.value = true;
    try {
      if (!await store.flush(id)) { notice.value = '请先同步画布，再写入正文。'; return; }
      const confirmed = await request.post<VideoProjectView, VideoProjectView>(`/conversations/${id}/canvas/confirm`, {
        target_node_id: targetId, message_id: messageId, expected_canvas_version: store.sessions.get(id)?.version,
      });
      store.acceptRemote(id, confirmed);
      await store.flush(id);
      if (currentConvId.value === id) {
        project.value = confirmed;
        const result = nodes.value.find(n => n.id === targetId);
        notice.value = result?.pending_ai ? '确认期间你又编辑了小框，已保留编辑；请核对后再次确定并写入小框。'
          : `AI 正文已写入“${target.title}”，可继续编辑或点击“撤销 AI 写入”。`;
      }
    } catch (err: any) { notice.value = err.message || 'AI 正文写入失败'; await refreshProject(id); }
    finally { isConfirming.value = false; }
  }

  async function prepareVideo(nodeIds: string[]) {
    const id = currentConvId.value;
    if (isPreparingVideo.value) return;
    if (currentConvId.value === id) notice.value = '';
    if (!store || !project.value || !nodeIds.length) {
      videoReviews.value[id] = { kind: 'error', content: '请选择需要生成视频的文本小框，可用 Ctrl 或框选多选。' }; return;
    }
    isPreparingVideo.value = true;
    videoReviews.value[id] = { kind: 'loading', content: 'AI 正在整理最终方案，并补全必要的创作细节…' };
    try {
      const settingsReason = videoSettingsBlockReason(canvas.value);
      if (settingsReason) { videoReviews.value[id] = { kind: 'error', content: settingsReason }; return; }
      if (!await store.flush(id)) { videoReviews.value[id] = { kind: 'error', content: '画布尚未同步，请先保存，再审理方案。' }; return; }
      const documentToPrepare = store.sessions.get(id)?.document;
      const prepared = await request.post<VideoProjectView, VideoProjectView>(`/conversations/${id}/canvas/prepare-video`, {
        node_ids: nodeIds, expected_canvas_version: store.sessions.get(id)?.version,
        duration_seconds: documentToPrepare?.video_duration_seconds, resolution: documentToPrepare?.video_resolution,
      }, { timeout: 240000 });
      store.acceptRemote(id, prepared);
      await store.flush(id);
      if (currentConvId.value === id) project.value = prepared;
      const document = store.sessions.get(id)?.document;
      if (document && !!prepared.compiled_prompt && generationMatches(document, prepared.current_spec_version, nodeIds)) {
        delete videoReviews.value[id];
      } else {
        videoReviews.value[id] = { kind: 'error', content: '审理期间小框已变化，请按当前内容重新审理。' };
      }
    } catch (err: any) {
      videoReviews.value[id] = { kind: 'error', content: err.message || 'AI 审理未完成，小框内容已保留，可以重新尝试。' };
      await refreshProject(id, false);
    }
    finally { isPreparingVideo.value = false; }
  }

  async function submitVideoJob(selectedIds: string[]) {
    if (!generationReady.value || !project.value || !store || isSubmittingJob.value
      || !generationMatches(canvas.value, project.value.current_spec_version, selectedIds)) {
      notice.value = '选择或小框内容已变化，请重新整理并查看视频提示词。'; return;
    }
    const id = currentConvId.value;
    const snapshot = project.value;
    const sourceId = canvas.value.generation_node_id;
    isSubmittingJob.value = true;
    try {
      // 确保模型约束已加载，并在提交前校验真实参数
      await ensureModelProfiles();
      const sessionDoc = store.sessions.get(id)?.document || canvas.value;
      const constraintError = validateBeforeSubmit(snapshot, sessionDoc);
      if (constraintError) {
        notice.value = constraintError;
        if (typeof window !== 'undefined' && typeof window.alert === 'function') {
          window.alert(constraintError);
        }
        return;
      }

      if (!await store.flush(id)) { notice.value = '请先同步画布，再生成视频。'; return; }
      const confirmed = await request.post<VideoProjectView, VideoProjectView>(`/conversations/${id}/project/confirm`, {
        spec_version: snapshot.current_spec_version,
      });
      if (currentConvId.value === id) project.value = confirmed;
      const job = await request.post<VideoJobView, VideoJobView>('/video-jobs', {
        conversation_id: id, project_id: snapshot.id, spec_version: snapshot.current_spec_version,
        api_config_id: selectedApiConfigId.value, mode: snapshot.current_spec.mode || 'text_to_video',
        generation_options: {
          ...store.sessions.get(id)?.document.generation_settings, generate_audio: true, canvas_source_node_id: sourceId,
          canvas_source_node_ids: selectedIds
        }, previous_job_id: null,
      }, { headers: { 'Idempotency-Key': newId() } });
      if (currentConvId.value === id) {
        jobs.value.unshift(job); materializeJob(id, job); schedulePolling();
        notice.value = '视频任务已提交，结果将连接到本次选中的来源小框。';
      }
    } catch (err: any) { notice.value = err.message || '视频任务提交失败'; }
    finally { isSubmittingJob.value = false; }
  }

  function materializeJob(id: string, job: VideoJobView) {
    const session = store?.sessions.get(id);
    if (!session || job.status !== 'succeeded' || session.document.dismissed_job_ids.includes(job.id)) return;
    const url = job.result_asset_id ? `/api/v1/assets/${job.result_asset_id}/content` : job.result_direct_url;
    if (!url) return;
    let node = session.document.nodes.find(n => n.job_id === job.id || n.id === `video_${job.id}`);
    if (node) { if (node.url !== url) { node.url = url; store?.edit(id, session.document); } return; }
    const source = session.document.nodes.find(n => n.id === job.generation_options.canvas_source_node_id);
    node = {
      id: `video_${job.id}`, job_id: job.id, type: 'video', title: '生成视频结果',
      x: source ? source.x + 360 : 800, y: source?.y || 160, url, asset_id: job.result_asset_id || undefined
    };
    session.document.nodes.push(node);
    const sourceIds: string[] = job.generation_options.canvas_source_node_ids || (source ? [source.id] : []);
    for (const sourceId of sourceIds) if (session.document.nodes.some(n => n.id === sourceId))
      session.document.connections.push({ id: `job_${job.id}_${sourceId}`, from: sourceId, to: node.id });
    store?.edit(id, session.document);
  }

  function schedulePolling() {
    stopPolling();
    if (disposed || !currentConvId.value) return;
    timer = setTimeout(() => { void poll(); }, 2500);
  }
  async function poll() {
    const id = currentConvId.value;
    if (!id || disposed) return;
    try {
      if (nodes.value.some(n => n.ai_running) || sending.value.includes(id)) {
        await refreshProject(id);
        if (currentConvId.value === id && !nodes.value.some(n => n.ai_running) && !sending.value.includes(id))
          messages.value = await listAll<MessageView>(`/conversations/${id}/messages`);
      }
      const active = jobs.value.filter(job => runningStatuses.includes(job.status) || job.status === 'succeeded' && job.download_status === 'not_started');
      for (const job of active) {
        const result = await request.get<VideoJobView, VideoJobView>(`/video-jobs/${job.id}`);
        materializeJob(id, result);
        if (currentConvId.value !== id || disposed) return;
        jobs.value = jobs.value.map(item => item.id === result.id ? result : item);
      }
    } catch (err: any) { if (currentConvId.value === id) notice.value = err.message || '任务状态暂时无法更新'; }
    finally { if (currentConvId.value === id) schedulePolling(); }
  }

  async function retrySave() { if (store && currentConvId.value) await store.flush(currentConvId.value); }
  async function resolveConflict(choice: 'local' | 'remote') {
    if (!store) return;
    try { await store.resolve(currentConvId.value, choice); }
    catch (err: any) { notice.value = err.message || '冲突处理失败，草稿已保留'; }
  }
  function restoreBeforeAi(node: FlowNode) {
    if (!node.last_ai || node.content !== node.last_ai.after) return;
    node.content = node.last_ai.before; delete node.last_ai;
  }
  async function handleLogout() {
    if (!await flushCurrent()) return;
    try { await request.post('/auth/logout'); await router.push('/login'); }
    catch (err: any) { notice.value = err.message || '退出登录失败'; }
  }

  function checkpointAll() { for (const session of store?.sessions.values() || []) store?.checkpoint(session); }
  function beforeUnload(event: BeforeUnloadEvent) {
    checkpointAll();
    if (Array.from(store?.sessions.values() || []).some(s => s.dirty && !s.localAvailable)) {
      event.preventDefault(); event.returnValue = '';
    }
  }
  function pageHide() {
    checkpointAll();
    const token = document.cookie.match(/(?:^|;\s*)hw_csrf=([^;]+)/)?.[1];
    if (!token) return;
    for (const session of store?.sessions.values() || []) {
      if (!session.dirty || session.pending || session.conflicts.length) continue;
      const body = JSON.stringify({ canvas_data: session.document, expected_canvas_version: session.version });
      if (new TextEncoder().encode(body).length > 60000) continue;
      void fetch(`/api/v1/conversations/${session.id}/canvas`, {
        method: 'PUT', credentials: 'include', keepalive: true,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': decodeURIComponent(token) }, body
      }).catch(() => { });
    }
  }
  async function reconnect() {
    for (const session of store?.sessions.values() || []) if (session.dirty) void store?.flush(session.id);
    if (currentConvId.value) { await refreshProject(currentConvId.value); schedulePolling(); }
  }
  function visibilityChanged() { if (document.visibilityState === 'hidden') { checkpointAll(); void flushCurrent(); } else void reconnect(); }

  onBeforeRouteLeave(async to => to.path === '/workspace' || await flushCurrent());
  watch(() => route.query.conversation, id => {
    if (!initialized.value || loading.value) return;
    if (typeof id === 'string' && id !== currentConvId.value) void switchConversation(id, false);
    else if (!id && currentConvId.value) void backToProjectSpace();
  });
  onMounted(async () => {
    try {
      const user = await request.get<UserView, UserView>('/users/me');
      if (disposed) return;
      store = new CanvasPersistence(user.id, {
        getItem: key => localStorage.getItem(key), setItem: (key, value) => localStorage.setItem(key, value), removeItem: key => localStorage.removeItem(key),
      }, {
        load: id => request.get<VideoProjectView, VideoProjectView>(`/conversations/${id}/project`, { timeout: 8000 }),
        save: (id, document, version) => request.put<VideoProjectView, VideoProjectView>(`/conversations/${id}/canvas`,
          { canvas_data: document, expected_canvas_version: version }, { timeout: 8000 }),
      }, reflect);
      await loadConversations();
      try {
        apiConfigs.value = await listAll<VideoApiConfigView>('/video-api-configs');
        await ensureModelProfiles();
      }
      catch (err: any) { notice.value = err.message || 'API 配置加载失败，可以继续编辑画布'; }
      if (disposed) return;
      initialized.value = true;
      if (typeof route.query.conversation === 'string') await switchConversation(route.query.conversation, false);
    } catch (err: any) { notice.value = err.message || '工作台初始化失败，请刷新重试'; }
    if (disposed) return;
    window.addEventListener('beforeunload', beforeUnload); window.addEventListener('pagehide', pageHide);
    window.addEventListener('online', reconnect); window.addEventListener('focus', reconnect);
    document.addEventListener('visibilitychange', visibilityChanged);
  });
  onBeforeUnmount(() => {
    disposed = true; ++loadSequence; stopPolling(); checkpointAll(); store?.stop();
    window.removeEventListener('beforeunload', beforeUnload); window.removeEventListener('pagehide', pageHide);
    window.removeEventListener('online', reconnect); window.removeEventListener('focus', reconnect);
    document.removeEventListener('visibilitychange', visibilityChanged);
  });

  return {
    canvas, nodes, connections, pan, zoom, currentConvId, conversations, messages, project, apiConfigs, modelProfiles,
    inputContent, referencedNodeIds, aiTargetNodeId, selectedApiConfigId, isAgentResponding, isCreatingConv, isSubmittingJob,
    isConfirming, isPreparingVideo, videoReview, isAgentDrawerOpen, activeJob, generationReady, initialized, loading, notice, saveState, saveLabel, uploading,
    switchConversation, createNewConversation, backToProjectSpace, deleteConversation, sendMessage, uploadImage,
    confirmSpec, prepareVideo, submitVideoJob, retrySave, resolveConflict, restoreBeforeAi, handleLogout, loadConversations
  };
}