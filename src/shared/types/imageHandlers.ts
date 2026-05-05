/** Shared handler contracts for shot image operations. */
export type ImageDeleteHandler = (id: string) => void;

export type AsyncImageDeleteHandler = (id: string) => void | Promise<void>;

export type BatchImageDeleteHandler = (ids: string[]) => void;

export type ImageDuplicateHandler = (id: string, atFrame: number) => void;

export type ImageReorderHandler = (
  orderedIds: string[],
  draggedItemId?: string,
) => void;

export type FileDropHandler = (
  files: File[],
  targetFrame?: number,
  handles?: Array<FileSystemFileHandle | null>,
) => Promise<void>;

export type GenerationDropHandler = (
  generationId: string,
  imageUrl: string,
  thumbUrl: string | undefined,
  targetFrame?: number,
) => Promise<void>;

export type AddToShotHandler = (
  targetShotId: string,
  generationId: string,
  imageUrl?: string,
  thumbUrl?: string,
) => Promise<boolean>;

export type AddToShotWithoutPositionHandler = (
  targetShotId: string,
  generationId: string,
) => Promise<boolean>;

export type ImageUploadHandler = (files: File[]) => Promise<void>;

export interface ShotImageHandlers {
  onDelete: ImageDeleteHandler;
  onBatchDelete?: BatchImageDeleteHandler;
  onDuplicate?: ImageDuplicateHandler;
  onReorder: ImageReorderHandler;
  onFileDrop?: FileDropHandler;
  onGenerationDrop?: GenerationDropHandler;
  onUpload?: ImageUploadHandler;
}
