/**
 * Authentication Service
 * Connects to backend /api/auth endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

export interface AuthResult {
  success: boolean;
  user?: User;
  token?: string;
  error?: string;
}

/**
 * Authenticate user via backend API
 */
export async function authenticate(email: string, password: string): Promise<AuthResult> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({ error: 'Invalid email or password' }));
      return { success: false, error: data.error || 'Invalid email or password' };
    }

    const data: { token: string; user: User } = await response.json();

    localStorage.setItem('auth_token', data.token);
    localStorage.setItem('user', JSON.stringify(data.user));

    return { success: true, user: data.user, token: data.token };
  } catch {
    return { success: false, error: 'Unable to connect to server' };
  }
}

/**
 * Get current authenticated user (from localStorage)
 */
export function getCurrentUser(): User | null {
  if (typeof window === 'undefined') return null;
  const userStr = localStorage.getItem('user');
  if (userStr) {
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  if (typeof window === 'undefined') return false;
  return !!localStorage.getItem('auth_token');
}

/**
 * Logout user
 */
export async function logout(): Promise<void> {
  const token = localStorage.getItem('auth_token');
  if (token) {
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user');
}

/**
 * Get the stored auth token
 */
export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('auth_token');
}

/**
 * Demo credentials for display on login screen
 */
export function getDemoCredentials() {
  return [
    { email: 'demo@tradepro.com', password: 'demo123', name: 'Demo Trader', role: 'trader' },
    { email: 'admin@tradepro.com', password: 'admin123', name: 'Admin User', role: 'admin' },
  ];
}
