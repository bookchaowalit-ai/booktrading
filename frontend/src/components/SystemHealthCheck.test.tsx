/**
 * Smoke tests for SystemHealthCheck component.
 *
 * These ensure the visibility layer doesn't crash or mislead
 * when the backend/strategy services return various states.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import SystemHealthCheck from '@/components/SystemHealthCheck';
import React from 'react';

// Mock framer-motion to avoid animation complexity in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock lucide-react icons to simple divs
vi.mock('lucide-react', () => ({
  Activity: () => <div data-testid="icon-activity" />,
  CheckCircle2: () => <div data-testid="icon-check-circle" />,
  AlertCircle: () => <div data-testid="icon-alert-circle" />,
  XCircle: () => <div data-testid="icon-x-circle" />,
  RefreshCw: () => <div data-testid="icon-refresh" />,
  Database: () => <div data-testid="icon-database" />,
  Server: () => <div data-testid="icon-server" />,
  Wifi: () => <div data-testid="icon-wifi" />,
}));

// Helper to create a healthy /health response
function mockHealthyResponse() {
  return {
    ok: true,
    json: () =>
      Promise.resolve({
        status: 'healthy',
        database: 'healthy',
        redis: 'healthy',
      }),
  };
}

// Helper to create a failed response
function mockUnhealthyResponse() {
  return {
    ok: false,
    status: 503,
    json: () => Promise.resolve({ status: 'unhealthy' }),
  };
}

describe('SystemHealthCheck — Smoke Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders without crashing when all services are healthy', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockHealthyResponse());

    render(<SystemHealthCheck />);

    // Should show "System Health" heading
    expect(screen.getByText('System Health')).toBeInTheDocument();

    // Wait for health checks to complete and services to render
    await waitFor(() => {
      expect(screen.getByText('Backend API')).toBeInTheDocument();
    });

    // All core services should appear
    expect(screen.getByText('WebSocket')).toBeInTheDocument();
    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(screen.getByText('Redis')).toBeInTheDocument();
    expect(screen.getByText('Strategy Service')).toBeInTheDocument();
  });

  it('renders "All Systems Operational" when all services return healthy', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockHealthyResponse());

    render(<SystemHealthCheck />);

    await waitFor(() => {
      expect(screen.getByText('All Systems Operational')).toBeInTheDocument();
    });
  });

  it('renders degraded/unhealthy state when API calls fail', async () => {
    // All fetches throw — simulates total backend outage
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    render(<SystemHealthCheck />);

    // Should still render the heading (component doesn't crash)
    expect(screen.getByText('System Health')).toBeInTheDocument();

    // Should show a degraded or system-down state
    await waitFor(() => {
      const unhealthyBadges = screen.getAllByText('unhealthy');
      expect(unhealthyBadges.length).toBeGreaterThan(0);
    });
  });

  it('shows "System Degraded" when some services fail', async () => {
    // Backend API healthy, but strategy service fails
    global.fetch = vi
      .fn()
      .mockResolvedValueOnce(mockHealthyResponse()) // Backend API
      .mockResolvedValueOnce(mockHealthyResponse()) // Database (via /api/health)
      .mockResolvedValueOnce(mockHealthyResponse()) // Redis (via /api/health)
      .mockRejectedValueOnce(new Error('Strategy down')); // Strategy Service

    render(<SystemHealthCheck />);

    await waitFor(() => {
      // Should show degraded overall status
      expect(
        screen.getByText('System Degraded') || screen.getByText('Partially Degraded')
      ).toBeInTheDocument();
    });
  });

  it('does not crash when fetch returns empty/invalid JSON', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    render(<SystemHealthCheck />);

    // Component should still render heading without crashing
    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
    });
  });

  it('shows "Check" button for manual refresh', async () => {
    global.fetch = vi.fn().mockResolvedValue(mockHealthyResponse());

    render(<SystemHealthCheck />);

    // Wait for health checks to finish (loading=true shows spinner, not text)
    await waitFor(() => {
      expect(screen.getByText('Check')).toBeInTheDocument();
    });
  });
});
