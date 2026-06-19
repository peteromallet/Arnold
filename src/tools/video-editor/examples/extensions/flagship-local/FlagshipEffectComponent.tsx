/**
 * FlagshipEffectComponent — Flagship trusted-local component effect example.
 *
 * Demonstrates a visible, parameterized Remotion component that can be
 * registered as a trusted component effect via ctx.effects.registerComponent().
 *
 * The component responds to schema parameters (intensity, color, style, animate)
 * and produces a visually distinct overlay that changes frame-by-frame.
 *
 * This file must NOT import from editor internals (src/tools/video-editor/*).
 * It imports from react and remotion — the standard component-effect runtime.
 *
 * @publicContract
 */

import type { FC } from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Parameter shape consumed by this component at render time. */
interface FlagshipGlowParams {
  /** Glow intensity, 0–1 (default 0.5). */
  intensity?: number;
  /** CSS-compatible color string (default "#ff6b6b"). */
  color?: string;
  /** Visual style: "glow", "vignette", or "both" (default "glow"). */
  style?: 'glow' | 'vignette' | 'both';
  /** Whether the glow pulses over time (default true). */
  animate?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Flagship Glow — a parameterized overlay effect.
 *
 * Renders a colored glow and/or vignette that responds to the current frame
 * and the parameters stored in `params`.
 */
export const FlagshipEffectComponent: FC<{
  children: React.ReactNode;
  durationInFrames: number;
  effectFrames?: number;
  intensity?: number;
  params?: Record<string, unknown>;
}> = ({ children, durationInFrames, intensity: legacyIntensity, params }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Resolve typed params with schema defaults
  const p = params as FlagshipGlowParams | undefined;
  const glowIntensity = p?.intensity ?? legacyIntensity ?? 0.5;
  const glowColor = p?.color ?? '#ff6b6b';
  const glowStyle = p?.style ?? 'glow';
  const glowAnimate = p?.animate ?? true;

  // Animate intensity when enabled
  const animatedIntensity = glowAnimate
    ? interpolate(
        Math.sin((frame / fps) * 3),
        [-1, 1],
        [glowIntensity * 0.4, glowIntensity],
      )
    : glowIntensity;

  const showGlow = glowStyle === 'glow' || glowStyle === 'both';
  const showVignette = glowStyle === 'vignette' || glowStyle === 'both';

  return (
    <AbsoluteFill>
      {/* Glow overlay */}
      {showGlow && (
        <AbsoluteFill
          style={{
            background: `radial-gradient(ellipse at center, ${glowColor} 0%, transparent 70%)`,
            opacity: animatedIntensity * 0.6,
            pointerEvents: 'none',
          }}
        />
      )}

      {/* Vignette overlay */}
      {showVignette && (
        <AbsoluteFill
          style={{
            background: `radial-gradient(ellipse at center, transparent 40%, ${glowColor} 100%)`,
            opacity: animatedIntensity * 0.5,
            pointerEvents: 'none',
          }}
        />
      )}

      {/* Children render beneath the overlays */}
      <AbsoluteFill style={{ zIndex: 0 }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};
