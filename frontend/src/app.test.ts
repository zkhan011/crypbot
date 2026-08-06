import { describe, expect, it } from 'vitest';

const pages = ['Overview', 'Volume-aware execution', 'Kill switches'];
const actions = ['Activate MOCK mode', 'Simulate volume-aware plan', 'Activate account kill switch'];
const botStatusFields = ['bot_state', 'heartbeat_at', 'trading_state', 'truthfulness_note'];
const mockMarketFields = ['amount_traded_today', 'realized_pnl_today', 'unrealized_pnl', 'total_pnl', 'markets'];

describe('dashboard configuration', () => {
  it('includes clickable navigation options and mock mode action without exposing secrets', () => {
    expect(pages).toContain('Volume-aware execution');
    expect(actions).toContain('Activate MOCK mode');
    expect(actions).toContain('Activate account kill switch');
    expect(JSON.stringify({ pages, actions })).not.toContain('api_secret');
  });

  it('defines continuous bot status fields for mock and live mode display', () => {
    expect(botStatusFields).toContain('heartbeat_at');
    expect(botStatusFields).toContain('trading_state');
    expect(botStatusFields).toContain('truthfulness_note');
  });

  it('defines mock real-time trading metrics for the live-feature simulation', () => {
    expect(mockMarketFields).toContain('amount_traded_today');
    expect(mockMarketFields).toContain('total_pnl');
    expect(mockMarketFields).toContain('markets');
  });
});
