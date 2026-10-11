import type { CanvasDocument } from '../types/canvas.ts';
import { copy, mergeCanvas, normalizeCanvas, same } from './canvasState.ts';

export interface RemoteCanvas { canvas_data: CanvasDocument | null; canvas_version: number }
export interface CanvasTransport {
  load(id: string): Promise<RemoteCanvas>;
  save(id: string, document: CanvasDocument, version: number): Promise<RemoteCanvas>;
}
export interface DraftStorage { getItem(key: string): string | null; setItem(key: string, value: string): void; removeItem(key: string): void }
export interface CanvasSession {
  id: string; document: CanvasDocument; base: CanvasDocument; version: number; dirty: boolean;
  status: 'saved' | 'pending' | 'saving' | 'error' | 'conflict'; error: string;
  localAvailable: boolean; conflicts: string[]; pending: Promise<boolean> | null;
}

/** Each conversation has a serialized save queue and an account-scoped durable local draft. */
export class CanvasPersistence {
  readonly sessions = new Map<string, CanvasSession>();
  private timers = new Map<string, ReturnType<typeof setTimeout>>();
  private storage: DraftStorage;
  private transport: CanvasTransport;
  private owner: string;
  private notify: (session: CanvasSession) => void;
  private delay: number;

  constructor(owner: string, storage: DraftStorage, transport: CanvasTransport,
    notify: (session: CanvasSession) => void = () => {}, delay = 700) {
    this.owner = owner; this.storage = storage; this.transport = transport; this.notify = notify; this.delay = delay;
  }

  key(id: string) { return `hw:canvas:v1:${this.owner}:${id}`; }

  open(id: string, remote: RemoteCanvas, initial: CanvasDocument): CanvasSession {
    const existing = this.sessions.get(id);
    if (existing) { this.acceptRemote(id, remote); return existing; }
    const base = remote.canvas_data ? normalizeCanvas(remote.canvas_data) : normalizeCanvas(initial);
    let document = copy(base);
    let conflicts: string[] = [];
    let recoveryError = '';
    try {
      const raw = this.storage.getItem(this.key(id));
      if (raw) {
        const draft = JSON.parse(raw);
        if (draft.dirty) {
          const merged = mergeCanvas(normalizeCanvas(draft.base), normalizeCanvas(draft.document), base);
          document = merged.document; conflicts = merged.conflicts;
        }
      } else {
        // Only migrate an old, unscoped cache after the server has verified ownership of this project.
        const legacy = this.storage.getItem(`canvas_${id}`);
        if (legacy && !remote.canvas_data) document = normalizeCanvas(JSON.parse(legacy));
      }
    } catch { recoveryError = '本地草稿无法读取，已加载云端画布'; }
    const session: CanvasSession = {
      id, document, base, version: remote.canvas_version || 0, dirty: !same(document, base) || !remote.canvas_data,
      status: conflicts.length ? 'conflict' : 'saved', error: recoveryError, localAvailable: true, conflicts, pending: null,
    };
    this.sessions.set(id, session);
    this.checkpoint(session);
    if (session.dirty && !conflicts.length) this.schedule(session);
    this.notify(session);
    return session;
  }

  edit(id: string, document: CanvasDocument) {
    const session = this.sessions.get(id);
    if (!session) return;
    session.document = document;
    session.dirty = !same(normalizeCanvas(document), session.base);
    this.checkpoint(session); // Synchronous: the most recent keystroke survives a reload.
    if (session.dirty && !session.conflicts.length) this.schedule(session);
    this.notify(session);
  }

  private schedule(session: CanvasSession) {
    this.clearTimer(session.id);
    session.status = session.pending ? 'saving' : 'pending';
    this.timers.set(session.id, setTimeout(() => { void this.flush(session.id); }, this.delay));
  }

  private clearTimer(id: string) {
    const timer = this.timers.get(id);
    if (timer) clearTimeout(timer);
    this.timers.delete(id);
  }

  checkpoint(session: CanvasSession) {
    try {
      this.storage.setItem(this.key(session.id), JSON.stringify({ document: normalizeCanvas(session.document),
        base: session.base, version: session.version, dirty: session.dirty }));
      session.localAvailable = true;
    } catch { session.localAvailable = false; }
  }

  acceptRemote(id: string, remote: RemoteCanvas) {
    const session = this.sessions.get(id);
    if (!session || !remote.canvas_data || remote.canvas_version < session.version) return;
    const server = normalizeCanvas(remote.canvas_data);
    const merged = mergeCanvas(session.base, normalizeCanvas(session.document), server);
    session.document = merged.document;
    session.base = server; session.version = remote.canvas_version;
    session.conflicts = merged.conflicts;
    session.dirty = !same(session.document, server);
    session.status = merged.conflicts.length ? 'conflict' : session.dirty ? 'pending' : 'saved';
    session.error = merged.conflicts.length ? '另一窗口修改了相同内容，请选择保留哪个版本；本地草稿仍在。' : '';
    this.checkpoint(session); this.notify(session);
  }

  async flush(id: string): Promise<boolean> {
    const session = this.sessions.get(id);
    if (!session) return true;
    this.clearTimer(id);
    if (session.pending) return session.pending;
    if (session.conflicts.length) return false;
    if (!session.dirty) return true;
    const pending = this.saveLoop(session);
    session.pending = pending;
    try { return await pending; }
    finally { session.pending = null; this.notify(session); }
  }

  private async saveLoop(session: CanvasSession): Promise<boolean> {
    for (let attempt = 0; attempt < 6 && session.dirty; attempt++) {
      if (session.conflicts.length) return false;
      session.status = 'saving'; session.error = ''; this.notify(session);
      const sent = normalizeCanvas(session.document);
      try {
        const response = await this.transport.save(session.id, sent, session.version);
        if (response.canvas_version >= session.version && response.canvas_data) {
          // Compare against the snapshot we sent, not the current editor contents.
          const server = normalizeCanvas(response.canvas_data);
          const merged = mergeCanvas(sent, normalizeCanvas(session.document), server);
          session.document = merged.document; session.base = server; session.version = response.canvas_version;
          session.conflicts = merged.conflicts; session.dirty = !same(session.document, server);
          this.checkpoint(session); this.notify(session);
        }
      } catch (error: any) {
        if (error?.code === 'CANVAS_VERSION_CONFLICT') {
          try { this.acceptRemote(session.id, await this.transport.load(session.id)); }
          catch (loadError: any) { return this.failed(session, loadError); }
          if (session.conflicts.length) return false;
          continue;
        }
        return this.failed(session, error);
      }
    }
    if (session.dirty) return this.failed(session, { message: '画布更新频繁，草稿已保留，请重试保存' });
    session.status = 'saved'; session.error = ''; this.notify(session);
    return true;
  }

  private failed(session: CanvasSession, error: any): false {
    session.status = 'error'; session.error = error?.message || '云端保存失败';
    this.checkpoint(session); this.notify(session);
    return false;
  }

  async resolve(id: string, choice: 'local' | 'remote'): Promise<boolean> {
    const session = this.sessions.get(id);
    if (!session) return true;
    const remote = await this.transport.load(id);
    if (!remote.canvas_data) return false;
    // Preserve the rejected draft as a separately recoverable backup before the explicit choice.
    try { this.storage.setItem(`${this.key(id)}:conflict-backup`, JSON.stringify(normalizeCanvas(session.document))); } catch { /* status below still reports storage failures */ }
    session.base = normalizeCanvas(remote.canvas_data); session.version = remote.canvas_version;
    if (choice === 'remote') session.document = copy(session.base);
    session.conflicts = []; session.error = ''; session.dirty = !same(normalizeCanvas(session.document), session.base);
    this.checkpoint(session); this.notify(session);
    return this.flush(id);
  }

  remove(id: string) {
    this.clearTimer(id); this.sessions.delete(id);
    try { this.storage.removeItem(this.key(id)); this.storage.removeItem(`canvas_${id}`); } catch { /* deleted project is no longer recoverable from this cache */ }
  }

  stop() { for (const id of this.timers.keys()) this.clearTimer(id); }
}
