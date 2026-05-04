export type RenderBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type RenderCropValues = {
  cropTop: number;
  cropBottom: number;
  cropLeft: number;
  cropRight: number;
};

export type ViewportMediaLayout = {
  fullBounds: RenderBounds;
  visibleBounds: RenderBounds;
  renderBounds: RenderBounds;
  mediaBounds: RenderBounds;
  cropValues: RenderCropValues;
};

export type IntrinsicMediaSize = {
  width?: number;
  height?: number;
};

const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

export const normalizeRenderCropValues = (cropValues?: Partial<RenderCropValues>): RenderCropValues => {
  let cropTop = clamp(cropValues?.cropTop ?? 0, 0, 1);
  let cropBottom = clamp(cropValues?.cropBottom ?? 0, 0, 1);
  let cropLeft = clamp(cropValues?.cropLeft ?? 0, 0, 1);
  let cropRight = clamp(cropValues?.cropRight ?? 0, 0, 1);

  const horizontalTotal = cropLeft + cropRight;
  if (horizontalTotal > 0.99) {
    const scale = 0.99 / horizontalTotal;
    cropLeft *= scale;
    cropRight *= scale;
  }

  const verticalTotal = cropTop + cropBottom;
  if (verticalTotal > 0.99) {
    const scale = 0.99 / verticalTotal;
    cropTop *= scale;
    cropBottom *= scale;
  }

  return {cropTop, cropBottom, cropLeft, cropRight};
};

export const getVisibleBoundsFromCrop = (
  fullBounds: RenderBounds,
  cropValues?: Partial<RenderCropValues>,
): RenderBounds => {
  const normalizedCrop = normalizeRenderCropValues(cropValues);
  const visibleWidthFactor = Math.max(0.01, 1 - normalizedCrop.cropLeft - normalizedCrop.cropRight);
  const visibleHeightFactor = Math.max(0.01, 1 - normalizedCrop.cropTop - normalizedCrop.cropBottom);

  return {
    x: fullBounds.x + fullBounds.width * normalizedCrop.cropLeft,
    y: fullBounds.y + fullBounds.height * normalizedCrop.cropTop,
    width: fullBounds.width * visibleWidthFactor,
    height: fullBounds.height * visibleHeightFactor,
  };
};

export const getIntrinsicMediaSize = (resolution?: string | null): IntrinsicMediaSize => {
  if (!resolution) {
    return {};
  }

  const [widthText, heightText] = resolution.toLowerCase().split('x');
  const width = Number(widthText);
  const height = Number(heightText);
  return Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0
    ? {width, height}
    : {};
};

export const computeRenderBounds = (
  bounds: RenderBounds,
  compositionWidth: number,
  compositionHeight: number,
): RenderBounds => {
  const right = Math.min(bounds.x + bounds.width, compositionWidth);
  const bottom = Math.min(bounds.y + bounds.height, compositionHeight);
  const x = Math.max(0, bounds.x);
  const y = Math.max(0, bounds.y);

  return {
    x,
    y,
    width: Math.max(0, right - x),
    height: Math.max(0, bottom - y),
  };
};

export const hasRenderableBounds = (bounds: RenderBounds): boolean => {
  return bounds.width > 0 && bounds.height > 0;
};

export const computeViewportMediaLayout = ({
  fullBounds,
  cropValues,
  compositionWidth,
  compositionHeight,
  intrinsicWidth,
  intrinsicHeight,
}: {
  fullBounds: RenderBounds;
  cropValues?: Partial<RenderCropValues>;
  compositionWidth: number;
  compositionHeight: number;
  intrinsicWidth?: number;
  intrinsicHeight?: number;
}): ViewportMediaLayout | null => {
  const normalizedCrop = normalizeRenderCropValues(cropValues);
  const visibleBounds = getVisibleBoundsFromCrop(fullBounds, normalizedCrop);
  const renderBounds = computeRenderBounds(visibleBounds, compositionWidth, compositionHeight);

  if (!hasRenderableBounds(renderBounds)) {
    return null;
  }

  const safeIntrinsicWidth = intrinsicWidth && intrinsicWidth > 0 ? intrinsicWidth : fullBounds.width;
  const safeIntrinsicHeight = intrinsicHeight && intrinsicHeight > 0 ? intrinsicHeight : fullBounds.height;
  const coverScale = Math.max(
    fullBounds.width / Math.max(1, safeIntrinsicWidth),
    fullBounds.height / Math.max(1, safeIntrinsicHeight),
  );
  const mediaWidth = safeIntrinsicWidth * coverScale;
  const mediaHeight = safeIntrinsicHeight * coverScale;
  const mediaOffsetX = (fullBounds.width - mediaWidth) / 2;
  const mediaOffsetY = (fullBounds.height - mediaHeight) / 2;
  const viewportOffsetX = renderBounds.x - fullBounds.x;
  const viewportOffsetY = renderBounds.y - fullBounds.y;

  return {
    fullBounds,
    visibleBounds,
    renderBounds,
    mediaBounds: {
      x: mediaOffsetX - viewportOffsetX,
      y: mediaOffsetY - viewportOffsetY,
      width: mediaWidth,
      height: mediaHeight,
    },
    cropValues: normalizedCrop,
  };
};
