import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LinkToEntity from './LinkToEntity';
import { linksAPI, linkTypesAPI } from '../../api/engram';
import useStore from '../../stores/useStore';

vi.mock('../../api/engram', () => ({
  linksAPI: { create: vi.fn() },
  linkTypesAPI: { forPair: vi.fn() },
}));
vi.mock('../../stores/useStore');

const baseStore = {
  notes: [{ id: 'note-1', raw_text: '# Test Note', type: 'note' }],
  tasks: [{ id: 'task-1', title: 'Test Task', type: 'task' }],
  projects: [{ id: 'proj-1', title: 'Test Project', type: 'project' }],
  areas: [],
  people: [],
  resources: [],
  addToast: vi.fn(),
};

function renderLinkToEntity(props = {}) {
  return render(
    <LinkToEntity entityId="entity-1" entityType="note" onLinkCreated={vi.fn()} {...props} />
  );
}

describe('LinkToEntity', () => {
  beforeEach(() => {
    vi.mocked(linksAPI.create).mockReset();
    vi.mocked(linkTypesAPI.forPair).mockReset();
    vi.mocked(useStore).mockReset();
    vi.mocked(useStore).mockReturnValue(baseStore);
  });

  it('renders the search input and dropdowns', () => {
    renderLinkToEntity();
    expect(screen.getByPlaceholderText('Filter entities...')).toBeInTheDocument();
    expect(screen.getByText('Select target...')).toBeInTheDocument();
    expect(screen.getByText('Select target first')).toBeInTheDocument();
  });

  it('shows link type options filtered by allowlist when target is selected', async () => {
    vi.mocked(linkTypesAPI.forPair).mockResolvedValue({
      data: [
        { link_type: 'parent', inverse: 'child' },
        { link_type: 'related', inverse: 'related' },
      ],
    });

    renderLinkToEntity();

    const searchInput = screen.getByPlaceholderText('Filter entities...');
    const selects = screen.getAllByRole('combobox');

    await userEvent.type(searchInput, 'Test');
    await userEvent.selectOptions(selects[0], 'task-1');

    const linkTypeSelect = selects[1];
    await waitFor(() => {
      expect(within(linkTypeSelect).getByText('Parent')).toBeInTheDocument();
      expect(within(linkTypeSelect).getByText('Related')).toBeInTheDocument();
    });
  });

  it('shows loading state while fetching link types', async () => {
    vi.mocked(linkTypesAPI.forPair).mockReturnValue(new Promise(() => {}));

    renderLinkToEntity();

    await userEvent.type(screen.getByPlaceholderText('Filter entities...'), 'Test');
    await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'task-1');

    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('shows disabled state when no link types are allowed', async () => {
    vi.mocked(linkTypesAPI.forPair).mockResolvedValue({ data: [] });

    renderLinkToEntity();

    await userEvent.type(screen.getByPlaceholderText('Filter entities...'), 'Test');
    await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'task-1');

    await waitFor(() => {
      expect(screen.getByText('No allowed link types')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Link' })).toBeDisabled();
  });

  it('calls linksAPI.create on submit', async () => {
    vi.mocked(linkTypesAPI.forPair).mockResolvedValue({
      data: [{ link_type: 'related', inverse: 'related' }],
    });
    vi.mocked(linksAPI.create).mockResolvedValue({});

    const onLinkCreated = vi.fn();
    renderLinkToEntity({ onLinkCreated });

    await userEvent.type(screen.getByPlaceholderText('Filter entities...'), 'Test');
    await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'task-1');

    await waitFor(() => {
      expect(screen.getByText('Related')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole('button', { name: 'Link' }));

    await waitFor(() => {
      expect(linksAPI.create).toHaveBeenCalledWith({
        src_id: 'entity-1',
        dst_id: 'task-1',
        link_type: 'related',
      });
    });
  });
});
