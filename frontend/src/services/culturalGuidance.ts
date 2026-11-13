export interface CulturalGuidanceItem {
  id: number;
  code: string;
  name: string;
  negative_prompt: string;
  taboo: string | null;
  sort_order: number;
  is_enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface CreateCulturalGuidancePayload {
  code: string;
  name: string;
  negative_prompt: string;
  taboo?: string | null;
  sort_order?: number;
}

export interface UpdateCulturalGuidancePayload {
  name?: string;
  negative_prompt?: string;
  taboo?: string | null;
  sort_order?: number;
  is_enabled?: boolean;
}

const API_BASE = '/api/v1/cultural-guidances';

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)hw_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : '';
}

async function parseErrorResponse(res: Response, fallbackMsg: string): Promise<never> {
  let detail = fallbackMsg;
  try {
    const errBody = await res.json();
    if (typeof errBody?.detail === 'string') {
      detail = errBody.detail;
    } else if (Array.isArray(errBody?.detail)) {
      detail = errBody.detail.map((d: any) => d.msg).join('；') || fallbackMsg;
    } else if (errBody?.message) {
      detail = errBody.message;
    }
  } catch {
    // 忽略非 JSON 响应体
  }
  throw new Error(`${detail} (HTTP ${res.status})`);
}

/**
 * 1. 查询所有已启用的国家及负面提示词列表
 * GET /api/v1/cultural-guidances
 */
export async function listCulturalGuidances(): Promise<CulturalGuidanceItem[]> {
  const res = await fetch(API_BASE, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'include',
  });
  if (!res.ok) {
    await parseErrorResponse(res, '获取国家负面提示词列表失败');
  }
  const data = await res.json();
  const rawList: any[] = Array.isArray(data) ? data : (data.items ?? data.data ?? []);
  return rawList.map((item) => ({
    id: Number(item.id),
    code: String(item.code || ''),
    name: String(item.name || ''),
    negative_prompt: String(item.negative_prompt ?? ''),
    taboo: item.taboo != null ? String(item.taboo) : null,
    sort_order: Number(item.sort_order ?? 0),
    is_enabled: item.is_enabled !== false,
    created_at: item.created_at,
    updated_at: item.updated_at,
  }));
}

/**
 * 2. 新增国家及负面提示词（严格过滤字段，防止 Pydantic extra="forbid" 报 422）
 * POST /api/v1/cultural-guidances
 */
export async function createCulturalGuidance(
  payload: CreateCulturalGuidancePayload
): Promise<CulturalGuidanceItem> {
  const body: CreateCulturalGuidancePayload = {
    code: payload.code.trim().toUpperCase(),
    name: payload.name.trim(),
    negative_prompt: payload.negative_prompt.trim(),
  };
  if (payload.taboo !== undefined) body.taboo = payload.taboo;
  if (payload.sort_order !== undefined) body.sort_order = payload.sort_order;

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
  if (!res.ok) {
    await parseErrorResponse(res, '新增国家负面提示词失败');
  }
  return await res.json();
}

/**
 * 3. 修改指定国家的负面提示词（支持局部字段更新，严格过滤未定义字段）
 * PUT /api/v1/cultural-guidances/{code}
 */
export async function updateCulturalGuidance(
  code: string,
  payload: UpdateCulturalGuidancePayload
): Promise<CulturalGuidanceItem> {
  const body: UpdateCulturalGuidancePayload = {};
  if (payload.name !== undefined) body.name = payload.name.trim();
  if (payload.negative_prompt !== undefined) body.negative_prompt = payload.negative_prompt.trim();
  if (payload.taboo !== undefined) body.taboo = payload.taboo;
  if (payload.sort_order !== undefined) body.sort_order = payload.sort_order;
  if (payload.is_enabled !== undefined) body.is_enabled = payload.is_enabled;

  const res = await fetch(`${API_BASE}/${encodeURIComponent(code.trim().toUpperCase())}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'X-CSRF-Token': getCsrfToken(),
    },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    await parseErrorResponse(res, '修改国家负面提示词失败');
  }
  return await res.json();
}