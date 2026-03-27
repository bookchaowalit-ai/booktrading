/**
 * Demo Authentication Service
 * Simple in-memory auth for demo purposes
 */

// Demo users for testing
export const demoUsers = [
  {
    id: '1',
    email: 'demo@tradepro.com',
    password: 'demo123',
    name: 'Demo Trader',
    role: 'trader'
  },
  {
    id: '2',
    email: 'admin@tradepro.com',
    password: 'admin123',
    name: 'Admin User',
    role: 'admin'
  }
];

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
 * Authenticate user (demo implementation)
 */
export function authenticate(email: string, password: string): AuthResult {
  const user = demoUsers.find(u => u.email === email && u.password === password);
  
  if (user) {
    // Create a simple token (in production, use JWT)
    const token = btoa(JSON.stringify({ ...user, iat: Date.now() }));
    
    // Store in localStorage
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role
    }));
    
    return {
      success: true,
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role
      },
      token
    };
  }
  
  return {
    success: false,
    error: 'Invalid email or password'
  };
}

/**
 * Get current authenticated user
 */
export function getCurrentUser(): User | null {
  const userStr = localStorage.getItem('user');
  if (userStr) {
    return JSON.parse(userStr);
  }
  return null;
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return !!localStorage.getItem('auth_token');
}

/**
 * Logout user
 */
export function logout(): void {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user');
}

/**
 * Get demo credentials for display
 */
export function getDemoCredentials() {
  return demoUsers.map(({ email, password, name, role }) => ({
    email,
    password,
    name,
    role
  }));
}
