interface Props {
  connected: boolean;
}

export function ConnectionStatus({ connected }: Props) {
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 12,
        color: connected ? '#16a34a' : '#dc2626',
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: connected ? '#22c55e' : '#ef4444',
        }}
      />
      {connected ? 'Live' : 'Reconnecting…'}
    </div>
  );
}
