/**
 * Test setup file for vitest.
 */
import '@testing-library/jest-dom/vitest';

// Mock window.location methods for tests
Object.defineProperty(window, 'location', {
  writable: true,
  value: {
    ...window.location,
    pathname: '/th',
    href: 'http://localhost:3000/th',
  },
});
