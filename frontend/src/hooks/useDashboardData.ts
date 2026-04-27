import { useEffect, useState } from "react";
import {
  fetchAlerts,
  fetchDatasetSummary,
  fetchForecast,
  fetchHistoricalTrend,
  fetchLiveData,
  fetchLiveNetwork,
  fetchModelMetadata,
} from "../services/api";
import {
  AlertsResponse,
  DatasetSummaryResponse,
  ForecastResponse,
  LiveNetworkResponse,
  LiveResponse,
  ModelMetadataResponse,
  TrendResponse,
} from "../types/api";

export function useDashboardData(
  siteId: number,
  networkScope: "india" | "global",
  horizonHours = 24,
  modelName: string | null = null,
) {
  const [summary, setSummary] = useState<DatasetSummaryResponse | null>(null);
  const [trend, setTrend] = useState<TrendResponse | null>(null);
  const [live, setLive] = useState<LiveResponse | null>(null);
  const [liveNetwork, setLiveNetwork] = useState<LiveNetworkResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertsResponse | null>(null);
  const [metadata, setMetadata] = useState<ModelMetadataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [networkRefreshing, setNetworkRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null);
  const [lastNetworkLoadedAt, setLastNetworkLoadedAt] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshIntervalMs, setRefreshIntervalMs] = useState(15000);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    let active = true;

    async function loadCore(isInitial = false) {
      if (isInitial) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }

      try {
        const [summaryData, trendData, liveData, forecastData, alertData, metadataData] = await Promise.all([
          fetchDatasetSummary(),
          fetchHistoricalTrend(siteId),
          fetchLiveData(siteId),
          fetchForecast(siteId, { horizonHours, modelName }),
          fetchAlerts(siteId),
          fetchModelMetadata(),
        ]);

        if (!active) return;

        setSummary(summaryData);
        setTrend(trendData);
        setLive(liveData);
        setForecast(forecastData);
        setAlerts(alertData);
        setMetadata(metadataData);
        setError(null);
        setLastLoadedAt(new Date().toISOString());
      } catch (loadError) {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : "Failed to refresh dashboard data.");
      } finally {
        if (!active) return;
        setLoading(false);
        setRefreshing(false);
      }
    }

    void loadCore(true);
    const interval = autoRefresh ? window.setInterval(() => void loadCore(false), refreshIntervalMs) : null;

    return () => {
      active = false;
      if (interval !== null) {
        window.clearInterval(interval);
      }
    };
  }, [siteId, horizonHours, modelName, autoRefresh, refreshIntervalMs, refreshTick]);

  useEffect(() => {
    let active = true;

    async function loadNetwork() {
      setNetworkRefreshing(true);
      try {
        const networkData = await fetchLiveNetwork(networkScope);
        if (!active) return;
        setLiveNetwork(networkData);
        setNetworkError(null);
        setLastNetworkLoadedAt(new Date().toISOString());
      } catch (loadError) {
        if (!active) return;
        setNetworkError(loadError instanceof Error ? loadError.message : "Failed to refresh live network.");
      } finally {
        if (!active) return;
        setNetworkRefreshing(false);
      }
    }

    void loadNetwork();
    const networkInterval = autoRefresh ? window.setInterval(() => void loadNetwork(), Math.max(refreshIntervalMs * 4, 60000)) : null;

    return () => {
      active = false;
      if (networkInterval !== null) {
        window.clearInterval(networkInterval);
      }
    };
  }, [networkScope, autoRefresh, refreshIntervalMs, refreshTick]);

  return {
    summary,
    trend,
    live,
    liveNetwork,
    forecast,
    alerts,
    metadata,
    loading,
    refreshing,
    networkRefreshing,
    error,
    networkError,
    lastLoadedAt,
    lastNetworkLoadedAt,
    autoRefresh,
    refreshIntervalMs,
    setAutoRefresh,
    setRefreshIntervalMs,
    refreshNow: () => setRefreshTick((value) => value + 1),
  };
}
