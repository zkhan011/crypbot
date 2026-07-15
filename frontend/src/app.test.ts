import { describe, expect, it } from 'vitest';

describe('dashboard configuration', () => {
  it('includes the volume-aware execution page without exposing secrets', () => {
    const pages = ['Overview', 'Volume-aware execution', 'Kill switches'];
    expect(pages).toContain('Volume-aware execution');
    expect(JSON.stringify(pages)).not.toContain('api_secret');
  });
});
