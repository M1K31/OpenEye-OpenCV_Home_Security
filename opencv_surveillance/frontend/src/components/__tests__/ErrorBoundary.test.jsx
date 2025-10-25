import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ErrorBoundary from '../ErrorBoundary';

describe('ErrorBoundary', () => {
  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Test Content</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('catches errors and displays error message', () => {
    // Component that throws an error
    const ThrowError = () => {
      throw new Error('Test error');
    };

    // Suppress console.error for this test
    const originalError = console.error;
    console.error = () => {};

    render(
      <ErrorBoundary fallbackMessage="Something went wrong">
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();

    // Restore console.error
    console.error = originalError;
  });

  it('displays custom fallback message', () => {
    const ThrowError = () => {
      throw new Error('Test error');
    };

    const originalError = console.error;
    console.error = () => {};

    render(
      <ErrorBoundary fallbackMessage="Custom error message">
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Custom error message/i)).toBeInTheDocument();

    console.error = originalError;
  });
});
