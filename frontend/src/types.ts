export interface Equipment {
  id: string;
  name: string;
  type: string;
  location: string;
  status: string | null;
  current_batch_id: string | null;
  current_unit_id: string | null;
  unit_started_at: string | null;
  latest_metrics: Record<string, number>;
  updated_at: string | null;
}

export interface EquipmentListResponse {
  equipment: Equipment[];
}

export interface TelemetryEvent {
  type: 'telemetry';
  equipment_id: string;
  time: string;
  status: string | null;
  batch_id: string | null;
  unit_id: string | null;
  metrics: Record<string, number>;
}
