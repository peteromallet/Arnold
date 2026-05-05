import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { continueRender, delayRender } from 'remotion';
import type { ResolvedTimelineClip } from '@/tools/video-editor/types/index.ts';

const FFT_SIZE = 1024;
const HALF_FFT_SIZE = FFT_SIZE / 2;
const MIX_SAMPLE_RATE = 44_100;
const BASS_MAX_HZ = 250;
const MID_MAX_HZ = 4_000;

export type AudioAnalysisData = {
  amplitude: number;
  bass: number;
  mid: number;
  treble: number;
  isBeat: boolean;
  frequencyBins: number[];
};

export const SILENT_AUDIO_DATA: AudioAnalysisData = {
  amplitude: 0,
  bass: 0,
  mid: 0,
  treble: 0,
  isBeat: false,
  frequencyBins: Array.from({ length: HALF_FFT_SIZE }, () => 0),
};

export const AudioAnalysisContext = createContext<AudioAnalysisData[] | null>(null);

const clamp01 = (value: number): number => Math.min(1, Math.max(0, value));

const getSilentFrames = (durationInFrames: number): AudioAnalysisData[] => {
  return Array.from({ length: Math.max(1, durationInFrames) }, () => SILENT_AUDIO_DATA);
};

const getFrameWindow = (samples: Float32Array, start: number, end: number): Float32Array => {
  const frameWindow = new Float32Array(FFT_SIZE);
  const available = Math.max(0, Math.min(samples.length, end) - start);
  const copyLength = Math.min(FFT_SIZE, available);

  for (let index = 0; index < copyLength; index += 1) {
    const sample = samples[start + index] ?? 0;
    const window = 0.5 - 0.5 * Math.cos((2 * Math.PI * index) / (FFT_SIZE - 1));
    frameWindow[index] = sample * window;
  }

  return frameWindow;
};

const runFft = (input: Float32Array): Float32Array => {
  const real = new Float32Array(FFT_SIZE);
  const imaginary = new Float32Array(FFT_SIZE);
  real.set(input.subarray(0, FFT_SIZE));

  for (let index = 1, bit = 0; index < FFT_SIZE; index += 1) {
    let mask = FFT_SIZE >> 1;
    while (bit & mask) {
      bit ^= mask;
      mask >>= 1;
    }
    bit ^= mask;
    if (index < bit) {
      [real[index], real[bit]] = [real[bit], real[index]];
    }
  }

  for (let size = 2; size <= FFT_SIZE; size <<= 1) {
    const halfSize = size >> 1;
    const step = (-2 * Math.PI) / size;
    for (let offset = 0; offset < FFT_SIZE; offset += size) {
      for (let index = 0; index < halfSize; index += 1) {
        const even = offset + index;
        const odd = even + halfSize;
        const angle = step * index;
        const cosine = Math.cos(angle);
        const sine = Math.sin(angle);
        const oddReal = real[odd] * cosine - imaginary[odd] * sine;
        const oddImaginary = real[odd] * sine + imaginary[odd] * cosine;
        real[odd] = real[even] - oddReal;
        imaginary[odd] = imaginary[even] - oddImaginary;
        real[even] += oddReal;
        imaginary[even] += oddImaginary;
      }
    }
  }

  const magnitudes = new Float32Array(HALF_FFT_SIZE);
  for (let index = 0; index < HALF_FFT_SIZE; index += 1) {
    magnitudes[index] = Math.hypot(real[index], imaginary[index]);
  }
  return magnitudes;
};

const getBandAverage = (
  magnitudes: Float32Array,
  sampleRate: number,
  minHz: number,
  maxHz: number | null,
): number => {
  const binSize = sampleRate / FFT_SIZE;
  const startBin = Math.max(0, Math.floor(minHz / binSize));
  const endBin = Math.min(
    magnitudes.length - 1,
    maxHz === null ? magnitudes.length - 1 : Math.floor(maxHz / binSize),
  );

  if (endBin < startBin) {
    return 0;
  }

  let total = 0;
  for (let index = startBin; index <= endBin; index += 1) {
    total += magnitudes[index] ?? 0;
  }

  return total / Math.max(1, endBin - startBin + 1);
};

const toMonoSamples = (buffer: AudioBuffer): Float32Array => {
  const mono = new Float32Array(buffer.length);
  const channelCount = Math.max(1, buffer.numberOfChannels);

  for (let channel = 0; channel < channelCount; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let index = 0; index < buffer.length; index += 1) {
      mono[index] += (data[index] ?? 0) / channelCount;
    }
  }

  return mono;
};

const analyzeMixedBuffer = (
  buffer: AudioBuffer,
  fps: number,
  totalDurationInFrames: number,
): AudioAnalysisData[] => {
  const samples = toMonoSamples(buffer);
  const samplesPerFrame = buffer.sampleRate / fps;
  const frames = Math.max(1, totalDurationInFrames);
  const rawFrames: Array<AudioAnalysisData & { rawBass: number }> = [];
  let maxMagnitude = 0;

  for (let frame = 0; frame < frames; frame += 1) {
    const start = Math.floor(frame * samplesPerFrame);
    const end = Math.floor((frame + 1) * samplesPerFrame);
    if (start >= samples.length) {
      rawFrames.push({ ...SILENT_AUDIO_DATA, rawBass: 0 });
      continue;
    }

    let squareSum = 0;
    const sampleCount = Math.max(1, Math.min(samples.length, end) - start);
    for (let index = start; index < Math.min(samples.length, end); index += 1) {
      const sample = samples[index] ?? 0;
      squareSum += sample * sample;
    }

    const magnitudes = runFft(getFrameWindow(samples, start, end));
    let framePeak = 0;
    for (const magnitude of magnitudes) {
      framePeak = Math.max(framePeak, magnitude);
    }
    maxMagnitude = Math.max(maxMagnitude, framePeak);

    rawFrames.push({
      amplitude: clamp01(Math.sqrt(squareSum / sampleCount)),
      bass: 0,
      mid: 0,
      treble: 0,
      isBeat: false,
      frequencyBins: Array.from(magnitudes),
      rawBass: getBandAverage(magnitudes, buffer.sampleRate, 0, BASS_MAX_HZ),
    });
    rawFrames[frame].mid = getBandAverage(magnitudes, buffer.sampleRate, BASS_MAX_HZ, MID_MAX_HZ);
    rawFrames[frame].treble = getBandAverage(magnitudes, buffer.sampleRate, MID_MAX_HZ, null);
  }

  const magnitudeScale = maxMagnitude > 0 ? maxMagnitude : 1;
  const rollingWindow = Math.max(1, Math.round(fps * 0.75));
  const beatCooldownFrames = Math.max(1, Math.ceil(fps * 0.3));
  const normalizedBass = rawFrames.map((frame) => clamp01(frame.rawBass / magnitudeScale));
  let lastBeatFrame = -beatCooldownFrames;

  return rawFrames.map((frame, index) => {
    const windowStart = Math.max(0, index - rollingWindow);
    const history = normalizedBass.slice(windowStart, index);
    const rollingAverage = history.length > 0
      ? history.reduce((total, value) => total + value, 0) / history.length
      : normalizedBass[index];
    const bass = normalizedBass[index];
    const isBeat = (
      index - lastBeatFrame >= beatCooldownFrames
      && rollingAverage > 0.01
      && bass > rollingAverage * 1.5
    );
    if (isBeat) {
      lastBeatFrame = index;
    }

    return {
      amplitude: frame.amplitude,
      bass,
      mid: clamp01(frame.mid / magnitudeScale),
      treble: clamp01(frame.treble / magnitudeScale),
      isBeat,
      frequencyBins: frame.frequencyBins.map((value) => clamp01(value / magnitudeScale)),
    };
  });
};

const analyzeAudioClips = async (
  clips: ResolvedTimelineClip[],
  fps: number,
  totalDurationInFrames: number,
): Promise<AudioAnalysisData[]> => {
  const validClips = clips.filter((clip) => clip.assetEntry?.src);
  if (validClips.length === 0 || typeof OfflineAudioContext === 'undefined') {
    return getSilentFrames(totalDurationInFrames);
  }

  const decoderContext = new OfflineAudioContext(1, 1, MIX_SAMPLE_RATE);
  const decodeCache = new Map<string, Promise<AudioBuffer>>();
  const getDecodedBuffer = (src: string): Promise<AudioBuffer> => {
    if (!decodeCache.has(src)) {
      decodeCache.set(src, fetch(src)
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Failed to fetch audio source: ${response.status}`);
          }
          return decoderContext.decodeAudioData((await response.arrayBuffer()).slice(0));
        }));
    }
    return decodeCache.get(src)!;
  };

  const totalSamples = Math.max(1, Math.ceil((totalDurationInFrames / fps) * MIX_SAMPLE_RATE));
  const mixContext = new OfflineAudioContext(2, totalSamples, MIX_SAMPLE_RATE);
  const decodedClips = await Promise.all(validClips.map(async (clip) => ({
    clip,
    buffer: await getDecodedBuffer(clip.assetEntry!.src),
  })));

  for (const { clip, buffer } of decodedClips) {
    const speed = clip.speed && clip.speed > 0 ? clip.speed : 1;
    const clipFrom = Math.max(0, clip.from ?? 0);
    const clipTo = Math.min(typeof clip.to === 'number' ? clip.to : buffer.duration, buffer.duration);
    const sourceDuration = Math.max(0, clipTo - clipFrom);
    if (sourceDuration <= 0) {
      continue;
    }

    const source = mixContext.createBufferSource();
    const gain = mixContext.createGain();
    source.buffer = buffer;
    source.playbackRate.value = speed;
    gain.gain.value = clip.volume ?? 1;
    source.connect(gain);
    gain.connect(mixContext.destination);
    source.start(Math.max(0, clip.at), clipFrom, sourceDuration);
  }

  return analyzeMixedBuffer(await mixContext.startRendering(), fps, totalDurationInFrames);
};

const createSyntheticFrame = (frame: number, fps: number): AudioAnalysisData => {
  const seconds = frame / fps;
  const beatInterval = Math.max(1, Math.round(fps * 0.6));
  const beatWindow = Math.max(1, Math.round(fps * 0.12));
  const beatOffset = frame % beatInterval;
  const beatPulse = beatOffset < beatWindow ? 1 - beatOffset / beatWindow : 0;
  const bass = clamp01(0.35 + 0.25 * Math.sin(seconds * Math.PI * 2 * 1.1) + beatPulse * 0.45);
  const mid = clamp01(0.4 + 0.25 * Math.sin(seconds * Math.PI * 2 * 2.3 + 0.8));
  const treble = clamp01(0.45 + 0.2 * Math.sin(seconds * Math.PI * 2 * 5.2 + 1.4));
  const amplitude = clamp01(0.2 + bass * 0.35 + mid * 0.25 + treble * 0.2);

  return {
    amplitude,
    bass,
    mid,
    treble,
    isBeat: beatPulse > 0.9,
    frequencyBins: Array.from({ length: HALF_FFT_SIZE }, (_, index) => {
      const ratio = index / HALF_FFT_SIZE;
      const bassBand = Math.max(0, 1 - Math.abs(ratio - 0.04) / 0.05) * bass;
      const midBand = Math.max(0, 1 - Math.abs(ratio - 0.18) / 0.08) * mid;
      const trebleBand = Math.max(0, 1 - Math.abs(ratio - 0.62) / 0.12) * treble;
      return clamp01(Math.max(bassBand + beatPulse * 0.4, midBand, trebleBand));
    }),
  };
};

type AudioAnalysisProviderProps = {
  children: ReactNode;
  clips: ResolvedTimelineClip[];
  fps: number;
  totalDurationInFrames: number;
};

export function AudioAnalysisProvider({
  children,
  clips,
  fps,
  totalDurationInFrames,
}: AudioAnalysisProviderProps) {
  const handle = useState(() => delayRender('Audio analysis'))[0];
  const renderReleasedRef = useRef(false);
  const silentFrames = useMemo(() => getSilentFrames(totalDurationInFrames), [totalDurationInFrames]);
  const [analysisFrames, setAnalysisFrames] = useState<AudioAnalysisData[]>(silentFrames);

  useEffect(() => {
    let cancelled = false;
    const releaseRender = () => {
      if (!renderReleasedRef.current) {
        renderReleasedRef.current = true;
        continueRender(handle);
      }
    };

    if (clips.length === 0) {
      setAnalysisFrames(silentFrames);
      releaseRender();
      return () => {
        releaseRender();
      };
    }

    analyzeAudioClips(clips, fps, totalDurationInFrames)
      .then((frames) => {
        if (!cancelled) {
          setAnalysisFrames(frames);
        }
      })
      .catch((error) => {
        console.warn('Audio analysis failed, falling back to silent data.', error);
        if (!cancelled) {
          setAnalysisFrames(silentFrames);
        }
      })
      .finally(() => {
        releaseRender();
      });

    return () => {
      cancelled = true;
      releaseRender();
    };
  }, [clips, fps, handle, silentFrames, totalDurationInFrames]);

  return (
    <AudioAnalysisContext.Provider value={analysisFrames}>
      {children}
    </AudioAnalysisContext.Provider>
  );
}

export function SyntheticAudioProvider({
  children,
  fps,
  durationInFrames,
}: {
  children: ReactNode;
  fps: number;
  durationInFrames: number;
}) {
  const frames = useMemo(
    () => Array.from({ length: Math.max(1, durationInFrames) }, (_, frame) => createSyntheticFrame(frame, fps)),
    [durationInFrames, fps],
  );

  return (
    <AudioAnalysisContext.Provider value={frames}>
      {children}
    </AudioAnalysisContext.Provider>
  );
}

export const useAudioAnalysisContext = (): AudioAnalysisData[] | null => useContext(AudioAnalysisContext);
