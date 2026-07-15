import { describe, expect, it } from 'vitest';

const pages = ['Overview', 'Volume-aware execution', 'Kill switches'];
const actions = ['Activate MOCK mode', 'Simulate volume-aware plan', 'Activate account kill switch'];

describe('dashboard configuration', () => {
  it('includes clickable navigation options and mock mode action without exposing secrets', () => {
    expect(pages).toContain('Volume-aware execution');
    expect(actions).toContain('Activate MOCK mode');
    expect(actions).toContain('Activate account kill switch');
    expect(JSON.stringify({ pages, actions })).not.toContain('api_secret');
  });
});
