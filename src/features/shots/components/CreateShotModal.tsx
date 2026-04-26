import React, { useEffect, useState } from 'react';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/primitives/label';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { FileInput } from '@/shared/components/FileInput';
import { parseRatio, findClosestAspectRatio } from '@/shared/lib/media/aspectRatios';
import { cropImageToProjectAspectRatio } from '@/shared/lib/media/imageCropper';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';
import { AspectRatioSelector } from '@/shared/components/GenerationControls/AspectRatioSelector';
import { useProjectCrudContext } from '@/shared/contexts/ProjectContext';
import { ModalContainer, ModalFooterButtons } from '@/shared/components/ModalContainer';

interface CreateShotModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (shotName: string, files: File[], aspectRatio: string | null) => Promise<void>;
  isLoading?: boolean;
  defaultShotName?: string;
  projectAspectRatio?: string;
  initialAspectRatio?: string | null;
  projectId?: string;
  cropToProjectSize?: boolean;
}

const CreateShotModal: React.FC<CreateShotModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  defaultShotName,
  projectAspectRatio,
  initialAspectRatio,
  projectId,
  cropToProjectSize = true,
}) => {
  const [shotName, setShotName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [aspectRatio, setAspectRatio] = useState<string>('');
  const [updateProjectAspectRatio, setUpdateProjectAspectRatio] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [imageChangedRatio, setImageChangedRatio] = useState(false);
  const { updateProject } = useProjectCrudContext();

  useEffect(() => {
    if (isOpen) {
      setAspectRatio(initialAspectRatio || projectAspectRatio || '3:2');
      setUpdateProjectAspectRatio(false);
      setImageChangedRatio(false);
    }
  }, [isOpen, initialAspectRatio, projectAspectRatio]);

  useEffect(() => {
    if (aspectRatio === projectAspectRatio) {
      setUpdateProjectAspectRatio(false);
    }
  }, [aspectRatio, projectAspectRatio]);

  const effectiveProjectRatio = initialAspectRatio || projectAspectRatio || '3:2';

  const handleFilesChange = (newFiles: File[]) => {
    setFiles(newFiles);

    if (newFiles.length === 0) {
      // If all files removed, revert to project ratio
      if (imageChangedRatio) {
        setAspectRatio(effectiveProjectRatio);
        setImageChangedRatio(false);
      }
      return;
    }

    // Read dimensions from the first image
    const file = newFiles[0];
    const img = new Image();
    img.onload = () => {
      const imageRatio = img.width / img.height;
      const projectRatioValue = parseRatio(effectiveProjectRatio);
      const tolerance = 0.05;

      // Only change if the image doesn't match the current project ratio
      if (!isNaN(projectRatioValue) && Math.abs(imageRatio - projectRatioValue) > tolerance) {
        const closest = findClosestAspectRatio(imageRatio);
        setAspectRatio(closest);
        setImageChangedRatio(true);
      }
      URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(file);
  };

  const handleRevertToProjectDimensions = () => {
    setAspectRatio(effectiveProjectRatio);
    setImageChangedRatio(false);
  };

  const handleSubmit = async () => {
    let finalShotName = shotName.trim();
    if (!finalShotName) {
      finalShotName = defaultShotName || 'Untitled Shot';
    }

    setIsProcessing(true);

    try {
      let processedFiles = files;

      if (cropToProjectSize && files.length > 0 && aspectRatio) {
        const targetAspectRatio = parseRatio(aspectRatio);

        if (!isNaN(targetAspectRatio)) {
          const cropPromises = files.map(async (file) => {
            try {
              const result = await cropImageToProjectAspectRatio(file, targetAspectRatio);
              if (result) {
                return result.croppedFile;
              }
              return file;
            } catch (error) {
              normalizeAndPresentError(error, { context: 'CreateShotModal', toastTitle: `Failed to crop ${file.name}` });
              return file;
            }
          });

          processedFiles = await Promise.all(cropPromises);
        }
      }

      if (updateProjectAspectRatio && projectId && aspectRatio && aspectRatio !== projectAspectRatio) {
        updateProject(projectId, { aspectRatio });
      }

      onSubmit(finalShotName, processedFiles, aspectRatio || null);
      setShotName('');
      setFiles([]);
      setAspectRatio(projectAspectRatio || '3:2');
      setUpdateProjectAspectRatio(false);
      setImageChangedRatio(false);
      setIsProcessing(false);
      onClose();
    } catch (error) {
      normalizeAndPresentError(error, { context: 'CreateShotModal', toastTitle: 'Failed to process images' });
      setIsProcessing(false);
    }
  };

  const handleClose = () => {
    setShotName('');
    setFiles([]);
    setAspectRatio(projectAspectRatio || '3:2');
    setUpdateProjectAspectRatio(false);
    setImageChangedRatio(false);
    onClose();
  };

  return (
    <ModalContainer
      open={isOpen}
      onOpenChange={handleClose}
      size="medium"
      title="New Shot"
      footer={
        <ModalFooterButtons
          onCancel={handleClose}
          onConfirm={handleSubmit}
          confirmText={isProcessing ? 'Processing...' : 'New Shot'}
          isLoading={isProcessing}
        />
      }
    >
      <div className="grid gap-3 py-3">
        <div className="space-y-2">
          <Label htmlFor="shot-name">
            Name:
          </Label>
          <Input
            id="shot-name"
            value={shotName}
            onChange={(e) => setShotName(e.target.value)}
            className="w-full"
            placeholder={defaultShotName || 'e.g., My Awesome Shot'}
            maxLength={30}
          />
        </div>
        <FileInput
          onFileChange={handleFilesChange}
          multiple
          acceptTypes={['image']}
          label="Starting Images: (Optional)"
        />

        <div className="space-y-2 pt-2 border-t">
          <Label htmlFor="shot-aspect-ratio" className="text-sm font-medium">What size would you like to use?</Label>
          <AspectRatioSelector
            value={aspectRatio}
            onValueChange={setAspectRatio}
            disabled={isProcessing}
            id="shot-aspect-ratio"
            showVisualizer={true}
          />

          {imageChangedRatio && aspectRatio !== effectiveProjectRatio && (
            <button
              type="button"
              onClick={handleRevertToProjectDimensions}
              className="text-sm text-muted-foreground hover:text-foreground underline cursor-pointer transition-colors"
            >
              Revert to project dimensions ({effectiveProjectRatio})
            </button>
          )}

          {aspectRatio && projectAspectRatio && aspectRatio !== projectAspectRatio && (
            <div className="flex items-center gap-x-2 pt-2">
              <Checkbox
                id="update-project-aspect-ratio"
                checked={updateProjectAspectRatio}
                onCheckedChange={(checked) => setUpdateProjectAspectRatio(checked === true)}
                disabled={isProcessing}
              />
              <Label
                htmlFor="update-project-aspect-ratio"
                className="text-sm font-normal cursor-pointer"
              >
                Update project aspect ratio to {aspectRatio}
              </Label>
            </div>
          )}
        </div>
      </div>
    </ModalContainer>
  );
};

export { CreateShotModal };
export default CreateShotModal;
