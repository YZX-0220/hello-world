<template>
  <div class="image-api-settings">
    <header><span class="eyebrow">图片创作</span><h1>图片 API</h1><p>添加并管理自己的 Seedream API。支持文字生图、参考图创作与连续修改。</p></header>
    <p v-if="error" class="message error" role="alert">{{ error }}</p><p v-if="message" class="message" role="status">{{ message }}</p>

    <section class="settings-card">
      <div class="title-row"><h2>{{ editing ? '编辑图片 API' : '添加自备图片 API' }}</h2><button v-if="editing" type="button" class="quiet" @click="reset">取消编辑</button></div>
      <p class="hint">填写支持所选 Seedream 模型的方舟 API Key。保存后，可在「AI 生图」中切换使用。</p>
      <form @submit.prevent="save" autocomplete="off">
        <label>密钥类型<select v-model="apiType" :disabled="saving" @change="changeApiType"><option value="standard">普通 API</option><option value="subscription">订阅 API</option></select></label>
        <p class="hint">{{ apiType === 'standard' ? '使用方舟普通 API Key，费用按厂商 API 计费规则计算。' : '使用方舟订阅服务的专用 Key，消耗对应订阅额度。' }} 两种密钥不能混用，请按密钥所属服务选择。</p>
        <div class="form-grid"><label>显示名称<input v-model="form.display_name" required maxlength="80" placeholder="例如：我的图片创作通道" /></label><label>Seedream 模型<select v-model="form.model" required><option v-for="model in availableModels" :key="model.id" :value="model.id">{{ model.label }}</option></select></label></div>
        <label>API Key {{ editing && !requiresNewKey ? '（留空保持原密钥）' : requiresNewKey ? '（更换密钥类型后请填写对应密钥）' : '' }}<input v-model="form.api_key" type="password" :required="!editing || requiresNewKey" autocomplete="new-password" placeholder="输入你的 API Key" /></label>
        <button class="primary" :disabled="saving || !availableModels.some(model => model.id === form.model)">{{ saving ? '保存中…' : editing ? '保存修改' : '保存图片 API' }}</button>
      </form>
    </section>
    <div class="title-row list-heading"><h2>已保存的图片 API <span>{{ configs.length }}</span></h2><button class="quiet" :disabled="loading" @click="load">{{ loading ? '加载中…' : '刷新列表' }}</button></div>
    <p v-if="!configs.length" class="empty">{{ loading ? '正在加载…' : '还没有图片 API，请在上方添加自己的 API Key。' }}</p>
    <section v-for="config in configs" :key="config.id" class="settings-card config-card">
      <div class="title-row"><h2>{{ config.display_name }}</h2><span class="state">自备 · {{ modelApiType(config.model) === 'standard' ? '普通 API' : '订阅 API' }}</span></div><p class="model" :title="config.model">{{ modelLabel(config.model) }}</p><p>密钥：{{ config.key_hint || '••••••••' }}</p>
      <div class="actions"><button @click="edit(config)" :disabled="saving">编辑</button><button class="danger quiet" :disabled="saving || deleting === config.id" @click="confirmDelete = config.id">删除</button></div>
      <div v-if="confirmDelete === config.id" class="delete-confirm"><span>删除后无法用于新任务，已有生成记录会保留。</span><div class="actions"><button class="danger" :disabled="deleting === config.id" @click="remove(config)">{{ deleting === config.id ? '删除中…' : '确认删除' }}</button><button class="quiet" @click="confirmDelete = ''">取消</button></div></div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import request from '@/utils/request';
import type { ImageApiConfig, ImageApiType, ImageOptions } from '@/types/imageGeneration';
import { imageModelApiType, imageModelLabel, imageModelsForType } from '@/services/imageGeneration';
const options = ref<ImageOptions | null>(null), configs = ref<ImageApiConfig[]>([]);
const loading = ref(false), saving = ref(false), editing = ref<ImageApiConfig | null>(null), deleting = ref(''), confirmDelete = ref(''), error = ref(''), message = ref('');
const apiType = ref<ImageApiType>('standard');
const availableModels = computed(() => imageModelsForType(options.value?.models || [], apiType.value));
const modelApiType = (id: string) => imageModelApiType(options.value?.models || [], id);
const modelLabel = (id: string) => imageModelLabel(options.value?.models || [], id);
const requiresNewKey = computed(() => !!editing.value && modelApiType(editing.value.model) !== apiType.value);
function changeApiType() { form.model = availableModels.value[0]?.id || ''; form.api_key = ''; }
const form = reactive({ display_name: '', api_key: '', model: '' });
function reset() { editing.value = null; form.display_name = ''; form.api_key = ''; apiType.value = 'standard'; form.model = availableModels.value[0]?.id || ''; }
async function load() {
  loading.value = true; error.value = '';
  const results = await Promise.allSettled([request.get<unknown, ImageOptions>('/image-generation/options'), request.get<unknown, { items: ImageApiConfig[] }>('/image-api-configs')]);
  if (results[0].status === 'fulfilled') { options.value = results[0].value; if (!form.model) form.model = availableModels.value[0]?.id || ''; }
  else error.value = results[0].reason?.message || '图片选项加载失败';
  if (results[1].status === 'fulfilled') configs.value = results[1].value.items;
  else error.value = results[1].reason?.message || '图片配置加载失败';
  loading.value = false;
}
function edit(config: ImageApiConfig) { editing.value = config; form.display_name = config.display_name; form.api_key = ''; apiType.value = modelApiType(config.model); form.model = config.model; message.value = ''; window.scrollTo({ top: 0, behavior: 'smooth' }); }
async function save() {
  if (saving.value || !availableModels.value.some(model => model.id === form.model)) return;
  if (requiresNewKey.value && !form.api_key.trim()) { error.value = '请填写所选密钥类型对应的 API Key。'; return; }
  saving.value = true; error.value = ''; message.value = '';
  const body = { display_name: form.display_name.trim(), model: form.model, ...(form.api_key.trim() ? { api_key: form.api_key.trim() } : {}) };
  try {
    if (editing.value) await request.patch(`/image-api-configs/${editing.value.id}`, { ...body, expected_revision: editing.value.revision });
    else await request.post('/image-api-configs', body);
    reset(); await load(); message.value = '图片 API 已保存，可在工作台的「AI 生图」中选择。';
  } catch (err: any) { error.value = err.message || '保存失败，请重试'; }
  finally { form.api_key = ''; saving.value = false; }
}
async function remove(config: ImageApiConfig) {
  deleting.value = config.id; error.value = ''; message.value = '';
  try { await request.delete(`/image-api-configs/${config.id}`); if (editing.value?.id === config.id) reset(); await load(); confirmDelete.value = ''; message.value = '图片 API 已删除。'; }
  catch (err: any) { error.value = err.message || '删除失败'; }
  finally { deleting.value = ''; }
}
onMounted(load);
</script>
<style scoped>
.image-api-settings{color:#cbd5e1;font-size:13px}.eyebrow{font-size:11px;color:#a5b4fc;letter-spacing:1px}h1{font-size:25px;color:#f8fafc;margin:9px 0}header p{color:#94a3b8;line-height:1.8;margin:0 0 22px}h2{font-size:16px;font-weight:600;color:#f1f5f9;margin:0}.settings-card{padding:24px;background:#111827;border:1px solid #28344b;border-radius:12px;margin-bottom:20px}.title-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.settings-card p{line-height:1.7;color:#8fa0bb;font-size:12px}.state{padding:3px 8px;font-size:10px;border:1px solid #42516e;color:#a4b2c9;border-radius:5px}.state.available{color:#78d8b3;border-color:#27634f;background:#15372e}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}label{display:flex;flex-direction:column;gap:8px;margin:18px 0;font-size:12px;color:#bdc9db}input,select{box-sizing:border-box;width:100%;min-width:0;background:#1a2438;border:1px solid #34425e;border-radius:7px;color:#eef2ff;padding:11px;font:inherit;outline:none}input:focus,select:focus{border-color:#818cf8}.hint{font-size:12px;color:#8797b1;line-height:1.8}.image-api-settings button{padding:9px 14px;border:1px solid #3b4964;background:#233049;color:#d9e5f8;border-radius:7px;cursor:pointer;font:inherit}.image-api-settings button:disabled{opacity:.5;cursor:not-allowed}.image-api-settings .primary{background:#6366f1;border-color:#818cf8;color:white;padding:11px 22px;margin-top:8px}.image-api-settings .quiet{background:transparent;border-color:transparent;color:#a5b4fc}.list-heading{margin:28px 0 16px}.list-heading h2 span{font-size:12px;color:#6f829e;margin-left:7px}.model{font-family:monospace;overflow-wrap:anywhere}.revision{margin-left:10px;color:#687d99;font-size:11px}.actions{display:flex;gap:10px;margin-top:14px}.image-api-settings .danger{color:#fda4af}.delete-confirm{border-top:1px solid #34415a;margin-top:15px;padding-top:15px;font-size:12px;line-height:1.8}.message{padding:12px 15px;background:#152d30;border:1px solid #285f59;color:#8cddc6;border-radius:8px;line-height:1.7}.message.error{background:#38202a;border-color:#6a3644;color:#fda4af}.simulation{color:#f0ce88!important}.empty{padding:25px;color:#7d8da8;border:1px dashed #34415a;border-radius:10px;line-height:1.8}@media(max-width:650px){.form-grid{grid-template-columns:1fr;gap:0}.settings-card{padding:18px}}
</style>
