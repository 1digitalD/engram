import { MemoryRouter } from 'react-router-dom';
import TopBar from './TopBar';

const meta = {
  title: 'V5/TopBar',
  component: TopBar,
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

export const Default = {
  args: {
    trustScore: 87,
    nowCount: 3,
    threadsCount: 7,
    onAsk: () => {},
  },
};

export const ThemeDark = {
  parameters: {
    backgrounds: { default: 'dark' },
  },
  args: {
    trustScore: 87,
    nowCount: 3,
    threadsCount: 7,
    onAsk: () => {},
  },
  decorators: [
    (Story) => {
      document.documentElement.dataset.theme = 'dark';
      return <Story />;
    },
  ],
};

export const TrustLow = {
  args: {
    trustScore: 42,
    nowCount: 1,
    threadsCount: 2,
    onAsk: () => {},
  },
};

export const Mobile = {
  parameters: {
    viewport: { defaultViewport: 'mobile1' },
  },
  args: {
    trustScore: 87,
    nowCount: 3,
    threadsCount: 7,
    onAsk: () => {},
  },
};
