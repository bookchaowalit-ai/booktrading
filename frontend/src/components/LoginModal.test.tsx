import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, initial: _i, animate: _a, exit: _e, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

const getAuthConfig = vi.fn();
vi.mock('@/services/auth', async (orig) => ({
  ...(await orig<typeof import('@/services/auth')>()),
  getAuthConfig: () => getAuthConfig(),
}));

import LoginModal from './LoginModal';

describe('LoginModal sign-up link', () => {
  afterEach(() => {
    getAuthConfig.mockReset();
  });

  it('hides sign-up when registration is closed', async () => {
    getAuthConfig.mockResolvedValue({ registrationOpen: false, inviteRequired: false });
    render(<LoginModal isOpen onClose={() => {}} />);
    await waitFor(() => expect(getAuthConfig).toHaveBeenCalled());
    expect(await screen.findByTestId('registration-closed')).toBeInTheDocument();
    expect(screen.queryByText('Sign up for free')).not.toBeInTheDocument();
  });

  it('offers sign-up and an invite field when invite-only', async () => {
    getAuthConfig.mockResolvedValue({ registrationOpen: true, inviteRequired: true });
    render(<LoginModal isOpen onClose={() => {}} />);
    const link = await screen.findByText('Sign up for free');
    link.click();
    expect(await screen.findByLabelText(/Invite Code/)).toBeInTheDocument();
  });
});
