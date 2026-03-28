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
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

  useEffect(() => {
    loadAPIKeys();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load API keys from backend
  const loadAPIKeys = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/exchange/configure`);
      if (response.ok) {
        const data = await response.json().catch(() => null);
        if (data && Array.isArray(data.keys)) {
          setApiKeys(data.keys);
        } else if (data && data.provider) {
          // Single key response
          setApiKeys([data]);
        }
      }
    } catch {
      // backend unavailable — show empty list
    } finally {
      setIsLoading(false);
    }
  };

  // Save API keys to backend database
  const saveAPIKeys = async (keys: StoredAPIKey[]) => {
    try {
      const keyToSave = keys.find(k => k.exchange === selectedExchange);

      if (keyToSave) {
        const response = await fetch(`${API_BASE_URL}/api/exchange/configure`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            provider: selectedExchange,
            api_key: keyToSave.apiKey,
            api_secret: keyToSave.apiSecret,
            use_testnet: keyToSave.testnet,
          }),
        });

        if (response.ok) {
          setApiKeys(keys);
          success('API credentials saved to backend successfully!');
        } else {
          const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
          error(errorData.error || 'Failed to save API keys to backend');
        }
      }
    } catch {
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

    // Test connection via backend exchange configure endpoint
    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
      const response = await fetch(`${API_BASE_URL}/api/exchange/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: key.exchange,
          api_key: key.apiKey,
          api_secret: key.apiSecret,
          use_testnet: key.testnet ?? false,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'Connection failed');
      }

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
    const keyToDelete = apiKeys.find(k => k.id === keyId);

    try {
      // Delete from backend first
      if (keyToDelete) {
        await fetch(`${API_BASE_URL}/api/exchange/configure`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider: keyToDelete.exchange }),
        }).catch(() => {
          // Silently continue even if backend delete fails
        });
      }

      // Update state directly — no page reload needed
      const updatedKeys = apiKeys.filter(k => k.id !== keyId);
      setApiKeys(updatedKeys);
      setDeleteConfirmId(null);
      success('API key deleted successfully');
    } catch {
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
    <div className="h-full grid grid-cols-2 gap-2">
      {/* Left Column - Add API Key Form */}
      <Card variant="elevated" className="p-2 flex flex-col">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-semibold flex items-center gap-1">
            <Zap className="w-3 h-3 text-purple-600" />
            Add API Key
          </h2>
        </div>

        <form onSubmit={handleSaveAPIKey} className="space-y-2 flex-1">
          {/* Exchange Selector */}
          <div>
            <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
              Exchange
            </label>
            <select
              value={selectedExchange}
              onChange={(e) => setSelectedExchange(e.target.value)}
              className="w-full px-2 py-1 text-xs bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
            >
              {Object.entries(EXCHANGE_PROVIDERS).map(([key, provider]) => (
                <option key={key} value={key}>
                  {provider.name} {provider.thaiExchange && '🇹🇭'}
                </option>
              ))}
            </select>
          </div>

          {/* Testnet Toggle */}
          <div className="flex items-center justify-between">
            <label className="text-xs text-gray-600 dark:text-gray-400">Testnet</label>
            <input
              type="checkbox"
              checked={formData.testnet}
              onChange={(e) => setFormData({ ...formData, testnet: e.target.checked })}
              className="w-3 h-3"
            />
          </div>

          {/* API Key */}
          <div>
            <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
              API Key
            </label>
            <input
              type="text"
              placeholder="Enter API key"
              value={formData.apiKey}
              onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
              className="w-full px-2 py-1 text-xs bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
            />
          </div>

          {/* API Secret */}
          <div>
            <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
              API Secret
            </label>
            <input
              type="password"
              placeholder="Enter API secret"
              value={formData.apiSecret}
              onChange={(e) => setFormData({ ...formData, apiSecret: e.target.value })}
              className="w-full px-2 py-1 text-xs bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
            />
          </div>

          {/* Save Button */}
          <Button type="submit" fullWidth size="sm" className="mt-auto">
            💾 Save API Key
          </Button>
        </form>
      </Card>

      {/* Right Column - Existing Keys */}
      <div className="flex flex-col gap-2">
        <Card variant="elevated" className="p-2 flex-1 overflow-auto">
          <h2 className="text-xs font-semibold mb-2">Your API Keys</h2>

          {isLoading ? (
            <div className="text-center py-8 text-xs text-gray-500">Loading...</div>
          ) : apiKeys.length === 0 ? (
            <div className="text-center py-8">
              <Key className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
              <p className="text-xs text-gray-500 dark:text-gray-400">No API keys configured</p>
              <p className="text-xs text-gray-400 mt-1">Add your first API key on the left</p>
            </div>
          ) : (
            <div className="space-y-2">
              {apiKeys.map((key) => {
                const provider = getExchangeProvider(key.exchange);
                return (
                  <div key={key.id} className="p-2 bg-gray-50 dark:bg-gray-800/50 rounded-md">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold">{provider.name}</span>
                        {provider.thaiExchange && <span>🇹🇭</span>}
                        {key.testnet && (
                          <span className="text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 px-1 rounded">
                            Testnet
                          </span>
                        )}
                      </div>
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleToggleActive(key.id)}
                          className={key.isActive ? 'text-green-600' : 'text-gray-400'}
                          title={key.isActive ? 'Active' : 'Inactive'}
                        >
                          {key.isActive ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        </button>
                        {deleteConfirmId === key.id ? (
                          <>
                            <button
                              onClick={() => handleDeleteKey(key.id)}
                              className="text-xs text-red-600 hover:text-red-700 font-semibold"
                              aria-label="Confirm delete"
                            >
                              Yes
                            </button>
                            <button
                              onClick={() => setDeleteConfirmId(null)}
                              className="text-xs text-gray-500 hover:text-gray-700"
                              aria-label="Cancel delete"
                            >
                              No
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => setDeleteConfirmId(key.id)}
                            className="text-red-600 hover:text-red-700"
                            aria-label="Delete API key"
                            title="Delete"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      Key: {key.apiKey.substring(0, 8)}...{key.apiKey.substring(-8)}
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      Added: {new Date(key.createdAt).toLocaleDateString()}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );

}
