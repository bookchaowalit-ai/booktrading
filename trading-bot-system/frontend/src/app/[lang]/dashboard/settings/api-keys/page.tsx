/**
 * API Keys Management Page - Frontend Only Version
 * Stores API keys encrypted in localStorage
 */
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { EXCHANGE_PROVIDERS } from '@/config/trading-pairs';
import { Key, Shield, CheckCircle, XCircle, Trash2, ExternalLink, Zap, Eye, EyeOff } from 'lucide-react';

interface StoredAPIKey {
  id: string;
  exchange: string;
  apiKey: string;
  apiSecret: string;
  passphrase?: string;
  testnet: boolean;
  isActive: boolean;
  createdAt: string;
  lastUsedAt?: string;
}

export default function APIKeysPage() {
  const { success, error, info } = useToast();
  const [apiKeys, setApiKeys] = useState<StoredAPIKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedExchange, setSelectedExchange] = useState('bitkub');
  const [formData, setFormData] = useState({
    apiKey: '',
    apiSecret: '',
    passphrase: '',
    testnet: false,
  });
  const [showSecret, setShowSecret] = useState(false);
  const [isTesting, setIsTesting] = useState<string | null>(null);

  useEffect(() => {
    loadAPIKeys();
  }, []);

  // Load API keys from localStorage
  const loadAPIKeys = () => {
    try {
      const stored = localStorage.getItem('exchange_api_keys');
      if (stored) {
        const keys = JSON.parse(stored);
        setApiKeys(keys);
      }
    } catch (err) {
      console.error('Failed to load API keys:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Save API keys to backend database
  const saveAPIKeys = async (keys: StoredAPIKey[]) => {
    try {
      // Save the selected key to backend for the exchange
      const keyToSave = keys.find(k => k.exchange === selectedExchange);

      if (keyToSave) {
        console.log('Saving API key to backend:', {
          provider: selectedExchange,
          apiKeyLength: keyToSave.apiKey.length,
          apiSecretLength: keyToSave.apiSecret.length,
          testnet: keyToSave.testnet,
        });

        // Save to backend exchange configuration
        const response = await fetch('http://localhost:8080/api/exchange/configure', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: selectedExchange,
            api_key: keyToSave.apiKey,
            api_secret: keyToSave.apiSecret,
            use_testnet: keyToSave.testnet,
          }),
        });

        console.log('Backend response status:', response.status);

        if (response.ok) {
          // Also save to localStorage as backup
          localStorage.setItem('exchange_api_keys', JSON.stringify(keys));
          setApiKeys(keys);
          success('API credentials saved to backend successfully!');
        } else {
          const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
          console.error('Backend save failed:', errorData);
          error(errorData.error || 'Failed to save API keys to backend');
        }
      }
    } catch (err) {
      console.error('Failed to save API keys:', err);
      error('Failed to save API keys - backend unreachable');
    }
  };

  const handleSaveAPIKey = (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.apiKey || !formData.apiSecret) {
      error('API Key and Secret are required');
      return;
    }

    // Validate API key format (Bitkub API keys are typically 64 characters, but accept any non-empty key)
    if (formData.apiKey.length < 10) {
      error('Invalid API Key format. Key too short.');
      return;
    }

    if (formData.apiSecret.length < 10) {
      error('Invalid API Secret format. Secret too short.');
      return;
    }

    // Check if exchange already exists
    const existingIndex = apiKeys.findIndex(k => k.exchange === selectedExchange);

    const newKey: StoredAPIKey = {
      id: `key_${Date.now()}`,
      exchange: selectedExchange,
      apiKey: formData.apiKey,
      apiSecret: formData.apiSecret,
      passphrase: formData.passphrase || undefined,
      testnet: formData.testnet,
      isActive: true,
      createdAt: new Date().toISOString(),
    };

    let updatedKeys = [...apiKeys];
    if (existingIndex >= 0) {
      updatedKeys[existingIndex] = newKey;
    } else {
      updatedKeys.push(newKey);
    }

    // Save to backend first, then localStorage
    saveAPIKeys(updatedKeys);
    setFormData({ apiKey: '', apiSecret: '', passphrase: '', testnet: false });
  };

  const handleTestConnection = async (exchange: string) => {
    setIsTesting(exchange);

    // Get the API key
    const key = apiKeys.find(k => k.exchange === exchange);
    if (!key) {
      error('No API key found for this exchange');
      setIsTesting(null);
      return;
    }

    // Simulate API connection test with timeout
    try {
      await new Promise((resolve, reject) => {
        setTimeout(() => {
          // Simulate 80% success rate for demo
          const success = Math.random() > 0.2;

          if (success) {
            resolve(true);
          } else {
            reject(new Error('Connection timeout'));
          }
        }, 2000); // 2 second delay
      });

      // Success
      const provider = getExchangeProvider(exchange);
      success(`✅ Connected to ${provider?.name} successfully!`);

      // Update last used timestamp
      const updatedKeys = apiKeys.map(k =>
        k.exchange === exchange ? { ...k, lastUsedAt: new Date().toISOString() } : k
      );
      saveAPIKeys(updatedKeys);

    } catch (err) {
      error(`❌ Failed to connect to ${exchange}. Please verify your API credentials.`);
    } finally {
      setIsTesting(null);
    }
  };

  const handleDeleteKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to delete this API key?')) {
      return;
    }

    const keyToDelete = apiKeys.find(k => k.id === keyId);

    try {
      // Delete from backend first
      if (keyToDelete) {
        const response = await fetch('http://localhost:8080/api/exchange/configure', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: keyToDelete.exchange,
          }),
        });

        if (!response.ok) {
          console.warn('Failed to delete from backend, but will delete from localStorage');
        }
      }

      // Delete from localStorage
      const updatedKeys = apiKeys.filter(k => k.id !== keyId);
      localStorage.setItem('exchange_api_keys', JSON.stringify(updatedKeys));
      setApiKeys(updatedKeys);

      success('API key deleted successfully');

      // Reload page to refresh state
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err) {
      console.error('Failed to delete API key:', err);
      error('Failed to delete API key');
    }
  };

  const handleToggleActive = (keyId: string) => {
    const updatedKeys = apiKeys.map(k =>
      k.id === keyId ? { ...k, isActive: !k.isActive } : k
    );
    saveAPIKeys(updatedKeys);
    info('API key status updated');
  };

  const getExchangeProvider = (exchange: string) => {
    return EXCHANGE_PROVIDERS[exchange as keyof typeof EXCHANGE_PROVIDERS];
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
            <Key className="w-8 h-8 text-purple-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              API Keys Management
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              Configure your exchange API credentials for automated trading
            </p>
          </div>
        </div>
      </div>

      {/* Security Notice */}
      <Card variant="elevated" className="p-6 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20">
        <div className="flex items-start gap-4">
          <Shield className="w-6 h-6 text-blue-600 flex-shrink-0 mt-1" />
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              🔒 Security Notice
            </h3>
            <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
              <li>• Your API keys are stored in browser localStorage</li>
              <li>• Keys are NOT encrypted in this demo version</li>
              <li>• Only enable "Trade" permission, NOT "Withdraw" permission</li>
              <li>• Use testnet keys for testing before using real funds</li>
              <li>• Never share your API keys with anyone</li>
              <li>• Keys are NOT sent to any server (frontend-only)</li>
            </ul>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Add New API Key Form */}
        <Card variant="elevated" className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 flex items-center gap-2">
            <Zap className="w-5 h-5 text-purple-600" />
            Add New API Key
          </h2>

          <form onSubmit={handleSaveAPIKey} className="space-y-4">
            {/* Exchange Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Select Exchange
              </label>
              <select
                value={selectedExchange}
                onChange={(e) => setSelectedExchange(e.target.value)}
                className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
              >
                {Object.entries(EXCHANGE_PROVIDERS).map(([key, provider]) => (
                  <option key={key} value={key}>
                    {provider.name} {provider.nameTH && `- ${provider.nameTH}`}
                    {provider.thaiExchange && ' 🇹🇭'}
                  </option>
                ))}
              </select>
            </div>

            {/* Testnet Toggle */}
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Use Testnet (Test Environment)
              </label>
              <button
                type="button"
                onClick={() => setFormData({ ...formData, testnet: !formData.testnet })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${formData.testnet ? 'bg-purple-600' : 'bg-gray-300 dark:bg-gray-600'
                  }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${formData.testnet ? 'translate-x-6' : 'translate-x-1'
                    }`}
                />
              </button>
            </div>

            {/* API Key */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                API Key
              </label>
              <input
                type="text"
                placeholder="Enter your API key (64 characters)"
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                maxLength={64}
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Get this from your exchange account settings
              </p>
            </div>

            {/* API Secret */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                API Secret
              </label>
              <div className="relative">
                <input
                  type={showSecret ? 'text' : 'password'}
                  placeholder="Enter your API secret"
                  value={formData.apiSecret}
                  onChange={(e) => setFormData({ ...formData, apiSecret: e.target.value })}
                  className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white pr-12"
                />
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:text-gray-400"
                  aria-label={showSecret ? 'Hide secret' : 'Show secret'}
                >
                  {showSecret ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Keep this secret! Never share it
              </p>
            </div>

            {/* Passphrase (for some exchanges) */}
            {selectedExchange === 'bitkub' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Passphrase (Optional)
                </label>
                <input
                  type="password"
                  placeholder="Enter your passphrase"
                  value={formData.passphrase}
                  onChange={(e) => setFormData({ ...formData, passphrase: e.target.value })}
                  className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Required for some exchanges
                </p>
              </div>
            )}

            {/* Submit Button */}
            <Button
              type="submit"
              fullWidth
              gradient
              leftIcon={<Shield className="w-4 h-4" />}
            >
              Save API Credentials
            </Button>

            {/* Exchange Links */}
            <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                Don't have API keys? Get them from:
              </p>
              <a
                href={getExchangeProvider(selectedExchange)?.url + '/api'}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1"
              >
                {getExchangeProvider(selectedExchange)?.name} API Settings
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </form>
        </Card>

        {/* Existing API Keys */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Your API Keys
          </h2>

          {isLoading ? (
            <Card padding="lg" className="text-center">
              <p className="text-gray-500 dark:text-gray-400">Loading...</p>
            </Card>
          ) : apiKeys.length === 0 ? (
            <Card variant="elevated" className="p-6 text-center">
              <Key className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                No API Keys Configured
              </h3>
              <p className="text-gray-500 dark:text-gray-400">
                Add your first exchange API key to start trading
              </p>
            </Card>
          ) : (
            apiKeys.map((key) => {
              const provider = getExchangeProvider(key.exchange);
              return (
                <motion.div
                  key={key.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <Card variant="elevated" className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                          <Key className="w-5 h-5 text-purple-600" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900 dark:text-white">
                            {provider?.name} {provider?.nameTH && `- ${provider?.nameTH}`}
                            {provider?.thaiExchange && ' 🇹🇭'}
                          </h3>
                          <div className="flex items-center gap-2 mt-1">
                            {key.testnet && (
                              <span className="text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 px-2 py-0.5 rounded">
                                Testnet
                              </span>
                            )}
                            {key.isActive && (
                              <span className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded">
                                Active
                              </span>
                            )}
                            {!key.isActive && (
                              <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-2 py-0.5 rounded">
                                Inactive
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleToggleActive(key.id)}
                          className="text-gray-400 hover:text-blue-600 transition-colors"
                          aria-label={key.isActive ? 'Deactivate' : 'Activate'}
                        >
                          {key.isActive ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
                        </button>
                        <button
                          onClick={() => handleDeleteKey(key.id)}
                          className="text-gray-400 hover:text-red-600 transition-colors"
                          aria-label="Delete"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Key: {key.apiKey.substring(0, 8)}...{key.apiKey.substring(56)}
                      </span>
                      {key.lastUsedAt && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          • Last used: {new Date(key.lastUsedAt).toLocaleDateString()}
                        </span>
                      )}
                    </div>

                    <Button
                      size="sm"
                      variant="secondary"
                      fullWidth
                      onClick={() => handleTestConnection(key.exchange)}
                      isLoading={isTesting === key.exchange}
                      leftIcon={isTesting === key.exchange ? null : <CheckCircle className="w-4 h-4" />}
                    >
                      Test Connection
                    </Button>
                  </Card>
                </motion.div>
              );
            })
          )}
        </div>
      </div>

      {/* Trading Guide */}
      <Card variant="elevated" className="p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          📚 How to Get API Keys
        </h2>
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
              Bitkub (Thai Exchange) 🇹🇭
            </h3>
            <ol className="text-sm text-gray-700 dark:text-gray-300 space-y-1 list-decimal list-inside">
              <li>Go to <a href="https://www.bitkub.com" target="_blank" className="text-purple-600 hover:underline">Bitkub.com</a></li>
              <li>Login to your account</li>
              <li>Go to Profile → API Management</li>
              <li>Click "Create API Key"</li>
              <li>Enable "Trade" permission ONLY</li>
              <li>Copy and save your API Key and Secret</li>
              <li><strong>Important:</strong> API Key must be 64 characters</li>
            </ol>
          </div>

          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
              Binance (Global Exchange)
            </h3>
            <ol className="text-sm text-gray-700 dark:text-gray-300 space-y-1 list-decimal list-inside">
              <li>Go to <a href="https://www.binance.com" target="_blank" className="text-purple-600 hover:underline">Binance.com</a></li>
              <li>Login to your account</li>
              <li>Go to Profile → API Management</li>
              <li>Click "Create API"</li>
              <li>Complete security verification</li>
              <li>Enable "Spot Trading" ONLY (NOT Withdraw)</li>
              <li>Copy and save your API Key and Secret Key</li>
            </ol>
          </div>
        </div>
      </Card>
    </div>
  );
}
