import { describe, expect, it } from 'vitest';
import {
  SHADER_DIAGNOSTIC_CODES,
  parseWebGLInfoLog,
  validateShaderSchemas,
  validateShaderTextureSchema,
  validateShaderUniformSchema,
} from '@/tools/video-editor/shaders/compile/diagnostics.ts';

const CONTEXT = {
  shaderId: 'shader.grade',
  extensionId: 'com.example.shader',
  contributionId: 'grade.contribution',
};

describe('shader compile diagnostics', () => {
  it('accepts every V1 supported uniform shape without diagnostics', () => {
    expect(validateShaderUniformSchema([
      { name: 'uFloat', label: 'Float', type: 'float', default: 0.5, min: 0, max: 1, step: 0.01 },
      { name: 'uInt', label: 'Int', type: 'int', default: 2 },
      { name: 'uBool', label: 'Bool', type: 'bool', default: true },
      { name: 'uVec2', label: 'Vec2', type: 'vec2', default: [0, 1] },
      { name: 'uVec3', label: 'Vec3', type: 'vec3', default: [0, 1, 2] },
      { name: 'uVec4', label: 'Vec4', type: 'vec4', default: [0, 1, 2, 3] },
      { name: 'uColor', label: 'Color', type: 'color', default: [1, 0.5, 0.25, 1] },
      {
        name: 'uMode',
        label: 'Mode',
        type: 'enum',
        default: 'soft',
        options: [
          { label: 'Soft', value: 'soft' },
          { label: 'Hard', value: 'hard' },
        ],
      },
      {
        name: 'uRef',
        label: 'Ref',
        type: 'textureRef',
        default: { kind: 'static-image-asset', ref: 'asset-1' },
      },
      { name: 'uFrame', label: 'Frame', type: 'frame', default: 12 },
      { name: 'uTime', label: 'Time', type: 'time', default: 1.25 },
    ], CONTEXT)).toEqual([]);
  });

  it('reports stable diagnostics for unsupported uniform schema entries', () => {
    const diagnostics = validateShaderUniformSchema([
      { name: 'uMat4', label: 'Matrix', type: 'mat4', default: [] },
      { name: 'uVec2', label: 'Vec2', type: 'vec2', default: [0, 1, 2] },
      { name: 'uMode', label: 'Mode', type: 'enum', options: [] },
      { name: 'uRef', label: 'Ref', type: 'textureRef', default: { kind: 'external-url' } },
      { name: 'uFloat', label: 'Float', type: 'float', min: '0' },
    ], CONTEXT);

    expect(diagnostics.map((diagnostic) => diagnostic.code)).toEqual([
      SHADER_DIAGNOSTIC_CODES.UNIFORM_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.UNIFORM_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.UNIFORM_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.UNIFORM_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.UNIFORM_UNSUPPORTED,
    ]);
    expect(diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        severity: 'error',
        extensionId: CONTEXT.extensionId,
        contributionId: CONTEXT.contributionId,
        detail: expect.objectContaining({
          shaderId: CONTEXT.shaderId,
          field: 'type',
          uniformName: 'uMat4',
          uniformType: 'mat4',
        }),
      }),
      expect.objectContaining({
        detail: expect.objectContaining({
          field: 'default',
          uniformName: 'uVec2',
          expected: 'a 2-number vector',
        }),
      }),
    ]));
    expect(Object.isFrozen(diagnostics)).toBe(true);
    expect(Object.isFrozen(diagnostics[0].detail)).toBe(true);
  });

  it('accepts every V1 supported texture shape without diagnostics', () => {
    expect(validateShaderTextureSchema([
      {
        name: 'clipFrame',
        label: 'Clip Frame',
        uniform: 'u_clip',
        sourceKind: 'clip-frame',
        required: true,
        colorSpace: 'srgb',
        filter: 'linear',
        wrap: 'clamp-to-edge',
      },
      {
        name: 'staticMatte',
        sourceKind: 'static-image-asset',
        colorSpace: 'linear',
        filter: 'nearest',
        wrap: 'repeat',
      },
      {
        name: 'liveFrame',
        sourceKind: 'live-generated-frame',
        required: false,
        wrap: 'mirrored-repeat',
      },
    ], CONTEXT)).toEqual([]);
  });

  it('reports stable diagnostics for unsupported texture schema entries', () => {
    const diagnostics = validateShaderTextureSchema([
      { name: '', sourceKind: 'clip-frame' },
      { name: 'video', sourceKind: 'video-element' },
      { name: 'matte', sourceKind: 'static-image-asset', filter: 'mipmap', wrap: 'border' },
      { name: 'required', sourceKind: 'clip-frame', required: 'yes' },
    ], CONTEXT);

    expect(diagnostics.map((diagnostic) => diagnostic.code)).toEqual([
      SHADER_DIAGNOSTIC_CODES.TEXTURE_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.TEXTURE_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.TEXTURE_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.TEXTURE_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.TEXTURE_UNSUPPORTED,
    ]);
    expect(diagnostics).toEqual(expect.arrayContaining([
      expect.objectContaining({
        message: expect.stringContaining('texture source kind "video-element" is not supported'),
        detail: expect.objectContaining({
          field: 'sourceKind',
          textureName: 'video',
          sourceKind: 'video-element',
        }),
      }),
      expect.objectContaining({
        detail: expect.objectContaining({
          field: 'filter',
          supportedFilters: ['nearest', 'linear'],
        }),
      }),
    ]));
  });

  it('combines uniform and texture validation diagnostics', () => {
    const diagnostics = validateShaderSchemas({
      uniforms: { not: 'an array' },
      textures: [{ name: 'frame', sourceKind: 'camera-stream' }],
    }, CONTEXT);

    expect(diagnostics.map((diagnostic) => diagnostic.code)).toEqual([
      SHADER_DIAGNOSTIC_CODES.UNIFORM_UNSUPPORTED,
      SHADER_DIAGNOSTIC_CODES.TEXTURE_UNSUPPORTED,
    ]);
  });

  it('parses Chrome and ANGLE-style WebGL info-log line and column ranges', () => {
    const source = [
      'precision mediump float;',
      'uniform sampler2D u_clip;',
      'void main() {',
      '  vec4 c = texture2D(u_clip, vUv);',
      '  gl_FragColor = c',
      '}',
    ].join('\n');
    const diagnostics = parseWebGLInfoLog([
      "ERROR: 0:5: 'assign' : l-value required",
      "WARNING: 0:4(17): 'texture2D' : legacy function",
      "ERROR: 0:3:11: 'vUv' : undeclared identifier",
    ].join('\n'), {
      ...CONTEXT,
      phase: 'fragment',
      source,
    });

    expect(diagnostics).toEqual([
      expect.objectContaining({
        code: SHADER_DIAGNOSTIC_CODES.COMPILE_ERROR,
        severity: 'error',
        message: "'assign' : l-value required",
        sourceRange: { startLine: 5, startCol: 1, endLine: 5, endCol: 2 },
      }),
      expect.objectContaining({
        code: SHADER_DIAGNOSTIC_CODES.COMPILE_ERROR,
        severity: 'warning',
        message: "'texture2D' : legacy function",
        sourceRange: { startLine: 4, startCol: 17, endLine: 4, endCol: 18 },
      }),
      expect.objectContaining({
        detail: expect.objectContaining({
          phase: 'fragment',
          line: 3,
          column: 11,
        }),
        sourceRange: { startLine: 3, startCol: 11, endLine: 3, endCol: 12 },
      }),
    ]);
  });

  it('parses location-first and global link info-log lines', () => {
    const diagnostics = parseWebGLInfoLog([
      '0:8(4): error: syntax error',
      'WARNING: program link succeeded with warnings',
      'Fragment shader is not compiled.',
    ].join('\n'), {
      ...CONTEXT,
      phase: 'link',
    });

    expect(diagnostics).toEqual([
      expect.objectContaining({
        code: SHADER_DIAGNOSTIC_CODES.LINK_ERROR,
        severity: 'error',
        message: 'syntax error',
        sourceRange: { startLine: 8, startCol: 4, endLine: 8, endCol: 5 },
      }),
      expect.objectContaining({
        code: SHADER_DIAGNOSTIC_CODES.LINK_ERROR,
        severity: 'warning',
        message: 'program link succeeded with warnings',
      }),
      expect.objectContaining({
        code: SHADER_DIAGNOSTIC_CODES.LINK_ERROR,
        severity: 'error',
        message: 'Fragment shader is not compiled.',
      }),
    ]);
    expect(diagnostics[1]).not.toHaveProperty('sourceRange');
    expect(diagnostics[2]).not.toHaveProperty('sourceRange');
  });
});
