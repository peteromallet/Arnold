export {
  SHADER_DIAGNOSTIC_CODES,
  parseWebGLInfoLog,
  validateShaderSchemas,
  validateShaderTextureSchema,
  validateShaderUniformSchema,
  type ShaderCompileDiagnosticPhase,
  type ShaderDiagnostic,
  type ShaderDiagnosticCode,
  type ShaderValidationContext,
  type WebGLInfoLogParseOptions,
} from './diagnostics.ts';

export {
  compileWebGLShaderProgram,
  type WebGLCanvasFactory,
  type WebGLShaderCompileInput,
  type WebGLShaderCompileResult,
  type WebGLShaderCompileStatus,
} from './webgl-adapter.ts';
