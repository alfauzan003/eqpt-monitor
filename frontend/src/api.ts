import type { EquipmentListResponse } from './types';

export async function fetchEquipment(): Promise<EquipmentListResponse> {
  const r = await fetch('/api/equipment');
  if (!r.ok) throw new Error(`fetch equipment failed: ${r.status}`);
  return r.json();
}
