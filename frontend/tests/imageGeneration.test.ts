import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createCanvas, normalizeCanvas } from '../src/services/canvasState.ts';
import { createImageNode, imageAlreadyInserted, imageDraftKey, imageEditDraft, imageInsertionPoint, imageJobActive, imageJobBlocksGeneration, imageDisplayModel, imageModelApiType, imageModelLabel, imageModelsForType, imageSourceDraft, imageSourceParent, imageSubmission, imageSuggestionRequest, imageTextOnlyDraft, readImageDraft, sanitizeImageReferences } from '../src/services/imageGeneration.ts';
import type { ImageJob } from '../src/types/imageGeneration.ts';

const job: ImageJob = { id: 'image-job', conversation_id: 'conv', api_config_id: 'platform', prompt: '上海雨夜', aspect_ratio: '16:9', model: 'seedream', channel_label: '平台默认', account_label: '', linked_video_api_config_id: null, config_revision: 1, status: 'succeeded', asset_id: 'asset-1', content_url: '/api/v1/assets/asset-1/content', download_url: '/api/v1/assets/asset-1/download', error_message: null, created_at: '', updated_at: '', simulation: false };

test('generated image is a persisted ordinary asset node without replacing source', () => {
  const canvas = createCanvas('conv');
  const source = structuredClone(canvas.nodes[1]!);
  const generated = createImageNode(canvas.nodes, job, 'new-image', source)!;
  canvas.nodes.push(generated);
  assert.deepEqual(canvas.nodes[1], source);
  const recovered = normalizeCanvas(JSON.parse(JSON.stringify(canvas)));
  assert.equal(recovered.nodes[2]?.asset_id, 'asset-1');
  assert.equal(recovered.nodes[2]?.type, 'image');
  assert.equal(recovered.nodes[2]?.url, job.content_url);
  assert.equal(recovered.nodes[2]?.job_id, job.id);
  assert.equal(recovered.nodes[2]?.content, `生图描述（用户提示词，并非看图结论）：\n${job.prompt}`);
  assert.equal(imageAlreadyInserted(recovered.nodes, job), true);
  assert.equal(createImageNode(recovered.nodes, job, 'duplicate'), null);
  assert.equal(createImageNode(recovered.nodes, { ...job, id: 'another-job' }, 'duplicate-asset'), null);
});
test('new image insertion uses free canvas space and skips source-adjacent occupied cards', () => {
  const nodes = createCanvas('conv').nodes;
  nodes.push({ id: 'video', type: 'video', title: '已有视频', x: 840, y: 180 });
  const rightmost = Math.max(...nodes.map(node => node.x + 248));
  const toolbar = imageInsertionPoint(nodes);
  assert.ok(toolbar.x > rightmost);
  const sourceRelative = imageInsertionPoint(nodes, nodes[0]);
  for (const node of nodes) {
    const height = node.type === 'text' ? 300 : node.type === 'image' ? 280 : 240;
    assert.ok(sourceRelative.x >= node.x + 248 + 72 || sourceRelative.x + 248 + 72 <= node.x
      || sourceRelative.y >= node.y + height + 72 || sourceRelative.y + 280 + 72 <= node.y);
  }
  assert.deepEqual(imageInsertionPoint([]), { x: 180, y: 200 });
});
test('unfinished images cannot be inserted', () => {
  for (const status of ['failed', 'queued', 'storage_failed', 'unknown', 'unknown_acknowledged'] as const) assert.equal(createImageNode([], { ...job, status }, 'new'), null);
  assert.equal(createImageNode([], { ...job, asset_id: null }, 'new'), null);
  assert.equal(imageJobActive(job), false);
});
test('unknown results stop polling and block new generations until explicitly acknowledged', () => {
  for (const status of ['queued', 'generating', 'saving'] as const) {
    assert.equal(imageJobActive({ ...job, status }), true);
    assert.equal(imageJobBlocksGeneration({ ...job, status }), true);
  }
  assert.equal(imageJobActive({ ...job, status: 'unknown' }), false);
  assert.equal(imageJobBlocksGeneration({ ...job, status: 'unknown' }), true);
  for (const status of ['unknown_acknowledged', 'failed', 'cancelled', 'storage_failed', 'succeeded'] as const) {
    assert.equal(imageJobActive({ ...job, status }), false);
    assert.equal(imageJobBlocksGeneration({ ...job, status }), false);
  }
});
test('draft recovery keeps exact ambiguous submission while discarding unrecognized fields and secrets', () => {
  const body = { conversation_id: 'conv', api_config_id: 'byok', prompt: '原始描述', aspect_ratio: '1:1', source_node_id: 'node' };
  const draft = readImageDraft(JSON.stringify({ prompt: '原始描述', api_config_id: 'byok', aspect_ratio: '1:1', api_key: 'must-not-persist', pending: { key: 'same-key', body: { ...body, api_key: 'must-not-persist' } } }));
  assert.deepEqual(draft.pending, { key: 'same-key', body });
  assert.ok(!JSON.stringify(draft).includes('must-not-persist'));
  assert.notEqual(imageDraftKey('account-A', 'conv'), imageDraftKey('account-B', 'conv'));
  assert.notEqual(imageDraftKey('account-A', 'conv'), imageDraftKey('account-A', 'other'));
  assert.equal(readImageDraft('malformed').prompt, '');
});
test('reference drafts recover full pending edit inputs and watermark while legacy pending bodies stay unchanged', () => {
  const draft = readImageDraft(null);
  assert.equal(draft.watermark, false);
  draft.prompt = '让背景更明亮'; draft.parent_job_id = 'parent-job';
  draft.reference_images = [{ asset_id: 'parent-image', content_url: '/api/v1/assets/parent-image/content?thumbnail=raw', original_name: '上一版' }];
  const body = imageSubmission(draft, 'conv');
  draft.pending = { key: 'immutable-key', body };
  const recovered = readImageDraft(JSON.stringify(draft));
  assert.deepEqual(recovered.pending, { key: 'immutable-key', body });
  assert.deepEqual(recovered.reference_images, draft.reference_images);
  assert.equal(recovered.parent_job_id, 'parent-job');
  assert.equal(body.watermark, false);
  draft.reference_images.push({ asset_id: 'new-image', content_url: '/new', original_name: '新图' });
  draft.watermark = true;
  assert.deepEqual(body.reference_asset_ids, ['parent-image']);
  assert.equal(body.watermark, false);
  const legacy = readImageDraft(JSON.stringify({ prompt: 'old', pending: { key: 'old-key', body: { conversation_id: 'conv', api_config_id: 'platform', prompt: 'old', aspect_ratio: '1:1' } } }));
  assert.ok(!Object.hasOwn(legacy.pending!.body, 'watermark'));
  assert.ok(!Object.hasOwn(legacy.pending!.body, 'reference_asset_ids'));
});
test('reference selection deduplicates and bounds four images without carrying secret metadata', () => {
  const references = sanitizeImageReferences([{ asset_id: 'a', content_url: '/a', original_name: 'A', api_key: 'secret' },
    { asset_id: 'a', content_url: '/duplicate' }, null, { asset_id: 'b' }, ...['b', 'c', 'd', 'e'].map(asset_id => ({ asset_id, content_url: '/' + asset_id }))]);
  assert.deepEqual(references.map(image => image.asset_id), ['a', 'b', 'c', 'd']);
  assert.ok(!JSON.stringify(references).includes('secret'));
});
test('continuous editing switches parent to latest successful image and text-only reset clears all references', () => {
  let draft = readImageDraft(null); draft.prompt = '原提示词';
  draft = imageEditDraft(draft, job)!;
  assert.equal(draft.prompt, '');
  assert.equal(draft.parent_job_id, job.id);
  assert.deepEqual(draft.reference_images.map(image => image.asset_id), [job.asset_id]);
  draft.prompt = '继续改成黄昏';
  const second = { ...job, id: 'second-job', asset_id: 'second-image', content_url: '/second' };
  draft = imageEditDraft(draft, second)!;
  assert.equal(draft.parent_job_id, 'second-job');
  assert.deepEqual(draft.reference_images.map(image => image.asset_id), ['second-image']);
  draft.prompt = '保留文字描述';
  const pure = imageTextOnlyDraft(draft);
  assert.equal(pure.parent_job_id, null);
  assert.deepEqual(pure.reference_images, []);
  assert.equal(pure.prompt, '保留文字描述');
  assert.equal(imageEditDraft(draft, { ...job, status: 'failed' }), null);
  draft.pending = { key: 'pending', body: imageSubmission(draft, 'conv') };
  assert.equal(imageEditDraft(draft, job), null);
  assert.equal(imageTextOnlyDraft(draft), draft);
});
test('generated-node entry keeps lineage and repeated opening preserves an existing edit draft', () => {
  const source = createImageNode([], job, 'source-node')!;
  const initial = readImageDraft(null); initial.prompt = '先保留我的修改描述';
  const fromNode = imageSourceDraft(initial, source, [job]);
  assert.equal(fromNode.parent_job_id, job.id);
  assert.equal(fromNode.reference_images[0]?.asset_id, job.asset_id);
  assert.equal(fromNode.prompt, initial.prompt);
  const stored = readImageDraft(JSON.stringify(fromNode));
  assert.equal(imageSourceDraft(stored, source, [job]), stored);
  const laterJob = { ...job, id: 'later-job', asset_id: 'later-asset', content_url: '/later' };
  const editing = imageEditDraft(stored, laterJob)!; editing.prompt = '继续改新版本';
  assert.equal(imageSourceDraft(editing, source, [job, laterJob]), editing);
  assert.equal(editing.parent_job_id, 'later-job');
  assert.deepEqual(editing.reference_images.map(image => image.asset_id), ['later-asset']);
  const deliberateReset = imageSourceDraft(editing, source, [job], true);
  assert.equal(deliberateReset.parent_job_id, job.id);
  assert.equal(deliberateReset.reference_images[0]?.asset_id, job.asset_id);
  assert.equal(deliberateReset.prompt, '继续改新版本');
  assert.ok(!Object.hasOwn(imageSubmission(deliberateReset, 'conv'), 'source_entry'));
});
test('ordinary uploads and re-uploaded generated nodes do not inherit a stale parent job', () => {
  const source = createImageNode([], job, 'source-node')!;
  const draft = imageSourceDraft(readImageDraft(null), source, []);
  assert.equal(draft.parent_job_id, null);
  assert.equal(imageSourceParent(source, [job]), job.id);
  const replaced = { ...source, asset_id: 'uploaded-replacement' };
  const updated = imageSourceDraft(draft, replaced, [job]);
  assert.equal(updated.parent_job_id, null);
  assert.equal(updated.reference_images[0]?.asset_id, 'uploaded-replacement');
  assert.equal(imageSourceParent(source, [{ ...job, status: 'failed' }]), null);
});


test('reference-only and parent-only drafts can request advice without changing the draft or generation prompt', () => {
  assert.equal(imageSuggestionRequest(readImageDraft(null), 'conv'), null);
  const referenceOnly = { ...readImageDraft(null), prompt: '  ', reference_images: [{ asset_id: 'reference', content_url: '/reference', original_name: '参考图' }] };
  const parentOnly = { ...readImageDraft(null), parent_job_id: 'previous-version' };
  for (const draft of [referenceOnly, parentOnly]) {
    const before = structuredClone(draft);
    const request = imageSuggestionRequest(draft, 'conv')!;
    assert.ok(request.prompt.includes('请观察参考图片'));
    assert.deepEqual(request.reference_asset_ids, draft.reference_images.map(image => image.asset_id));
    assert.equal(request.parent_job_id, draft.parent_job_id);
    assert.equal(request.watermark, false);
    assert.deepEqual(draft, before);
    assert.equal(imageSubmission(draft, 'conv').prompt, '');
    draft.prompt = '保留人物，改成黄昏';
    assert.equal(imageSuggestionRequest(draft, 'conv')?.prompt, draft.prompt);
    assert.equal(before.prompt.trim(), '');
  }
});


test('API key types keep separate model choices and legacy configurations remain subscription models', () => {
  const models = [
    { id: 'doubao-seedream-5-0-pro-260628', label: 'Seedream 5.0 Pro', api_type: 'standard' as const },
    { id: 'doubao-seedream-5-0-flash-260915', label: 'Seedream 5.0 Flash', api_type: 'standard' as const },
    { id: 'subscription-pro', label: 'Seedream 5.0 Pro', api_type: 'subscription' as const },
    { id: 'legacy-flash', label: 'Seedream 5.0 Flash' },
  ];
  assert.deepEqual(imageModelsForType(models, 'standard').map(model => model.id), models.slice(0, 2).map(model => model.id));
  assert.deepEqual(imageModelsForType(models, 'subscription').map(model => model.id), ['subscription-pro', 'legacy-flash']);
  assert.equal(imageModelApiType(models, models[0]!.id), 'standard');
  assert.equal(imageModelApiType(models, 'legacy-flash'), 'subscription');
  assert.equal(imageModelApiType(models, 'older-removed-id'), 'subscription');
  assert.equal(imageModelLabel(models, models[0]!.id), 'Seedream 5.0 Pro');
  assert.equal(imageModelLabel([], 'doubao-seedream-5-0-flash-260915'), 'Seedream 5.0 Flash');
  assert.equal(imageModelLabel([], 'unknown-historical-model'), 'Seedream 图片模型');
});


test('all new generation and suggestion requests disable watermark without rewriting frozen pending requests', () => {
  const frozen = { conversation_id: 'conv', api_config_id: 'platform', prompt: '原请求', aspect_ratio: '1:1', watermark: true };
  const draft = readImageDraft(JSON.stringify({ prompt: '新的描述', watermark: true, pending: { key: 'same-key', body: frozen } }));
  assert.equal(imageSubmission(draft, 'conv').watermark, false);
  assert.equal(imageSuggestionRequest(draft, 'conv')?.watermark, false);
  assert.deepEqual(draft.pending, { key: 'same-key', body: frozen });
  const restored = readImageDraft(JSON.stringify(draft));
  assert.deepEqual(restored.pending, draft.pending);
  const reused = imageTextOnlyDraft({ ...restored, pending: undefined });
  assert.equal(imageSubmission(reused, 'conv').watermark, false);
  assert.equal(imageSuggestionRequest(reused, 'conv')?.watermark, false);
});

test('platform model presentation stays generic for both current selection and historical model ids', () => {
  const models = [{ id: 'internal-platform-model', label: 'Private platform model' }, { id: 'own-model', label: 'Seedream 5.0 Pro' }];
  assert.equal(imageDisplayModel(models, 'internal-platform-model', 'platform'), '平台默认模型');
  assert.equal(imageDisplayModel(models, 'older-platform-model', 'platform'), '平台默认模型');
  assert.equal(imageDisplayModel(models, '', 'platform'), '平台默认模型');
  assert.equal(imageDisplayModel(models, 'own-model', 'my-api'), 'Seedream 5.0 Pro');
});
