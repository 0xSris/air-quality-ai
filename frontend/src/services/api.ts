import axios from "axios";
import {
  AlertsResponse,
  DatasetSummaryResponse,
  ForecastResponse,
  LiveNetworkResponse,
  LiveResponse,
  ModelMetadataResponse,
  TrendResponse,
} from "../types/api";
import {
  AuthResponse,
  ExportResponse,
  KnowledgeGraphResponse,
  ResearchQueryResponse,
  SessionDetail,
  SessionSummary,
  DashboardContext,
  UserProfile,
} from "../types/research";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
});

export const fetchDatasetSummary = async (): Promise<DatasetSummaryResponse> => {
  const response = await api.get("/data/summary");
  return response.data;
};

export const fetchHistoricalTrend = async (siteId: number): Promise<TrendResponse> => {
  const response = await api.get(`/data/historical/${siteId}?hours=168`);
  return response.data;
};

export const fetchLiveData = async (siteId: number): Promise<LiveResponse> => {
  const response = await api.get(`/data/live/${siteId}`);
  return response.data;
};

export const fetchLiveNetwork = async (scope: "india" | "global"): Promise<LiveNetworkResponse> => {
  const response = await api.get("/data/live-network", { params: { scope } });
  return response.data;
};

export const fetchForecast = async (
  siteId: number,
  options?: { horizonHours?: number; modelName?: string | null },
): Promise<ForecastResponse> => {
  const response = await api.post("/forecast", {
    site_id: siteId,
    horizon_hours: options?.horizonHours ?? 24,
    model_name: options?.modelName ?? undefined,
  });
  return response.data;
};

export const fetchAlerts = async (siteId?: number): Promise<AlertsResponse> => {
  const response = await api.get("/forecast/alerts", { params: siteId ? { site_id: siteId } : {} });
  return response.data;
};

export const fetchModelMetadata = async (): Promise<ModelMetadataResponse> => {
  const response = await api.get("/forecast/metadata");
  return response.data;
};

export const setApiToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
};

export const signUp = async (payload: {
  email: string;
  password: string;
  display_name: string;
}): Promise<AuthResponse> => {
  const response = await api.post("/auth/signup", payload);
  return response.data;
};

export const signIn = async (payload: { email: string; password: string }): Promise<AuthResponse> => {
  const response = await api.post("/auth/signin", payload);
  return response.data;
};

export const signOut = async (): Promise<void> => {
  await api.post("/auth/signout");
};

export const fetchMe = async (): Promise<UserProfile> => {
  const response = await api.get("/auth/me");
  return response.data;
};

export const fetchResearchSessions = async (): Promise<SessionSummary[]> => {
  const response = await api.get("/research/sessions");
  return response.data;
};

export const createResearchSession = async (payload: {
  title?: string;
  mode: string;
  depth: string;
  tags?: string[];
}): Promise<SessionSummary> => {
  const response = await api.post("/research/sessions", payload);
  return response.data;
};

export const updateResearchSession = async (
  sessionId: string,
  payload: Partial<{
    title: string;
    pinned: boolean;
    bookmarked: boolean;
    compare_selected: boolean;
    tags: string[];
  }>,
): Promise<SessionSummary> => {
  const response = await api.patch(`/research/sessions/${sessionId}`, payload);
  return response.data;
};

export const deleteResearchSession = async (sessionId: string): Promise<void> => {
  await api.delete(`/research/sessions/${sessionId}`);
};

export const fetchResearchSessionDetail = async (sessionId: string): Promise<SessionDetail> => {
  const response = await api.get(`/research/sessions/${sessionId}`);
  return response.data;
};

export const runResearchQuery = async (payload: {
  session_id?: string;
  query: string;
  mode: string;
  depth: string;
  site_id?: number;
  network_scope: "india" | "global";
  dashboard_context?: DashboardContext;
}): Promise<ResearchQueryResponse> => {
  const response = await api.post("/research/query", payload);
  return response.data;
};

export const exportResearchReport = async (
  sessionId: string,
  reportId: string,
  format: "json" | "markdown" | "pdf",
): Promise<ExportResponse> => {
  const response = await api.get(`/research/sessions/${sessionId}/reports/${reportId}/export`, {
    params: { format },
  });
  return response.data;
};

export const fetchKnowledgeGraph = async (): Promise<KnowledgeGraphResponse> => {
  const response = await api.get("/research/graph");
  return response.data;
};

export const submitResearchFeedback = async (payload: {
  report_id: string;
  target_type: "summary" | "section" | "source";
  target_key: string;
  value: "positive" | "negative";
  notes?: string;
}): Promise<void> => {
  await api.post("/research/feedback", payload);
};
