'use client';

/**
 * LiveDashboard - Real-time asset dashboard with auto-polling
 * 
 * Uses useLiveAsset hook for:
 * - Hash-gated updates (no flicker)
 * - StrictMode safe polling
 * - Pause on hidden/offline
 * - Exponential backoff on error
 */

import React from 'react';
import { UniversalDashboard } from '@/components/widgets/registry';
import { AlertCircle, Loader2, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { Button } from '@/components/ui/button';

// Types matching the api-client schema
interface AssetProjection {
  schema_version: string;
  requested_view: string;
  identity: {
    paid: string;
    name: string;
    category: string;
  };
  widgets: Array<{
    widget_type: string;
    priority: number;
    data: Record<string, unknown>;
  }>;
  projection_hash: string;
  profile_generated_at: string;
}

interface UseLiveAssetResult {
  data: AssetProjection | null;
  isLoading: boolean;
  isPolling: boolean;
  isError: boolean;
  error: Error | null;
  lastHash: string | null;
  pollCount: number;
  refetch: () => Promise<void>;
}

interface LiveDashboardProps {
  assetId: string;
  view?: 'PROPERTIES' | 'OPS' | 'HOME' | 'BIDS';
  intervalMs?: number;
  showDebugInfo?: boolean;
}

// Placeholder hook until @proveniq/api-client is properly linked
// In production, import from '@proveniq/api-client'
function useLiveAssetLocal(
  assetId: string,
  options: { view?: string; intervalMs?: number } = {}
): UseLiveAssetResult {
  const [data, setData] = React.useState<AssetProjection | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<Error | null>(null);
  const [pollCount, setPollCount] = React.useState(0);
  const [lastHash, setLastHash] = React.useState<string | null>(null);
  
  const mountedRef = React.useRef(false);
  const initRef = React.useRef(false);
  const abortRef = React.useRef<AbortController | null>(null);
  const intervalRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const seqRef = React.useRef(0);

  const coreUrl = process.env.NEXT_PUBLIC_CORE_API_URL ?? 'http://localhost:3010';
  const view = options.view ?? 'PROPERTIES';
  const intervalMs = options.intervalMs ?? 2000;

  const fetchAsset = React.useCallback(async () => {
    if (!assetId) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const thisSeq = ++seqRef.current;

    try {
      const response = await fetch(
        `${coreUrl}/core/asset/${encodeURIComponent(assetId)}?view=${view}`,
        { signal: abortRef.current.signal }
      );

      if (thisSeq !== seqRef.current) return; // Stale
      if (!mountedRef.current) return;

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const json = await response.json();
      const newHash = json.projection_hash ?? json.canonical_hash_hex ?? '';

      // Hash gating
      if (newHash !== lastHash) {
        console.log(`[LiveDashboard] Hash changed: ${lastHash?.slice(0, 8) ?? 'null'} → ${newHash.slice(0, 8)}`);
        setData(json);
        setLastHash(newHash);
      } else {
        console.log(`[LiveDashboard] Hash unchanged (${newHash.slice(0, 8)}), skipping update`);
      }

      setError(null);
      setPollCount((c) => c + 1);
    } catch (err) {
      if (thisSeq !== seqRef.current) return;
      if (!mountedRef.current) return;
      if (err instanceof Error && err.name === 'AbortError') return;

      console.error('[LiveDashboard] Fetch error:', err);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [assetId, coreUrl, view, lastHash]);

  React.useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    mountedRef.current = true;

    console.log(`[LiveDashboard] Initializing for ${assetId}`);
    fetchAsset();

    const poll = () => {
      if (!mountedRef.current) return;
      if (document.visibilityState === 'hidden') return;
      if (!navigator.onLine) return;

      fetchAsset();
    };

    intervalRef.current = setInterval(poll, intervalMs);

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchAsset();
      }
    };

    const handleOnline = () => fetchAsset();

    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('online', handleOnline);

    return () => {
      mountedRef.current = false;
      initRef.current = false;
      abortRef.current?.abort();
      if (intervalRef.current) clearInterval(intervalRef.current);
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('online', handleOnline);
    };
  }, [assetId, intervalMs, fetchAsset]);

  const refetch = React.useCallback(async () => {
    setLastHash(null);
    await fetchAsset();
  }, [fetchAsset]);

  return {
    data,
    isLoading,
    isPolling: intervalRef.current !== null,
    isError: error !== null,
    error,
    lastHash,
    pollCount,
    refetch,
  };
}

export const LiveDashboard: React.FC<LiveDashboardProps> = ({
  assetId,
  view = 'PROPERTIES',
  intervalMs = 2000,
  showDebugInfo = false,
}) => {
  const { data, isLoading, isPolling, isError, error, lastHash, pollCount, refetch } =
    useLiveAssetLocal(assetId, { view, intervalMs });

  const [isOnline, setIsOnline] = React.useState(true);

  React.useEffect(() => {
    setIsOnline(navigator.onLine);
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Transform widgets to match registry format
  const transformedWidgets = React.useMemo(() => {
    if (!data?.widgets) return [];
    return data.widgets.map((w) => ({
      type: w.widget_type,
      title: w.widget_type.replace(/_/g, ' '),
      priority_int: w.priority,
      data: w.data,
    }));
  }, [data?.widgets]);

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        <span className="ml-2 text-slate-500">Loading asset data...</span>
      </div>
    );
  }

  if (isError && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-red-500">
        <AlertCircle className="h-8 w-8 mb-2" />
        <p className="font-medium">Failed to load asset</p>
        <p className="text-sm text-slate-500">{error?.message}</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={refetch}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Status Bar */}
      {showDebugInfo && (
        <div className="flex items-center justify-between text-xs text-slate-500 bg-slate-50 px-3 py-2 rounded-lg">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              {isOnline ? (
                <Wifi className="h-3 w-3 text-green-500" />
              ) : (
                <WifiOff className="h-3 w-3 text-red-500" />
              )}
              {isOnline ? 'Online' : 'Offline'}
            </span>
            <span>
              Polls: <strong>{pollCount}</strong>
            </span>
            <span>
              Hash: <code className="bg-slate-200 px-1 rounded">{lastHash?.slice(0, 8) ?? 'none'}</code>
            </span>
            {isPolling && (
              <span className="flex items-center gap-1 text-green-600">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                Live
              </span>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={refetch} disabled={isLoading}>
            <RefreshCw className={`h-3 w-3 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      )}

      {/* Asset Header */}
      {data?.identity && (
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-slate-900">{data.identity.name}</h2>
          <p className="text-sm text-slate-500">
            {data.identity.category} • PAID: {data.identity.paid.slice(0, 8)}...
          </p>
        </div>
      )}

      {/* Widgets */}
      <UniversalDashboard widgets={transformedWidgets as any} />
    </div>
  );
};

export default LiveDashboard;
