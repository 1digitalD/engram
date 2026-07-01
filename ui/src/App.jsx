import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import styles from './App.module.css';
import { v4API } from './api/v4Client';
import V5EntityList from './views/V5EntityList';
import V5ThreadDetail from './views/V5ThreadDetail';
import V5Threads from './views/V5Threads';
import V5Now from './views/V5Now';
import V5Recall from './views/V5Recall';
import V5RecallOpener from './views/V5RecallOpener';
import V5Memory from './views/V5Memory';
import TopBar from './components/TopBar';
import { CaptureProvider, useCapture } from './context/CaptureContext';
import { RecallProvider, useRecall } from './context/RecallContext';
import V5CaptureSheet, { CaptureFab, CaptureToast } from './views/V5CaptureSheet';
import V5AskSheet from './views/V5AskSheet';

function AppShell() {
  const location = useLocation();
  const { toast } = useCapture();
  const { open, openRecall, closeRecall } = useRecall();
  const [counts, setCounts] = useState({ today: 0, threads: 0, recall: 0 });
  const [trustScore, setTrustScore] = useState(null);
  const [askOpen, setAskOpen] = useState(false);

  // Fetch lens counts once on mount; data doesn't change between
  // navigations, so re-fetching on every route change is wasted work.
  // (Was previously keyed on location.pathname; see audit B-015.)
  useEffect(() => {
    let active = true;
    v4API.summary()
      .then((data) => {
        if (!active) return;
        // /summary doesn't expose threads_count or recall_count; keep
        // them at 0 rather than silently falling back to today_count.
        setCounts({
          today: data?.today_count ?? 0,
          threads: 0,
          recall: 0,
        });
      })
      .catch(() => {
        if (active) setCounts({ today: 0, threads: 0, recall: 0 });
      });
    return () => { active = false; };
  }, []);

  // Trust score derived from /metrics/trust's correction_rate:
  // trust = (1 - correction_rate) * 100, rounded. Until the API exposes
  // a dedicated trust_score, this gives a value the user can actually
  // trust. (Was hard-coded to 87; see audit B-009.)
  useEffect(() => {
    let active = true;
    v4API.metrics.trust()
      .then((data) => {
        if (!active || data?.correction_rate == null) return;
        const score = Math.round((1 - data.correction_rate) * 100);
        setTrustScore(score);
      })
      .catch(() => {
        // Silent fallback — leave the chip hidden rather than show 87%
        // (or some other arbitrary number) when we can't compute it.
      });
    return () => { active = false; };
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
    <div className={styles.shell} data-v5="true">
      <TopBar
        onAsk={() => setAskOpen(true)}
        onRecall={openRecall}
        nowCount={counts.today}
        threadsCount={counts.threads}
        recallCount={counts.recall}
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
      <CaptureToast toast={toast} />
      <V5Recall open={open} onClose={closeRecall} />
    </div>
  );
}

function App() {
  return (
    <CaptureProvider>
      <RecallProvider>
        <AppShell />
      </RecallProvider>
    </CaptureProvider>
  );
}

export default App;
