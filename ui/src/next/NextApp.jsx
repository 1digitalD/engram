import { Navigate, Route, Routes } from 'react-router-dom';
import DossierSurface from './DossierSurface';
import NextShell from './NextShell';
import PeopleSurface from './PeopleSurface';
import ReviewSurface from './ReviewSurface';
import SpacesSurface from './SpacesSurface';
import StreamSurface from './StreamSurface';
import TodaySurface from './TodaySurface';
import WorkboardSurface from './WorkboardSurface';

export default function NextApp() {
  return (
    <Routes>
      <Route element={<NextShell />}>
        <Route index element={<Navigate to="today" replace />} />
        <Route path="today" element={<TodaySurface />} />
        <Route path="workboard" element={<WorkboardSurface />} />
        <Route path="stream" element={<StreamSurface />} />
        <Route path="review" element={<ReviewSurface />} />
        <Route path="spaces" element={<SpacesSurface />} />
        <Route path="spaces/:spaceId" element={<DossierSurface />} />
        <Route path="people" element={<PeopleSurface />} />
        <Route path="people/:personId" element={<PeopleSurface />} />
        <Route path="*" element={<Navigate to="today" replace />} />
      </Route>
    </Routes>
  );
}
