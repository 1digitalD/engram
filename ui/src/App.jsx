import React, { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import Dashboard from './views/Dashboard';
import Inbox from './views/Inbox';
import Notes from './views/Notes';
import NoteDetailView from './views/NoteDetailView';
import Projects from './views/Projects';
import ProjectFocus from './views/ProjectFocus';
import Areas from './views/Areas';
import AreaFocus from './views/AreaFocus';
import People from './views/People';
import Tasks from './views/Tasks';
import Graph from './views/Graph';
import Review from './views/Review';
import Toast from './components/ui/Toast';
import useStore from './stores/useStore';

export default function App() {
  const { loadAll, toasts, removeToast } = useStore();

  useEffect(() => {
    loadAll();
  }, []);

  return (
    <>
      <AppShell>
        <Routes>
          <Route path="/"                element={<Dashboard />} />
          <Route path="/inbox"           element={<Inbox />} />
          <Route path="/notes"           element={<Notes />} />
          <Route path="/notes/:id"       element={<NoteDetailView />} />
          <Route path="/projects"        element={<Projects />} />
          <Route path="/projects/:id"    element={<ProjectFocus />} />
          <Route path="/areas"           element={<Areas />} />
          <Route path="/areas/:id"       element={<AreaFocus />} />
          <Route path="/people"          element={<People />} />
          <Route path="/tasks"           element={<Tasks />} />
          <Route path="/graph"           element={<Graph />} />
          <Route path="/review"          element={<Review />} />
          <Route path="*"               element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>

      {/* Toast stack */}
      <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {toasts.map(t => (
          <Toast key={t.id} toast={t} onDismiss={() => removeToast(t.id)} />
        ))}
      </div>
    </>
  );
}
