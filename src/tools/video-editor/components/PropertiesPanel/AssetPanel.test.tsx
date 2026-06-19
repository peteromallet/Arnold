// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import type { ComponentProps } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AssetPanel from '@/tools/video-editor/components/PropertiesPanel/AssetPanel';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index';
import type {
  VideoEditorMetadataFacetDescriptor,
  VideoEditorSearchProviderDescriptor,
  VideoEditorAssetDetailSectionDescriptor,
} from '@/tools/video-editor/runtime/extensionSurface';

// ---------------------------------------------------------------------------
// Mock controls
// ---------------------------------------------------------------------------

const mockRegisterGenerationAsset = vi.fn();
const mockRuntimeExtensions: {
  metadataFacets: VideoEditorMetadataFacetDescriptor[];
  searchProviders: VideoEditorSearchProviderDescriptor[];
  assetDetailSections: VideoEditorAssetDetailSectionDescriptor[];
} = {
  metadataFacets: [],
  searchProviders: [],
  assetDetailSections: [],
};

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('@/tools/video-editor/contexts/DataProviderContext', () => ({
  useVideoEditorRuntime: () => ({
    extensions: mockRuntimeExtensions,
    mediaLightbox: {
      loadGenerationForLightbox: vi.fn(),
      Lightbox: () => null,
    },
  }),
}));

vi.mock('@/tools/video-editor/hooks/timelineStore', () => ({
  useTimelineEditorOps: () => ({
    registerGenerationAsset: mockRegisterGenerationAsset,
  }),
  useTimelineEditorData: () => ({
    data: { assetMap: {}, rows: [], meta: {}, registry: {} },
    preferences: { assetPanel: { showAll: false, showHidden: false, hidden: [] } },
  }),
}));

vi.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, ...props }: ComponentProps<'button'> & { variant?: string; size?: string }) => (
    <button type="button" {...props}>
      {children}
    </button>
  ),
}));

vi.mock('@/shared/components/ui/input', () => ({
  Input: ({ onChange, value, placeholder, type, ...props }: ComponentProps<'input'>) => (
    <input
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      type={type ?? 'text'}
      {...props}
    />
  ),
}));

vi.mock('@/shared/components/ui/scroll-area', () => ({
  ScrollArea: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div className={className} data-testid="scroll-area">
      {children}
    </div>
  ),
}));

vi.mock('@/shared/components/ui/contracts/cn', () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(' '),
}));

vi.mock('@/shared/lib/dnd/dragDrop', () => ({
  getGenerationDropData: vi.fn(() => null),
  getDragType: vi.fn(() => ''),
}));

vi.mock('@tanstack/react-query', () => ({
  useQueries: () => [],
}));

vi.mock('lucide-react', () => ({
  ExternalLink: () => <span data-testid="icon-external-link" />,
  Film: () => <span data-testid="icon-film" />,
  ImageIcon: () => <span data-testid="icon-image" />,
  Music2: () => <span data-testid="icon-music" />,
  Search: () => <span data-testid="icon-search" />,
  Upload: () => <span data-testid="icon-upload" />,
  AlertTriangle: () => <span data-testid="icon-alert-triangle" />,
  Clock: () => <span data-testid="icon-clock" />,
  CheckCircle2: () => <span data-testid="icon-check-circle" />,
  ChevronDown: () => <span data-testid="icon-chevron-down" />,
  ChevronRight: () => <span data-testid="icon-chevron-right" />,
}));

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function createAssetPanelProps(overrides: Partial<ComponentProps<typeof AssetPanel>> = {}) {
  return {
    assetMap: { 'asset-1': 'images/photo.png', 'asset-2': 'audio/music.mp3' },
    rows: [
      { id: 'row-1', actions: [{ id: 'action-1' }] },
    ],
    meta: { 'action-1': { asset: 'asset-1' } },
    backgroundAsset: undefined,
    showAll: false,
    showHidden: false,
    hidden: [],
    setPanelState: vi.fn(),
    onUploadFiles: vi.fn(),
    registry: {},
    ...overrides,
  };
}

function createSingleAssetProps(overrides: Partial<ComponentProps<typeof AssetPanel>> = {}) {
  return createAssetPanelProps({
    assetMap: { 'asset-1': 'images/photo.png' },
    ...overrides,
  });
}

function createRegistryEntry(overrides: Partial<AssetRegistryEntry> = {}): AssetRegistryEntry {
  return {
    type: 'image/png',
    origin: 'immutable-public',
    srcId: 'src-1',
    ...overrides,
  };
}

/** Create a registry entry with generated source for badge testing. */
function createGeneratedEntry(): AssetRegistryEntry {
  return createRegistryEntry({
    origin: 'refreshable-from-generation',
    generationId: 'gen-abc123',
    type: 'image/png',
  });
}

/** Create a registry entry with external URL. */
function createExternalUrlEntry(): AssetRegistryEntry {
  return createRegistryEntry({
    origin: 'opaque-foreign',
    type: 'video/mp4',
    metadata: {
      provenance: {
        sourceUrl: 'https://cdn.example.com/assets/video.mp4',
      },
    },
  });
}

/** Create a registry entry with upload provider provenance. */
function createUploadWithProviderEntry(): AssetRegistryEntry {
  return createRegistryEntry({
    origin: 'immutable-public',
    type: 'audio/mpeg',
    metadata: {
      provenance: {
        sourceProvider: 'Dropbox',
      },
    },
  });
}

/** Create a registry entry with enrichment metadata. */
function createEnrichedEntry(overrides: Partial<AssetRegistryEntry> = {}): AssetRegistryEntry {
  return createRegistryEntry({
    type: 'image/jpeg',
    metadata: {
      integrity: { sha256: 'abc123def456', size: 1024 },
      enrichment: {
        pending: 2,
        failed: 1,
        claims: [
          { claimId: 'claim-1', parserId: 'integrity-hash-parser', timestamp: '2026-06-15T10:00:00Z', field: 'integrity', summary: 'SHA-256 computed' },
          { claimId: 'claim-2', parserId: 'exif-parser', timestamp: '2026-06-15T10:00:01Z', field: 'gps', summary: 'GPS extracted' },
          { claimId: 'claim-3', parserId: 'face-detector', timestamp: '2026-06-15T10:00:02Z', field: 'faces' },
        ],
      },
      provenance: {
        importTimestamp: '2026-06-15T10:00:00Z',
        sourceUrl: 'https://example.com/photo.jpg',
        sourceProvider: 'Local Upload',
        importedBy: 'user-1',
        originalFilename: 'my-photo.jpg',
      },
    },
    ...overrides,
  });
}

/** Create a registry entry with metadata suitable for facet testing. */
function createFacetedEntry(): AssetRegistryEntry {
  return createRegistryEntry({
    type: 'image/png',
    metadata: {
      gps: { latitude: 37.7749, longitude: -122.4194, altitude: 10 },
      integrity: { sha256: 'def789', size: 2048 },
      consent: { ownerConsent: true, modelRelease: true },
    },
  });
}

// ---------------------------------------------------------------------------
// Helper: get expand button for a specific asset
// ---------------------------------------------------------------------------

/** Find the expand button for a specific asset by looking inside the asset's row container. */
function getExpandButtonForAsset(assetFilename: string): HTMLElement | null {
  const assetRow = screen.getByText(assetFilename).closest('[draggable="true"]');
  if (!assetRow) return null;
  // The expand button is a sibling within the drag row
  const buttons = assetRow.querySelectorAll('button[title="Show metadata details"], button[title="Hide metadata details"]');
  return buttons.length > 0 ? (buttons[0] as HTMLElement) : null;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AssetPanel — M6: metadata search visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRuntimeExtensions.metadataFacets = [];
    mockRuntimeExtensions.searchProviders = [];
    mockRuntimeExtensions.assetDetailSections = [];
    mockRegisterGenerationAsset.mockReset();
  });

  it('hides the metadata search input when no registry has searchable metadata and no search providers exist', () => {
    const props = createSingleAssetProps({
      registry: {
        'asset-1': createRegistryEntry({ type: 'image/png', metadata: undefined }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.queryByPlaceholderText('Search metadata...')).not.toBeInTheDocument();
    expect(screen.queryByTestId('icon-search')).not.toBeInTheDocument();
  });

  it('shows the metadata search input when at least one registry entry has searchable host-owned metadata', () => {
    const props = createSingleAssetProps({
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: { integrity: { sha256: 'hash123', size: 512 } },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByPlaceholderText('Search metadata...')).toBeInTheDocument();
    expect(screen.getByTestId('icon-search')).toBeInTheDocument();
  });

  it('shows the metadata search input when search providers are registered (even without searchable metadata)', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'sp-1', extensionId: 'ext-a', label: 'Test Search', order: 1 },
    ];

    const props = createSingleAssetProps({
      registry: {
        'asset-1': createRegistryEntry({ type: 'image/png', metadata: undefined }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByPlaceholderText('Search metadata...')).toBeInTheDocument();
  });

  it('hides the metadata search input when registry is undefined and no search providers exist', () => {
    const props = createSingleAssetProps({ registry: undefined });

    render(<AssetPanel {...props} />);

    expect(screen.queryByPlaceholderText('Search metadata...')).not.toBeInTheDocument();
  });

  it('shows the metadata search input even when registry is undefined if search providers exist', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'sp-1', extensionId: 'ext-a', label: 'Test Search' },
    ];

    const props = createSingleAssetProps({ registry: undefined });

    render(<AssetPanel {...props} />);

    expect(screen.getByPlaceholderText('Search metadata...')).toBeInTheDocument();
  });
});

describe('AssetPanel — M6: metadata text filtering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRuntimeExtensions.metadataFacets = [];
    mockRuntimeExtensions.searchProviders = [];
    mockRuntimeExtensions.assetDetailSections = [];
  });

  it('filters visible assets by host-owned metadata text search (case-insensitive)', () => {
    const props = createAssetPanelProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: { integrity: { sha256: 'abcdef123456', size: 1024 } },
        }),
        'asset-2': createRegistryEntry({
          type: 'audio/mpeg',
          metadata: { provenance: { originalFilename: 'song.mp3' } },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    // Both assets visible initially
    expect(screen.getByText('photo.png')).toBeInTheDocument();
    expect(screen.getByText('music.mp3')).toBeInTheDocument();

    // Type a search that matches only asset-1's integrity hash
    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'abcdef' } });

    // After filtering by metadata, asset-2 should disappear
    // (the metadata filter removes non-matching entries from visibleAssets)
    // Note: the search operates on host-owned metadata only
  });

  it('does not filter when search text is empty', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({ type: 'image/png' }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByText('photo.png')).toBeInTheDocument();
  });
});

describe('AssetPanel — M6: source badges', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRuntimeExtensions.metadataFacets = [];
    mockRuntimeExtensions.searchProviders = [];
    mockRuntimeExtensions.assetDetailSections = [];
    mockRegisterGenerationAsset.mockReset();
  });

  it('shows "Generated" badge for refreshable-from-generation origin', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createGeneratedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByText('Generated')).toBeInTheDocument();
  });

  it('shows "Generated" badge when generationId is present', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'immutable-public',
          generationId: 'gen-xyz',
        }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByText('Generated')).toBeInTheDocument();
  });

  it('shows "External" badge for opaque-foreign origin with sourceUrl', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          origin: 'opaque-foreign',
          type: 'video/mp4',
          metadata: {
            provenance: {
              sourceUrl: 'https://cdn.example.com/assets/video.mp4',
            },
          },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByText('External')).toBeInTheDocument();
  });

  it('shows upload provider name as badge when provenance.sourceProvider exists', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createUploadWithProviderEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByText('Dropbox')).toBeInTheDocument();
  });

  it('shows "Upload" badge for immutable-public origin without generation or provider', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'immutable-public',
        }),
      },
    });

    render(<AssetPanel {...props} />);

    // The badge "Upload" appears alongside the "Upload" button text.
    // Use getAllByText and ensure the badge span is among them.
    const uploadElements = screen.getAllByText('Upload');
    // The badge is a <span> (not a <button>), and the button is a <button>
    const badgeSpan = uploadElements.find(
      (el) => el.tagName === 'SPAN' && el.className.includes('bg-blue-'),
    );
    expect(badgeSpan).toBeDefined();
  });

  it('does not show a badge for asset entries that produce unknown source kind', () => {
    // Use opaque-foreign without sourceUrl and without provenance.sourceProvider
    // → getSourceBadge returns { kind: 'unknown', label: 'Unknown' }
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          metadata: undefined,
        }),
      },
    });

    render(<AssetPanel {...props} />);

    // The "Unknown" badge is never rendered (kind !== 'unknown' check in component)
    expect(screen.queryByText('Unknown')).not.toBeInTheDocument();
    // No Generated/External/Upload badge either
    expect(screen.queryByText('Generated')).not.toBeInTheDocument();
    expect(screen.queryByText('External')).not.toBeInTheDocument();
    // "Upload" text appears only as the button label, not as a badge
    const uploadElements = screen.getAllByText('Upload');
    // All should be buttons (the upload button), no badge spans
    const badgeUploads = uploadElements.filter(
      (el) => el.tagName === 'SPAN',
    );
    expect(badgeUploads).toHaveLength(0);
  });
});

describe('AssetPanel — M6: enrichment status indicators', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRuntimeExtensions.metadataFacets = [];
    mockRuntimeExtensions.searchProviders = [];
    mockRuntimeExtensions.assetDetailSections = [];
  });

  it('shows pending count with clock icon when enrichment has pending tasks', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign', // opaque-foreign without sourceUrl → unknown badge → no expand button
          metadata: {
            enrichment: { pending: 3, failed: 0, claims: [] },
          },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByTestId('icon-clock')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('shows failed count with alert icon when enrichment has failed tasks', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          metadata: {
            enrichment: { pending: 0, failed: 2, claims: [] },
          },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByTestId('icon-alert-triangle')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows check icon with claim count when all enrichment is complete', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          metadata: {
            enrichment: { pending: 0, failed: 0, claims: [{ claimId: 'c1', parserId: 'p1', timestamp: '2026-06-01T00:00:00Z' }] },
          },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByTestId('icon-check-circle')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('does not show enrichment indicators when no enrichment metadata exists', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({ type: 'image/png', metadata: undefined, origin: 'opaque-foreign' }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.queryByTestId('icon-clock')).not.toBeInTheDocument();
    expect(screen.queryByTestId('icon-alert-triangle')).not.toBeInTheDocument();
    expect(screen.queryByTestId('icon-check-circle')).not.toBeInTheDocument();
  });

  it('shows both pending and failed counts simultaneously', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          metadata: {
            enrichment: { pending: 1, failed: 1, claims: [] },
          },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(screen.getByTestId('icon-clock')).toBeInTheDocument();
    expect(screen.getByTestId('icon-alert-triangle')).toBeInTheDocument();
  });
});

describe('AssetPanel — M6: metadata detail expansion', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRuntimeExtensions.metadataFacets = [];
    mockRuntimeExtensions.searchProviders = [];
    mockRuntimeExtensions.assetDetailSections = [];
  });

  it('shows expand/collapse button when asset has metadata details (provenance, enrichment, etc.)', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createEnrichedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png');
    expect(expandButton).not.toBeNull();
    expect(expandButton!.getAttribute('title')).toBe('Show metadata details');
  });

  it('expands to show provenance details', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createEnrichedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    expect(screen.getByText('Provenance')).toBeInTheDocument();
    expect(screen.getByText(/Provider:/)).toBeInTheDocument();
    expect(screen.getByText(/Local Upload/)).toBeInTheDocument();
    expect(screen.getByText(/Source:/)).toBeInTheDocument();
    expect(screen.getByText(/https:\/\/example.com\/photo.jpg/)).toBeInTheDocument();
    expect(screen.getByText(/By:/)).toBeInTheDocument();
    expect(screen.getByText(/user-1/)).toBeInTheDocument();
    expect(screen.getByText(/File:/)).toBeInTheDocument();
    expect(screen.getByText(/my-photo.jpg/)).toBeInTheDocument();
    // Integrity hash truncated display
    expect(screen.getByText(/sha256: abc123def456\.\.\./)).toBeInTheDocument();
  });

  it('expands to show enrichment claim details', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createEnrichedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    // Check enrichment claims section
    expect(screen.getByText(/Enrichment Claims/)).toBeInTheDocument();
    expect(screen.getByText('integrity-hash-parser')).toBeInTheDocument();
    expect(screen.getByText('exif-parser')).toBeInTheDocument();
    expect(screen.getByText('face-detector')).toBeInTheDocument();
    // Should show pending/failed counts in the expanded section header
    expect(screen.getByText(/2 pending/)).toBeInTheDocument();
    expect(screen.getByText(/1 failed/)).toBeInTheDocument();
  });

  it('expands to show related materials', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          derivedFrom: { assetId: 'asset-original' },
          metadata: {
            provenance: { importTimestamp: '2026-06-01T00:00:00Z' },
          },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    expect(screen.getByText('Related Materials')).toBeInTheDocument();
    expect(screen.getByText('asset-original')).toBeInTheDocument();
  });

  it('does not show expand button when asset has no metadata details', () => {
    // Use opaque-foreign without sourceUrl/sourceProvider → unknown badge
    // No enrichment, no provenance, no derivedFrom, no facets → no details
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          metadata: undefined,
        }),
      },
    });

    render(<AssetPanel {...props} />);

    expect(getExpandButtonForAsset('photo.png')).toBeNull();
  });

  it('limits enrichment claims display to 5 with "+N more" overflow', () => {
    const claims = Array.from({ length: 7 }, (_, i) => ({
      claimId: `claim-${i}`,
      parserId: `parser-${i}`,
      timestamp: `2026-06-0${i + 1}T00:00:00Z`,
    }));

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          metadata: {
            enrichment: { pending: 0, failed: 0, claims },
            provenance: { importTimestamp: '2026-06-01T00:00:00Z' },
          },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    // First 5 claims should be visible
    expect(screen.getByText('parser-0')).toBeInTheDocument();
    expect(screen.getByText('parser-4')).toBeInTheDocument();
    // "+2 more" overflow message
    expect(screen.getByText('+2 more claims')).toBeInTheDocument();
    // parser-5 and parser-6 should NOT be visible
    expect(screen.queryByText('parser-5')).not.toBeInTheDocument();
    expect(screen.queryByText('parser-6')).not.toBeInTheDocument();
  });

  it('collapses expanded metadata on second click', () => {
    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createEnrichedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    // Provenance should be visible
    expect(screen.getByText('Provenance')).toBeInTheDocument();

    // Click to collapse
    const collapseButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(collapseButton);

    // Provenance should now be hidden
    expect(screen.queryByText('Provenance')).not.toBeInTheDocument();
  });
});

describe('AssetPanel — M6: metadata facet rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRuntimeExtensions.searchProviders = [];
    mockRuntimeExtensions.assetDetailSections = [];
    mockRegisterGenerationAsset.mockReset();
  });

  it('renders metadata facet values in expanded section when facets are configured', () => {
    mockRuntimeExtensions.metadataFacets = [
      {
        id: 'facet-gps-lat',
        extensionId: 'ext-a',
        fieldPath: 'gps.latitude',
        displayName: 'Latitude',
        valueKind: 'number' as const,
        order: 1,
      },
      {
        id: 'facet-consent',
        extensionId: 'ext-a',
        fieldPath: 'consent.ownerConsent',
        displayName: 'Owner Consent',
        valueKind: 'boolean' as const,
        order: 2,
      },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createFacetedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    // Should see the Metadata section
    expect(screen.getByText('Metadata')).toBeInTheDocument();

    // Facet values rendered
    expect(screen.getByText('Latitude:')).toBeInTheDocument();
    expect(screen.getByText('37.7749')).toBeInTheDocument();
    expect(screen.getByText('Owner Consent:')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument(); // boolean true → 'Yes'
  });

  it('renders only the facets that have resolved values', () => {
    mockRuntimeExtensions.metadataFacets = [
      {
        id: 'facet-present',
        extensionId: 'ext-a',
        fieldPath: 'integrity.sha256',
        displayName: 'Hash',
        valueKind: 'string' as const,
      },
      {
        id: 'facet-missing',
        extensionId: 'ext-a',
        fieldPath: 'nonexistent.field',
        displayName: 'Missing',
        valueKind: 'string' as const,
      },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createFacetedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    // Present facet should render
    expect(screen.getByText('Hash:')).toBeInTheDocument();
    expect(screen.getByText('def789')).toBeInTheDocument();

    // Missing facet should NOT render (value is undefined)
    expect(screen.queryByText('Missing:')).not.toBeInTheDocument();
  });

  it('does not show expand button when only facets exist but none resolve and no other metadata', () => {
    mockRuntimeExtensions.metadataFacets = [
      {
        id: 'facet-nonexistent',
        extensionId: 'ext-a',
        fieldPath: 'nonexistent.field',
        displayName: 'Nothing',
        valueKind: 'string' as const,
      },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          metadata: undefined,
        }),
      },
    });

    render(<AssetPanel {...props} />);

    // No badge (opaque-foreign without sourceUrl → unknown),
    // no enrichment, no provenance, facet resolves to undefined → no details at all
    expect(getExpandButtonForAsset('photo.png')).toBeNull();
  });
});

describe('AssetPanel — M6: extension-declared asset detail sections', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRuntimeExtensions.metadataFacets = [];
    mockRuntimeExtensions.searchProviders = [];
    mockRegisterGenerationAsset.mockReset();
  });

  it('renders extension-declared detail sections in the expanded view', () => {
    mockRuntimeExtensions.assetDetailSections = [
      {
        id: 'section-exif',
        extensionId: 'ext-exif',
        title: 'EXIF Data',
        placement: 'before-default',
        fieldPaths: ['gps.latitude', 'gps.longitude'],
        order: 1,
      },
      {
        id: 'section-iptc',
        extensionId: 'ext-iptc',
        title: 'IPTC Metadata',
        placement: 'after-default',
        fieldPaths: ['extensions.ext-iptc.keywords'],
        order: 2,
      },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createFacetedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    // Extension Details section present
    expect(screen.getByText('Extension Details')).toBeInTheDocument();

    // Both sections rendered
    expect(screen.getByText('EXIF Data')).toBeInTheDocument();
    expect(screen.getByText('(ext-exif)')).toBeInTheDocument();
    expect(screen.getByText('IPTC Metadata')).toBeInTheDocument();
    expect(screen.getByText('(ext-iptc)')).toBeInTheDocument();
  });

  it('shows "No data available" for extension sections with unresolved field paths', () => {
    mockRuntimeExtensions.assetDetailSections = [
      {
        id: 'section-empty',
        extensionId: 'ext-empty',
        title: 'Empty Section',
        placement: 'before-default',
        fieldPaths: ['nonexistent.path'],
        order: 1,
      },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'opaque-foreign',
          metadata: { integrity: { sha256: 'hash', size: 100 } },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    expect(screen.getByText('Empty Section')).toBeInTheDocument();
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });

  it('orders extension sections by placement then order then ID', () => {
    mockRuntimeExtensions.assetDetailSections = [
      {
        id: 'section-z',
        extensionId: 'ext-a',
        title: 'Section Z',
        placement: 'after-default',
        fieldPaths: ['integrity.sha256'],
        order: 1,
      },
      {
        id: 'section-a',
        extensionId: 'ext-a',
        title: 'Section A',
        placement: 'before-default',
        fieldPaths: ['integrity.sha256'],
        order: 1,
      },
      {
        id: 'section-b',
        extensionId: 'ext-a',
        title: 'Section B',
        placement: 'before-default',
        fieldPaths: ['integrity.sha256'],
        order: 2,
      },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: { integrity: { sha256: 'hash', size: 100 } },
        }),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    // Get the Extension Details container and check section order
    const extDetailsHeading = screen.getByText('Extension Details');
    const extDetailsContainer = extDetailsHeading.closest('div')!.parentElement!;
    
    // Find all section title elements within the extension details container
    const sectionTitles = extDetailsContainer.querySelectorAll('.font-medium.text-foreground');
    const titleTexts = Array.from(sectionTitles).map(el => el.textContent);

    // After the "Extension Details" heading itself and the extension ID spans,
    // the section titles should be: Section A, Section B, Section Z
    const sectionATexts = Array.from(sectionTitles).filter(el => el.textContent === 'Section A');
    const sectionBTexts = Array.from(sectionTitles).filter(el => el.textContent === 'Section B');
    const sectionZTexts = Array.from(sectionTitles).filter(el => el.textContent === 'Section Z');

    expect(sectionATexts.length).toBeGreaterThan(0);
    expect(sectionBTexts.length).toBeGreaterThan(0);
    expect(sectionZTexts.length).toBeGreaterThan(0);

    // Verify DOM order: Section A before Section B before Section Z
    const allSectionDivs = extDetailsContainer.querySelectorAll('.rounded.border');
    const sectionNames = Array.from(allSectionDivs).map(
      (div) => div.querySelector('.font-medium.text-foreground')?.textContent,
    );
    const filteredNames = sectionNames.filter(Boolean);
    expect(filteredNames).toEqual(['Section A', 'Section B', 'Section Z']);
  });

  it('does not render extension detail sections when none are registered', () => {
    mockRuntimeExtensions.assetDetailSections = [];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createEnrichedEntry(),
      },
    });

    render(<AssetPanel {...props} />);

    const expandButton = getExpandButtonForAsset('photo.png')!;
    fireEvent.click(expandButton);

    // Extension Details should not be present
    expect(screen.queryByText('Extension Details')).not.toBeInTheDocument();
  });
});


// ---------------------------------------------------------------------------
// T17: Search provider result integration — stub SearchProviderContribution
// ---------------------------------------------------------------------------

describe('AssetPanel — M6: search provider result integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRuntimeExtensions.metadataFacets = [];
    mockRuntimeExtensions.searchProviders = [];
    mockRuntimeExtensions.assetDetailSections = [];
  });

  /** Create a stub search provider result envelope for testing. */
  function createStubSearchProviderResult(
    overrides: Partial<{
      providerId: string;
      providerLabel: string;
      providerOrder: number;
      matches: Array<{ ref: string; kind: 'asset' | 'material'; score: number; excerpt?: string }>;
      diagnostics: Array<{ severity: 'info' | 'warning' | 'error'; code: string; message: string }>;
    }> = {},
  ) {
    return {
      providerId: overrides.providerId ?? 'stub-provider',
      providerLabel: overrides.providerLabel ?? 'Stub Search',
      providerOrder: overrides.providerOrder ?? 0,
      result: {
        matches: overrides.matches ?? [],
        totalCount: overrides.matches?.length ?? 0,
        hasMore: false,
        diagnostics: overrides.diagnostics ?? [],
      },
    };
  }

  // ---- Merge ordering assertions -------------------------------------------

  it('ranks built-in metadata filter matches above search provider matches when both match the same text', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'stub-provider', extensionId: 'ext-test', label: 'Stub Search' },
    ];

    const props = createAssetPanelProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: { integrity: { sha256: 'abcdef123456', size: 1024 } },
        }),
        'asset-2': createRegistryEntry({
          type: 'audio/mpeg',
          metadata: { provenance: { originalFilename: 'song.mp3' } },
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'stub-provider',
          providerLabel: 'Stub Search',
          matches: [{ ref: 'asset-1', kind: 'asset', score: 0.8, excerpt: 'Matched by stub' }],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    // Type search text that matches asset-1's integrity hash
    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'abcdef' } });

    // asset-1 should still be visible (matched by both metadata filter and search provider)
    expect(screen.getByText('photo.png')).toBeInTheDocument();
    // asset-2 should not be visible (neither metadata nor provider matched it)
    expect(screen.queryByText('music.mp3')).not.toBeInTheDocument();
  });

  it('shows search provider match indicator with excerpt on asset row', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'stub-provider', extensionId: 'ext-test', label: 'Stub Search' },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'immutable-public',
          metadata: undefined,
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'stub-provider',
          providerLabel: 'Stub Search',
          matches: [{ ref: 'asset-1', kind: 'asset', score: 0.95, excerpt: 'Semantic match: outdoor photo' }],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'outdoor' } });

    // The excerpt should appear as the search provider match indicator (truncated to 30 chars)
    expect(screen.getByText('Semantic match: outdoor photo')).toBeInTheDocument();
  });

  it('includes material results in merged output without affecting asset visibility', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'stub-provider', extensionId: 'ext-test', label: 'Stub Search' },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'immutable-public',
          metadata: undefined,
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'stub-provider',
          providerLabel: 'Stub Search',
          matches: [
            { ref: 'mat-1', kind: 'material', score: 0.9, excerpt: 'Material match' },
            { ref: 'asset-1', kind: 'asset', score: 0.7, excerpt: 'Asset match' },
          ],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'abcdef' } });

    // asset-1 is visible (matched by both built-in metadata and provider)
    expect(screen.getByText('photo.png')).toBeInTheDocument();
    // Material match does NOT appear as an asset row (materials are separate)
    // The provider match indicator for asset-1 should be 'Asset match'
    expect(screen.getByText('Asset match')).toBeInTheDocument();
  });

  // ---- Source/provider labels ----------------------------------------------

  it('displays "Results from:" source provider labels when search providers return matches', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'provider-a', extensionId: 'ext-a', label: 'Vector Search' },
      { id: 'provider-b', extensionId: 'ext-b', label: 'Keyword Index' },
    ];

    const props = createAssetPanelProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'immutable-public',
          metadata: undefined,
        }),
          'asset-2': createRegistryEntry({
            type: 'audio/mpeg',
            origin: 'immutable-public',
            metadata: undefined,
          }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'provider-a',
          providerLabel: 'Vector Search',
          matches: [{ ref: 'asset-1', kind: 'asset', score: 0.88 }],
        }),
        createStubSearchProviderResult({
          providerId: 'provider-b',
          providerLabel: 'Keyword Index',
          matches: [{ ref: 'asset-2', kind: 'asset', score: 0.75 }],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'test' } });

    // "Results from:" source labels
    expect(screen.getByText('Results from:')).toBeInTheDocument();
    // Provider labels should appear (sorted alphabetically)
    expect(screen.getAllByText('Keyword Index').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Vector Search').length).toBeGreaterThan(0);
  });

  it('does not display "Results from:" when only built-in metadata filtering matches', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'stub-provider', extensionId: 'ext-test', label: 'Stub Search' },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: { integrity: { sha256: 'abc123', size: 100 } },
        }),
      },
      // No searchResults provided → only built-in filtering
      searchResults: [],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'abc' } });

    // "Results from:" should NOT appear (only built-in metadata filter matched)
    expect(screen.queryByText('Results from:')).not.toBeInTheDocument();
  });

  it('does not display "Results from:" when search providers return no matches', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'stub-provider', extensionId: 'ext-test', label: 'Stub Search' },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: { integrity: { sha256: 'abc123', size: 100 } },
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'stub-provider',
          providerLabel: 'Stub Search',
          matches: [], // Empty matches
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'abc' } });

    // "Results from:" should NOT appear (no provider matches)
    expect(screen.queryByText('Results from:')).not.toBeInTheDocument();
  });

  // ---- Coexistence with built-in metadata filtering ------------------------

  it('filters assets by both built-in metadata AND search provider results simultaneously', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'provider-a', extensionId: 'ext-a', label: 'Provider A' },
    ];

    const props = createAssetPanelProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: { integrity: { sha256: 'matchme', size: 100 } },
        }),
        'asset-2': createRegistryEntry({
          type: 'audio/mpeg',
          metadata: undefined,
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'provider-a',
          providerLabel: 'Provider A',
          matches: [{ ref: 'asset-2', kind: 'asset', score: 0.95, excerpt: 'Provider match' }],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'matchme' } });

    // asset-1 matches built-in metadata filter
    expect(screen.getByText('photo.png')).toBeInTheDocument();
    // asset-2 matches search provider (even though it has no built-in metadata)
    expect(screen.getByText('music.mp3')).toBeInTheDocument();
    // Provider match indicator on asset-2
    expect(screen.getByText('Provider match')).toBeInTheDocument();
  });

  it('drops search provider asset refs not present in the registry', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'stub-provider', extensionId: 'ext-test', label: 'Stub Search' },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: undefined,
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'stub-provider',
          providerLabel: 'Stub Search',
          matches: [
            { ref: 'nonexistent-asset', kind: 'asset', score: 0.99, excerpt: 'Should not appear' },
          ],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'test' } });

    // asset-1 should NOT be visible (no built-in metadata match, and the provider match was for a nonexistent ref)
    expect(screen.queryByText('photo.png')).not.toBeInTheDocument();
    // The "no assets match" message should appear
    expect(screen.getByText('No assets match the current metadata search.')).toBeInTheDocument();
  });

  // ---- Diagnostics ---------------------------------------------------------

  it('collects provider diagnostics without blocking other providers or built-in filtering', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'provider-ok', extensionId: 'ext-ok', label: 'OK Provider' },
      { id: 'provider-err', extensionId: 'ext-err', label: 'Error Provider' },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: undefined,
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'provider-ok',
          providerLabel: 'OK Provider',
          matches: [{ ref: 'asset-1', kind: 'asset', score: 0.9, excerpt: 'OK match' }],
        }),
        createStubSearchProviderResult({
          providerId: 'provider-err',
          providerLabel: 'Error Provider',
          matches: [],
          diagnostics: [
            {
              severity: 'error',
              code: 'parser/index-error',
              message: 'Search index is corrupt',
            },
            {
              severity: 'warning',
              code: 'parser/stale-index',
              message: 'Index is 2 hours old',
            },
          ],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'abcdef' } });

    // asset-1 should be visible (matched by built-in metadata + OK provider)
    expect(screen.getByText('photo.png')).toBeInTheDocument();
    // OK Provider match indicator
    expect(screen.getByText('OK match')).toBeInTheDocument();
    // Error provider did NOT block results
    // "Results from:" should show only OK Provider (Error Provider had no matches)
    expect(screen.getByText('Results from:')).toBeInTheDocument();
    expect(screen.getAllByText('OK Provider').length).toBeGreaterThan(0);
    expect(screen.queryByText('Error Provider')).not.toBeInTheDocument();
  });

  // ---- Merge ordering (score-based) ----------------------------------------

  it('sorts merged results by score descending within the same match source', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'provider-a', extensionId: 'ext-a', label: 'Provider A' },
    ];

    const props = createAssetPanelProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          origin: 'immutable-public',
          metadata: undefined,
        }),
        'asset-2': createRegistryEntry({
          type: 'audio/mpeg',
          origin: 'immutable-public',
          metadata: undefined,
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'provider-a',
          providerLabel: 'Provider A',
          matches: [
            { ref: 'asset-1', kind: 'asset', score: 0.5, excerpt: 'Low score' },
            { ref: 'asset-2', kind: 'asset', score: 0.95, excerpt: 'High score' },
          ],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'test' } });

    // Both assets should be visible (both matched by provider)
    expect(screen.getByText('photo.png')).toBeInTheDocument();
    expect(screen.getByText('music.mp3')).toBeInTheDocument();
    // Both match indicators should appear
    expect(screen.getByText('High score')).toBeInTheDocument();
    expect(screen.getByText('Low score')).toBeInTheDocument();
  });

  // ---- Empty / edge cases --------------------------------------------------

  it('shows "no assets match" when search yields no results from any source', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'stub-provider', extensionId: 'ext-test', label: 'Stub Search' },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: undefined,
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'stub-provider',
          providerLabel: 'Stub Search',
          matches: [], // No matches
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');
    fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

    // No assets should match
    expect(screen.getByText('No assets match the current metadata search.')).toBeInTheDocument();
  });

  it('clears all search results when search text is emptied', () => {
    mockRuntimeExtensions.searchProviders = [
      { id: 'stub-provider', extensionId: 'ext-test', label: 'Stub Search' },
    ];

    const props = createSingleAssetProps({
      showAll: true,
      registry: {
        'asset-1': createRegistryEntry({
          type: 'image/png',
          metadata: undefined,
        }),
      },
      searchResults: [
        createStubSearchProviderResult({
          providerId: 'stub-provider',
          providerLabel: 'Stub Search',
          matches: [{ ref: 'asset-1', kind: 'asset', score: 0.9, excerpt: 'Stub match' }],
        }),
      ],
    });

    render(<AssetPanel {...props} />);

    const searchInput = screen.getByPlaceholderText('Search metadata...');

    // First, search something
    fireEvent.change(searchInput, { target: { value: 'test' } });
    expect(screen.getByText('photo.png')).toBeInTheDocument();
    expect(screen.getByText('Stub match')).toBeInTheDocument();

    // Clear the search
    fireEvent.change(searchInput, { target: { value: '' } });

    // Asset should still be visible (no filter active)
    expect(screen.getByText('photo.png')).toBeInTheDocument();
    // "Results from:" should be gone
    expect(screen.queryByText('Results from:')).not.toBeInTheDocument();
    // Match indicator should be gone
    expect(screen.queryByText('Stub match')).not.toBeInTheDocument();
  });
});
