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
      <ErrorBoundary fallbackMessage="A distinctive fallback notice">
        <ThrowError />
      </ErrorBoundary>
    );

    // The message must be distinct from the boundary's own heading. Asserting on
    // /Something went wrong/i matched BOTH the built-in "Oops! Something went
    // wrong" title and the fallbackMessage, so getByText threw "Found multiple
    // elements" — the test failed while the component was working correctly.
    expect(screen.getByText('A distinctive fallback notice')).toBeInTheDocument();
    // The default heading is still shown alongside the custom message.
    expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();

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
