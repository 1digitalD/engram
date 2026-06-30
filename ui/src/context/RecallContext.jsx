/* eslint-disable react-refresh/only-export-components */
import {
  createContext, useCallback, useContext, useMemo, useState,
} from 'react';

const RecallContext = createContext(null);

export function RecallProvider({ children }) {
  const [open, setOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState('');

  const openRecall = useCallback((query = '') => {
    setInitialQuery(query);
    setOpen(true);
  }, []);

  const closeRecall = useCallback(() => {
    setOpen(false);
    setInitialQuery('');
  }, []);

  const value = useMemo(() => ({
    open,
    initialQuery,
    openRecall,
    closeRecall,
  }), [open, initialQuery, openRecall, closeRecall]);

  return (
    <RecallContext.Provider value={value}>
      {children}
    </RecallContext.Provider>
  );
}

export function useRecall() {
  const ctx = useContext(RecallContext);
  if (!ctx) throw new Error('useRecall must be used within RecallProvider');
  return ctx;
}
