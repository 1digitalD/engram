import { useCallback, useEffect, useMemo } from 'react';
import { setAppPathPrefix } from '../legacy/legacyPaths';
import { CaptureProvider, useCapture } from '../context/CaptureContext';
import { ReviewProvider, useReview } from '../context/ReviewContext';
import { SummaryProvider } from '../context/SummaryContext';
import V5CaptureSheet, { CaptureToast } from '../views/V5CaptureSheet';
import V5ReviewSheet from '../views/V5ReviewSheet';

function LegacyCaptureOverlays() {
  const { toast } = useCapture();
  const { open, openReview, closeReview } = useReview();

  return (
    <>
      <V5CaptureSheet />
      <CaptureToast toast={toast} onOpenReview={openReview} />
      <V5ReviewSheet open={open} onClose={closeReview} />
    </>
  );
}

export default function NextLegacyProviders({ children, onSummaryRefresh }) {
  useEffect(() => {
    setAppPathPrefix('');
  }, []);

  const refreshSummary = useCallback(() => {
    onSummaryRefresh?.();
  }, [onSummaryRefresh]);

  const summaryContext = useMemo(() => ({ refreshSummary }), [refreshSummary]);

  return (
    <CaptureProvider>
      <ReviewProvider>
        <SummaryProvider value={summaryContext}>
          {children}
          <LegacyCaptureOverlays />
        </SummaryProvider>
      </ReviewProvider>
    </CaptureProvider>
  );
}
