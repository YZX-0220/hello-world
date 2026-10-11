import assert from 'node:assert/strict';
import { test } from 'node:test';
import { copy, createCanvas, mergeCanvas } from '../src/services/canvasState.ts';
import { generationMatches, generationSources, savedVideoReview, videoGenerationBlockReason } from '../src/services/generationState.ts';

function prepared() {
  const document = createCanvas('one', '手动脚本');
  document.nodes.push({ id: 'second', type: 'text', title: '镜头', x: 300, y: 600, content: '固定镜头' });
  document.generation_source_ids = [document.nodes[0].id, 'second'];
  document.generation_spec_version = 3;
  document.video_duration_seconds = 8; document.video_resolution = '1080p';
  document.generation_settings = { duration_seconds: 8, resolution: '1080p' };
  document.generation_snapshot = generationSources(document, document.generation_source_ids);
  return document;
}

test('a prepared multi-box plan matches regardless of click order, but rejects changed selection and content', () => {
  const document = prepared();
  assert.equal(generationMatches(document, 3, [...document.generation_source_ids].reverse()), true);
  assert.equal(generationMatches(document, 2), false);
  assert.equal(generationMatches(document, 3, [document.nodes[0].id]), false);
  document.nodes[2].content = '新的镜头设计';
  assert.equal(generationMatches(document, 3), false);
});

test('position, zoom and discussion do not change prepared text; an accepted reply does', () => {
  const document = prepared();
  const node = document.nodes[0];
  node.x = -500; document.zoom = 1.5; document.agent_draft = '继续讨论';
  node.pending_ai = { content: '新方案', message_id: 'reply', apply_mode: 'replace' };
  assert.equal(generationMatches(document, 3), true);
  node.content = node.pending_ai.content;
  assert.equal(generationMatches(document, 3), false);
});

test('changing a linked image or deleting a source invalidates the video plan', () => {
  const document = prepared();
  document.nodes[1].asset_id = 'image-one';
  document.connections = [{ id: 'link', from: document.nodes[1].id, to: document.nodes[0].id }];
  document.generation_snapshot = generationSources(document, document.generation_source_ids);
  assert.equal(generationMatches(document, 3), true);
  document.nodes[1].asset_id = 'image-two';
  assert.equal(generationMatches(document, 3), false);
  document.nodes.splice(2, 1);
  assert.equal(generationMatches(document, 3), false);
});

test('a saved candidate and its structure merge with simultaneous manual typing without replacing the box', () => {
  const base = createCanvas('one', '原文');
  const local = copy(base); local.nodes[0].content = '手动新文本';
  const remote = copy(base);
  remote.nodes[0].pending_ai = { content: '讨论方案', message_id: 'reply', apply_mode: 'replace' };
  remote.nodes[0].ai_running = false;
  const result = mergeCanvas(base, local, remote);
  assert.deepEqual(result.conflicts, []);
  assert.equal(result.document.nodes[0].content, '手动新文本');
  assert.equal(result.document.nodes[0].pending_ai?.content, '讨论方案');
});

test('typing during explicit confirmation retains the accepted prompt for a later confirmation', () => {
  const base = createCanvas('one', '原文');
  const local = copy(base); local.nodes[0].content = '确认时的新手动编辑';
  const remote = copy(base); remote.nodes[0].content = 'AI 分镜方案';
  remote.nodes[0].last_ai = {
    before: '原文', after: 'AI 分镜方案', message_id: 'confirmed',
    suggested_prompt: '带有镜头、动作和光线的完整视频提示词',
  };
  const result = mergeCanvas(base, local, remote);
  assert.deepEqual(result.conflicts, []);
  assert.equal(result.document.nodes[0].content, '确认时的新手动编辑');
  assert.equal(result.document.nodes[0].pending_ai?.suggested_prompt, remote.nodes[0].last_ai.suggested_prompt);
  assert.equal(result.document.nodes[0].pending_ai?.original, '原文');
});

test('a persisted review restores with the matching plan and optional suggestions do not block generation', () => {
  const document = prepared();
  document.generation_review = { spec_version: 3, content: '### 最终方案\n用途未填写。\n### 可选建议\n可增加旁白。' };
  const restored = JSON.parse(JSON.stringify(document));
  assert.equal(savedVideoReview(restored, 3)?.content, document.generation_review.content);
  assert.equal(savedVideoReview(restored, 4), undefined);
  const state = { compiledPrompt: true, preparing: false, submitting: false, collaborating: false,
    confirming: false, channel: 'platform', saveStatus: 'saved' };
  assert.equal(videoGenerationBlockReason(restored, 3, restored.generation_source_ids, state), '');
  restored.nodes[0].content = '新的方向';
  assert.match(videoGenerationBlockReason(restored, 3, restored.generation_source_ids, state), /已变化/);
});

test('an unavailable generation action explains whether it needs a review, a channel, or save recovery', () => {
  const document = prepared();
  const state = { compiledPrompt: true, preparing: false, submitting: false, collaborating: false,
    confirming: false, channel: 'platform', saveStatus: 'saved' };
  const ids = document.generation_source_ids;
  assert.match(videoGenerationBlockReason(document, 3, ids, { ...state, compiledPrompt: false }), /先点击/);
  assert.match(videoGenerationBlockReason(document, 3, ids, { ...state, preparing: true }), /正在整理/);
  assert.match(videoGenerationBlockReason(document, 3, ids, { ...state, channel: '' }), /生成通道/);
  assert.match(videoGenerationBlockReason(document, 3, ids, { ...state, saveStatus: 'conflict' }), /保存提示/);
});

test('duration and resolution require a manual choice and changing either invalidates the reviewed plan', () => {
  const document = prepared();
  const state = { compiledPrompt: true, preparing: false, submitting: false, collaborating: false,
    confirming: false, channel: 'platform', saveStatus: 'saved' };
  const ids = document.generation_source_ids;
  document.video_duration_seconds = null;
  assert.match(videoGenerationBlockReason(document, 3, ids, state), /填写视频时长/);
  document.video_duration_seconds = 7.5;
  assert.match(videoGenerationBlockReason(document, 3, ids, state), /整数/);
  for (const duration of [0, 16, 120]) {
    document.video_duration_seconds = duration;
    assert.match(videoGenerationBlockReason(document, 3, ids, state), /1–15/);
  }
  for (const duration of [1, 15]) {
    document.video_duration_seconds = duration;
    document.generation_settings = { duration_seconds: duration, resolution: '1080p' };
    assert.equal(videoGenerationBlockReason(document, 3, ids, state), '');
  }
  document.generation_settings = { duration_seconds: 8, resolution: '1080p' };
  document.video_duration_seconds = 8; document.video_resolution = '';
  assert.match(videoGenerationBlockReason(document, 3, ids, state), /请选择视频清晰度/);
  document.video_resolution = '720p';
  assert.equal(generationMatches(document, 3), false);
  document.video_resolution = '1080p'; document.video_duration_seconds = 12;
  assert.equal(generationMatches(document, 3), false);
});
