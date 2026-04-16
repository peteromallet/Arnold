import React from 'react';
import { useProject } from '@/shared/contexts/ProjectContext';
import {
  useListShots,
} from '@/shared/hooks/shots';
import { ShotListDisplay } from '@/tools/travel-between-images/components/VideoGallery/ShotListDisplay';
import { ShotImageManagerContainer as ShotImageManager } from '@/shared/components/ShotImageManager/ShotImageManagerContainer';
import { Button } from '@/shared/components/ui/button';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { useShotSelection } from '@/pages/shots/hooks/useShotSelection';
import { useShotImageMutations } from '@/pages/shots/hooks/useShotImageMutations';

const ShotsPage: React.FC = () => {
  const { selectedProjectId } = useProject();
  const { data: shots, isLoading: isLoadingShots, error: shotsError } = useListShots(selectedProjectId);
  const { currentShotId, setCurrentShotId } = useCurrentShot();

  const {
    selectedShot,
    managedImages,
    setManagedImages,
    simplifiedShotOptions,
    handleSelectShot,
    handleBackToList,
    handleShotChange,
  } = useShotSelection({
    shots,
    currentShotId,
    setCurrentShotId,
  });

  const {
    handleDeleteImage,
    handleReorderImage,
    handleAddToShot,
    handleAddToShotWithoutPosition,
  } = useShotImageMutations({
    selectedProjectId,
    currentShotId,
    selectedShot,
    setManagedImages,
  });

  if (!selectedProjectId) {
    return <div className="container mx-auto p-4">Please select a project to view shots.</div>;
  }

  if (isLoadingShots) {
    return <div className="container mx-auto p-4">Loading shots...</div>;
  }

  if (shotsError) {
    const isCancelled = shotsError?.message?.includes('CancelledError') || shotsError?.message?.includes('cancelled');
    if (isCancelled) {
      return <div className="container mx-auto p-4">Loading shots...</div>;
    }
    return <div className="container mx-auto p-4">Error loading shots: {shotsError.message}</div>;
  }

  return (
    <div className="container mx-auto p-4">
      {!selectedShot ? (
        <>
          <h1 className="text-3xl font-light mb-6">All Shots</h1>
          <ShotListDisplay
            shots={shots}
            onSelectShot={handleSelectShot}
          />
        </>
      ) : (
        <>
          <Button onPointerUp={handleBackToList} className="mb-4">Back to All Shots</Button>
          <h2 className="text-2xl font-normal mb-4">Images in: <span className="preserve-case">{selectedShot.name}</span></h2>
          <ShotImageManager
            images={managedImages}
            onImageDelete={handleDeleteImage}
            onImageReorder={handleReorderImage}
            columns={8}
            generationMode="batch"
            allShots={simplifiedShotOptions}
            selectedShotId={currentShotId || undefined}
            onShotChange={handleShotChange}
            onAddToShot={handleAddToShot}
            onAddToShotWithoutPosition={handleAddToShotWithoutPosition}
          />
        </>
      )}
    </div>
  );
};

export default ShotsPage; 
