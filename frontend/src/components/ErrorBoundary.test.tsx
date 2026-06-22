/**
 * Tests for the ErrorBoundary component.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ErrorBoundary from '@/components/ErrorBoundary';
import React from 'react';

// Component that throws an error
function BrokenComponent(): React.ReactElement {
  throw new Error('Test error');
}

// Component that renders normally
function WorkingComponent() {
  return <div data-testid="working">Working properly</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <WorkingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByTestId('working')).toBeInTheDocument();
    expect(screen.getByText('Working properly')).toBeInTheDocument();
  });

  it('renders fallback UI when child component throws', () => {
    // Suppress console.error during test
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <BrokenComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/unexpected error occurred/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();

    consoleError.mockRestore();
  });

  it('renders go home action when child component throws', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <BrokenComponent />
      </ErrorBoundary>
    );

    expect(screen.getByRole('button', { name: /go home/i })).toBeInTheDocument();

    consoleError.mockRestore();
  });

  it('renders custom fallback when provided', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary fallback={<div data-testid="custom-fallback">Custom Error</div>}>
        <BrokenComponent />
      </ErrorBoundary>
    );

    expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
    expect(screen.getByText('Custom Error')).toBeInTheDocument();

    consoleError.mockRestore();
  });

  it('reloads the page when "Refresh" is clicked', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const reload = vi.fn();
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...window.location, reload },
    });

    // We can't easily test re-rendering after error reset with a broken component,
    // but we can verify the button exists and is clickable
    render(
      <ErrorBoundary>
        <BrokenComponent />
      </ErrorBoundary>
    );

    const button = screen.getByRole('button', { name: /refresh/i });
    expect(button).toBeInTheDocument();

    fireEvent.click(button);
    expect(reload).toHaveBeenCalled();

    consoleError.mockRestore();
  });
});
