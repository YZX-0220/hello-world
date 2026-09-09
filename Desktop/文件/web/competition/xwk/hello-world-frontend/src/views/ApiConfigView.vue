<template>
  <div class="page">
    <div class="head">
      <h2>添加视频 API</h2>
      <p class="sub">选择协议后，只需填写该协议真正需要的信息。密钥加密保存，页面只显示末四位。</p>
      <button class="back" @click="$router.back()">返回</button>
    </div>

    <div class="card">
      <div class="row">
        <div class="grow">
          <label>配置名称 <span class="req">*</span></label>
          <input v-model="form.display_name" placeholder="我的视频接口" maxlength="40">
        </div>
        <div class="grow">
          <label>接口协议 <span class="req">*</span></label>
          <select v-model="selectedProto" @change="onProtoChange">
            <option v-for="p in presets" :key="p.code" :value="p.code">{{ p.label }}</option>
          </select>
          <div class="hint">{{ currentProtocol?.description }}</div>
        </div>
      </div>

      <div class="row">
        <div class="grow">
          <label>接口来源 <span class="req">*</span></label>
          <div class="radios">
            <label v-for="s in allowedSources" :key="s" class="radio">
              <input type="radio" :value="s" v-model="form.source_type">{{ s === 'official' ? '官方接口' : '兼容中转站' }}
            </label>
          </div>
        </div>
        <div v-if="templateRequired" class="grow">
          <label>协议模板 <span class="req">*</span></label>
          <div class="radios">
            <label v-for="m in templateModes" :key="m.value" class="radio">
              <input type="radio" :value="m.value" v-model="form.template_mode">{{ m.label }}
            </label>
          </div>
          <div class="hint">内置模板按官方约定（template_code 固定为 v1_videos_json_v1）；用户自定义模板可完全按你的接口文档定制提交与轮询。</div>
        </div>
      </div>

      <div v-if="templateRequired && form.template_mode === 'custom'" class="custombox">
        <div class="customtitle">用户自定义模板</div>

        <div class="row">
          <div class="grow">
            <label>提交接口路径 <span class="req">*</span></label>
            <input v-model="form.submit_path" placeholder="如 /v1/videos/generate">
            <div class="hint">相对路径，创建任务接口</div>
          </div>
          <div class="grow">
            <label>提交方法</label>
            <select v-model="form.submit_method">
              <option value="GET">GET</option>
              <option value="POST">POST</option>
            </select>
            <div class="hint">请求方法，默认 POST</div>
          </div>
        </div>

        <div class="row">
          <div class="grow">
            <label>提交请求体模板 <span class="req">*</span></label>
            <textarea v-model="form.request_template_json" rows="5" placeholder='{"model":"{model}","prompt":"{prompt}","duration":{duration_seconds}}'></textarea>
            <div class="hint">怎么把提示词/模型/时长/素材放进请求体。支持占位符：{model} {prompt} {duration_seconds} {aspect_ratio} {resolution} {first_frame_url} {last_frame_url} {reference_image_urls} {source_video_url} {audio_url} {generation_options}</div>
          </div>
        </div>

        <div class="row">
          <div class="grow">
            <label>任务ID字段路径 <span class="req">*</span></label>
            <input v-model="form.task_id_path" placeholder="如 data.task_id">
            <div class="hint">提交响应里任务ID在哪</div>
          </div>
          <div class="grow">
            <label>查询接口路径 <span class="req">*</span></label>
            <input v-model="form.poll_path" placeholder="如 /v1/videos/tasks/{task_id}">
            <div class="hint">查询任务状态；{task_id} 自动替换成任务ID</div>
          </div>
        </div>

        <div class="row">
          <div class="grow">
            <label>查询方法</label>
            <select v-model="form.poll_method">
              <option value="GET">GET</option>
              <option value="POST">POST</option>
            </select>
            <div class="hint">请求方法，默认 GET</div>
          </div>
          <div class="grow">
            <label>状态字段路径 <span class="req">*</span></label>
            <input v-model="form.status_path" placeholder="如 data.status">
            <div class="hint">查询响应状态在哪</div>
          </div>
        </div>

        <div class="row">
          <div class="grow">
            <label>状态映射 <span class="req">*</span></label>
            <textarea v-model="form.status_map" rows="4" placeholder='{"queued":"queued","running":"running","succeeded":"succeeded","failed":"failed","cancelled":"cancelled"}'></textarea>
            <div class="hint">远端状态值→本站状态；本站用 queued/running/succeeded/failed/cancelled；未列出的原样透传</div>
          </div>
          <div class="grow">
            <label>结果URL字段路径 <span class="req">*</span></label>
            <input v-model="form.result_url_path" placeholder="如 data.video_url">
            <div class="hint">查询响应里成品视频地址，用于下载</div>
          </div>
        </div>
      </div>

      <div class="row">
        <div class="grow">
          <label>远程模型 ID <span class="req">*</span></label>
          <select v-if="profiles.length" v-model="form.remote_model_id">
            <option value="">请选择模型</option>
            <option v-for="m in profiles" :key="m.code" :value="m.remote_model_id">{{ m.label }}</option>
          </select>
          <input v-else v-model="form.remote_model_id" placeholder="填写接口文档中的真实模型名">
        </div>
        <div class="grow">
          <label>Base URL{{ form.source_type === 'relay' ? '（中转必填）' : '' }}</label>
          <input v-model="form.base_url" :disabled="form.source_type === 'official'" :placeholder="officialBaseUrl || 'https://…（必须 https）'">
          <div class="hint">官方来源使用官方地址（不可改）；中转来源需填写。</div>
        </div>
      </div>

      <div v-for="f in authFields" :key="'a-' + f.name" class="row">
        <div class="grow">
          <label>{{ f.label }}<template v-if="f.required"> <span class="req">*</span></template></label>
          <div class="keyrow">
            <input :type="f.secret ? (showKey ? 'text' : 'password') : 'text'" v-model="form.auth[f.name]" :placeholder="f.placeholder || ''">
            <button v-if="f.secret" type="button" class="toggle" @click="showKey = !showKey">{{ showKey ? '隐藏' : '显示' }}</button>
          </div>
        </div>
      </div>

      <div v-for="f in optionFields" :key="'o-' + f.name" class="row">
        <div class="grow">
          <label>{{ f.label }}</label>
          <input v-model="form.options[f.name]" :placeholder="f.placeholder || ''">
        </div>
      </div>

      <div v-if="form.source_type === 'relay'" class="risk">
        <label class="radio">
          <input type="checkbox" v-model="form.relay_risk_accepted">
          我理解素材会发送给第三方中转站，接受此风险（中转必选）
        </label>
      </div>

      <div class="actions">
        <button class="secondary" :disabled="isTesting" @click="testConnection">
          {{ isTesting ? '检测中…' : '检测连接' }}
        </button>
        <span class="status" :class="'st-' + verificationStatus">
          {{ testMessage || (verificationStatus === 'verified' ? '已验证' : verificationStatus === 'invalid' ? '验证失败' : '待检测') }}
        </span>
      </div>

      <div class="actions">
        <button class="primary" :disabled="isSaving" @click="saveConfig">
          {{ isSaving ? '保存中…' : '保存视频 API 配置' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import request from '../utils/request';

const router = useRouter();

const presets = ref<any[]>([]);
const profiles = ref<any[]>([]);
const selectedProto = ref('');
const showKey = ref(false);
const isTesting = ref(false);
const isSaving = ref(false);
const testMessage = ref('');
const verificationStatus = ref<'unverified' | 'verified' | 'invalid'>('unverified');

const form = reactive<any>({
  display_name: '',
  source_type: 'relay',
  template_code: null,
  template_mode: 'builtin',
  // 用户自定义模板字段
  submit_path: '',
  submit_method: 'POST',
  request_template_json: '',
  task_id_path: '',
  poll_path: '',
  poll_method: 'GET',
  status_path: '',
  status_map: '{"queued":"queued","running":"running","succeeded":"succeeded","failed":"failed","cancelled":"cancelled"}',
  result_url_path: '',
  base_url: '',
  remote_model_id: '',
  auth: {},
  options: {},
  capability_profile_code: null,
  relay_risk_accepted: false,
});

const currentProtocol = computed(() => presets.value.find((p) => p.code === selectedProto.value));
const allowedSources = computed(() => (currentProtocol.value ? currentProtocol.value.source_types : []));
const authFields = computed(() => (currentProtocol.value ? currentProtocol.value.auth_fields : []));
const optionFields = computed(() => (currentProtocol.value ? currentProtocol.value.option_fields : []));
const templateRequired = computed(() => (currentProtocol.value ? currentProtocol.value.template_required : false));
const officialBaseUrl = computed(() => currentProtocol.value?.official_base_url || '');

const templateModes = [
  { value: 'builtin', label: '内置模板' },
  { value: 'custom', label: '用户自定义模板' },
];

const STATUS_MAP_DEFAULT = '{"queued":"queued","running":"running","succeeded":"succeeded","failed":"failed","cancelled":"cancelled"}';

function safeParseJson(s: string): any {
  const t = (s || '').trim();
  if (!t) return null;
  try { return JSON.parse(t); } catch { return null; }
}

function isValidJson(s: string): boolean {
  const t = (s || '').trim();
  if (!t) return false;
  try { JSON.parse(t); return true; } catch { return false; }
}

function customTemplateValidation(): string | null {
  if (!(form.template_mode === 'custom' && templateRequired.value)) return null;
  if (!form.submit_path.trim()) return '请填写提交接口路径 submit_path';
  if (!form.request_template_json.trim()) return '请填写提交请求体模板 request_template_json';
  if (!isValidJson(form.request_template_json)) return '请求体模板不是合法 JSON，请检查';
  if (!form.task_id_path.trim()) return '请填写任务ID字段路径 task_id_path';
  if (!form.poll_path.trim()) return '请填写查询接口路径 poll_path';
  if (!form.status_path.trim()) return '请填写状态字段路径 status_path';
  if (!form.status_map.trim()) return '请填写状态映射 status_map';
  if (!isValidJson(form.status_map)) return '状态映射不是合法 JSON，请检查';
  if (!form.result_url_path.trim()) return '请填写结果URL字段路径 result_url_path';
  return null;
}

async function loadPresets() {
  try {
    const res: any = await request.get('/video-api-presets');
    presets.value = res.items || [];
  } catch (e) {
    presets.value = [
      { code: 'generic_async_json_v1', label: '通用异步 JSON 视频接口', description: '通用中转协议', source_types: ['official', 'relay'], supports_custom_base_url: true, template_required: true, official_base_url: null },
      { code: 'ark_seedance_v1', label: '火山方舟 Seedance 视频生成', description: '官方原生协议', source_types: ['official'], supports_custom_base_url: false, template_required: false, official_base_url: 'https://ark.cn-beijing.volces.com' },
    ];
  }
  if (presets.value.length) {
    selectedProto.value = presets.value[0].code;
    onProtoChange();
  }
}

async function loadModels() {
  if (!selectedProto.value) return;
  try {
    const res: any = await request.get('/video-model-profiles', { params: { protocol_code: selectedProto.value } });
    profiles.value = res.items || [];
  } catch (e) {
    profiles.value = [];
  }
}

function defaultSource(p: any) {
  if (!p) return 'relay';
  // 官方原生协议（无自定义地址）→ official；通用中转协议 → relay
  return p.supports_custom_base_url ? 'relay' : 'official';
}

function onProtoChange() {
  const p = currentProtocol.value;
  const src = allowedSources.value.includes(defaultSource(p)) ? defaultSource(p) : (allowedSources.value[0] || 'relay');
  form.source_type = src;
  form.template_code = templateRequired.value ? 'v1_videos_json_v1' : null;
  // 切换到通用协议时，模板模式默认回到内置模板，并重置自定义字段
  form.template_mode = 'builtin';
  form.submit_path = '';
  form.submit_method = 'POST';
  form.request_template_json = '';
  form.task_id_path = '';
  form.poll_path = '';
  form.poll_method = 'GET';
  form.status_path = '';
  form.status_map = STATUS_MAP_DEFAULT;
  form.result_url_path = '';
  form.base_url = form.source_type === 'official' ? officialBaseUrl.value : '';
  // 初始化 auth / option 字段的 key
  authFields.value.forEach((f) => { if (!(f.name in form.auth)) form.auth[f.name] = ''; });
  optionFields.value.forEach((f) => { if (!(f.name in form.options)) form.options[f.name] = ''; });
  form.remote_model_id = '';
  loadModels();
}

function payload() {
  const mp = profiles.value.find((m) => m.remote_model_id === form.remote_model_id);
  const capability = mp ? mp.code : (form.capability_profile_code || null);
  const isCustom = templateRequired.value && form.template_mode === 'custom';
  const out: any = {
    display_name: form.display_name.trim(),
    source_type: form.source_type,
    protocol_code: selectedProto.value,
    template_code: form.template_code,
    base_url: form.source_type === 'official' ? officialBaseUrl.value : form.base_url.trim(),
    remote_model_id: form.remote_model_id.trim(),
    auth: form.auth,
    options: form.options,
    capability_profile_code: capability,
    relay_risk_accepted: form.source_type === 'relay' ? form.relay_risk_accepted : false,
  };
  if (templateRequired.value) {
    out.template_mode = isCustom ? 'custom' : 'builtin';
  }
  if (isCustom) {
    // 空字符串不提交成空值：仅当非空才带出；两个 JSON 字段解析为对象（非法 JSON 交还给校验函数拦截）
    if (form.submit_path.trim()) out.submit_path = form.submit_path.trim();
    if (form.submit_method) out.submit_method = form.submit_method;
    const reqJson = safeParseJson(form.request_template_json);
    if (reqJson !== null) out.request_template_json = reqJson;
    if (form.task_id_path.trim()) out.task_id_path = form.task_id_path.trim();
    if (form.poll_path.trim()) out.poll_path = form.poll_path.trim();
    if (form.poll_method) out.poll_method = form.poll_method;
    if (form.status_path.trim()) out.status_path = form.status_path.trim();
    const statusMap = safeParseJson(form.status_map);
    if (statusMap !== null) out.status_map = statusMap;
    if (form.result_url_path.trim()) out.result_url_path = form.result_url_path.trim();
  }
  return out;
}

async function testConnection() {
  if (!form.display_name.trim()) { testMessage.value = '请先填写配置名称'; return; }
  if (!form.remote_model_id.trim()) { testMessage.value = '请先填写/选择模型 ID'; return; }
  const customErr = customTemplateValidation();
  if (customErr) { testMessage.value = customErr; verificationStatus.value = 'invalid'; return; }
  isTesting.value = true;
  testMessage.value = '正在检测…';
  try {
    const p: any = payload(); delete p.display_name; // 检测接口不接受配置名称
    const res: any = await request.post('/video-api-configs/test', p);
    verificationStatus.value = res.verification_status;
    testMessage.value = res.message || '检测完成';
  } catch (err: any) {
    verificationStatus.value = 'invalid';
    testMessage.value = err.message || '检测失败';
  } finally {
    isTesting.value = false;
  }
}

async function saveConfig() {
  if (!form.display_name.trim()) { alert('请填写配置名称'); return; }
  if (!form.remote_model_id.trim()) { alert('请填写/选择模型 ID'); return; }
  const secretKey = authFields.value.find((f) => f.secret);
  if (secretKey && !form.auth[secretKey.name]) { alert('请填写 ' + secretKey.label); return; }
  if (form.source_type === 'relay' && !form.relay_risk_accepted) { alert('请确认中转风险'); return; }
  const customErr = customTemplateValidation();
  if (customErr) { alert(customErr); return; }
  isSaving.value = true;
  try {
    await request.post('/video-api-configs', payload());
    alert('配置已加密保存！');
    router.push('/workspace');
  } catch (err: any) {
    alert(err.message || '保存失败');
  } finally {
    isSaving.value = false;
  }
}

onMounted(loadPresets);
</script>

<style scoped>
.page { min-height: 100vh; background: #090c14; color: #e2e8f0; padding: 32px; }
.head { max-width: 860px; margin: 0 auto 20px; }
.head h2 { margin: 0; }
.head .sub { color: #94a3b8; margin: 6px 0 0; font-size: 14px; }
.back { margin-top: 12px; background: transparent; border: none; color: #94a3b8; cursor: pointer; }
.card { max-width: 860px; margin: 0 auto; background: #111624; border: 1px solid #1e2740; border-radius: 14px; padding: 24px 28px; }
.row { display: flex; gap: 18px; margin-bottom: 16px; flex-wrap: wrap; }
.grow { flex: 1; min-width: 240px; }
label { font-size: 13px; color: #cbd5e1; margin-bottom: 6px; display: block; }
.req { color: #ef4444; }
input, select { width: 100%; height: 42px; background: #182030; border: 1px solid #28354f; border-radius: 8px; padding: 0 12px; color: #e2e8f0; font-size: 14px; }
input:disabled { opacity: .6; }
textarea { width: 100%; background: #182030; border: 1px solid #28354f; border-radius: 8px; padding: 10px 12px; color: #e2e8f0; font-size: 14px; font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; resize: vertical; }
.hint { color: #64748b; font-size: 12px; margin-top: 4px; }
.radios { display: flex; gap: 20px; height: 42px; align-items: center; }
.radio { display: inline-flex; align-items: center; gap: 6px; color: #e2e8f0; font-size: 14px; }
.custombox { border: 1px dashed #2c3a5c; border-radius: 10px; padding: 16px 16px 4px; margin-bottom: 16px; background: rgba(24, 32, 48, .35); }
.customtitle { font-size: 13px; color: #94a3b8; margin-bottom: 12px; font-weight: 600; }
.radio input { width: auto; height: auto; }
.keyrow { display: flex; gap: 8px; }
.keyrow input { flex: 1; }
.toggle { background: #1e273b; border: 1px solid #334155; color: #cbd5e1; padding: 0 12px; border-radius: 8px; cursor: pointer; }
.risk { margin: 12px 0; color: #cbd5e1; font-size: 13px; }
.actions { display: flex; align-items: center; gap: 14px; margin-top: 14px; }
.secondary { background: #1e273b; border: 1px solid #334155; color: #e2e8f0; padding: 10px 18px; border-radius: 8px; cursor: pointer; }
.primary { background: #6366f1; border: none; color: #fff; padding: 12px 26px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; }
.primary:disabled, .secondary:disabled { opacity: .5; cursor: default; }
.status { font-size: 13px; color: #94a3b8; }
.st-verified { color: #10b981; }
.st-invalid { color: #ef4444; }
.st-unverified { color: #f59e0b; }
</style>
