import { useLocation, useSearchParams } from 'react-router-dom';

const VIDEO_EDITOR_ROUTE = '/tools/video-editor';

export function isVideoEditorRoute(pathname: string): boolean {
  return pathname === VIDEO_EDITOR_ROUTE || pathname.startsWith(`${VIDEO_EDITOR_ROUTE}/`);
}

export function useVideoEditorRouteState() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const timelineId = searchParams.get('timeline');
  const isEditorRoute = isVideoEditorRoute(pathname);
  const isVideoEditorShellActive = isEditorRoute && Boolean(timelineId);

  return {
    isEditorRoute,
    timelineId,
    isVideoEditorShellActive,
  };
}
