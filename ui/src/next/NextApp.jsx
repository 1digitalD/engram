import { Navigate, Route, Routes } from 'react-router-dom';
import NextShell from './NextShell';
import ReviewSurface from './ReviewSurface';

export default function NextApp() {
  return (
    <Routes>
      <Route element={<NextShell />}>
        <Route index element={<Navigate to="review" replace />} />
        <Route path="review" element={<ReviewSurface />} />
        <Route path="*" element={<Navigate to="review" replace />} />
      </Route>
    </Routes>
  );
}
