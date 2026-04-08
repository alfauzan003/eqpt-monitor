import type { Equipment } from '../types';

interface Props {
  equipment: Equipment;
}

const STATUS_COLORS: Record<string, string> = {
  running: '#22c55e',
  idle: '#94a3b8',
  fault: '#ef4444',
  maintenance: '#f59e0b',
};

export function EquipmentCard({ equipment }: Props) {
  const status = equipment.status ?? 'unknown';
  const color = STATUS_COLORS[status] ?? '#64748b';
  const metrics = Object.entries(equipment.latest_metrics);

  return (
    <div
      style={{
        border: '1px solid #e2e8f0',
        borderRadius: 8,
        padding: 16,
        minWidth: 260,
        fontFamily: 'system-ui, sans-serif',
        background: '#fff',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{equipment.name}</div>
          <div style={{ color: '#64748b', fontSize: 12 }}>{equipment.location}</div>
        </div>
        <span
          style={{
            background: color,
            color: '#fff',
            padding: '2px 8px',
            borderRadius: 12,
            fontSize: 11,
            textTransform: 'uppercase',
          }}
        >
          {status}
        </span>
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: '#475569' }}>
        Processing: {equipment.current_unit_id ?? '—'}
      </div>
      <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
        {metrics.map(([k, v]) => (
          <div key={k} style={{ fontSize: 12 }}>
            <span style={{ color: '#64748b' }}>{k}:</span>{' '}
            <span style={{ fontWeight: 600 }}>{v.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
