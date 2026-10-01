/**
 * Shows a Thai toast whenever a backend call is refused with 403 (admin-only
 * route called from a non-admin session). Mount once inside ToastProvider.
 */
'use client';

import { useEffect } from 'react';
import { useToast } from '@/components/ui/Toast';
import {
  FORBIDDEN_EVENT,
  installForbiddenWatcher,
  type ForbiddenEventDetail,
} from '@/services/forbidden';

export default function ForbiddenNotice() {
  const { showToast } = useToast();

  useEffect(() => {
    const uninstall = installForbiddenWatcher();
    const onForbidden = (e: Event) => {
      const detail = (e as CustomEvent<ForbiddenEventDetail>).detail;
      if (detail?.message) showToast(detail.message, 'warning', 7000);
    };
    window.addEventListener(FORBIDDEN_EVENT, onForbidden);
    return () => {
      window.removeEventListener(FORBIDDEN_EVENT, onForbidden);
      uninstall();
    };
  }, [showToast]);

  return null;
}
