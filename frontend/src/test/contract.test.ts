/**
 * Contract / Smoke Tests for 5 Main Pages
 *
 * Verifies:
 * 1. Each page module can be imported (no syntax/compile errors)
 * 2. No forbidden action buttons (Start / Trade / Configure / Reset) in main UX
 *
 * These are lightweight smoke tests — they confirm the pages compile and
 * that the observe-only constraint is respected.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── Mock dependencies ──────────────────────────────────────────────────────────

// Mock API service
vi.mock('@/services/api', () => ({
  api: {
    getCommandCenter: vi.fn().mockResolvedValue(null),
    getEvidence: vi.fn().mockResolvedValue(null),
    getResearch: vi.fn().mockResolvedValue(null),
    getBotStatus: vi.fn().mockResolvedValue(null),
    getRealGridHealth: vi.fn().mockResolvedValue(null),
    getRiskStatus: vi.fn().mockResolvedValue(null),
    getPolyPaperStatus: vi.fn().mockResolvedValue(null),
    getPolyPaperPositions: vi.fn().mockResolvedValue([]),
    getPolyPaperPerformance: vi.fn().mockResolvedValue(null),
  },
}));

// Mock monitoring service
vi.mock('@/services/monitoring', () => ({
  monitoringService: {
    getHealth: vi.fn().mockResolvedValue({ status: 'healthy', redis_connected: true }),
  },
}));

// Mock translation — return key as string
vi.mock('@/i18n/translations', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    locale: 'th',
  }),
  TranslationKey: {} as any,
}));

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => '/th/dashboard',
}));

// ── Forbidden button patterns ──────────────────────────────────────────────────

const FORBIDDEN_PATTERNS = [
  /start(?:\s+bot|\s+trading|\s+grid)?/i,
  /trade(?:\s+now|\s+this|\s+crypto)?/i,
  /configure/i,
  /reset(?:\s+all|\s+data|\s+bot)?/i,
  /execute/i,
  /place\s+order/i,
  /submit\s+trade/i,
];

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('Contract: Page modules can be imported', () => {
  it('imports Today (Command Center) page', async () => {
    const mod = await import('@/app/[lang]/dashboard/page');
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe('function');
  });

  it('imports Evidence page', async () => {
    const mod = await import('@/app/[lang]/dashboard/evidence/page');
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe('function');
  });

  it('imports Research page', async () => {
    const mod = await import('@/app/[lang]/dashboard/research/page');
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe('function');
  });

  it('imports System page', async () => {
    const mod = await import('@/app/[lang]/dashboard/system/page');
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe('function');
  });

  it('imports Daily Report page', async () => {
    const mod = await import('@/app/[lang]/dashboard/daily-report/page');
    expect(mod.default).toBeDefined();
    expect(typeof mod.default).toBe('function');
  });
});

describe('Contract: No forbidden action buttons in page source', () => {
  // Read page source files and verify no forbidden button text exists
  // This is a static analysis approach — checks the source code directly

  const pages = [
    { name: 'Today', path: '@/app/[lang]/dashboard/page' },
    { name: 'Evidence', path: '@/app/[lang]/dashboard/evidence/page' },
    { name: 'Research', path: '@/app/[lang]/dashboard/research/page' },
    { name: 'System', path: '@/app/[lang]/dashboard/system/page' },
    { name: 'Daily Report', path: '@/app/[lang]/dashboard/daily-report/page' },
  ];

  for (const page of pages) {
    it(`${page.name} page has no forbidden action buttons`, async () => {
      // Dynamic import to get the module source
      const fs = await import('fs');
      const pathModule = await import('path');
      
      // Resolve the file path relative to the project src directory
      const srcDir = pathModule.resolve(process.cwd(), 'src');
      const filePath = page.path
        .replace('@/', '')
        .replace('[lang]', '[lang]');
      const fullPath = pathModule.join(srcDir, filePath + '.tsx');
      
      const source = fs.readFileSync(fullPath, 'utf-8');
      
      // Check for forbidden button patterns in JSX text content
      // We look for button elements with forbidden text
      for (const pattern of FORBIDDEN_PATTERNS) {
        // Match button/Btn elements containing forbidden text
        const buttonRegex = new RegExp(
          `<(?:button|Button|Btn)[^>]*>[^<]*${pattern.source}[^<]*</(?:button|Button|Btn)>`,
          'gi'
        );
        const matches = source.match(buttonRegex);
        expect(matches, `Found forbidden button in ${page.name}: ${matches?.join(', ')}`).toBeNull();
      }
    });
  }
});
