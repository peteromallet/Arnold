import type { CSSProperties } from 'react';
import type { TimelineRow } from '@/tools/video-editor/types/timeline-canvas.ts';

export type CropValues = { cropTop: number; cropBottom: number; cropLeft: number; cropRight: number };
export type OverlayBounds = { x: number; y: number; width: number; height: number };
export type OverlayLayout = { left: number; top: number; width: number; height: number };

export const MIN_CLIP_SIZE = 20;
export const MAX_CROP_FRACTION = 0.99;

export const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

export const normalizeCropValues = (cropValues?: Partial<CropValues>): CropValues => {
  let cropTop = clamp(cropValues?.cropTop ?? 0, 0, 1);
  let cropBottom = clamp(cropValues?.cropBottom ?? 0, 0, 1);
  let cropLeft = clamp(cropValues?.cropLeft ?? 0, 0, 1);
  let cropRight = clamp(cropValues?.cropRight ?? 0, 0, 1);

  const horizontalTotal = cropLeft + cropRight;
  if (horizontalTotal > MAX_CROP_FRACTION) {
    const scale = MAX_CROP_FRACTION / horizontalTotal;
    cropLeft *= scale;
    cropRight *= scale;
  }

  const verticalTotal = cropTop + cropBottom;
  if (verticalTotal > MAX_CROP_FRACTION) {
    const scale = MAX_CROP_FRACTION / verticalTotal;
    cropTop *= scale;
    cropBottom *= scale;
  }

  return { cropTop, cropBottom, cropLeft, cropRight };
};

export const getVisibleBoundsFromCrop = (fullBounds: OverlayBounds, cropValues: CropValues): OverlayBounds => {
  const normalizedCrop = normalizeCropValues(cropValues);
  const visibleWidthFactor = Math.max(0.01, 1 - normalizedCrop.cropLeft - normalizedCrop.cropRight);
  const visibleHeightFactor = Math.max(0.01, 1 - normalizedCrop.cropTop - normalizedCrop.cropBottom);

  return {
    x: fullBounds.x + fullBounds.width * normalizedCrop.cropLeft,
    y: fullBounds.y + fullBounds.height * normalizedCrop.cropTop,
    width: fullBounds.width * visibleWidthFactor,
    height: fullBounds.height * visibleHeightFactor,
  };
};

export const getFullBoundsFromVisibleBounds = (visibleBounds: OverlayBounds, cropValues: CropValues): OverlayBounds => {
  const normalizedCrop = normalizeCropValues(cropValues);
  const visibleWidthFactor = Math.max(0.01, 1 - normalizedCrop.cropLeft - normalizedCrop.cropRight);
  const visibleHeightFactor = Math.max(0.01, 1 - normalizedCrop.cropTop - normalizedCrop.cropBottom);
  const fullWidth = visibleBounds.width / visibleWidthFactor;
  const fullHeight = visibleBounds.height / visibleHeightFactor;

  return {
    x: visibleBounds.x - fullWidth * normalizedCrop.cropLeft,
    y: visibleBounds.y - fullHeight * normalizedCrop.cropTop,
    width: fullWidth,
    height: fullHeight,
  };
};

export const toOverlayStyle = (
  bounds: OverlayBounds,
  layout: OverlayLayout,
  compositionWidth: number,
  compositionHeight: number,
): CSSProperties => ({
  left: (bounds.x / compositionWidth) * layout.width,
  top: (bounds.y / compositionHeight) * layout.height,
  width: (bounds.width / compositionWidth) * layout.width,
  height: (bounds.height / compositionHeight) * layout.height,
});

export function getVisibleClipIds(rows: TimelineRow[], time: number): string {
  const ids: string[] = [];
  for (const row of rows) {
    if (!row.id.startsWith('V')) continue;
    for (const action of row.actions) {
      if (time >= action.start && time < action.end) ids.push(action.id);
    }
  }
  return ids.join(',');
}
