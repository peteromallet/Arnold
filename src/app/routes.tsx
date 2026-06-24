import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
const HomePage = lazy(() => import('@/pages/Home/HomePage'));
import ArtPage from '@/pages/ArtPage';
import PaymentSuccessPage from '@/pages/PaymentSuccessPage';
import PaymentCancelPage from '@/pages/PaymentCancelPage';
import SharePage from '@/pages/SharePage';

// Main tools: eagerly loaded because lazy() caused blank screens on Safari mobile
// (dynamic import race with TanStack Query hydration — query cache not ready when component mounts)
import ImageGenerationToolPage from '@/tools/image-generation/pages/ImageGenerationToolPage';
import VideoTravelToolPage from '@/tools/travel-between-images/pages/VideoTravelToolPage';
import CharacterAnimatePage from '@/tools/character-animate/pages/CharacterAnimatePage';
import JoinClipsPage from '@/tools/join-clips/pages/JoinClipsPage';
import EditVideoPage from '@/tools/edit-video/pages/EditVideoPage';
import VideoEditorPage from '@/tools/video-editor/pages/VideoEditorPage';
// Dev-only test harness route for extension activity region and manager states
const ExtensionHarnessPage = import.meta.env.DEV
  ? lazy(() => import('@/tools/video-editor/pages/ExtensionHarnessPage'))
  : null;
// Secondary tools: lazy-loaded (not default landing pages, so hydration race is less likely)
const EditImagesPage = lazy(() => import('@/tools/edit-images/pages/EditImagesPage'));
const TrainingDataHelperPage = lazy(() => import('@/tools/training-data-helper/pages/TrainingDataHelperPage'));
const BlogListPage = lazy(() => import('@/pages/Blog/BlogListPage'));
const BlogPostPage = lazy(() => import('@/pages/Blog/BlogPostPage'));
import NotFoundPage from '@/pages/NotFoundPage';
import ShotsPage from '@/pages/ShotsPage';
import { Layout } from './Layout';
import { DefaultToolRedirect } from './DefaultToolRedirect';
import { AppEnv } from '@/types/env';
import { ReighLoading } from '@/shared/components/ReighLoading';
import { ToolErrorBoundary } from '@/shared/components/ToolErrorBoundary';
import { probeStoredSessionToken } from '@/shared/lib/supabaseSession';
import { normalizeAndPresentError } from '@/shared/lib/errorHandling/runtimeError';

// Determine the environment
const currentEnv = (import.meta.env.VITE_APP_ENV?.toLowerCase() || AppEnv.WEB);

// Loading fallback component for lazy loaded pages
const LazyLoadingFallback = () => (
  <ReighLoading />
);

function HomeWithAuthRedirect() {
  const storedSessionProbe = probeStoredSessionToken();
  if (!storedSessionProbe.ok) {
    normalizeAndPresentError(storedSessionProbe.error, {
      context: 'routes.authRedirect.storageProbe',
      showToast: false,
      logData: {
        errorCode: storedSessionProbe.errorCode,
        recoverable: storedSessionProbe.recoverable,
        policy: storedSessionProbe.policy,
      },
    });
    return (
      <Suspense fallback={<LazyLoadingFallback />}>
        <HomePage />
      </Suspense>
    );
  }

  if (storedSessionProbe.value) {
    return <Navigate to='/tools' replace />;
  }

  return (
    <Suspense fallback={<LazyLoadingFallback />}>
      <HomePage />
    </Suspense>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      {currentEnv === AppEnv.WEB ? (
        <Route path="/" element={<HomeWithAuthRedirect />} />
      ) : null}

      <Route
        path="/home"
        element={(
          <Suspense fallback={<LazyLoadingFallback />}>
            <HomePage />
          </Suspense>
        )}
      />

      <Route path="/payments/success" element={<PaymentSuccessPage />} />
      <Route path="/payments/cancel" element={<PaymentCancelPage />} />
      <Route path="/share/:shareId" element={<SharePage />} />
      <Route
        path="/blog"
        element={(
          <Suspense fallback={<LazyLoadingFallback />}>
            <BlogListPage />
          </Suspense>
        )}
      />
      <Route
        path="/blog/:slug"
        element={(
          <Suspense fallback={<LazyLoadingFallback />}>
            <BlogPostPage />
          </Suspense>
        )}
      />

      <Route element={<Layout />}>
        {currentEnv !== AppEnv.WEB ? (
          <Route path="/" element={<DefaultToolRedirect />} />
        ) : null}
        <Route path="/tools" element={<DefaultToolRedirect />} />
        <Route
          path="/tools/image-generation"
          element={<ToolErrorBoundary toolName="Image Generation"><ImageGenerationToolPage /></ToolErrorBoundary>}
        />
        <Route
          path="/tools/travel-between-images"
          element={<ToolErrorBoundary toolName="Video Travel"><VideoTravelToolPage /></ToolErrorBoundary>}
        />
        <Route
          path="/tools/character-animate"
          element={<ToolErrorBoundary toolName="Character Animate"><CharacterAnimatePage /></ToolErrorBoundary>}
        />
        <Route
          path="/tools/join-clips"
          element={<ToolErrorBoundary toolName="Join Clips"><JoinClipsPage /></ToolErrorBoundary>}
        />
        <Route
          path="/tools/edit-images"
          element={(
            <ToolErrorBoundary toolName="Edit Images">
              <Suspense fallback={<LazyLoadingFallback />}>
                <EditImagesPage />
              </Suspense>
            </ToolErrorBoundary>
          )}
        />
        <Route
          path="/tools/edit-video"
          element={<ToolErrorBoundary toolName="Edit Video"><EditVideoPage /></ToolErrorBoundary>}
        />
        <Route
          path="/tools/video-editor"
          element={<ToolErrorBoundary toolName="Video Editor"><VideoEditorPage /></ToolErrorBoundary>}
        />
        {import.meta.env.DEV && ExtensionHarnessPage ? (
          <Route
            path="/tools/video-editor/harness"
            element={<ToolErrorBoundary toolName="Extension Harness"><ExtensionHarnessPage /></ToolErrorBoundary>}
          />
        ) : null}
        <Route
          path="/tools/training-data-helper"
          element={(
            <ToolErrorBoundary toolName="Training Data Helper">
              <Suspense fallback={<LazyLoadingFallback />}>
                <TrainingDataHelperPage />
              </Suspense>
            </ToolErrorBoundary>
          )}
        />
        <Route path="/shots" element={<ShotsPage />} />
        <Route path="/art" element={<ArtPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
