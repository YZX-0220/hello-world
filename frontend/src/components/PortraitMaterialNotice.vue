<template>
  <Teleport to="body">
    <div v-if="open" class="portrait-notice-mask" @click.self="$emit('close')" @keydown.esc.stop.prevent="$emit('close')" @keydown.tab="trapFocus">
      <section class="portrait-notice-dialog" role="dialog" aria-modal="true" aria-labelledby="portrait-notice-title" aria-describedby="portrait-notice-summary">
        <header><h2 id="portrait-notice-title">人像素材须知</h2><button ref="closeButton" class="notice-close" aria-label="关闭人像素材须知" @click="$emit('close')">×</button></header>
        <div class="notice-scroll">
          <p id="portrait-notice-summary">使用人像素材前，请确认图片与视频通道的来源及配套关系。</p>
          <ol>
            <li><strong>图片 API 支持范围</strong><p>当前图片生成功能仅支持火山方舟的 API 密钥。</p></li>
            <li><strong>人像来源</strong><p>在当前支持的视频链路中，请使用 AI 生成的人像素材，避免上传真实人物照片作为人像生成素材。</p></li>
            <li><strong>通道配套</strong><p>图片与视频需在同一方舟账号下配套使用；使用订阅 API 时，也应使用该账号内配套的订阅通道。同服务商或同套餐名不代表同源。</p></li>
            <li><strong>平台通道</strong><p>选择平台默认图片通道生成人像后，请搭配平台视频体验通道使用；切换到自备视频 API 时，请改用该账号下配套的图片 API 重新生成。</p></li>
            <li><strong>自备通道</strong><p>自行配置视频 API 时，请同时配置该方舟账号下配套的图片 API，并用它生成人像；不配套可能被厂商拒绝。</p></li>
            <li><strong>保留原始图片</strong><p>优先使用文生图原始结果并直接插入画布，避免压缩或二次编辑。受信产物目前有 30 天有效期；继续改图后的产物是否受信，以厂商规则为准。</p></li>
          </ol>
          <p class="notice-footer">来源符合要求后，仍需通过厂商内容审核。</p>
          <a class="official-rules" href="https://docs.volcengine.com/docs/ark/seedance-portrait-asset-guide?lang=zh" target="_blank" rel="noopener noreferrer">查看厂商官方规则 ↗</a>
        </div>
      </section>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';
const props = defineProps<{ open: boolean }>();
defineEmits<{ close: [] }>();
const closeButton = ref<HTMLButtonElement | null>(null);
function trapFocus(event: KeyboardEvent) {
  const dialog = closeButton.value?.closest('section');
  const elements = dialog?.querySelectorAll<HTMLElement>('button,a[href]');
  if (!elements?.length) return;
  const first = elements[0], last = elements[elements.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
}
let previousFocus: HTMLElement | null = null;
watch(() => props.open, async open => {
  if (open) { previousFocus = document.activeElement as HTMLElement; await nextTick(); closeButton.value?.focus(); }
  else if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
});
</script>
<style scoped>
.portrait-notice-mask{position:fixed;inset:0;z-index:1900;display:flex;align-items:center;justify-content:center;padding:24px;background:#020617b8;backdrop-filter:blur(4px)}
.portrait-notice-dialog{display:flex;flex-direction:column;width:min(540px,100%);max-height:85dvh;min-height:0;background:#151b29;border:1px solid #3b465f;border-radius:15px;color:#dbe4f3;box-shadow:0 24px 90px #0009}
header{display:flex;align-items:center;justify-content:space-between;padding:19px 24px;border-bottom:1px solid #2d374e;flex-shrink:0}
h2{font-size:18px;margin:0;font-weight:600}.notice-close{border:0;background:transparent;color:#a7b5ce;font-size:26px;cursor:pointer;padding:0 4px}.notice-close:focus-visible{outline:2px solid #a5b4fc;outline-offset:3px;border-radius:4px}
.notice-scroll{overflow:auto;min-height:0;padding:8px 24px 23px;scrollbar-width:thin;scrollbar-color:#46516a #151b29;font-size:13px;line-height:1.85}.notice-scroll>p{color:#9eafc9}ol{padding-left:20px;margin:18px 0}li{padding-left:4px;margin:17px 0}li::marker{color:#a5b4fc}strong{font-weight:500;color:#c7d2fe}li p{margin:4px 0 0;color:#b3c1d7}.notice-footer{border-top:1px solid #2d374e;padding-top:15px;margin:18px 0 0;font-size:12px}.notice-scroll::-webkit-scrollbar{width:6px}.notice-scroll::-webkit-scrollbar-thumb{background:#46516a;border-radius:6px}
.official-rules{display:inline-block;margin-top:12px;color:#a5b4fc;font-size:12px;text-underline-offset:3px}
@media(max-width:600px){.portrait-notice-mask{padding:16px}header{padding:17px 20px}.notice-scroll{padding:8px 20px 20px}}
</style>
