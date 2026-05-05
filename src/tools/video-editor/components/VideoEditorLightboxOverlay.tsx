import type { VideoEditorLightboxIndicator } from '@/tools/video-editor/hooks/useVideoEditorLightboxNavigation.ts';

export function VideoEditorLightboxOverlay({
  indicator,
}: {
  indicator: VideoEditorLightboxIndicator;
}) {
  const showListPosition = indicator.positionInList.total > 1;
  if (!indicator.shotGroupLabel && !showListPosition) {
    return null;
  }

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed left-1/2 top-4 z-[100001] -translate-x-1/2"
    >
      <div className="inline-flex items-center gap-2 rounded-full bg-black/60 px-3 py-1.5 text-sm text-white backdrop-blur-sm transition-opacity duration-200">
        {indicator.shotGroupLabel ? (
          <>
            <span className="inline-flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={indicator.shotGroupColor ? { backgroundColor: indicator.shotGroupColor } : undefined}
              />
              <span>{indicator.shotGroupLabel}</span>
            </span>
            {indicator.positionInGroup ? (
              <span className="text-white/80">{`${indicator.positionInGroup.current} of ${indicator.positionInGroup.total}`}</span>
            ) : null}
          </>
        ) : null}
        {showListPosition ? (
          <span className="text-white/60">{`${indicator.positionInList.current} of ${indicator.positionInList.total}`}</span>
        ) : null}
      </div>
    </div>
  );
}
