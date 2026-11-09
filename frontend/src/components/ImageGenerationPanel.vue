<template>
  <Teleport to="body" :disabled="embedded">
    <div v-if="open" :class="['image-panel-backdrop', { embedded }]" @click.self="$emit('close')">
      <section ref="panel" class="image-panel" :role="embedded ? 'region' : 'dialog'" :aria-modal="embedded ? undefined : true" aria-labelledby="image-panel-title" tabindex="-1" @keydown.esc="!embedded && $emit('close')" @keydown.tab="!embedded && trapFocus($event)">
        <header class="panel-heading"><div><span class="eyebrow">图片创作</span><h2 id="image-panel-title">把画面想法变成素材</h2></div><button v-if="!embedded" class="close" aria-label="关闭生图面板" @click="$emit('close')">×</button></header>
        <div class="panel-scroll">
          <p v-if="options?.simulation" class="simulation">当前通道提供示例图片，不会调用生图服务</p>
          <p v-else class="intro">描述画面或上传参考图，按需请 AI 看图完善描述。每个结果都可继续修改，也可插入画布用于视频创作。</p>
          <div class="portrait-notice-entry"><button type="button" @click="$emit('portrait-notice')">人像素材须知 ↗</button></div>
          <p v-if="options?.notice" class="muted">{{ options.notice }}</p>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <p v-if="storageError" class="error" role="status">浏览器草稿保存不可用；请保留此页面，任务记录仍可从服务器恢复。</p>
          <div class="two-col">
            <label>生图通道<select v-model="draft.api_config_id" :disabled="inputsLocked">
              <option value="platform" :disabled="!options?.platform.available">{{ options?.platform.display_name || '平台默认' }}{{ options?.platform.available ? '' : '（未启用）' }}</option>
              <option v-for="cfg in configs" :key="cfg.id" :value="cfg.id">{{ cfg.display_name }} · 自备 API</option>
            </select></label>
            <label>画面比例<select v-model="draft.aspect_ratio" :disabled="inputsLocked"><option v-for="ratio in options?.aspect_ratios || ['1:1']" :key="ratio">{{ ratio }}</option></select></label>
          </div>
          <div class="channel-meta"><span>{{ displayModel(selectedModel || '', draft.api_config_id) || '请选择可用通道' }}</span><RouterLink to="/settings/api?tab=image" @click="$emit('close')">管理图片 API ↗</RouterLink></div>
          <p v-if="draft.api_config_id === 'platform' && !options?.platform.available" class="muted">{{ options?.platform.reason || '平台默认通道暂不可用，请添加自己的图片 API。' }}</p>
          <p v-if="draft.source_node_id" class="source-tag">从图片节点发起 · 生成结果将作为新素材插入</p>
          <button v-if="sourceNode?.asset_id" class="quiet source-reset" :disabled="inputsLocked" @click="applySourceNode(true)">重新使用此节点图片</button>
          <section class="reference-section" aria-label="图片参考">
            <div class="reference-heading"><span>{{ draft.parent_job_id ? '继续修改 · 上一版作为参考' : draft.reference_images.length ? '参考图创作' : '上传可参考图' }}</span><button v-if="draft.reference_images.length || draft.parent_job_id" class="quiet" :disabled="inputsLocked" @click="clearReferences">清空参考图</button></div>
            <div v-if="draft.reference_images.length" class="reference-grid">
              <div v-for="(image, index) in draft.reference_images" :key="image.asset_id" class="reference-card"><button class="reference-image" @click="preview = { content_url: image.content_url, prompt: image.original_name }" :aria-label="'查看参考图：' + image.original_name"><img :src="image.content_url" :alt="image.original_name" /></button><span>{{ draft.parent_job_id && index === 0 ? '上一版本' : `参考图 ${index + 1}` }}</span><button class="remove-reference" :disabled="inputsLocked" @click="removeReference(index)" :aria-label="'移除参考图 ' + (index + 1)">×</button></div>
            </div>
            <input ref="uploadInput" class="reference-file-input" type="file" accept="image/png,image/jpeg" multiple :disabled="inputsLocked || draft.reference_images.length >= maxReferences" @change="uploadReferences" />
            <button class="upload-reference" :disabled="inputsLocked || draft.reference_images.length >= maxReferences" @click="uploadInput?.click()">{{ uploading ? '正在上传参考图…' : '+ 上传参考图' }} <span>{{ draft.reference_images.length }}/{{ maxReferences }}</span></button>
            <small>PNG / JPEG，每张不超过 10 MB；最多 {{ maxReferences }} 张，包含继续修改的上一版本。</small>
          </section>
          <label class="prompt-label" for="image-prompt">{{ draft.parent_job_id ? '希望如何修改' : '画面描述' }}<span>{{ draft.prompt.length }} / 4000</span></label>
          <textarea id="image-prompt" v-model="draft.prompt" maxlength="4000" rows="5" :placeholder="draft.parent_job_id ? '例如：保留人物与构图，把背景改成黄昏海边，色调更温暖。' : '描述主体、场景、构图与风格；使用参考图时，请说明保留什么、改变什么。'" :disabled="inputsLocked"></textarea>
          <p class="muted model-hint">AI 会为 {{ displayModel(selectedModel || '', draft.api_config_id) || '所选模型' }} 优化画面描述{{ (draft.reference_images.length || draft.parent_job_id) && options?.vision?.available ? '，并结合参考图内容' : '' }}。</p>
          <p v-if="(draft.reference_images.length || draft.parent_job_id) && !options?.vision?.available" class="vision-unavailable" role="status">{{ options?.vision?.reason || '看图建议暂不可用，您仍可填写描述并使用参考图生成。' }}</p>
          <button class="suggest-btn" :disabled="!canSuggest" @click="suggest">{{ suggesting ? 'AI 正在整理建议…' : (draft.reference_images.length || draft.parent_job_id) ? '✧ 请 AI 看图提供建议' : '✧ 请 AI 优化画面描述' }}</button>
          <div v-if="suggestion" class="suggestion"><div class="suggestion-title">AI 建议 · 尚未采用</div><p>{{ suggestion.suggested_prompt }}</p><small>{{ suggestion.explanation }}</small><div class="actions"><button :disabled="!!draft.pending || submitting" @click="adoptSuggestion">采用到输入框</button><button class="quiet" @click="suggestion = null">保留原文</button></div></div>
          <p class="muted suggestion-help">AI 建议仅供参考，采用后仍需点击生成图片。</p>
          <div class="generation-action">
          <button v-if="draft.pending" class="primary" :disabled="submitting" @click="submitPending">{{ submitting ? '正在确认请求…' : '查询上次生成状态' }}</button>
          <button v-else class="primary" :disabled="!canGenerate" @click="generate">{{ submitting ? '提交中…' : options?.simulation ? '生成示例图片' : '生成图片' }}</button>
          <p class="muted generation-cost">点击生成将使用所选通道的额度。</p>
          </div>
          <p v-if="jobs.some(imageJobActive) && !draft.pending" class="muted">当前图片任务仍在处理，完成后可提交下一张。</p>
          <p v-if="jobs.some(job => job.status === 'unknown') && !draft.pending" class="muted">有任务的结果尚未确认，请先核对方舟控制台，再在对应记录中结束等待。</p>
          <p v-if="draft.pending && !submitting" class="muted">上次提交尚未确认，已保留原请求。请先确认状态，避免重复消耗额度。</p>
          <div class="history-heading"><h3>本对话的生成记录 <span>{{ jobs.length }}</span></h3><button class="quiet" :disabled="refreshing" @click="refresh">{{ refreshing ? '更新中…' : '刷新' }}</button></div>
          <p v-if="!jobs.length" class="empty">{{ refreshing ? '正在恢复任务记录…' : '第一张灵感，从这里开始。关闭面板后也能找回任务。' }}</p>
          <article v-for="job in jobs" :key="job.id" class="job-card">
            <div class="job-heading"><span :class="['job-status', { running: imageJobActive(job), failed: ['failed', 'storage_failed'].includes(job.status) }]">{{ imageJobLabels[job.status] || job.status }}</span><span v-if="job.simulation" class="simulation-tag">示例图片</span><time>{{ formatTime(job.created_at) }}</time></div>
            <button v-if="job.status === 'succeeded' && job.content_url" class="preview" @click="preview = job" aria-label="放大查看生成图片"><img :src="job.content_url" :alt="job.prompt" loading="lazy" /></button>
            <div v-else-if="imageJobActive(job)" class="progress"><span class="spinner"></span>画面正在成形，您可以关闭面板继续创作</div>
            <p v-if="job.status === 'unknown'" class="muted">请到方舟控制台核对，平台不会自动重复提交。</p>
            <p v-if="job.status === 'unknown_acknowledged'" class="muted">您已结束等待；原任务结果仍待确认，平台未重新提交。</p>
            <p class="job-prompt">{{ job.prompt }}</p>
            <p class="job-meta">{{ job.api_config_id === 'platform' ? '平台默认' : job.channel_label }} · {{ displayModel(job.model, job.api_config_id) }} · {{ job.aspect_ratio }}</p>
            <p class="job-meta" v-if="job.parent_job_id">此版本基于历史结果继续修改</p>
            <div v-if="job.reference_images?.length" class="history-references"><span>参考</span><button v-for="image in job.reference_images" :key="image.asset_id" @click="preview = { content_url: image.content_url, prompt: image.original_name }" :aria-label="'查看原参考图：' + image.original_name"><img :src="image.content_url" :alt="image.original_name" loading="lazy" /></button></div>
            <p v-if="job.error_message" class="error">{{ job.error_message }}</p>
            <div class="actions">
              <button v-if="job.status === 'succeeded'" :disabled="!job.asset_id || inputsLocked" @click="continueEditing(job)">继续修改</button>
              <button v-if="job.status === 'succeeded'" :disabled="!job.asset_id || alreadyInserted(job) || canvasBusy" @click="$emit('insert', job)">{{ alreadyInserted(job) ? '已在画布中' : '插入画布' }}</button>
              <a v-if="job.status === 'succeeded' && job.download_url" :href="job.download_url" download>下载图片 ↓</a>
              <button v-if="job.status === 'storage_failed'" :disabled="actionJob === job.id" @click="jobAction(job, 'retry-storage')">重新保存图片</button>
              <button v-if="job.status === 'queued'" class="quiet" :disabled="actionJob === job.id" @click="jobAction(job, 'cancel')">取消排队</button>
              <button v-if="job.status === 'unknown' && confirmUnknown !== job.id" class="quiet" :disabled="actionJob === job.id" @click="confirmUnknown = job.id">我已核对，结束等待</button>
              <button v-if="['succeeded', 'failed', 'cancelled', 'unknown_acknowledged'].includes(job.status)" class="quiet" :disabled="inputsLocked" @click="reuse(job)">复用描述</button>
            </div>
            <div v-if="job.status === 'unknown' && confirmUnknown === job.id" class="unknown-confirm"><p>原任务可能已经消耗额度。此操作只结束等待，并允许您之后手动发起新生成；不会取消方舟任务，也不会自动重试。</p><div class="actions"><button :disabled="actionJob === job.id" @click="jobAction(job, 'acknowledge-unknown')">{{ actionJob === job.id ? '确认中…' : '确认结束等待' }}</button><button class="quiet" :disabled="actionJob === job.id" @click="confirmUnknown = ''">继续等待</button></div></div>
          </article>
        </div>
      </section>
    </div>
    <Teleport to="body">
    <div v-if="preview && open" ref="lightbox" class="image-lightbox" role="dialog" aria-modal="true" aria-label="生成图片预览" tabindex="0" @click="preview = null" @keydown.esc.stop="preview = null" @keydown.tab.prevent="lightbox?.querySelector('button')?.focus()"><button aria-label="关闭图片预览" @click="preview = null">×</button><img :src="preview.content_url || ''" :alt="preview.prompt" /><span>点击任意位置关闭</span></div>
    </Teleport>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import request from '@/utils/request';
import type { FlowNode } from '@/types/canvas';
import type { ImageApiConfig, ImageDraft, ImageJob, ImageOptions, ImageReferenceUpload } from '@/types/imageGeneration';
import { imageAlreadyInserted, imageDraftKey, imageEditDraft, imageJobActive, imageJobBlocksGeneration, imageJobLabels, imageDisplayModel, imageSourceDraft, imageSourceParent, imageSubmission, imageSuggestionRequest, imageTextOnlyDraft, readImageDraft, sanitizeImageReferences } from '@/services/imageGeneration';
const props = defineProps<{ open: boolean; embedded?: boolean; accountId: string; conversationId: string; nodes: FlowNode[]; canvasBusy: boolean; sourceNodeId?: string }>();
defineEmits<{ close: []; insert: [job: ImageJob]; 'portrait-notice': [] }>();
const panel = ref<HTMLElement | null>(null);
const lightbox = ref<HTMLElement | null>(null);
const uploadInput = ref<HTMLInputElement | null>(null);
const draft = ref<ImageDraft>(readImageDraft(null));
const options = ref<ImageOptions | null>(null), configs = ref<ImageApiConfig[]>([]), jobs = ref<ImageJob[]>([]);
const error = ref(''), storageError = ref(false), submitting = ref(false), suggesting = ref(false), refreshing = ref(false), actionJob = ref('');
const confirmUnknown = ref('');
const uploading = ref(false);
const historyLoaded = ref(false);
const suggestion = ref<{ suggested_prompt: string; explanation: string } | null>(null), preview = ref<{ content_url: string | null; prompt: string } | null>(null);
let timer: ReturnType<typeof setTimeout> | undefined, epoch = 0, disposed = false, previousFocus: HTMLElement | null = null;
let previewFocus: HTMLElement | null = null;
watch(preview, async value => { if (value) { previewFocus = document.activeElement as HTMLElement; await nextTick(); lightbox.value?.focus(); } else if (props.open) previewFocus?.focus(); });
const displayModel = (id: string, channel: string) => imageDisplayModel(options.value?.models || [], id, channel);
const selectedModel = computed(() => draft.value.api_config_id === 'platform' ? options.value?.platform.model : configs.value.find(c => c.id === draft.value.api_config_id)?.model);
const selectedAvailable = computed(() => draft.value.api_config_id === 'platform' ? !!options.value?.platform.available : configs.value.some(c => c.id === draft.value.api_config_id));
const sourceNode = computed(() => props.nodes.find(node => node.id === props.sourceNodeId && node.type === 'image'));
const maxReferences = computed(() => Math.min(4, Math.max(1, options.value?.max_reference_images || 4)));
const inputsLocked = computed(() => !!draft.value.pending || submitting.value || uploading.value);
const canSuggest = computed(() => !!imageSuggestionRequest(draft.value, props.conversationId) && selectedAvailable.value && !inputsLocked.value && !suggesting.value
  && (!(draft.value.reference_images.length || draft.value.parent_job_id) || options.value?.vision?.available));
const canGenerate = computed(() => historyLoaded.value && !!props.accountId && !!props.conversationId && !!draft.value.prompt.trim() && selectedAvailable.value && !inputsLocked.value && !jobs.value.some(imageJobBlocksGeneration));
function persist(value = draft.value, account = props.accountId, conversation = props.conversationId) {
  if (!account || !conversation) return;
  try { localStorage.setItem(imageDraftKey(account, conversation), JSON.stringify(value)); storageError.value = false; } catch { storageError.value = true; }
}
watch(draft, () => persist(), { deep: true, flush: 'sync' });
watch(() => JSON.stringify([draft.value.api_config_id, draft.value.aspect_ratio, draft.value.parent_job_id, draft.value.reference_images.map(image => image.asset_id)]), () => { suggestion.value = null; });
function schedule() {
  clearTimeout(timer);
  if (!disposed && jobs.value.some(imageJobActive)) timer = setTimeout(() => void refresh(), 3500);
}
async function refresh() {
  if (!props.conversationId || refreshing.value) return;
  const version = epoch; refreshing.value = true;
  try {
    const response = await request.get<unknown, { items: ImageJob[] }>('/image-jobs', { params: { conversation_id: props.conversationId }, timeout: 15000 });
    if (version !== epoch) return;
    jobs.value = response.items;
    historyLoaded.value = true;
    linkSourceParent();
  } catch (err: any) { if (version === epoch) error.value = err.message || '任务记录暂时无法加载'; }
  finally { if (version === epoch) { refreshing.value = false; schedule(); } }
}
async function loadOptions() {
  const version = epoch;
  const results = await Promise.allSettled([request.get<unknown, ImageOptions>('/image-generation/options'), request.get<unknown, { items: ImageApiConfig[] }>('/image-api-configs')]);
  if (version !== epoch) return;
  if (results[0].status === 'fulfilled') options.value = results[0].value;
  else error.value = results[0].reason?.message || '生图选项加载失败';
  if (results[1].status === 'fulfilled') configs.value = results[1].value.items;
  else error.value = results[1].reason?.message || '图片 API 配置加载失败';
}
watch(() => [props.accountId, props.conversationId], () => {
  ++epoch; clearTimeout(timer); refreshing.value = false; submitting.value = false; suggesting.value = false; uploading.value = false;
  jobs.value = []; historyLoaded.value = false; error.value = ''; suggestion.value = null; preview.value = null; confirmUnknown.value = '';
  try { draft.value = readImageDraft(localStorage.getItem(imageDraftKey(props.accountId, props.conversationId))); } catch { draft.value = readImageDraft(null); storageError.value = true; }
  if (props.accountId && props.conversationId) { void refresh(); void loadOptions(); }
}, { immediate: true });
watch(() => props.open, async open => {
  if (open) { if (!props.embedded) previousFocus = document.activeElement as HTMLElement; applySourceNode(); void refresh(); void loadOptions(); await nextTick(); if (!props.embedded) panel.value?.focus(); }
  else { preview.value = null; if (!props.embedded) previousFocus?.focus(); }
});
watch(() => props.sourceNodeId, () => { if (props.open) applySourceNode(); });
function applySourceNode(force = false) {
  if (inputsLocked.value || !props.sourceNodeId) return;
  const next = imageSourceDraft(draft.value, sourceNode.value, jobs.value, force);
  if (next !== draft.value) { draft.value = next; suggestion.value = null; }
  linkSourceParent();
}
function linkSourceParent() {
  if (inputsLocked.value || !draft.value.source_node_id || draft.value.parent_job_id) return;
  const node = props.nodes.find(node => node.id === draft.value.source_node_id);
  if (node?.asset_id && draft.value.reference_images[0]?.asset_id === node.asset_id) draft.value.parent_job_id = imageSourceParent(node, jobs.value);
}
function clearReferences() { if (!inputsLocked.value) { draft.value = imageTextOnlyDraft(draft.value); suggestion.value = null; } }
function removeReference(index: number) {
  if (inputsLocked.value) return;
  if (index === 0 && draft.value.parent_job_id) draft.value.parent_job_id = null;
  draft.value.reference_images.splice(index, 1); draft.value.source_node_id = undefined; suggestion.value = null;
}
async function uploadReferences(event: Event) {
  const input = event.target as HTMLInputElement, files = Array.from(input.files || []); input.value = '';
  if (!files.length || inputsLocked.value) return;
  const version = epoch; uploading.value = true; error.value = ''; suggestion.value = null;
  try {
    for (const file of files) {
      if (version !== epoch) return;
      if (draft.value.reference_images.length >= maxReferences.value) { error.value = `最多使用 ${maxReferences.value} 张参考图（含上一版本），其余文件未上传。`; break; }
      if (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 10_000_000) { error.value = `「${file.name}」未上传：仅支持 PNG / JPEG，每张不超过 10 MB。`; continue; }
      const form = new FormData(); form.append('file', file); form.append('conversation_id', props.conversationId);
      const asset = await request.post<unknown, ImageReferenceUpload>('/image-reference-uploads', form, { headers: { 'Content-Type': undefined } });
      if (version !== epoch) return;
      draft.value.reference_images = sanitizeImageReferences([...draft.value.reference_images, { asset_id: asset.id, content_url: asset.content_url, original_name: asset.original_name || file.name }], maxReferences.value);
    }
  } catch (err: any) { if (version === epoch) error.value = err.message || '参考图上传失败，已上传的图片已保留。'; }
  finally { if (version === epoch) { uploading.value = false; linkSourceParent(); } }
}
async function suggest() {
  if (!canSuggest.value) return;
  const body = imageSuggestionRequest(draft.value, props.conversationId);
  if (!body) return;
  const context = JSON.stringify(imageSubmission(draft.value, props.conversationId)), version = epoch; suggesting.value = true; error.value = ''; suggestion.value = null;
  try {
    const response = await request.post<unknown, { suggested_prompt: string; explanation: string }>('/image-prompt-suggestions', { prompt: body.prompt, aspect_ratio: body.aspect_ratio, conversation_id: body.conversation_id,
      api_config_id: body.api_config_id, reference_asset_ids: body.reference_asset_ids, parent_job_id: body.parent_job_id, watermark: body.watermark });
    if (version === epoch) {
      if (context === JSON.stringify(imageSubmission(draft.value, props.conversationId))) suggestion.value = response;
      else error.value = '描述、参考图或通道已变化，请按当前内容重新获取建议。';
    }
  } catch (err: any) { if (version === epoch) error.value = err.message || 'AI 建议暂不可用'; }
  finally { if (version === epoch) suggesting.value = false; }
}
function adoptSuggestion() { if (suggestion.value) draft.value.prompt = suggestion.value.suggested_prompt.slice(0, 4000); suggestion.value = null; }
function generate() {
  if (!canGenerate.value) return;
  draft.value.pending = { key: crypto.randomUUID(), body: imageSubmission(draft.value, props.conversationId) };
  void submitPending();
}
async function submitPending() {
  const saved = draft.value, pending = saved.pending;
  if (!pending || submitting.value) return;
  const account = props.accountId, conversation = props.conversationId, version = epoch;
  submitting.value = true; error.value = ''; persist(saved, account, conversation);
  try {
    const job = await request.post<unknown, ImageJob>('/image-jobs', pending.body, { headers: { 'Idempotency-Key': pending.key }, timeout: 25000 });
    delete saved.pending; persist(saved, account, conversation);
    if (version === epoch) { jobs.value = [job, ...jobs.value.filter(j => j.id !== job.id)]; void refresh(); }
  } catch (err: any) {
    if ([400, 403, 404, 422, 429].includes(err.status)) { delete saved.pending; persist(saved, account, conversation); }
    if (version === epoch) error.value = err.message || '提交结果尚未确认，请确认原请求状态';
  } finally { if (version === epoch) { submitting.value = false; schedule(); } }
}
async function jobAction(job: ImageJob, action: string) {
  const version = epoch; actionJob.value = job.id; error.value = '';
  try { const updated = await request.post<unknown, ImageJob>(`/image-jobs/${job.id}/${action}`); if (version === epoch) jobs.value = jobs.value.map(j => j.id === updated.id ? updated : j); }
  catch (err: any) { if (version === epoch) error.value = err.message || '操作失败，请刷新状态'; }
  finally { if (version === epoch) { actionJob.value = ''; schedule(); } }
}
function focusComposer() { panel.value?.querySelector('.panel-scroll')?.scrollTo({ top: 0, behavior: 'smooth' }); panel.value?.querySelector('textarea')?.focus({ preventScroll: true }); }
function reuse(job: ImageJob) { if (inputsLocked.value) return; draft.value = imageTextOnlyDraft(draft.value); draft.value.prompt = job.prompt; draft.value.aspect_ratio = job.aspect_ratio; suggestion.value = null; focusComposer(); }
function continueEditing(job: ImageJob) { if (inputsLocked.value) return; const next = imageEditDraft(draft.value, job); if (next) { draft.value = next; suggestion.value = null; focusComposer(); } }
const alreadyInserted = (job: ImageJob) => imageAlreadyInserted(props.nodes, job);
const formatTime = (value: string) => new Date(value).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
function trapFocus(event: KeyboardEvent) {
  const elements = panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],select:not(:disabled),textarea:not(:disabled),input:not(:disabled)');
  if (!elements?.length) return;
  const first = elements[0], last = elements[elements.length - 1];
  if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.value)) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}
onBeforeUnmount(() => { disposed = true; ++epoch; clearTimeout(timer); });
</script>

<style scoped>
.image-panel-backdrop{position:fixed;inset:0;z-index:1000;background:#02061799;display:flex;justify-content:flex-end;backdrop-filter:blur(4px)}
.image-panel{width:min(540px,100vw);height:100dvh;background:#0f1422;border-left:1px solid #2b3550;color:#e2e8f0;display:flex;flex-direction:column;box-shadow:-24px 0 90px #0005;outline:none;font-size:13px}
.panel-heading{display:flex;align-items:center;justify-content:space-between;padding:25px 26px 20px;border-bottom:1px solid #253049}.eyebrow{font-size:10px;color:#a5b4fc;letter-spacing:2px}.panel-heading h2{font-size:21px;margin:8px 0 0;font-weight:600}.close{font-size:25px!important;border:0!important;background:none!important;color:#94a3b8!important}.panel-scroll{overflow-y:auto;flex:1;padding:20px 26px 30px}.intro{color:#b1bed2;line-height:1.8;margin:0 0 18px}.muted{font-size:12px;line-height:1.7;color:#8899b2}.simulation{padding:12px;background:#49381966;color:#fcd989;border:1px solid #75602d;border-radius:9px;line-height:1.7}.two-col{display:grid;grid-template-columns:1.6fr 1fr;gap:12px;margin-top:18px}label{display:flex;flex-direction:column;gap:8px;font-size:12px;color:#b9c6d9}.image-panel select,.image-panel textarea{background:#182033;border:1px solid #34415a;border-radius:8px;color:#eef2ff;padding:11px;width:100%;box-sizing:border-box;font:inherit;outline:none}.image-panel select:focus,.image-panel textarea:focus{border-color:#818cf8;box-shadow:0 0 0 3px #6366f11a}.image-panel textarea{resize:vertical;min-height:136px;line-height:1.8}.channel-meta{display:flex;justify-content:space-between;gap:10px;margin:10px 0 20px;font-size:11px;color:#8594ad;overflow-wrap:anywhere}.channel-meta a{color:#a5b4fc;white-space:nowrap}.source-tag{font-size:11px;color:#93c5fd}.prompt-label{flex-direction:row;justify-content:space-between;margin-bottom:8px}.prompt-label span{color:#66768f}.image-panel button,.image-panel .actions a{border:1px solid #3a4560;border-radius:7px;padding:9px 12px;background:#222d46;color:#dce5f5;cursor:pointer;font:inherit;text-decoration:none;text-align:center}.image-panel button:disabled{opacity:.45;cursor:not-allowed}.image-panel .primary{width:100%;background:#6366f1;color:white;border-color:#818cf8;padding:13px;font-weight:600;margin-top:8px}.image-panel .suggest-btn{margin-top:10px;background:#1c2340;color:#b8bcff;border-color:#3a4166;font-size:12px}.image-panel .quiet{background:transparent;border-color:transparent;color:#9caec8}.suggestion{margin-top:14px;border:1px solid #454b7e;border-radius:10px;background:#20223e;padding:15px;line-height:1.8}.suggestion-title{font-size:11px;color:#bbbdfb}.suggestion p{white-space:pre-wrap;margin:8px 0}.suggestion small{color:#9caec8}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:13px}.actions button,.actions a{font-size:12px!important}.history-heading{display:flex;align-items:center;justify-content:space-between;border-top:1px solid #29334b;margin-top:25px;padding-top:17px}.history-heading h3{font-size:14px;font-weight:500;margin:0}.history-heading h3 span{font-size:11px;color:#8293b0;margin-left:6px}.empty{padding:30px 18px;text-align:center;color:#74849f;border:1px dashed #35405a;border-radius:10px;line-height:1.8}.job-card{margin-top:14px;background:#151d2e;border:1px solid #2b3650;border-radius:12px;padding:14px}.job-heading{display:flex;gap:8px;align-items:center;margin-bottom:12px;font-size:11px}.job-status{color:#7addba}.job-status.running{color:#b4b5fd}.job-status.failed{color:#fdb391}.job-heading time{margin-left:auto;color:#71819b}.simulation-tag{background:#62502655;color:#e9c36e;padding:2px 5px;border-radius:4px}.image-panel .preview{padding:0;display:block;border:0;background:#080e19;width:100%;border-radius:8px;overflow:hidden}.preview img{width:100%;max-height:300px;object-fit:contain;display:block}.job-prompt{font-size:12px;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0 6px}.job-meta{font-size:10px;color:#8494ae;line-height:1.6;overflow-wrap:anywhere}.error{color:#fda4af;font-size:12px;line-height:1.7;overflow-wrap:anywhere}.progress{padding:24px 8px;display:flex;align-items:center;gap:10px;font-size:12px;color:#94a3b8}.spinner{width:13px;height:13px;border:2px solid #454b76;border-top-color:#a5b4fc;border-radius:50%;animation:spin 1s linear infinite;flex-shrink:0}@keyframes spin{to{transform:rotate(360deg)}}.image-lightbox{position:fixed;inset:0;z-index:1100;background:#020617ed;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px;gap:15px;color:#94a3b8;font-size:12px}.image-lightbox img{max-width:100%;max-height:85vh;object-fit:contain}.image-lightbox button{position:absolute;right:24px;top:20px;font-size:28px;background:none;border:0;color:white;cursor:pointer}@media(max-width:600px){.panel-heading{padding:20px}.panel-scroll{padding:18px 20px}.panel-heading h2{font-size:19px}.two-col{grid-template-columns:1.5fr 1fr}}
.unknown-confirm{margin-top:13px;padding:12px;border:1px solid #75602d;border-radius:8px;background:#49381933;color:#e8cc96;font-size:12px;line-height:1.8}.unknown-confirm p{margin:0}.unknown-confirm .actions{margin-top:10px}
.reference-section{margin:16px 0 20px;padding:14px;border:1px solid #33405b;background:#141d2f;border-radius:10px}.reference-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;color:#c4d0e7}.reference-heading .quiet{padding:3px 0;font-size:11px}.reference-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:13px}.reference-card{position:relative;min-width:0}.image-panel .reference-image{padding:0;width:100%;height:82px;overflow:hidden;background:#080e19;border:1px solid #3e4a63}.reference-image img{width:100%;height:100%;object-fit:contain;display:block}.reference-card>span{display:block;color:#9caec8;font-size:10px;margin-top:5px;text-align:center}.image-panel .remove-reference{position:absolute;right:-5px;top:-6px;background:#303c55;border-radius:50%;padding:0;width:20px;height:20px;line-height:16px;font-size:15px}.reference-file-input{display:none}.image-panel .upload-reference{width:100%;padding:9px;margin-top:12px;background:#1b2941;border-style:dashed;font-size:12px}.upload-reference span{color:#8299bc;margin-left:8px}.reference-section>small{display:block;margin-top:9px;color:#7589a8;font-size:10px;line-height:1.7}.vision-unavailable{font-size:11px;color:#ebc57e;padding:10px;border-left:2px solid #9f7d40;line-height:1.8;background:#49381933}.model-hint{font-size:11px;margin:7px 0}.history-references{display:flex;align-items:center;gap:6px;margin-top:10px}.history-references>span{font-size:10px;color:#7e94b5;margin-right:2px}.image-panel .history-references button{width:42px;height:42px;padding:0;overflow:hidden;background:#080e19;border-color:#34415c}.history-references img{width:100%;height:100%;object-fit:contain}
</style>

<style scoped>
.embedded.image-panel-backdrop{position:relative;inset:auto;z-index:auto;background:transparent;backdrop-filter:none;display:flex;flex:1;min-height:0;width:100%;overflow:hidden}
.embedded .image-panel{width:100%;height:100%;min-height:0;flex:1;border:0;box-shadow:none;background:transparent}
.embedded .panel-heading{padding:18px 22px;flex-shrink:0}
.embedded .panel-heading h2{font-size:18px}
.panel-scroll{min-height:0;scrollbar-width:thin;scrollbar-color:#46516a #111827;scrollbar-gutter:stable}
.panel-scroll::-webkit-scrollbar{width:7px}
.panel-scroll::-webkit-scrollbar-track{background:#111827}
.panel-scroll::-webkit-scrollbar-thumb{background:#46516a;border:2px solid #111827;border-radius:8px}
.panel-scroll::-webkit-scrollbar-thumb:hover{background:#65748f}
.generation-action{margin-top:18px;padding-top:10px;border-top:1px solid #29334b}
.generation-cost{margin:8px 0 0;text-align:center}
.suggestion-help{font-size:11px;margin:9px 0}
</style>

<style scoped>
.portrait-notice-entry{margin:0 0 16px}.image-panel .portrait-notice-entry button{padding:0;border:0;background:none;color:#a5b4fc;font-size:12px;text-decoration:underline;text-underline-offset:3px}.portrait-notice-entry button:focus-visible{outline:2px solid #a5b4fc;outline-offset:3px}
</style>
