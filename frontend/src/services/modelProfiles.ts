export interface ModelProfileChoice {
  code: string;
  remote_model_id?: string | null;
}

const VERSION_SUFFIX = /-\d{6}$/;

/** 去掉结尾的六位版本号（如 -260128），用于跨版本匹配同一模型。 */
export function normalizeModelId(value: string | null | undefined): string {
  return (value ?? '').trim().replace(VERSION_SUFFIX, '');
}

/**
 * 把用户填写的模型 ID 匹配到已登记的能力档案。
 * 顺序：完全相等 → 去掉版本号后相等 → 最长前缀（要求命中后紧跟 "-"）。
 */
export function matchProfileCode(
  profiles: ModelProfileChoice[],
  modelId: string | null | undefined,
): string | null {
  const model = (modelId ?? '').trim();
  if (!model) return null;

  const exact = profiles.find(m => m.remote_model_id === model || m.code === model);
  if (exact) return exact.code;

  const base = normalizeModelId(model);
  const byBase = profiles.find(
    m => normalizeModelId(m.remote_model_id) === base || normalizeModelId(m.code) === base,
  );
  if (byBase) return byBase.code;

  const prefixed = profiles
    .filter(m => m.code && model.startsWith(`${m.code}-`))
    .sort((a, b) => b.code.length - a.code.length)[0];
  return prefixed?.code ?? null;
}
