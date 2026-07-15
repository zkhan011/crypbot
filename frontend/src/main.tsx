import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider, useMutation, useQuery } from '@tanstack/react-query';
import './style.css';

const queryClient = new QueryClient();

const pages = [
  'Overview',
  'Organizations',
  'Users and roles',
  'Exchange accounts',
  'Masters',
  'Followers',
  'Copy relationships',
  'Strategies',
  'Risk settings',
  'Volume-aware execution',
  'Live orders',
  'Positions',
  'Balances',
  'Reconciliation incidents',
  'Alerts',
  'Audit trail',
  'System health',
  'Kill switches',
  'Reports',
];

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

type HealthResponse = { status: string; mode: string };
type VolumePlanResponse = {
  mode: string;
  objective: string;
  max_participation_rate: string;
  child_orders: Array<{ slice: number; quantity: string; max_market_volume_quantity: string }>;
};

function Dashboard() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<HealthResponse>('/health') });
  const volumePlan = useMutation({
    mutationFn: () =>
      api<VolumePlanResponse>('/api/v1/demo/volume-execution', {
        method: 'POST',
        body: JSON.stringify({
          symbol: 'BTC-USDT',
          side: 'BUY',
          target_quantity: '0.02',
          slices: 4,
          observed_market_volume: '10',
          max_participation_rate: '0.001',
          objective: 'Accumulate inventory using a capped participation schedule without creating artificial volume.',
        }),
      }),
  });

  const overviewCards = [
    ['Connected exchange accounts', '0'],
    ['Active strategies', '0'],
    ['Follower relationships', '0'],
    ['Open positions', '0'],
    ['Total exposure', '0 USDT'],
    ['Daily PnL', '0 USDT'],
    ['Rejected orders', '0'],
    ['Reconciliation incidents', '0'],
    ['Worker health', 'OK'],
    ['WebSocket health', 'OK'],
  ];

  return (
    <main>
      <aside>
        <h1>Crypbot</h1>
        <strong className="badge">MOCK MODE</strong>
        {pages.map((page) => (
          <a key={page}>{page}</a>
        ))}
      </aside>
      <section>
        <h2>Operational Overview</h2>
        <p>Production-oriented crypto copy-trading control plane. Secrets never leave the backend.</p>
        <div className="grid">
          {overviewCards.map(([label, value]) => (
            <article key={label}>
              <span>{label}</span>
              <b>{value}</b>
            </article>
          ))}
        </div>

        <section className="panel">
          <h3>Compliant volume-aware execution</h3>
          <p>
            Builds capped participation child orders for legitimate execution objectives only. It is not a fake-volume,
            wash-trading, or self-trading tool.
          </p>
          <button type="button" onClick={() => volumePlan.mutate()}>
            Simulate volume-aware plan
          </button>
          {volumePlan.data ? <pre>{JSON.stringify(volumePlan.data, null, 2)}</pre> : null}
          {volumePlan.error ? <p className="error">{String(volumePlan.error)}</p> : null}
        </section>

        <section className="panel">
          <h3>API health</h3>
          {health.isLoading ? <p>Loading API health…</p> : null}
          {health.error ? <p className="error">{String(health.error)}</p> : <pre>{JSON.stringify(health.data, null, 2)}</pre>}
        </section>
      </section>
    </main>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
