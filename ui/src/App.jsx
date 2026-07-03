import { useCallback, useEffect, useMemo, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import styles from './App.module.css';
import { v4API } from './api/v4Client';
import TopBar from './components/TopBar';
import { CaptureProvider, useCapture } from './context/CaptureContext';
import { RecallProvider, useRecall } from './context/RecallContext';
import { ReviewProvider, useReview } from './context/ReviewContext';
import { SummaryProvider } from './context/SummaryContext';
import V5EntityList from './views/V5EntityList';
import V5ThreadDetail from './views/V5ThreadDetail';
import V5Threads from './views/V5Threads';
import V5Now from './views/V5Now';
import V5Recall from './views/V5Recall';
import V5RecallOpener from './views/V5RecallOpener';
import V5Memory from './views/V5Memory';
import V5CaptureSheet, { CaptureFab, CaptureToast } from './views/V5CaptureSheet';
import V5AskSheet from './views/V5AskSheet';
import V5ReviewSheet from './views/V5ReviewSheet';

function AppShell() {
  const { toast } = useCapture();
  const { open, openRecall, closeRecall } = useRecall();
  const { open: reviewOpen, openReview, closeReview } = useReview();
  const [counts, setCounts] = useState({
    today: 0,
    threads: undefined,
    recall: undefined,
    suggestions: 0,
  });
  const [trustScore, setTrustScore] = useState(null);
  const [askOpen, setAskOpen] = useState(false);
  const [summaryVersion, setSummaryVersion] = useState(0);

  const refreshSummary = useCallback(() => {
    setSummaryVersion((version) => version + 1);
  }, []);

  const summaryContext = useMemo(() => ({ refreshSummary }), [refreshSummary]);

  useEffect(() => {
    let active = true;

    v4API.summary()
      .then((data) => {
        if (!active) return;
        setCounts({
          today: data?.today_count ?? 0,
          threads: data?.threads_count ?? 0,
          recall: undefined,
          suggestions: data?.suggestions_count ?? 0,
        });
      })
      .catch(() => {
        if (active) {
          setCounts({
            today: 0,
            threads: 0,
            recall: undefined,
            suggestions: 0,
          });
        }
      });

    return () => {
      active = false;
    };
  }, [summaryVersion]);

  useEffect(() => {
    let active = true;

    v4API.metrics.trust()
      .then((data) => {
        if (!active || data?.correction_rate == null) return;
        const score = Math.round((1 - data.correction_rate) * 100);
        setTrustScore(score);
      })
      .catch(() => {
        // Leave the trust chip hidden when the metric is unavailable.
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    function onKeyDown(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        openRecall();
      }
    }

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [openRecall]);

  return (
    <SummaryProvider value={summaryContext}>
      <div className={styles.shell} data-v5="true">
        <TopBar
          onAsk={() => setAskOpen(true)}
          onRecall={openRecall}
          onReview={openReview}
          nowCount={counts.today}
          threadsCount={counts.threads}
          recallCount={counts.recall}
          suggestionsCount={counts.suggestions}
          trustScore={trustScore}
        />

        <div className={styles.mainColumn}>
          <div className={styles.routeViewport}>
            <Routes>
              <Route path="/" element={<Navigate to="/now" replace />} />
              <Route path="/now" element={<V5Now />} />
              <Route path="/threads" element={<V5Threads />} />
              <Route path="/memory" element={<V5Memory />} />
              <Route path="/recall" element={<V5RecallOpener />} />
              <Route path="/entities/:id" element={<V5ThreadDetail />} />
              <Route path="/notes" element={<V5EntityList type="note" />} />
              <Route path="/notes/:id" element={<V5ThreadDetail type="note" />} />
              <Route path="/projects" element={<V5EntityList type="project" />} />
              <Route path="/projects/:id" element={<V5ThreadDetail type="project" />} />
              <Route path="/tasks" element={<V5EntityList type="task" />} />
              <Route path="/tasks/:id" element={<V5ThreadDetail type="task" />} />
              <Route path="/areas" element={<V5EntityList type="area" />} />
              <Route path="/areas/:id" element={<V5ThreadDetail type="area" />} />
              <Route path="/people" element={<V5EntityList type="person" />} />
              <Route path="/people/:id" element={<V5ThreadDetail type="person" />} />
              <Route path="/resources" element={<V5EntityList type="resource" />} />
              <Route path="/resources/:id" element={<V5ThreadDetail type="resource" />} />
              <Route path="*" element={<Navigate to="/now" replace />} />
            </Routes>
          </div>
        </div>

        <CaptureFab />
        <V5CaptureSheet />
        <V5AskSheet open={askOpen} onClose={() => setAskOpen(false)} />
        <CaptureToast toast={toast} onOpenReview={openReview} />
        <V5ReviewSheet open={reviewOpen} onClose={closeReview} />
        <V5Recall open={open} onClose={closeRecall} onAsk={() => setAskOpen(true)} />
      </div>
    </SummaryProvider>
  );
}

function App() {
  return (
    <CaptureProvider>
      <RecallProvider>
        <ReviewProvider>
          <AppShell />
        </ReviewProvider>
      </RecallProvider>
    </CaptureProvider>
  );
}

export default App;
