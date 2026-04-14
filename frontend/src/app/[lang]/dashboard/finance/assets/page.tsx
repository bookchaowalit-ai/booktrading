/**
 * Finance Assets Page
 * Manage physical and intangible assets (real estate, vehicles, jewelry, etc.)
 */
'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import {
  Plus, Edit2, Trash2, Home, Car, Gem, Briefcase, Building2,
  TrendingUp, TrendingDown, DollarSign, X, Check
} from 'lucide-react';

// Simple types
interface AssetData {
  id?: string;
  name: string;
  type: string;
  description?: string;
  purchasePrice: number;
  currentValue: number;
  currency: string;
  purchaseDate?: string;
  location?: string;
  created_at?: string;
  updated_at?: string;
}

const ASSET_TYPES = [
  { value: 'real_estate', label: 'Real Estate', icon: <Home className="w-5 h-5" />, color: '#8B5CF6' },
  { value: 'vehicle', label: 'Vehicle', icon: <Car className="w-5 h-5" />, color: '#3B82F6' },
  { value: 'jewelry', label: 'Jewelry', icon: <Gem className="w-5 h-5" />, color: '#EC4899' },
  { value: 'collectibles', label: 'Collectibles', icon: <Briefcase className="w-5 h-5" />, color: '#F59E0B' },
  { value: 'business', label: 'Business', icon: <Building2 className="w-5 h-5" />, color: '#10B981' },
  { value: 'other', label: 'Other', icon: <DollarSign className="w-5 h-5" />, color: '#6366F1' },
];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function AssetsPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning } = useToast();

  const [assets, setAssets] = useState<AssetData[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingAsset, setEditingAsset] = useState<AssetData | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    type: 'real_estate',
    description: '',
    purchasePrice: 0,
    currentValue: 0,
    currency: 'THB',
    purchaseDate: '',
    location: '',
  });

  useEffect(() => {
    loadAssets();
  }, []);

  const loadAssets = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/finance/assets`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        // Endpoint may not exist yet
        setAssets([]);
        return;
      }
      const data = await response.json();
      setAssets(Array.isArray(data) ? data : []);
    } catch {
      // API not available
      setAssets([]);
    } finally {
      setLoading(false);
    }
  };

  const openNewAsset = () => {
    setEditingAsset(null);
    setFormData({
      name: '',
      type: 'real_estate',
      description: '',
      purchasePrice: 0,
      currentValue: 0,
      currency: 'THB',
      purchaseDate: '',
      location: '',
    });
    setShowModal(true);
  };

  const openEditAsset = (asset: AssetData) => {
    setEditingAsset(asset);
    setFormData({
      name: asset.name || '',
      type: asset.type || 'real_estate',
      description: asset.description || '',
      purchasePrice: asset.purchasePrice || 0,
      currentValue: asset.currentValue || 0,
      currency: asset.currency || 'THB',
      purchaseDate: asset.purchaseDate || '',
      location: asset.location || '',
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formData.name) {
      warning('Asset name is required');
      return;
    }

    try {
      const newAsset: AssetData = {
        id: editingAsset?.id || `asset_${Date.now()}`,
        ...formData,
      };

      if (editingAsset) {
        setAssets(assets.map(a => a.id === editingAsset.id ? { ...a, ...formData } : a));
        success('Asset updated');
      } else {
        setAssets([...assets, newAsset]);
        success('Asset added');
      }
      setShowModal(false);
    } catch (err: any) {
      showError(err.message || 'Failed to save asset');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this asset?')) return;
    try {
      setAssets(assets.filter(a => a.id !== id));
      success('Asset deleted');
    } catch (err: any) {
      showError(err.message || 'Failed to delete asset');
    }
  };

  const formatCurrency = (amount: number, currency: string = 'THB') => {
    try {
      return new Intl.NumberFormat('th-TH', {
        style: 'currency',
        currency,
        minimumFractionDigits: 0,
      }).format(amount);
    } catch {
      return `${amount.toLocaleString()} ${currency}`;
    }
  };

  const totalValue = assets.reduce((sum, a) => sum + (a.currentValue || 0), 0);
  const totalPurchase = assets.reduce((sum, a) => sum + (a.purchasePrice || 0), 0);
  const totalGainLoss = totalValue - totalPurchase;
  const gainLossPercent = totalPurchase > 0 ? (totalGainLoss / totalPurchase) * 100 : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading assets...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Assets</h1>
          <p className="text-gray-500 dark:text-gray-400">Track your physical and intangible assets</p>
        </div>
        <Button onClick={openNewAsset} leftIcon={<Plus className="w-4 h-4" />}>
          Add Asset
        </Button>
      </div>

      {/* Summary */}
      {assets.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Total Value</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatCurrency(totalValue)}</p>
          </Card>
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Total Purchase Price</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatCurrency(totalPurchase)}</p>
          </Card>
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Gain/Loss</p>
            <p className={`text-2xl font-bold ${totalGainLoss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {totalGainLoss >= 0 ? '+' : ''}{formatCurrency(totalGainLoss)}
              {gainLossPercent !== 0 && (
                <span className="text-sm ml-2">({gainLossPercent >= 0 ? '+' : ''}{gainLossPercent.toFixed(1)}%)</span>
              )}
            </p>
          </Card>
        </div>
      )}

      {/* Assets Grid */}
      {assets.length === 0 ? (
        <Card variant="elevated" className="p-12 text-center">
          <Building2 className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">No assets yet</h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">Add your first real estate, vehicle, or other asset</p>
          <Button onClick={openNewAsset} leftIcon={<Plus className="w-4 h-4" />}>
            Add Asset
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {assets.map((asset) => {
            const assetType = ASSET_TYPES.find(t => t.value === asset.type) || ASSET_TYPES[ASSET_TYPES.length - 1];
            const gainLoss = (asset.currentValue || 0) - (asset.purchasePrice || 0);
            const gainLossPct = asset.purchasePrice > 0 ? (gainLoss / asset.purchasePrice) * 100 : 0;

            return (
              <Card key={asset.id} variant="elevated" className="p-4 relative overflow-hidden">
                <div
                  className="absolute top-0 left-0 w-1 h-full"
                  style={{ backgroundColor: assetType.color }}
                />
                <div className="pl-3">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg" style={{ backgroundColor: `${assetType.color}20` }}>
                        <span style={{ color: assetType.color }}>{assetType.icon}</span>
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900 dark:text-white">{asset.name}</h3>
                        <p className="text-sm text-gray-500 capitalize">{asset.type?.replace('_', ' ')}</p>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => openEditAsset(asset)}
                        className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => asset.id && handleDelete(asset.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="mb-2">
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {formatCurrency(asset.currentValue || 0, asset.currency)}
                    </p>
                    {asset.location && (
                      <p className="text-xs text-gray-500">📍 {asset.location}</p>
                    )}
                  </div>

                  {asset.purchasePrice > 0 && (
                    <div className="flex items-center justify-between text-xs text-gray-500 mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                      <span>Purchase: {formatCurrency(asset.purchasePrice, asset.currency)}</span>
                      <Badge variant={gainLoss >= 0 ? 'success' : 'error'} size="sm">
                        {gainLoss >= 0 ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
                        {gainLossPct >= 0 ? '+' : ''}{gainLossPct.toFixed(1)}%
                      </Badge>
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                {editingAsset ? 'Edit Asset' : 'Add Asset'}
              </h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Asset Name *</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Bangkok Condo"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Asset Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {ASSET_TYPES.map((accType) => (
                    <button
                      key={accType.value}
                      type="button"
                      className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-colors ${formData.type === accType.value
                        ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30'
                        : 'border-gray-200 dark:border-gray-600 hover:border-purple-300'
                        }`}
                      onClick={() => setFormData({ ...formData, type: accType.value })}
                    >
                      {accType.icon}
                      <span className="text-sm">{accType.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Purchase Price</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    value={formData.purchasePrice}
                    onChange={(e) => setFormData({ ...formData, purchasePrice: parseFloat(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Current Value</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    value={formData.currentValue}
                    onChange={(e) => setFormData({ ...formData, currentValue: parseFloat(e.target.value) || 0 })}
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Location</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                  placeholder="e.g. Bangkok, Thailand"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
                <textarea
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                />
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700">
              <Button variant="ghost" onClick={() => setShowModal(false)}>Cancel</Button>
              <Button onClick={handleSave} leftIcon={<Check className="w-4 h-4" />}>
                {editingAsset ? 'Update' : 'Add'} Asset
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
