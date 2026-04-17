import {
  useRef,
  useState,
  useEffect,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from 'react';
import { GenerationRow } from '@/domains/generation/types';
import { isVideoAny } from '@/shared/lib/typeGuards';
import { useIsMobile } from '@/shared/hooks/mobile';
import { useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { useUserUIState } from '@/shared/hooks/useUserUIState';
import { usePublicLoras } from '@/features/resources/hooks/useResources';
import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { useUpscale } from '@/domains/media-lightbox/hooks/useUpscale';
import { useInpainting } from '@/domains/media-lightbox/hooks/useInpainting';
import { useSourceGeneration } from '@/domains/media-lightbox/hooks/useSourceGeneration';
import { useMagicEditMode } from '@/domains/media-lightbox/hooks/useMagicEditMode';
import { useStarToggle } from '@/domains/media-lightbox/hooks/useStarToggle';
import { useRepositionMode } from '@/domains/media-lightbox/hooks/useRepositionMode';
import { useImg2ImgMode } from '@/domains/media-lightbox/hooks/useImg2ImgMode';
import { useEditSettingsPersistence } from '@/domains/media-lightbox/hooks/persistence/useEditSettingsPersistence';
import type { AnnotationMode } from '@/domains/media-lightbox/hooks/inpainting/types';
import type { ImageEditState } from '@/domains/media-lightbox/contexts/ImageEditContext';
import { buildImageEditStateValue } from '@/tools/edit-images/model/buildImageEditStateValue';
import { downloadMedia } from '@/shared/lib/media/downloadMedia';
import { useVariants } from '@/shared/hooks/variants/useVariants';
type InpaintingHookResult = ReturnType<typeof useInpainting>;
type MagicEditHookResult = ReturnType<typeof useMagicEditMode>;
type RepositionHookResult = ReturnType<typeof useRepositionMode>;
type Img2ImgHookResult = ReturnType<typeof useImg2ImgMode>;
type StarToggleHookResult = ReturnType<typeof useStarToggle>;
type SourceGenerationData = ReturnType<typeof useSourceGeneration>['sourceGenerationData'];
type PublicLorasData = ReturnType<typeof usePublicLoras>['data'];
type ImageEditValue = ImageEditState;

function resolveActualGenerationId(media: GenerationRow): string | null {
  const isShotGenerationRecord = media.shotImageEntryId === media.id ||
    media.shot_generation_id === media.id;
  return media.generation_id || (!isShotGenerationRecord ? media.id : null);
}

// Inpainting fields forwarded 1:1 from the hook
const INPAINTING_PASSTHROUGH_KEYS = [
  'isInpaintMode', 'editMode', 'brushStrokes', 'currentStroke', 'isDrawing',
  'isEraseMode', 'brushSize', 'annotationMode', 'selectedShapeId', 'isAnnotateMode',
  'handleKonvaPointerDown', 'handleKonvaPointerMove', 'handleKonvaPointerUp',
  'handleShapeClick', 'strokeOverlayRef', 'getDeleteButtonPosition',
  'handleToggleFreeForm', 'handleDeleteSelected', 'handleUndo', 'handleClearMask',
  'setIsInpaintMode', 'setEditMode', 'setBrushSize', 'setIsEraseMode', 'setAnnotationMode',
] as const;

type InpaintingPassthroughKeys = typeof INPAINTING_PASSTHROUGH_KEYS[number];

function pickInpaintingPassthrough(
  inpainting: InpaintingHookResult,
): Pick<InpaintingHookResult, InpaintingPassthroughKeys> {
  const result = {} as Pick<InpaintingHookResult, InpaintingPassthroughKeys>;
  for (const key of INPAINTING_PASSTHROUGH_KEYS) {
    (result as Record<string, unknown>)[key] = inpainting[key];
  }
  return result;
}

export interface InlineEditStateResult {
  media: GenerationRow;
  canvasEnvironment: {
    isMobile: boolean;
    selectedProjectId: string | null | undefined;
    isCloudMode: boolean;
    isVideo: boolean;
    imageContainerRef: RefObject<HTMLDivElement>;
    effectiveImageUrl: string;
    imageDimensions: { width: number; height: number } | null;
    setImageDimensions: Dispatch<SetStateAction<{ width: number; height: number } | null>>;
    isUpscaling: boolean;
    handleUpscale: () => Promise<void>;
  };
  inpaintingState:
    Pick<InpaintingHookResult, InpaintingPassthroughKeys> & {
      isSpecialEditMode: boolean;
      handleEnterMagicEditMode: MagicEditHookResult['handleEnterMagicEditMode'];
    };
  transformState: {
    repositionTransform: RepositionHookResult['transform'];
    setScale: RepositionHookResult['setScale'];
    setRotation: RepositionHookResult['setRotation'];
    toggleFlipH: RepositionHookResult['toggleFlipH'];
    toggleFlipV: RepositionHookResult['toggleFlipV'];
    resetTransform: RepositionHookResult['resetTransform'];
    getTransformStyle: RepositionHookResult['getTransformStyle'];
  };
  generationState: {
    localStarred: StarToggleHookResult['localStarred'];
    toggleStarMutation: StarToggleHookResult['toggleStarMutation'];
    handleToggleStar: StarToggleHookResult['handleToggleStar'];
    handleDownload: () => Promise<void>;
    handleUnifiedGenerate: MagicEditHookResult['handleUnifiedGenerate'];
    handleGenerateAnnotatedEdit: InpaintingHookResult['handleGenerateAnnotatedEdit'];
    handleGenerateReposition: RepositionHookResult['handleGenerateReposition'];
    handleSaveAsVariant: RepositionHookResult['handleSaveAsVariant'];
    handleGenerateImg2Img: Img2ImgHookResult['handleGenerateImg2Img'];
    img2imgLoraManager: Img2ImgHookResult['loraManager'];
  };
  variants: {
    variants: ReturnType<typeof useVariants>['variants'];
    activeVariant: ReturnType<typeof useVariants>['activeVariant'];
    isLoading: boolean;
    setActiveVariantId: ReturnType<typeof useVariants>['setActiveVariantId'];
    setPrimaryVariant: ReturnType<typeof useVariants>['setPrimaryVariant'];
    deleteVariant: ReturnType<typeof useVariants>['deleteVariant'];
  };
  sourceGenerationData: SourceGenerationData;
  availableLoras: PublicLorasData;
  imageEditValue: ImageEditValue;
}

export function useInlineEditState(
  media: GenerationRow,
  onNavigateToGeneration?: (generationId: string) => Promise<void>,
): InlineEditStateResult {
  // --- Environment ---
  const imageContainerRef = useRef<HTMLDivElement>(null);
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);
  const [createAsGeneration, setCreateAsGeneration] = useState(false);
  const isMobile = useIsMobile();
  const { selectedProjectId } = useProjectSelectionContext();
  const { value: generationMethods } = useUserUIState('generationMethods', { onComputer: true, inCloud: true });
  const isCloudMode = generationMethods.inCloud;
  const isVideo = isVideoAny(media);
  const actualGenerationId = resolveActualGenerationId(media);
  const { effectiveImageUrl: upscaleImageUrl, isUpscaling, handleUpscale, setActiveVariant: setUpscaleActiveVariant } = useUpscale({
    media,
    selectedProjectId,
    isVideo,
  });

  // --- Persistence ---
  const editSettings = useEditSettingsPersistence({
    generationId: actualGenerationId,
    projectId: selectedProjectId ?? null,
  });
  const variants = useVariants({
    generationId: actualGenerationId,
    enabled: true,
  });
  const [annotationMode, setAnnotationMode] = useState<AnnotationMode>(null);

  const activeVariant = variants.activeVariant;
  const effectiveImageUrl = activeVariant?.location || upscaleImageUrl;

  useEffect(() => {
    setUpscaleActiveVariant(activeVariant?.location, activeVariant?.id);
  }, [setUpscaleActiveVariant, activeVariant?.location, activeVariant?.id]);

  useEffect(() => {
    setAnnotationMode(null);
  }, [media.id]);

  const { data: availableLoras } = usePublicLoras();

  // --- Inpainting & Magic Edit ---
  const handleExitInpaintModeRef = useRef<() => void>(() => {});
  const inpainting = useInpainting({
    media,
    selectedProjectId,
    isVideo,
    imageDimensions,
    imageContainerRef,
    handleExitInpaintMode: () => handleExitInpaintModeRef.current(),
    loras: editSettings.editModeLoras,
    toolTypeOverride: TOOL_IDS.EDIT_IMAGES,
    activeVariantId: activeVariant?.id,
    activeVariantLocation: activeVariant?.location,
    createAsGeneration,
    advancedSettings: editSettings.advancedSettings,
    qwenEditModel: editSettings.qwenEditModel,
    editMode: editSettings.editMode ?? 'text',
    annotationMode,
    inpaintPrompt: editSettings.prompt,
    inpaintNumGenerations: editSettings.numGenerations,
    setEditMode: editSettings.setEditMode,
    setAnnotationMode,
    setInpaintPrompt: editSettings.setPrompt,
    setInpaintNumGenerations: editSettings.setNumGenerations,
    initialActive: true,
  });

  const magic = useMagicEditMode({
    media,
    selectedProjectId,
    isInpaintMode: inpainting.isInpaintMode,
    setIsInpaintMode: (v: boolean) => inpainting.setIsInpaintMode(v),
    handleEnterInpaintMode: inpainting.handleEnterInpaintMode,
    handleGenerateInpaint: inpainting.handleGenerateInpaint,
    brushStrokes: inpainting.brushStrokes,
    inpaintPrompt: inpainting.inpaintPrompt,
    setInpaintPrompt: inpainting.setInpaintPrompt,
    inpaintNumGenerations: inpainting.inpaintNumGenerations,
    setInpaintNumGenerations: inpainting.setInpaintNumGenerations,
    editModeLoras: editSettings.editModeLoras,
    loraMode: editSettings.loraMode,
    setLoraMode: editSettings.setLoraMode,
    sourceUrlForTasks: effectiveImageUrl,
    imageDimensions,
    toolTypeOverride: TOOL_IDS.EDIT_IMAGES,
    activeVariantLocation: activeVariant?.location,
    createAsGeneration,
    advancedSettings: editSettings.advancedSettings,
    qwenEditModel: editSettings.qwenEditModel,
    initialActive: true,
  });

  handleExitInpaintModeRef.current = () => {
    inpainting.setIsInpaintMode(false);
    magic.setIsMagicEditMode(false);
  };

  // --- Reposition ---
  const reposition = useRepositionMode({
    media,
    selectedProjectId,
    imageDimensions,
    imageContainerRef,
    loras: editSettings.editModeLoras,
    inpaintPrompt: inpainting.inpaintPrompt,
    inpaintNumGenerations: inpainting.inpaintNumGenerations,
    toolTypeOverride: TOOL_IDS.EDIT_IMAGES,
    onVariantCreated: variants.setActiveVariantId,
    refetchVariants: variants.refetch,
    createAsGeneration,
    activeVariantLocation: activeVariant?.location,
    activeVariantId: activeVariant?.id,
    activeVariantParams: activeVariant?.params,
  });

  // --- Img2Img ---
  const img2img = useImg2ImgMode({
    media,
    selectedProjectId,
    isVideo,
    availableLoras,
    state: {
      strength: editSettings.img2imgStrength,
      setStrength: editSettings.setImg2imgStrength,
      enablePromptExpansion: editSettings.img2imgEnablePromptExpansion,
      setEnablePromptExpansion: editSettings.setImg2imgEnablePromptExpansion,
      prompt: editSettings.img2imgPrompt,
      setPrompt: editSettings.setImg2imgPrompt,
      promptHasBeenSet: editSettings.img2imgPromptHasBeenSet,
      numGenerations: editSettings.numGenerations,
    },
    source: {
      baseImageUrl: effectiveImageUrl,
      activeVariantLocation: activeVariant?.location,
      activeVariantId: activeVariant?.id,
    },
    options: {
      toolTypeOverride: TOOL_IDS.EDIT_IMAGES,
      createAsGeneration,
    },
  });

  const { sourceGenerationData } = useSourceGeneration({
    media,
    onOpenExternalGeneration: onNavigateToGeneration,
  });
  const starToggle = useStarToggle({ media });

  const handleDownload = async () => {
    await downloadMedia(effectiveImageUrl, media.id, isVideo, media.contentType);
  };

  const handleUnifiedGenerate = async () => {
    await editSettings.flushTextFields();
    await magic.handleUnifiedGenerate();
  };

  const handleGenerateAnnotatedEdit = async () => {
    await editSettings.flushTextFields();
    await inpainting.handleGenerateAnnotatedEdit();
  };

  const handleGenerateReposition = async () => {
    await editSettings.flushTextFields();
    await reposition.handleGenerateReposition();
  };

  const handleGenerateImg2Img = async () => {
    await editSettings.flushTextFields();
    await img2img.handleGenerateImg2Img();
  };

  // --- Build imageEditValue ---
  const imageEditValue = buildImageEditStateValue({
    inpainting,
    magic,
    reposition,
    img2img,
    imageContainerRef,
    handleExitInpaintMode: () => inpainting.setIsInpaintMode(false),
    editMode: editSettings.editMode ?? 'text',
    setEditMode: editSettings.setEditMode,
    loraMode: editSettings.loraMode,
    setLoraMode: editSettings.setLoraMode,
    customLoraUrl: editSettings.customLoraUrl,
    setCustomLoraUrl: editSettings.setCustomLoraUrl,
    createAsGeneration,
    setCreateAsGeneration,
    qwenEditModel: editSettings.qwenEditModel,
    setQwenEditModel: editSettings.setQwenEditModel,
    advancedSettings: editSettings.advancedSettings,
    setAdvancedSettings: editSettings.setAdvancedSettings,
    flushTextFields: editSettings.flushTextFields,
  });

  return {
    media,
    canvasEnvironment: {
      isMobile,
      selectedProjectId,
      isCloudMode,
      isVideo,
      imageContainerRef,
      effectiveImageUrl,
      imageDimensions,
      setImageDimensions,
      isUpscaling,
      handleUpscale,
    },
    inpaintingState: {
      ...pickInpaintingPassthrough(inpainting),
      isSpecialEditMode: magic.isSpecialEditMode,
      handleEnterMagicEditMode: magic.handleEnterMagicEditMode,
    },
    transformState: {
      repositionTransform: reposition.transform,
      setScale: reposition.setScale,
      setRotation: reposition.setRotation,
      toggleFlipH: reposition.toggleFlipH,
      toggleFlipV: reposition.toggleFlipV,
      resetTransform: reposition.resetTransform,
      getTransformStyle: reposition.getTransformStyle,
    },
    generationState: {
      localStarred: starToggle.localStarred,
      toggleStarMutation: starToggle.toggleStarMutation,
      handleToggleStar: starToggle.handleToggleStar,
      handleDownload,
      handleUnifiedGenerate,
      handleGenerateAnnotatedEdit,
      handleGenerateReposition,
      handleSaveAsVariant: reposition.handleSaveAsVariant,
      handleGenerateImg2Img,
      img2imgLoraManager: img2img.loraManager,
    },
    variants: {
      variants: variants.variants,
      activeVariant: variants.activeVariant,
      isLoading: variants.isLoading,
      setActiveVariantId: variants.setActiveVariantId,
      setPrimaryVariant: variants.setPrimaryVariant,
      deleteVariant: variants.deleteVariant,
    },
    sourceGenerationData,
    availableLoras,
    imageEditValue,
  } satisfies InlineEditStateResult;
}
