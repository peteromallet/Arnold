import type { ExtensionDiagnostic, RenderRoute } from '@reigh/editor-sdk';
import { RENDER_ROUTES } from '@reigh/editor-sdk';
import {
  buildUnknownRouteDiagnostic,
  buildUnsupportedRouteDiagnostic,
  type RouteScopeDiagnosticParams,
} from '@/tools/video-editor/runtime/composition/diagnostics.ts';

const CANONICAL_RENDER_ROUTE_SET = new Set<string>(RENDER_ROUTES);

export interface ValidateRenderRouteScopeInput {
  readonly extensionId: string;
  readonly contributionId: string;
  readonly routes?: readonly string[];
  readonly routeMode?: RouteScopeDiagnosticParams['routeMode'];
  readonly missingMessage: string;
  readonly unknownMessage: (route: string) => string;
}

export interface ValidateRenderRouteScopeResult {
  readonly validRoutes: readonly RenderRoute[];
  readonly unknownRoutes: readonly string[];
  readonly diagnostics: readonly ExtensionDiagnostic[];
  readonly missingScope: boolean;
}

export function isCanonicalRenderRoute(route: string | undefined): route is RenderRoute {
  return typeof route === 'string' && CANONICAL_RENDER_ROUTE_SET.has(route);
}

export function canonicalRenderRoutes(routes: readonly string[] | undefined): readonly RenderRoute[] {
  if (!routes?.length) {
    return Object.freeze([]);
  }

  const requested = new Set<string>(routes.filter((route): route is string => typeof route === 'string'));
  return Object.freeze(RENDER_ROUTES.filter((route) => requested.has(route)));
}

export function validateRenderRouteScope(
  input: ValidateRenderRouteScopeInput,
): ValidateRenderRouteScopeResult {
  const routes = input.routes?.filter((route): route is string => typeof route === 'string') ?? [];
  if (input.routeMode === 'missing-routes' || routes.length === 0) {
    return Object.freeze({
      validRoutes: Object.freeze([]),
      unknownRoutes: Object.freeze([]),
      diagnostics: Object.freeze([
        buildUnsupportedRouteDiagnostic({
          extensionId: input.extensionId,
          contributionId: input.contributionId,
          routeMode: input.routeMode ?? 'missing-routes',
          expectedRoutes: RENDER_ROUTES,
          message: input.missingMessage,
        }),
      ]),
      missingScope: true,
    });
  }

  const unknownRoutes = Object.freeze([...new Set(
    routes.filter((route) => !isCanonicalRenderRoute(route)),
  )]);
  const diagnostics = Object.freeze(unknownRoutes.map((route) => buildUnknownRouteDiagnostic({
    extensionId: input.extensionId,
    contributionId: input.contributionId,
    route,
    routeMode: 'unknown',
    expectedRoutes: RENDER_ROUTES,
    message: input.unknownMessage(route),
  })));

  return Object.freeze({
    validRoutes: canonicalRenderRoutes(routes),
    unknownRoutes,
    diagnostics,
    missingScope: false,
  });
}
