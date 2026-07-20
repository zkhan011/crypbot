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
  'AI Strategy Assistant',
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
  'AI Strategy Assistant': 'Mock AI creates non-executing strategy drafts that require administrator approval and mock validation.',
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

async function authenticatedApi<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  return api<T>(path, { ...init, headers: { authorization: `Bearer ${token}`, ...(init?.headers ?? {}) } });
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
type MockMarketResponse = {
  mode: string;
  timestamp: string;
  data_quality: string;
  truthfulness_note: string;
  amount_traded_today: string;
  realized_pnl_today: string;
  unrealized_pnl: string;
  total_pnl: string;
  markets: Array<{
    symbol: string;
    price: string;
    change_percent: string;
    mock_volume: string;
    simulated_position_quantity: string;
    simulated_notional: string;
    simulated_unrealized_pnl: string;
  }>;
};
type TradingDashboardResponse = {
  bot_state: string;
  copy_state: string;
  volume_state: string;
  scenario: string;
  api_connected: boolean;
  balance: { asset: string; total: string; available: string };
  scenario_options: string[];
  open_positions: Array<Record<string, string>>;
  closed_trades: Array<Record<string, string>>;
  signals: Array<Record<string, string>>;
  orders: Array<Record<string, string>>;
  notifications: Array<Record<string, string | boolean>>;
  risk_events: Array<Record<string, string>>;
  reports: Record<string, unknown>;
};

type VolumePlanResponse = {
  mode: string;
  objective: string;
  max_participation_rate: string;
  child_orders: Array<{ slice: number; quantity: string; max_market_volume_quantity: string }>;
};
type LoggedInUser = { id: string; email: string; display_name: string; role: string; force_password_change: boolean };
type LoginResponse = { access_token: string; user: LoggedInUser };
type StrategyDraft = { id: string; strategyName: string; strategyType: string; activationStatus: string; riskExplanation: string };

type DemoAction = {
  label: string;
  page: PageName;
  run: () => Promise<GenericResponse>;
  dangerous?: boolean;
};

function Dashboard() {
  const [activePage, setActivePage] = useState<PageName>('Overview');
  const [email, setEmail] = useState('superadmin@example.local');
  const [password, setPassword] = useState('ChangeMe123!');
  const [aiPrompt, setAiPrompt] = useState('Create a conservative BTC and ETH volume breakout strategy');
  const [session, setSession] = useState<LoginResponse | null>(null);
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<HealthResponse>('/health') });
  const botStatus = useQuery({
    queryKey: ['bot-status'],
    queryFn: () => api<BotStatusResponse>('/api/v1/bot/status'),
    refetchInterval: 5000,
  });
  const mockMarket = useQuery({
    queryKey: ['mock-market-live'],
    queryFn: () => api<MockMarketResponse>('/api/v1/mock/market-live'),
    refetchInterval: 3000,
  });
  const tradingDashboard = useQuery({
    queryKey: ['trading-dashboard'],
    queryFn: () => api<TradingDashboardResponse>('/api/v1/trading/dashboard'),
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
  const login = useMutation({
    mutationFn: () => api<LoginResponse>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
    onSuccess: setSession,
  });
  const drafts = useQuery({
    queryKey: ['ai-drafts', session?.access_token],
    queryFn: () => authenticatedApi<{ drafts: StrategyDraft[] }>('/api/v1/ai/strategy-drafts', session!.access_token),
    enabled: Boolean(session),
  });
  const createDraft = useMutation({
    mutationFn: () => authenticatedApi<StrategyDraft>('/api/v1/ai/strategy-drafts', session!.access_token, { method: 'POST', body: JSON.stringify({ prompt: aiPrompt }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-drafts'] }),
  });
  const approveDraft = useMutation({
    mutationFn: (draftId: string) => authenticatedApi<StrategyDraft>(`/api/v1/ai/strategy-drafts/${draftId}/approve`, session!.access_token, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-drafts'] }),
  });

  const demoActions = useMemo<DemoAction[]>(
    () => [
      {
        page: 'Overview',
        label: 'Activate MOCK mode',
        run: () => api<GenericResponse>('/api/v1/system/mode/activate-mock', { method: 'POST' }),
      },
      {
        page: 'Overview',
        label: 'Start bot',
        run: () => api<GenericResponse>('/api/v1/trading/start', { method: 'POST' }),
      },
      {
        page: 'Overview',
        label: 'Stop bot',
        run: () => api<GenericResponse>('/api/v1/trading/stop', { method: 'POST' }),
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
        run: () => api<GenericResponse>('/api/v1/trading/emergency-close-all', { method: 'POST' }),
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
  const triggerScenario = (scenario: string) => {
    action.mutate(() => api<GenericResponse>(`/api/v1/trading/mock-scenario/${encodeURIComponent(scenario)}`, { method: 'POST' }));
  };

  const overviewCards = [
    ['Connected exchange accounts', tradingDashboard.data?.api_connected ? '1 mock BingX' : 'Disconnected'],
    ['Active strategies', `Copy ${tradingDashboard.data?.copy_state ?? 'RUNNING'} / Volume ${tradingDashboard.data?.volume_state ?? 'RUNNING'}`],
    ['Follower relationships', '0'],
    ['Open positions', String(tradingDashboard.data?.open_positions?.length ?? 0)],
    ['Total exposure', `${mockMarket.data?.amount_traded_today ?? '0'} USDT`],
    ['Amount traded today', `${mockMarket.data?.amount_traded_today ?? '0'} USDT`],
    ['Realized PnL', `${mockMarket.data?.realized_pnl_today ?? '0'} USDT`],
    ['Unrealized PnL', `${mockMarket.data?.unrealized_pnl ?? '0'} USDT`],
    ['Total PnL', `${mockMarket.data?.total_pnl ?? '0'} USDT`],
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

        <section className="panel loginPanel">
          <h3>Authenticated admin demo</h3>
          {session ? (
            <p>Signed in as <strong>{session.user.display_name}</strong> ({session.user.role}). AI drafts are never executable directly.</p>
          ) : (
            <div className="loginFields">
              <input aria-label="Email" value={email} onChange={(event) => setEmail(event.target.value)} />
              <input aria-label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
              <button type="button" onClick={() => login.mutate()}>Sign in to control plane</button>
              <small>Demo credentials are documented for local MOCK mode only.</small>
            </div>
          )}
          {login.error ? <p className="error">{String(login.error)}</p> : null}
        </section>

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
          <h3>Mock scenario selector</h3>
          <p>Each scenario runs backend mock behavior through the same strategy/risk/order abstractions used by the dashboard.</p>
          <select
            value={tradingDashboard.data?.scenario ?? 'Normal market'}
            onChange={(event) => triggerScenario(event.target.value)}
          >
            {(tradingDashboard.data?.scenario_options ?? ['Normal market']).map((scenario) => (
              <option key={scenario} value={scenario}>
                {scenario}
              </option>
            ))}
          </select>
          <div className="actions">
            <button type="button" onClick={() => action.mutate(() => api<GenericResponse>('/api/v1/trading/copy/pause', { method: 'POST' }))}>Pause copy strategy</button>
            <button type="button" onClick={() => action.mutate(() => api<GenericResponse>('/api/v1/trading/copy/resume', { method: 'POST' }))}>Resume copy strategy</button>
            <button type="button" onClick={() => action.mutate(() => api<GenericResponse>('/api/v1/trading/volume/pause', { method: 'POST' }))}>Pause volume strategy</button>
            <button type="button" onClick={() => action.mutate(() => api<GenericResponse>('/api/v1/trading/volume/resume', { method: 'POST' }))}>Resume volume strategy</button>
          </div>
        </section>

        <section className="panel marketPanel">
          <h3>Mock real-time market and P&amp;L simulation</h3>
          <p>{mockMarket.data?.truthfulness_note ?? 'Loading mock real-time market data…'}</p>
          <div className="pnlStrip">
            <span>Amount traded: <strong>{mockMarket.data?.amount_traded_today ?? '0'} USDT</strong></span>
            <span>Realized P&amp;L: <strong>{mockMarket.data?.realized_pnl_today ?? '0'} USDT</strong></span>
            <span>Unrealized P&amp;L: <strong>{mockMarket.data?.unrealized_pnl ?? '0'} USDT</strong></span>
            <span>Total P&amp;L: <strong>{mockMarket.data?.total_pnl ?? '0'} USDT</strong></span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Mock price</th>
                <th>Change %</th>
                <th>Mock volume</th>
                <th>Position</th>
                <th>Notional</th>
                <th>Unrealized P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {(mockMarket.data?.markets ?? []).map((market) => (
                <tr key={market.symbol}>
                  <td>{market.symbol}</td>
                  <td>{market.price}</td>
                  <td>{market.change_percent}</td>
                  <td>{market.mock_volume}</td>
                  <td>{market.simulated_position_quantity}</td>
                  <td>{market.simulated_notional}</td>
                  <td>{market.simulated_unrealized_pnl}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <small>Last mock tick: {mockMarket.data?.timestamp ? new Date(mockMarket.data.timestamp).toLocaleTimeString() : 'pending'}</small>
        </section>



        <section className="panel marketPanel">
          <h3>Trading engine data</h3>
          <div className="pnlStrip">
            <span>Balance: <strong>{tradingDashboard.data?.balance.total ?? '0'} {tradingDashboard.data?.balance.asset ?? 'USDT'}</strong></span>
            <span>Available: <strong>{tradingDashboard.data?.balance.available ?? '0'} USDT</strong></span>
            <span>Copy: <strong>{tradingDashboard.data?.copy_state ?? 'RUNNING'}</strong></span>
            <span>Volume: <strong>{tradingDashboard.data?.volume_state ?? 'RUNNING'}</strong></span>
          </div>
          <h4>Open positions</h4>
          <pre>{JSON.stringify(tradingDashboard.data?.open_positions ?? [], null, 2)}</pre>
          <h4>Recent signals</h4>
          <pre>{JSON.stringify(tradingDashboard.data?.signals ?? [], null, 2)}</pre>
          <h4>Recent orders</h4>
          <pre>{JSON.stringify(tradingDashboard.data?.orders ?? [], null, 2)}</pre>
          <h4>Notification preview</h4>
          <pre>{JSON.stringify(tradingDashboard.data?.notifications ?? [], null, 2)}</pre>
          <h4>Reports</h4>
          <pre>{JSON.stringify(tradingDashboard.data?.reports ?? {}, null, 2)}</pre>
        </section>

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

        {activePage === 'AI Strategy Assistant' ? (
          <section className="panel">
            <h3>AI Strategy Assistant — draft-only</h3>
            <p>The mock AI assistant produces structured recommendations only. It cannot submit orders, and approval rejects drafts that exceed hard limits.</p>
            {session ? (
              <>
                <textarea aria-label="AI strategy prompt" value={aiPrompt} onChange={(event) => setAiPrompt(event.target.value)} />
                <div className="actions"><button type="button" onClick={() => createDraft.mutate()}>Create mock AI draft</button></div>
                {createDraft.error ? <p className="error">{String(createDraft.error)}</p> : null}
                {(drafts.data?.drafts ?? []).map((draft) => (
                  <article className="draftCard" key={draft.id}>
                    <div><b>{draft.strategyName}</b><br /><small>{draft.strategyType} · {draft.activationStatus}</small><p>{draft.riskExplanation}</p></div>
                    {session.user.role === 'SUPER_ADMIN' || session.user.role === 'ADMIN' ? <button type="button" disabled={draft.activationStatus !== 'DRAFT'} onClick={() => approveDraft.mutate(draft.id)}>Approve safe draft</button> : null}
                  </article>
                ))}
              </>
            ) : <p>Sign in to create or review a draft.</p>}
          </section>
        ) : null}

        <section className="panel">
          <h3>API health</h3>
          {health.isLoading ? <p>Loading API health…</p> : null}
          {health.error ? <p className="error">{String(health.error)}</p> : <pre>{JSON.stringify({ health: health.data, botStatus: botStatus.data, mockMarket: mockMarket.data, tradingDashboard: tradingDashboard.data }, null, 2)}</pre>}
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
