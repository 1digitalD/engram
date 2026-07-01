import { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useRecall } from '../context/RecallContext';

export default function V5RecallOpener() {
  const { openRecall } = useRecall();
  const location = useLocation();

  useEffect(() => {
    openRecall();
  }, [openRecall]);

  // Replace the brittle history shim with a route-safe redirect.
  // If a background location was provided (e.g. in-app navigation), return
  // there; otherwise fall back to the default lens so direct /recall loads
  // and refreshes are predictable and never rely on browser history length.
  const target = location.state?.backgroundLocation ?? { pathname: '/now' };
  return <Navigate to={target} replace />;
}
