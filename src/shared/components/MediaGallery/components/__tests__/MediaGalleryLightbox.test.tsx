import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import type { GeneratedImageWithMetadata } from '../../types';
import type { GenerationRow } from '@/domains/generation/types';
import { MediaGalleryLightbox } from '../MediaGalleryLightbox';

const mediaLightboxSpy = vi.fn();
const useLocalMediaUrlMock = vi.fn();

vi.mock('@/domains/media-lightbox/MediaLightbox', () => ({
  MediaLightbox: (props: unknown) => {
    mediaLightboxSpy(props);
    return null;
  },
}));

vi.mock('@/shared/media/localMediaResolver', () => ({
  useLocalMediaUrl: (media: unknown) => useLocalMediaUrlMock(media),
}));

vi.mock('@/shared/components/TaskDetails/TaskDetailsModal', () => ({
  TaskDetailsModal: () => null,
}));

vi.mock('@/domains/generation/components/GenerationDetails', () => ({
  GenerationDetails: () => null,
}));

function buildMedia(overrides: Partial<GeneratedImageWithMetadata>): GeneratedImageWithMetadata {
  return {
    id: 'gen-1',
    url: 'https://example.com/image.png',
    metadata: {},
    createdAt: '2025-01-01T00:00:00Z',
    ...overrides,
  } as GeneratedImageWithMetadata;
}

function buildLightboxMedia(overrides: Partial<GenerationRow>): GenerationRow {
  return {
    id: 'gen-1',
    location: 'https://example.com/image.png',
    metadata: {},
    starred: false,
    ...overrides,
  };
}

function renderLightbox({
  activeLightboxMedia,
  lightboxMedia,
  isMobile = false,
  onShowTaskDetails = vi.fn(),
}: {
  activeLightboxMedia: GeneratedImageWithMetadata | null;
  lightboxMedia: GenerationRow | null;
  isMobile?: boolean;
  onShowTaskDetails?: () => void;
}) {
  return render(
    <MediaGalleryLightbox
      session={{
        activeLightboxMedia,
        lightboxMedia,
        autoEnterEditMode: false,
        onClose: vi.fn(),
        filteredImages: [],
        isServerPagination: false,
        totalPages: 1,
        onNext: vi.fn(),
        onPrevious: vi.fn(),
        hasNext: false,
        hasPrevious: false,
        handleNavigateToGeneration: vi.fn(),
        handleOpenExternalGeneration: vi.fn(),
        simplifiedShotOptions: [],
        selectedShotIdLocal: 'all',
        onShotChange: vi.fn(),
        showTickForImageId: null,
        setShowTickForImageId: vi.fn(),
        isMobile,
        showTaskDetailsModal: false,
        setShowTaskDetailsModal: vi.fn(),
        selectedImageForDetails: null,
        setSelectedImageForDetails: vi.fn(),
        onShowTaskDetails,
        taskDetailsData: null,
      }}
    />
  );
}

describe('MediaGalleryLightbox', () => {
  beforeEach(() => {
    mediaLightboxSpy.mockClear();
    useLocalMediaUrlMock.mockReturnValue({
      url: 'https://example.com/resolved.png',
      state: 'ready',
    });
  });

  it('uses session-owned lightbox media while preserving auto-enter edit mode from active metadata', () => {
    const active = buildMedia({
      id: 'gen-1',
      metadata: { __autoEnterEditMode: true, source: 'active' } as GeneratedImageWithMetadata['metadata'],
    });
    const lightboxMedia = buildLightboxMedia({
      id: 'gen-1',
      starred: true,
      metadata: { source: 'session' },
    });

    renderLightbox({ activeLightboxMedia: active, lightboxMedia });

    const props = mediaLightboxSpy.mock.calls[0]?.[0] as {
      actions?: { starred?: boolean };
      features?: { initialEditActive?: boolean };
      media?: GenerationRow;
    };
    expect(props.actions?.starred).toBe(true);
    expect(props.features?.initialEditActive).toBe(true);
    expect(props.media?.metadata).toEqual({ source: 'session' });
    expect(props.media?.location).toBe('https://example.com/resolved.png');
  });

  it('disables image edit tools for video media and forwards mobile task details callbacks', () => {
    const active = buildMedia({
      id: 'gen-video',
      type: 'video',
      metadata: { source: 'active-video' } as GeneratedImageWithMetadata['metadata'],
    });
    const onShowTaskDetails = vi.fn();
    const lightboxMedia = buildLightboxMedia({ id: 'gen-video', starred: false, metadata: { source: 'video' } });

    renderLightbox({
      activeLightboxMedia: active,
      lightboxMedia,
      isMobile: true,
      onShowTaskDetails,
    });

    const props = mediaLightboxSpy.mock.calls[0]?.[0] as {
      features?: { showImageEditTools?: boolean };
      videoProps?: { onShowTaskDetails?: () => void };
    };
    expect(props.features?.showImageEditTools).toBe(false);
    expect(props.videoProps?.onShowTaskDetails).toBe(onShowTaskDetails);
  });
});
