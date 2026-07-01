import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';

const CaptureContext = createContext(null);

const THREAD_ROUTE = /^\/(projects|people|tasks|areas|resources|notes|entities)\/([^/]+)/;

const ROUTE_ENTITY_TYPES = {
  projects: 'project',
  people: 'person',
  tasks: 'task',
  areas: 'area',
  resources: 'resource',
  notes: 'note',
  entities: 'entity',
};

export function threadFromPathname(pathname) {
  const match = pathname.match(THREAD_ROUTE);
  if (!match) return null;
  const segment = match[1];
  return {
    id: match[2],
    type: ROUTE_ENTITY_TYPES[segment] || segment,
    routeType: segment,
  };
}

export function CaptureProvider({ children }) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [initialContent, setInitialContent] = useState('');

  const defaultAttachment = useMemo(
    () => threadFromPathname(location.pathname),
    [location.pathname],
  );

  const openCapture = useCallback((content) => {
    const safeContent = typeof content === 'string' ? content : '';
    setInitialContent(safeContent);
    setOpen(true);
  }, []);
  const closeCapture = useCallback(() => {
    setOpen(false);
    setInitialContent('');
  }, []);

  const showToast = useCallback((payload) => {
    setToast(payload);
    window.setTimeout(() => setToast(null), 1500);
  }, []);

  const value = useMemo(() => ({
    open,
    setOpen,
    openCapture,
    closeCapture,
    defaultAttachment,
    initialContent,
    toast,
    showToast,
  }), [open, openCapture, closeCapture, defaultAttachment, initialContent, toast, showToast]);

  return (
    <CaptureContext.Provider value={value}>
      {children}
    </CaptureContext.Provider>
  );
}

export function useCapture() {
  const ctx = useContext(CaptureContext);
  if (!ctx) throw new Error('useCapture must be used within CaptureProvider');
  return ctx;
}
