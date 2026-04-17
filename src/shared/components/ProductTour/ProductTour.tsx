import {
  useEffect,
  useRef,
  useState,
  useCallback
} from 'react';
import { useNavigate } from 'react-router-dom';
import Joyride, { CallBackProps, STATUS, EVENTS, ACTIONS } from 'react-joyride';
import { tourSteps } from './tourSteps';
import {
  getJoyrideAdvanceBehavior,
  getSpotlightAdvanceBehavior,
} from './stateMachine';
import { useProductTour } from '@/shared/hooks/useProductTour';
import { TOOL_ROUTES } from '@/shared/lib/tooling/toolRoutes';
import { dispatchAppEvent } from '@/shared/lib/typedEvents';
import { usePanesStore } from '@/shared/state/panesStore';
import { CustomTooltip } from './CustomTooltip';
import { scheduleBoundedTargetWait } from './waitForTarget';
type ScheduleTimeout = (callback: () => void, delayMs: number) => ReturnType<typeof setTimeout>;

function useManagedTimeouts() {
  const timeoutIdsRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());

  const scheduleTimeout = useCallback<ScheduleTimeout>((callback, delayMs) => {
    const timeoutId = setTimeout(() => {
      timeoutIdsRef.current.delete(timeoutId);
      callback();
    }, delayMs);
    timeoutIdsRef.current.add(timeoutId);
    return timeoutId;
  }, []);

  const clearScheduledTimeouts = useCallback(() => {
    for (const timeoutId of timeoutIdsRef.current) {
      clearTimeout(timeoutId);
    }
    timeoutIdsRef.current.clear();
  }, []);

  useEffect(() => () => {
    clearScheduledTimeouts();
  }, [clearScheduledTimeouts]);

  return { scheduleTimeout, clearScheduledTimeouts };
}

function pauseThenAdvance(
  nextIndex: number,
  setStepIndex: (value: number) => void,
  setIsPaused: (value: boolean) => void,
  delayMs: number,
  scheduleTimeout: ScheduleTimeout,
) {
  setIsPaused(true);
  scheduleTimeout(() => {
    setStepIndex(nextIndex);
    setIsPaused(false);
  }, delayMs);
}

function dispatchTourEvent(name: 'openGenerationModal' | 'closeGenerationModal') {
  dispatchAppEvent(name);
}

function useTourProgressState(isRunning: boolean, resetAllPaneLocks: () => void) {
  const [stepIndex, setStepIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const hasInitializedRef = useRef(false);

  useEffect(() => {
    if (isRunning && !hasInitializedRef.current) {
      hasInitializedRef.current = true;
      setStepIndex(0);
      setIsPaused(false);
      resetAllPaneLocks();
    } else if (!isRunning) {
      hasInitializedRef.current = false;
    }
  }, [isRunning, resetAllPaneLocks]);

  return { stepIndex, setStepIndex, isPaused, setIsPaused };
}

function useSpotlightClickAdvance(input: {
  isRunning: boolean;
  isPaused: boolean;
  stepIndex: number;
  setStepIndex: (value: number) => void;
  setIsPaused: (value: boolean) => void;
  setIsTasksPaneLocked: (locked: boolean) => void;
  scheduleTimeout: ScheduleTimeout;
}) {
  const {
    isRunning,
    isPaused,
    stepIndex,
    setStepIndex,
    setIsPaused,
    setIsTasksPaneLocked,
    scheduleTimeout,
  } = input;

  useEffect(() => {
    if (!isRunning || isPaused) {
      return;
    }

    const currentStep = tourSteps[stepIndex];
    if (!currentStep?.spotlightClicks) {
      return;
    }

    const target = document.querySelector(currentStep.target as string);
    if (!target) {
      return;
    }

    const handleClick = () => {
      const nextIndex = stepIndex + 1;
      const behavior = getSpotlightAdvanceBehavior(stepIndex);

      if (behavior.lockTasksPane) {
        setIsTasksPaneLocked(true);
      }

      if (behavior.delayMs) {
        pauseThenAdvance(nextIndex, setStepIndex, setIsPaused, behavior.delayMs, scheduleTimeout);
        return;
      }

      setStepIndex(nextIndex);
    };

    target.addEventListener('click', handleClick);
    return () => target.removeEventListener('click', handleClick);
  }, [isPaused, isRunning, scheduleTimeout, setIsPaused, setIsTasksPaneLocked, setStepIndex, stepIndex]);
}

function useJoyrideCallback(input: {
  completeTour: () => void;
  skipTour: () => void;
  setIsGenerationsPaneLocked: (locked: boolean) => void;
  setIsTasksPaneLocked: (locked: boolean) => void;
  setStepIndex: (value: number) => void;
  setIsPaused: (value: boolean) => void;
  navigate: (path: string) => void;
  scheduleTimeout: ScheduleTimeout;
}) {
  const {
    completeTour,
    skipTour,
    setIsGenerationsPaneLocked,
    setIsTasksPaneLocked,
    setStepIndex,
    setIsPaused,
    navigate,
    scheduleTimeout,
  } = input;

  return useCallback((data: CallBackProps) => {
    const { status, index, type, action } = data;

    if (type === EVENTS.STEP_AFTER || type === EVENTS.TARGET_NOT_FOUND) {
      const nextIndex = index + (action === ACTIONS.PREV ? -1 : 1);
      const behavior = getJoyrideAdvanceBehavior(index, action);

      if (behavior.type === 'advance') {
        setStepIndex(nextIndex);
      } else if (behavior.type === 'pause') {
        if (behavior.dispatchEvent) {
          dispatchTourEvent(behavior.dispatchEvent);
        }
        if (behavior.lockGenerationsPane) {
          setIsGenerationsPaneLocked(true);
        }
        if (behavior.lockTasksPane) {
          setIsTasksPaneLocked(true);
        }
        pauseThenAdvance(nextIndex, setStepIndex, setIsPaused, behavior.delayMs, scheduleTimeout);
      } else if (behavior.type === 'waitForTarget') {
        if (behavior.dispatchEvent) {
          dispatchTourEvent(behavior.dispatchEvent);
        }
        if (behavior.releaseGenerationsPane) {
          setIsGenerationsPaneLocked(false);
        }
        setIsPaused(true);
        scheduleBoundedTargetWait({
          delayMs: behavior.delayMs,
          fallbackIndex: nextIndex + 1,
          maxRetries: behavior.maxRetries,
          nextIndex,
          queryTarget: (selector) => document.querySelector(selector),
          resumeDelayMs: behavior.resumeDelayMs,
          scheduleTimeout,
          selector: behavior.selector,
          setIsPaused,
          setStepIndex,
        });
      } else {
        const target = document.querySelector(behavior.selector) as HTMLElement | null;
        target?.click();
        pauseThenAdvance(nextIndex, setStepIndex, setIsPaused, behavior.delayMs, scheduleTimeout);
      }
    }

    if (status === STATUS.FINISHED) {
      completeTour();
      navigate(TOOL_ROUTES.TRAVEL_BETWEEN_IMAGES);
    } else if (status === STATUS.SKIPPED) {
      skipTour();
    }
  }, [
    completeTour,
    navigate,
    setIsGenerationsPaneLocked,
    setIsPaused,
    setIsTasksPaneLocked,
    setStepIndex,
    scheduleTimeout,
    skipTour,
  ]);
}

export function ProductTour() {
  const { isRunning, completeTour, skipTour } = useProductTour();
  const setIsGenerationsPaneLocked = usePanesStore((state) => state.setIsGenerationsPaneLocked);
  const setIsTasksPaneLocked = usePanesStore((state) => state.setIsTasksPaneLocked);
  const resetAllPaneLocks = usePanesStore((state) => state.resetAllPaneLocks);
  const navigate = useNavigate();
  const { scheduleTimeout, clearScheduledTimeouts } = useManagedTimeouts();
  const { stepIndex, setStepIndex, isPaused, setIsPaused } = useTourProgressState(
    isRunning,
    resetAllPaneLocks
  );

  useEffect(() => {
    if (!isRunning) {
      clearScheduledTimeouts();
    }
  }, [clearScheduledTimeouts, isRunning]);

  useSpotlightClickAdvance({
    isRunning,
    isPaused,
    stepIndex,
    setStepIndex,
    setIsPaused,
    setIsTasksPaneLocked,
    scheduleTimeout,
  });

  const handleCallback = useJoyrideCallback({
    completeTour,
    skipTour,
    setIsGenerationsPaneLocked,
    setIsTasksPaneLocked,
    setStepIndex,
    setIsPaused,
    navigate,
    scheduleTimeout,
  });

  if (!isRunning) {
    return null;
  }

  return (
    <Joyride
      steps={tourSteps}
      run={isRunning && !isPaused}
      stepIndex={stepIndex}
      continuous
      scrollToFirstStep
      showSkipButton
      showProgress
      disableCloseOnEsc={false}
      disableOverlayClose
      callback={handleCallback}
      tooltipComponent={CustomTooltip}
      styles={{
        options: {
          zIndex: 100010,
          arrowColor: 'hsl(var(--background))',
        },
        spotlight: {
          borderRadius: 8,
          transition: 'opacity 0.3s ease, transform 0.3s ease',
        },
        overlay: {
          backgroundColor: 'hsl(0 0% 0% / 0.5)',
          transition: 'opacity 0.3s ease',
        },
      }}
      floaterProps={{
        styles: {
          floater: {
            filter: 'drop-shadow(0 4px 12px hsl(0 0% 0% / 0.15))',
            transition: 'opacity 0.3s ease, transform 0.3s ease',
          },
        },
      }}
    />
  );
}
