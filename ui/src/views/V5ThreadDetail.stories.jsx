import { MemoryRouter, Route, Routes } from 'react-router-dom';
import V5ThreadDetail from './V5ThreadDetail';
import { fixtureForType, threadDetailFixtures } from './V5ThreadDetail.fixtures';

const meta = {
  title: 'V5/ThreadDetail',
  component: V5ThreadDetail,
  parameters: {
    layout: 'fullscreen',
  },
};

function PreviewStory({ type }) {
  const fixture = fixtureForType(type);
  const path = type === 'person' ? `/people/${fixture.detail.entity.id}` : `/${type}s/${fixture.detail.entity.id}`;
  return (
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path={path}
          element={(
            <V5ThreadDetail
              type={type}
              previewDetail={fixture.detail}
              previewEvents={fixture.events}
              previewCanonical={fixture.canonical}
            />
          )}
        />
      </Routes>
    </MemoryRouter>
  );
}

export default meta;

export const Project = {
  render: () => <PreviewStory type="project" />,
};

export const Person = {
  render: () => <PreviewStory type="person" />,
};

export const Area = {
  render: () => <PreviewStory type="area" />,
};

export const Resource = {
  render: () => <PreviewStory type="resource" />,
};

export const Task = {
  render: () => <PreviewStory type="task" />,
};

export const Note = {
  render: () => <PreviewStory type="note" />,
};

export const MobileProject = {
  parameters: {
    viewport: { defaultViewport: 'mobile1' },
  },
  render: () => <PreviewStory type="project" />,
};

export { threadDetailFixtures };
