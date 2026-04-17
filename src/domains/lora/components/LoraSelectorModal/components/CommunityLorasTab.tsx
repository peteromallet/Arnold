import React, { useEffect, useMemo, useState } from 'react';
import { Input } from "@/shared/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/shared/components/ui/alert-dialog";
import { Search } from 'lucide-react';
import { useIsMobile } from '@/shared/hooks/mobile';
import { getClosestOverlayContainer } from '@/shared/components/ui/overlay';

import { CommunityLorasTabProps, LoraModel, ModelFilterCategory, SortOption } from '../types';
import { getSubFilterOptions, matchesFilters } from '../utils/filter-utils';
import { LoraCard } from './LoraCard';
import { DescriptionModal } from './DescriptionModal';

const PAGE_SIZE = 20;

function useSelectPortalContainer<T extends HTMLElement>() {
  const sectionRef = React.useRef<T | null>(null);
  const [container, setContainer] = React.useState<HTMLElement | null>(null);

  React.useLayoutEffect(() => {
    const nextContainer = getClosestOverlayContainer(sectionRef.current);
    setContainer(nextContainer ?? null);
  }, []);

  return { sectionRef, container };
}

export const CommunityLorasTab: React.FC<CommunityLorasTabProps> = ({
  loras,
  onAddLora,
  onRemoveLora,
  onUpdateLoraStrength,
  selectedLoras,
  myLorasResource,
  createResource,
  deleteResource,
  onEdit,
  showMyLorasOnly,
  showAddedLorasOnly,
  onProcessedLorasLengthChange,
  onPageChange,
  selectedModelFilter,
  setSelectedModelFilter,
  selectedSubFilter,
  setSelectedSubFilter,
}) => {
  const { sectionRef, container } = useSelectPortalContainer<HTMLDivElement>();
  const isMobile = useIsMobile();
  const [searchTerm, setSearchTerm] = useState('');
  const [sortOption, setSortOption] = useState<SortOption>('default');
  const [page, setPage] = useState(0);
  const selectedLoraIds = useMemo(
    () => new Set(selectedLoras.map((lora) => lora['Model ID'])),
    [selectedLoras],
  );
  const selectedStrengthById = useMemo(
    () => new Map(selectedLoras.map((lora) => [lora['Model ID'], lora.strength])),
    [selectedLoras],
  );
  const savedResourcesByModelId = useMemo(() => {
    const entries = (myLorasResource.data ?? []).flatMap((resource) => {
      const metadata = resource.metadata as Partial<LoraModel>;
      const modelId = typeof metadata?.['Model ID'] === 'string'
        ? metadata['Model ID']
        : typeof metadata?.filename === 'string'
          ? metadata.filename
          : undefined;

      return modelId ? [[modelId, resource] as const] : [];
    });

    return new Map(entries);
  }, [myLorasResource.data]);
  const processedLoras = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();

    const filtered = loras.filter((lora) => {
      const modelId = lora['Model ID'];
      const matchingResource = savedResourcesByModelId.get(modelId);
      const isMine = Boolean(
        lora.created_by?.is_you
        || (matchingResource?.metadata as Partial<LoraModel> | undefined)?.created_by?.is_you
        || lora.Author === 'You'
        || lora.Author === 'You (Local)'
      );

      if (showMyLorasOnly && !isMine) {
        return false;
      }

      if (showAddedLorasOnly && !selectedLoraIds.has(modelId)) {
        return false;
      }

      if (!matchesFilters(lora.lora_type, selectedModelFilter, selectedSubFilter)) {
        return false;
      }

      if (!normalizedSearch) {
        return true;
      }

      const haystack = [
        modelId,
        lora.Name,
        lora.Author,
        lora.Description,
        lora.lora_type,
        lora.base_model,
        ...(lora.Tags ?? []),
      ]
        .filter((value): value is string => typeof value === 'string' && value.length > 0)
        .join(' ')
        .toLowerCase();

      return haystack.includes(normalizedSearch);
    });

    const sorted = [...filtered];
    switch (sortOption) {
      case 'downloads':
        sorted.sort((a, b) => (b.Downloads ?? 0) - (a.Downloads ?? 0));
        break;
      case 'likes':
        sorted.sort((a, b) => (b.Likes ?? 0) - (a.Likes ?? 0));
        break;
      case 'lastModified':
        sorted.sort((a, b) => {
          const aTime = Date.parse(a['Last Modified'] ?? '') || 0;
          const bTime = Date.parse(b['Last Modified'] ?? '') || 0;
          return bTime - aTime;
        });
        break;
      case 'name':
        sorted.sort((a, b) => a.Name.localeCompare(b.Name));
        break;
      default:
        break;
    }

    return sorted;
  }, [
    loras,
    savedResourcesByModelId,
    searchTerm,
    selectedLoraIds,
    selectedModelFilter,
    selectedSubFilter,
    showAddedLorasOnly,
    showMyLorasOnly,
    sortOption,
  ]);
  const totalPages = Math.max(1, Math.ceil(processedLoras.length / PAGE_SIZE));
  const paginatedLoras = useMemo(
    () => processedLoras.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [page, processedLoras],
  );

  // Description modal state
  const [descriptionModalOpen, setDescriptionModalOpen] = useState(false);
  const [selectedDescription, setSelectedDescription] = useState<{ title: string; description: string }>({ title: '', description: '' });

  // Delete confirmation state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [loraToDelete, setLoraToDelete] = useState<{ id: string; name: string; isAdded: boolean } | null>(null);

  // Handle delete confirmation
  const handleDeleteConfirm = () => {
    if (loraToDelete) {
      deleteResource.mutate({ id: loraToDelete.id, type: 'lora' });
      if (loraToDelete.isAdded) {
        onRemoveLora(loraToDelete.id);
      }
      setDeleteDialogOpen(false);
      setLoraToDelete(null);
    }
  };

  // Handle description modal
  const handleShowFullDescription = (title: string, description: string) => {
    setSelectedDescription({ title, description });
    setDescriptionModalOpen(true);
  };

  // Update parent with processed LoRAs length
  useEffect(() => {
    onProcessedLorasLengthChange(processedLoras.length);
  }, [processedLoras.length, onProcessedLorasLengthChange]);

  useEffect(() => {
    setPage(0);
  }, [searchTerm, selectedModelFilter, selectedSubFilter, showAddedLorasOnly, showMyLorasOnly, sortOption]);

  useEffect(() => {
    if (page >= totalPages) {
      setPage(totalPages - 1);
    }
  }, [page, totalPages]);

  // Notify parent about pagination state
  useEffect(() => {
    if (onPageChange) {
      onPageChange(page, totalPages, setPage);
    }
  }, [page, totalPages, onPageChange, setPage]);

  const tabContainerClass = 'relative flex flex-col h-full min-h-0 px-0 sm:px-4';
  const scrollAreaClass = 'flex-1 min-h-0 overflow-y-auto relative';
  const sortControl = (
    <Select value={sortOption} onValueChange={(value) => value && setSortOption(value as SortOption)}>
      <SelectTrigger variant="retro" className="w-[140px]">
        <SelectValue placeholder="Sort by" />
      </SelectTrigger>
      <SelectContent container={container} variant="retro">
        <SelectItem variant="retro" value="default">Default</SelectItem>
        <SelectItem variant="retro" value="downloads">Downloads</SelectItem>
        <SelectItem variant="retro" value="likes">Likes</SelectItem>
        <SelectItem variant="retro" value="lastModified">Modified</SelectItem>
        <SelectItem variant="retro" value="name">Name</SelectItem>
      </SelectContent>
    </Select>
  );

  return (
    <div ref={sectionRef} className={tabContainerClass}>
      <div className="flex gap-2 mb-3">
        <Input
          type="text"
          placeholder="Search all LoRA fields..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-grow"
        />
        {sortControl}
        {/* Model Filter Dropdown - far right */}
        <Select value={selectedModelFilter} onValueChange={(v) => v && setSelectedModelFilter(v as ModelFilterCategory)}>
          <SelectTrigger variant="retro" className="w-[120px] ml-auto">
            <SelectValue placeholder="Model" />
          </SelectTrigger>
          <SelectContent container={container} variant="retro">
            <SelectItem variant="retro" value="all">All Models</SelectItem>
            <SelectItem variant="retro" value="qwen">Qwen</SelectItem>
            <SelectItem variant="retro" value="wan">Wan</SelectItem>
            <SelectItem variant="retro" value="ltx">LTX</SelectItem>
            <SelectItem variant="retro" value="z-image">Z-Image</SelectItem>
          </SelectContent>
        </Select>
        {/* Sub-filter - appears when a category is selected */}
        {selectedModelFilter !== 'all' && (
          <Select value={selectedSubFilter} onValueChange={(value) => setSelectedSubFilter(value ?? 'all')}>
            <SelectTrigger variant="retro" className="w-[150px]">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent container={container} variant="retro">
              {getSubFilterOptions(selectedModelFilter).map(opt => (
                <SelectItem key={opt.value} variant="retro" value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Scrollable content area with floating controls */}
      <div className={scrollAreaClass}>
        <div className={`grid grid-cols-1 lg:grid-cols-2 gap-2 ${isMobile ? 'pb-2' : 'pb-4'}`}>
          {paginatedLoras.length > 0 ? (
            paginatedLoras.map((lora) => {
              const modelId = lora['Model ID'];
              const matchingResource = savedResourcesByModelId.get(modelId);
              const isSelectedOnGenerator = selectedLoraIds.has(modelId);
              const strength = selectedStrengthById.get(modelId);
              const loraIsMyLora = Boolean(
                lora.created_by?.is_you
                || (matchingResource?.metadata as Partial<LoraModel> | undefined)?.created_by?.is_you
                || lora.Author === 'You'
                || lora.Author === 'You (Local)'
              );
              const loraIsInSavedLoras = Boolean(matchingResource);
              const isLocalLora = lora.Author === 'You (Local)';
              const resourceId = matchingResource?.id ?? (lora as LoraModel & { _resourceId?: string })._resourceId;

              return (
                <LoraCard
                  key={modelId}
                  lora={lora}
                  isSelectedOnGenerator={isSelectedOnGenerator}
                  strength={strength}
                  isMyLora={loraIsMyLora}
                  isInSavedLoras={loraIsInSavedLoras}
                  isLocalLora={isLocalLora}
                  resourceId={resourceId}
                  onAddLora={onAddLora}
                  onRemoveLora={onRemoveLora}
                  onUpdateLoraStrength={onUpdateLoraStrength}
                  onSave={(lora) => createResource.mutate({ type: 'lora', metadata: lora })}
                  onEdit={onEdit}
                  onDelete={(id, name, isAdded) => {
                    setLoraToDelete({ id, name, isAdded });
                    setDeleteDialogOpen(true);
                  }}
                  onShowFullDescription={handleShowFullDescription}
                  isSaving={createResource.isPending}
                  isDeleting={deleteResource.isPending}
                />
              );
            })
          ) : (
            <div className="col-span-full flex items-center justify-center py-12">
              <div className="flex flex-col items-center justify-center p-8 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/30 text-center max-w-sm">
                <Search className="h-10 w-10 text-muted-foreground/50 mb-3" />
                <p className="text-base font-medium text-foreground mb-1">No LoRA models found</p>
                <p className="text-sm text-muted-foreground">Try adjusting your search or filter criteria</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Description Modal */}
      <DescriptionModal
        open={descriptionModalOpen}
        onOpenChange={setDescriptionModalOpen}
        title={selectedDescription.title}
        description={selectedDescription.description}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete LoRA</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "<span className="preserve-case">{loraToDelete?.name}</span>"? This action cannot be undone.
              {loraToDelete?.isAdded && (
                <span className="block mt-2 text-amber-600 dark:text-amber-400">
                  Note: This LoRA is currently added to your generator and will be removed.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => {
              setDeleteDialogOpen(false);
              setLoraToDelete(null);
            }}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete LoRA
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};
