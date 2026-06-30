import { MemoryRouter } from 'react-router-dom';
import V5Now from './V5Now';
import { MOCKED_NOW_DATA } from './V5Now.fixtures';

const meta = {
  title: 'V5/Now',
  component: V5Now,
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <MemoryRouter initialEntries={['/now']}>
        <Story />
      </MemoryRouter>
    ),
  ],
};

export default meta;

const sectionData = (section) => ({
  needs_you_now: section === 'needs_you_now' ? MOCKED_NOW_DATA.needs_you_now : [],
  waiting_on_you: section === 'waiting_on_you' ? MOCKED_NOW_DATA.waiting_on_you : [],
  ambient: section === 'ambient' ? MOCKED_NOW_DATA.ambient : [],
});

export const NeedsYouNow = {
  args: {
    previewData: sectionData('needs_you_now'),
  },
};

export const WaitingOnYou = {
  args: {
    previewData: sectionData('waiting_on_you'),
  },
};

export const Ambient = {
  args: {
    previewData: sectionData('ambient'),
  },
};

export const Full = {
  args: {
    previewData: MOCKED_NOW_DATA,
  },
};

export const MobileFull = {
  parameters: {
    viewport: { defaultViewport: 'mobile1' },
  },
  args: {
    previewData: MOCKED_NOW_DATA,
  },
};
