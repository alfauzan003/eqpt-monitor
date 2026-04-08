import type { Equipment } from '../types';
import { EquipmentCard } from './EquipmentCard';

interface Props {
  equipment: Equipment[];
}

export function EquipmentGrid({ equipment }: Props) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: 12,
      }}
    >
      {equipment.map((e) => (
        <EquipmentCard key={e.id} equipment={e} />
      ))}
    </div>
  );
}
