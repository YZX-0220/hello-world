<template>
  <div class="export-modal-backdrop" @click.self="$emit('close')">
    <div class="export-card">
      <div class="card-title-bar">
        <h3>导出剪辑成片 (MP4)</h3>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>

      <div class="card-body">
        <div class="spec-summary">
          <div class="summary-item">
            <span class="label">分辨率</span>
            <span class="val">{{ timeline.width }} × {{ timeline.height }}</span>
          </div>
          <div class="summary-item">
            <span class="label">基准帧率</span>
            <span class="val">{{ timeline.fps }} FPS</span>
          </div>
          <div class="summary-item">
            <span class="label">成片时长</span>
            <span class="val">{{ (timeline.duration_ms / 1000).toFixed(1) }} 秒</span>
          </div>
        </div>

        <div class="export-options-box">
          <!-- 默认必定执行项 -->
          <label class="opt-row mandatory">
            <input type="checkbox" checked disabled />
            <div>
              <strong>下载到本地电脑 (零流量消耗)</strong>
              <p>由前端浏览器直接完成本地 MP4 打包保存，不占云端带宽</p>
            </div>
          </label>

          <!-- Opt-in 自选转存云端项 -->
          <label class="opt-row opt-in">
            <input type="checkbox" v-model="saveToCloud" />
            <div>
              <strong>同时保存至云端资料库 (占用云存储配额)</strong>
              <p>通过华为云 OBS 直传归档至平台资料库，方便多端回看与再次调用</p>
            </div>
          </label>
        </div>

        <!-- 配额预检状态 -->
        <div v-if="saveToCloud && quota" class="quota-check-info">
          <span class="quota-text">
            当前资料库已用: {{ (quota.used_bytes / (1024 * 1024)).toFixed(1) }} MB / {{ quota.quota_gb }} GB
          </span>
          <span v-if="isOverQuota" class="warn-text">⚠️ 警告：当前剩余容量可能不足，超出将拦截上传！</span>
        </div>

        <div v-if="uploadError" class="err-tip-box">
          {{ uploadError }}
        </div>
      </div>

      <div class="card-footer">
        <button class="cancel-btn" @click="$emit('close')">取消</button>
        <button class="confirm-export-btn" :disabled="isProcessing" @click="handleExecuteExport">
          {{ isProcessing ? 'WebAV 客户端合成中...' : '开始本地合成并导出' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { libraryApi } from '../../services/libraryApi';
import type { TimelineDocument, StorageQuotaView } from '../../types/clip';

const props = defineProps<{
  timeline: TimelineDocument;
  quota: StorageQuotaView | null;
  onSynthesizeMp4: () => Promise<Blob>;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'exportCompleted'): void;
}>();

const saveToCloud = ref(false);
const isProcessing = ref(false);
const uploadError = ref('');

const isOverQuota = computed(() => {
  if (!props.quota) return false;
  return props.quota.usage_percent > 95;
});

async function handleExecuteExport() {
  isProcessing.value = true;
  uploadError.value = '';

  try {
    // 1. 调用 WebAV 纯前端混流并打包 MP4 Blob
    const mp4Blob = await props.onSynthesizeMp4();

    // 2. 必定执行：直接触发浏览器下载到本地
    const downloadUrl = URL.createObjectURL(mp4Blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `成片_${Date.now()}.mp4`;
    a.click();
    URL.revokeObjectURL(downloadUrl);

    // 3. 用户勾选（Opt-in）：执行两阶段直传华为云 OBS 归档入库
    if (saveToCloud.value) {
      // 预签名直传通道
      const buffer = await mp4Blob.arrayBuffer();
      const digest = await crypto.subtle.digest('SHA-256', buffer);
      const sha256 = Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');

      const intent = await libraryApi.requestUploadIntent({
        file_name: `剪辑成片_${Date.now()}.mp4`,
        byte_size: mp4Blob.size,
        mime_type: 'video/mp4',
        sha256,
        purpose: 'clip_export'
      });

      // OBS 直传 (PUT 零服务端中转)
      await fetch(intent.upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': 'video/mp4' },
        body: mp4Blob
      });

      // 回执通知
      await libraryApi.completeUpload(intent.asset_id);
    }

    emit('exportCompleted');
    emit('close');
  } catch (err: any) {
    uploadError.value = err?.message || '导出合成失败，请检查浏览器兼容性';
  } finally {
    isProcessing.value = false;
  }
}
</script>

<style scoped>
.export-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.export-card {
  width: 480px;
  background: #17151f;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
}

.card-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.card-title-bar h3 { font-size: 15px; color: #fff; margin: 0; }
.close-btn { background: transparent; border: none; font-size: 20px; color: #71717a; cursor: pointer; }

.card-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }

.spec-summary {
  display: flex;
  justify-content: space-around;
  background: rgba(255, 255, 255, 0.03);
  padding: 12px;
  border-radius: 8px;
}

.summary-item { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.summary-item .label { font-size: 11px; color: #71717a; }
.summary-item .val { font-size: 13px; color: #cbd5e1; font-weight: 600; font-family: monospace; }

.export-options-box { display: flex; flex-direction: column; gap: 10px; }

.opt-row {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
}

.opt-row.mandatory { border-color: rgba(99, 102, 241, 0.3); cursor: default; }
.opt-row strong { font-size: 13px; color: #e4e4e7; }
.opt-row p { font-size: 11px; color: #71717a; margin: 4px 0 0 0; }

.quota-check-info {
  font-size: 11px;
  color: #a1a1aa;
  background: rgba(255, 255, 255, 0.04);
  padding: 8px 12px;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.warn-text { color: #f59e0b; }
.err-tip-box { font-size: 12px; color: #ef4444; background: rgba(239, 68, 68, 0.1); padding: 8px 12px; border-radius: 6px; }

.card-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.cancel-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
}

.confirm-export-btn {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  border: none;
  color: #fff;
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.confirm-export-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>