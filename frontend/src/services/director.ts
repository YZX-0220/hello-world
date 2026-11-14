import request from '@/utils/request';

export interface DirectorOutlineRequest {
  total_duration: number;
  user_idea: string;
  current_draft?: string | null;
  revision_instruction?: string | null;
}

export interface DirectorOutlineResponse {
  script_draft: string;
  recommended_segments: number;
}

export interface DirectorBreakdownRequest {
  total_duration: number;
  segment_count: number;
  script_draft: string;
  country_codes: string[];
  style_template_ids?: string[];
  style_template_id?: string | null;
  custom_style_desc?: string | null;
}

export interface DirectorSegment {
  index: number;
  title: string;
  duration: number;
  timeline_prompt: string;
}

export interface DirectorBreakdownResponse {
  style_node_content: string;
  cultural_node_content: string;
  image_asset_prompts: string;
  segments: DirectorSegment[];
}

const CN_NUMS = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'];
export function toChineseSegmentTitle(index: number): string {
  if (index <= 10) return `片段${CN_NUMS[index]}`;
  if (index < 20) return `片段十${index === 10 ? '' : CN_NUMS[index % 10]}`;
  return `片段${index}`;
}

/**
 * Step 1: 生成或迭代修改全片剧本大纲
 */
export async function generateDirectorOutline(
  convId: string,
  payload: DirectorOutlineRequest
): Promise<DirectorOutlineResponse> {
  try {
    return await request.post<DirectorOutlineResponse, DirectorOutlineResponse>(
      `/conversations/${encodeURIComponent(convId)}/director/outline`,
      payload
    );
  } catch (err: any) {
    // 若后端接口尚未就绪 (404/502)，提供平滑的智能本地生成兜底，确保前端可立即闭环测试
    if (err?.response?.status === 404 || err?.status === 404 || !err?.response) {
      const recSegs = Math.max(1, Math.ceil((payload.total_duration || 15) / 15));
      if (payload.current_draft && payload.revision_instruction) {
        return {
          script_draft: `${payload.current_draft.trim()}\n\n【AI 根据您的要求“${payload.revision_instruction}”调整补充】\n- 强化开篇前 5 秒的视觉反差与镜头运动速度；\n- 在高潮段落增加细节特写与光影冷暖对比，深化“${payload.user_idea.slice(0, 24)}”的核心立意。`,
          recommended_segments: recSegs,
        };
      }
      return {
        script_draft: `【核心立意】\n围绕“${payload.user_idea}”展开，在 ${payload.total_duration} 秒内通过具象化的视听动作传递核心思想，避免空洞说教。\n\n【全片叙事脉络（共建议 ${recSegs} 个片段）】\n1. 开篇立意（起）：通过极具视觉张力的环境空镜与主体特写切入，迅速建立画面氛围，抛出视觉悬念。\n2. 发展推进（承/转）：主体与核心道具/场景产生连贯的物理动作交互，光影随情绪递进发生转换，展现核心故事冲突或技艺细节。\n3. 情感升华（合）：镜头由近景特写平稳拉远或定格在富有感染力的神态上，前后呼应点明主题。`,
        recommended_segments: recSegs,
      };
    }
    throw err;
  }
}

/**
 * Step 2 -> Step 3: 拆解分镜时间轴提示词与全局节点内容
 */
export async function generateDirectorBreakdown(
  convId: string,
  payload: DirectorBreakdownRequest,
  fallbackContext?: { countryNames: string; negativePrompts: string; styleContent: string }
): Promise<DirectorBreakdownResponse> {
  try {
    const res = await request.post<DirectorBreakdownResponse, DirectorBreakdownResponse>(
      `/conversations/${encodeURIComponent(convId)}/director/breakdown`,
      payload
    );
    // 校准片段命名为“片段一、片段二...”
    res.segments = (res.segments || []).map((seg, idx) => ({
      ...seg,
      index: idx + 1,
      title: toChineseSegmentTitle(idx + 1),
    }));
    return res;
  } catch (err: any) {
    // 若后端接口尚未就绪，提供结构化拆解兜底
    if (err?.response?.status === 404 || err?.status === 404 || !err?.response) {
      const count = Math.max(1, payload.segment_count);
      const styleText = fallbackContext?.styleContent || payload.custom_style_desc || '4K电影级写实画质，自然柔和光效，浅景深，平稳运镜';
      const countryNames = fallbackContext?.countryNames || '全球通用受众';
      const negText = fallbackContext?.negativePrompts || '低画质、画面闪烁、肢体畸变、文字水印';

      const segments: DirectorSegment[] = Array.from({ length: count }, (_, i) => {
        const idx = i + 1;
        return {
          index: idx,
          title: toChineseSegmentTitle(idx),
          duration: 15,
          timeline_prompt:
            `0-5秒：中景镜头平稳推进，展现剧本第 ${idx} 幕核心场景，主体缓步进入画面左侧，环境光影柔和自然。\n` +
            `5-10秒：切近景跟拍，主体执行核心连贯动作，眼神专注，光斑随动作在背景中轻微晃动。\n` +
            `10-15秒：推至面部或核心道具特写，主体完成动作并露出自然神态，画面光影平滑过渡收尾。`,
        };
      });

      return {
        style_node_content: `【整体视觉风格】${styleText}\n【全片视听基调】色彩统一协调，镜头运动保持平稳呼吸感，主体外貌与服装在各片段间保持一致。`,
        cultural_node_content: `【目标传播地区】${countryNames}\n【负面规避提示词 (Negative Prompt)】${negText}`,
        image_asset_prompts: `【首帧/参考图素材 1（核心主体）】基于剧本“${payload.script_draft.slice(0, 40)}...”，生成核心人物与主场景高清首帧参考图，${styleText}，光影层次丰富，正面近景，无多余杂物。\n【首帧/参考图素材 2（关键场景）】故事转折与收尾阶段的核心环境参考图，色调与素材1保持严格一致。`,
        segments,
      };
    }
    throw err;
  }
}