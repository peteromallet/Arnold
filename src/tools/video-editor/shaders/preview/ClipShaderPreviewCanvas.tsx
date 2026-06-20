import {
  useLayoutEffect,
  useMemo,
  useRef,
  type CSSProperties,
} from 'react';
import type {
  TimelineClipShaderMetadata,
} from '@/tools/video-editor/types/index.ts';
import {
  createWebGLShaderPreviewSurface,
  type WebGLShaderPreviewSurface,
} from '@/tools/video-editor/shaders/preview/WebGLShaderPreviewSurface.ts';
import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';

export interface ClipShaderPreviewCanvasProps {
  readonly shader: TimelineClipShaderMetadata;
  readonly record: ShaderEffectRegistryRecord;
  readonly timeSeconds: number;
  readonly frame: number;
  readonly width: number;
  readonly height: number;
  readonly className?: string;
  readonly style?: CSSProperties;
  readonly testId?: string;
}

function normalizeDimension(value: number): number {
  return Number.isFinite(value) ? Math.max(1, Math.floor(value)) : 1;
}

function passKind(record: ShaderEffectRegistryRecord): string {
  return typeof record.pass === 'string' ? record.pass : record.pass.kind;
}

function sourceKey(record: ShaderEffectRegistryRecord): string {
  return record.source.kind === 'inline'
    ? `inline:${record.source.vertex ?? ''}:${record.source.fragment}`
    : `module:${record.source.specifier}:${record.source.exportName ?? 'default'}`;
}

export function ClipShaderPreviewCanvas({
  shader,
  record,
  timeSeconds,
  frame,
  width,
  height,
  className,
  style,
  testId = 'clip-shader-preview-canvas',
}: ClipShaderPreviewCanvasProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const surfaceRef = useRef<WebGLShaderPreviewSurface | null>(null);
  const canvasKey = useMemo(() => sourceKey(record), [record]);
  const canvasWidth = normalizeDimension(width);
  const canvasHeight = normalizeDimension(height);
  const active = shader.enabled !== false
    && record.status === 'active'
    && passKind(record) === 'clip'
    && record.source.kind === 'inline';

  useLayoutEffect(() => {
    const host = hostRef.current;
    surfaceRef.current?.dispose();
    surfaceRef.current = null;

    if (!host || !active || record.source.kind !== 'inline') {
      return undefined;
    }

    const surface = createWebGLShaderPreviewSurface({
      shaderId: shader.shaderId,
      extensionId: shader.extensionId,
      contributionId: shader.contributionId,
      vertexSource: record.source.vertex,
      fragmentSource: record.source.fragment,
      uniforms: record.uniforms,
      uniformValues: shader.uniforms,
      textures: record.textures,
      textureValues: shader.textures,
      width: canvasWidth,
      height: canvasHeight,
    });

    surfaceRef.current = surface;
    if (surface.canvas) {
      surface.canvas.dataset.testid = `${testId}-surface`;
      surface.canvas.style.display = 'block';
      surface.canvas.style.width = '100%';
      surface.canvas.style.height = '100%';
      host.replaceChildren(surface.canvas);
    } else {
      host.replaceChildren();
    }

    return () => {
      surface.dispose();
      if (surfaceRef.current === surface) {
        surfaceRef.current = null;
      }
      host.replaceChildren();
    };
  }, [
    active,
    canvasHeight,
    canvasKey,
    canvasWidth,
    record,
    shader.contributionId,
    shader.extensionId,
    shader.shaderId,
    shader.textures,
    shader.uniforms,
    testId,
  ]);

  useLayoutEffect(() => {
    const surface = surfaceRef.current;
    if (!surface || !active) return;
    surface.setUniformValues(shader.uniforms ?? {});
    surface.setTextureValues(shader.textures ?? {});
    surface.resize(canvasWidth, canvasHeight);
    surface.renderFrame(timeSeconds, frame);
  }, [
    active,
    canvasHeight,
    canvasWidth,
    frame,
    shader.textures,
    shader.uniforms,
    timeSeconds,
  ]);

  if (!active) {
    return null;
  }

  return (
    <div
      ref={hostRef}
      className={className}
      data-testid={testId}
      data-shader-id={shader.shaderId}
      data-shader-frame={Math.floor(frame)}
      data-shader-time={timeSeconds}
      style={style}
    />
  );
}
