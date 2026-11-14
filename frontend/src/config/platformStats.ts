/**
 * 平台运行数据配置。
 *
 * 现状（对应后端 OpenAPI 文档）：
 * - 公开汇总接口只有 `GET /api/v1/site-traffic/summary`（累计访问量）。
 * - Token 消耗只存在于 DB 字段（agent_runs.input_tokens / output_tokens），
 *   后端尚未提供任何聚合接口，前端拿不到真实值。
 *
 * 因此这里预留了两个可配置项：等后端确认部署并给出聚合接口后，
 * 只需把 tokenTotal / dailyTokens 接到真实返回值（或先用下面的环境变量注入），
 * 首页的 Token 卡片与 14 天趋势图会自动从「待接入」切换为真实数据，无需改模板。
 *
 * 环境变量（.env.local）：
 *   VITE_PLATFORM_TOKEN_TOTAL=12845600
 *   VITE_PLATFORM_TOKEN_DAILY=[{"day":"2026-11-01","tokens":18200}, ...]
 */
function readNumber(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function readDaily(raw: unknown): Array<{ day: string; tokens: number }> {
  if (typeof raw !== 'string' || !raw.trim()) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((p) => p && typeof p.day === 'string' && Number.isFinite(Number(p.tokens)))
      .map((p) => ({ day: p.day, tokens: Math.max(0, Number(p.tokens)) }));
  } catch {
    return [];
  }
}

export interface PlatformStatsConfig {
  /** 全平台累计 Token 消耗；null 表示后端尚未提供，页面显示「待接入」 */
  tokenTotal: number | null;
  /** 近 14 天每日 Token 消耗；空数组表示尚未提供 */
  dailyTokens: Array<{ day: string; tokens: number }>;
}

export const platformStats: PlatformStatsConfig = {
  tokenTotal: readNumber(import.meta.env.VITE_PLATFORM_TOKEN_TOTAL),
  dailyTokens: readDaily(import.meta.env.VITE_PLATFORM_TOKEN_DAILY),
};
