import assert from 'node:assert/strict';
import { test } from 'node:test';
import { CanvasPersistence } from '../src/services/canvasPersistence.ts';
import { copy, createCanvas, mergeCanvas } from '../src/services/canvasState.ts';
import type { CanvasDocument } from '../src/types/canvas.ts';

const memory = () => {
  const data = new Map<string, string>();
  return { data, getItem: (key: string) => data.get(key) || null, setItem: (key: string, value: string) => { data.set(key, value); }, removeItem: (key: string) => { data.delete(key); } };
};
const deferred = <T>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
};
function server(initial = createCanvas('one')) {
  const docs = new Map([['one', { canvas_data: initial, canvas_version: 0 }]]);
  const calls: { id: string; version: number; document: CanvasDocument }[] = [];
  let gate: ReturnType<typeof deferred<void>> | null = null;
  let failing = false;
  return {
    docs, calls,
    setGate(value: typeof gate) { gate = value; }, setFailing(value: boolean) { failing = value; },
    async load(id: string) { return copy(docs.get(id)!); },
    async save(id: string, document: CanvasDocument, version: number) {
      calls.push({ id, version, document: copy(document) });
      if (gate) { const wait = gate; gate = null; await wait.promise; }
      if (failing) throw { code: 'NETWORK_ERROR', message: '网络已断开' };
      const current = docs.get(id)!;
      if (current.canvas_version !== version) throw { code: 'CANVAS_VERSION_CONFLICT' };
      const result = { canvas_data: copy(document), canvas_version: version + 1 };
      docs.set(id, result); return copy(result);
    },
  };
}

test('an edit made while a save is in flight is saved afterwards, in order', async t => {
  const backend = server(); const storage = memory();
  const store = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => store.stop());
  const session = store.open('one', await backend.load('one'), createCanvas('one'));
  const gate = deferred<void>(); backend.setGate(gate);
  session.document.nodes[0].content = 'first'; store.edit('one', session.document);
  const saving = store.flush('one');
  session.document.nodes[0].content = 'latest'; session.document.agent_draft = 'not yet sent'; store.edit('one', session.document);
  gate.resolve(); assert.equal(await saving, true);
  assert.deepEqual(backend.calls.map(call => [call.version, call.document.nodes[0].content]), [[0, 'first'], [1, 'latest']]);
  assert.equal(backend.docs.get('one')!.canvas_data.agent_draft, 'not yet sent');
  assert.equal(JSON.parse(storage.data.get(store.key('one'))!).dirty, false);
});

test('a failed save recovers every field from a draft after reloading', async t => {
  const backend = server(); const storage = memory(); backend.setFailing(true);
  const first = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => first.stop());
  const session = first.open('one', await backend.load('one'), createCanvas('one'));
  session.document.nodes[0].content = 'manual'; session.document.nodes[0].title = 'renamed';
  session.document.nodes[0].x = -300; session.document.zoom = 1.5; session.document.pan.y = 280;
  session.document.agent_draft = 'draft'; session.document.ai_target_node_id = session.document.nodes[0].id;
  first.edit('one', session.document); assert.equal(await first.flush('one'), false); assert.equal(session.status, 'error');
  const next = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => next.stop());
  const restored = next.open('one', await backend.load('one'), createCanvas('one'));
  assert.deepEqual(restored.document, session.document);
  backend.setFailing(false); assert.equal(await next.flush('one'), true);
});

test('an acknowledged cloud document supersedes an older clean cache', async t => {
  const backend = server(); const storage = memory();
  const first = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => first.stop());
  first.open('one', await backend.load('one'), createCanvas('one'));
  backend.docs.get('one')!.canvas_data.nodes[0].content = 'from another device'; backend.docs.get('one')!.canvas_version++;
  const next = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => next.stop());
  const restored = next.open('one', await backend.load('one'), createCanvas('one'));
  assert.equal(restored.document.nodes[0].content, 'from another device'); assert.equal(restored.dirty, false);
});

test('independent edits on different nodes merge on a version conflict', async t => {
  const backend = server(); const store = new CanvasPersistence('user', memory(), backend, undefined, 60000); t.after(() => store.stop());
  const session = store.open('one', await backend.load('one'), createCanvas('one'));
  session.document.nodes[0].content = 'local script'; store.edit('one', session.document);
  backend.docs.get('one')!.canvas_data.nodes[1].title = 'remote image title'; backend.docs.get('one')!.canvas_version++;
  assert.equal(await store.flush('one'), true);
  assert.equal(session.document.nodes[0].content, 'local script'); assert.equal(session.document.nodes[1].title, 'remote image title');
});

test('conflicting edits to the same text require a choice and preserve the rejected draft', async t => {
  const backend = server(); const storage = memory(); const store = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => store.stop());
  const session = store.open('one', await backend.load('one'), createCanvas('one'));
  session.document.nodes[0].content = 'mine'; store.edit('one', session.document);
  backend.docs.get('one')!.canvas_data.nodes[0].content = 'theirs'; backend.docs.get('one')!.canvas_version++;
  assert.equal(await store.flush('one'), false); assert.equal(session.status, 'conflict');
  assert.equal(backend.docs.get('one')!.canvas_data.nodes[0].content, 'theirs');
  assert.equal(await store.resolve('one', 'remote'), true);
  assert.equal(session.document.nodes[0].content, 'theirs');
  assert.equal(JSON.parse(storage.data.get(`${store.key('one')}:conflict-backup`)!).nodes[0].content, 'mine');
});

test('AI arriving after an unsaved manual edit becomes an explicit candidate', () => {
  const base = createCanvas('one', 'original'); const mine = copy(base); const remote = copy(base);
  mine.nodes[0].content = 'my newer edit'; remote.nodes[0].content = 'AI reply';
  remote.nodes[0].last_ai = { before: 'original', after: 'AI reply', message_id: 'reply-id' };
  const merged = mergeCanvas(base, mine, remote);
  assert.equal(merged.document.nodes[0].content, 'my newer edit'); assert.equal(merged.document.nodes[0].pending_ai?.content, 'AI reply');
  assert.deepEqual(merged.conflicts, []);
});

test('deleting a node while AI runs does not resurrect it during reconciliation', () => {
  const base = createCanvas('one'); const mine = copy(base); const remote = copy(base);
  mine.nodes = []; remote.nodes[0].content = 'AI reply';
  assert.deepEqual(mergeCanvas(base, mine, remote).document.nodes, []);
});

test('saving and reopening an empty canvas preserves the intentional empty state', async t => {
  const backend = server(); const storage = memory(); const store = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => store.stop());
  const session = store.open('one', await backend.load('one'), createCanvas('one'));
  session.document.nodes = []; session.document.connections = []; store.edit('one', session.document);
  await store.flush('one');
  const next = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => next.stop());
  assert.deepEqual(next.open('one', await backend.load('one'), createCanvas('one')).document.nodes, []);
});

test('project queues and account caches remain isolated', async t => {
  const backend = server(); backend.docs.set('two', { canvas_data: createCanvas('two'), canvas_version: 0 });
  const storage = memory(); const store = new CanvasPersistence('user-a', storage, backend, undefined, 60000); t.after(() => store.stop());
  for (const id of ['one', 'two']) { const session = store.open(id, await backend.load(id), createCanvas(id)); session.document.nodes[0].content = id; store.edit(id, session.document); }
  await Promise.all([store.flush('one'), store.flush('two')]);
  assert.equal(backend.docs.get('one')!.canvas_data.nodes[0].content, 'one'); assert.equal(backend.docs.get('two')!.canvas_data.nodes[0].content, 'two');
  const other = new CanvasPersistence('user-b', storage, backend); t.after(() => other.stop());
  assert.notEqual(other.key('one'), store.key('one'));
});

test('local storage failures remain visible and a failed cloud save is never reported as saved', async t => {
  const backend = server(); backend.setFailing(true);
  const storage = { getItem: () => null, setItem: () => { throw new Error('quota'); }, removeItem: () => {} };
  const store = new CanvasPersistence('user', storage, backend, undefined, 60000); t.after(() => store.stop());
  const session = store.open('one', await backend.load('one'), createCanvas('one'));
  session.document.nodes[0].content = 'must not disappear'; store.edit('one', session.document);
  assert.equal(await store.flush('one'), false); assert.equal(session.localAvailable, false); assert.equal(session.dirty, true); assert.equal(session.status, 'error');
});
