# Frontend Testing Guide

This directory contains test utilities and setup for OpenEye frontend testing.

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run tests with coverage
npm run test:coverage

# Run tests with UI
npm run test:ui
```

## Test Structure

```
frontend/src/
├── components/__tests__/     # Component tests
├── services/__tests__/       # Service/utility tests
├── pages/__tests__/          # Page component tests (future)
└── test/                     # Test setup and utilities
    ├── setup.js              # Global test setup
    └── README.md             # This file
```

## Writing Tests

### Component Tests

```jsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MyComponent from '../MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });
});
```

### Service Tests

```javascript
import { describe, it, expect } from 'vitest';
import myService from '../myService';

describe('myService', () => {
  it('performs action correctly', () => {
    const result = myService.doSomething();
    expect(result).toBe(expected);
  });
});
```

## Testing Libraries

- **Vitest**: Fast unit test framework
- **React Testing Library**: Test React components
- **jsdom**: DOM implementation for testing
- **@testing-library/jest-dom**: Custom matchers

## Best Practices

1. **Test behavior, not implementation**
2. **Use descriptive test names**
3. **Keep tests focused and isolated**
4. **Mock external dependencies**
5. **Aim for >80% coverage**
