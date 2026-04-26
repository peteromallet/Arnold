import React from 'react';
import { Card, CardContent, CardDescription, CardFooter as ItemCardFooter, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Input } from "@/shared/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select";
import { Textarea } from '@/shared/components/ui/textarea';
import { Label } from "@/shared/components/ui/primitives/label";
import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
import { Pencil, Upload, Link } from 'lucide-react';

import { MyLorasTabProps, LoraModel } from '../../types';
import { BASE_MODEL_OPTIONS } from '../../constants';
import { useLoraFormState } from './hooks/useLoraFormState';
import { useLoraSubmission } from './hooks/useLoraSubmission';
import { UrlInputSection } from './components/UrlInputSection';
import { FileUploadSection } from './components/FileUploadSection';
import { SampleGenerationsSection } from './components/SampleGenerationsSection';
import { getClosestOverlayContainer } from '@/shared/components/ui/overlay';

function useSelectPortalContainer<T extends HTMLElement>() {
  const sectionRef = React.useRef<T | null>(null);
  const [container, setContainer] = React.useState<HTMLElement | null>(null);

  React.useLayoutEffect(() => {
    const nextContainer = getClosestOverlayContainer(sectionRef.current);
    setContainer(nextContainer ?? null);
  }, []);

  return { sectionRef, container };
}

export const MyLorasTab: React.FC<MyLorasTabProps> = ({
  myLorasResource,
  createResource,
  updateResource,
  onSwitchToBrowse,
  editingLora,
  onClearEdit,
  defaultIsPublic
}) => {
  const { sectionRef, container } = useSelectPortalContainer<HTMLDivElement>();
  const formState = useLoraFormState({ editingLora, defaultIsPublic });

  // Get existing filenames from saved LoRAs
  const getExistingFilenames = () => {
    const savedFilenames = myLorasResource.data?.map(r => (r.metadata as LoraModel).filename || (r.metadata as LoraModel)["Model ID"]) || [];
    return savedFilenames;
  };

  const { handleAddLoraFromForm, isButtonDisabled } = useLoraSubmission({
    addForm: formState.addForm,
    isEditMode: formState.isEditMode,
    editingLora,
    isMultiStageModel: formState.isMultiStageModel,
    uploadMode: formState.uploadMode,
    loraFiles: formState.loraFiles,
    sampleFiles: formState.sampleFiles,
    deletedExistingSampleUrls: formState.deletedExistingSampleUrls,
    mainGenerationIndex: formState.mainGenerationIndex,
    userName: formState.userName,
    hasHfToken: formState.hasHfToken,
    isSubmitting: formState.isSubmitting,
    isUploading: formState.isUploading,
    setIsSubmitting: formState.setIsSubmitting,
    uploadToHuggingFace: formState.uploadToHuggingFace,
    createResource,
    updateResource,
    onClearEdit,
    onSwitchToBrowse,
    resetForm: formState.resetForm,
    getExistingFilenames,
  });

  return (
    <div ref={sectionRef} className="space-y-4">
      {formState.isEditMode && (
        <div className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
          <div className="flex items-center gap-2">
            <Pencil className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <span className="text-sm font-medium text-blue-900 dark:text-blue-100">
              Editing: {editingLora?.metadata.Name}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onClearEdit();
              formState.resetForm();
            }}
          >
            Cancel Edit
          </Button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{formState.isEditMode ? 'Edit LoRA' : 'Add a New LoRA'}</CardTitle>
          <CardDescription>
            {formState.isEditMode ? 'Update your LoRA details.' : 'Create and save a new LoRA to your collection.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Name and Trigger Word */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="lora-name">Name: *</Label>
              <Input
                id="lora-name"
                placeholder="My Awesome LoRA"
                value={formState.addForm.name}
                onChange={e => formState.handleFormChange('name', e.target.value)}
                maxLength={30}
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="lora-trigger-word">Trigger Word:</Label>
              <Input
                id="lora-trigger-word"
                placeholder="e.g., ohwx, sks, xyz style"
                value={formState.addForm.trigger_word}
                onChange={e => formState.handleFormChange('trigger_word', e.target.value)}
              />
            </div>
          </div>

          {/* Description */}
          <div className="space-y-1">
            <Label htmlFor="lora-description">Description: (optional)</Label>
            <Textarea
              id="lora-description"
              placeholder="Describe what this LoRA does..."
              value={formState.addForm.description}
              onChange={e => formState.handleFormChange('description', e.target.value)}
              rows={2}
              clearable
              onClear={() => formState.handleFormChange('description', '')}
              voiceInput
              voiceContext="This is a description for a LoRA model. Describe what the LoRA does - what style, character, or effect it adds to AI-generated images or videos. Keep it concise and informative."
              onVoiceResult={(result) => {
                formState.handleFormChange('description', result.prompt || result.transcription);
              }}
            />
          </div>

          {/* Base Model */}
          <div className="space-y-1">
            <Label>Base Model:</Label>
            <div className="flex gap-2">
              <Select
                value={formState.addForm.base_model}
                onValueChange={(value) => formState.handleFormChange('base_model', value ?? '')}
              >
                <SelectTrigger variant="retro" className={formState.supportsMultiStage ? "flex-1" : "w-full"}>
                  <SelectValue placeholder="Select Base Model" />
                </SelectTrigger>
                <SelectContent container={container} variant="retro">
                  {BASE_MODEL_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} variant="retro" value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {formState.supportsMultiStage && (
                <Select
                  value={formState.loraMode}
                  onValueChange={(value) => {
                    if (value === 'single' || value === 'multi') {
                      formState.setLoraMode(value);
                    }
                  }}
                >
                  <SelectTrigger variant="retro" className="w-[180px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent container={container} variant="retro">
                    <SelectItem variant="retro" value="single">Single LoRA</SelectItem>
                    <SelectItem variant="retro" value="multi">High + Low Noise</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>
          </div>

          {/* Upload Mode Toggle */}
          {!formState.isEditMode && (
            <div className="space-y-2">
              <Label>How do you want to add this LoRA?</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={formState.uploadMode === 'url' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    formState.setUploadMode('url');
                    formState.setLoraFiles({});
                    formState.resetProgress();
                  }}
                  className="flex items-center gap-2"
                >
                  <Link className="h-4 w-4" />
                  Paste URL
                </Button>
                <Button
                  type="button"
                  variant={formState.uploadMode === 'file' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    formState.setUploadMode('file');
                    formState.handleFormChange('huggingface_url', '');
                    formState.handleFormChange('high_noise_url', '');
                    formState.handleFormChange('low_noise_url', '');
                  }}
                  className="flex items-center gap-2"
                >
                  <Upload className="h-4 w-4" />
                  Upload File
                </Button>
              </div>
            </div>
          )}

          {/* URL or File Input Section */}
          {formState.uploadMode === 'url' || formState.isEditMode ? (
            <UrlInputSection
              addForm={formState.addForm}
              handleFormChange={formState.handleFormChange}
              isMultiStageModel={formState.isMultiStageModel}
            />
          ) : (
            <FileUploadSection
              isLoadingHfToken={formState.isLoadingHfToken}
              hasHfToken={formState.hasHfToken}
              isMultiStageModel={formState.isMultiStageModel}
              loraFiles={formState.loraFiles}
              setLoraFiles={formState.setLoraFiles}
              uploadProgress={formState.uploadProgress}
            />
          )}

          {/* Created By */}
          <div className="space-y-1">
            <Label>Created By:</Label>
            <div className="flex items-center gap-x-2 mb-2">
              <Checkbox
                id="created-by-you"
                checked={formState.addForm.created_by_is_you}
                onCheckedChange={(checked) => formState.handleFormChange('created_by_is_you', checked)}
              />
              <Label htmlFor="created-by-you" className="font-normal">This is my creation</Label>
            </div>
            {!formState.addForm.created_by_is_you && (
              <Input
                placeholder="Creator's username"
                value={formState.addForm.created_by_username}
                onChange={e => formState.handleFormChange('created_by_username', e.target.value)}
                maxLength={30}
              />
            )}
          </div>

          {/* Sample Generations */}
          <SampleGenerationsSection
            isEditMode={formState.isEditMode}
            editingLora={editingLora}
            deletedExistingSampleUrls={formState.deletedExistingSampleUrls}
            setDeletedExistingSampleUrls={formState.setDeletedExistingSampleUrls}
            sampleFiles={formState.sampleFiles}
            setSampleFiles={formState.setSampleFiles}
            previewUrls={formState.previewUrls}
            mainGenerationIndex={formState.mainGenerationIndex}
            setMainGenerationIndex={formState.setMainGenerationIndex}
            fileInputKey={formState.fileInputKey}
            setFileInputKey={formState.setFileInputKey}
          />

          {/* Public Checkbox */}
          <div className="flex items-center gap-x-2">
            <Checkbox
              id="is-public"
              checked={formState.addForm.is_public}
              onCheckedChange={(checked) => formState.handleFormChange('is_public', checked)}
            />
            <Label htmlFor="is-public">Available to others</Label>
          </div>
        </CardContent>
        <ItemCardFooter>
          <Button
            onClick={handleAddLoraFromForm}
            disabled={isButtonDisabled()}
          >
            {formState.isUploading
              ? 'Uploading to HuggingFace...'
              : formState.isSubmitting
                ? (formState.isEditMode ? 'Saving Changes...' : 'Adding LoRA...')
                : (formState.isEditMode ? 'Save Changes' : (formState.uploadMode === 'file' && !formState.isEditMode ? 'Upload & Add LoRA' : 'Add LoRA'))
            }
          </Button>
        </ItemCardFooter>
      </Card>
    </div>
  );
};
