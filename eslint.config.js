import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";
import { dialogEarlyReturnRestrictedSyntax } from "./eslint-rules/dialogEarlyReturnRule.js";
import { strictLintDebtFiles } from "./eslint.strict-debt.js";
import { supabaseFacadeAllowlist } from "./eslint.supabase-facade-allowlist.js";
import { sharedLayerAllowlist } from "./eslint.shared-layer-allowlist.js";

const strictRefreshFiles = [
  "src/app/**/*.{ts,tsx}",
  "src/integrations/supabase/bootstrap/**/*.{ts,tsx}",
  "src/shared/lib/debugPolling.ts",
  "src/shared/lib/mobileProjectDebug.ts",
  "src/shared/components/MediaGallery/hooks/useMediaGalleryDebugTools.ts",
  "src/shared/components/MediaLightbox/hooks/useVideoLightboxEnvironment.ts",
  "src/shared/components/MediaLightbox/hooks/useVideoLightboxRenderModel.tsx",
  "src/tools/travel-between-images/components/ShotImagesEditor/hooks/useShotImagesEditorCallbacks.ts",
  "src/tools/travel-between-images/components/ShotImagesEditor/hooks/useShotImagesEditorModel.ts",
];

export default tseslint.config(
  { ignores: ["dist", "eslint-rules/__fixtures__/**", "vendor/**"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-hooks/exhaustive-deps": "error",
      "react-refresh/only-export-components": [
        "off",
        { allowConstantExport: true },
      ],
      "@typescript-eslint/no-unused-vars": ["error", {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "^_",
        ignoreRestSiblings: true,
      }],
      "no-restricted-syntax": ["error", dialogEarlyReturnRestrictedSyntax],
    },
  },
  {
    files: strictRefreshFiles,
    rules: {
      "react-refresh/only-export-components": [
        "error",
        { allowConstantExport: true },
      ],
    },
  },
  // Temporary strict-lint debt allowlist.
  // Rails are enabled globally, and only known legacy violations are allowlisted.
  // Keep this list shrinking over time; new violations outside this list fail lint.
  ...(strictLintDebtFiles.length > 0
    ? [{
      files: strictLintDebtFiles,
      rules: {
        "react-hooks/exhaustive-deps": "off",
        "@typescript-eslint/no-unused-vars": "off",
      },
    }]
    : []),
  // Utility boundary rule: keep URL + file-conversion helpers in their dedicated modules.
  // Avoid importing these from shared/lib/utils (which now only hosts generic helpers).
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": ["error", {
        paths: [
          {
            name: "@/shared/lib/utils",
            importNames: ["dataURLtoFile", "getDisplayUrl", "stripQueryParameters"],
            message: "Import dataURLtoFile from '@/shared/lib/fileConversion' and URL helpers from '@/shared/lib/mediaUrl'.",
          },
          {
            name: "./utils",
            importNames: ["dataURLtoFile", "getDisplayUrl", "stripQueryParameters"],
            message: "Import dataURLtoFile from '@/shared/lib/fileConversion' and URL helpers from '@/shared/lib/mediaUrl'.",
          },
          {
            name: "../utils",
            importNames: ["dataURLtoFile", "getDisplayUrl", "stripQueryParameters"],
            message: "Import dataURLtoFile from '@/shared/lib/fileConversion' and URL helpers from '@/shared/lib/mediaUrl'.",
          },
        ],
      }],
    },
  },
  // Architectural rule: shared/ should not import from tools/
  // This prevents coupling between the shared layer and tool-specific code.
  // Existing exceptions are documented in tasks/2026-02-02-shared-tools-cleanup.md
  {
    files: ["src/shared/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": ["error", {
        paths: [
          {
            name: "@/shared/lib/utils",
            importNames: ["dataURLtoFile", "getDisplayUrl", "stripQueryParameters"],
            message: "Import dataURLtoFile from '@/shared/lib/fileConversion' and URL helpers from '@/shared/lib/mediaUrl'.",
          },
          {
            name: "./utils",
            importNames: ["dataURLtoFile", "getDisplayUrl", "stripQueryParameters"],
            message: "Import dataURLtoFile from '@/shared/lib/fileConversion' and URL helpers from '@/shared/lib/mediaUrl'.",
          },
          {
            name: "../utils",
            importNames: ["dataURLtoFile", "getDisplayUrl", "stripQueryParameters"],
            message: "Import dataURLtoFile from '@/shared/lib/fileConversion' and URL helpers from '@/shared/lib/mediaUrl'.",
          },
        ],
        patterns: [{
          group: ["@/tools/*", "**/tools/*"],
          message: "shared/ cannot import from tools/. Move the type/utility to shared/, or move the component to tools/. See tasks/2026-02-02-shared-tools-cleanup.md for documented exceptions."
        }],
      }]
    }
  },
  // Shared-layer dependency boundary:
  // shared/ should not take direct dependencies on feature/domain layers.
  // Existing legacy imports are temporarily tracked in a dedicated allowlist.
  {
    files: ["src/shared/**/*.{ts,tsx}"],
    ignores: [
      "src/shared/**/__tests__/**/*.{ts,tsx}",
      "src/shared/**/*.test.ts",
      "src/shared/**/*.test.tsx",
      ...sharedLayerAllowlist,
    ],
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [{
          group: ["@/features/*", "@/domains/*"],
          message: "shared/ is a foundational layer. Move feature/domain-aware logic into features/domains (or app composition), and keep shared consuming boundary-neutral contracts.",
        }],
      }],
    },
  },
  // Supabase facade boundary: block direct facade imports globally.
  // Existing legacy callsites are temporarily tracked in a dedicated allowlist file.
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: [
      "src/integrations/supabase/**/*.{ts,tsx}",
      "src/**/__tests__/**/*.{ts,tsx}",
      "src/**/*.test.ts",
      "src/**/*.test.tsx",
      ...supabaseFacadeAllowlist,
    ],
    rules: {
      "no-restricted-imports": ["error", {
        paths: [{
          name: "@/integrations/supabase/client",
          message: "Use integration repositories/gateways under '@/integrations/supabase/repositories/*'. If migration is temporarily blocked, add the file path to eslint.supabase-facade-allowlist.js with a cleanup task.",
        }],
      }],
    },
  },
  // Supabase runtime boundary for high-churn modules.
  // These callsites should consume integration repositories/gateways, not the global client facade.
  {
    files: [
      "src/shared/realtime/RealtimeConnection.ts",
      "src/shared/hooks/useToolSettings.ts",
      "src/domains/generation/hooks/useGenerationMutations.ts",
    ],
    rules: {
      "no-restricted-imports": ["error", {
        paths: [{
          name: "@/integrations/supabase/client",
          message: "Use an integration repository/gateway under '@/integrations/supabase/repositories/*' instead of importing the global Supabase client facade directly.",
        }],
      }],
    },
  },
  // Domain boundary: domain modules should consume integration repositories,
  // not the global Supabase client facade directly.
  {
    files: ["src/domains/**/*.{ts,tsx}"],
    ignores: ["src/domains/**/*.test.ts", "src/domains/**/*.test.tsx"],
    rules: {
      "no-restricted-imports": ["error", {
        paths: [{
          name: "@/integrations/supabase/client",
          message: "Use an integration repository under '@/integrations/supabase/repositories/*' instead of importing the global Supabase client facade directly.",
        }],
      }],
    },
  }
);
