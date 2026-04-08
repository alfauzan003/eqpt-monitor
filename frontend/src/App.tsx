import { useEffect, useRef, useState } from 'react';
import { fetchEquipment } from './api';
import { TelemetryWebSocket } from './websocket';
import { EquipmentGrid } from './components/EquipmentGrid';
import { ConnectionStatus } from './components/ConnectionStatus';
import type { Equipment, TelemetryEvent } from './types';

export default function App() {
  const [equipment, setEquipment] = useState<Record<string, Equipment>>({});
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<TelemetryWebSocket | null>(null);

  useEffect(() => {
    fetchEquipment()
      .then((res) => {
        const map: Record<string, Equipment> = {};
        for (const e of res.equipment) map[e.id] = e;
        setEquipment(map);
      })
      .catch((err) => console.error('fetch equipment', err));

    const ws = new TelemetryWebSocket(
      (ev: TelemetryEvent) => {
        setEquipment((prev) => {
          const cur = prev[ev.equipment_id];
          if (!cur) return prev;
          return {
            ...prev,
            [ev.equipment_id]: {
              ...cur,
              status: ev.status,
              current_batch_id: ev.batch_id,
              current_unit_id: ev.unit_id,
              latest_metrics: { ...cur.latest_metrics, ...ev.metrics },
              updated_at: ev.time,
            },
          };
        });
      },
      (ok) => setConnected(ok),
    );
    wsRef.current = ws;
    ws.connect();
    return () => ws.close();
  }, []);

  const list = Object.values(equipment).sort((a, b) => a.id.localeCompare(b.id));

  return (
    <div style={{ padding: 16, fontFamily: 'system-ui, sans-serif', background: '#f8fafc', minHeight: '100vh' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Factory Pulse — Floor Overview</h1>
        <ConnectionStatus connected={connected} />
      </header>
      <EquipmentGrid equipment={list} />
    </div>
  );
}
