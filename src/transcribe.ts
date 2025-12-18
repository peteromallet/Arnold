import Groq from 'groq-sdk';
import { config } from './config.js';
import { logger } from './logger.js';
import { ConfigError, TranscriptionError } from './errors.js';

let groqClient: Groq | null = null;

/**
 * Get or create Groq client (lazy initialization)
 */
function getGroqClient(): Groq {
  if (!config.groq.apiKey) {
    throw new ConfigError('GROQ_API_KEY not set - add it to .env to enable voice notes');
  }
  
  if (!groqClient) {
    groqClient = new Groq({ apiKey: config.groq.apiKey });
  }
  
  return groqClient;
}

/**
 * Transcribe an audio file using Groq's Whisper API
 * 
 * @param audioBuffer - The audio file buffer
 * @param filename - Original filename (used for content type detection)
 * @returns The transcribed text
 * @throws TranscriptionError if transcription fails
 * @throws ConfigError if GROQ_API_KEY is not set
 */
export async function transcribeAudio(audioBuffer: Buffer, filename: string): Promise<string> {
  const client = getGroqClient();

  // Create a File object from the buffer
  // Use slice to get a proper ArrayBuffer that's compatible with File constructor
  const arrayBuffer = audioBuffer.buffer.slice(
    audioBuffer.byteOffset,
    audioBuffer.byteOffset + audioBuffer.byteLength,
  ) as ArrayBuffer;
  const file = new File([arrayBuffer], filename, { type: 'audio/ogg' });

  logger.info('Transcribing audio', { filename, sizeBytes: audioBuffer.length });

  try {
    const transcription = await client.audio.transcriptions.create({
      file: file,
      model: 'whisper-large-v3-turbo',
      temperature: 0,
      response_format: 'verbose_json',
    });

    const text = transcription.text?.trim() || '';
    
    if (!text) {
      throw new TranscriptionError('No speech detected in audio');
    }

    logger.info('Transcription completed', { 
      filename, 
      textLength: text.length,
      preview: text.substring(0, 50) + (text.length > 50 ? '...' : ''),
    });

    return text;
  } catch (error) {
    if (error instanceof TranscriptionError) {
      throw error;
    }
    
    const message = error instanceof Error ? error.message : String(error);
    logger.error('Transcription failed', error instanceof Error ? error : undefined, { filename });
    throw new TranscriptionError(`Failed to transcribe audio: ${message}`);
  }
}

/**
 * Check if voice transcription is available
 */
export function isTranscriptionAvailable(): boolean {
  return !!config.groq.apiKey;
}
