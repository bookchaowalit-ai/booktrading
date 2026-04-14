/**
 * WebSocket Status Indicator
 * Shows connection status with compact badge
 */
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Wifi, WifiOff } from 'lucide-react';
import Tooltip from './ui/Tooltip';
import Badge from './ui/Badge';

interface WSStatus {
  connected: boolean;
  lastMessage?: Date;
}

export function WSStatusIndicator() {
  const [status, setStatus] = useState<WSStatus>({ connected: false });

  useEffect(() => {
    // Check WebSocket status from store or service
    const checkStatus = () => {
      // This would connect to your WebSocket service
      // For now, simulate
      setStatus({
        connected: true,
        lastMessage: new Date(),
      });
    };

    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Tooltip content={status.connected ? 'Connected' : 'Disconnected'} position="bottom">
      <div className="flex items-center gap-1.5">
        {status.connected ? (
          <>
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              <Wifi className="w-3.5 h-3.5 text-green-600" />
            </motion.div>
            <Badge variant="success" size="sm">Live</Badge>
          </>
        ) : (
          <>
            <WifiOff className="w-3.5 h-3.5 text-gray-400" />
            <Badge variant="default" size="sm">Offline</Badge>
          </>
        )}
      </div>
    </Tooltip>
  );
}
