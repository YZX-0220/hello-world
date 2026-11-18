import type { FlowNode, FlowConnection } from '@/types/canvas';

export interface TourStep {
  id: string;
  targetSelector: string;
  badge: string;
  title: string;
  content: string;
  placement: 'bottom' | 'right' | 'top-left' | 'left';
  showSampleBtn?: boolean;
  /** 进入该步骤前需要自动执行的钩子（如自动打开右侧抽屉并切到生成视频 Tab） */
  onEnter?: () => void;
}

export const WORKSPACE_TOUR_STEPS: TourStep[] = [
  {
    id: 'step-director',
    targetSelector: '[data-tour="director-btn"]',
    badge: 'STEP 1 / 5 · 顶层策划起点',
    title: '🎬 全片 AI 统筹规划向导',
    content:
      '不知道怎么写分镜提示词？点这里输入一句话核心创意，AI 会自动为您拆解多镜头剧本、匹配目标国文化禁忌，并一键在画布生成全套分镜节点。您也可以点击下方按钮直接加载一套现成示例节点体验！',
    placement: 'bottom',
    showSampleBtn: true,
  },
  {
    id: 'step-cultural',
    targetSelector: '[data-tour="cultural-btn"]',
    badge: 'STEP 2 / 5 · 国际传播避坑',
    title: '🌐 国际传播叙事指引与受众偏好',
    content:
      '面向海外受众创作时，点此多选目标传播国家（如美、英、法、日、印等），系统会自动组合对应的文化禁忌与负面提示词（Negative Prompt）并注入画布节点。',
    placement: 'right',
  },
  {
    id: 'step-canvas-node',
    targetSelector: '.canvas-node',
    badge: 'STEP 3 / 5 · 三级点选与流光连线',
    title: '🔗 节点连线与三级点选技巧',
    content:
      '• 单击节点：自动关联选中所有连线节点\n• 双击节点：仅单独选中当前 1 个节点\n• 按住 Shift 点击：精准加减节点\n悬停节点右侧圆孔「+」即可拉出流光连线传递上下文。',
    placement: 'right',
  },
  {
    id: 'step-agent-orb',
    targetSelector: '[data-tour="agent-orb"]',
    badge: 'STEP 4 / 5 · 多模态创作中枢',
    title: '✨ 唤出右侧「创作助手」',
    content:
      '点击右下角悬浮球（或直接点本卡片“下一步”），即可滑出创作助手抽屉：支持与 AI 对话打磨文案、调用 Seedream 素材生图，以及将选中节点合成视频。',
    placement: 'top-left',
  },
  {
    id: 'step-video-review',
    targetSelector: '[data-tour="prepare-video-btn"]',
    badge: 'STEP 5 / 5 · 防误触双重确认',
    title: '🛡️ 先「AI 审理方案」，再安全生成',
    content:
      '在「生成视频」标签页选好通道、时长与清晰度后，请先点击【1. AI审理方案】前置核查参数与图片合规性，审理通过后再点击【2. 确认并生成视频】，杜绝参数报错与额度浪费！',
    placement: 'left',
  },
];

/** 一键生成的“非遗竹编出海”新手示例节点网络 */
export function buildSampleProjectGraph(genId: () => string): {
  nodes: FlowNode[];
  connections: FlowConnection[];
} {
  const styleId = genId();
  const negId = genId();
  const seg1Id = genId();

  const nodes: FlowNode[] = [
    {
      id: styleId,
      type: 'text',
      title: '整体风格',
      x: 150,
      y: 130,
      content:
        '【整体视觉风格】4K纪录片电影质感，柔和晨光与丁达尔光效，浅景深，原木暖色调统一，镜头平稳缓推，富有东方美学呼吸感。',
    },
    {
      id: negId,
      type: 'text',
      title: '负面提示词',
      x: 150,
      y: 460,
      content:
        '负面提示词：3D卡通感、劣质塑料感、画面闪烁、肢体畸变、多余手指、宗教敏感符号、刺眼高饱和霓虹、文字水印',
    },
    {
      id: seg1Id,
      type: 'text',
      title: '片段一（示例分镜）',
      x: 500,
      y: 260,
      content:
        '0-5秒：全景镜头缓慢推进，清晨薄雾中的翠绿竹林，阳光穿透竹叶洒下金色光斑；\n5-10秒：切近景特写，老匠人布满纹理的双手持篾刀利落破开青竹，竹丝在指尖轻盈上下交织；\n10-15秒：中景环绕，一盏现代北欧风竹编台灯在木桌上点亮，暖黄光芒从竹编缝隙温柔透出。',
    },
  ];

  const connections: FlowConnection[] = [
    { id: genId(), from: styleId, to: seg1Id },
    { id: genId(), from: negId, to: seg1Id },
  ];

  return { nodes, connections };
}