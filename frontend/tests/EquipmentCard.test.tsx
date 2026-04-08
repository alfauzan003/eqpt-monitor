import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EquipmentCard } from '../src/components/EquipmentCard';
import type { Equipment } from '../src/types';

const base: Equipment = {
  id: 'FORM-01',
  name: 'Formation Cycler #1',
  type: 'formation_cycler',
  location: 'Line-A / Bay-1',
  status: 'running',
  current_batch_id: 'B-1',
  current_unit_id: 'CELL-2026-04-05-0001',
  unit_started_at: '2026-04-05T12:00:00Z',
  latest_metrics: { temperature: 45.2, voltage: 3.72 },
  updated_at: '2026-04-05T12:00:01Z',
};

describe('EquipmentCard', () => {
  it('renders name and status', () => {
    render(<EquipmentCard equipment={base} />);
    expect(screen.getByText('Formation Cycler #1')).toBeDefined();
    expect(screen.getByText(/running/i)).toBeDefined();
  });

  it('renders the unit id', () => {
    render(<EquipmentCard equipment={base} />);
    expect(screen.getByText(/CELL-2026-04-05-0001/)).toBeDefined();
  });

  it('renders metric values', () => {
    render(<EquipmentCard equipment={base} />);
    expect(screen.getByText(/45.2/)).toBeDefined();
  });

  it('handles missing status', () => {
    render(<EquipmentCard equipment={{ ...base, status: null }} />);
    expect(screen.getByText(/unknown/i)).toBeDefined();
  });
});
