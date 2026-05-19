/* eslint-disable no-unused-vars */
import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V4EntityList from './V4EntityList';
import V4EntityDetail from './V4EntityDetail';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      list: vi.fn(),
      create: vi.fn(),
      detail: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
    relationships: {
      create: vi.fn(),
      delete: vi.fn(),
    },
  },
}));

describe('v4 entity screens', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates a task manually from the task list', async () => {
    v4API.entities.list.mockResolvedValue({ data: [] });
    v4API.entities.create.mockResolvedValue({
      data: { id: 't1', type: 'task', title: 'Follow up', status: 'open' },
    });

    render(
      <MemoryRouter>
        <V4EntityList type="task" />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Follow up' } });
    fireEvent.click(screen.getByRole('button', { name: /create task/i }));

    await waitFor(() => {
      expect(v4API.entities.create).toHaveBeenCalledWith({
        type: 'task',
        title: 'Follow up',
        content: null,
      });
    });
    expect(await screen.findByRole('link', { name: /Follow up/i })).toHaveAttribute('href', '/tasks/t1');
  });

  it('updates status and manages relationships from detail sections', async () => {
    const detail = {
      entity: { id: 't1', type: 'task', title: 'Follow up', content: 'Body', status: 'open' },
      sections: [{
        key: 'project',
        title: 'Project',
        items: [{
          entity: { id: 'p1', type: 'project', title: 'Memory Lookup', status: 'active' },
          relationship: { id: 'r1', relationship_type: 'parent' },
        }],
      }],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.update.mockResolvedValue({ data: { ...detail.entity, status: 'done' } });
    v4API.relationships.create.mockResolvedValue({ data: { id: 'r2' } });
    v4API.relationships.delete.mockResolvedValue({ data: { id: 'r1', deleted: true } });

    render(
      <MemoryRouter initialEntries={['/tasks/t1']}>
        <Routes>
          <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Memory Lookup')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'done' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(v4API.entities.update).toHaveBeenCalledWith('t1', {
      title: 'Follow up',
      content: 'Body',
      status: 'done',
    }));

    fireEvent.change(screen.getByLabelText('Target entity ID'), { target: { value: 'p2' } });
    fireEvent.change(screen.getByLabelText('Relationship type'), { target: { value: 'parent' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add link' }));
    await waitFor(() => expect(v4API.relationships.create).toHaveBeenCalledWith('t1', {
      target_entity_id: 'p2',
      relationship_type: 'parent',
    }));

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(v4API.relationships.delete).toHaveBeenCalledWith('r1'));
  });
});
