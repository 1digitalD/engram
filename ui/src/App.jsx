import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import LegacyApp from './legacy/LegacyApp';
import NextApp from './next/NextApp';

function NextRedirect() {
  const location = useLocation();
  const target = location.pathname.replace(/^\/next/, '') || '/';
  return <Navigate to={`${target}${location.search}${location.hash}`} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/legacy/*" element={<LegacyApp />} />
      <Route path="/next/*" element={<NextRedirect />} />
      <Route path="/*" element={<NextApp />} />
    </Routes>
  );
}
