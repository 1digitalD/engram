import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import CommitmentDetailSurface from './CommitmentDetailSurface';
import DossierSurface from './DossierSurface';
import NextShell from './NextShell';
import PeopleSurface from './PeopleSurface';
import ReviewSurface from './ReviewSurface';
import SpacesSurface from './SpacesSurface';
import StreamSurface from './StreamSurface';
import TasksSurface from './TasksSurface';
import TodaySurface from './TodaySurface';
import WorkboardSurface from './WorkboardSurface';
import V5EntityList from '../views/V5EntityList';
import V5ThreadDetail from '../views/V5ThreadDetail';

const BROWSE_ROUTES = [
  { list: 'notes', detailType: 'note' },
  { list: 'projects', detailType: 'project' },
  { list: 'areas', detailType: 'area' },
  { list: 'resources', detailType: 'resource' },
];

function TaskDetailRedirect() {
  const { id } = useParams();
  return <Navigate to={`/commitments/${id}`} replace />;
}

export default function NextApp() {
  return (
    <Routes>
      <Route element={<NextShell />}>
          <Route index element={<Navigate to="today" replace />} />
          <Route path="today" element={<TodaySurface />} />
          <Route path="commitments/:taskId" element={<CommitmentDetailSurface />} />
          <Route path="workboard" element={<WorkboardSurface />} />
          <Route path="tasks" element={<TasksSurface />} />
          <Route path="tasks/:id" element={<TaskDetailRedirect />} />
          <Route path="stream" element={<StreamSurface />} />
          <Route path="review" element={<ReviewSurface />} />
          <Route path="spaces" element={<SpacesSurface />} />
          <Route path="spaces/:spaceId" element={<DossierSurface />} />
          <Route path="people" element={<PeopleSurface />} />
          <Route path="people/:personId" element={<PeopleSurface />} />
          {BROWSE_ROUTES.map(({ list, detailType }) => (
            <Route key={list} path={list} element={<V5EntityList type={detailType} />} />
          ))}
          {BROWSE_ROUTES.map(({ list, detailType }) => (
            <Route
              key={`${list}-detail`}
              path={`${list}/:id`}
              element={<V5ThreadDetail type={detailType} />}
            />
          ))}
          <Route path="*" element={<Navigate to="today" replace />} />
      </Route>
    </Routes>
  );
}
