import { Navigate, Route, Routes } from 'react-router-dom';
import NextShell from './NextShell';
import ReviewSurface from './ReviewSurface';
import WorkboardSurface from './WorkboardSurface';

export default function NextApp() {
  return (
    <Routes>
      <Route element={<NextShell />}>
        <Route index element={<Navigate to="review" replace />} />
        <Route path="workboard" element={<WorkboardSurface />} />
        <Route path="review" element={<ReviewSurface />} />
        <Route path="*" element={<Navigate to="review" replace />} />
      </Route>
    </Routes>
  );
}
