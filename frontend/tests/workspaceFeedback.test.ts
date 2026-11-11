import assert from 'node:assert/strict';
import { test } from 'node:test';
import { collaborationReferenceIds, portraitFailureGate, portraitFailureMessage } from '../src/services/workspaceFeedback.ts';
import type { FlowNode } from '../src/types/canvas.ts';

const nodes: FlowNode[] = [
  { id: 'target', type: 'text', title: '目标', x: 0, y: 0 },
  { id: 'pinned', type: 'text', title: '参考文本', x: 0, y: 0 },
  { id: 'selected-text', type: 'text', title: '其他文本', x: 0, y: 0 },
  { id: 'image-1', type: 'image', title: '图片一', x: 0, y: 0 },
  { id: 'image-2', type: 'image', title: '图片二', x: 0, y: 0 },
];
test('selected images reach collaboration even with pinned references, without duplicating target text', () => {
  const references = collaborationReferenceIds(nodes, ['pinned', 'target', 'image-1', 'deleted'], ['image-1', 'image-2', 'target', 'selected-text'], 'target');
  assert.deepEqual(references, ['pinned', 'image-1', 'image-2']);
  assert.deepEqual(collaborationReferenceIds(nodes, references, [], 'target'), references);
  assert.deepEqual(collaborationReferenceIds(nodes, ['selected-text', 'target'], ['image-1'], 'target'), ['selected-text', 'image-1']);
});
test('portrait popup requires exact normalized code and ignores stale conversations and ordinary failures', () => {
  const claim = portraitFailureGate();
  for (const code of ['CONTENT_REJECTED', 'INSUFFICIENT_BALANCE', 'UNKNOWN_ERROR', undefined])
    assert.equal(claim('current', 'current', 'job:a', code), false);
  assert.equal(claim('current', 'previous', 'job:a', 'VIDEO_PORTRAIT_REJECTED'), false);
  assert.equal(claim('current', 'current', 'job:a', 'VIDEO_PORTRAIT_REJECTED'), true);
  assert.equal(claim('current', 'current', 'job:a', 'VIDEO_PORTRAIT_REJECTED'), false);
  assert.equal(claim('other', 'other', 'job:a', 'VIDEO_PORTRAIT_REJECTED'), true);
  assert.equal(claim('current', 'current', 'job:b', 'VIDEO_PORTRAIT_REJECTED'), true);
});
test('synchronous portrait submissions are deduplicated independently and a fresh page can recover the failure', () => {
  const claim = portraitFailureGate();
  assert.equal(claim('conv', 'conv', 'submission:request-1', 'VIDEO_PORTRAIT_REJECTED'), true);
  assert.equal(claim('conv', 'conv', 'submission:request-1', 'VIDEO_PORTRAIT_REJECTED'), false);
  assert.equal(portraitFailureGate()('conv', 'conv', 'submission:request-1', 'VIDEO_PORTRAIT_REJECTED'), true);
  assert.equal(portraitFailureMessage, '含人像图片来源必须是与视频AI模型同属的图片AI模型，请使用AI素材图片生成。');
});
