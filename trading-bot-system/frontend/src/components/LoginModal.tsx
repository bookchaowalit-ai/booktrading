/**
 * Login Modal Component
 * Modern, secure login modal with email/password and social login options
 */
'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Mail, Lock, Eye, EyeOff, AlertCircle, CheckCircle, Key } from 'lucide-react';
import { authenticate, getDemoCredentials } from '@/services/auth';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess?: () => void;
}

export default function LoginModal({ isOpen, onClose, onLoginSuccess }: LoginModalProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [showDemoCredentials, setShowDemoCredentials] = useState(false);

  const demoCredentials = getDemoCredentials();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const result = authenticate(email, password);

      if (result.success) {
        // Login successful
        onClose();
        if (onLoginSuccess) {
          onLoginSuccess();
        }
        // Get current locale from pathname or default to 'en'
        const currentLocale = typeof window !== 'undefined'
          ? window.location.pathname.split('/')[1]
          : 'en';

        // Redirect to dashboard with locale
        window.location.href = `/${currentLocale}/dashboard`;
      } else {
        setError(result.error || 'Login failed');
      }
    } catch (err) {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = (email: string, password: string) => {
    setEmail(email);
    setPassword(password);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed inset-0 flex items-center justify-center z-50 px-4"
          >
            <div className="bg-slate-900 rounded-2xl border border-slate-700 w-full max-w-md shadow-2xl">
              {/* Header */}
              <div className="flex justify-between items-center p-6 border-b border-slate-700">
                <div>
                  <h2 className="text-2xl font-bold text-white">Welcome Back</h2>
                  <p className="text-gray-400 text-sm mt-1">Sign in to your account</p>
                </div>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-white transition"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              {/* Body */}
              <div className="p-6">
                {/* Demo Credentials Info */}
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
                  <div className="flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-100 mb-2">
                        Demo Login Credentials
                      </h3>
                      <div className="space-y-2 text-sm">
                        {demoCredentials.map((cred, index) => (
                          <div key={index} className="flex items-center justify-between gap-2">
                            <div className="text-blue-800 dark:text-blue-200">
                              <span className="font-medium">{cred.name}</span> ({cred.role})
                            </div>
                            <button
                              onClick={() => handleDemoLogin(cred.email, cred.password)}
                              className="text-xs bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-300 px-2 py-1 rounded hover:bg-blue-200 dark:hover:bg-blue-700 transition"
                            >
                              Use These
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Login Form */}
                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* Email */}
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Email Address
                    </label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-600 text-white pl-10 pr-4 py-3 rounded-lg focus:outline-none focus:border-purple-500 transition"
                        placeholder="you@example.com"
                        required
                      />
                    </div>
                  </div>

                  {/* Password */}
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Password
                    </label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-600 text-white pl-10 pr-12 py-3 rounded-lg focus:outline-none focus:border-purple-500 transition"
                        placeholder="••••••••"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                  </div>

                  {/* Remember Me & Forgot Password */}
                  <div className="flex items-center justify-between">
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={rememberMe}
                        onChange={(e) => setRememberMe(e.target.checked)}
                        className="w-4 h-4 rounded border-slate-600 text-purple-600 focus:ring-purple-500 bg-slate-800"
                      />
                      <span className="ml-2 text-sm text-gray-300">Remember me</span>
                    </label>
                    <a href="#" className="text-sm text-purple-400 hover:text-purple-300 transition">
                      Forgot password?
                    </a>
                  </div>

                  {/* Error Message */}
                  {error && (
                    <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 p-3 rounded-lg">
                      <AlertCircle className="w-4 h-4" />
                      {error}
                    </div>
                  )}

                  {/* Submit Button */}
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 text-white py-3 rounded-lg font-semibold transition disabled:cursor-not-allowed"
                  >
                    {isLoading ? 'Signing in...' : 'Sign In'}
                  </button>
                </form>

                {/* Sign Up Link */}
                <p className="text-center text-gray-400 text-sm mt-6">
                  Don't have an account?{' '}
                  <a href="#" className="text-purple-400 hover:text-purple-300 font-medium transition">
                    Sign up for free
                  </a>
                </p>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
