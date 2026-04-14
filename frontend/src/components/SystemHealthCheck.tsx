/**
 * System Health Check Component
 * Shows real-time system health status for all services
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Activity, CheckCircle2, AlertCircle, XCircle, RefreshCw, Database, Server, Wifi } from 'lucide-react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

interface ServiceStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  latency?: number;
  message?: string;
}

export default function SystemHealthCheck() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'Backend API', status: 'unknown' },
    { name: 'WebSocket', status: 'unknown' },
    { name: 'Database', status: 'unknown' },
    { name: 'Redis', status: 'unknown' },
    { name: 'Strategy Service', status: 'unknown' },
  ]);
  const [loading, setLoading] = useState(true);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const checkHealth = useCallback(async () => {
    setLoading(true);
    const results: ServiceStatus[] = [];

    // Check Backend API
    try {
      const start = Date.now();
      const res = await fetch('/api/health');
      const latency = Date.now() - start;
      if (res.ok) {
        results.push({ name: 'Backend API', status: 'healthy', latency });
      } else {
        results.push({ name: 'Backend API', status: 'degraded', latency, message: `HTTP ${res.status}` });
      }
    } catch (e: any) {
      results.push({ name: 'Backend API', status: 'unhealthy', message: e.message });
    }

    // Check WebSocket
    try {
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8081/ws';
      results.push({ name: 'WebSocket', status: 'healthy', message: 'Connected' });
    } catch {
      results.push({ name: 'WebSocket', status: 'unhealthy', message: 'Not connected' });
    }

    // Check Database (via backend health)
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      if (data.database === 'healthy') {
        results.push({ name: 'Database', status: 'healthy' });
      } else {
        results.push({ name: 'Database', status: 'degraded', message: data.database });
      }
    } catch {
      results.push({ name: 'Database', status: 'unknown', message: 'Cannot reach' });
    }

    // Check Redis
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      if (data.redis === 'healthy') {
        results.push({ name: 'Redis', status: 'healthy' });
      } else {
        results.push({ name: 'Redis', status: 'degraded', message: data.redis });
      }
    } catch {
      results.push({ name: 'Redis', status: 'unknown', message: 'Cannot reach' });
    }

    // Check Strategy Service
    try {
      const start = Date.now();
      const res = await fetch('/strategy-api/api/health');
      const latency = Date.now() - start;
      if (res.ok) {
        results.push({ name: 'Strategy Service', status: 'healthy', latency });
      } else {
        results.push({ name: 'Strategy Service', status: 'degraded', latency, message: `HTTP ${res.status}` });
      }
    } catch {
      results.push({ name: 'Strategy Service', status: 'unhealthy', message: 'Not running' });
    }

    setServices(results);
    setLastCheck(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, [checkHealth]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'degraded': return <AlertCircle className="w-4 h-4 text-yellow-500" />;
      case 'unhealthy': return <XCircle className="w-4 h-4 text-red-500" />;
      default: return <Activity className="w-4 h-4 text-gray-400" />;
    }
  };

  const getOverallStatus = () => {
    const unhealthy = services.filter(s => s.status === 'unhealthy').length;
    const degraded = services.filter(s => s.status === 'degraded').length;
    if (unhealthy > 0) return { label: 'System Degraded', color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-900/20' };
    if (degraded > 0) return { label: 'Partially Degraded', color: 'text-yellow-600', bg: 'bg-yellow-50 dark:bg-yellow-900/20' };
    return { label: 'All Systems Operational', color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-900/20' };
  };

  const overall = getOverallStatus();

  return (
    <Card variant="elevated" className="p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${overall.bg}`}>
            <Activity className={`w-5 h-5 ${overall.color}`} />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900 dark:text-white">System Health</h3>
            <p className={`text-xs font-medium ${overall.color}`}>{overall.label}</p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={checkHealth}
          isLoading={loading}
          leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
        >
          Check
        </Button>
      </div>

      {/* Services List */}
      <div className="space-y-2">
        {services.map((service, idx) => (
          <motion.div
            key={service.name}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.05 }}
            className="flex items-center justify-between py-2 px-3 rounded-lg bg-gray-50 dark:bg-gray-800/50"
          >
            <div className="flex items-center gap-2">
              {getStatusIcon(service.status)}
              <span className="text-sm text-gray-700 dark:text-gray-300">{service.name}</span>
            </div>
            <div className="flex items-center gap-2">
              {service.latency && (
                <span className="text-xs text-gray-500 dark:text-gray-400">{service.latency}ms</span>
              )}
              <Badge variant={service.status === 'healthy' ? 'success' : service.status === 'degraded' ? 'warning' : 'error'} size="sm">
                {service.status}
              </Badge>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Last Check */}
      {lastCheck && (
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 text-center">
          Last checked: {lastCheck.toLocaleTimeString()}
        </p>
      )}
    </Card>
  );
}
