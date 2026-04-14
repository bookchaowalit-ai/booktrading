/**
 * Login Modal Component
 * Modern, secure login modal with email/password and register options
 */
'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Mail, Lock, Eye, EyeOff, AlertCircle, User } from 'lucide-react';
import { authenticate, register } from '@/services/auth';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess?: () => void;
}

export default function LoginModal({ isOpen, onClose, onLoginSuccess }: LoginModalProps) {
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setIsLoading(true);

    try {
      if (isRegister) {
        const result = await register(email, password, name);
        if (result.success) {
          setSuccess('Account created successfully! Redirecting...');
          setTimeout(() => {
            onClose();
            onLoginSuccess?.();
            const locale = typeof window !== 'undefined' ? window.location.pathname.split('/')[1] || 'en' : 'en';
            window.location.href = `/${locale}/dashboard`;
          }, 1000);
        } else {
          setError(result.error || 'Registration failed');
        }
      } else {
        const result = await authenticate(email, password);
        if (result.success) {
          onClose();
          onLoginSuccess?.();
          const locale = typeof window !== 'undefined' ? window.location.pathname.split('/')[1] || 'en' : 'en';
          // Use setTimeout to ensure localStorage is flushed before redirect
          setTimeout(() => {
            window.location.href = `/${locale}/dashboard`;
          }, 200);
        } else {
          setError(result.error || 'Login failed');
        }
      }
    } catch {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsLoading(false);
    }
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
            role="dialog"
            aria-modal="true"
            aria-labelledby="auth-modal-title"
          >
            <div className="bg-slate-900 rounded-2xl border border-slate-700 w-full max-w-md shadow-2xl">
              {/* Header */}
              <div className="flex justify-between items-center p-6 border-b border-slate-700">
                <div>
                  <h2 id="auth-modal-title" className="text-2xl font-bold text-white">
                    {isRegister ? 'Create Account' : 'Welcome Back'}
                  </h2>
                  <p className="text-gray-400 text-sm mt-1">
                    {isRegister ? 'Register to get started' : 'Sign in to your account'}
                  </p>
                </div>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-white transition"
                  aria-label="Close dialog"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              {/* Body */}
              <div className="p-6">
                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* Name (Register only) */}
                  {isRegister && (
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Full Name
                      </label>
                      <div className="relative">
                        <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                        <input
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          className="w-full bg-slate-800 border border-slate-600 text-white pl-10 pr-4 py-3 rounded-lg focus:outline-none focus:border-purple-500 transition"
                          placeholder="John Doe"
                          required
                          minLength={2}
                        />
                      </div>
                    </div>
                  )}

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
                        minLength={8}
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

                  {/* Error Message */}
                  {error && (
                    <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 p-3 rounded-lg">
                      <AlertCircle className="w-4 h-4" />
                      {error}
                    </div>
                  )}

                  {/* Success Message */}
                  {success && (
                    <div className="text-green-400 text-sm bg-green-900/20 p-3 rounded-lg">
                      {success}
                    </div>
                  )}

                  {/* Submit Button */}
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 text-white py-3 rounded-lg font-semibold transition disabled:cursor-not-allowed"
                  >
                    {isLoading
                      ? 'Processing...'
                      : isRegister
                        ? 'Create Account'
                        : 'Sign In'}
                  </button>
                </form>

                {/* Toggle Register/Login */}
                <p className="text-center text-gray-400 text-sm mt-6">
                  {isRegister ? (
                    <>
                      Already have an account?{' '}
                      <button
                        onClick={() => {
                          setIsRegister(false);
                          setError('');
                          setSuccess('');
                        }}
                        className="text-purple-400 hover:text-purple-300 font-medium transition"
                      >
                        Sign in
                      </button>
                    </>
                  ) : (
                    <>
                      Don't have an account?{' '}
                      <button
                        onClick={() => {
                          setIsRegister(true);
                          setError('');
                          setSuccess('');
                        }}
                        className="text-purple-400 hover:text-purple-300 font-medium transition"
                      >
                        Sign up for free
                      </button>
                    </>
                  )}
                </p>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
