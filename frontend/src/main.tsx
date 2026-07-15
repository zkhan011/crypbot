import React, { useMemo, useState } from 'react';
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
] as const;

type PageName = (typeof pages)[number];

const pageDescriptions: Record<PageName, string> = {
  Overview: 'Portfolio-wide operational status and safety controls.',
  Organizations: 'Tenant administration and organization-level controls.',
  'Users and roles': 'Least-privilege role assignment and operator access review.',
  'Exchange accounts': 'Exchange account registration, verification, and credential rotation.',
  Masters: 'Master account signal sources and ingestion status.',
  Followers: 'Follower account configuration, limits, and pause state.',
  'Copy relationships': 'Master-to-follower copy mappings and state-machine status.',
  Strategies: 'Automated execution strategies, simulation controls, pause/resume, and emergency stop.',
  'Risk settings': 'Pre-trade risk limits and rejection reason visibility.',
  'Volume-aware execution': 'Legitimate participation-capped execution planning; not fake volume generation.',
  'Live orders': 'Current order lifecycle and idempotency status.',
  Positions: 'Open positions and reconciliation state.',
  Balances: 'Latest fake-exchange balance snapshots for local demonstration.',
  'Reconciliation incidents': 'Mismatches requiring review before additional trading.',
  Alerts: 'Operational and security alert queue.',
  'Audit trail': 'Append-only administrative and trading decision history.',
  'System health': 'API, worker, WebSocket, database, and Redis readiness.',
  'Kill switches': 'Emergency controls that fail closed for new trading.',
  Reports: 'Tenant-scoped operational and compliance reports.',
};

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
type BotStatusResponse = {
  mode: string;
  bot_state: string;
  heartbeat_at: string;
  market_data_state: string;
  worker_state: string;
  trading_state: string;
  orders_processed_today: number;
  last_trade_summary: string;
  truthfulness_note: string;
};
type GenericResponse = Record<string, unknown>;
type VolumePlanResponse = {
  mode: string;
  objective: string;
  max_participation_rate: string;
  child_orders: Array<{ slice: number; quantity: string; max_market_volume_quantity: string }>;
};

type DemoAction = {
  label: string;
  page: PageName;
  run: () => Promise<GenericResponse>;
  dangerous?: boolean;
};

function Dashboard() {
  const [activePage, setActivePage] = useState<PageName>('Overview');
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<HealthResponse>('/health') });
  const botStatus = useQuery({
    queryKey: ['bot-status'],
    queryFn: () => api<BotStatusResponse>('/api/v1/bot/status'),
    refetchInterval: 5000,
  });
  const action = useMutation({ mutationFn: (run: () => Promise<GenericResponse>) => run() });
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

  const demoActions = useMemo<DemoAction[]>(
    () => [
      {
        page: 'Overview',
        label: 'Activate MOCK mode',
        run: () => api<GenericResponse>('/api/v1/system/mode/activate-mock', { method: 'POST' }),
      },
      {
        page: 'Copy relationships',
        label: 'Simulate copy trade',
        run: () => api<GenericResponse>('/api/v1/demo/copy-trade', { method: 'POST' }),
      },
      {
        page: 'Live orders',
        label: 'Submit fake exchange order',
        run: () => api<GenericResponse>('/api/v1/demo/submit-order', { method: 'POST' }),
      },
      {
        page: 'Strategies',
        label: 'Simulate TWAP plan',
        run: () => api<GenericResponse>('/api/v1/demo/twap', { method: 'POST' }),
      },
      {
        page: 'Reconciliation incidents',
        label: 'Load reconciliation demo',
        run: () => api<GenericResponse>('/api/v1/reconciliation/demo'),
      },
      {
        page: 'Kill switches',
        label: 'Activate account kill switch',
        dangerous: true,
        run: () => api<GenericResponse>('/api/v1/kill-switch/account/acct-1', { method: 'POST' }),
      },
      {
        page: 'System health',
        label: 'Refresh readiness',
        run: () => api<GenericResponse>('/ready'),
      },
    ],
    [],
  );

  const activeActions = demoActions.filter((demoAction) => demoAction.page === activePage || activePage === 'Overview');

  const overviewCards = [
    ['Connected exchange accounts', '0'],
    ['Active strategies', '0'],
    ['Follower relationships', '0'],
    ['Open positions', '0'],
    ['Total exposure', '0 USDT'],
    ['Daily PnL', '0 USDT'],
    ['Rejected orders', '0'],
    ['Reconciliation incidents', '0'],
    ['Worker health', botStatus.data?.worker_state ?? 'RUNNING'],
    ['WebSocket health', botStatus.data?.market_data_state ?? 'STREAMING_SIMULATED'],
    ['Bot trading state', botStatus.data?.trading_state ?? 'SIMULATED_TRADING'],
    ['Orders processed today', String(botStatus.data?.orders_processed_today ?? 0)],
  ];

  return (
    <main>
      <aside>
        <h1>Crypbot</h1>
        <button
          type="button"
          className="modeButton"
          onClick={() => action.mutate(() => api<GenericResponse>('/api/v1/system/mode/activate-mock', { method: 'POST' }))}
        >
          Activate MOCK mode
        </button>
        <strong className="badge">{botStatus.data?.mode ?? health.data?.mode ?? 'MOCK'} MODE</strong>
        <span className="sidebarStatus">{botStatus.data?.bot_state ?? 'RUNNING'}</span>
        <nav aria-label="Administration sections">
          {pages.map((page) => (
            <button
              type="button"
              key={page}
              className={page === activePage ? 'navItem active' : 'navItem'}
              aria-pressed={page === activePage}
              onClick={() => setActivePage(page)}
            >
              {page}
            </button>
          ))}
        </nav>
      </aside>
      <section>
        <h2>{activePage}</h2>
        <p>{pageDescriptions[activePage]}</p>

        <section className="statusBanner" aria-live="polite">
          <div>
            <span className="pulse" aria-hidden="true" />
            <strong>Bot {botStatus.data?.bot_state ?? 'RUNNING'}</strong>
            <p>{botStatus.data?.last_trade_summary ?? 'Loading continuous bot status…'}</p>
          </div>
          <dl>
            <div>
              <dt>Mode</dt>
              <dd>{botStatus.data?.mode ?? 'MOCK'}</dd>
            </div>
            <div>
              <dt>Trading</dt>
              <dd>{botStatus.data?.trading_state ?? 'SIMULATED_TRADING'}</dd>
            </div>
            <div>
              <dt>Workers</dt>
              <dd>{botStatus.data?.worker_state ?? 'RUNNING'}</dd>
            </div>
            <div>
              <dt>Heartbeat</dt>
              <dd>{botStatus.data?.heartbeat_at ? new Date(botStatus.data.heartbeat_at).toLocaleTimeString() : 'pending'}</dd>
            </div>
          </dl>
          <small>{botStatus.data?.truthfulness_note ?? 'MOCK mode displays simulated activity only.'}</small>
        </section>
        {activePage === 'Overview' ? (
          <div className="grid">
            {overviewCards.map(([label, value]) => (
              <article key={label}>
                <span>{label}</span>
                <b>{value}</b>
              </article>
            ))}
          </div>
        ) : null}

        <section className="panel">
          <h3>Actions</h3>
          <p>Each button runs a safe mock/demo workflow. Dangerous operations require explicit confirmation.</p>
          <div className="actions">
            {activeActions.length ? (
              activeActions.map((demoAction) => (
                <button
                  type="button"
                  key={`${demoAction.page}-${demoAction.label}`}
                  className={demoAction.dangerous ? 'dangerButton' : undefined}
                  onClick={() => {
                    if (demoAction.dangerous && !window.confirm('This activates a demo kill switch and blocks new trading for the account. Continue?')) {
                      return;
                    }
                    action.mutate(demoAction.run);
                  }}
                >
                  {demoAction.label}
                </button>
              ))
            ) : (
              <button type="button" onClick={() => setActivePage('Overview')}>
                Back to overview actions
              </button>
            )}
          </div>
          {action.data ? <pre>{JSON.stringify(action.data, null, 2)}</pre> : null}
          {action.error ? <p className="error">{String(action.error)}</p> : null}
        </section>

        {activePage === 'Volume-aware execution' || activePage === 'Overview' ? (
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
        ) : null}

        <section className="panel">
          <h3>API health</h3>
          {health.isLoading ? <p>Loading API health…</p> : null}
          {health.error ? <p className="error">{String(health.error)}</p> : <pre>{JSON.stringify({ health: health.data, botStatus: botStatus.data }, null, 2)}</pre>}
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
