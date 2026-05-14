import React, { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import ErrorBoundary from './components/ErrorBoundary';
import styles from './App.module.css';
import Dashboard from './views/Dashboard';
import Today from './views/Today';
import Inbox from './views/Inbox';
import Notes from './views/Notes';
import NoteDetailView from './views/NoteDetailView';
import Projects from './views/Projects';
import ProjectFocus from './views/ProjectFocus';
import Areas from './views/Areas';
import AreaFocus from './views/AreaFocus';
import Resources from './views/Resources';
import ResourceDetail from './views/ResourceDetail';
import People from './views/People';
import PersonFocus from './views/PersonFocus';
import Tasks from './views/Tasks';
import TaskDetail from './views/TaskDetail';
import Review from './views/Review';
import Tags from './views/Tags';
import Toast from './components/ui/Toast';
import useStore from './stores/useStore';

export default function App() {
  const { loadAll, toasts, removeToast } = useStore();

  useEffect(() => {
    loadAll();
  }, []);

  return (
    <ErrorBoundary>
      <AppShell>
        <Routes>
          <Route path="/"                element={<Dashboard />} />
          <Route path="/today"           element={<Today />} />
          <Route path="/inbox"           element={<Inbox />} />
          <Route path="/notes"           element={<Notes />} />
          <Route path="/notes/:id"       element={<NoteDetailView />} />
          <Route path="/projects"        element={<Projects />} />
          <Route path="/projects/:id"    element={<ProjectFocus />} />
          <Route path="/areas"           element={<Areas />} />
          <Route path="/areas/:id"       element={<AreaFocus />} />
          <Route path="/resources"       element={<Resources />} />
          <Route path="/resources/:id"  element={<ResourceDetail />} />
          <Route path="/tags"            element={<Tags />} />
          <Route path="/people"          element={<People />} />
          <Route path="/people/:id"      element={<PersonFocus />} />
          <Route path="/tasks"           element={<Tasks />} />
          <Route path="/tasks/:id"      element={<TaskDetail />} />
          <Route path="/review"          element={<Review />} />
          <Route path="*"               element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>

      {/* Toast stack */}
      <div className={styles.toastStack}>
        {toasts.map(t => (
          <Toast key={t.id} toast={t} onDismiss={() => removeToast(t.id)} />
        ))}
      </div>
    </ErrorBoundary>
  );
}
