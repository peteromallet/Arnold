/**
 * LineageGifModal
 *
 * Modal component that displays the lineage chain as a grid of images
 * (4 across, scrollable) with a Download GIF button at the bottom.
 */

import React, { useState } from 'react';
import { Download, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Progress } from '@/shared/components/ui/progress';
import { useLineageChain } from '@/shared/hooks/variants/useLineageChain';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
interface CreateGifProgress {
  stage: 'loading' | 'encoding' | 'complete';
  current: number;
  total: number;
  message: string;
}

function loadImageFromBlobUrl(blobUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Failed to load image from blob'));
    img.src = blobUrl;
  });
}

async function createLineageGif(
  imageUrls: string[],
  options: { frameDelay?: number; width?: number } = {},
  onProgress?: (progress: CreateGifProgress) => void
): Promise<Blob> {
  const { frameDelay = 800, width = 512 } = options;
  if (imageUrls.length === 0) throw new Error('No images provided for GIF creation');

  onProgress?.({ stage: 'loading', current: 0, total: imageUrls.length, message: 'Loading images...' });

  const images: HTMLImageElement[] = [];
  const blobUrls: string[] = [];

  for (let i = 0; i < imageUrls.length; i++) {
    try {
      const response = await fetch(imageUrls[i]);
      if (!response.ok) continue;
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      blobUrls.push(blobUrl);
      const img = await loadImageFromBlobUrl(blobUrl);
      images.push(img);
      onProgress?.({ stage: 'loading', current: i + 1, total: imageUrls.length, message: `Loading images ${i + 1}/${imageUrls.length}` });
    } catch { /* Skip failed images */ }
  }

  if (images.length === 0) {
    blobUrls.forEach(url => URL.revokeObjectURL(url));
    throw new Error('No images could be loaded');
  }

  const firstImage = images[0];
  const aspectRatio = firstImage.width / firstImage.height;
  const height = Math.round(width / aspectRatio);

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });

  if (!ctx) {
    blobUrls.forEach(url => URL.revokeObjectURL(url));
    throw new Error('Could not get canvas context');
  }

  const { GIFEncoder, quantize, applyPalette } = await import('gifenc');
  const gif = GIFEncoder();
  onProgress?.({ stage: 'encoding', current: 0, total: images.length, message: 'Encoding frames...' });

  for (let i = 0; i < images.length; i++) {
    const img = images[i];
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, width, height);

    const imgAspect = img.width / img.height;
    const targetAspect = width / height;
    let drawWidth: number, drawHeight: number, drawX: number, drawY: number;

    if (imgAspect > targetAspect) {
      drawWidth = width;
      drawHeight = width / imgAspect;
      drawX = 0;
      drawY = (height - drawHeight) / 2;
    } else {
      drawHeight = height;
      drawWidth = height * imgAspect;
      drawX = (width - drawWidth) / 2;
      drawY = 0;
    }

    ctx.drawImage(img, drawX, drawY, drawWidth, drawHeight);
    const imageData = ctx.getImageData(0, 0, width, height);
    const rgbaPixels = new Uint8Array(imageData.data);
    const palette = quantize(rgbaPixels, 256, { format: 'rgba4444' });
    const indexedPixels = applyPalette(rgbaPixels, palette);
    gif.writeFrame(indexedPixels, width, height, { palette, delay: frameDelay / 10 });
    onProgress?.({ stage: 'encoding', current: i + 1, total: images.length, message: `Encoding frames ${i + 1}/${images.length}` });
  }

  blobUrls.forEach(url => URL.revokeObjectURL(url));
  gif.finish();
  const gifBytes = gif.bytes();
  const blob = new Blob([gifBytes], { type: 'image/gif' });
  onProgress?.({ stage: 'complete', current: images.length, total: images.length, message: 'Complete!' });
  return blob;
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { ModalContainer } from '@/shared/components/ModalContainer';

interface LineageGifModalProps {
  open: boolean;
  onClose: () => void;
  variantId: string | null;
}

type DownloadState =
  | { status: 'idle' }
  | { status: 'generating'; progress: CreateGifProgress }
  | { status: 'error'; message: string };

export const LineageGifModal: React.FC<LineageGifModalProps> = ({
  open,
  onClose,
  variantId,
}) => {
  const { selectedProjectId } = useProjectSelectionContext();
  const [downloadState, setDownloadState] = useState<DownloadState>({ status: 'idle' });

  // Fetch the lineage chain
  const { chain, isLoading: isChainLoading, hasLineage, error: chainError } = useLineageChain(
    open ? variantId : null,
    selectedProjectId ?? null,
  );

  const handleDownloadGif = async () => {
    if (chain.length === 0) return;

    setDownloadState({ status: 'generating', progress: { stage: 'loading', current: 0, total: chain.length, message: 'Starting...' } });

    try {
      const imageUrls = chain.map((item) => item.imageUrl);

      const blob = await createLineageGif(imageUrls, { frameDelay: 800 }, (progress) => {
        setDownloadState({ status: 'generating', progress });
      });

      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      downloadBlob(blob, `lineage-${timestamp}.gif`);
      setDownloadState({ status: 'idle' });
    } catch (err) {
      normalizeAndPresentError(err, { context: 'LineageGifModal', showToast: false });
      setDownloadState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Failed to generate GIF',
      });
    }
  };

  const renderContent = () => {
    if (isChainLoading) {
      return (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading lineage...</p>
        </div>
      );
    }

    if (chainError) {
      return (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <AlertCircle className="w-8 h-8 text-destructive" />
          <p className="text-sm text-muted-foreground text-center">{chainError.message}</p>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      );
    }

    if (!hasLineage || chain.length < 2) {
      return (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <AlertCircle className="w-8 h-8 text-destructive" />
          <p className="text-sm text-muted-foreground text-center">No lineage found for this image</p>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      );
    }

    const isGenerating = downloadState.status === 'generating';
    const progress = isGenerating ? downloadState.progress : null;
    const percentage = progress && progress.total > 0
      ? Math.round((progress.current / progress.total) * 100)
      : 0;

    return (
      <div className="flex flex-col gap-4">
        {/* Image grid - 4 across, scrollable */}
        <div className="max-h-[60vh] overflow-y-auto">
          <div className="grid grid-cols-4 gap-2">
            {chain.map((item, index) => (
              <div
                key={item.id}
                className="relative aspect-square rounded-md overflow-hidden bg-muted border border-border"
              >
                <img
                  src={item.thumbnailUrl || item.imageUrl}
                  alt={`Lineage ${index + 1}`}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
                {/* Generation number badge */}
                <div className="absolute bottom-1 left-1 px-1.5 py-0.5 text-xs font-medium bg-background/80 rounded">
                  {index + 1}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Info text */}
        <p className="text-xs text-muted-foreground text-center">
          {chain.length} images · Oldest to newest (left to right, top to bottom)
        </p>

        {/* Download button with progress */}
        {isGenerating ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-full max-w-xs space-y-2">
              <Progress value={percentage} className="h-2" />
              <p className="text-sm text-muted-foreground text-center">{progress?.message}</p>
            </div>
          </div>
        ) : (
          <Button onClick={handleDownloadGif} className="gap-2 self-center">
            <Download className="w-4 h-4" />
            Download GIF
          </Button>
        )}

        {/* Error message */}
        {downloadState.status === 'error' && (
          <p className="text-sm text-destructive text-center">{downloadState.message}</p>
        )}
      </div>
    );
  };

  return (
    <ModalContainer
      open={open}
      onOpenChange={(isOpen) => !isOpen && onClose()}
      size="large"
      title="Evolution"
    >
      {renderContent()}
    </ModalContainer>
  );
};
