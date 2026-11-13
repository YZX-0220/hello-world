export type TemplateScope = 'system' | 'user';
export type TemplateCategory = 'positive' | 'negative' | 'cultural' | 'storyboard';

export interface PromptTemplateItem {
  id: string;
  user_id?: string | null;
  code?: string | null;
  scope: TemplateScope;
  category: TemplateCategory;
  name: string;
  description?: string | null;
  content: string;
  negative_prompt?: string | null;
  variables?: string[];
  variables_json?: string;
  current_version: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplateVersionItem {
  id: string;
  template_id: string;
  version: number;
  name: string;
  content: string;
  negative_prompt?: string | null;
  variables?: string[];
  variables_json?: string;
  source_type: 'init' | 'edit' | 'rollback';
  change_note?: string | null;
  created_by?: string | null;
  created_at: string;
}

export interface CreatePromptTemplatePayload {
  name: string;
  category: TemplateCategory;
  content: string;
  negative_prompt?: string;
  description?: string;
  variables?: string[];
}

export interface UpdatePromptTemplatePayload {
  name?: string;
  category?: TemplateCategory;
  content?: string;
  negative_prompt?: string;
  description?: string;
  variables?: string[];
  change_note?: string;
}

const API_BASE = '/api/v1/prompt-templates';

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)hw_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

async function handleResponse<T>(res: Response, fallbackMsg: string): Promise<T> {
  if (!res.ok) {
    let detail = fallbackMsg;
    try {
      const data = await res.json();
      if (typeof data?.detail === 'string') detail = data.detail;
      else if (Array.isArray(data?.detail)) detail = data.detail.map((d: any) => d.msg).join('；') || fallbackMsg;
      else if (data?.message) detail = data.message;
    } catch {
      // 忽略非 JSON 错误体
    }
    throw new Error(`${detail} (HTTP ${res.status})`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return await res.json();
}

function normalizeTemplate(raw: any): PromptTemplateItem {
  let vars: string[] = [];
  if (Array.isArray(raw.variables)) {
    vars = raw.variables;
  } else if (typeof raw.variables_json === 'string') {
    try {
      const parsed = JSON.parse(raw.variables_json);
      if (Array.isArray(parsed)) vars = parsed;
    } catch {}
  }
  return {
    ...raw,
    variables: vars,
    current_version: Number(raw.current_version ?? 1),
  };
}

export const promptTemplateApi = {
  // 1. 获取模板列表
  async list(params?: { category?: string; scope?: string; q?: string }): Promise<PromptTemplateItem[]> {
    const url = new URL(API_BASE, window.location.origin);
    if (params?.category && params.category !== 'all') url.searchParams.set('category', params.category);
    if (params?.scope && params.scope !== 'all') url.searchParams.set('scope', params.scope);
    if (params?.q?.trim()) url.searchParams.set('q', params.q.trim());

    const res = await fetch(url.toString(), {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });
    const data = await handleResponse<any>(res, '获取提示词模板列表失败');
    const items = Array.isArray(data) ? data : (data.items ?? data.data ?? []);
    return items.map(normalizeTemplate);
  },

  // 2. 新建模板 (自动生成 v1 快照)
  async create(payload: CreatePromptTemplatePayload): Promise<PromptTemplateItem> {
    const body: Record<string, any> = {
      name: payload.name.trim(),
      category: payload.category,
      content: payload.content.trim(),
    };
    if (payload.negative_prompt !== undefined) body.negative_prompt = payload.negative_prompt.trim();
    if (payload.description !== undefined) body.description = payload.description.trim();
    if (payload.variables !== undefined) body.variables = payload.variables;

    const res = await fetch(API_BASE, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRF-Token': getCsrfToken(),
      },
      credentials: 'include',
      body: JSON.stringify(body),
    });
    const created = await handleResponse<any>(res, '新建提示词模板失败');
    return normalizeTemplate(created);
  },

  // 3. 修改模板 (自动递增版本号并留存快照)
  async update(id: string, payload: UpdatePromptTemplatePayload): Promise<PromptTemplateItem> {
    const body: Record<string, any> = {};
    if (payload.name !== undefined) body.name = payload.name.trim();
    if (payload.category !== undefined) body.category = payload.category;
    if (payload.content !== undefined) body.content = payload.content.trim();
    if (payload.negative_prompt !== undefined) body.negative_prompt = payload.negative_prompt.trim();
    if (payload.description !== undefined) body.description = payload.description.trim();
    if (payload.variables !== undefined) body.variables = payload.variables;
    if (payload.change_note !== undefined && payload.change_note.trim()) {
      body.change_note = payload.change_note.trim();
    }

    const res = await fetch(`${API_BASE}/${encodeURIComponent(id)}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRF-Token': getCsrfToken(),
      },
      credentials: 'include',
      body: JSON.stringify(body),
    });
    const updated = await handleResponse<any>(res, '更新提示词模板失败');
    return normalizeTemplate(updated);
  },

  // 4. 删除自定义模板 (软删除)
  async remove(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      headers: {
        Accept: 'application/json',
        'X-CSRF-Token': getCsrfToken(),
      },
      credentials: 'include',
    });
    await handleResponse<void>(res, '删除提示词模板失败');
  },

  // 5. 查询全部历史版本列表
  async listVersions(id: string): Promise<PromptTemplateVersionItem[]> {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(id)}/versions`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });
    const data = await handleResponse<any>(res, '获取版本历史失败');
    return Array.isArray(data) ? data : (data.items ?? data.data ?? []);
  },

  // 6. 查询指定版本详情快照
  async getVersionDetail(id: string, version: number): Promise<PromptTemplateVersionItem> {
    const res = await fetch(`${API_BASE}/${encodeURIComponent(id)}/versions/${version}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    });
    return await handleResponse<PromptTemplateVersionItem>(res, `获取 v${version} 快照失败`);
  },

  // 7. 一键回滚至目标版本
  async rollback(id: string, targetVersion: number, changeNote?: string): Promise<PromptTemplateItem> {
    const body: Record<string, any> = { target_version: targetVersion };
    if (changeNote?.trim()) body.change_note = changeNote.trim();

    const res = await fetch(`${API_BASE}/${encodeURIComponent(id)}/rollback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRF-Token': getCsrfToken(),
      },
      credentials: 'include',
      body: JSON.stringify(body),
    });
    const rolled = await handleResponse<any>(res, '回滚版本失败');
    return normalizeTemplate(rolled);
  },
};