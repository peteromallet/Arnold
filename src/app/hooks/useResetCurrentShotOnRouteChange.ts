import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useCurrentShot } from '@/shared/state/selectionStore';
import { TOOL_ROUTES } from '@/shared/lib/tooling/toolRoutes';

export function useResetCurrentShotOnRouteChange() {
  const { setCurrentShotId } = useCurrentShot();
  const location = useLocation();
  const prevPathnameRef = useRef(location.pathname);

  useEffect(() => {
    const isNavigatingToShotPage = location.pathname === TOOL_ROUTES.TRAVEL_BETWEEN_IMAGES;
    const wasOnShotPage = prevPathnameRef.current === TOOL_ROUTES.TRAVEL_BETWEEN_IMAGES;

    if (!isNavigatingToShotPage && wasOnShotPage) {
      setCurrentShotId(null);
    }

    prevPathnameRef.current = location.pathname;
  }, [location.pathname, setCurrentShotId]);
}
