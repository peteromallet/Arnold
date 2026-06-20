import { describe, expect, it, vi } from 'vitest';
import { scheduleBoundedTargetWait } from './waitForTarget';

describe('scheduleBoundedTargetWait', () => {
  it('advances after the target appears within the retry budget', () => {
    const scheduleTimeout = vi.fn((callback: () => void) => {
      callback();
      return 0 as ReturnType<typeof setTimeout>;
    });
    const queryTarget = vi.fn()
      .mockReturnValueOnce(null)
      .mockReturnValueOnce(document.createElement('div'));
    const setStepIndex = vi.fn();
    const setIsPaused = vi.fn();

    scheduleBoundedTargetWait({
      delayMs: 10,
      fallbackIndex: 5,
      maxRetries: 3,
      nextIndex: 4,
      queryTarget,
      resumeDelayMs: 5,
      scheduleTimeout,
      selector: '[data-tour="first-shot"]',
      setIsPaused,
      setStepIndex,
    });

    expect(queryTarget).toHaveBeenCalledTimes(2);
    expect(setStepIndex).toHaveBeenCalledWith(4);
    expect(setIsPaused).toHaveBeenCalledWith(false);
  });

  it('skips ahead when the target never appears before max retries', () => {
    const scheduleTimeout = vi.fn((callback: () => void) => {
      callback();
      return 0 as ReturnType<typeof setTimeout>;
    });
    const queryTarget = vi.fn(() => null);
    const setStepIndex = vi.fn();
    const setIsPaused = vi.fn();

    scheduleBoundedTargetWait({
      delayMs: 10,
      fallbackIndex: 8,
      maxRetries: 2,
      nextIndex: 7,
      queryTarget,
      resumeDelayMs: 5,
      scheduleTimeout,
      selector: '[data-tour="missing"]',
      setIsPaused,
      setStepIndex,
    });

    expect(queryTarget).toHaveBeenCalledTimes(3);
    expect(setStepIndex).toHaveBeenCalledWith(8);
    expect(setIsPaused).toHaveBeenCalledWith(false);
  });
});
