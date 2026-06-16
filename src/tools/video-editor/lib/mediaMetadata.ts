import { extractVideoMetadata } from '@/shared/lib/media/videoMetadata.ts';
import type { AssetRegistryEntry } from '@/tools/video-editor/types/index.ts';

const VIDEO_EXTENSION_TYPES: Record<string, string> = {
  '.avi': 'video/x-msvideo',
  '.m4v': 'video/x-m4v',
  '.mkv': 'video/x-matroska',
  '.mov': 'video/quicktime',
  '.mp4': 'video/mp4',
  '.ogv': 'video/ogg',
  '.webm': 'video/webm',
};

const AUDIO_EXTENSION_TYPES: Record<string, string> = {
  '.aac': 'audio/aac',
  '.flac': 'audio/flac',
  '.m4a': 'audio/mp4',
  '.mp3': 'audio/mpeg',
  '.ogg': 'audio/ogg',
  '.wav': 'audio/wav',
};

function loadImageMetadata(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      resolve({ width: image.width, height: image.height });
      URL.revokeObjectURL(url);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load image metadata'));
    };
    image.src = url;
  });
}

function loadAudioMetadata(file: File): Promise<{ duration: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();
    audio.preload = 'metadata';
    audio.onloadedmetadata = () => {
      resolve({ duration: audio.duration });
      URL.revokeObjectURL(url);
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('Failed to load audio metadata'));
    };
    audio.src = url;
  });
}

export async function extractAssetRegistryEntry(
  file: File,
  storagePath: string,
): Promise<AssetRegistryEntry> {
  if (file.type.startsWith('video/')) {
    const metadata = await extractVideoMetadata(file);
    return {
      file: storagePath,
      type: file.type,
      duration: metadata.duration_seconds,
      resolution: `${metadata.width}x${metadata.height}`,
      fps: metadata.frame_rate,
      origin: 'immutable-public',
    };
  }

  if (file.type.startsWith('image/')) {
    const metadata = await loadImageMetadata(file);
    return {
      file: storagePath,
      type: file.type,
      resolution: `${metadata.width}x${metadata.height}`,
      origin: 'immutable-public',
    };
  }

  if (file.type.startsWith('audio/')) {
    const metadata = await loadAudioMetadata(file);
    return {
      file: storagePath,
      type: file.type,
      duration: metadata.duration,
      origin: 'immutable-public',
    };
  }

  const extension = file.name.includes('.')
    ? file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    : '';

  if (extension in VIDEO_EXTENSION_TYPES) {
    try {
      const metadata = await extractVideoMetadata(file);
      return {
        file: storagePath,
        type: file.type || VIDEO_EXTENSION_TYPES[extension],
        duration: metadata.duration_seconds,
        resolution: `${metadata.width}x${metadata.height}`,
        fps: metadata.frame_rate,
        origin: 'immutable-public',
      };
    } catch {
      // Fall through to the generic entry when metadata extraction fails.
    }
  }

  if (extension in AUDIO_EXTENSION_TYPES) {
    try {
      const metadata = await loadAudioMetadata(file);
      return {
        file: storagePath,
        type: file.type || AUDIO_EXTENSION_TYPES[extension],
        duration: metadata.duration,
        origin: 'immutable-public',
      };
    } catch {
      // Fall through to the generic entry when metadata extraction fails.
    }
  }

  return {
    file: storagePath,
    type: file.type || 'application/octet-stream',
    origin: 'immutable-public',
  };
}
