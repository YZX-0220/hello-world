import { ref, computed } from 'vue';
import { WORKSPACE_TOUR_STEPS, type TourStep } from './tourConfig';

const TOUR_STORAGE_PREFIX = 'hw_onboarding_v1_';
const COACHMARK_PREFIX = 'hw_coachmark_v1_';

const isTourOpen = ref(false);
const currentStepIndex = ref(0);

export function useOnboarding() {
  const steps = WORKSPACE_TOUR_STEPS;
  const totalSteps = steps.length;
  const currentStep = computed<TourStep | null>(() =>
    isTourOpen.value ? steps[currentStepIndex.value] || null : null
  );

  function getTourKey(accountId?: string) {
    return `${TOUR_STORAGE_PREFIX}${accountId || 'guest'}`;
  }

  /** 首次进入工作台画布时自动检查是否需要开启新手引导 */
  function checkAndStartWorkspaceTour(accountId?: string) {
    try {
      const done = localStorage.getItem(getTourKey(accountId));
      if (!done) {
        currentStepIndex.value = 0;
        isTourOpen.value = true;
      }
    } catch {
      // 忽略隐私模式 localStorage 异常
    }
  }

  /** 手动点击顶部「？新手引导」按钮随时重播 */
  function startTourManually() {
    currentStepIndex.value = 0;
    isTourOpen.value = true;
  }

  function nextStep(onBeforeStepChange?: (nextStepId: string) => void) {
    if (currentStepIndex.value < totalSteps - 1) {
      const nextIdx = currentStepIndex.value + 1;
      const nextStepObj = steps[nextIdx];
      if (onBeforeStepChange && nextStepObj) {
        onBeforeStepChange(nextStepObj.id);
      }
      currentStepIndex.value = nextIdx;
    } else {
      finishTour();
    }
  }

  function prevStep() {
    if (currentStepIndex.value > 0) {
      currentStepIndex.value--;
    }
  }

  function finishTour(accountId?: string) {
    isTourOpen.value = false;
    currentStepIndex.value = 0;
    try {
      localStorage.setItem(getTourKey(accountId), 'completed');
    } catch {
      // ignore
    }
  }

  /** 支线微提示条（如 3D 视角弹窗、剪辑器首次进入提示）：判断是否已读 */
  function shouldShowCoachmark(moduleKey: 'p3d' | 'editor'): boolean {
    try {
      return !localStorage.getItem(`${COACHMARK_PREFIX}${moduleKey}`);
    } catch {
      return false;
    }
  }

  function dismissCoachmark(moduleKey: 'p3d' | 'editor') {
    try {
      localStorage.setItem(`${COACHMARK_PREFIX}${moduleKey}`, '1');
    } catch {
      // ignore
    }
  }

  return {
    isTourOpen,
    currentStepIndex,
    totalSteps,
    currentStep,
    checkAndStartWorkspaceTour,
    startTourManually,
    nextStep,
    prevStep,
    finishTour,
    shouldShowCoachmark,
    dismissCoachmark,
  };
}