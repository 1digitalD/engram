import {
  createContext, useCallback, useContext, useMemo, useState,
} from 'react';

const ReviewContext = createContext(null);

export function ReviewProvider({ children }) {
  const [open, setOpen] = useState(false);

  const openReview = useCallback(() => {
    setOpen(true);
  }, []);

  const closeReview = useCallback(() => {
    setOpen(false);
  }, []);

  const value = useMemo(() => ({
    open,
    openReview,
    closeReview,
  }), [open, openReview, closeReview]);

  return (
    <ReviewContext.Provider value={value}>
      {children}
    </ReviewContext.Provider>
  );
}

export function useReview() {
  const ctx = useContext(ReviewContext);
  if (!ctx) throw new Error('useReview must be used within ReviewProvider');
  return ctx;
}
