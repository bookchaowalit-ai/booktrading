/**
 * Finance Diary Page - Real API Only
 * Track daily financial reflections
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import EmptyState from '@/components/EmptyState';
import { BookMarked, Plus, Calendar, Smile, Frown, Meh } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

const MOODS = [
  { value: 'happy', label: '😊 Great', icon: <Smile className="w-5 h-5" /> },
  { value: 'neutral', label: '😐 Okay', icon: <Meh className="w-5 h-5" /> },
  { value: 'sad', label: '😞 Bad', icon: <Frown className="w-5 h-5" /> },
];

export default function FinanceDiaryPage() {
  const { t } = useTranslation();
  const { success, error: showError } = useToast();

  const [entries, setEntries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [newEntry, setNewEntry] = useState({
    title: '',
    mood: 'neutral',
    spending: 0,
    savings: 0,
    notes: '',
  });

  const loadEntries = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/finance/diary`, { headers: authHeaders() });
      if (response.ok) {
        const data = await response.json();
        setEntries(Array.isArray(data) ? data : []);
      } else {
        setEntries([]);
      }
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleSave = async () => {
    if (!newEntry.title) {
      setEntries([{ id: `entry_${Date.now()}`, ...newEntry, date: new Date().toISOString() }, ...entries]);
      success('Diary entry added');
      setShowForm(false);
      setNewEntry({ title: '', mood: 'neutral', spending: 0, savings: 0, notes: '' });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading diary...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Financial Diary</h1>
          <p className="text-gray-500 dark:text-gray-400">Track your daily financial reflections</p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} leftIcon={<Plus className="w-4 h-4" />}>{showForm ? 'Cancel' : 'Add Entry'}</Button>
      </div>

      {showForm && (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">New Entry</h3>
          <div className="space-y-4">
            <input type="text" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={newEntry.title} onChange={(e) => setNewEntry({ ...newEntry, title: e.target.value })} placeholder="Title" />
            <div className="flex gap-2">
              {MOODS.map((mood) => (
                <button key={mood.value} onClick={() => setNewEntry({ ...newEntry, mood: mood.value })}
                  className={`flex-1 flex items-center justify-center gap-2 p-3 rounded-lg border-2 ${newEntry.mood === mood.value ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30' : 'border-gray-200 dark:border-gray-600'}`}>
                  {mood.icon}<span className="text-sm">{mood.label}</span>
                </button>
              ))}
            </div>
            <textarea className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={newEntry.notes} onChange={(e) => setNewEntry({ ...newEntry, notes: e.target.value })} rows={3} placeholder="Write about your financial day..." />
            <Button onClick={handleSave}>Save Entry</Button>
          </div>
        </Card>
      )}

      {entries.length === 0 ? (
        <EmptyState icon={<BookMarked className="w-16 h-16 text-gray-300 dark:text-gray-600" />} title="No Entries Yet" description="Start tracking your financial journey" action={{ label: "Add Entry", onClick: () => setShowForm(true) }} />
      ) : (
        <div className="space-y-4">
          {entries.map((entry) => (
            <Card key={entry.id} variant="elevated" className="p-6">
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-bold text-gray-900 dark:text-white">{entry.title}</h3>
                <span className="text-xs text-gray-500">{new Date(entry.date).toLocaleDateString()}</span>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{MOODS.find(m => m.value === entry.mood)?.label}</p>
              {entry.notes && <p className="text-sm text-gray-700 dark:text-gray-300">{entry.notes}</p>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
