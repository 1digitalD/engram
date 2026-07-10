import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StatusBadge, statusLabel, statusToneClass } from './statusTheme';
import styles from './statusTheme.module.css';

describe('statusTheme', () => {
  it('maps task and space statuses to labels and tone classes', () => {
    expect(statusLabel('in_progress')).toBe('In progress');
    expect(statusToneClass('blocked')).toBe(styles.toneBlocked);
    expect(statusToneClass('on_hold')).toBe(styles.toneOnHold);
  });

  it('renders a color-coded badge', () => {
    render(<StatusBadge status="waiting" />);
    expect(screen.getByText('Waiting')).toBeInTheDocument();
  });
});
